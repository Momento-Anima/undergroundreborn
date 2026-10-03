/* The Underground: Reborn - Discord login, admin gate and appeals (Cloudflare Worker at api.theundergroundserver.com).
 *
 * Routes
 *   /login        send the visitor to Discord to approve the login
 *   /callback     Discord sends them back; we read who they are, whether they are in our server and
 *                 whether they hold an admin role, and set a signed session cookie
 *   /me           JSON for the site: { loggedIn, id, name, avatar, inGuild, staff }
 *   /logout       clear the cookie
 *   /appeal       POST (members only): a report / appeal / bug / application, posted to a private admin
 *                 channel through a Discord webhook
 *   /admin/players GET (admins only): who is online and where, from the CFTools Data API (live.position)
 *   /admin/hub    GET (admins only): the admin page's content. Served from here, NOT from the public
 *                 static site, because anything in the repo is public.
 *
 * Settings (Worker > Settings > Variables and Secrets)
 *   CLIENT_ID        text    Discord application's Client ID (public)
 *   GUILD_ID         text    our PUBLIC Discord server's ID ("The Underground")
 *   STAFF_ROLE_IDS   text    comma-separated role IDs in that server that count as staff
 *   CLIENT_SECRET    secret  Discord application's Client Secret
 *   SESSION_SECRET   secret  any long random string; signs the session cookie
 *   CFTOOLS_APP_ID    text    CFTools Data API application ID (developer.cftools.cloud)
 *   CFTOOLS_SERVER_ID text    the server's "Server API ID" in CFTools Cloud
 *   CFTOOLS_SECRET    secret  the CFTools application's secret
 *   APPEALS_WEBHOOK  secret  Discord webhook URL of the private admin channel (appeals)
 *   TUR_KV           binding (optional) a KV namespace; if present it rate-limits /appeal per person
 *
 * We keep nothing: Discord's access token is used once, during /callback, and thrown away. The cookie
 * holds only the Discord ID, display name, avatar hash, "is in our server" and "is an admin" (the flag is still called staff in code and in STAFF_ROLE_IDS).
 * Admin sessions last 8 hours (so removing an admin role takes effect the same day); everyone else's last 7 days.
 */
const SITE = 'https://theundergroundserver.com';
const API = 'https://api.theundergroundserver.com';
const COOKIE = 'tur_session';
const STATE = 'tur_state';
const DAY = 24 * 3600;
const enc = new TextEncoder();

// Starter links for the admin page. Links only, never secrets: this file is public.
const STAFF_LINKS = [
  { group: 'Server', title: 'Game server panel (Gatz)', url: 'https://gamepanel.gatzgamehosting.com', note: 'Restarts, mod list, files' },
  { group: 'Server', title: 'Server in the DZSA launcher', url: 'https://dayzsalauncher.com', note: 'Check the live listing' },
  { group: 'Project', title: 'Project board', url: 'https://github.com/orgs/Momento-Anima/projects/2', note: 'What is planned and in progress' },
  { group: 'Website', title: 'Visitor statistics (Google Analytics)', url: 'https://analytics.google.com', note: 'Property: theundergroundserver.com' },
  { group: 'Website', title: 'Cloudflare (DNS and the login Worker)', url: 'https://dash.cloudflare.com', note: 'Owner only' },
];

const KINDS = { appeal: 'Ban appeal', report: 'Player report', bug: 'Bug report', application: 'Admin application', other: 'Other' };

const b64u = (bytes) => btoa(String.fromCharCode(...bytes)).replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/, '');
const unb64u = (s) => Uint8Array.from(atob(s.replace(/-/g, '+').replace(/_/g, '/')), (c) => c.charCodeAt(0));

const hmacKey = (secret) => crypto.subtle.importKey('raw', enc.encode(secret), { name: 'HMAC', hash: 'SHA-256' }, false, ['sign', 'verify']);
async function sign(secret, payload) {
  const body = b64u(enc.encode(JSON.stringify(payload)));
  const sig = new Uint8Array(await crypto.subtle.sign('HMAC', await hmacKey(secret), enc.encode(body)));
  return body + '.' + b64u(sig);
}
async function verify(secret, token) {
  if (!token || !token.includes('.')) return null;
  const [body, sig] = token.split('.');
  let ok = false;
  try { ok = await crypto.subtle.verify('HMAC', await hmacKey(secret), unb64u(sig), enc.encode(body)); } catch (e) { return null; }
  if (!ok) return null;
  const data = JSON.parse(new TextDecoder().decode(unb64u(body)));
  return data.exp > Date.now() / 1000 ? data : null;
}

function cookies(req) {
  const out = {};
  (req.headers.get('Cookie') || '').split(/;\s*/).forEach((p) => { const i = p.indexOf('='); if (i > 0) out[p.slice(0, i)] = p.slice(i + 1); });
  return out;
}
const setCookie = (name, value, maxAge, domain) =>
  `${name}=${value}; ${domain ? 'Domain=' + domain + '; ' : ''}Path=/; Max-Age=${maxAge}; HttpOnly; Secure; SameSite=Lax`;

function redirect(to, ...setCookies) {
  const h = new Headers({ Location: to });
  setCookies.forEach((c) => h.append('Set-Cookie', c));
  return new Response(null, { status: 302, headers: h });
}

const json = (cors, body, status = 200) =>
  new Response(JSON.stringify(body), { status, headers: { ...cors, 'Content-Type': 'application/json', 'Cache-Control': 'no-store' } });

const avatarUrl = (s) => (s.avatar
  ? `https://cdn.discordapp.com/avatars/${s.id}/${s.avatar}.png?size=64`
  : `https://cdn.discordapp.com/embed/avatars/${Number((BigInt(s.id) >> 22n) % 6n)}.png`);

async function session(req, env) {
  return verify(env.SESSION_SECRET, cookies(req)[COOKIE]);
}

async function appeal(req, env, cors) {
  const s = await session(req, env);
  if (!s) return json(cors, { ok: false, error: 'Log in with Discord first.' }, 401);
  if (!s.inGuild) return json(cors, { ok: false, error: 'You need to be a member of our Discord server to send this.' }, 403);
  // Only our own pages may POST (cookies are SameSite=Lax too; this is a second lock).
  if (req.headers.get('Origin') !== SITE) return json(cors, { ok: false, error: 'Not allowed.' }, 403);
  let b;
  try { b = await req.json(); } catch (e) { return json(cors, { ok: false, error: 'Bad request.' }, 400); }
  const kind = KINDS[b.kind] ? b.kind : 'other';
  const who = String(b.who || '').trim().slice(0, 120);
  const text = String(b.text || '').trim();
  if (text.length < 20) return json(cors, { ok: false, error: 'Please write a little more (at least 20 characters).' }, 400);
  if (text.length > 1800) return json(cors, { ok: false, error: 'That is too long (1,800 characters at most).' }, 400);
  if (!env.APPEALS_WEBHOOK) return json(cors, { ok: false, error: 'This form is not set up yet.' }, 503);
  if (env.TUR_KV) {
    const key = 'appeal:' + s.id;
    if (await env.TUR_KV.get(key)) return json(cors, { ok: false, error: 'You sent one a moment ago. Please wait 10 minutes before sending another.' }, 429);
    await env.TUR_KV.put(key, '1', { expirationTtl: 600 });
  }
  const r = await fetch(env.APPEALS_WEBHOOK, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      username: 'Website',
      allowed_mentions: { parse: [] },   // never let a submission ping anyone
      embeds: [{
        title: KINDS[kind],
        description: text,
        color: 0xe8622c,
        fields: [
          { name: 'From', value: `<@${s.id}> (${s.name}, ${s.id})`, inline: false },
          { name: 'In-game name / Steam ID given', value: who || 'not given', inline: false },
        ],
        footer: { text: 'Sent from theundergroundserver.com' },
        timestamp: new Date().toISOString(),
      }],
    }),
  });
  if (!r.ok) return json(cors, { ok: false, error: 'Could not deliver that. Please try again, or ask in Discord.' }, 502);
  return json(cors, { ok: true });
}


// ---- CFTools Data API (read-only): online players and their live positions ----
const CF = 'https://data.cftools.cloud';
let cfToken = { t: null, until: 0 };

async function cfAuth(env, force) {
  if (!force && cfToken.t && Date.now() < cfToken.until) return cfToken.t;
  const r = await fetch(CF + '/v1/auth/register', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', 'User-Agent': 'TUR-website-worker/1.0 (theundergroundserver.com)' },
    // Trim: a pasted secret can carry a trailing space or line break.
    body: JSON.stringify({ application_id: String(env.CFTOOLS_APP_ID).trim(), secret: String(env.CFTOOLS_SECRET).trim() }),
  });
  if (!r.ok) throw new Error('login to CFTools failed: ' + r.status + ' ' + (await r.text()).slice(0, 80));
  cfToken = { t: (await r.json()).token, until: Date.now() + 20 * 3600 * 1000 };
  return cfToken.t;
}

async function cfSessions(env) {
  const url = `${CF}/v1/server/${String(env.CFTOOLS_SERVER_ID).trim()}/GSM/list`;
  for (let attempt = 0; attempt < 2; attempt++) {
    const r = await fetch(url, { headers: { Authorization: 'Bearer ' + await cfAuth(env, attempt > 0), 'User-Agent': 'TUR-website-worker/1.0' } });
    if (r.status === 401 || r.status === 403) { cfToken = { t: null, until: 0 }; continue; }
    if (!r.ok) throw new Error('player list failed: ' + r.status + ' ' + (await r.text()).slice(0, 80));
    return (await r.json()).sessions || [];
  }
  throw new Error('CFTools refused the token: the application has no access to this server (check the grant and CFTOOLS_SERVER_ID)');
}

async function players(req, env, cors) {
  const s = await session(req, env);
  if (!s || !s.staff) return json(cors, { ok: false }, s ? 403 : 401);
  if (!env.CFTOOLS_APP_ID || !env.CFTOOLS_SECRET || !env.CFTOOLS_SERVER_ID) return json(cors, { ok: false, error: 'CFTools is not connected yet.' }, 503);
  // 8-second shared cache so a few admins refreshing do not hammer CFTools.
  const key = new Request('https://cache.invalid/admin-players');
  const hit = await caches.default.match(key);
  if (hit) return new Response(hit.body, { status: 200, headers: { ...cors, 'Content-Type': 'application/json', 'Cache-Control': 'no-store' } });
  let list;
  try { list = await cfSessions(env); } catch (e) { return json(cors, { ok: false, error: 'CFTools did not answer (' + e.message + ').' }, 502); }
  // Only what an admin needs. Never pass on IP addresses or locations.
  const out = list.map((x) => {
    const pos = x.live && x.live.position && (x.live.position.latest || x.live.position.join);
    return {
      name: (x.gamedata && x.gamedata.player_name) || '?',
      steam64: (x.gamedata && x.gamedata.steam64) || '',
      loaded: !!(x.live && x.live.loaded),
      ping: x.live && x.live.ping ? Math.round(x.live.ping.actual) : null,
      x: pos ? Math.round(pos[0]) : null,
      // CFTools orders the numbers (east, NORTH, height): NOT DayZ's (east, height, north) (cftools-sdk Coordinates note).
      z: pos ? Math.round(pos[1]) : null,   // north, the map's vertical axis
      y: pos ? Math.round(pos[2]) : null,   // height
    };
  });
  const body = JSON.stringify({ ok: true, updated: new Date().toISOString(), players: out });
  await caches.default.put(key, new Response(body, { headers: { 'Content-Type': 'application/json', 'Cache-Control': 'max-age=8' } }));
  return new Response(body, { status: 200, headers: { ...cors, 'Content-Type': 'application/json', 'Cache-Control': 'no-store' } });
}

export default {
  async fetch(req, env) {
    const url = new URL(req.url);
    const cors = {
      'Access-Control-Allow-Origin': SITE,
      'Access-Control-Allow-Credentials': 'true',
      'Access-Control-Allow-Headers': 'Content-Type',
      'Access-Control-Allow-Methods': 'GET, POST, OPTIONS',
      'Vary': 'Origin',
    };
    if (req.method === 'OPTIONS') return new Response(null, { status: 204, headers: cors });

    if (url.pathname === '/login') {
      const state = b64u(crypto.getRandomValues(new Uint8Array(16)));
      const q = new URLSearchParams({
        client_id: env.CLIENT_ID, response_type: 'code', redirect_uri: API + '/callback',
        scope: 'identify guilds guilds.members.read', state, prompt: 'none',
      });
      return redirect('https://discord.com/oauth2/authorize?' + q, setCookie(STATE, state, 600));
    }

    if (url.pathname === '/callback') {
      const code = url.searchParams.get('code');
      const state = url.searchParams.get('state');
      const fail = () => redirect(SITE + '/?login=failed', setCookie(STATE, '', 0));
      if (!code || !state || cookies(req)[STATE] !== state) return fail();
      const tok = await fetch('https://discord.com/api/oauth2/token', {
        method: 'POST',
        headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
        body: new URLSearchParams({
          client_id: env.CLIENT_ID, client_secret: env.CLIENT_SECRET, grant_type: 'authorization_code',
          code, redirect_uri: API + '/callback',
        }),
      });
      if (!tok.ok) return fail();
      const { access_token } = await tok.json();
      const auth = { headers: { Authorization: 'Bearer ' + access_token } };
      const [me, member] = await Promise.all([
        fetch('https://discord.com/api/users/@me', auth).then((r) => r.json()),
        // 404 if they are not in our server; otherwise includes their role IDs.
        fetch(`https://discord.com/api/users/@me/guilds/${env.GUILD_ID}/member`, auth).then((r) => (r.ok ? r.json() : null)),
      ]);
      if (!me.id) return fail();
      const staffRoles = String(env.STAFF_ROLE_IDS || '').split(',').map((x) => x.trim()).filter(Boolean);
      const staff = !!(member && Array.isArray(member.roles) && member.roles.some((r) => staffRoles.includes(r)));
      const life = staff ? 8 * 3600 : 7 * DAY;
      const sess = await sign(env.SESSION_SECRET, {
        id: me.id, name: me.global_name || me.username, avatar: me.avatar || null,
        inGuild: !!member, staff,
        exp: Math.floor(Date.now() / 1000) + life,
      });
      return redirect(SITE + '/', setCookie(COOKIE, sess, life, 'theundergroundserver.com'), setCookie(STATE, '', 0));
    }

    if (url.pathname === '/me') {
      const s = await session(req, env);
      return json(cors, s
        ? { loggedIn: true, id: s.id, name: s.name, inGuild: !!s.inGuild, staff: !!s.staff, avatar: avatarUrl(s) }
        : { loggedIn: false });
    }

    if (url.pathname === '/logout') {
      return redirect(SITE + '/', setCookie(COOKIE, '', 0, 'theundergroundserver.com'));
    }

    if (url.pathname === '/appeal' && req.method === 'POST') return appeal(req, env, cors);

    if (url.pathname === '/admin/players') return players(req, env, cors);

    if (url.pathname === '/admin/hub') {
      const s = await session(req, env);
      if (!s || !s.staff) return json(cors, { ok: false }, s ? 403 : 401);
      return json(cors, { ok: true, name: s.name, links: STAFF_LINKS });
    }

    return new Response('Not found', { status: 404 });
  },
};

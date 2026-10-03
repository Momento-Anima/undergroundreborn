/* The Underground: Reborn - Discord login (Cloudflare Worker, served at api.theundergroundserver.com).
 *
 * Routes
 *   /login     send the visitor to Discord to approve the login
 *   /callback  Discord sends them back here; we read who they are and set a session cookie
 *   /me        JSON for the site: { loggedIn, id, name, avatar, inGuild }
 *   /logout    clear the cookie
 *
 * Settings (Worker > Settings > Variables and Secrets)
 *   CLIENT_ID       text    Discord application's Client ID (public)
 *   GUILD_ID        text    our Discord server's ID (public)
 *   CLIENT_SECRET   secret  Discord application's Client Secret
 *   SESSION_SECRET  secret  any long random string; signs the session cookie
 *
 * We keep nothing: Discord's access token is used once, during /callback, and thrown away.
 * The cookie holds only the Discord ID, display name, avatar hash and "is in our server".
 */
const SITE = 'https://theundergroundserver.com';
const API = 'https://api.theundergroundserver.com';
const COOKIE = 'tur_session';
const STATE = 'tur_state';
const WEEK = 7 * 24 * 3600;
const enc = new TextEncoder();

const b64u = (bytes) => btoa(String.fromCharCode(...bytes)).replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/, '');
const unb64u = (s) => Uint8Array.from(atob(s.replace(/-/g, '+').replace(/_/g, '/')), (c) => c.charCodeAt(0));

async function hmac(secret, data) {
  const key = await crypto.subtle.importKey('raw', enc.encode(secret), { name: 'HMAC', hash: 'SHA-256' }, false, ['sign', 'verify']);
  return key;
}
async function sign(secret, payload) {
  const body = b64u(enc.encode(JSON.stringify(payload)));
  const sig = new Uint8Array(await crypto.subtle.sign('HMAC', await hmac(secret), enc.encode(body)));
  return body + '.' + b64u(sig);
}
async function verify(secret, token) {
  if (!token || !token.includes('.')) return null;
  const [body, sig] = token.split('.');
  let ok = false;
  try { ok = await crypto.subtle.verify('HMAC', await hmac(secret), unb64u(sig), enc.encode(body)); } catch (e) { return null; }
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

export default {
  async fetch(req, env) {
    const url = new URL(req.url);
    const cors = {
      'Access-Control-Allow-Origin': SITE,
      'Access-Control-Allow-Credentials': 'true',
      'Access-Control-Allow-Headers': 'Content-Type',
      'Vary': 'Origin',
    };
    if (req.method === 'OPTIONS') return new Response(null, { status: 204, headers: cors });

    if (url.pathname === '/login') {
      const state = b64u(crypto.getRandomValues(new Uint8Array(16)));
      const q = new URLSearchParams({
        client_id: env.CLIENT_ID, response_type: 'code', redirect_uri: API + '/callback',
        scope: 'identify guilds', state, prompt: 'none',
      });
      return redirect('https://discord.com/oauth2/authorize?' + q, setCookie(STATE, state, 600));
    }

    if (url.pathname === '/callback') {
      const code = url.searchParams.get('code');
      const state = url.searchParams.get('state');
      if (!code || !state || cookies(req)[STATE] !== state) return redirect(SITE + '/?login=failed', setCookie(STATE, '', 0));
      const tok = await fetch('https://discord.com/api/oauth2/token', {
        method: 'POST',
        headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
        body: new URLSearchParams({
          client_id: env.CLIENT_ID, client_secret: env.CLIENT_SECRET, grant_type: 'authorization_code',
          code, redirect_uri: API + '/callback',
        }),
      });
      if (!tok.ok) return redirect(SITE + '/?login=failed', setCookie(STATE, '', 0));
      const { access_token } = await tok.json();
      const auth = { headers: { Authorization: 'Bearer ' + access_token } };
      const [me, guilds] = await Promise.all([
        fetch('https://discord.com/api/users/@me', auth).then((r) => r.json()),
        fetch('https://discord.com/api/users/@me/guilds', auth).then((r) => (r.ok ? r.json() : [])),
      ]);
      if (!me.id) return redirect(SITE + '/?login=failed', setCookie(STATE, '', 0));
      const session = await sign(env.SESSION_SECRET, {
        id: me.id, name: me.global_name || me.username, avatar: me.avatar || null,
        inGuild: Array.isArray(guilds) && guilds.some((g) => g.id === env.GUILD_ID),
        exp: Math.floor(Date.now() / 1000) + WEEK,
      });
      return redirect(SITE + '/', setCookie(COOKIE, session, WEEK, 'theundergroundserver.com'), setCookie(STATE, '', 0));
    }

    if (url.pathname === '/me') {
      const s = await verify(env.SESSION_SECRET, cookies(req)[COOKIE]);
      const body = s
        ? { loggedIn: true, id: s.id, name: s.name, inGuild: s.inGuild,
            avatar: s.avatar ? `https://cdn.discordapp.com/avatars/${s.id}/${s.avatar}.png?size=64`
                             : `https://cdn.discordapp.com/embed/avatars/${Number((BigInt(s.id) >> 22n) % 6n)}.png` }
        : { loggedIn: false };
      return new Response(JSON.stringify(body), { headers: { ...cors, 'Content-Type': 'application/json', 'Cache-Control': 'no-store' } });
    }

    if (url.pathname === '/logout') {
      return redirect(SITE + '/', setCookie(COOKIE, '', 0, 'theundergroundserver.com'));
    }

    return new Response('Not found', { status: 404 });
  },
};

/* Appeals form and admin hub. Talks to the login Worker (window.TUR.api). Everything private is served by the
   Worker after a role check; nothing sensitive is in this file or the repo. */
(function () {
  var cfg = window.TUR || {};
  if (!cfg.api) return;

  function show(root, name) {
    Array.prototype.forEach.call(root.querySelectorAll('[data-state]'), function (el) {
      el.hidden = el.getAttribute('data-state') !== name;
    });
  }
  function loginLinks(root) {
    Array.prototype.forEach.call(root.querySelectorAll('[data-login]'), function (a) { a.href = cfg.api + '/login'; });
  }
  function me() {
    return fetch(cfg.api + '/me', { credentials: 'include', cache: 'no-store' }).then(function (r) { return r.json(); });
  }

  /* ---- appeals ---- */
  var ap = document.querySelector('[data-appeal]');
  if (ap) {
    loginLinks(ap);
    me().then(function (u) {
      if (!u.loggedIn) return show(ap, 'loggedout');
      if (!u.inGuild) return show(ap, 'notmember');
      show(ap, 'form');
    }).catch(function () { show(ap, 'loggedout'); });

    var form = ap.querySelector('form');
    var text = form.querySelector('#ap-text');
    var count = form.querySelector('[data-count]');
    var msg = form.querySelector('[data-msg]');
    text.addEventListener('input', function () { count.textContent = text.value.length; });
    form.addEventListener('submit', function (ev) {
      ev.preventDefault();
      msg.textContent = '';
      if (text.value.trim().length < 20) { msg.textContent = 'Please write a little more (at least 20 characters).'; return; }
      var btn = form.querySelector('button[type=submit]');
      btn.disabled = true;
      fetch(cfg.api + '/appeal', {
        method: 'POST', credentials: 'include',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ kind: form.kind.value, who: form.who.value, text: text.value })
      }).then(function (r) { return r.json().then(function (j) { return { ok: r.ok && j.ok, j: j }; }); })
        .then(function (res) {
          if (res.ok) { show(ap, 'sent'); return; }
          msg.textContent = (res.j && res.j.error) || 'Something went wrong. Please try again.';
          btn.disabled = false;
        })
        .catch(function () { msg.textContent = 'Could not reach the server. Please try again.'; btn.disabled = false; });
    });
  }

  /* ---- admin hub ---- */
  var st = document.querySelector('[data-admin]');
  if (st) {
    loginLinks(st);
    fetch(cfg.api + '/admin/hub', { credentials: 'include', cache: 'no-store' })
      .then(function (r) {
        if (r.status === 401) return show(st, 'loggedout');
        if (r.status === 403) return show(st, 'denied');
        return r.json().then(function (j) {
          st.querySelector('[data-name]').textContent = j.name;
          var host = st.querySelector('[data-links]');
          var groups = {};
          (j.links || []).forEach(function (l) { (groups[l.group] = groups[l.group] || []).push(l); });
          Object.keys(groups).forEach(function (g) {
            var h = document.createElement('h3'); h.textContent = g; host.appendChild(h);
            var ul = document.createElement('ul'); ul.className = 'rules';
            groups[g].forEach(function (l) {
              var li = document.createElement('li');
              var a = document.createElement('a'); a.href = l.url; a.textContent = l.title; a.rel = 'noopener';
              li.appendChild(a);
              if (l.note) { var n = document.createElement('span'); n.textContent = ' (' + l.note + ')'; n.className = 'hint'; li.appendChild(n); }
              ul.appendChild(li);
            });
            host.appendChild(ul);
          });
          show(st, 'hub');
          livePlayers(st);
        });
      })
      .catch(function () { show(st, 'loggedout'); });
  }

  /* ---- live map (admins only): players from CFTools, zones from our own data, search + layer toggles ---- */
  function livePlayers(root) {
    var note = root.querySelector('[data-live-note]');
    var mapbox = root.querySelector('#livemap');
    var svg = root.querySelector('#livesvg');
    var tip = root.querySelector('#livetip');
    var tbl = root.querySelector('#livetable');
    var body = tbl.querySelector('tbody');
    var search = root.querySelector('#pl-search');
    var matchNote = root.querySelector('[data-match]');
    var legend = root.querySelector('#livelegend');
    var NS = 'http://www.w3.org/2000/svg', W = 16384;
    var players = [];          // latest list from the Worker
    var layerOn = { players: true, pvp: true, safe: true, trader: false, dino: false };
    var morphs = [];

    function el(tag, attrs, parent) {
      var e = document.createElementNS(NS, tag);
      for (var k in attrs) e.setAttribute(k, attrs[k]);
      (parent || svg).appendChild(e);
      return e;
    }
    function showTip(target, title, sub) {
      var r = target.getBoundingClientRect(), b = mapbox.getBoundingClientRect();
      tip.innerHTML = '<b></b><small></small>'; tip.firstChild.textContent = title; tip.lastChild.textContent = sub || '';
      tip.style.left = (r.left + r.width / 2 - b.left) + 'px'; tip.style.top = (r.top - b.top) + 'px'; tip.style.display = 'block';
    }
    function wire(node, title, sub) {
      node.addEventListener('mouseenter', function () { showTip(node, title, sub); });
      node.addEventListener('mouseleave', function () { tip.style.display = 'none'; });
      node.addEventListener('click', function (e) { e.stopPropagation(); showTip(node, title, sub); });
    }

    /* base layers: filters, zone groups, then the players group on top */
    var defs = el('defs', {});
    function blobFilter(id, color) {
      var f = el('filter', { id: id, filterUnits: 'userSpaceOnUse', x: -600, y: -600, width: W + 1200, height: W + 1200 }, defs);
      morphs.push(el('feMorphology', { 'in': 'SourceAlpha', operator: 'dilate', radius: 30, result: 'grown' }, f));
      el('feComposite', { 'in': 'grown', in2: 'SourceAlpha', operator: 'out', result: 'ring' }, f);
      el('feFlood', { result: 'ink', style: 'flood-color: var(' + color + ')' }, f);
      el('feComposite', { 'in': 'ink', in2: 'ring', operator: 'in', result: 'edge' }, f);
      el('feFlood', { result: 'tint', style: 'flood-color: var(' + color + '); flood-opacity: .22' }, f);
      el('feComposite', { 'in': 'tint', in2: 'SourceAlpha', operator: 'in', result: 'fill' }, f);
      var m = el('feMerge', {}, f);
      el('feMergeNode', { 'in': 'fill' }, m); el('feMergeNode', { 'in': 'edge' }, m);
    }
    blobFilter('lv-pvp', '--pvp');
    var groups = {};
    ['dino', 'safe', 'pvp', 'trader', 'players'].forEach(function (k) {
      groups[k] = el('g', { 'data-layer': k, 'class': layerOn[k] ? '' : 'hidden' });
    });

    fetch('/assets/map-data.json').then(function (r) { return r.json(); }).then(function (d) {
      d.pvp.forEach(function (a) {
        var g = el('g', { 'class': 'blob pvp', filter: 'url(#lv-pvp)' }, groups.pvp);
        a.circles.forEach(function (c) { el('circle', { cx: c.x, cy: W - c.z, r: c.r }, g); });
        wire(g, a.name, 'PvP zone');
      });
      d.zones.filter(function (z) { return z.type === 'safe'; }).forEach(function (z) {
        wire(el('circle', { cx: z.x, cy: W - z.z, r: z.r, 'class': 'z safe' }, groups.safe), z.name, 'Safe zone');
      });
      d.dinos.forEach(function (sp) {
        sp.areas.forEach(function (a) { wire(el('circle', { cx: a.x, cy: W - a.z, r: Math.max(a.r, 90), 'class': 'z dino' }, groups.dino), sp.name, 'Territory'); });
      });
      d.traders.forEach(function (t) {
        var y = W - t.z, s = 150;
        wire(el('path', { d: 'M' + t.x + ' ' + (y - s) + 'L' + (t.x + s) + ' ' + y + 'L' + t.x + ' ' + (y + s) + 'L' + (t.x - s) + ' ' + y + 'Z', 'class': 'pin' }, groups.trader), t.name, t.npcs + ' traders');
      });
      fit();
    }).catch(function () { /* zones are optional; players still work */ });

    function fit() {
      var k = W / mapbox.getBoundingClientRect().width;
      morphs.forEach(function (m) { m.setAttribute('radius', Math.round(1.6 * k)); });
    }
    addEventListener('resize', function () { fit(); render(); });

    /* legend: real layers toggle; layers that need a server feed are shown but off */
    Array.prototype.forEach.call(legend.querySelectorAll('button[data-layer]'), function (b) {
      if (b.disabled) return;
      b.addEventListener('click', function () {
        var key = b.getAttribute('data-layer'), on = b.getAttribute('aria-pressed') !== 'true';
        b.setAttribute('aria-pressed', on); layerOn[key] = on;
        if (groups[key]) groups[key].setAttribute('class', on ? '' : 'hidden');
        if (key === 'players') { tbl.hidden = !on; }
        tip.style.display = 'none';
      });
    });

    /* search: matches name or Steam ID; narrows the dots and the table */
    function matches(p) {
      var q = search.value.trim().toLowerCase();
      return !q || p.name.toLowerCase().indexOf(q) >= 0 || String(p.steam64).indexOf(q) >= 0;
    }
    search.addEventListener('input', render);

    function render() {
      var list = players.filter(matches);
      var q = search.value.trim();
      matchNote.textContent = q ? list.length + ' of ' + players.length + ' match' : '';
      var k = W / mapbox.getBoundingClientRect().width;
      while (groups.players.firstChild) groups.players.removeChild(groups.players.firstChild);
      body.textContent = '';
      list.forEach(function (p) {
        var tr = document.createElement('tr');
        [p.name, p.steam64, p.x == null ? '' : p.x, p.z == null ? '' : p.z, p.ping == null ? '' : p.ping].forEach(function (v, i) {
          var td = document.createElement('td'); td.textContent = v; if (i === 1) td.className = 'mono'; tr.appendChild(td);
        });
        body.appendChild(tr);
        if (p.x == null) return;
        var c = el('circle', { cx: p.x, cy: W - p.z, r: Math.round((q ? 9 : 6) * k), 'class': 'pl' + (q ? ' hit' : '') }, groups.players);
        wire(c, p.name, p.x + ', ' + p.z);
        if (q && list.length <= 8) {
          var t = el('text', { x: p.x, y: W - p.z - Math.round(12 * k), 'text-anchor': 'middle' }, groups.players);
          t.style.fontSize = Math.round(11 * k) + 'px'; t.style.strokeWidth = Math.round(3 * k) + 'px';
          t.textContent = p.name;
        }
      });
    }

    function load() {
      if (document.hidden) return;
      fetch(cfg.api + '/admin/players', { credentials: 'include', cache: 'no-store' })
        .then(function (r) { return r.json(); })
        .then(function (j) {
          if (!j.ok) { note.textContent = j.error || 'Could not load players.'; return; }
          players = j.players.slice().sort(function (a, b) { return a.name.localeCompare(b.name); });
          note.textContent = players.length + ' online. Updated ' + new Date(j.updated).toLocaleTimeString() + ', refreshes every 10 seconds.';
          mapbox.hidden = false; tbl.hidden = !layerOn.players; legend.hidden = false;
          search.closest('.searchbar').hidden = false;
          fit(); render();
        })
        .catch(function () { note.textContent = 'Could not reach the server.'; });
    }
    load();
    setInterval(load, 10000);
  }
})();

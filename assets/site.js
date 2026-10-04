/* Shared page script: fireflies in the hero, live server status, the join link. */
(function () {
  var cfg = window.TUR || {};

  /* Fireflies: the drifting canvas from the Deer Isle overview page. */
  var c = document.getElementById('drift');
  if (c && !window.matchMedia('(prefers-reduced-motion: reduce)').matches) {
    var x = c.getContext('2d'), pts = [];
    var rect = function () { return c.getBoundingClientRect(); };
    var size = function () {
      var r = rect(), dpr = window.devicePixelRatio || 1;
      c.width = r.width * dpr; c.height = r.height * dpr;
      x.setTransform(dpr, 0, 0, dpr, 0, 0);
    };
    var seed = function () {
      var r = rect(), n = Math.round(r.width / 34);
      pts = [];
      for (var i = 0; i < n; i++) pts.push({
        x: Math.random() * r.width, y: Math.random() * r.height,
        r: Math.random() * 1.5 + .7, p: Math.random() * Math.PI * 2,
        s: .10 + Math.random() * .22, d: Math.random() * Math.PI * 2
      });
    };
    var frame = function (t) {
      var r = rect();
      x.clearRect(0, 0, r.width, r.height);
      for (var i = 0; i < pts.length; i++) {
        var p = pts[i];
        p.x += Math.cos(p.d) * p.s * .36; p.y += Math.sin(p.d) * p.s * .24; p.d += .005;
        if (p.x < -10) p.x = r.width + 10; if (p.x > r.width + 10) p.x = -10;
        if (p.y < -10) p.y = r.height + 10; if (p.y > r.height + 10) p.y = -10;
        var a = (Math.sin(t / 900 + p.p) * .5 + .5) * .5 + .08;
        var g = x.createRadialGradient(p.x, p.y, 0, p.x, p.y, p.r * 5);
        g.addColorStop(0, 'rgba(232,150,62,' + a + ')');
        g.addColorStop(1, 'rgba(232,150,62,0)');
        x.fillStyle = g; x.beginPath(); x.arc(p.x, p.y, p.r * 5, 0, 6.284); x.fill();
      }
      requestAnimationFrame(frame);
    };
    var boot = function () { size(); seed(); };
    boot(); requestAnimationFrame(frame);
    var tm; addEventListener('resize', function () { clearTimeout(tm); tm = setTimeout(boot, 180); });
  }

  /* Join link + address: DZSA Launcher registers dzsal://IP:QUERYPORT. */
  if (cfg.ip) {
    Array.prototype.forEach.call(document.querySelectorAll('[data-join]'), function (a) {
      a.href = 'dzsal://' + cfg.ip + ':' + cfg.queryPort;
    });
    Array.prototype.forEach.call(document.querySelectorAll('[data-addr]'), function (el) {
      el.textContent = cfg.ip + ':' + cfg.gamePort;
    });
  }

  /* Live status from the DZSA Launcher's public query (CORS open, no key). */
  var status = document.querySelector('[data-status]');
  if (status && cfg.ip) {
    var players = status.querySelector('[data-players]');
    var note = status.querySelector('[data-note]');
    var dot = status.querySelector('.dot');
    var set = function (txt, sub, state) {
      if (players) players.textContent = txt;
      if (note) note.textContent = sub;
      if (dot) dot.className = 'dot ' + state;
    };
    var load = function () {
      fetch('https://dayzsalauncher.com/api/v1/query/' + cfg.ip + '/' + cfg.queryPort, { cache: 'no-store' })
        .then(function (r) { return r.json(); })
        .then(function (d) {
          var s = d && d.result;
          if (!s || !s.maxPlayers) throw new Error('offline');
          set(s.players + ' / ' + s.maxPlayers + ' online', 'In-game time ' + s.time, 'on');
        })
        .catch(function () { set('Offline or restarting', 'Check Discord for restart times', 'off'); });
    };
    load();
    setInterval(load, 60000);
  }

  /* Discord login: the Worker at cfg.api knows who is logged in. */
  var acct = document.querySelector('[data-account]');
  if (acct && cfg.api) {
    var login = function () {
      acct.innerHTML = '<a class="login" href="' + cfg.api + '/login">Log in with Discord</a>';
    };
    fetch(cfg.api + '/me', { credentials: 'include', cache: 'no-store' })
      .then(function (r) { return r.json(); })
      .then(function (u) {
        if (!u.loggedIn) return login();
        acct.innerHTML = '<img alt="" width="24" height="24"><span></span><a href="' + cfg.api + '/logout">Log out</a>';
        acct.querySelector('img').src = u.avatar;
        acct.querySelector('span').textContent = u.name + (u.staff ? ' (admin)' : '');
      })
      .catch(login);
  }

  /* Sakura look (pages with a .grove marker only): fireflies drift behind the page and petals fall slowly.
     Visitors who prefer reduced motion get still fireflies and no petals (the stylesheet also stops the animation). */
  if (document.querySelector('.grove')) {
    var ff = document.createElement('div');
    ff.className = 'ff'; ff.setAttribute('aria-hidden', 'true'); ff.innerHTML = '<i></i><i></i>';
    document.body.insertBefore(ff, document.body.firstChild);
    var still = window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    if (!still) {
      var host = document.createElement('div');
      host.className = 'petals'; host.setAttribute('aria-hidden', 'true');
      document.body.insertBefore(host, document.body.firstChild);
      var seed = 7, clean = [0, 2, 3, 4, 5, 7, 8, 10, 11];
      var rnd = function () { seed = (seed * 16807) % 2147483647; return seed / 2147483647; };
      for (var n = 0; n < 16; n++) {
        var p = document.createElement('div'), i = document.createElement('i'), k = clean[Math.floor(rnd() * 9)];
        var sc = 0.28 + rnd() * 0.32, dur = 26 + rnd() * 26;
        p.className = 'petal';
        p.style.left = (rnd() * 100) + 'vw';
        p.style.setProperty('--dx', (rnd() * 24 - 6) + 'vw');
        p.style.animationDuration = dur + 's'; p.style.animationDelay = (-rnd() * dur) + 's';
        i.style.backgroundPosition = (-(k % 4) * 128) + 'px ' + (-Math.floor(k / 4) * 128) + 'px';
        i.style.setProperty('--s', sc); i.style.setProperty('--r0', (rnd() * 180 - 90) + 'deg'); i.style.setProperty('--r1', (rnd() * 180 + 20) + 'deg');
        i.style.animationDuration = (5 + rnd() * 5) + 's';
        p.appendChild(i); host.appendChild(p);
      }
    }
  }
})();

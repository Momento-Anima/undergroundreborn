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
        });
      })
      .catch(function () { show(st, 'loggedout'); });
  }
})();

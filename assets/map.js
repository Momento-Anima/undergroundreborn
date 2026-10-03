/* Zone map: draws assets/map-data.json over the island silhouette.
   World coords are x east, z north, 0..16384; the SVG viewBox is the same square with y flipped. */
(function () {
  var svg = document.getElementById('mapsvg'), tip = document.getElementById('maptip'), box = document.getElementById('mapbox');
  var list = document.getElementById('zonelist');
  if (!svg) return;
  var NS = 'http://www.w3.org/2000/svg';
  var dataUrl = (document.querySelector('script[src*="map.js"]') || {}).src || '';
  dataUrl = dataUrl.replace(/map\.js.*$/, 'map-data.json');

  function el(tag, attrs, parent) {
    var e = document.createElementNS(NS, tag);
    for (var k in attrs) e.setAttribute(k, attrs[k]);
    (parent || svg).appendChild(e);
    return e;
  }
  function Y(z, world) { return world - z; }

  function showTip(target, title, sub) {
    var r = target.getBoundingClientRect(), b = box.getBoundingClientRect();
    tip.innerHTML = '<b></b><small></small>';
    tip.firstChild.textContent = title;
    tip.lastChild.textContent = sub || '';
    tip.style.left = (r.left + r.width / 2 - b.left) + 'px';
    tip.style.top = (r.top - b.top) + 'px';
    tip.style.display = 'block';
  }
  function hideTip() { tip.style.display = 'none'; }

  function wire(node, title, sub) {
    node.addEventListener('mouseenter', function () { showTip(node, title, sub); });
    node.addEventListener('mouseleave', hideTip);
    node.addEventListener('click', function (ev) { ev.stopPropagation(); showTip(node, title, sub); });
  }

  fetch(dataUrl).then(function (r) { return r.json(); }).then(function (d) {
    var W = d.world;
    var layers = {};
    ['pve', 'dino', 'gas', 'pvp', 'safe', 'trader'].forEach(function (k) {
      layers[k] = el('g', { 'data-layer': k, 'class': k === 'pve' ? 'hidden' : '' });
    });
    var sub = { pvp: 'PvP zone', pve: 'PvE', safe: 'Safe zone', gas: 'Contaminated' };

    // Big circles first so small ones stay clickable.
    d.zones.slice().sort(function (a, b) { return b.r - a.r; }).forEach(function (z) {
      var g = layers[z.type]; if (!g) return;
      var c = el('circle', { cx: z.x, cy: Y(z.z, W), r: z.r, 'class': 'z ' + z.type }, g);
      wire(c, z.name, (z.gas ? 'PvP zone, gas mask needed' : sub[z.type]) + ' · ' + (z.r * 2 / 1000).toFixed(1) + ' km across');
      if (z.type === 'pvp' && z.r >= 380 && !/Oil Rig/.test(z.name)) {
        var t = el('text', { x: z.x, y: Y(z.z, W), 'text-anchor': 'middle', 'font-size': 220 }, g);
        t.textContent = z.name;
      }
    });

    d.dinos.forEach(function (sp) {
      sp.areas.forEach(function (a) {
        var c = el('circle', { cx: a.x, cy: Y(a.z, W), r: Math.max(a.r, 90), 'class': 'z dino' }, layers.dino);
        wire(c, sp.name, 'Territory');
      });
    });

    d.traders.forEach(function (t) {
      var y = Y(t.z, W), s = 150;
      var p = el('path', { d: 'M' + t.x + ' ' + (y - s) + 'L' + (t.x + s) + ' ' + y + 'L' + t.x + ' ' + (y + s) + 'L' + (t.x - s) + ' ' + y + 'Z', 'class': 'pin' }, layers.trader);
      wire(p, t.name, t.npcs + ' traders');
      var lab = el('text', { x: t.x, y: y - s - 80, 'text-anchor': 'middle', 'font-size': 240 }, layers.trader);
      lab.textContent = t.name;
    });

    // Text sizes are in world units; keep them readable at any box size.
    var fit = function () {
      var k = W / box.getBoundingClientRect().width;      // world units per CSS px
      Array.prototype.forEach.call(svg.querySelectorAll('text'), function (t) {
        var base = t.parentNode.getAttribute('data-layer') === 'trader' ? 11 : 10;
        t.setAttribute('font-size', Math.round(base * k));
        t.setAttribute('stroke-width', Math.round(3 * k));
      });
    };
    fit(); addEventListener('resize', fit);

    // The list under the map: PvP zones, deduplicated, alphabetical.
    if (list) {
      var seen = {};
      d.zones.filter(function (z) { return z.type === 'pvp'; })
        .sort(function (a, b) { return a.name.localeCompare(b.name); })
        .forEach(function (z) {
          if (seen[z.name]) return; seen[z.name] = 1;
          var li = document.createElement('li');
          li.textContent = z.name + (z.gas ? ' (gas)' : '');
          list.appendChild(li);
        });
    }
  });

  Array.prototype.forEach.call(document.querySelectorAll('.legend button'), function (b) {
    b.addEventListener('click', function () {
      var on = b.getAttribute('aria-pressed') !== 'true';
      b.setAttribute('aria-pressed', on);
      var g = svg.querySelector('[data-layer="' + b.getAttribute('data-layer') + '"]');
      if (g) g.setAttribute('class', on ? '' : 'hidden');
      hideTip();
    });
  });
  document.addEventListener('click', hideTip);
})();

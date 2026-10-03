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
    /* PvP areas are drawn as solid blobs (so overlapping circles read as one shape) and the
       filter turns that shape into a faint fill plus a single outline round the outside. */
    var defs = el('defs', {}), morphs = [];
    function blobFilter(id, color) {
      var f = el('filter', { id: id, filterUnits: 'userSpaceOnUse', x: -600, y: -600, width: W + 1200, height: W + 1200 }, defs);
      morphs.push(el('feMorphology', { 'in': 'SourceAlpha', operator: 'dilate', radius: 30, result: 'grown' }, f));
      el('feComposite', { 'in': 'grown', in2: 'SourceAlpha', operator: 'out', result: 'ring' }, f);
      el('feFlood', { result: 'ink', style: 'flood-color: var(' + color + ')' }, f);
      el('feComposite', { 'in': 'ink', in2: 'ring', operator: 'in', result: 'edge' }, f);
      el('feFlood', { result: 'tint', style: 'flood-color: var(' + color + '); flood-opacity: .22' }, f);
      el('feComposite', { 'in': 'tint', in2: 'SourceAlpha', operator: 'in', result: 'fill' }, f);
      var m = el('feMerge', {}, f);
      el('feMergeNode', { 'in': 'fill' }, m);
      el('feMergeNode', { 'in': 'edge' }, m);
    }
    blobFilter('blob-pvp', '--pvp');
    blobFilter('blob-pve', '--pve');
    var layers = {};
    ['pve', 'dino', 'gas', 'pvp', 'safe', 'trader'].forEach(function (k) {
      layers[k] = el('g', { 'data-layer': k, 'class': k === 'pve' ? 'hidden' : '' });
    });
    var sub = { pvp: 'PvP zone', pve: 'PvE', safe: 'Safe zone', gas: 'Contaminated' };

    // Big circles first so small ones stay clickable.
    function drawAreas(areas, kind, noun, labelMin) {
      areas.slice().sort(function (a, b) {
        return Math.max.apply(null, b.circles.map(function (c) { return c.r; })) - Math.max.apply(null, a.circles.map(function (c) { return c.r; }));
      }).forEach(function (a) {
        var grp = el('g', { 'class': 'blob ' + kind, filter: 'url(#blob-' + kind + ')' }, layers[kind]);
        var x0 = 1e9, x1 = -1e9, z0 = 1e9, z1 = -1e9;
        a.circles.forEach(function (c) {
          el('circle', { cx: c.x, cy: Y(c.z, W), r: c.r }, grp);
          x0 = Math.min(x0, c.x - c.r); x1 = Math.max(x1, c.x + c.r);
          z0 = Math.min(z0, c.z - c.r); z1 = Math.max(z1, c.z + c.r);
        });
        var span = Math.max(x1 - x0, z1 - z0);
        wire(grp, a.name, noun + (a.gas ? ', gas mask needed' : '') + ' · ' + (span / 1000).toFixed(1) + ' km across');
        if (span >= labelMin && !/Oil Rig/.test(a.name)) {
          var t = el('text', { x: a.x, y: Y(a.z, W), 'text-anchor': 'middle' }, layers[kind]);
          t.textContent = a.label;
        }
      });
    }
    drawAreas(d.pve, 'pve', 'PvE', 700);
    drawAreas(d.pvp, 'pvp', 'PvP zone', 800);

    d.zones.slice().sort(function (a, b) { return b.r - a.r; }).forEach(function (z) {
      var g = layers[z.type]; if (!g) return;
      var c = el('circle', { cx: z.x, cy: Y(z.z, W), r: z.r, 'class': 'z ' + z.type }, g);
      wire(c, z.name, (z.gas ? 'PvP zone, gas mask needed' : sub[z.type]) + ' · ' + (z.r * 2 / 1000).toFixed(1) + ' km across');
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
      var lab = el('text', { x: t.x, y: y - s - 80, 'text-anchor': 'middle' }, layers.trader);
      lab.textContent = t.name;
    });

    // Text sizes are in world units; keep them readable at any box size.
    var fit = function () {
      var k = W / box.getBoundingClientRect().width;      // world units per CSS px
      morphs.forEach(function (m) { m.setAttribute('radius', Math.round(1.6 * k)); });
      Array.prototype.forEach.call(svg.querySelectorAll('text'), function (t) {
        var base = t.parentNode.getAttribute('data-layer') === 'trader' ? 11 : 10;
        t.style.fontSize = Math.round(base * k) + 'px';
        t.style.strokeWidth = Math.round(3 * k) + 'px';
      });
    };
    fit(); addEventListener('resize', fit);

    // The list under the map: PvP zones, deduplicated, alphabetical.
    if (list) {
      d.pvp.forEach(function (a) {
        var li = document.createElement('li');
        li.textContent = a.names.join(', ') + (a.gas ? ' (gas)' : '');
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

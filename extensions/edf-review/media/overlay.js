/* EDF Review diagram click-through overlay (preview webview). No network, no dynamic code. */
(function () {
  'use strict';
  var SEL = 'svg[id^="mermaid"]';
  var bySource = new WeakMap();
  var sources = [];
  var rafBusy = false;

  function designRootOf(p) {
    var m = p.indexOf('/docs/design/');
    if (m !== -1) return p.slice(0, m);
    var s = p.split('/').filter(Boolean);
    return /^[A-Za-z]:/.test(p) ? '/' + s.slice(0, 2).join('/') : '/' + (s[0] || '');
  }

  function resolveAndValidateHref(href) {
    if (!href) return null;
    var h = String(href).trim();
    if (!h) return null;
    if (h.charAt(0) === '#') return h;
    if (/^[a-z][a-z0-9+.-]*:/i.test(h)) return null;
    var base, r;
    try {
      base = new URL(document.baseURI);
      r = new URL(h, base);
    } catch (e) { return null; }
    if (r.origin !== base.origin) return null;
    var root = designRootOf(base.pathname);
    var rp = r.pathname;
    if (rp !== root && rp.indexOf(root + '/') !== 0) return null;
    return h;
  }

  function place(overlay, el) {
    var rc = el.getBoundingClientRect();
    overlay.style.position = 'absolute';
    overlay.style.left = (rc.left + (window.scrollX || 0)) + 'px';
    overlay.style.top = (rc.top + (window.scrollY || 0)) + 'px';
    overlay.style.width = rc.width + 'px';
    overlay.style.height = rc.height + 'px';
  }

  function createOverlaysFor(svg) {
    if (!svg || !svg.querySelectorAll) return;
    var as = svg.querySelectorAll('a[href], a[xlink\\:href]');
    for (var i = 0; i < as.length; i++) {
      var a = as[i];
      var href = a.getAttribute('href') || a.getAttribute('xlink:href');
      if (!href) continue;
      var v = resolveAndValidateHref(href);
      if (v === null) continue;
      var ex = bySource.get(a);
      if (ex) { place(ex, a); continue; }
      var o = document.createElement('a');
      o.className = 'edf-review-overlay';
      o.setAttribute('href', v);
      place(o, a);
      document.body.appendChild(o);
      bySource.set(a, o);
      sources.push(a);
    }
  }

  function removeStaleOverlays() {
    sources = sources.filter(function (s) {
      if (s.isConnected) return true;
      var o = bySource.get(s);
      if (o && o.parentNode) o.parentNode.removeChild(o);
      bySource.delete(s);
      return false;
    });
  }

  function repositionAll() {
    for (var i = 0; i < sources.length; i++) {
      var s = sources[i];
      if (s.isConnected) {
        var o = bySource.get(s);
        if (o) place(o, s);
      }
    }
  }

  function observeMermaidContainers() {
    if (typeof window.MutationObserver === 'undefined') {
      throw new Error('MutationObserver unavailable');
    }
    var ob = new window.MutationObserver(function (ms) {
      try {
        for (var i = 0; i < ms.length; i++) {
          var rec = ms[i];
          for (var j = 0; j < rec.addedNodes.length; j++) {
            var n = rec.addedNodes[j];
            if (n.nodeType !== 1) continue;
            if (n.matches && n.matches(SEL)) createOverlaysFor(n);
            var nested = n.querySelectorAll ? n.querySelectorAll(SEL) : null;
            for (var k = 0; nested && k < nested.length; k++) createOverlaysFor(nested[k]);
          }
          var stale = false;
          for (var r = 0; r < rec.removedNodes.length; r++) {
            var rn = rec.removedNodes[r];
            if (rn.nodeType !== 1) continue;
            if (rn.matches && rn.matches(SEL)) stale = true;
            else if (rn.querySelector && rn.querySelector(SEL)) stale = true;
          }
          if (stale) removeStaleOverlays();
        }
      } catch (e) { reportError(e); }
    });
    ob.observe(document.body, { childList: true, subtree: true });
    var ex = document.querySelectorAll(SEL);
    for (var e = 0; e < ex.length; e++) createOverlaysFor(ex[e]);
  }

  function scheduleReposition() {
    if (rafBusy) return;
    rafBusy = true;
    var raf = window.requestAnimationFrame ||
      function (cb) { return window.setTimeout(cb, 16); };
    raf(function () {
      rafBusy = false;
      try { repositionAll(); } catch (e) { reportError(e); }
    });
  }

  function reportError(err) {
    try {
      var msg = err && err.message ? err.message : String(err);
      var api = window.acquireVsCodeApi && window.acquireVsCodeApi();
      if (api && api.postMessage) {
        api.postMessage({ type: 'edf-overlay-error', message: msg });
      }
    } catch (e2) { /* swallow — keep the webview alive */ }
  }

  window.addEventListener('scroll', scheduleReposition, true);
  window.addEventListener('resize', scheduleReposition, true);

  window.__edfOverlay = {
    resolveAndValidateHref: resolveAndValidateHref,
    createOverlaysFor: createOverlaysFor,
    removeStaleOverlays: removeStaleOverlays,
    observeMermaidContainers: observeMermaidContainers
  };

  try {
    observeMermaidContainers();
  } catch (err) {
    reportError(err);
  }
})();

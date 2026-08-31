// PROTOTYPE — not production code.
//
// Hypothesis under test: VS Code's built-in markdown preview click handler
// (media/index.js in markdown-language-features) only opens a link when the
// clicked element's tagName === "A" (checked case-sensitively). An SVG <a>
// reports tagName "a" (SVG is case-sensitive XML), so it never matches and
// clicks on Mermaid diagram links do nothing.
//
// This script does not talk to any extension host and defines no new
// message channel. It only creates real HTML <a> elements, positioned over
// each SVG <a>'s clickable area, carrying the same href. If the hypothesis
// is right, the *existing* built-in click handler picks up these HTML
// anchors on its own and opens the file — proving a small previewScripts-only
// extension is enough, with no custom webview and no extension-host code.

(function () {
  var OVERLAY_MARK = "data-edf-poc-overlay";
  var container = null;

  function ensureContainer() {
    if (container && document.body.contains(container)) return container;
    container = document.createElement("div");
    container.id = "edf-poc-overlay-container";
    container.style.position = "absolute";
    container.style.top = "0";
    container.style.left = "0";
    container.style.width = "0";
    container.style.height = "0";
    container.style.zIndex = "9999";
    document.body.appendChild(container);
    return container;
  }

  function injectStyle() {
    var s = document.getElementById("edf-ov-style");
    if (s) return;
    s = document.createElement("style");
    s.id = "edf-ov-style";
    // Clickable diagram areas must LOOK clickable: the transparent overlay <a>
    // provides the pointer cursor, but the affordance (underline + link colour
    // on the node label) is drawn on the SVG underneath, so it must be styled
    // directly. Mermaid emits the label as <text>/<tspan> or, in newer
    // versions, inside <foreignObject> — cover all three.
    s.textContent =
      "svg a,svg a *{cursor:pointer}" +
      "svg a text,svg a tspan,svg a foreignObject{text-decoration:underline!important;text-underline-offset:2px}" +
      "svg a:hover text,svg a:hover tspan,svg a:hover foreignObject{color:var(--vscode-textLink-foreground,#2aa1e2)}";
    document.head.appendChild(s);
  }

  function findSvgAnchors() {
    // Mermaid emits either href or xlink:href depending on version.
    var nodes = document.querySelectorAll("svg a");
    return Array.prototype.filter.call(nodes, function (a) {
      return (
        a.getAttribute("href") || a.getAttributeNS("http://www.w3.org/1999/xlink", "href")
      );
    });
  }

  function positionOverlay(overlay, svgAnchor) {
    var rect = svgAnchor.getBoundingClientRect();
    overlay.style.position = "fixed";
    overlay.style.left = rect.left + "px";
    overlay.style.top = rect.top + "px";
    overlay.style.width = Math.max(rect.width, 1) + "px";
    overlay.style.height = Math.max(rect.height, 1) + "px";
  }

  function rescan() {
    var c = ensureContainer();
    var svgAnchors = findSvgAnchors();
    var live = new Set();

    svgAnchors.forEach(function (svgAnchor) {
      var href =
        svgAnchor.getAttribute("href") ||
        svgAnchor.getAttributeNS("http://www.w3.org/1999/xlink", "href");
      if (!href) return;
      // Security: never put a scheme-bearing href (javascript:, data:, ...) on
      // a real HTML anchor. Relative paths and #fragments — the only targets
      // diagrams and the probe use — have no scheme and pass through.
      if (/^[a-z][a-z0-9+.-]*:/i.test(href)) return;

      // svgAnchor.isConnected guards against a stale reference surviving on
      // an old node after the preview replaces the SVG wholesale (Mermaid
      // re-renders diagrams outright rather than patching them in place).
      var overlay =
        svgAnchor.isConnected && svgAnchor[OVERLAY_MARK] && c.contains(svgAnchor[OVERLAY_MARK])
          ? svgAnchor[OVERLAY_MARK]
          : null;
      if (!overlay) {
        overlay = document.createElement("a");
        overlay.setAttribute(OVERLAY_MARK, "1");
        overlay.style.display = "block";
        overlay.style.background = "transparent";
        overlay.style.cursor = "pointer";
        c.appendChild(overlay);
        svgAnchor[OVERLAY_MARK] = overlay;
      }

      overlay.href = href;
      positionOverlay(overlay, svgAnchor);
      live.add(overlay);
    });

    // Remove overlays whose SVG anchor is gone or was replaced — otherwise
    // every diagram re-render (edit-while-previewing, scroll-triggered
    // Mermaid re-layout) leaks a stale, invisible click-trap at the old
    // position.
    Array.prototype.slice.call(c.children).forEach(function (child) {
      if (!live.has(child)) c.removeChild(child);
    });
  }

  var busy = false;
  function scheduleRescan() {
    if (busy) return;
    busy = true;
    requestAnimationFrame(function () {
      busy = false;
      rescan();
    });
  }

  window.addEventListener("load", scheduleRescan);
  window.addEventListener("resize", scheduleRescan);
  window.addEventListener("scroll", scheduleRescan, true);
  // Dispatched by the built-in preview script after it patches in new
  // content (e.g. on document edit while the preview is open).
  window.addEventListener("vscode.markdown.updateContent", scheduleRescan);

  var observer = new MutationObserver(scheduleRescan);
  observer.observe(document.body || document.documentElement, {
    childList: true,
    subtree: true,
  });

  injectStyle();

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", scheduleRescan);
  } else {
    scheduleRescan();
  }
})();

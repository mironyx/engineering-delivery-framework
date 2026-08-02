/**
 * EDF Review — Markdown Preview Script
 *
 * Injected into every VSCode markdown preview webview via the
 * `markdown.previewScripts` contribution. Intercepts `edf://` links
 * in rendered Mermaid SVG diagrams for hover-and-click navigation.
 *
 * Two interactions:
 *   Hover → tooltip with first ~40 lines of the source file
 *   Click → opens full file in the right editor column
 *
 * `#LLD-` anchor links (new-to-be-created code) work via native browser
 * anchor navigation — no postMessage needed.
 */
(function () {
  const vscode = acquireVsCodeApi();

  let tooltip = null;
  let hoverTimeout = null;
  let lastMouseEvent = null;

  // Track mouse position globally so we can position the tooltip
  // when the peek response arrives asynchronously.
  document.addEventListener('mousemove', (e) => { lastMouseEvent = e; });

  // ── Tooltip ────────────────────────────────────────────────────────

  function createTooltip() {
    if (tooltip) return tooltip;
    const el = document.createElement('div');
    el.className = 'edf-tooltip';
    Object.assign(el.style, {
      display: 'none',
      position: 'fixed',
      zIndex: '99999',
      maxWidth: '520px',
      maxHeight: '320px',
      overflow: 'auto',
      padding: '8px 10px',
      background: 'var(--vscode-editor-background, #1e1e1e)',
      color: 'var(--vscode-editor-foreground, #d4d4d4)',
      border: '1px solid var(--vscode-widget-border, #3c3c3c)',
      borderRadius: '4px',
      fontFamily: 'var(--vscode-editor-font-family, monospace)',
      fontSize: 'var(--vscode-editor-font-size, 12px)',
      lineHeight: '1.45',
      whiteSpace: 'pre',
      boxShadow: '0 4px 12px rgba(0,0,0,0.4)',
      pointerEvents: 'none'
    });
    document.body.appendChild(el);
    tooltip = el;
    return el;
  }

  function showTooltip(e, content) {
    const tip = createTooltip();
    tip.textContent = content;
    // Position near cursor, clamped to viewport
    let left = e.clientX + 12;
    let top = e.clientY + 12;
    const rect = tip.getBoundingClientRect();
    if (left + rect.width > window.innerWidth - 8) {
      left = e.clientX - rect.width - 12;
    }
    if (top + rect.height > window.innerHeight - 8) {
      top = e.clientY - rect.height - 12;
    }
    tip.style.left = Math.max(4, left) + 'px';
    tip.style.top = Math.max(4, top) + 'px';
    tip.style.display = 'block';
  }

  function hideTooltip() {
    if (tooltip) tooltip.style.display = 'none';
  }

  // ── Link discovery ─────────────────────────────────────────────────

  /**
   * Walk the DOM for <a> elements with edf:// or #LLD- hrefs.
   * Mermaid `click` directives generate <a xlink:href="..."> inside SVG.
   */
  function findLinks() {
    const links = [];

    // SVG <a> elements (Mermaid output)
    document.querySelectorAll('a[xlink\\:href], a[href]').forEach(a => {
      const href = a.getAttribute('xlink:href') || a.getAttribute('href');
      if (!href) return;
      if (href.startsWith('edf://') || href.startsWith('#LLD-')) {
        links.push(a);
      }
    });

    return links;
  }

  function attachHandlers(link) {
    if (link.dataset.edfHandled) return;
    link.dataset.edfHandled = '1';

    const href = link.getAttribute('xlink:href') || link.getAttribute('href');

    link.addEventListener('mouseenter', (e) => {
      if (href.startsWith('edf://')) {
        const path = href.replace('edf://', '');
        // Clear any pending timeout
        if (hoverTimeout) clearTimeout(hoverTimeout);
        // Small debounce to avoid flicker
        hoverTimeout = setTimeout(() => {
          vscode.postMessage({ command: 'peek', path });
        }, 150);
      } else if (href.startsWith('#LLD-')) {
        if (hoverTimeout) clearTimeout(hoverTimeout);
        hoverTimeout = setTimeout(() => {
          showTooltip(e, '→ Part B implementation spec\n(click to scroll)');
        }, 150);
      }
    });

    link.addEventListener('mouseleave', () => {
      if (hoverTimeout) clearTimeout(hoverTimeout);
      hideTooltip();
    });

    link.addEventListener('click', (e) => {
      if (href.startsWith('edf://')) {
        e.preventDefault();
        e.stopPropagation();
        hideTooltip();
        const path = href.replace('edf://', '');
        vscode.postMessage({ command: 'open', path });
      }
      // #LLD- links: let the browser handle anchor navigation naturally
    });
  }

  // ── Initialise + watch for late-rendered SVGs ─────────────────────

  function scan() {
    findLinks().forEach(attachHandlers);
  }

  // Scan immediately
  scan();

  // Watch for dynamically inserted SVGs (Mermaid may render after DOMContentLoaded)
  const observer = new MutationObserver(() => {
    scan();
  });

  observer.observe(document.body, {
    childList: true,
    subtree: true
  });

  // ── Receive peek response from extension host ─────────────────────

  window.addEventListener('message', (event) => {
    const msg = event.data;
    if (msg && msg.command === 'peekResult') {
      if (msg.text) {
        if (hoverTimeout) clearTimeout(hoverTimeout);
        const pos = lastMouseEvent || { clientX: window.innerWidth / 3, clientY: window.innerHeight / 4 };
        showTooltip(pos, msg.text);
      }
    }
  });
})();

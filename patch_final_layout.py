with open("web/index.html", "r") as f:
    html = f.read()

def strip_block(html, start_marker, end_marker):
    while start_marker in html:
        start = html.find(start_marker)
        end = html.find(end_marker, start)
        if end == -1:
            break
        end += len(end_marker)
        html = html[:start] + html[end:]
    return html

# Remove ALL previous guess-based patches
for s, e in [
    ('<style id="gemini-style-patch">', '</style>'),
    ('<script id="gemini-ui-patch">', '</script>'),
    ('<style id="kiemaen-logo-patch">', '</style>'),
    ('<style id="kiemaen-layout-fix">', '</style>'),
    ('<script id="kiemaen-logo-ui-patch">', '</script>'),
]:
    html = strip_block(html, s, e)

CSS_BLOCK = """
<style id="kiemaen-fix-v3">
html, body {
  height: 100%;
  margin: 0;
  overflow: hidden;
  background: linear-gradient(180deg, #05070d 0%, #0a0e1a 45%, #10213d 100%) !important;
}
body {
  display: flex;
  flex-direction: column;
  height: 100vh;
  height: 100dvh;
}
#header {
  flex-shrink: 0;
  background: transparent;
}
#chat-wrapper {
  flex: 1 1 auto;
  min-height: 0;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
  justify-content: center;
}
#chat-container {
  display: flex;
  flex-direction: column;
  min-height: 100%;
  justify-content: center;
}
#input-area {
  flex-shrink: 0;
  margin-bottom: 10px;
}

.kiemaen-empty-state {
  display:flex; flex-direction:column; align-items:center; justify-content:center;
  padding: 20px; text-align:center; animation: fadeInUp 0.6s ease;
}
.kiemaen-clover-logo {
  width: 140px; height: 140px;
  margin-bottom: 20px;
  filter: drop-shadow(0 4px 20px rgba(66,133,244,0.4));
}
.kiemaen-empty-state h1 {
  font-size: 34px;
  font-weight: 700;
  margin: 0;
  background: linear-gradient(135deg, #6ea8ff 0%, #1a73e8 45%, #05070d 100%);
  -webkit-background-clip: text;
  background-clip: text;
  -webkit-text-fill-color: transparent;
  color: transparent;
}
.kiemaen-empty-state p.tagline {
  color:#8ab4f8; font-size:15px; margin-top:10px; opacity:0.85;
}
@keyframes fadeInUp { from{opacity:0; transform:translateY(14px);} to{opacity:1; transform:translateY(0);} }
</style>
"""

CLOVER_SVG = """<svg class=\\"kiemaen-clover-logo\\" viewBox=\\"0 0 200 200\\" xmlns=\\"http://www.w3.org/2000/svg\\"><defs><linearGradient id=\\"cloverGrad\\" x1=\\"0%\\" y1=\\"0%\\" x2=\\"100%\\" y2=\\"100%\\"><stop offset=\\"0%\\" stop-color=\\"#6ea8ff\\"/><stop offset=\\"45%\\" stop-color=\\"#1a73e8\\"/><stop offset=\\"100%\\" stop-color=\\"#05070d\\"/></linearGradient></defs><g transform=\\"translate(100,100)\\"><g id=\\"leafGroup\\"><path d=\\"M0,0 C-22,-30 -22,-70 0,-95 C22,-70 22,-30 0,0 Z\\" fill=\\"url(%23cloverGrad)\\"/></g><use href=\\"%23leafGroup\\" transform=\\"rotate(72)\\"/><use href=\\"%23leafGroup\\" transform=\\"rotate(144)\\"/><use href=\\"%23leafGroup\\" transform=\\"rotate(216)\\"/><use href=\\"%23leafGroup\\" transform=\\"rotate(288)\\"/><circle r=\\"10\\" fill=\\"%2305070d\\" stroke=\\"%234285f4\\" stroke-width=\\"2\\"/></g></svg>"""

JS_BLOCK = """
<script id="kiemaen-fix-v3-js">
(function(){
  function init(){
    var container = document.getElementById('chat-container');
    if (container && !document.querySelector('.kiemaen-empty-state')) {
      var empty = document.createElement('div');
      empty.className = 'kiemaen-empty-state';
      empty.id = 'kiemaenEmptyState';
      empty.innerHTML = '""" + CLOVER_SVG.replace("%23", "#") + """<h1>Kiemaen AI</h1><p class="tagline">Your ultimate agentic assistant</p>';
      container.prepend(empty);

      var observer = new MutationObserver(function(){
        var hasMessages = container.querySelectorAll('.message').length > 0;
        empty.style.display = hasMessages ? 'none' : 'flex';
      });
      observer.observe(container, { childList: true });
    }
  }
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
  setTimeout(init, 300);
})();
</script>
"""

html = html.replace("</head>", CSS_BLOCK + "\\n</head>", 1)
html = html.replace("</body>", JS_BLOCK + "\\n</body>", 1)

with open("web/index.html", "w") as f:
    f.write(html)

print("Patched web/index.html with corrected selectors targeting real #chat-container/#chat-wrapper/#header/#input-area.")

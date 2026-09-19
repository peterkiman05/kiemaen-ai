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

for s, e in [
    ('<style id="kiemaen-fix-v5">', '</style>'),
    ('<script id="kiemaen-fix-v5-js">', '</script>'),
]:
    html = strip_block(html, s, e)

# Ensure proper viewport meta tag exists for auto-fit (won't duplicate if already present)
if 'name="viewport"' not in html:
    html = html.replace(
        "<head>",
        '<head>\\n<meta name="viewport" content="width=device-width, initial-scale=1, maximum-scale=1, user-scalable=no, viewport-fit=cover">',
        1
    )

CSS_BLOCK = """
<style id="kiemaen-fix-v6">
html, body {
  height: 100%;
  width: 100%;
  margin: 0;
  padding: 0;
  overflow: hidden;
  position: fixed;
  inset: 0;
  background: linear-gradient(180deg, #05070d 0%, #0a0e1a 45%, #10213d 100%) !important;
}
body {
  display: flex;
  flex-direction: column;
  height: 100vh;
  height: 100dvh;
  width: 100vw;
}
#header { flex-shrink: 0; background: transparent; }
#chat-wrapper {
  flex: 1 1 auto;
  min-height: 0;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
}
#chat-container { display: flex; flex-direction: column; min-height: 100%; }
#input-area { flex-shrink: 0; margin-bottom: env(safe-area-inset-bottom, 14px); }

.kiemaen-empty-state {
  display:flex; flex-direction:column; align-items:center; justify-content:center;
  flex: 1;
  text-align:center; animation: fadeInUp 0.6s ease;
}
.kiemaen-clover-logo {
  width: 150px; height: 150px;
  margin-bottom: 24px;
  filter: drop-shadow(0 4px 20px rgba(66,133,244,0.45));
}
.kiemaen-empty-state h1 {
  font-size: 38px;
  font-weight: 700;
  margin: 0;
  line-height: 1.3;
  background: linear-gradient(135deg, #6ea8ff 0%, #1a73e8 45%, #05070d 100%);
  -webkit-background-clip: text;
  background-clip: text;
  -webkit-text-fill-color: transparent;
  color: transparent;
}
@keyframes fadeInUp { from{opacity:0; transform:translateY(10px);} to{opacity:1; transform:translateY(0);} }

.input-wrapper {
  border-radius: 32px !important;
  background: #1e1f22 !important;
  padding: 8px 10px 8px 16px !important;
}
.input-wrapper .icon-btn { background: transparent; color: #9aa0a6; }
#actionBtn {
  width: 40px; height: 40px;
  border-radius: 50% !important;
  background: linear-gradient(135deg,#4285f4,#1a73e8) !important;
  display: flex; align-items: center; justify-content: center;
}
#actionBtn #actionIcon { color: #fff !important; }
#actionBtn.jarvis-active { animation: pulseVoice 1.2s infinite; }
@keyframes pulseVoice {
  0% { box-shadow:0 0 0 0 rgba(66,133,244,0.5); }
  70% { box-shadow:0 0 0 12px rgba(66,133,244,0); }
  100% { box-shadow:0 0 0 0 rgba(66,133,244,0); }
}
</style>
"""

# Clover with matching blue-to-black gradient fill (same gradient direction as title text)
CLOVER_SVG = """<svg class=\\"kiemaen-clover-logo\\" viewBox=\\"0 0 200 200\\" xmlns=\\"http://www.w3.org/2000/svg\\"><defs><linearGradient id=\\"cloverGrad\\" x1=\\"0%\\" y1=\\"0%\\" x2=\\"100%\\" y2=\\"100%\\"><stop offset=\\"0%\\" stop-color=\\"#6ea8ff\\"/><stop offset=\\"45%\\" stop-color=\\"#1a73e8\\"/><stop offset=\\"100%\\" stop-color=\\"#05070d\\"/></linearGradient></defs><g transform=\\"translate(100,100)\\"><g id=\\"leafGroup\\"><path d=\\"M0,0 C-22,-30 -22,-70 0,-95 C22,-70 22,-30 0,0 Z\\" fill=\\"url(%23cloverGrad)\\"/></g><use href=\\"%23leafGroup\\" transform=\\"rotate(72)\\"/><use href=\\"%23leafGroup\\" transform=\\"rotate(144)\\"/><use href=\\"%23leafGroup\\" transform=\\"rotate(216)\\"/><use href=\\"%23leafGroup\\" transform=\\"rotate(288)\\"/><circle r=\\"11\\" fill=\\"%2305070d\\" stroke=\\"%234285f4\\" stroke-width=\\"2.5\\"/></g></svg>"""

JS_BLOCK = """
<script id="kiemaen-fix-v6-js">
(function(){
  function init(){
    var container = document.getElementById('chat-container');
    var old = document.getElementById('kiemaenEmptyState');
    if (old) old.remove();
    document.querySelectorAll('.gemini-voice-btn').forEach(function(el){ el.remove(); });

    if (container && !document.getElementById('kiemaenEmptyState')) {
      var empty = document.createElement('div');
      empty.className = 'kiemaen-empty-state';
      empty.id = 'kiemaenEmptyState';
      empty.innerHTML = '""" + CLOVER_SVG.replace("%23", "#") + """<h1>Kiemaen AI</h1>';
      container.prepend(empty);

      var observer = new MutationObserver(function(){
        var hasMessages = container.querySelectorAll('.message').length > 0;
        empty.style.display = hasMessages ? 'none' : 'flex';
      });
      observer.observe(container, { childList: true });
    }

    var actionBtn = document.getElementById('actionBtn');
    if (actionBtn) {
      setInterval(function(){
        if (window.jarvisMode) actionBtn.classList.add('jarvis-active');
        else actionBtn.classList.remove('jarvis-active');
      }, 400);
    }
  }
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
  setTimeout(init, 300);

  // Re-fit on viewport/keyboard resize (mobile browsers)
  window.addEventListener('resize', function(){
    document.documentElement.style.height = window.innerHeight + 'px';
  });
})();
</script>
"""

html = html.replace("</head>", CSS_BLOCK + "\\n</head>", 1)
html = html.replace("</body>", JS_BLOCK + "\\n</body>", 1)

with open("web/index.html", "w") as f:
    f.write(html)

print("Patched: auto-fit viewport, bigger blue-black gradient logo (150px), matching gradient title (38px).")

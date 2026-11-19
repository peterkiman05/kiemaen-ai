with open("web/index.html", "r") as f:
    html = f.read()

def strip_block(html, start_marker, end_marker):
    start = html.find(start_marker)
    if start == -1:
        return html
    end = html.find(end_marker, start)
    if end == -1:
        return html
    end += len(end_marker)
    return html[:start] + html[end:]

# Remove old patches so we don't stack duplicates
html = strip_block(html, '<style id="gemini-style-patch">', '</style>')
html = strip_block(html, '<script id="gemini-ui-patch">', '</script>')

CSS_BLOCK = """
<style id="kiemaen-logo-patch">
html, body {
  background: linear-gradient(180deg, #05070d 0%, #0a0e1a 45%, #10213d 100%) !important;
  min-height: 100vh;
}
#chatArea, .chat-area, .messages, main {
  background: transparent !important;
}
.kiemaen-empty-state {
  display:flex; flex-direction:column; align-items:center; justify-content:flex-start;
  padding-top: 12vh;
  min-height:60vh; text-align:center; animation: fadeIn 0.6s ease;
}
.kiemaen-clover-logo {
  width: 130px; height: 130px;
  margin-bottom: 18px;
  filter: drop-shadow(0 4px 18px rgba(66,133,244,0.35));
}
.kiemaen-empty-state h1 {
  font-size: 32px;
  font-weight: 700;
  letter-spacing: 0.5px;
  margin: 0;
  background: linear-gradient(135deg, #4285f4 0%, #1a73e8 40%, #0a0a0a 100%);
  -webkit-background-clip: text;
  background-clip: text;
  -webkit-text-fill-color: transparent;
  color: transparent;
}
.kiemaen-empty-state p.tagline {
  color:#8ab4f8; font-size:15px; margin-top:8px; opacity:0.85; font-weight:400;
}
@keyframes fadeIn { from{opacity:0; transform:translateY(10px);} to{opacity:1; transform:translateY(0);} }

.gemini-input-bar {
  display:flex; align-items:center; gap:8px;
  background:#1e1f22; border-radius:32px; padding:8px 10px 8px 16px;
  margin:12px; box-shadow:0 2px 10px rgba(0,0,0,0.3);
}
.gemini-input-bar input, .gemini-input-bar textarea {
  background:transparent !important; border:none !important; color:#e8eaed !important;
  outline:none !important; flex:1; font-size:16px; resize:none;
}
.gemini-icon-btn {
  background:transparent; border:none; color:#9aa0a6; cursor:pointer;
  display:flex; align-items:center; justify-content:center;
  width:36px; height:36px; border-radius:50%; transition:background 0.15s;
}
.gemini-icon-btn:hover { background:rgba(255,255,255,0.08); }
.gemini-voice-btn {
  width:40px; height:40px; border-radius:50%;
  background:linear-gradient(135deg,#4285f4,#0a0a0a);
  display:flex; align-items:center; justify-content:center;
  border:none; cursor:pointer; flex-shrink:0;
  box-shadow:0 2px 8px rgba(66,133,244,0.4);
}
.gemini-voice-btn:hover { filter:brightness(1.15); }
.gemini-voice-btn.jarvis-active { animation: pulseVoice 1.2s infinite; }
@keyframes pulseVoice {
  0% { box-shadow:0 0 0 0 rgba(66,133,244,0.5); }
  70% { box-shadow:0 0 0 12px rgba(66,133,244,0); }
  100% { box-shadow:0 0 0 0 rgba(66,133,244,0); }
}
</style>
"""

CLOVER_SVG = """
<svg class="kiemaen-clover-logo" viewBox="0 0 200 200" xmlns="http://www.w3.org/2000/svg">
  <defs>
    <linearGradient id="cloverGrad" x1="0%" y1="0%" x2="100%" y2="100%">
      <stop offset="0%" stop-color="#5b9bff"/>
      <stop offset="45%" stop-color="#1a73e8"/>
      <stop offset="100%" stop-color="#050810"/>
    </linearGradient>
  </defs>
  <g transform="translate(100,100)">
    <g id="leafGroup">
      <path d="M0,0 C-22,-30 -22,-70 0,-95 C22,-70 22,-30 0,0 Z" fill="url(#cloverGrad)"/>
    </g>
    <use href="#leafGroup" transform="rotate(72)"/>
    <use href="#leafGroup" transform="rotate(144)"/>
    <use href="#leafGroup" transform="rotate(216)"/>
    <use href="#leafGroup" transform="rotate(288)"/>
    <circle r="10" fill="#0a0a0a" stroke="#4285f4" stroke-width="2"/>
  </g>
</svg>
"""

JS_BLOCK = """
<script id="kiemaen-logo-ui-patch">
(function(){
  function init(){
    var chatArea = document.getElementById('chatArea') || document.querySelector('.chat-area') || document.querySelector('main');
    if (chatArea && !document.querySelector('.kiemaen-empty-state')) {
      var empty = document.createElement('div');
      empty.className = 'kiemaen-empty-state';
      empty.innerHTML = `""" + CLOVER_SVG + """<h1>Kiemaen AI</h1><p class="tagline">Your ultimate agentic assistant</p>`;
      chatArea.prepend(empty);

      var observer = new MutationObserver(function(){
        var hasMessages = chatArea.querySelectorAll('.message').length > 0;
        empty.style.display = hasMessages ? 'none' : 'flex';
      });
      observer.observe(chatArea, { childList: true });
    }

    var textarea = document.querySelector('textarea');
    if (textarea) {
      var bar = textarea.closest('div');
      if (bar && !bar.classList.contains('gemini-input-bar')) {
        bar.classList.add('gemini-input-bar');
      }
      if (!document.querySelector('.gemini-voice-btn')) {
        var voiceBtn = document.createElement('button');
        voiceBtn.className = 'gemini-voice-btn';
        voiceBtn.title = 'Start voice conversation';
        voiceBtn.innerHTML = '<span class="material-symbols-outlined" style="color:#fff;font-size:20px;">graphic_eq</span>';
        voiceBtn.onclick = function(){
          if (typeof toggleJarvis === 'function') {
            toggleJarvis();
            voiceBtn.classList.toggle('jarvis-active');
          }
        };
        bar.appendChild(voiceBtn);
      }
    }
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
  setTimeout(init, 500);
})();
</script>
"""

html = html.replace("</head>", CSS_BLOCK + "\\n</head>", 1)
html = html.replace("</body>", JS_BLOCK + "\\n</body>", 1)

with open("web/index.html", "w") as f:
    f.write(html)

print("Patched web/index.html with 5-leaf clover logo + Kiemaen AI branding.")

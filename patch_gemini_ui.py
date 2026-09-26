with open("web/index.html", "r") as f:
    html = f.read()

CSS_BLOCK = """
<style id="gemini-style-patch">
html, body {
  background: linear-gradient(180deg, #0a0a0a 0%, #0a0a0a 55%, #16213e 100%) !important;
  min-height: 100vh;
}
#chatArea, .chat-area, .messages, main {
  background: transparent !important;
}
.gemini-empty-state {
  display:flex; flex-direction:column; align-items:center; justify-content:center;
  height:65vh; text-align:center; padding:20px; animation: fadeIn 0.6s ease;
}
.gemini-empty-state .sparkle-icon {
  font-size:52px; margin-bottom:22px;
  background: linear-gradient(135deg,#ff6b6b,#feca57,#48dbfb,#1dd1a1,#a55eea);
  -webkit-background-clip:text; background-clip:text; -webkit-text-fill-color:transparent;
  color: transparent;
}
.gemini-empty-state h2 {
  font-size:26px; font-weight:400; color:#e8eaed; margin:0; line-height:1.4;
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
  background:linear-gradient(135deg,#4285f4,#1a73e8);
  display:flex; align-items:center; justify-content:center;
  border:none; cursor:pointer; flex-shrink:0;
  box-shadow:0 2px 8px rgba(66,133,244,0.4);
}
.gemini-voice-btn:hover { filter:brightness(1.1); }
.gemini-voice-btn.jarvis-active {
  animation: pulseVoice 1.2s infinite;
}
@keyframes pulseVoice {
  0% { box-shadow:0 0 0 0 rgba(66,133,244,0.5); }
  70% { box-shadow:0 0 0 12px rgba(66,133,244,0); }
  100% { box-shadow:0 0 0 0 rgba(66,133,244,0); }
}
.gemini-header {
  display:flex; align-items:center; justify-content:space-between;
  padding:14px 16px; background:transparent;
}
.gemini-header .brand-row { display:flex; align-items:center; gap:6px; color:#e8eaed; font-size:17px; }
</style>
"""

JS_BLOCK = """
<script id="gemini-ui-patch">
(function(){
  function init(){
    // 1. Insert empty-state greeting if chat is empty
    var chatArea = document.getElementById('chatArea') || document.querySelector('.chat-area') || document.querySelector('main');
    if (chatArea && !document.querySelector('.gemini-empty-state')) {
      var empty = document.createElement('div');
      empty.className = 'gemini-empty-state';
      empty.innerHTML = '<span class="material-symbols-outlined sparkle-icon">auto_awesome</span><h2>Where should we start?</h2>';
      chatArea.prepend(empty);

      var observer = new MutationObserver(function(){
        var hasMessages = chatArea.querySelectorAll('.message').length > 0;
        empty.style.display = hasMessages ? 'none' : 'flex';
      });
      observer.observe(chatArea, { childList: true });
    }

    // 2. Wrap input bar with gemini styling class
    var textarea = document.querySelector('textarea');
    if (textarea) {
      var bar = textarea.closest('div');
      if (bar && !bar.classList.contains('gemini-input-bar')) {
        bar.classList.add('gemini-input-bar');
      }

      // 3. Add distinct blue voice-mode button if not already present
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

    // 4. Style header if found
    var header = document.querySelector('header') || document.querySelector('.header');
    if (header) header.classList.add('gemini-header');
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
  setTimeout(init, 500); // retry in case elements load late
})();
</script>
"""

changed = False
if "gemini-style-patch" not in html:
    html = html.replace("</head>", CSS_BLOCK + "\\n</head>", 1)
    changed = True
if "gemini-ui-patch" not in html:
    html = html.replace("</body>", JS_BLOCK + "\\n</body>", 1)
    changed = True

if changed:
    with open("web/index.html", "w") as f:
        f.write(html)
    print("Patched web/index.html with Gemini-style UI.")
else:
    print("Already patched — no changes made.")

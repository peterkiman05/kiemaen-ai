with open("web/index.html", "r") as f:
    html = f.read()

if "kiemaen-voice-speed" in html:
    print("Already patched.")
else:
    JS_BLOCK = """
<script id="kiemaen-voice-speed">
(function(){
  function init(){
    if (typeof recognition === 'undefined' || !recognition) {
      setTimeout(init, 300);
      return;
    }

    // 1. FASTER SETTINGS: interim results = instant partial feedback,
    //    non-continuous = auto-finalizes quickly after you stop talking
    try {
      recognition.interimResults = true;
      recognition.continuous = false;
      recognition.maxAlternatives = 1;
    } catch(e){}

    // 2. INSTANT VISUAL FEEDBACK the moment recognition truly starts
    recognition.addEventListener('start', function(){
      var btn = document.getElementById('actionBtn');
      if (btn) btn.classList.add('jarvis-active');
      if (typeof updateMicVisual === 'function') updateMicVisual('listening');
    });

    // 3. Show live interim transcript in the input box as you speak
    recognition.addEventListener('result', function(e){
      var txt = '';
      for (var i = e.resultIndex; i < e.results.length; i++) {
        txt += e.results[i][0].transcript;
      }
      var input = document.getElementById('userInput');
      if (input) input.value = txt;
    });

    console.log('[Kiemaen] Voice speed patch applied.');
  }

  // 4. Pre-warm the TTS engine so first reply speaks instantly (no cold-start lag)
  function warmTTS(){
    if (window.speechSynthesis) {
      window.speechSynthesis.getVoices();
      window.speechSynthesis.onvoiceschanged = function(){
        window.speechSynthesis.getVoices();
      };
    }
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', function(){ init(); warmTTS(); });
  } else {
    init(); warmTTS();
  }
})();
</script>
"""
    html = html.replace("</body>", JS_BLOCK + "\\n</body>", 1)
    with open("web/index.html", "w") as f:
        f.write(html)
    print("Patched web/index.html with voice speed improvements.")

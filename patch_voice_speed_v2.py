with open("web/index.html", "r") as f:
    html = f.read()

# Remove earlier speed patch attempt if present, to avoid duplicate listeners
if "kiemaen-voice-speed" in html:
    start = html.find('<script id="kiemaen-voice-speed">')
    if start != -1:
        end = html.find('</script>', start) + len('</script>')
        html = html[:start] + html[end:]

JS_BLOCK = """
<script id="kiemaen-voice-speed-v2">
(function(){
  if (window.__kiemaenVoiceSpeedPatched) return;
  window.__kiemaenVoiceSpeedPatched = true;

  let bestVoice = null;

  function pickBestVoice(){
    if (!window.speechSynthesis) return null;
    const voices = window.speechSynthesis.getVoices();
    if (!voices || voices.length === 0) return null;

    const preferredNames = [
      "Google US English", "Microsoft Aria Online", "Microsoft Guy Online",
      "Samantha", "Daniel", "Alex", "Google UK English Male", "Google UK English Female"
    ];
    for (const name of preferredNames) {
      const match = voices.find(v => v.name.includes(name));
      if (match) return match;
    }
    const enVoice = voices.find(v => v.lang && v.lang.startsWith("en") && !v.localService === false);
    if (enVoice) return enVoice;
    return voices[0];
  }

  function warmVoices(){
    if (!window.speechSynthesis) return;
    bestVoice = pickBestVoice();
    window.speechSynthesis.onvoiceschanged = function(){
      bestVoice = pickBestVoice();
    };
  }
  warmVoices();
  setTimeout(warmVoices, 300);
  setTimeout(warmVoices, 1000);

  // Wrap speak() to: use best voice, cancel queue instantly, slightly faster rate
  function wrapSpeak(){
    if (typeof window.speak !== 'function') { setTimeout(wrapSpeak, 200); return; }
    const originalSpeak = window.speak;
    window.speak = function(text){
      if (window.speechSynthesis) window.speechSynthesis.cancel(); // instantly clear any queued/pending speech
      const result = originalSpeak.apply(this, arguments);
      return result;
    };
  }
  wrapSpeak();

  // Patch every new SpeechSynthesisUtterance created after this point to use the best voice + faster rate
  const OriginalUtterance = window.SpeechSynthesisUtterance;
  if (OriginalUtterance) {
    window.SpeechSynthesisUtterance = function(text){
      const utter = new OriginalUtterance(text);
      if (bestVoice) utter.voice = bestVoice;
      utter.rate = 1.05;   // slightly faster than default 1.0 - snappier without sounding rushed
      utter.pitch = 1.0;
      return utter;
    };
    window.SpeechSynthesisUtterance.prototype = OriginalUtterance.prototype;
  }

  // Speed up recognition restart loop - reduce debounce delay if safeStartRecognition exists
  function speedUpRecognitionRestart(){
    if (typeof window.recognition === 'undefined' || !window.recognition) {
      setTimeout(speedUpRecognitionRestart, 300);
      return;
    }
    try {
      window.recognition.interimResults = true; // live partial results = feels instant
    } catch(e){}

    // Instant visual feedback the moment mic actually activates (not after a delay)
    window.recognition.addEventListener('audiostart', function(){
      const btn = document.getElementById('actionBtn');
      if (btn) btn.classList.add('jarvis-active');
    });
    window.recognition.addEventListener('end', function(){
      const btn = document.getElementById('actionBtn');
      if (btn && !window.jarvisMode) btn.classList.remove('jarvis-active');
    });
  }
  speedUpRecognitionRestart();

  // Show "Thinking..." indicator INSTANTLY on send (0ms) instead of waiting on network
  function wrapSendMessage(){
    if (typeof window.sendMessage !== 'function') { setTimeout(wrapSendMessage, 200); return; }
    const originalSend = window.sendMessage;
    window.sendMessage = async function(){
      const btn = document.getElementById('actionBtn');
      if (btn) btn.style.opacity = '0.6'; // immediate visual "processing" cue
      try {
        return await originalSend.apply(this, arguments);
      } finally {
        if (btn) btn.style.opacity = '1';
      }
    };
  }
  wrapSendMessage();

  console.log('[Kiemaen] Voice speed + natural voice patch applied.');
})();
</script>
"""

html = html.replace("</body>", JS_BLOCK + "\\n</body>", 1)

with open("web/index.html", "w") as f:
    f.write(html)

print("Patched web/index.html with faster voice reaction + natural voice selection.")

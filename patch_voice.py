import re

with open("web/index.html", "r", encoding="utf-8") as f:
    html = f.read()

new_script = '''<script>
let token = localStorage.getItem('kiemaen_token') || null;
let isAdmin = false;
let authMode = 'login';
let ttsEnabled = true;

const notebook = document.getElementById('notebookText');
notebook.value = localStorage.getItem('kiemaen_notebook') || '';
notebook.addEventListener('input', () => localStorage.setItem('kiemaen_notebook', notebook.value));

function toggleSidebar() {
  document.getElementById('sidebar').classList.toggle('open');
  document.getElementById('overlay').classList.toggle('open');
}
function newChat() {
  document.getElementById('chat-container').innerHTML = '';
  toggleSidebar();
  addMessage("New session started.", "bot");
}

function openAuthModal(){ document.getElementById('authModal').classList.add('open'); }
function closeAuthModal(){ document.getElementById('authModal').classList.remove('open'); }
function switchAuthMode(){
  authMode = authMode === 'login' ? 'register' : 'login';
  document.getElementById('authTitle').innerText = authMode === 'login' ? 'Login' : 'Register';
  document.getElementById('authSubmitBtn').innerText = authMode === 'login' ? 'Login' : 'Create Account';
  document.getElementById('authSwitch').innerText = authMode === 'login' ? "Don't have an account? Register" : "Already have an account? Login";
}
async function submitAuth(){
  const username = document.getElementById('authUsername').value.trim();
  const password = document.getElementById('authPassword').value;
  if(!username || !password) return;
  const fd = new FormData();
  fd.append('username', username);
  fd.append('password', password);
  const endpoint = authMode === 'login' ? '/login' : '/register';
  const res = await fetch(endpoint, { method:'POST', body: fd });
  const data = await res.json();
  if(data.status === 'ok'){
    token = data.token;
    localStorage.setItem('kiemaen_token', token);
    isAdmin = data.is_admin;
    updateAuthUI(data.username, data.is_admin);
    closeAuthModal();
  } else {
    alert(data.message);
  }
}
function updateAuthUI(username, admin){
  document.getElementById('authBtn').innerText = username;
  document.getElementById('adminBadge').style.display = admin ? 'inline-block' : 'none';
}
async function checkSession(){
  if(!token) return;
  const res = await fetch('/me', { headers: { 'X-Session-Token': token } });
  const data = await res.json();
  if(data.username && data.username !== 'guest'){
    isAdmin = data.is_admin;
    updateAuthUI(data.username, data.is_admin);
  }
}
checkSession();

function handleInput(){
  const input = document.getElementById("userInput");
  const icon = document.getElementById("actionIcon");
  input.style.height = '';
  input.style.height = Math.min(input.scrollHeight, 150) + 'px';
  if(input.value.trim().length > 0){
    icon.innerText = "send";
    updateMicVisual('idle');
  } else {
    icon.innerText = "mic";
    if(jarvisMode) updateMicVisual(voiceState);
  }
}
function handleAction(){
  const icon = document.getElementById("actionIcon").innerText;
  if(icon === "send") sendMessage();
  else toggleJarvis();
}

function toggleTTS(){
  ttsEnabled = !ttsEnabled;
  const btn = document.getElementById('ttsToggle');
  btn.classList.toggle('active-toggle', ttsEnabled);
  if(!ttsEnabled) window.speechSynthesis.cancel();
}
document.getElementById('ttsToggle').classList.add('active-toggle');

/* ================= VOICE ENGINE (rebuilt) ================= */
const SpeechRecognitionAPI = window.SpeechRecognition || window.webkitSpeechRecognition;
let recognition = null;
let jarvisMode = false;
let voiceState = 'idle'; // idle | listening | speaking | thinking
let recognitionActive = false;
let restartTimer = null;

function updateMicVisual(state){
  voiceState = state;
  const btn = document.getElementById('actionBtn');
  btn.classList.remove('jarvis-active');
  if(!jarvisMode) return;
  if(state === 'listening' || state === 'speaking' || state === 'thinking'){
    btn.classList.add('jarvis-active');
  }
  btn.title = state === 'listening' ? 'Listening...' :
              state === 'speaking' ? 'Speaking...' :
              state === 'thinking' ? 'Processing...' : 'Voice Mode';
}

function safeStartRecognition(){
  if(!recognition || recognitionActive || !jarvisMode) return;
  if(voiceState === 'speaking' || voiceState === 'thinking') return;
  clearTimeout(restartTimer);
  restartTimer = setTimeout(() => {
    if(!jarvisMode || recognitionActive) return;
    try {
      recognition.start();
    } catch(e){
      // Already started or transient error - ignore, next cycle will retry
      console.warn('Recognition start skipped:', e.message);
    }
  }, 350);
}

if(SpeechRecognitionAPI){
  recognition = new SpeechRecognitionAPI();
  recognition.continuous = false;
  recognition.interimResults = false;
  recognition.lang = 'en-US';

  recognition.onstart = () => {
    recognitionActive = true;
    updateMicVisual('listening');
  };

  recognition.onresult = (event) => {
    const text = event.results[0][0].transcript;
    document.getElementById("userInput").value = text;
    updateMicVisual('thinking');
    sendMessage();
  };

  recognition.onend = () => {
    recognitionActive = false;
    if(jarvisMode && voiceState !== 'speaking' && voiceState !== 'thinking'){
      updateMicVisual('idle');
      safeStartRecognition();
    }
  };

  recognition.onerror = (e) => {
    recognitionActive = false;
    if(e.error === 'not-allowed' || e.error === 'service-not-allowed'){
      jarvisMode = false;
      updateMicVisual('idle');
      addMessage("Microphone access was blocked. Please allow mic permission in your browser settings and try again.", "error");
      return;
    }
    if(jarvisMode && (e.error === 'no-speech' || e.error === 'network' || e.error === 'aborted')){
      safeStartRecognition();
    }
  };
} else {
  console.warn("SpeechRecognition not supported in this browser.");
}

function toggleJarvis(){
  if(!recognition){
    addMessage("Voice input is not supported in this browser. Try Chrome on Android.", "error");
    return;
  }
  jarvisMode = !jarvisMode;
  if(jarvisMode){
    // Unlock TTS engine with a near-silent utterance triggered by this user tap
    try {
      const unlock = new SpeechSynthesisUtterance(' ');
      unlock.volume = 0;
      window.speechSynthesis.speak(unlock);
    } catch(e){}
    safeStartRecognition();
  } else {
    clearTimeout(restartTimer);
    if(recognitionActive){ try { recognition.stop(); } catch(e){} }
    window.speechSynthesis.cancel();
    updateMicVisual('idle');
  }
}

function speak(text){
  if(!ttsEnabled || !('speechSynthesis' in window)) return;
  window.speechSynthesis.cancel();

  if(jarvisMode){
    clearTimeout(restartTimer);
    if(recognitionActive){ try { recognition.stop(); } catch(e){} }
    updateMicVisual('speaking');
  }

  let cleanText = text.replace(/```[\\s\\S]*?```/g, "Code provided on screen.")
                       .replace(/[*_#]/g, "")
                       .replace(/<[^>]*>?/gm, '');

  if(!cleanText.trim()){
    if(jarvisMode) safeStartRecognition();
    return;
  }

  let utterance = new SpeechSynthesisUtterance(cleanText);
  utterance.rate = 1.05;

  utterance.onend = () => {
    if(jarvisMode){
      updateMicVisual('idle');
      safeStartRecognition();
    }
  };
  utterance.onerror = () => {
    if(jarvisMode){
      updateMicVisual('idle');
      safeStartRecognition();
    }
  };

  window.speechSynthesis.speak(utterance);
}
/* =============== END VOICE ENGINE =============== */

function addMessage(text, sender, category){
  const chat = document.getElementById("chat-container");
  const wrapper = document.getElementById("chat-wrapper");

  const msgDiv = document.createElement("div");
  msgDiv.className = `message ${sender}`;

  if(sender === 'bot' && category && category !== 'general'){
    const tag = document.createElement("div");
    tag.className = "category-tag";
    tag.innerText = category.replace('_',' ');
    msgDiv.appendChild(tag);
  }

  const bubbleDiv = document.createElement("div");
  bubbleDiv.className = "bubble";

  if(sender === 'bot'){
    bubbleDiv.innerHTML = marked.parse(String(text));
    bubbleDiv.querySelectorAll("pre code").forEach((block) => {
      hljs.highlightElement(block);
      const pre = block.parentElement;
      const header = document.createElement("div");
      header.className = "code-header";
      const lang = document.createElement("span");
      lang.style.cssText = "font-size:12px;color:#888;text-transform:uppercase;";
      lang.innerText = block.className.replace('hljs','').trim() || "code";
      const actions = document.createElement("div");
      actions.className = "code-actions";
      const copyBtn = document.createElement("button");
      copyBtn.innerHTML = '<span class="material-symbols-outlined" style="font-size:16px;">content_copy</span>';
      copyBtn.onclick = () => navigator.clipboard.writeText(block.innerText);
      const playBtn = document.createElement("button");
      playBtn.innerHTML = '<span class="material-symbols-outlined" style="font-size:16px;">play_arrow</span>';
      playBtn.onclick = () => { const win = window.open("", "_blank"); win.document.write(block.innerText); };
      actions.append(copyBtn, playBtn);
      header.append(lang, actions);
      pre.parentNode.insertBefore(header, pre);
    });
  } else {
    bubbleDiv.innerText = String(text);
  }

  msgDiv.appendChild(bubbleDiv);
  chat.appendChild(msgDiv);
  setTimeout(() => { wrapper.scrollTop = wrapper.scrollHeight; }, 100);
}

async function sendMessage(){
  const input = document.getElementById("userInput");
  const imageInput = document.getElementById("imageInput");
  const text = input.value.trim();
  const file = imageInput.files[0];
  if(!text && !file) return;

  addMessage(text || "[Image Attached]", "user");
  input.value = "";
  handleInput();

  const formData = new FormData();
  if(text){ formData.append("msg", text); formData.append("prompt", text); }
  if(file){ formData.append("image", file); imageInput.value = ""; }

  const loadingId = "load-" + Date.now();
  document.getElementById("chat-container").insertAdjacentHTML('beforeend',
    `<div id="${loadingId}" class="message bot"><div class="bubble">Thinking...</div></div>`);
  document.getElementById("chat-wrapper").scrollTop = document.getElementById("chat-wrapper").scrollHeight;

  try {
    const headers = {};
    if(token) headers['X-Session-Token'] = token;
    let response = await fetch("/chat", { method: "POST", body: formData, headers });
    document.getElementById(loadingId)?.remove();

    if(!response.ok){
      throw new Error(`Connection issue (${response.status}).`);
    }
    let result = await response.json();

    let finalResponse = result.response || result.reply || result.message || "Done.";
    if(Array.isArray(finalResponse)) finalResponse = finalResponse[0];
    finalResponse = String(finalResponse);

    if(result.status === 'error'){
      addMessage(finalResponse, "error");
      if(jarvisMode){ updateMicVisual('idle'); safeStartRecognition(); }
    } else {
      addMessage(finalResponse, "bot", result.category);
      speak(finalResponse);
    }
  } catch(error){
    document.getElementById(loadingId)?.remove();
    addMessage("I ran into an issue processing that. Please try again.", "error");
    if(jarvisMode){ updateMicVisual('idle'); safeStartRecognition(); }
  }
}
</script>'''

# Replace everything between the first <script> and last </script>
pattern = re.compile(r"<script>.*</script>", re.DOTALL)
if pattern.search(html):
    html = pattern.sub(lambda m: new_script, html)
    with open("web/index.html", "w", encoding="utf-8") as f:
        f.write(html)
    print("✅ Voice engine successfully rebuilt inside web/index.html")
else:
    print("⚠️ Could not find a <script> block to replace. No changes made.")

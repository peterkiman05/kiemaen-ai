with open("web/index.html", "r") as f:
    html = f.read()

if "kiemaen-history-patch" in html:
    print("Already patched.")
else:
    CSS_BLOCK = """
<style id="kiemaen-history-patch">
* { box-sizing: border-box; }

#sidebar {
  max-width: 85vw !important;
}

.chat-history-section {
  display:flex; flex-direction:column; gap:6px;
  max-height:32vh; overflow-y:auto;
  border-bottom:1px solid #333; padding-bottom:12px; margin-bottom:4px;
}
.chat-history-title {
  font-size:12px; color:#8ab4f8; text-transform:uppercase;
  letter-spacing:0.5px; margin-bottom:4px;
}
.chat-history-item {
  background:#282a2c; color:#c4c7c5; padding:10px 12px; border-radius:8px;
  font-size:13px; cursor:pointer; display:flex; align-items:center;
  justify-content:space-between; gap:6px;
}
.chat-history-item:hover { background:#333537; }
.chat-title-text {
  white-space:nowrap; overflow:hidden; text-overflow:ellipsis; flex:1;
}
.chat-history-item .del-btn {
  font-size:16px; opacity:0.55; flex-shrink:0;
}
.chat-history-item .del-btn:hover { opacity:1; color:#ff8a80; }

@media (max-width: 380px) {
  .kiemaen-empty-state h1 { font-size: 30px !important; }
  .kiemaen-clover-logo { width: 110px !important; height: 110px !important; }
}

/* Ensure input bar and chat never overflow horizontally on narrow screens */
#input-area, #chat-container, .input-wrapper {
  max-width: 100vw;
}
</style>
"""

    JS_BLOCK = """
<script id="kiemaen-history-patch-js">
(function(){
  if (window.__kiemaenHistoryPatched) return;
  window.__kiemaenHistoryPatched = true;

  const HISTORY_KEY = 'kiemaen_chat_history';
  const CURRENT_ID_KEY = 'kiemaen_current_chat_id';

  function loadHistory(){
    try { return JSON.parse(localStorage.getItem(HISTORY_KEY)) || []; }
    catch(e){ return []; }
  }
  function saveHistory(list){ localStorage.setItem(HISTORY_KEY, JSON.stringify(list)); }
  function getCurrentId(){
    let id = localStorage.getItem(CURRENT_ID_KEY);
    if (!id) { id = 'chat_' + Date.now(); localStorage.setItem(CURRENT_ID_KEY, id); }
    return id;
  }
  function setCurrentId(id){ localStorage.setItem(CURRENT_ID_KEY, id); }

  function getFirstUserMessageText(){
    const container = document.getElementById('chat-container');
    if (!container) return 'New Chat';
    const userMsg = container.querySelector('.message.user .bubble');
    if (userMsg) {
      const t = userMsg.textContent.trim();
      return t.length > 34 ? t.slice(0,34) + '...' : (t || 'New Chat');
    }
    return 'New Chat';
  }

  function saveCurrentChat(){
    const container = document.getElementById('chat-container');
    if (!container) return;
    if (container.querySelectorAll('.message').length === 0) return;

    const id = getCurrentId();
    const entry = { id, title: getFirstUserMessageText(), timestamp: Date.now(), html: container.innerHTML };
    let list = loadHistory();
    const idx = list.findIndex(c => c.id === id);
    if (idx >= 0) list[idx] = entry; else list.unshift(entry);
    list = list.slice(0, 30);
    saveHistory(list);
  }

  function renderHistoryList(){
    const sidebarContent = document.querySelector('.sidebar-content');
    if (!sidebarContent) return;
    let section = document.getElementById('chatHistorySection');
    if (!section) {
      section = document.createElement('div');
      section.className = 'chat-history-section';
      section.id = 'chatHistorySection';
      const newChatBtn = sidebarContent.querySelector('.new-chat-btn');
      if (newChatBtn && newChatBtn.nextSibling) {
        sidebarContent.insertBefore(section, newChatBtn.nextSibling);
      } else {
        sidebarContent.insertBefore(section, sidebarContent.firstChild.nextSibling || null);
      }
    }
    const list = loadHistory();
    section.innerHTML = '<div class="chat-history-title">Recent Chats</div>';
    if (list.length === 0) {
      const empty = document.createElement('div');
      empty.style.cssText = 'font-size:12px;color:#777;padding:6px 0;';
      empty.textContent = 'No previous chats yet';
      section.appendChild(empty);
      return;
    }
    list.forEach(chat => {
      const item = document.createElement('div');
      item.className = 'chat-history-item';
      item.innerHTML = '<span class="chat-title-text"></span><span class="material-symbols-outlined del-btn">close</span>';
      item.querySelector('.chat-title-text').textContent = chat.title;
      item.querySelector('.chat-title-text').onclick = () => loadChat(chat.id);
      item.querySelector('.del-btn').onclick = (e) => { e.stopPropagation(); deleteChat(chat.id); };
      section.appendChild(item);
    });
  }

  function loadChat(id){
    saveCurrentChat();
    const chat = loadHistory().find(c => c.id === id);
    const container = document.getElementById('chat-container');
    if (chat && container) {
      container.innerHTML = chat.html;
      setCurrentId(id);
    }
    if (typeof toggleSidebar === 'function') toggleSidebar();
    renderHistoryList();
  }

  function deleteChat(id){
    saveHistory(loadHistory().filter(c => c.id !== id));
    if (getCurrentId() === id) localStorage.removeItem(CURRENT_ID_KEY);
    renderHistoryList();
  }

  function wrapNewChat(){
    if (typeof window.newChat !== 'function') { setTimeout(wrapNewChat, 200); return; }
    const original = window.newChat;
    window.newChat = function(){
      saveCurrentChat();
      localStorage.removeItem(CURRENT_ID_KEY);
      original();
      renderHistoryList();
    };
  }

  function wrapSendMessage(){
    if (typeof window.sendMessage !== 'function') { setTimeout(wrapSendMessage, 200); return; }
    const original = window.sendMessage;
    window.sendMessage = async function(){
      const result = await original.apply(this, arguments);
      setTimeout(saveCurrentChat, 600);
      setTimeout(renderHistoryList, 700);
      return result;
    };
  }

  function init(){
    renderHistoryList();
    wrapNewChat();
    wrapSendMessage();
    const container = document.getElementById('chat-container');
    if (container && container.querySelectorAll('.message').length === 0) {
      const id = localStorage.getItem(CURRENT_ID_KEY);
      if (id) {
        const chat = loadHistory().find(c => c.id === id);
        if (chat) {
          container.innerHTML = chat.html;
          const emptyState = document.getElementById('kiemaenEmptyState');
          if (emptyState) emptyState.remove();
        }
      }
    }
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
  setTimeout(init, 400);
})();
</script>
"""
    html = html.replace("</head>", CSS_BLOCK + "\\n</head>", 1)
    html = html.replace("</body>", JS_BLOCK + "\\n</body>", 1)
    with open("web/index.html", "w") as f:
        f.write(html)
    print("Patched web/index.html with chat history panel + mobile responsive fixes.")

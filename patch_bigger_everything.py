with open("web/index.html", "r") as f:
    html = f.read()

if "kiemaen-bigger-ui" in html:
    print("Already patched - removing old version first to refresh values.")
    start = html.find('<style id="kiemaen-bigger-ui">')
    end = html.find('</style>', start) + len('</style>')
    html = html[:start] + html[end:]

CSS_BLOCK = """
<style id="kiemaen-bigger-ui">
/* ===== GLOBAL BASE FONT BUMP ===== */
html { font-size: 18px !important; }

/* ===== HEADER ===== */
#header { padding: 14px 16px !important; }
#header .brand { font-size: 20px !important; font-weight: 600 !important; }
#adminBadge { font-size: 13px !important; padding: 4px 10px !important; }
.login-btn { font-size: 15px !important; padding: 10px 20px !important; border-radius: 22px !important; }
.menu-btn .material-symbols-outlined { font-size: 28px !important; }

/* ===== SIDEBAR ===== */
.sidebar-header .brand { font-size: 19px !important; }
.new-chat-btn { font-size: 16px !important; padding: 14px !important; }
.new-chat-btn .material-symbols-outlined { font-size: 22px !important; }
.notebook-area h3 { font-size: 16px !important; }
#notebookText { font-size: 15px !important; padding: 14px !important; }
.chat-history-title { font-size: 13px !important; }
.chat-history-item { font-size: 15px !important; padding: 12px 14px !important; }
.chat-history-item .del-btn { font-size: 19px !important; }

/* ===== CHAT MESSAGES ===== */
.bubble { font-size: 18px !important; line-height: 1.7 !important; padding: 14px 22px !important; }
.message.user .bubble { border-radius: 26px 26px 4px 26px !important; }
.category-tag { font-size: 13px !important; }
.message { margin-bottom: 34px !important; }

/* ===== CODE BLOCKS ===== */
pre, pre code { font-size: 15px !important; line-height: 1.6 !important; }
.code-header { font-size: 14px !important; padding: 10px 16px !important; }
.code-actions button { font-size: 14px !important; padding: 6px 14px !important; }

/* ===== MESSAGE ACTION BUTTONS (copy/read-aloud) ===== */
.msg-actions { gap: 10px !important; margin-top: 8px !important; }
.msg-action-btn { padding: 8px !important; }
.msg-action-btn .material-symbols-outlined { font-size: 22px !important; }

/* ===== INPUT BAR ===== */
.input-wrapper { padding: 12px 14px 12px 20px !important; gap: 8px !important; }
#userInput { font-size: 17px !important; }
.input-wrapper .icon-btn { width: 44px !important; height: 44px !important; }
.input-wrapper .icon-btn .material-symbols-outlined { font-size: 26px !important; }
#actionBtn { width: 48px !important; height: 48px !important; }
#actionBtn #actionIcon { font-size: 26px !important; }

/* ===== EMPTY STATE (logo + title) ===== */
.kiemaen-clover-logo { width: 170px !important; height: 170px !important; }
.kiemaen-empty-state h1 { font-size: 42px !important; }

/* ===== AUTH MODAL ===== */
.modal-overlay input, .modal-overlay button { font-size: 16px !important; padding: 14px !important; }
#authTitle { font-size: 22px !important; }
.switch-link { font-size: 14px !important; }
</style>
"""

html = html.replace("</head>", CSS_BLOCK + "\\n</head>", 1)

with open("web/index.html", "w") as f:
    f.write(html)

print("Patched web/index.html: significantly larger fonts, icons, buttons, and tap targets everywhere.")

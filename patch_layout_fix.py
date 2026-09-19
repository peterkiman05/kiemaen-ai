with open("web/index.html", "r") as f:
    html = f.read()

CSS_BLOCK = """
<style id="kiemaen-layout-fix">
html, body {
  height: 100%;
  margin: 0;
  overflow: hidden;
}
body {
  display: flex;
  flex-direction: column;
  height: 100vh;
  height: 100dvh; /* dynamic viewport height - accounts for mobile browser chrome */
}

/* Force the app's root wrapper (whatever it's called) to fill height as flex column */
body > div:first-child,
#app, .app, #root {
  display: flex;
  flex-direction: column;
  height: 100%;
  flex: 1;
  min-height: 0;
}

/* Chat/message area should flex-grow and scroll internally, not create page-level empty space */
#chatArea, .chat-area, main {
  flex: 1 1 auto;
  min-height: 0;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
  justify-content: center; /* centers empty-state vertically within available space, not whole page */
}

.kiemaen-empty-state {
  padding-top: 0 !important; /* remove old top-offset, let flex centering handle position */
  min-height: unset !important;
  margin: auto 0;
}

/* Input bar stays pinned at bottom but close to content, not floating far below */
.gemini-input-bar {
  flex-shrink: 0;
  margin: 8px 12px 16px 12px !important;
}
</style>
"""

if "kiemaen-layout-fix" not in html:
    html = html.replace("</head>", CSS_BLOCK + "\\n</head>", 1)
    with open("web/index.html", "w") as f:
        f.write(html)
    print("Patched web/index.html with proper viewport-filling flex layout.")
else:
    print("Already patched.")

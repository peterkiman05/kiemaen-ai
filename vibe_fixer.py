import os
import re

print("🛠️ Initiating Vibe Code Fixer...")

# 1. Update web/index.html (Meta, OG, Favicon, Canonical)
html_path = "web/index.html"
if os.path.exists(html_path):
    with open(html_path, "r", encoding="utf-8") as f:
        html = f.read()
    
    if "og:title" not in html:
        meta_injection = """
    <!-- SEO & Open Graph Meta Tags -->
    <title>Kiemaen AI | Autonomous Android Agent</title>
    <meta name="description" content="Kiemaen AI is a powerful, locally-hosted AGI assistant built for Termux and Android.">
    <link rel="canonical" href="https://kiemaen-ai.onrender.com/">
    
    <!-- Open Graph Tags -->
    <meta property="og:title" content="Kiemaen AI Terminal">
    <meta property="og:description" content="Autonomous Termux-based AI Assistant for Huawei.">
    <meta property="og:image" content="https://kiemaen-ai.onrender.com/static/og-image.jpg">
    <meta property="og:url" content="https://kiemaen-ai.onrender.com/">
    <meta property="og:type" content="website">
    
    <!-- SVG Favicon (Emoji bypasses external file requests) -->
    <link rel="icon" href="data:image/svg+xml,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 100 100'><text y='.9em' font-size='90'>🤖</text></svg>">
"""
        html = html.replace("<head>", f"<head>\n{meta_injection}")
        
    # Strip console.logs to hide raw source traces
    html = re.sub(r'console\.log\(.*?\);?', '/* trace removed */', html)
    
    with open(html_path, "w", encoding="utf-8") as f:
        f.write(html)
    print("✅ Injected Meta tags, OG Previews, Canonical URLs, and an emoji Favicon into web/index.html")
else:
    print("⚠️ web/index.html not found. Skipping frontend fixes.")

# 2. Update main.py (Custom 404 and Sitemap)
main_path = "main.py"
if os.path.exists(main_path):
    with open(main_path, "r", encoding="utf-8") as f:
        main_code = f.read()

    if "custom_404_handler" not in main_code:
        injection = """

# --- VIBE CODE FIXES: 404 & SITEMAP ---
from fastapi.responses import JSONResponse, Response

@app.exception_handler(404)
async def custom_404_handler(request, exc):
    return JSONResponse(
        status_code=404,
        content={"status": "error", "message": "404: Route not found. The AI mainframe cannot locate this path."}
    )

@app.get("/sitemap.xml")
async def sitemap():
    xml_content = '''<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
  <url>
    <loc>https://kiemaen-ai.onrender.com/</loc>
    <changefreq>daily</changefreq>
    <priority>1.0</priority>
  </url>
</urlset>'''
    return Response(content=xml_content, media_type="application/xml")
"""
        with open(main_path, "a", encoding="utf-8") as f:
            f.write(injection)
        print("✅ Added Custom 404 handler and /sitemap.xml to main.py")
else:
    print("⚠️ main.py not found. Skipping backend fixes.")

# 3. Clean console logs in Python patch files
for file_name in ["patch_ui.py", "patch_voice.py", "app.py"]:
    if os.path.exists(file_name):
        with open(file_name, "r", encoding="utf-8") as f:
            content = f.read()
            
        new_content = re.sub(r'console\.log\(.*?\);?', '/* trace removed */', content)
        
        if content != new_content:
            with open(file_name, "w", encoding="utf-8") as f:
                f.write(new_content)
            print(f"✅ Stripped console.logs from {file_name}")

print("\n🚀 All fixes applied locally! Run git add, commit, and push to Render.")

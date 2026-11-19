with open("web/index.html", "r") as f:
    html = f.read()

if 'name="viewport"' in html:
    print("Viewport meta tag already present - no change needed.")
else:
    html = html.replace(
        "<head>",
        '<head>\\n<meta name="viewport" content="width=device-width, initial-scale=1.0">',
        1
    )
    with open("web/index.html", "w") as f:
        f.write(html)
    print("Viewport meta tag added.")

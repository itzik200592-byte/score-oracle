import pathlib
R = pathlib.Path(__file__).resolve().parent.parent
p = R / "docs/index.html"; s = p.read_text(encoding="utf-8")
s = s.replace('<link rel="stylesheet" href="style.css">', '<script>document.write(\'<link rel="stylesheet" href="style.css?v=\' + Math.floor(Date.now() / 300000) + \'">\')</script>')
s = s.replace('<script src="app.js"></script>\n<script src="verdict.js"></script>', '<script>var __v = Math.floor(Date.now() / 300000); document.write(\'<script src="app.js?v=\' + __v + \'"><\\/script><script src="verdict.js?v=\' + __v + \'"><\\/script>\')</script>')
p.write_text(s, encoding="utf-8")
print("cache-bust:", "style.css?v=" in s, "app.js?v=" in s)

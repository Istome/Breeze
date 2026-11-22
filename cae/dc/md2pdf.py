"""Render a Markdown report to a styled PDF with headless Chromium.
Usage: python3 md2pdf.py report.md out.pdf"""
import base64, os, re, sys, subprocess, json
import markdown

src, out = sys.argv[1], sys.argv[2]
base = os.path.dirname(os.path.abspath(src))
md = open(src, encoding="utf-8").read()


def inline_img(m):
    alt, path = m.group(1), m.group(2)
    p = os.path.join(base, path)
    data = base64.b64encode(open(p, "rb").read()).decode()
    return f'<figure><img alt="{alt}" src="data:image/png;base64,{data}"><figcaption>{alt}</figcaption></figure>'


html_body = markdown.markdown(md, extensions=["tables", "fenced_code", "toc", "attr_list", "sane_lists"])
html_body = re.sub(r'<p><img alt="([^"]*)" src="([^"]+)" ?/?></p>', inline_img, html_body)
css = """
@page { size: A4; margin: 18mm 16mm 18mm 16mm; }
body { font-family: 'DejaVu Sans', 'Liberation Sans', Arial, sans-serif; font-size: 10.2pt; line-height: 1.5; color: #1b2233; }
h1 { font-size: 22pt; color: #0e1630; border-bottom: 3px solid #2346d6; padding-bottom: 6px; margin-top: 0; }
h2 { font-size: 15pt; color: #0e1630; border-bottom: 1px solid #c9d2e3; padding-bottom: 3px; margin-top: 22px; page-break-after: avoid; }
h3 { font-size: 12pt; color: #2346d6; margin-top: 16px; page-break-after: avoid; }
h4 { font-size: 10.5pt; color: #c2410c; margin: 12px 0 4px; page-break-after: avoid; }
p, li { text-align: left; }
code { font-family: 'DejaVu Sans Mono', monospace; font-size: 8.6pt; background: #eef2fb; padding: 0 3px; border-radius: 3px; }
pre { background: #eef2fb; padding: 8px 10px; border-radius: 4px; font-size: 8.4pt; white-space: pre-wrap; page-break-inside: avoid; }
pre code { background: none; padding: 0; }
table { border-collapse: collapse; width: 100%; margin: 8px 0 12px; font-size: 8.6pt; page-break-inside: avoid; }
th { background: #0e1630; color: #fff; text-align: left; padding: 4px 6px; font-weight: 600; }
td { border-bottom: 1px solid #dde3ee; padding: 3.5px 6px; vertical-align: top; }
tr:nth-child(even) td { background: #f5f7fb; }
figure { margin: 10px 0 14px; page-break-inside: avoid; text-align: center; }
figure img { max-width: 100%; }
figcaption { font-size: 8.6pt; color: #4a5468; margin-top: 3px; text-align: left; }
blockquote { border-left: 4px solid #2346d6; margin: 10px 0; padding: 4px 12px; background: #f5f7fb; color: #1b2233; }
.pb { page-break-before: always; }
hr { border: 0; border-top: 1px solid #c9d2e3; margin: 16px 0; }
strong { color: #0e1630; }
"""
html = f"<!doctype html><html><head><meta charset='utf-8'><style>{css}</style></head><body>{html_body}</body></html>"
tmp = os.path.splitext(out)[0] + ".html"
open(tmp, "w", encoding="utf-8").write(html)
js = f"""
const {{ chromium }} = require('playwright');
(async () => {{
  const b = await chromium.launch();
  const p = await b.newPage();
  await p.goto('file://{os.path.abspath(tmp)}', {{waitUntil: 'load'}});
  await p.pdf({{path: '{os.path.abspath(out)}', format: 'A4', printBackground: true,
    displayHeaderFooter: true, headerTemplate: '<div></div>',
    footerTemplate: '<div style="font-size:7pt;color:#6e7781;width:100%;text-align:center">Zenith DC: evolutionary redesign · page <span class="pageNumber"></span> / <span class="totalPages"></span></div>',
    margin: {{top: '16mm', bottom: '18mm', left: '15mm', right: '15mm'}}}});
  await b.close();
}})();
"""
jsf = os.path.abspath(os.path.splitext(out)[0] + "_render.js")
open(jsf, "w").write(js)
subprocess.run(["node", jsf], check=True, cwd="/tmp/claude-0")
os.remove(jsf)
print("wrote", out)

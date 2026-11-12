#!/usr/bin/env python3
"""Xuất docs/thuyet-trinh.md ra PDF A4 để in. Chạy: .venv-report/bin/python docs/build_thuyet_trinh.py"""
from pathlib import Path

from markdown_it import MarkdownIt
from playwright.sync_api import sync_playwright

DOCS = Path(__file__).resolve().parent
CSS = """
body{font-family:'Times New Roman',serif;font-size:12.5pt;line-height:1.4;color:#000}
h1{font-size:19pt;text-align:center;margin:0 0 8pt}
h2{font-size:15pt;border-bottom:1.5pt solid #000;padding-bottom:2pt;margin-top:16pt;break-after:avoid}
h3{font-size:13pt;margin:12pt 0 4pt;break-after:avoid}
table{border-collapse:collapse;width:100%;margin:6pt 0;font-size:11pt}
th,td{border:.75pt solid #000;padding:3pt 5pt;vertical-align:top;text-align:left}
th{background:#e6e6e6}
tr,blockquote p,li{break-inside:avoid}
blockquote{margin:4pt 0;padding:2pt 10pt;border-left:3pt solid #000;font-size:13.5pt;line-height:1.5}
code{font-family:Menlo,monospace;font-size:10pt}
hr{display:none}
a{color:#000;text-decoration:none}
"""
body = MarkdownIt("commonmark").enable("table").render((DOCS / "thuyet-trinh.md").read_text())
with sync_playwright() as p:
    browser = p.chromium.launch()
    page = browser.new_page()
    page.set_content(f"<meta charset='utf-8'><style>{CSS}</style>{body}")
    page.pdf(path=str(DOCS / "ThuyetTrinh.pdf"), format="A4", display_header_footer=True,
             header_template="<span></span>",
             footer_template="<div style='font-size:9pt;width:100%;text-align:center'>Nhóm 11 — trang <span class='pageNumber'></span>/<span class='totalPages'></span></div>",
             margin={"top": "15mm", "bottom": "16mm", "left": "16mm", "right": "14mm"})
    browser.close()

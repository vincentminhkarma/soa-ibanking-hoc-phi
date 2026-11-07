#!/usr/bin/env python3
"""Xuất Word/PDF từ cùng nguồn Markdown, render Mermaid cục bộ."""
import base64
import hashlib
import html
from html.parser import HTMLParser
from pathlib import Path
import re
import tempfile

import pypandoc
from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Mm, Pt
from playwright.sync_api import sync_playwright

DOCS = Path(__file__).resolve().parent
ASSETS = DOCS / "report-assets"
MERMAID = DOCS.parent / ".report-tools/node_modules/mermaid/dist/mermaid.min.js"
OUTPUT = DOCS / "BaoCao"
BREAK = '<div class="page-break"></div>'


def assemble():
    source = (DOCS / "bao-cao.md").read_text()
    return re.sub(r"<!--\s*INCLUDE:\s*(\S+)\s*-->",
                  lambda m: (DOCS / m[1]).read_text(), source)


def render_diagrams(source, browser):
    if not MERMAID.is_file():
        raise SystemExit("Chạy: npm install --prefix .report-tools mermaid@12.0.0")
    ASSETS.mkdir(exist_ok=True)
    page = browser.new_page(viewport={"width": 1800, "height": 1200}, device_scale_factor=2)
    page.set_content('<html><body style="margin:0;background:white"><div id="diagram"></div></body></html>')
    page.add_script_tag(path=str(MERMAID))
    page.evaluate("mermaid.initialize({startOnLoad:false,theme:'neutral',flowchart:{useMaxWidth:false},sequence:{useMaxWidth:false},er:{useMaxWidth:false}})")
    index = 0

    def replace(match):
        nonlocal index
        index += 1
        code = match[1].strip()
        key = hashlib.sha256(code.encode()).hexdigest()[:12]
        stem = f"figure-{index:02}-{key}"
        svg = page.evaluate("""async ({code,id}) => {
            const {svg} = await mermaid.render(id, code);
            document.getElementById('diagram').innerHTML = svg;
            await document.fonts.ready;
            return svg;
        }""", {"code": code, "id": f"figure{index}"})
        if "Syntax error in text" in svg:
            raise ValueError(f"Mermaid không hợp lệ: hình {index}")
        (ASSETS / f"{stem}.svg").write_text(svg)
        page.locator("#diagram svg").screenshot(path=str(ASSETS / f"{stem}.png"))
        return f"\n\n![Hình {index}. Sơ đồ phân tích và thiết kế](report-assets/{stem}.png)\n\n"

    result = re.sub(r"```mermaid\s*\n(.*?)```", replace, source, flags=re.S)
    page.close()
    return result


class Headings(HTMLParser):
    def __init__(self):
        super().__init__()
        self.items = []
        self.active = None

    def handle_starttag(self, tag, attrs):
        if tag in ("h1", "h2"):
            self.active = [tag, dict(attrs).get("id", ""), ""]

    def handle_data(self, data):
        if self.active is not None:
            self.active[2] += data

    def handle_endtag(self, tag):
        if self.active is not None and tag == self.active[0]:
            self.items.append(self.active)
            self.active = None


def convert(source, target, **kwargs):
    return pypandoc.convert_text(source, to=target, format="markdown+raw_html", cworkdir=str(DOCS), **kwargs)


def build_docx(body, headings):
    with tempfile.TemporaryDirectory() as temporary:
        path = Path(temporary) / "body.docx"
        convert(body.replace(BREAK, ""), "docx", outputfile=str(path))
        doc = Document(path)
    for section in doc.sections:
        section.page_width, section.page_height = Mm(210), Mm(297)
        section.top_margin, section.bottom_margin = Mm(25), Mm(25)
        section.left_margin, section.right_margin = Mm(30), Mm(20)
        section.different_first_page_header_footer = True
        footer = section.footer.paragraphs[0]
        footer.alignment = WD_ALIGN_PARAGRAPH.RIGHT
        footer.add_run("Trang ")
        field = OxmlElement("w:fldSimple")
        field.set(qn("w:instr"), "PAGE")
        footer._p.append(field)
    for name in ("Normal", "Body Text", "First Paragraph", "Caption", "Table"):
        if name in doc.styles:
            style = doc.styles[name]
            style.font.name, style.font.size = "Times New Roman", Pt(12)
            if name != "Table":
                style.paragraph_format.line_spacing = 1.3
    for level in range(1, 4):
        style = doc.styles[f"Heading {level}"]
        style.font.name, style.font.size = "Times New Roman", Pt(18 - level * 2)
        style.paragraph_format.keep_with_next = True
        if level == 1:
            style.paragraph_format.page_break_before = True
    for table in doc.tables:
        header = OxmlElement("w:tblHeader")
        table.rows[0]._tr.get_or_add_trPr().append(header)
        for row in table.rows:
            for cell in row.cells:
                for paragraph in cell.paragraphs:
                    for run in paragraph.runs:
                        run.font.name, run.font.size = "Times New Roman", Pt(9)
    for image in doc.inline_shapes:
        ratio = min(Mm(160) / image.width, Mm(215) / image.height, 1)
        image.width, image.height = int(image.width * ratio), int(image.height * ratio)
    for index, (paragraph, _) in enumerate(zip(
        (p for p in doc.paragraphs if p.style.name in ("Heading 1", "Heading 2")),
        headings, strict=True,
    ), start=1000):
        bookmark = OxmlElement("w:bookmarkStart")
        bookmark.set(qn("w:id"), str(index))
        bookmark.set(qn("w:name"), f"report_{index}")
        end = OxmlElement("w:bookmarkEnd")
        end.set(qn("w:id"), str(index))
        paragraph._p.insert(1 if paragraph._p.pPr is not None else 0, bookmark)
        paragraph._p.append(end)
    front = []

    def paragraph(text, size=12, bold=False, space=6, centered=True):
        p = doc.add_paragraph()
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER if centered else WD_ALIGN_PARAGRAPH.LEFT
        p.paragraph_format.space_after = Pt(space)
        run = p.add_run(text)
        run.font.name, run.font.size, run.bold = "Times New Roman", Pt(size), bold
        front.append(p)

    paragraph("TRƯỜNG ĐẠI HỌC TÔN ĐỨC THẮNG", 15, True)
    paragraph("KHOA CÔNG NGHỆ THÔNG TIN", 13, True, 55)
    paragraph("BÁO CÁO ĐỒ ÁN GIỮA KỲ", 20, True, 20)
    paragraph("504070 — Service-Oriented Architecture\n(Kiến trúc hướng dịch vụ)", 14, True, 22)
    paragraph("PHÂN HỆ ĐÓNG HỌC PHÍ TRÊN ỨNG DỤNG IBANKING\nTHEO KIẾN TRÚC MICROSERVICES", 14, True, 55)
    for text in ("Giảng viên hướng dẫn: Dương Hữu Phúc", "Thành viên nhóm:",
                 "523H0020 — Lê Nam Giang", "523H0149 — Nguyễn Gia Nhật Khánh",
                 "519H0194 — Nguyễn Hoàng Thanh Minh",
                 "Mã nhóm: 11", "Học kỳ: HK1 / 2026–2027"):
        paragraph(text, centered=False)
    paragraph("TP. HỒ CHÍ MINH, 2026", 12, True, 0)
    paragraph("MỤC LỤC", 16, True)
    front[-1].paragraph_format.page_break_before = True
    for index, (level, anchor, text) in enumerate(headings, start=1000):
        p = doc.add_paragraph()
        p.paragraph_format.space_after = Pt(2)
        p.paragraph_format.left_indent = Mm(5 if level == "h2" else 0)
        link = OxmlElement("w:hyperlink")
        link.set(qn("w:anchor"), f"report_{index}")
        run = OxmlElement("w:r")
        node = OxmlElement("w:t")
        node.text = text
        run.append(node)
        link.append(run)
        p._p.append(link)
        front.append(p)
    for index, p in enumerate(front):
        doc._body._body.insert(index, p._p)
    doc.save(OUTPUT.with_suffix(".docx"))


def build_pdf(cover, body_html, headings, browser):
    toc = '<section class="toc"><h1>MỤC LỤC</h1><ul>' + "".join(
        f'<li class="{level}"><a href="#{html.escape(anchor)}">{html.escape(text)}</a></li>'
        for level, anchor, text in headings
    ) + "</ul></section>"
    body_html = re.sub(r'src="(report-assets/[^"<>]+\.png)"',
                       lambda m: 'src="data:image/png;base64,' + base64.b64encode((DOCS / m[1]).read_bytes()).decode() + '"',
                       body_html)
    page = browser.new_page()
    page.set_content(f'<!doctype html><html lang="vi"><head><meta charset="utf-8">'
                     f'<style>{(DOCS / "report.css").read_text()}</style>'
                     f'</head><body>{cover}{toc}<main>{body_html}</main></body></html>')
    page.evaluate("""async () => {
        await document.fonts.ready;
        for (const image of document.images) {
            try { await image.decode(); }
            catch { throw new Error('Ảnh lỗi: ' + image.getAttribute('src').slice(0, 120)); }
        }
    }""")
    assert page.locator(".toc a").count() == len(headings)
    page.pdf(path=str(OUTPUT.with_suffix(".pdf")), prefer_css_page_size=True, print_background=True)
    page.close()


def main():
    source = assemble()
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        try:
            rendered = render_diagrams(source, browser)
            cover, body = rendered.split(BREAK, 1)
            body_html = convert(body.replace(BREAK, ""), "html5")
            headings = Headings()
            headings.feed(body_html)
            build_docx(body, headings.items)
            build_pdf(cover, body_html, headings.items, browser)
        finally:
            browser.close()
    print(f"Đã xuất: {OUTPUT.with_suffix('.docx')}\nĐã xuất: {OUTPUT.with_suffix('.pdf')}")


if __name__ == "__main__":
    main()

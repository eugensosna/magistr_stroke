#!/usr/bin/env python3
"""Генерує тези у форматі шаблону конференції ДУІКТ з tezy.md.

    uv run --with python-docx python3 conference/duikt-2026/make_docx.py

Результат: build/Сосна_Секція_3.docx і build/Сосна_Секція_3.pdf (PDF — через LibreOffice, якщо він є).

Оформлення береться з абзаців-зразків самого шаблону (template.docx): відомості про авторів,
назва (стиль Heading2), основний текст з відступом 1 см, «Табл. N», таблиця, список джерел.
"""
import copy
import re
import shutil
import subprocess
import sys
from pathlib import Path

from docx import Document
from docx.oxml.ns import qn
from docx.shared import Emu
from docx.text.paragraph import Paragraph
from lxml import etree

HERE = Path(__file__).resolve().parent
SRC = HERE / "tezy.md"
EQ = HERE / "eq"                     # формули (OMML-абзаци з редакції керівника)
ROOT = HERE.parents[1]
TEMPLATE = HERE / "template.docx"
BUILD = HERE.parents[1] / "build"   # каталог build/ у корені репозиторію (ігнорується git)
OUT = BUILD / "Сосна_Секція_3.docx"


def parse(text):
    text = re.sub(r"<!--.*?-->", "", text, flags=re.S)
    blocks, cur = [], None
    for line in text.splitlines():
        if line.startswith("@"):
            cur = [line[1:].strip(), []]
            blocks.append(cur)
        elif cur is not None:
            cur[1].append(line)
    return blocks


def find(doc, start):
    for p in doc.paragraphs:
        if p.text.startswith(start):
            return p
    sys.exit(f"у шаблоні не знайдено абзац «{start}»")


def fill(p_el, text):
    """Замінює вміст абзацу текстом з розміткою *курсив*, _{нижній} і ^{верхній} індекс, зберігаючи формат першого run."""
    runs = p_el.findall(qn("w:r"))
    rpr = runs[0].find(qn("w:rPr")) if runs else None
    for r in p_el.findall(qn("w:r")) + p_el.findall(qn("w:hyperlink")):
        p_el.remove(r)
    for tok in re.split(r"(\*[^*]+\*|_\{[^}]+\}|\^\{[^}]+\})", text):
        if not tok:
            continue
        italic = tok.startswith("*")
        sub = tok.startswith("_{")
        sup = tok.startswith("^{")
        body = tok[1:-1] if italic else tok[2:-1] if sub or sup else tok
        r = p_el.makeelement(qn("w:r"), {})
        rp = copy.deepcopy(rpr) if rpr is not None else r.makeelement(qn("w:rPr"), {})
        if italic and rp.find(qn("w:i")) is None:
            rp.append(rp.makeelement(qn("w:i"), {}))
        if sub or sup:
            va = rp.makeelement(qn("w:vertAlign"), {qn("w:val"): "subscript" if sub else "superscript"})
            rp.append(va)
        r.append(rp)
        t = r.makeelement(qn("w:t"), {})
        t.text = body
        t.set("{http://www.w3.org/XML/1998/namespace}space", "preserve")
        r.append(t)
        p_el.append(r)
    return p_el


def main():
    doc = Document(TEMPLATE)
    proto = {
        "author": find(doc, "Іваненко Іван")._p,
        "supervisor": find(doc, "Петренко Петро")._p,
        "title": find(doc, "ОСОБЛИВОСТІ ОПТИМІЗАЦІЇ")._p,
        "text": find(doc, "Текст текст")._p,
        "tblnum": find(doc, "Табл. 1")._p,
        "tbltitle": find(doc, "Назва таблиці")._p,
        "refhead": find(doc, "Список використаних джерел")._p,
        "heading": find(doc, "Список використаних джерел")._p,   # заголовки частин тез — тим самим стилем
        "ref": find(doc, "Будіщев")._p,
        "figure": find(doc, "Текст текст")._p,
        "caption": find(doc, "Текст текст")._p,
        "blank": next(p for p in doc.paragraphs if not p.text.strip())._p,
    }
    proto = {k: copy.deepcopy(v) for k, v in proto.items()}
    tbl_proto = copy.deepcopy(doc.tables[0]._tbl)

    body = doc.element.body
    sect = body.find(qn("w:sectPr"))
    for el in list(body):
        if el is not sect:
            body.remove(el)

    def add(kind, text=""):
        el = copy.deepcopy(proto[kind])
        if text or kind != "blank":
            fill(el, text.replace("'", "’"))   # типографський апостроф
        if kind in ("tblnum", "tbltitle", "title", "heading", "figure"):  # не відривати від наступного абзацу/таблиці
            ppr = el.find(qn("w:pPr"))
            if ppr is not None and ppr.find(qn("w:keepNext")) is None:
                ppr.insert(0, ppr.makeelement(qn("w:keepNext"), {}))
        if kind in ("figure", "caption"):  # по центру, без абзацного відступу
            ppr = el.find(qn("w:pPr"))
            for tag in ("w:ind", "w:jc"):
                old = ppr.find(qn(tag))
                if old is not None:
                    ppr.remove(old)
            ppr.append(ppr.makeelement(qn("w:ind"), {qn("w:left"): "0", qn("w:firstLine"): "0"}))
            ppr.append(ppr.makeelement(qn("w:jc"), {qn("w:val"): "center"}))
        sect.addprevious(el)
        return el

    tables = 0
    for kind, lines in parse(SRC.read_text(encoding="utf-8")):
        lines = [l for l in lines]
        if kind in ("author", "supervisor"):
            for l in (l for l in lines if l.strip()):
                add(kind, l.strip())
            if kind == "supervisor":
                add("blank")
        elif kind == "title":
            add("title", " ".join(l.strip() for l in lines if l.strip()))
            add("blank")
        elif kind.startswith("equation"):
            name = kind.split()[1]
            sect.addprevious(etree.fromstring((EQ / f"{name}.xml").read_bytes()))
        elif kind == "figure":
            path, caption = [l.strip() for l in lines if l.strip()]
            el = add("figure", "")
            for r in el.findall(qn("w:r")):
                el.remove(r)
            Paragraph(el, doc._body).add_run().add_picture(str(ROOT / path), width=Emu(5348614))
            add("caption", caption)
        elif kind == "heading":
            add("heading", " ".join(l.strip() for l in lines if l.strip()))
        elif kind == "text":
            for para in "\n".join(lines).split("\n\n"):
                if para.strip():
                    add("text", " ".join(para.split()))
        elif kind == "table":
            rows = [l for l in lines if l.strip()]
            tables += 1
            add("tblnum", f"Табл. {tables}")
            add("tbltitle", rows[0].strip())
            cells = [[c.strip() for c in r.split("|")] for r in rows[1:]]
            tbl = copy.deepcopy(tbl_proto)
            trs = tbl.findall(qn("w:tr"))
            head_tr, body_tr = trs[0], trs[1]
            for tr in trs:
                tbl.remove(tr)
            ncol = len(cells[0])
            widths = [2300, 3500, 3828][:ncol]
            grid = tbl.find(qn("w:tblGrid"))
            for gc in grid.findall(qn("w:gridCol")):
                grid.remove(gc)
            for w in widths:
                grid.append(grid.makeelement(qn("w:gridCol"), {qn("w:w"): str(w)}))
            for i, row in enumerate(cells):
                tr = copy.deepcopy(head_tr if i == 0 else body_tr)
                tcs = tr.findall(qn("w:tc"))
                for extra in tcs[ncol:]:
                    tr.remove(extra)
                for tc, w, text in zip(tr.findall(qn("w:tc")), widths, row):
                    tcw = tc.find(qn("w:tcPr")).find(qn("w:tcW"))
                    if tcw is not None:
                        tcw.set(qn("w:w"), str(w))
                    ps = tc.findall(qn("w:p"))
                    for extra in ps[1:]:
                        tc.remove(extra)
                    fill(ps[0], text)
                    ppr = ps[0].find(qn("w:pPr"))
                    if ppr is None:
                        ppr = ps[0].makeelement(qn("w:pPr"), {})
                        ps[0].insert(0, ppr)
                    if i > 0:  # тіло таблиці — ліворуч, без розтягування пробілів
                        jc = ppr.find(qn("w:jc"))
                        if jc is None:
                            jc = ppr.makeelement(qn("w:jc"), {})
                            ppr.append(jc)
                        jc.set(qn("w:val"), "left")
                tbl.append(tr)
            sect.addprevious(tbl)
            add("blank")
        elif kind == "references":
            add("refhead", "Список використаних джерел")
            for l in (l for l in lines if l.strip()):
                add("ref", l.strip())

    BUILD.mkdir(parents=True, exist_ok=True)
    doc.save(OUT)
    print(f"готово: {OUT}")

    soffice = shutil.which("soffice") or shutil.which("libreoffice")
    if soffice is None:
        print("LibreOffice не знайдено, PDF не створено")
        return
    subprocess.run([soffice, "--headless", "--convert-to", "pdf", "--outdir", str(BUILD), str(OUT)],
                   check=True, capture_output=True)
    print(f"готово: {OUT.with_suffix('.pdf')}")


if __name__ == "__main__":
    main()

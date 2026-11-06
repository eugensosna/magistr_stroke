#!/usr/bin/env python3
"""Доводить DOCX після pandoc до вимог ДСТУ 3008:2015.

  * розмір сторінки і поля, номер сторінки у верхньому правому куті
    (на титульному аркуші номер не друкується, але враховується);
  * переліки: маркер «–», нумерація «1)», «а)», відступи як в абзаців;
  * Word пропонує оновити поля (зміст) під час відкриття документа;
  * автоматичне перенесення слів (якщо ввімкнено у format.toml);
  * dev-збірка: примітки до виправлених зауважень позначаються як закриті (resolved);
  * версія документа ($DOC_VERSION) - у властивостях DOCX (cp:version), а в dev-збірці
    ($MODE=dev) ще й у колонтитулі титульного аркуша.

Використання: postprocess.py format.toml in.docx out.docx [review.json]
"""
import json
import os
import re
from xml.sax.saxutils import escape
import sys
import tomllib
import zipfile

MM = 56.6929
CM = 567.0
W_NS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
R_NS = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
HEADER_CT = "application/vnd.openxmlformats-officedocument.wordprocessingml.header+xml"
FOOTER_CT = "application/vnd.openxmlformats-officedocument.wordprocessingml.footer+xml"
HEADER_REL = "http://schemas.openxmlformats.org/officeDocument/2006/relationships/header"
FOOTER_REL = "http://schemas.openxmlformats.org/officeDocument/2006/relationships/footer"
W14_NS = "http://schemas.microsoft.com/office/word/2010/wordml"
W15_NS = "http://schemas.microsoft.com/office/word/2012/wordml"
MC_NS = "http://schemas.openxmlformats.org/markup-compatibility/2006"
COMMENTS_EX_CT = "application/vnd.openxmlformats-officedocument.wordprocessingml.commentsExtended+xml"
COMMENTS_EX_REL = "http://schemas.microsoft.com/office/2011/relationships/commentsExtended"


def tw(v):
    return str(int(round(v)))


def page_number_part(kind, align, with_number, note=""):
    tag = "hdr" if kind == "header" else "ftr"
    style = "Header" if kind == "header" else "Footer"
    runs = ""
    if note:   # дрібний сірий напис (версія документа на титульному аркуші dev-збірки)
        runs += ('<w:r><w:rPr><w:color w:val="808080"/><w:sz w:val="18"/></w:rPr>'
                 f'<w:t xml:space="preserve">{escape(note)}</w:t></w:r>')
    if with_number:
        runs = ('<w:r><w:fldChar w:fldCharType="begin"/></w:r>'
                '<w:r><w:instrText xml:space="preserve"> PAGE </w:instrText></w:r>'
                '<w:r><w:fldChar w:fldCharType="separate"/></w:r>'
                '<w:r><w:t>1</w:t></w:r>'
                '<w:r><w:fldChar w:fldCharType="end"/></w:r>')
    return ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
            f'<w:{tag} xmlns:w="{W_NS}" xmlns:r="{R_NS}">'
            f'<w:p><w:pPr><w:pStyle w:val="{style}"/><w:jc w:val="{align}"/></w:pPr>'
            f'{runs}</w:p></w:{tag}>')


def section_properties(fmt):
    p = fmt["page"]
    kind = p.get("page_number_position", "header")
    ref = "headerReference" if kind == "header" else "footerReference"
    return (
        '<w:sectPr>'
        f'<w:{ref} w:type="default" r:id="rIdDstuPageNum"/>'
        f'<w:{ref} w:type="first" r:id="rIdDstuPageNumFirst"/>'
        '<w:footnotePr><w:numRestart w:val="eachPage"/></w:footnotePr>'
        f'<w:pgSz w:w="{tw(p["width_mm"] * MM)}" w:h="{tw(p["height_mm"] * MM)}"/>'
        f'<w:pgMar w:top="{tw(p["margin_top_mm"] * MM)}" w:right="{tw(p["margin_right_mm"] * MM)}" '
        f'w:bottom="{tw(p["margin_bottom_mm"] * MM)}" w:left="{tw(p["margin_left_mm"] * MM)}" '
        f'w:header="{tw(p["header_mm"] * MM)}" w:footer="{tw(p["header_mm"] * MM)}" w:gutter="0"/>'
        '<w:pgNumType w:start="1"/>'
        '<w:titlePg/>'
        '</w:sectPr>')


def fix_document(xml, fmt):
    # Залишаємо тільки один (останній) розділ документа з нашими параметрами
    body_end = xml.rfind("</w:body>")
    last = xml.rfind("<w:sectPr", 0, body_end)
    if last != -1:
        xml = xml[:last] + section_properties(fmt) + xml[body_end:]
    else:
        xml = xml[:body_end] + section_properties(fmt) + xml[body_end:]
    if 'xmlns:r=' not in xml[:2000]:
        xml = xml.replace("<w:document ", f'<w:document xmlns:r="{R_NS}" ', 1)
    return xml


def fix_numbering(xml, fmt):
    indent = fmt["text"]["first_line_indent_cm"] * CM

    def fix_lvl(m):
        lvl = m.group(0)
        ilvl = int(re.search(r'w:ilvl="(\d+)"', lvl).group(1))
        fmt_m = re.search(r'<w:numFmt w:val="([^"]+)"', lvl)
        num_fmt = fmt_m.group(1) if fmt_m else "bullet"
        if num_fmt == "bullet":
            lvl = re.sub(r'<w:lvlText w:val="[^"]*"\s*/>', '<w:lvlText w:val="–"/>', lvl)
            # маркер тим самим шрифтом, що й текст
            lvl = re.sub(r'<w:rPr>.*?</w:rPr>', '', lvl, flags=re.S)
        elif num_fmt == "lowerLetter":
            # а), б), в) ... (перші літери збігаються з українським алфавітом)
            lvl = lvl.replace('<w:numFmt w:val="lowerLetter"', '<w:numFmt w:val="russianLower"')
        elif num_fmt == "upperLetter":
            lvl = lvl.replace('<w:numFmt w:val="upperLetter"', '<w:numFmt w:val="russianUpper"')
        # Номер/маркер з абзацного відступу, далі текст через пробіл,
        # наступні рядки від лівого поля.
        lvl = re.sub(r'<w:suff [^>]*/>', '', lvl)
        lvl = re.sub(r'(<w:lvlText )', r'<w:suff w:val="space"/>\1', lvl, count=1)
        ind = f'<w:ind w:left="0" w:firstLine="{tw(indent * (ilvl + 1))}"/>'
        if re.search(r'<w:ind [^>]*/>', lvl):
            lvl = re.sub(r'<w:ind [^>]*/>', ind, lvl)
        elif "<w:pPr>" in lvl:
            lvl = lvl.replace("<w:pPr>", "<w:pPr>" + ind, 1)
        else:
            lvl = lvl.replace("</w:lvl>", f"<w:pPr>{ind}</w:pPr></w:lvl>")
        lvl = re.sub(r'<w:tabs>.*?</w:tabs>', '', lvl, flags=re.S)
        return lvl

    return re.sub(r'<w:lvl [^>]*>.*?</w:lvl>', fix_lvl, xml, flags=re.S)


def fix_settings(xml, fmt):
    xml = re.sub(r'<w:updateFields[^>]*/>', '', xml)
    xml = re.sub(r'<w:autoHyphenation[^>]*/>', '', xml)
    # updateFields має стояти перед footnotePr / compat / rsids (порядок схеми)
    for anchor in ("<w:hdrShapeDefaults", "<w:footnotePr", "<w:endnotePr", "<w:compat",
                   "<w:docVars", "<w:rsids", "<m:mathPr", "<w:themeFontLang",
                   "<w:clrSchemeMapping", "<w:decimalSymbol", "</w:settings>"):
        if anchor in xml:
            xml = xml.replace(anchor, '<w:updateFields w:val="true"/>' + anchor, 1)
            break
    if fmt["text"].get("hyphenation"):
        xml = re.sub(r'(<w:defaultTabStop [^>]*/>)', r'\1<w:autoHyphenation/>', xml, count=1)
    lang = fmt["text"]["language"]
    xml = re.sub(r'<w:themeFontLang w:val="[^"]*"', f'<w:themeFontLang w:val="{lang}"', xml)
    return xml


def fix_rels(xml, kind):
    rel = HEADER_REL if kind == "header" else FOOTER_REL
    name = "header" if kind == "header" else "footer"
    xml = re.sub(r'<Relationship [^>]*Id="rIdDstuPageNum(First)?"[^>]*/>', '', xml)
    add = (f'<Relationship Type="{rel}" Id="rIdDstuPageNum" Target="dstu-{name}1.xml"/>'
           f'<Relationship Type="{rel}" Id="rIdDstuPageNumFirst" Target="dstu-{name}2.xml"/>')
    return xml.replace("</Relationships>", add + "</Relationships>")


def para_id(comment_id):
    return f"{0x10000000 + int(comment_id):08X}"


def fix_comments(xml):
    """Додає w14:paraId останньому абзацу кожної примітки (потрібно для commentsExtended)."""
    if "xmlns:w14=" not in xml:
        xml = xml.replace("<w:comments ", f'<w:comments xmlns:w14="{W14_NS}" ', 1)

    def one(m):
        body = m.group(2)
        last = body.rfind("<w:p>")
        if last >= 0:
            body = body[:last] + f'<w:p w14:paraId="{para_id(m.group(1))}">' + body[last + 5:]
        return m.group(0)[:m.start(2) - m.start(0)] + body + "</w:comment>"
    return re.sub(r'<w:comment w:id="(\d+)"[^>]*>(.*?)</w:comment>', one, xml, flags=re.S)


def comments_extended(comment_ids, fixed):
    items = "".join(f'<w15:commentEx w15:paraId="{para_id(i)}" w15:done="{1 if i in fixed else 0}"/>'
                    for i in comment_ids)
    return (f'<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            f'<w15:commentsEx xmlns:mc="{MC_NS}" xmlns:w15="{W15_NS}" mc:Ignorable="w15">'
            f'{items}</w15:commentsEx>')


def fix_core(xml, version):
    """Записує версію документа у властивість cp:version."""
    xml = re.sub(r"<cp:version>.*?</cp:version>", "", xml, flags=re.S)
    return xml.replace("</cp:coreProperties>",
                       f"<cp:version>{escape(version)}</cp:version></cp:coreProperties>")


def fix_content_types(xml, kind):
    ct = HEADER_CT if kind == "header" else FOOTER_CT
    name = "header" if kind == "header" else "footer"
    add = "".join(f'<Override PartName="/word/dstu-{name}{i}.xml" ContentType="{ct}"/>'
                  for i in (1, 2) if f"/word/dstu-{name}{i}.xml" not in xml)
    return xml.replace("</Types>", add + "</Types>")


def main():
    fmt_path, src_path, out_path = sys.argv[1:4]
    version = os.environ.get("DOC_VERSION", "")
    note = f"Версія документа: {version} (dev)" if version and os.environ.get("MODE") == "dev" else ""
    fixed = set()
    if len(sys.argv) > 4 and sys.argv[4]:
        with open(sys.argv[4], encoding="utf-8") as fh:
            fixed = {str(c["id"]) for c in json.load(fh) if c["fixed"]}
    with open(fmt_path, "rb") as fh:
        fmt = tomllib.load(fh)
    kind = fmt["page"].get("page_number_position", "header")
    align = fmt["page"].get("page_number_align", "right")
    name = "header" if kind == "header" else "footer"

    with zipfile.ZipFile(src_path) as src, \
            zipfile.ZipFile(out_path, "w", zipfile.ZIP_DEFLATED) as dst:
        names = src.namelist()
        has_comments = ("word/comments.xml" in names
                        and b"<w:comment " in src.read("word/comments.xml"))
        comment_ids = []
        for item in src.infolist():
            data = src.read(item.filename)
            fn = item.filename
            if fn.startswith(f"word/dstu-{name}"):
                continue
            if fn in ("word/document.xml", "word/numbering.xml", "word/settings.xml",
                      "word/_rels/document.xml.rels", "[Content_Types].xml", "word/comments.xml",
                      "docProps/core.xml"):
                text = data.decode("utf-8")
                if fn == "word/document.xml":
                    text = fix_document(text, fmt)
                elif fn == "word/numbering.xml":
                    text = fix_numbering(text, fmt)
                elif fn == "word/settings.xml":
                    text = fix_settings(text, fmt)
                elif fn == "docProps/core.xml":
                    if version:
                        text = fix_core(text, version)
                elif fn == "word/comments.xml":
                    if has_comments:
                        text = fix_comments(text)
                    comment_ids = re.findall(r'<w:comment w:id="(\d+)"', text)
                elif fn == "word/_rels/document.xml.rels":
                    text = fix_rels(text, kind)
                    if has_comments:
                        text = text.replace("</Relationships>", f'<Relationship Type="{COMMENTS_EX_REL}" '
                                            'Id="rIdDstuCommentsEx" Target="commentsExtended.xml"/></Relationships>')
                else:
                    text = fix_content_types(text, kind)
                    if has_comments:
                        text = text.replace("</Types>", '<Override PartName="/word/commentsExtended.xml" '
                                            f'ContentType="{COMMENTS_EX_CT}"/></Types>')
                data = text.encode("utf-8")
            dst.writestr(item, data)
        dst.writestr(f"word/dstu-{name}1.xml", page_number_part(kind, align, True))
        dst.writestr(f"word/dstu-{name}2.xml", page_number_part(kind, align, False, note))
        if has_comments:
            dst.writestr("word/commentsExtended.xml", comments_extended(comment_ids, fixed))
        assert "word/document.xml" in names


if __name__ == "__main__":
    main()

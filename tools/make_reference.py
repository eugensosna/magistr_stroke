#!/usr/bin/env python3
"""Генерує reference.docx (набір стилів Word) за параметрами config/format.toml.

pandoc бере з reference.docx лише стилі, тому тут ми беремо стандартний
reference.docx pandoc і повністю замінюємо в ньому word/styles.xml.

Використання: make_reference.py format.toml pandoc-default.docx out.docx
"""
import sys
import tomllib
import zipfile
from xml.sax.saxutils import escape

MM = 56.6929  # twips в 1 мм
CM = 567.0    # twips в 1 см


def tw(v):
    return str(int(round(v)))


def half_points(pt):
    return str(int(round(pt * 2)))


def line(spacing):
    return tw(240 * spacing)


def build_styles(f):
    page, text, hd, tbl, code, fn = (f["page"], f["text"], f["headings"],
                                     f["tables"], f["code"], f["footnotes"])
    font = escape(text["font"])
    lang = escape(text["language"])
    size = half_points(text["size_pt"])
    body_line = line(text["line_spacing"])
    indent = tw(text["first_line_indent_cm"] * CM)
    text_width = (page["width_mm"] - page["margin_left_mm"] - page["margin_right_mm"]) * MM

    def rfonts(name=font):
        return (f'<w:rFonts w:ascii="{name}" w:hAnsi="{name}" w:eastAsia="{name}" '
                f'w:cs="{name}"/>')

    def para(style_id, name, ppr="", rpr="", based="Normal", nxt=None,
             custom=True, extra=""):
        nxt_xml = f'<w:next w:val="{nxt}"/>' if nxt else ""
        based_xml = f'<w:basedOn w:val="{based}"/>' if based else ""
        cust = ' w:customStyle="1"' if custom else ""
        return (f'<w:style w:type="paragraph"{cust} w:styleId="{style_id}">'
                f'<w:name w:val="{name}"/>{based_xml}{nxt_xml}{extra}<w:qFormat/>'
                f'<w:pPr>{ppr}</w:pPr><w:rPr>{rpr}</w:rPr></w:style>')

    def char(style_id, name, rpr, custom=True):
        cust = ' w:customStyle="1"' if custom else ""
        return (f'<w:style w:type="character"{cust} w:styleId="{style_id}">'
                f'<w:name w:val="{name}"/><w:basedOn w:val="DefaultParagraphFont"/>'
                f'<w:rPr>{rpr}</w:rPr></w:style>')

    single = '<w:spacing w:before="0" w:after="0" w:line="240" w:lineRule="auto"/>'
    body = f'<w:spacing w:before="0" w:after="0" w:line="{body_line}" w:lineRule="auto"/>'
    no_ind = '<w:ind w:left="0" w:right="0" w:firstLine="0"/>'
    keep = '<w:keepNext/><w:keepLines/>'

    def heading_ppr(level):
        if level == 1:
            return (f'{keep}<w:pageBreakBefore/>'
                    f'<w:spacing w:before="0" w:after="{tw(hd["chapter_space_after_pt"] * 20)}" '
                    f'w:line="{body_line}" w:lineRule="auto"/>{no_ind}<w:jc w:val="center"/>'
                    f'<w:outlineLvl w:val="0"/>')
        return (f'{keep}<w:spacing w:before="{tw(hd["section_space_before_pt"] * 20)}" '
                f'w:after="{tw(hd["section_space_after_pt"] * 20)}" w:line="{body_line}" '
                f'w:lineRule="auto"/><w:ind w:left="0" w:firstLine="{indent}"/>'
                f'<w:jc w:val="left"/><w:outlineLvl w:val="{level - 1}"/>')

    chapter_rpr = f'<w:b/><w:bCs/><w:caps/><w:sz w:val="{half_points(hd["chapter_size_pt"])}"/>'
    section_rpr = f'<w:b/><w:bCs/><w:sz w:val="{half_points(hd["section_size_pt"])}"/>'

    styles = []
    # --- базові ---------------------------------------------------------
    styles.append(para(
        "Normal", "Normal", custom=False, based=None,
        ppr=(f'<w:widowControl/><w:spacing w:before="0" w:after="0" w:line="{body_line}" '
             f'w:lineRule="auto"/><w:ind w:firstLine="{indent}"/><w:jc w:val="both"/>'),
        extra="") .replace('<w:style w:type="paragraph" w:styleId="Normal">',
                           '<w:style w:type="paragraph" w:default="1" w:styleId="Normal">'))
    styles.append(para("BodyText", "Body Text", custom=False))
    styles.append(para("FirstParagraph", "First Paragraph", based="BodyText", nxt="BodyText"))
    # Compact pandoc застосовує до пунктів переліків
    styles.append(para("Compact", "Compact", based="BodyText"))
    styles.append(para("BlockText", "Block Text", based="BodyText", custom=False))
    # --- заголовки ------------------------------------------------------
    for lvl in range(1, 7):
        rpr = chapter_rpr if lvl == 1 else section_rpr
        styles.append(para(f"Heading{lvl}", f"heading {lvl}", heading_ppr(lvl), rpr,
                           nxt="BodyText", custom=False))
    # Заголовок структурного елемента, який не потрапляє до змісту
    # (АНОТАЦІЯ, ABSTRACT, ЗМІСТ): той самий вигляд, але без рівня структури.
    styles.append(para("HeadingUnlisted", "Heading Unlisted",
                       heading_ppr(1).replace('<w:outlineLvl w:val="0"/>', ''),
                       chapter_rpr, nxt="BodyText"))
    styles.append(para("TOCHeading", "TOC Heading",
                       heading_ppr(1).replace('<w:outlineLvl w:val="0"/>', ''),
                       chapter_rpr, custom=False, nxt="BodyText"))
    # --- зміст ----------------------------------------------------------
    for lvl in range(1, 4):
        styles.append(para(
            f"TOC{lvl}", f"toc {lvl}", custom=False, nxt="BodyText",
            ppr=(f'<w:tabs><w:tab w:val="right" w:leader="dot" w:pos="{tw(text_width)}"/></w:tabs>'
                 f'<w:spacing w:before="0" w:after="0" w:line="{body_line}" w:lineRule="auto"/>'
                 f'<w:ind w:left="{tw((lvl - 1) * 0.5 * CM)}" w:right="567" w:firstLine="0"/>'
                 f'<w:jc w:val="left"/>')))
    # --- титульний аркуш і довільне вирівнювання ------------------------
    styles.append(para("TitlePageCenter", "Title Page Center",
                       f'{body}{no_ind}<w:jc w:val="center"/>'))
    styles.append(para("TitlePageTitle", "Title Page Title",
                       f'{body}{no_ind}<w:jc w:val="center"/>',
                       f'<w:b/><w:bCs/><w:sz w:val="{half_points(text["size_pt"] + 2)}"/>'))
    styles.append(para("TitlePageRight", "Title Page Right",
                       f'{body}<w:ind w:left="{tw(text_width * 0.45)}" w:firstLine="0"/>'
                       f'<w:jc w:val="left"/>'))
    styles.append(para("TitlePageLeft", "Title Page Left", f'{body}{no_ind}<w:jc w:val="left"/>'))
    styles.append(para("Centered", "Centered", f'{no_ind}<w:jc w:val="center"/>', based="BodyText"))
    styles.append(para("NoIndent", "No Indent", f'{no_ind}', based="BodyText"))
    styles.append(para("RightAligned", "Right Aligned", f'{no_ind}<w:jc w:val="right"/>',
                       based="BodyText"))
    # --- рисунки, таблиці, формули, лістинги ----------------------------
    styles.append(para("Figure", "Figure",
                       f'{keep}<w:spacing w:before="120" w:after="0" w:line="240" '
                       f'w:lineRule="auto"/>{no_ind}<w:jc w:val="center"/>', based="BodyText"))
    styles.append(para("CaptionedFigure", "Captioned Figure", based="Figure"))
    styles.append(para("ImageCaption", "Image Caption",
                       f'<w:spacing w:before="120" w:after="240"/>{no_ind}<w:jc w:val="center"/>',
                       based="BodyText"))
    styles.append(para("TableCaption", "Table Caption",
                       f'{keep}<w:spacing w:before="240" w:after="0"/>{no_ind}<w:jc w:val="left"/>',
                       based="BodyText"))
    styles.append(para("ListingCaption", "Listing Caption",
                       f'{keep}<w:spacing w:before="240" w:after="0"/>{no_ind}<w:jc w:val="left"/>',
                       based="BodyText"))
    styles.append(para("Caption", "caption", based="BodyText", custom=False))
    styles.append(para(
        "TableText", "Table Text",
        f'<w:spacing w:before="0" w:after="0" w:line="{line(tbl["line_spacing"])}" '
        f'w:lineRule="auto"/>{no_ind}<w:jc w:val="left"/>',
        f'<w:sz w:val="{half_points(tbl["size_pt"])}"/><w:szCs w:val="{half_points(tbl["size_pt"])}"/>'))
    # Формула по центру, номер (1.1) притиснутий до правого поля
    styles.append(para(
        "Equation", "Equation",
        f'<w:tabs><w:tab w:val="center" w:pos="{tw(text_width / 2)}"/>'
        f'<w:tab w:val="right" w:pos="{tw(text_width)}"/></w:tabs>'
        f'<w:spacing w:before="120" w:after="120"/>{no_ind}<w:jc w:val="left"/>',
        based="BodyText"))
    styles.append(para(
        "SourceCode", "Source Code",
        f'<w:wordWrap w:val="off"/><w:spacing w:before="0" w:after="120" w:line="240" w:lineRule="auto"/>'
        f'{no_ind}<w:jc w:val="left"/>',
        f'{rfonts(escape(code["font"]))}<w:sz w:val="{half_points(code["size_pt"])}"/>'
        f'<w:szCs w:val="{half_points(code["size_pt"])}"/>', based="Normal"))
    styles.append(char("VerbatimChar", "Verbatim Char",
                       f'{rfonts(escape(code["font"]))}'))
    # --- бібліографія, примітки, означення ------------------------------
    styles.append(para("Bibliography", "Bibliography", based="BodyText", custom=False))
    styles.append(para("Note", "Note", based="BodyText"))
    styles.append(para("DefinitionTerm", "Definition Term", keep, based="BodyText"))
    styles.append(para("Definition", "Definition", based="BodyText"))
    # --- виноски, колонтитули, посилання --------------------------------
    styles.append(para("FootnoteText", "footnote text",
                       f'{single}<w:ind w:firstLine="{indent}"/>',
                       f'<w:sz w:val="{half_points(fn["size_pt"])}"/>'
                       f'<w:szCs w:val="{half_points(fn["size_pt"])}"/>', custom=False))
    styles.append(para("FootnoteBlockText", "Footnote Block Text", based="FootnoteText"))
    styles.append(char("FootnoteReference", "footnote reference",
                       '<w:vertAlign w:val="superscript"/>', custom=False))
    styles.append(para("Header", "header", f'{single}{no_ind}', custom=False))
    styles.append(para("Footer", "footer", f'{single}{no_ind}', custom=False))
    # Перехресні посилання в тексті роботи не виділяються кольором
    styles.append(char("Hyperlink", "Hyperlink", '', custom=False))
    styles.append(char("BodyTextChar", "Body Text Char", ''))
    styles.append(char("SectionNumber", "Section Number", ''))
    # Службові стилі pandoc для титульного блоку (не використовуються)
    for sid, name in [("Title", "Title"), ("Subtitle", "Subtitle"), ("Author", "Author"),
                      ("Date", "Date"), ("AbstractTitle", "Abstract Title"),
                      ("Abstract", "Abstract")]:
        styles.append(para(sid, name, f'{no_ind}<w:jc w:val="center"/>', based="BodyText"))

    hyph = '' if text.get("hyphenation") else '<w:suppressAutoHyphens/>'
    table_style = (
        '<w:style w:type="table" w:default="1" w:styleId="Table"><w:name w:val="Table"/>'
        '<w:basedOn w:val="TableNormal"/><w:uiPriority w:val="59"/>'
        '<w:pPr><w:spacing w:before="0" w:after="0" w:line="240" w:lineRule="auto"/>'
        '<w:ind w:firstLine="0"/><w:jc w:val="left"/></w:pPr>'
        f'<w:rPr><w:sz w:val="{half_points(tbl["size_pt"])}"/></w:rPr>'
        '<w:tblPr><w:tblBorders>'
        + ''.join(f'<w:{b} w:val="single" w:sz="4" w:space="0" w:color="000000"/>'
                  for b in ("top", "left", "bottom", "right", "insideH", "insideV"))
        + '</w:tblBorders><w:tblCellMar><w:top w:w="0" w:type="dxa"/>'
        '<w:left w:w="108" w:type="dxa"/><w:bottom w:w="0" w:type="dxa"/>'
        '<w:right w:w="108" w:type="dxa"/></w:tblCellMar></w:tblPr></w:style>'
        '<w:style w:type="table" w:styleId="TableNormal"><w:name w:val="Normal Table"/>'
        '<w:uiPriority w:val="99"/><w:semiHidden/><w:tblPr><w:tblInd w:w="0" w:type="dxa"/>'
        '<w:tblCellMar><w:top w:w="0" w:type="dxa"/><w:left w:w="108" w:type="dxa"/>'
        '<w:bottom w:w="0" w:type="dxa"/><w:right w:w="108" w:type="dxa"/></w:tblCellMar>'
        '</w:tblPr></w:style>')

    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
        '<w:styles xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
        '<w:docDefaults><w:rPrDefault><w:rPr>'
        f'{rfonts()}<w:sz w:val="{size}"/><w:szCs w:val="{size}"/>'
        f'<w:lang w:val="{lang}" w:eastAsia="{lang}" w:bidi="ar-SA"/>'
        '</w:rPr></w:rPrDefault><w:pPrDefault><w:pPr>'
        f'{hyph}<w:spacing w:after="0" w:line="{body_line}" w:lineRule="auto"/>'
        '</w:pPr></w:pPrDefault></w:docDefaults>'
        '<w:style w:type="character" w:default="1" w:styleId="DefaultParagraphFont">'
        '<w:name w:val="Default Paragraph Font"/><w:uiPriority w:val="1"/><w:semiHidden/>'
        '</w:style>'
        + table_style + ''.join(styles) + '</w:styles>')


def main():
    fmt_path, default_ref, out = sys.argv[1:4]
    with open(fmt_path, "rb") as fh:
        fmt = tomllib.load(fh)
    styles = build_styles(fmt)
    with zipfile.ZipFile(default_ref) as src, \
            zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as dst:
        for item in src.infolist():
            data = src.read(item.filename)
            if item.filename == "word/styles.xml":
                data = styles.encode("utf-8")
            dst.writestr(item, data)


if __name__ == "__main__":
    main()

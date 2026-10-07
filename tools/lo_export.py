#!/usr/bin/env python3
"""Оновлює зміст і поля DOCX у LibreOffice та експортує PDF (і/або DOCX).

Word оновлює зміст сам під час відкриття (документ це пропонує), а
LibreOffice — ні. Скрипт робить це без графічного інтерфейсу:

    python3 tools/lo_export.py build/thesis.docx build/thesis.pdf
    python3 tools/lo_export.py build/thesis.docx build/thesis-lo.docx

Потрібен LibreOffice з модулем python3-uno (системний python).
"""
import os
import subprocess
import sys
import tempfile
import time

import uno
from com.sun.star.beans import PropertyValue


def prop(name, value):
    p = PropertyValue()
    p.Name, p.Value = name, value
    return p


def main():
    src, *outs = sys.argv[1:]
    if not outs:
        sys.exit("використання: lo_export.py in.docx out.pdf [out.docx]")
    profile = tempfile.mkdtemp(prefix="lo-profile-")
    pipe = f"magistr{os.getpid()}"
    office = subprocess.Popen([
        "soffice", "--headless", "--invisible", "--nologo", "--norestore",
        f"-env:UserInstallation=file://{profile}",
        f"--accept=pipe,name={pipe};urp;StarOffice.ComponentContext",
    ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        local = uno.getComponentContext()
        resolver = local.ServiceManager.createInstanceWithContext(
            "com.sun.star.bridge.UnoUrlResolver", local)
        for _ in range(100):
            try:
                ctx = resolver.resolve(
                    f"uno:pipe,name={pipe};urp;StarOffice.ComponentContext")
                break
            except Exception:
                time.sleep(0.2)
        else:
            sys.exit("не вдалося запустити LibreOffice")
        desktop = ctx.ServiceManager.createInstanceWithContext(
            "com.sun.star.frame.Desktop", ctx)
        doc = desktop.loadComponentFromURL(
            uno.systemPathToFileUrl(os.path.abspath(src)), "_blank", 0,
            (prop("Hidden", True),))
        # Двічі: після першого оновлення змісту може зсунутися нумерація сторінок
        for _ in range(2):
            doc.getTextFields().refresh()
            indexes = doc.getDocumentIndexes()
            for i in range(indexes.getCount()):
                indexes.getByIndex(i).update()
            doc.refresh()
        for out in outs:
            url = uno.systemPathToFileUrl(os.path.abspath(out))
            if out.lower().endswith(".pdf"):
                doc.storeToURL(url, (prop("FilterName", "writer_pdf_Export"),))
            else:
                doc.storeToURL(url, (prop("FilterName", "MS Word 2007 XML"),))
            print(f">> {out}")
        doc.close(True)
    finally:
        try:
            desktop.terminate()
        except Exception:
            pass
        office.wait(timeout=30)
        subprocess.run(["rm", "-rf", profile])


if __name__ == "__main__":
    main()

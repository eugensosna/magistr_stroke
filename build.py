#!/usr/bin/env python3
"""Збірка магістерської роботи (Linux, macOS, Windows).

    uv run build.py              зібрати build/thesis.docx (у контейнері)
    uv run build.py pdf          DOCX + build/thesis.pdf (LibreOffice у контейнері,
                                 оновлює зміст і номери сторінок)
    uv run build.py html         швидкий HTML-перегляд build/thesis-preview.html
    uv run build.py check        перевірка посилань, джерел, рисунків і таблиць
    uv run build.py check --sort-bib   впорядкувати джерела за першим посиланням
    uv run build.py image        перезібрати образ контейнера
    uv run build.py shell        оболонка в контейнері
    uv run build.py local        зібрати без контейнера (asciidoctor, pandoc, sh)
    uv run build.py clean        видалити build/

Потрібні uv і podman або docker (на Windows — Docker Desktop з WSL 2).
Рушій можна задати змінною середовища ENGINE=docker|podman.
"""
import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
OUT = ROOT / "build"
SRC = "thesis.adoc"
NAME = Path(SRC).stem
IMAGE = "magistr-builder"
STAMP = OUT / ".image"


def run(cmd, **kw):
    print("$ " + " ".join(str(c) for c in cmd), flush=True)
    code = subprocess.run([str(c) for c in cmd], cwd=ROOT, **kw).returncode
    if code:
        sys.exit(code)


def engine():
    name = os.environ.get("ENGINE")
    exe = shutil.which(name) if name else (shutil.which("podman") or shutil.which("docker"))
    if not exe:
        sys.exit("не знайдено podman або docker (на Windows встановіть Docker Desktop з WSL 2)")
    return exe


def is_podman(exe):
    return Path(exe).stem.lower() == "podman"


def ensure_image(exe, force=False):
    """Збирає образ, якщо його немає або змінився Containerfile."""
    containerfile = ROOT / "Containerfile"
    exists = subprocess.run([exe, "image", "inspect", IMAGE], capture_output=True).returncode == 0
    fresh = STAMP.exists() and STAMP.stat().st_mtime >= containerfile.stat().st_mtime
    if force or not exists or not fresh:
        run([exe, "build", "-t", IMAGE, "-f", "Containerfile", "."])
        OUT.mkdir(exist_ok=True)
        STAMP.touch()


def container(*cmd, interactive=False):
    exe = engine()
    ensure_image(exe)
    args = [exe, "run", "--rm"]
    if interactive:
        args.append("-it")
    if is_podman(exe):
        args += ["-v", f"{ROOT}:/documents:Z"]
    else:
        args += ["--mount", f"type=bind,source={ROOT},target=/documents"]
        if hasattr(os, "getuid"):  # Linux/macOS: файли в build/ належатимуть користувачу
            args += ["-u", f"{os.getuid()}:{os.getgid()}"]
    args += ["-w", "/documents", IMAGE, *cmd]
    run(args)


def docx():
    container("sh", "tools/build.sh", SRC)


def pdf():
    docx()
    container("python3", "tools/lo_export.py", f"build/{NAME}.docx", f"build/{NAME}.pdf")


def html():
    container("asciidoctor", "-a", "toc=left", "-a", "sectnums", "-a", "stem=latexmath",
              "-a", "lang=uk", "-a", "imagesdir=../images",
              "-o", f"build/{NAME}-preview.html", SRC)


def check(*extra):
    run([sys.executable, "tools/check.py", *extra])


def local():
    run(["sh", "tools/build.sh", SRC])


def image():
    ensure_image(engine(), force=True)


def shell():
    container("sh", interactive=True)


def clean():
    shutil.rmtree(OUT, ignore_errors=True)


COMMANDS = {
    "docx": docx, "pdf": pdf, "html": html, "check": check, "local": local,
    "image": image, "shell": shell, "clean": clean,
}


def main():
    # Українські повідомлення в консолі Windows
    for stream in (sys.stdout, sys.stderr):
        stream.reconfigure(encoding="utf-8")
    os.environ.setdefault("PYTHONUTF8", "1")

    cmd, *rest = sys.argv[1:] or ["docx"]
    if cmd not in COMMANDS:
        sys.exit(__doc__)
    COMMANDS[cmd](*rest)


if __name__ == "__main__":
    main()

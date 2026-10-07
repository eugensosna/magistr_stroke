# Образ з усім інструментарієм для збірки магістерської роботи:
# asciidoctor (AsciiDoc -> HTML) + pandoc (HTML -> DOCX) + python3 (стилі та пост-обробка)
FROM docker.io/asciidoctor/docker-asciidoctor:latest
RUN apk add --no-cache pandoc-cli python3 make
WORKDIR /documents

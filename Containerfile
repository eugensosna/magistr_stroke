# Образ з усім інструментарієм для збірки магістерської роботи:
# asciidoctor (AsciiDoc -> HTML) + pandoc (HTML -> DOCX) + python3 (стилі та пост-обробка)
# + LibreOffice (оновлення змісту і PDF; Liberation Serif метрично сумісний з Times New Roman)
FROM docker.io/asciidoctor/docker-asciidoctor:latest
RUN apk add --no-cache pandoc-cli python3 libreoffice-writer font-liberation
WORKDIR /documents

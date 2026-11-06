#!/bin/sh
# Збірка роботи: AsciiDoc -> HTML (asciidoctor) -> DOCX (pandoc) -> пост-обробка.
# Запускається в контейнері (uv run build.py) або локально (uv run build.py local), якщо встановлені
# asciidoctor, pandoc >= 3.1 і python3 >= 3.11.
#
# MODE=dev (типово) - зауваження рецензента (// ЗАУВАЖЕННЯ ...) стають примітками Word,
#            виправлені ([fixed]) позначаються як закриті; результат: $OUT/<name>-dev.docx.
# MODE=release - чистовий документ без приміток; результат: $OUT/<name>-release.docx.
set -eu

SRC="${1:-thesis.adoc}"
NAME="$(basename "$SRC" .adoc)"
OUT="${OUT:-build}"
FORMAT="${FORMAT:-config/format.toml}"
MODE="${MODE:-dev}"

mkdir -p "$OUT"

REVIEW_JSON=""
if [ "$MODE" = "dev" ]; then
  echo ">> dev: зауваження рецензента -> примітки Word"
  python3 tools/review.py prepare "$OUT/src"
  SRC="$OUT/src/$SRC"
  REVIEW_JSON="$OUT/src/review.json"
  NAME="$NAME-dev"
elif [ "$MODE" = "release" ]; then
  NAME="$NAME-release"
else
  echo "!! невідомий MODE=$MODE (dev або release)" >&2
  exit 2
fi
export REVIEW_JSON

echo ">> reference.docx (стилі за $FORMAT)"
pandoc -o "$OUT/pandoc-default.docx" --print-default-data-file reference.docx
python3 tools/make_reference.py "$FORMAT" "$OUT/pandoc-default.docx" "$OUT/reference.docx"

echo ">> перевірка посилань"
python3 tools/check.py || echo "!! є помилки посилань (див. вище)"

echo ">> asciidoctor: $SRC"
asciidoctor \
  -r ./tools/asciidoctor/dstu_converter.rb -b dstuhtml -e \
  --failure-level WARN \
  -a sectnums! -a toc=macro -a stem=latexmath \
  -a figure-caption! -a table-caption! -a listing-caption! -a example-caption! \
  -a appendix-caption! -a lang=uk \
  -o "$OUT/$NAME.html" "$SRC"

echo ">> pandoc: $OUT/$NAME.docx"
pandoc "$OUT/$NAME.html" -f html -t docx \
  --reference-doc="$OUT/reference.docx" \
  --lua-filter=tools/filters/dstu.lua \
  --resource-path=. \
  --syntax-highlighting=none \
  -o "$OUT/$NAME.raw.docx"

python3 tools/postprocess.py "$FORMAT" "$OUT/$NAME.raw.docx" "$OUT/$NAME.docx" $REVIEW_JSON
rm -f "$OUT/$NAME.raw.docx" "$OUT/pandoc-default.docx"
echo ">> готово: $OUT/$NAME.docx"

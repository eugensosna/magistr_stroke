# Збірка магістерської роботи.
#
#   make          - зібрати build/thesis.docx (у контейнері, нічого не треба встановлювати)
#   make pdf      - додатково PDF через локальний LibreOffice (для перегляду)
#   make html     - швидкий HTML-перегляд у браузері
#   make check    - перевірка посилань, джерел, рисунків і таблиць
#   make local    - зібрати без контейнера (потрібні asciidoctor, pandoc, python3)
#   make clean    - видалити build/

SRC    ?= thesis.adoc
NAME   := $(basename $(notdir $(SRC)))
OUT    ?= build
IMAGE  ?= magistr-builder
ENGINE ?= $(shell command -v podman 2>/dev/null || command -v docker 2>/dev/null)

ifeq ($(notdir $(ENGINE)),docker)
  USER_FLAGS := -u $(shell id -u):$(shell id -g)
endif
RUN := $(ENGINE) run --rm $(USER_FLAGS) -v "$(CURDIR)":/documents:Z -w /documents $(IMAGE)

SOURCES := $(SRC) $(wildcard config/* chapters/*.adoc images/* tools/*.py tools/*.sh tools/*/*)

.PHONY: all docx pdf html local image shell clean check

all: docx

docx: $(OUT)/$(NAME).docx

$(OUT)/$(NAME).docx: $(SOURCES) $(OUT)/.image
	$(RUN) sh tools/build.sh $(SRC)

$(OUT)/.image: Containerfile
	@mkdir -p $(OUT)
	$(ENGINE) build -t $(IMAGE) -f Containerfile .
	@touch $@

image:
	$(ENGINE) build -t $(IMAGE) -f Containerfile .
	@mkdir -p $(OUT) && touch $(OUT)/.image

local:
	sh tools/build.sh $(SRC)

# PDF для перегляду: LibreOffice також оновлює зміст і номери сторінок
pdf: $(OUT)/$(NAME).pdf

$(OUT)/$(NAME).pdf: $(OUT)/$(NAME).docx
	python3 tools/lo_export.py $< $@

html: $(OUT)/$(NAME)-preview.html

$(OUT)/$(NAME)-preview.html: $(SOURCES) $(OUT)/.image
	$(RUN) asciidoctor -a toc=left -a sectnums -a stem=latexmath -a lang=uk \
	  -a imagesdir=../images -o $@ $(SRC)

shell: $(OUT)/.image
	$(ENGINE) run --rm -it $(USER_FLAGS) -v "$(CURDIR)":/documents:Z -w /documents $(IMAGE) sh

check:
	python3 tools/check.py

clean:
	rm -rf $(OUT)

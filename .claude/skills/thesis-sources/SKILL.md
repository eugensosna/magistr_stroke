---
name: thesis-sources
description: Пошук, перевірка та оформлення наукових джерел для магістерської роботи за ДСТУ 8302:2015 (список використаних джерел, chapters/95-references.adoc). Use when adding, verifying, formatting or citing literature, references, bibliography, DOI, "джерела", "література", "список літератури".
---

# Джерела за ДСТУ 8302:2015

**Головне правило: у список потрапляють лише джерела, існування яких перевірено.**
Не можна вигадувати авторів, назви, DOI, том, сторінки чи результати досліджень.
Не можна приписувати джерелу твердження, якого в ньому немає.

## Порядок роботи

1. **Пошук.** Використовуйте WebSearch, віддаючи перевагу таким джерелам:
   - систематичні огляди й метааналізи (Cochrane, PubMed / PMC);
   - рецензовані журнали (Journal of NeuroEngineering and Rehabilitation, Sensors, IEEE, Elsevier);
   - матеріали конференцій (CVPR, CHI);
   - офіційні сайти ВООЗ, МОЗ України, zakon.rada.gov.ua;
   - фахові видання України (категорії А, Б).

   Бажано, щоб у списку були свіжі (останні 5 років) та українські джерела.
2. **Перевірка метаданих** через Crossref за DOI:
   ```sh
   curl -s https://api.crossref.org/works/10.1186/s12984-016-0125-x | python3 -c "
   import json,sys; m=json.load(sys.stdin)['message']
   print([f\"{a.get('family')} {a.get('given','')}\" for a in m.get('author',[])])
   print(m['title'][0]); print(m.get('container-title'), m.get('volume'), m.get('issue'),
         m.get('page') or m.get('article-number'), m.get('issued'))"
   ```
   Якщо DOI невідомий, шукайте за назвою: `https://api.crossref.org/works?query.bibliographic=<назва>&rows=3`.
   Законодавчі акти перевіряйте на zakon.rada.gov.ua. Для них URL має вигляд `laws/show/<номер>-20` для актів IX скликання.
3. **Перевірка змісту.** Факт, який ви цитуєте (число, висновок), звіряйте з анотацією або текстом джерела через WebFetch.
   Якщо сторінка недоступна (403), шукайте ту саму роботу на PMC, arXiv або в репозиторії автора.
   Якщо підтвердити факт не вдалося, не наводьте його.
4. **Запис.** Додайте рядок до `chapters/95-references.adoc` (шаблони наведено нижче). Ідентифікатор утворюється з прізвища першого автора і року латиницею (`laver2020`). Для однакових ідентифікаторів додайте `a`, `b`.
5. **Цитування в тексті:** `<<laver2020>>` або `<<laver2020,с. 15>>`.
6. **Порядок і перевірка:**
   ```sh
   uv run build.py check --sort-bib    # порядок за першим посиланням
   uv run build.py check               # без помилок: усі джерела процитовані, немає битих посилань
   ```

## Шаблони опису (ДСТУ 8302:2015)

Правила оформлення:
- до 4 авторів перелічуються всі;
- від 5 авторів пишуться перші три, далі `et al.` (для кириличних джерел — `та ін.`);
- ініціали стоять після прізвища, між ними пробіл;
- назва журналу, книги чи збірника виділяється курсивом;
- між елементами опису ставиться «. » (крапка й пробіл);
- місце видання відокремлюється від видавця пробілом, двокрапкою і пробілом (` : `);
- діапазони сторінок пишуться через тире без пробілів (`P. 18–29`, `С. 161–170`);
- DOI указується в кінці, без `https://doi.org/`;
- для електронних ресурсів обов'язкові `URL:` і `(дата звернення: ДД.ММ.РРРР)`.

```asciidoc
// Стаття в журналі (латиниця)
* [[[weichert2013]]] Weichert F., Bachmann D., Rudak B., Fisseler D. Analysis of the accuracy and robustness of the Leap Motion Controller. _Sensors_. 2013. Vol. 13, No. 5. P. 6380–6393. DOI: 10.3390/s130506380.

// Стаття з номером статті замість сторінок, 5+ авторів
* [[[shin2016]]] Shin J.-H., Kim M.-Y., Lee J.-Y. et al. Effects of virtual reality-based rehabilitation ... _Journal of NeuroEngineering and Rehabilitation_. 2016. Vol. 13. Art. 17. DOI: 10.1186/s12984-016-0125-x.

// Стаття в журналі (кирилиця)
* [[[totska2025]]] Тоцька А. В., Мохна В. С., Соміло О. В. та ін. Назва статті. _Медичні перспективи_. 2025. Т. 30, № 4. С. 161–170. DOI: 10.26641/2307-0404.2025.4.348366.

// Огляд Cochrane
* [[[laver2020]]] Laver K. E., Adey-Wakeling Z., Crotty M. et al. Telerehabilitation services for stroke. _Cochrane Database of Systematic Reviews_. 2020. Issue 1. Art. No. CD010255. DOI: 10.1002/14651858.CD010255.pub3.

// Доповідь на конференції
* [[[simon2017]]] Simon T., Joo H., Matthews I., Sheikh Y. Hand keypoint detection in single images using multiview bootstrapping. _2017 IEEE Conference on Computer Vision and Pattern Recognition (CVPR)_, Honolulu, 21–26 July 2017. P. 4645–4653. DOI: 10.1109/CVPR.2017.494.

// Препринт arXiv
* [[[zhang2020]]] Zhang F., Bazarevsky V., Vakunov A. et al. MediaPipe Hands: on-device real-time hand tracking. arXiv:2006.10214. 2020. DOI: 10.48550/arXiv.2006.10214.

// Книга
* [[[id]]] Прізвище І. Б. Назва книги : підзаголовок. 2-ге вид. Київ : Наук. думка, 2024. 250 с.

// Закон
* [[[law1053]]] Про реабілітацію у сфері охорони здоров'я : Закон України від 03.12.2020 № 1053-IX. URL: https://zakon.rada.gov.ua/laws/show/1053-20 (дата звернення: 07.10.2026).

// Вебсторінка, документація ПЗ
* [[[id]]] MediaPipe Hand Landmarker guide. _Google AI for Developers_ : вебсайт. URL: https://ai.google.dev/edge/mediapipe/solutions/vision/hand_landmarker (дата звернення: ДД.ММ.РРРР).

// Стандарт
* [[[dstu3008]]] ДСТУ 3008:2015. Інформація та документація. Звіти у сфері науки і техніки. Структура та правила оформлювання. Вид. офіц. Київ : ДП «УкрНДНЦ», 2016. 26 с.
```

Документацію бібліотек (MediaPipe, OpenCV, Unity, Godot тощо) оформлюйте як вебсторінку з датою звернення.
Перед додаванням перевірте, що URL відкривається.

## Звіт користувачу

Після додавання джерел коротко перелічіть їх, укажіть, чим кожне підтверджено (DOI / Crossref / офіційний сайт), і позначте, що перевірити не вдалося.

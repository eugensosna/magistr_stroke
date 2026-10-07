--[[
Lua-фільтр pandoc: перетворює HTML від tools/asciidoctor/dstu_converter.rb
на структуру, оформлену за ДСТУ 3008:2015 / Наказом МОН № 40.

  * РОЗДІЛ 1 / ДОДАТОК А - заголовки, нумерація підрозділів 1.1, 1.1.1, А.1;
  * "Рисунок 1.1 – Назва" під рисунком, "Таблиця 1.1 – Назва" над таблицею,
    "Лістинг 1.1 – Назва" над лістингом;
  * формули з номером (1.1) біля правого поля;
  * нумерація джерел у списку та посилань [1], [1, с. 15];
  * автоматичний текст перехресних посилань: <<fig-x>> -> 1.1;
  * зміст (поле TOC Word), розриви сторінок, виноски, примітки.
]]

local stringify = pandoc.utils.stringify

local LABEL = {
  chapter  = 'РОЗДІЛ',
  appendix = 'ДОДАТОК',
  figure   = 'Рисунок',
  table    = 'Таблиця',
  listing  = 'Лістинг',
  dash     = '–',
}
local ADMONITION = {
  note = 'Примітка.', tip = 'Порада.', important = 'Важливо.',
  warning = 'Увага.', caution = 'Застереження.',
}
-- Літери для позначення додатків (без Ґ, Є, З, І, Ї, Й, О, Ч, Ь)
local APPENDIX_LETTERS = {
  'А', 'Б', 'В', 'Г', 'Д', 'Е', 'Ж', 'К', 'Л', 'М', 'Н', 'П', 'Р', 'С',
  'Т', 'У', 'Ф', 'Х', 'Ц', 'Ш', 'Щ', 'Ю', 'Я',
}

local TOC_XML = [[
<w:sdt><w:sdtPr><w:docPartObj><w:docPartGallery w:val="Table of Contents"/><w:docPartUnique/></w:docPartObj></w:sdtPr><w:sdtContent>
<w:p><w:pPr><w:pStyle w:val="TOC1"/></w:pPr><w:r><w:fldChar w:fldCharType="begin" w:dirty="true"/></w:r><w:r><w:instrText xml:space="preserve"> TOC \o "1-3" \h \z \u </w:instrText></w:r><w:r><w:fldChar w:fldCharType="separate"/></w:r><w:r><w:t>Зміст буде сформовано після оновлення полів документа (у Word: Ctrl+A, F9).</w:t></w:r><w:r><w:fldChar w:fldCharType="end"/></w:r></w:p>
</w:sdtContent></w:sdt>]]
local PAGE_BREAK_XML = '<w:p><w:r><w:br w:type="page"/></w:r></w:p>'
local TAB = pandoc.RawInline('openxml', '<w:r><w:tab/></w:r>')

-- ---------------------------------------------------------------------------
-- Стан нумерації
-- ---------------------------------------------------------------------------
local kind = nil          -- 'chapter' | 'appendix' | 'structural'
local prefix = nil        -- '1', '2', 'А', ...
local chapter_no, appendix_no = 0, 0
local sec = {}            -- лічильники підрозділів за рівнями
local counters = {}       -- рисунки, таблиці, формули, лістинги
local refs = {}           -- id -> текст для перехресного посилання
local bib = {}            -- id джерела -> номер у списку
local bib_no = 0

local function reset_counters()
  sec = {}
  counters = { figure = 0, table = 0, equation = 0, listing = 0 }
end
reset_counters()

local function next_number(what)
  counters[what] = counters[what] + 1
  if prefix then
    return prefix .. '.' .. counters[what]
  end
  return tostring(counters[what])
end

local function styled(style, blocks)
  return pandoc.Div(blocks, pandoc.Attr('', {}, { ['custom-style'] = style }))
end

local function caption_inlines(label, num, id, title)
  local head = pandoc.Inlines({ pandoc.Str(label), pandoc.Space(), pandoc.Str(num) })
  local res = pandoc.Inlines({ pandoc.Span(head, pandoc.Attr(id or '')) })
  if title and #title > 0 then
    res:extend({ pandoc.Space(), pandoc.Str(LABEL.dash), pandoc.Space() })
    res:extend(title)
  end
  return res
end

-- Перші інлайни першого блоку (Plain/Para) у списку блоків
local function first_inlines(blocks)
  for _, b in ipairs(blocks) do
    if b.t == 'Para' or b.t == 'Plain' then return b.content end
    if b.t == 'Div' then
      local r = first_inlines(b.content)
      if r then return r end
    end
  end
  return nil
end

local function find_div(blocks, class)
  for _, b in ipairs(blocks) do
    if b.t == 'Div' and b.classes:includes(class) then return b end
  end
  return nil
end

local function attr_value(el, name)
  return el.attributes[name] or el.attributes['data-' .. name]
end

-- ---------------------------------------------------------------------------
-- Перетворення окремих елементів
-- ---------------------------------------------------------------------------
local process_blocks -- оголошення наперед

-- Великі літери в самому тексті (а не лише стилем), щоб так само було і в змісті
local function upper(inlines)
  return inlines:walk({ Str = function(s) return pandoc.Str(pandoc.text.upper(s.text)) end })
end

local function header(h)
  local level = h.level - 1  -- <h2> відповідає розділу першого рівня
  local id = h.identifier
  local title = h.content
  local content

  if level <= 1 then
    level = 1
    title = upper(title)
    reset_counters()
    if h.classes:includes('chapter') then
      kind = 'chapter'
      chapter_no = chapter_no + 1
      prefix = tostring(chapter_no)
      refs[id] = prefix
      content = pandoc.Inlines({ pandoc.Str(LABEL.chapter), pandoc.Space(),
                                 pandoc.Str(prefix), pandoc.LineBreak() })
      content:extend(title)
    elseif h.classes:includes('appendix') then
      kind = 'appendix'
      appendix_no = appendix_no + 1
      prefix = APPENDIX_LETTERS[appendix_no] or tostring(appendix_no)
      refs[id] = prefix
      content = pandoc.Inlines({ pandoc.Str(LABEL.appendix), pandoc.Space(),
                                 pandoc.Str(prefix), pandoc.LineBreak() })
      content:extend(title)
    else
      kind = 'structural'
      prefix = nil
      content = title
    end
    if h.classes:includes('notoc') then
      return { styled('Heading Unlisted', { pandoc.Para({ pandoc.Span(content, pandoc.Attr(id)) }) }) }
    end
    return { pandoc.Header(1, content, pandoc.Attr(id)) }
  end

  content = title
  if (kind == 'chapter' or kind == 'appendix') and not h.classes:includes('unnumbered') then
    sec[level] = (sec[level] or 0) + 1
    for l = level + 1, 9 do sec[l] = 0 end
    local parts = { prefix }
    for l = 2, level do parts[#parts + 1] = tostring(sec[l] or 0) end
    local num = table.concat(parts, '.')
    refs[id] = num
    content = pandoc.Inlines({ pandoc.Str(num), pandoc.Space() })
    content:extend(title)
  end
  if h.classes:includes('notoc') then
    return { styled('Heading Unlisted', { pandoc.Para({ pandoc.Span(content, pandoc.Attr(id)) }) }) }
  end
  return { pandoc.Header(level, content, pandoc.Attr(id)) }
end

local function image_block(div)
  local image
  div:walk({ Image = function(img) image = image or img end })
  if not image then return { div } end
  local title_div = find_div(div.content, 'title')
  local out = { styled('Figure', { pandoc.Para({ image }) }) }
  if title_div then
    local num = next_number('figure')
    if div.identifier ~= '' then refs[div.identifier] = num end
    out[#out + 1] = styled('Image Caption', {
      pandoc.Para(caption_inlines(LABEL.figure, num, div.identifier, first_inlines(title_div.content)))
    })
  end
  return out
end

local function stem_block(div)
  local tex
  div:walk({ Span = function(s)
    if s.classes:includes('math') then tex = attr_value(s, 'tex') or stringify(s) end
  end })
  if not tex then return { div } end
  local math = pandoc.Math('InlineMath', '\\displaystyle ' .. tex)
  local inl = { TAB, math }
  if not div.classes:includes('nonumber') then
    local num = '(' .. next_number('equation') .. ')'
    if div.identifier ~= '' then refs[div.identifier] = num end
    inl[#inl + 1] = TAB
    inl[#inl + 1] = pandoc.Span({ pandoc.Str(num) }, pandoc.Attr(div.identifier))
  end
  return { styled('Equation', { pandoc.Para(inl) }) }
end

local function listing_block(div)
  local title_div = find_div(div.content, 'title')
  local out = {}
  if title_div then
    local num = next_number('listing')
    if div.identifier ~= '' then refs[div.identifier] = num end
    out[#out + 1] = styled('Listing Caption', {
      pandoc.Para(caption_inlines(LABEL.listing, num, div.identifier, first_inlines(title_div.content)))
    })
  end
  div:walk({ CodeBlock = function(cb)
    cb.attr = pandoc.Attr()
    out[#out + 1] = cb
  end })
  return out
end

local function wrap_cells(rows)
  for _, row in ipairs(rows) do
    for _, cell in ipairs(row.cells) do
      -- Абзаци в комірках мають бути Para: для Plain pandoc завжди ставить
      -- стиль Compact і ігнорує custom-style.
      local blocks = process_blocks(cell.contents)
      blocks = blocks:walk({ Plain = function(p) return pandoc.Para(p.content) end })
      cell.contents = { styled('Table Text', blocks) }
    end
  end
end

local function table_block(tbl)
  wrap_cells(tbl.head.rows)
  for _, body in ipairs(tbl.bodies) do
    wrap_cells(body.head)
    wrap_cells(body.body)
  end
  wrap_cells(tbl.foot.rows)

  local title = first_inlines(tbl.caption.long or {})
  local out = {}
  if title and #title > 0 then
    local num = next_number('table')
    if tbl.identifier ~= '' then refs[tbl.identifier] = num end
    out[#out + 1] = styled('Table Caption', {
      pandoc.Para(caption_inlines(LABEL.table, num, tbl.identifier, title))
    })
  end
  tbl.caption = pandoc.Caption()
  tbl.attr = pandoc.Attr()
  out[#out + 1] = tbl
  return out
end

local function bibliography_block(div)
  local out = {}
  div:walk({ BulletList = function(list)
    for _, item in ipairs(list.content) do
      local blocks = pandoc.Blocks(item)
      local first = blocks[1]
      if first and (first.t == 'Para' or first.t == 'Plain') then
        bib_no = bib_no + 1
        local inl = first.content
        local id = ''
        local rest = pandoc.Inlines({})
        local i = 1
        -- [[[id]]] -> Span(id) "[мітка]"; мітку asciidoctor відкидаємо
        if inl[i] and inl[i].t == 'Span' and inl[i].identifier ~= '' then
          id = inl[i].identifier
          i = i + 1
        end
        if inl[i] and inl[i].t == 'Str' and inl[i].text:match('^%[.*%]$') then
          i = i + 1
          if inl[i] and inl[i].t == 'Space' then i = i + 1 end
        end
        for j = i, #inl do rest:insert(inl[j]) end
        if id ~= '' then bib[id] = bib_no end
        local para = pandoc.Inlines({ pandoc.Span({ pandoc.Str(bib_no .. '.') }, pandoc.Attr(id)),
                                      pandoc.Space() })
        para:extend(rest)
        blocks[1] = pandoc.Para(para)
      end
      out[#out + 1] = styled('Bibliography', blocks)
    end
    return list
  end })
  return out
end

-- Перелік скорочень: "ДСТУ – Державний стандарт України"
local function definition_items(items)
  local out = {}
  for _, item in ipairs(items) do
    local term, defs = item[1], item[2]
    local inl = pandoc.Inlines(term)
    inl:extend({ pandoc.Space(), pandoc.Str(LABEL.dash), pandoc.Space() })
    local first_def = defs[1] and first_inlines(defs[1])
    if first_def then inl:extend(first_def) end
    out[#out + 1] = pandoc.Para(inl)
  end
  return out
end

local function hdlist_block(div)
  local items = {}
  div:walk({ Table = function(tbl)
    for _, body in ipairs(tbl.bodies) do
      for _, row in ipairs(body.body) do
        local cells = row.cells
        if #cells >= 2 then
          items[#items + 1] = { first_inlines(cells[1].contents) or {},
                                { cells[2].contents } }
        end
      end
    end
  end })
  return definition_items(items)
end

local TITLEPAGE_STYLES = {
  center = 'Title Page Center', right = 'Title Page Right',
  left = 'Title Page Left', title = 'Title Page Title',
}
local PARAGRAPH_STYLES = {
  center = 'Centered', noindent = 'No Indent', right = 'Right Aligned',
}

local function titlepage_block(div)
  local out = {}
  local function visit(blocks)
    for _, b in ipairs(blocks) do
      if b.t == 'Div' and b.classes:includes('paragraph') then
        local style = 'Title Page Center'
        for cls, st in pairs(TITLEPAGE_STYLES) do
          if b.classes:includes(cls) then style = st end
        end
        out[#out + 1] = styled(style, process_blocks(b.content))
      elseif b.t == 'Div' then
        visit(b.content)
      else
        out[#out + 1] = styled('Title Page Center', { b })
      end
    end
  end
  visit(div.content)
  -- Розрив сторінки не потрібен: наступний заголовок (АНОТАЦІЯ) і так
  -- починається з нової сторінки.
  return out
end

local function admonition_block(div)
  local label = 'Примітка.'
  for cls, l in pairs(ADMONITION) do
    if div.classes:includes(cls) then label = l end
  end
  local blocks = process_blocks(div.content)
  local done = false
  local function prepend(p)
    if done then return nil end
    done = true
    local inl = pandoc.Inlines({ pandoc.Str(label), pandoc.Space() })
    inl:extend(p.content)
    return pandoc.Para(inl)
  end
  blocks = blocks:walk({ Para = prepend, Plain = prepend })
  return { styled('Note', blocks) }
end

-- ---------------------------------------------------------------------------
-- Обхід документа в порядку слідування (важливо для нумерації)
-- ---------------------------------------------------------------------------
local function process_block(b)
  if b.t == 'Header' then
    return header(b)
  elseif b.t == 'Table' then
    return table_block(b)
  elseif b.t == 'OrderedList' then
    b.listAttributes = pandoc.ListAttributes(b.listAttributes.start,
                                             b.listAttributes.style, 'OneParen')
    b.content = b.content:map(function(item) return process_blocks(item) end)
    return { b }
  elseif b.t == 'BulletList' then
    b.content = b.content:map(function(item) return process_blocks(item) end)
    return { b }
  elseif b.t == 'DefinitionList' then
    return definition_items(b.content)
  elseif b.t == 'Div' then
    local c = b.classes
    if c:includes('dstu-toc') then
      return { styled('Heading Unlisted', { pandoc.Para(first_inlines(b.content)) }),
               pandoc.RawBlock('openxml', TOC_XML) }
    elseif c:includes('page-break') then
      return { pandoc.RawBlock('openxml', PAGE_BREAK_XML) }
    elseif c:includes('titlepage') then
      return titlepage_block(b)
    elseif c:includes('imageblock') then
      return image_block(b)
    elseif c:includes('stemblock') then
      return stem_block(b)
    elseif c:includes('listingblock') then
      return listing_block(b)
    elseif c:includes('bibliography') then
      return bibliography_block(b)
    elseif c:includes('hdlist') then
      return hdlist_block(b)
    elseif c:includes('admonition') then
      return admonition_block(b)
    elseif c:includes('paragraph') then
      for cls, st in pairs(PARAGRAPH_STYLES) do
        if c:includes(cls) then return { styled(st, process_blocks(b.content)) } end
      end
    end
    b.content = process_blocks(b.content)
    return { b }
  end
  return { b }
end

process_blocks = function(blocks)
  local out = pandoc.Blocks({})
  for _, b in ipairs(blocks) do
    out:extend(process_block(b))
  end
  return out
end

-- ---------------------------------------------------------------------------
-- Інлайни: формули, виноски, перехресні посилання
-- ---------------------------------------------------------------------------
local inline_filter = {
  Span = function(s)
    if s.classes:includes('math') and s.classes:includes('inline') then
      return pandoc.Math('InlineMath', attr_value(s, 'tex') or stringify(s))
    elseif s.classes:includes('footnote-inline') then
      return pandoc.Note({ pandoc.Para(s.content) })
    end
  end,
}

local link_filter = {
  Link = function(link)
    local id = link.target:match('^#(.+)$')
    if not id then return nil end
    local auto = link.classes:includes('xref-auto')
    link.attr = pandoc.Attr()
    if bib[id] then
      if auto then
        link.content = { pandoc.Str('[' .. bib[id] .. ']') }
      else
        local inl = pandoc.Inlines({ pandoc.Str('[' .. bib[id] .. ','), pandoc.Space() })
        inl:extend(link.content)
        inl:insert(pandoc.Str(']'))
        link.content = inl
      end
    elseif auto and refs[id] then
      link.content = { pandoc.Str(refs[id]) }
    end
    return link
  end,
}

function Pandoc(doc)
  -- Блок з виносками asciidoctor не потрібен
  doc.blocks = doc.blocks:filter(function(b)
    return not (b.t == 'Div' and b.identifier == 'footnotes')
  end)
  doc.blocks = doc.blocks:walk(inline_filter)
  doc.blocks = process_blocks(doc.blocks)
  doc.blocks = doc.blocks:walk(link_filter)
  -- Титульну сторінку формує сам документ, метадані pandoc не друкуємо
  doc.meta = pandoc.Meta({})
  return doc
end

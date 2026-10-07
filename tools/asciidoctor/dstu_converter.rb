# frozen_string_literal: true
#
# Конвертер asciidoctor -> "семантичний" HTML, який далі читає pandoc.
#
# Від стандартного html5 відрізняється тим, що:
#   * не нумерує розділи і не додає підписів "Figure 1." (нумерацію за ДСТУ
#     робить Lua-фільтр tools/filters/dstu.lua);
#   * позначає вид розділу (chapter / structural / appendix) класами на <hN>;
#   * передає формули LaTeX у data-tex, щоб pandoc зробив з них формули Word (OMML);
#   * позначає перехресні посилання без явного тексту класом xref-auto;
#   * виносить виноски у вигляд, з якого pandoc робить справжні виноски Word.
require 'cgi'

class DstuHtmlConverter < (Asciidoctor::Converter.for 'html5')
  register_for 'dstuhtml'

  # Назви структурних елементів, які не нумеруються (порівнюються без регістру).
  STRUCTURAL = [
    'анотація', 'abstract', 'зміст', 'перелік умовних позначень',
    'перелік скорочень', 'перелік умовних позначень, символів, одиниць, скорочень і термінів',
    'вступ', 'висновки', 'загальні висновки', 'список використаних джерел',
    'список використаної літератури', 'додатки'
  ].freeze
  # Структурні елементи, які не включаються до змісту.
  NOT_IN_TOC = ['анотація', 'abstract', 'зміст'].freeze

  def convert_section node
    level = node.level
    title = node.title
    plain = title.gsub(/<[^>]+>/, '').strip.downcase
    classes = []
    if level == 1
      if node.sectname == 'appendix'
        classes << 'appendix'
      elsif node.sectname == 'bibliography' || node.role?('unnumbered') || STRUCTURAL.include?(plain)
        classes << 'structural'
      else
        classes << 'chapter'
      end
      classes << 'notoc' if node.role?('notoc') || NOT_IN_TOC.include?(plain)
    else
      classes << 'unnumbered' if node.role?('unnumbered')
      classes << 'notoc' if node.role?('notoc')
    end
    tag = "h#{[level + 1, 6].min}"
    id_attr = node.id ? %( id="#{node.id}") : ''
    %(<#{tag}#{id_attr} class="#{classes.join ' '}">#{title}</#{tag}>\n#{node.content})
  end

  def convert_stem node
    id_attr = node.id ? %( id="#{node.id}") : ''
    tex = CGI.escapeHTML(node.content.to_s.strip)
    %(<div#{id_attr} class="stemblock #{node.role}"><p><span class="math display" data-tex="#{tex}">#{tex}</span></p></div>)
  end

  def convert_inline_quoted node
    if node.type == :latexmath || node.type == :asciimath
      tex = CGI.escapeHTML(CGI.unescapeHTML(node.text.to_s))
      %(<span class="math inline" data-tex="#{tex}">#{tex}</span>)
    else
      super
    end
  end

  def convert_inline_anchor node
    html = super
    if node.type == :xref && !node.attributes['path'] && node.text.nil?
      html = html.sub('<a ', '<a class="xref-auto" ')
    end
    html
  end

  def convert_inline_footnote node
    if node.type == :xref
      '' # повторне посилання на ту саму виноску не підтримується Word, пропускаємо
    else
      %(<span class="footnote-inline">#{node.text}</span>)
    end
  end

  def convert_toc node
    %(<div class="dstu-toc"><p>#{node.document.attr 'toc-title', 'Зміст'}</p></div>)
  end

  def convert_page_break node
    %(<div class="page-break"><p>page-break</p></div>)
  end

  def convert_admonition node
    %(<div class="admonition #{node.attr 'name'}"><div class="content">#{node.content}</div></div>)
  end

  # Футер з виносками не потрібен: виноски будуть справжніми виносками Word.
  def convert_embedded node
    node.content
  end
end

/**
 * 基础 HTML 消毒：移除 script 标签和事件属性，保留安全标签
 */
export function sanitizeHtml(html) {
  if (!html) return ''
  return html
    .replace(/<script\b[^<]*(?:(?!<\/script>)<[^<]*)*<\/script>/gi, '')
    .replace(/\bon\w+\s*=\s*["'][^"']*["']/gi, (match) => {
      // 保留代码复制按钮的 onclick 事件
      if (match.includes('navigator.clipboard.writeText')) return match
      return ''
    })
    .replace(/\bjavascript\s*:/gi, '')
}

/**
 * Markdown 转 HTML 渲染器
 * 支持：代码块(带语法高亮类名)、Mermaid 流程图、表格、行内代码、
 *       粗体、斜体、标题、有序/无序列表、链接、引用、分割线、换行
 */
export function renderMarkdown(text) {
  if (!text) return ''

  const escapeHtml = (str) =>
    str
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;')

  // ── 1. 提取代码块 ──────────────────────────────────
  const codeBlocks = []
  text = text.replace(/```(\w*)\n?([\s\S]*?)```/g, (_, lang, code) => {
    const idx = codeBlocks.length
    const trimmed = code.trimEnd()
    if (lang === 'mermaid') {
      codeBlocks.push(`<div class="mermaid-chart">${escapeHtml(trimmed)}</div>`)
    } else {
      codeBlocks.push(
        `<div class="code-block-wrapper"><button class="code-copy-btn" onclick="navigator.clipboard.writeText(this.parentElement.querySelector('code').textContent)">复制</button><pre><code class="code-block${lang ? ' language-' + lang : ''}">${escapeHtml(trimmed)}</code></pre></div>`
      )
    }
    return `\x00CODEBLOCK${idx}\x00`
  })

  // ── 2. 提取行内代码 ──────────────────────────────────
  const inlineCodes = []
  text = text.replace(/`([^`\n]+)`/g, (_, code) => {
    const idx = inlineCodes.length
    inlineCodes.push(`<code class="inline-code">${escapeHtml(code)}</code>`)
    return `\x00INLINECODE${idx}\x00`
  })

  // ── 3. 提取表格 ──────────────────────────────────
  const tables = []
  text = text.replace(/^(\|.+\|)\n(\|[\s\-:|]+\|)\n((?:\|.+\|\n?)*)/gm, (_, headerRow, sepRow, bodyRows) => {
    const idx = tables.length
    const parseRow = (row) =>
      row.split('|').filter(c => c.trim() !== '').map(c => c.trim())
    const headers = parseRow(headerRow)
    const bodyLines = bodyRows.trim().split('\n').filter(l => l.trim())
    let html = '<table class="md-table"><thead><tr>'
    headers.forEach(h => { html += `<th>${renderInline(h)}</th>` })
    html += '</tr></thead><tbody>'
    bodyLines.forEach(line => {
      const cells = parseRow(line)
      html += '<tr>'
      cells.forEach(c => { html += `<td>${renderInline(c)}</td>` })
      html += '</tr>'
    })
    html += '</tbody></table>'
    tables.push(html)
    return `\x00TABLE${idx}\x00`
  })

  // ── 4. 按行处理块级元素 ──────────────────────────
  const lines = text.split('\n')
  const result = []
  let inList = false
  let listType = ''
  let inBlockquote = false

  const closeList = () => {
    if (inList) {
      result.push(listType === 'ul' ? '</ul>' : '</ol>')
      inList = false
      listType = ''
    }
  }

  const closeBlockquote = () => {
    if (inBlockquote) {
      result.push('</blockquote>')
      inBlockquote = false
    }
  }

  for (let i = 0; i < lines.length; i++) {
    const line = lines[i]

    // 代码块/表格占位符
    if (/\x00(CODEBLOCK|TABLE)\d+\x00/.test(line)) {
      closeList()
      closeBlockquote()
      result.push(line)
      continue
    }

    // 引用块 (> ...)
    if (line.match(/^>\s?/)) {
      closeList()
      if (!inBlockquote) {
        inBlockquote = true
        result.push('<blockquote class="md-quote">')
      }
      const content = line.replace(/^>\s?/, '')
      result.push(`<p>${renderInline(content)}</p>`)
      continue
    }

    closeBlockquote()

    // 分割线 (--- or ***)
    if (/^(\-{3,}|\*{3,}|_{3,})\s*$/.test(line)) {
      closeList()
      result.push('<hr class="md-hr">')
      continue
    }

    // 标题
    const headingMatch = line.match(/^(#{1,6})\s+(.+)$/)
    if (headingMatch) {
      closeList()
      const level = headingMatch[1].length
      result.push(`<h${level}>${renderInline(headingMatch[2])}</h${level}>`)
      continue
    }

    // 无序列表
    const ulMatch = line.match(/^[\-\*]\s+(.+)$/)
    if (ulMatch) {
      if (!inList || listType !== 'ul') {
        closeList()
        inList = true
        listType = 'ul'
        result.push('<ul>')
      }
      result.push(`<li>${renderInline(ulMatch[1])}</li>`)
      continue
    }

    // 有序列表
    const olMatch = line.match(/^\d+\.\s+(.+)$/)
    if (olMatch) {
      if (!inList || listType !== 'ol') {
        closeList()
        inList = true
        listType = 'ol'
        result.push('<ol>')
      }
      result.push(`<li>${renderInline(olMatch[1])}</li>`)
      continue
    }

    // 空行
    if (line.trim() === '') {
      closeList()
      closeBlockquote()
      result.push('')
      continue
    }

    // 普通段落
    closeList()
    result.push(`<p>${renderInline(line)}</p>`)
  }

  closeList()
  closeBlockquote()

  let html = result.join('\n')

  // 还原占位符
  html = html.replace(/\x00CODEBLOCK(\d+)\x00/g, (_, idx) => codeBlocks[idx])
  html = html.replace(/\x00INLINECODE(\d+)\x00/g, (_, idx) => inlineCodes[idx])
  html = html.replace(/\x00TABLE(\d+)\x00/g, (_, idx) => tables[idx])

  return sanitizeHtml(html)

  // 行内元素渲染
  function renderInline(s) {
    // 图片 ![alt](url)
    s = s.replace(/!\[([^\]]*)\]\(([^)]+)\)/g, '<img src="$2" alt="$1" style="max-width:100%">')
    // 链接 [text](url)
    s = s.replace(/\[([^\]]+)\]\(([^)]+)\)/g, '<a href="$2" target="_blank" rel="noopener">$1</a>')
    // 粗体
    s = s.replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
    s = s.replace(/__(.+?)__/g, '<strong>$1</strong>')
    // 斜体
    s = s.replace(/(?<!\*)\*(?!\*)(.+?)(?<!\*)\*(?!\*)/g, '<em>$1</em>')
    s = s.replace(/(?<!_)_(?!_)(.+?)(?<!_)_(?!_)/g, '<em>$1</em>')
    // 删除线 ~~text~~
    s = s.replace(/~~(.+?)~~/g, '<del>$1</del>')
    // 换行
    s = s.replace(/\n/g, '<br>')
    return s
  }
}

import type { ReactNode } from 'react'

/**
 * 轻量文本渲染：不引 markdown 依赖，只认报告里真实会出现的几种结构。
 * - `#` / `##` 标题
 * - 整行【标题】
 * - `1.` / `1、` 序号
 * - `-` / `•` 项目符号
 * - 行内 **加粗**
 * 其余按段落显示，保留原始换行与缩进。
 */
function renderInline(text: string, keyPrefix: string): ReactNode[] {
  // 先切 **加粗** 和 `代码`，避免互相嵌套时错位
  return text.split(/(\*\*[^*]+\*\*|`[^`]+`)/g).map((part, i) => {
    const key = `${keyPrefix}-${i}`
    if (part.startsWith('**') && part.endsWith('**') && part.length > 4) {
      return <strong key={key}>{part.slice(2, -2)}</strong>
    }
    if (part.startsWith('`') && part.endsWith('`') && part.length > 2) {
      return (
        <code
          key={key}
          style={{
            background: '#f5f5f5',
            border: '1px solid #eeeeee',
            borderRadius: 4,
            padding: '1px 5px',
            fontSize: 12.5,
          }}
        >
          {part.slice(1, -1)}
        </code>
      )
    }
    return <span key={key}>{part}</span>
  })
}

export default function ReportView({ content }: { content: string }) {
  const lines = (content || '').replace(/\r\n/g, '\n').split('\n')

  return (
    <div style={{ fontSize: 14, lineHeight: 1.9, color: '#1f1f1f' }}>
      {lines.map((raw, index) => {
        const line = raw.replace(/\s+$/, '')
        const text = line.trim()
        const key = `line-${index}`

        if (!text) return <div key={key} style={{ height: 10 }} />

        // 引用块：模型常用 > 写数据告警，给个浅色背景比裸文本好读
        if (/^>\s?/.test(text)) {
          return (
            <div
              key={key}
              style={{
                margin: '6px 0',
                padding: '6px 12px',
                background: '#fafafa',
                borderLeft: '3px solid #d9d9d9',
                color: '#595959',
              }}
            >
              {renderInline(text.replace(/^>\s?/, ''), key)}
            </div>
          )
        }

        const heading = /^(#{1,4})\s+(.*)$/.exec(text)
        if (heading) {
          return (
            <div
              key={key}
              style={{
                fontSize: heading[1].length <= 2 ? 19 : 16,
                fontWeight: 600,
                margin: '18px 0 8px',
              }}
            >
              {heading[2]}
            </div>
          )
        }

        if (/^【.+】$/.test(text)) {
          return (
            <div
              key={key}
              style={{
                fontSize: 16,
                fontWeight: 600,
                color: '#ad6800',
                margin: '20px 0 8px',
                paddingLeft: 10,
                borderLeft: '3px solid #faad14',
              }}
            >
              {text}
            </div>
          )
        }

        const numbered = /^(\d+)\s*[.、)]\s*(.*)$/.exec(text)
        if (numbered) {
          return (
            <div key={key} style={{ margin: '6px 0', paddingLeft: 2 }}>
              <strong style={{ marginRight: 6 }}>{numbered[1]}.</strong>
              {renderInline(numbered[2], key)}
            </div>
          )
        }

        if (/^[-*•·]\s+/.test(text)) {
          return (
            <div key={key} style={{ margin: '4px 0 4px 16px' }}>
              <span style={{ color: '#8c8c8c', marginRight: 6 }}>•</span>
              {renderInline(text.replace(/^[-*•·]\s+/, ''), key)}
            </div>
          )
        }

        return (
          <div key={key} style={{ margin: '4px 0', whiteSpace: 'pre-wrap' }}>
            {renderInline(line, key)}
          </div>
        )
      })}
    </div>
  )
}

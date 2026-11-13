import { useMemo, useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useSearchParams } from 'react-router-dom'
import {
  Button,
  Card,
  Descriptions,
  Drawer,
  Empty,
  Input,
  Popconfirm,
  Space,
  Table,
  Tag,
  Typography,
  message,
} from 'antd'
import type { ColumnsType } from 'antd/es/table'
import { CopyOutlined, DeleteOutlined, DownloadOutlined, ReloadOutlined } from '@ant-design/icons'

import { api, type AgentReportSummary } from '../api/client'
import ReportView from '../components/ReportView'

const { Text } = Typography

export default function Reports() {
  const qc = useQueryClient()
  const [params, setParams] = useSearchParams()
  const [keyword, setKeyword] = useState('')

  const activeId = params.get('report')
  const setActive = (id: string | null) => {
    const next = new URLSearchParams(params)
    if (id) next.set('report', id)
    else next.delete('report')
    setParams(next, { replace: true })
  }

  const list = useQuery({ queryKey: ['reports'], queryFn: () => api.reports() })

  const detail = useQuery({
    queryKey: ['report', activeId],
    queryFn: () => api.report(activeId as string),
    enabled: !!activeId,
  })

  const remove = useMutation({
    mutationFn: (id: string) => api.deleteReport(id),
    onSuccess: (_, id) => {
      message.success('已删除')
      if (activeId === id) setActive(null)
      qc.invalidateQueries({ queryKey: ['reports'] })
    },
    onError: (err) => message.error((err as Error).message),
  })

  const rows = useMemo(() => {
    const all = list.data ?? []
    if (!keyword.trim()) return all
    const kw = keyword.trim().toLowerCase()
    return all.filter(
      (r) => r.title.toLowerCase().includes(kw) || r.agent_name.toLowerCase().includes(kw),
    )
  }, [list.data, keyword])

  const copyContent = async (text: string) => {
    try {
      await navigator.clipboard.writeText(text)
      message.success('已复制到剪贴板')
    } catch {
      message.error('浏览器不允许访问剪贴板')
    }
  }

  const download = (title: string, content: string) => {
    const blob = new Blob([content], { type: 'text/plain;charset=utf-8' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `${title || 'report'}.md`
    a.click()
    URL.revokeObjectURL(url)
  }

  const columns: ColumnsType<AgentReportSummary> = [
    {
      title: '标题',
      dataIndex: 'title',
      render: (title: string, row) => (
        <Space direction="vertical" size={0}>
          <a onClick={() => setActive(row.report_id)}>{title || '（无标题）'}</a>
          <Text type="secondary" style={{ fontSize: 12 }}>
            {row.agent_name}
            {row.mock && <Tag style={{ marginLeft: 8 }}>样例</Tag>}
          </Text>
        </Space>
      ),
    },
    {
      title: '字数',
      dataIndex: 'length',
      width: 90,
      render: (v: number) => <Text type="secondary">{v}</Text>,
    },
    {
      title: '工具',
      dataIndex: 'tool_calls',
      width: 90,
      render: (c: unknown[]) => (c?.length ? `${c.length} 次` : '—'),
    },
    {
      title: 'tokens',
      dataIndex: 'tokens',
      width: 100,
      render: (v: number) => (v ? v.toLocaleString() : '—'),
    },
    {
      title: '生成时间',
      dataIndex: 'created_at',
      width: 170,
      render: (v: string | null) => v?.replace('T', ' ').slice(0, 19) ?? '—',
    },
    {
      title: '操作',
      width: 130,
      render: (_, row) => (
        <Space>
          <Button size="small" type="link" onClick={() => setActive(row.report_id)}>
            查看
          </Button>
          <Popconfirm title="删除这份报告？" onConfirm={() => remove.mutate(row.report_id)}>
            <Button size="small" type="link" danger icon={<DeleteOutlined />} />
          </Popconfirm>
        </Space>
      ),
    },
  ]

  return (
    <Card
      title="报告"
      extra={
        <Space>
          <Input.Search
            allowClear
            placeholder="搜索标题或智能体"
            style={{ width: 240 }}
            value={keyword}
            onChange={(e) => setKeyword(e.target.value)}
          />
          <Button icon={<ReloadOutlined />} onClick={() => list.refetch()} loading={list.isFetching}>
            刷新
          </Button>
        </Space>
      }
    >
      <Text type="secondary">
        智能体每次试运行/生成都会留档在这里，点标题在线查看排版后的内容。
      </Text>
      <Table
        style={{ marginTop: 12 }}
        rowKey="report_id"
        size="middle"
        loading={list.isLoading}
        dataSource={rows}
        columns={columns}
        pagination={{ pageSize: 20, hideOnSinglePage: true }}
        locale={{ emptyText: <Empty description="还没有报告，去「智能体」页试运行一次" /> }}
      />

      <Drawer
        title={detail.data?.title ?? '报告'}
        width={860}
        open={!!activeId}
        onClose={() => setActive(null)}
        extra={
          detail.data && (
            <Space>
              <Button icon={<CopyOutlined />} onClick={() => copyContent(detail.data!.content)}>
                复制
              </Button>
              <Button
                icon={<DownloadOutlined />}
                onClick={() => download(detail.data!.title, detail.data!.content)}
              >
                下载
              </Button>
            </Space>
          )
        }
      >
        {detail.isLoading && <Text type="secondary">加载中…</Text>}
        {detail.data && (
          <>
            <Descriptions size="small" column={2} style={{ marginBottom: 16 }}>
              <Descriptions.Item label="智能体">{detail.data.agent_name}</Descriptions.Item>
              <Descriptions.Item label="生成时间">
                {detail.data.created_at?.replace('T', ' ').slice(0, 19) ?? '—'}
              </Descriptions.Item>
              <Descriptions.Item label="tokens">{detail.data.tokens || '—'}</Descriptions.Item>
              <Descriptions.Item label="工具调用">
                {detail.data.tool_calls?.length ? `${detail.data.tool_calls.length} 次` : '无'}
              </Descriptions.Item>
            </Descriptions>

            {detail.data.format === 'json' ? (
              <pre
                style={{
                  background: '#fafafa',
                  border: '1px solid #f0f0f0',
                  borderRadius: 6,
                  padding: 12,
                  fontSize: 12,
                  overflow: 'auto',
                }}
              >
                {detail.data.content}
              </pre>
            ) : (
              <ReportView content={detail.data.content} />
            )}
          </>
        )}
      </Drawer>
    </Card>
  )
}

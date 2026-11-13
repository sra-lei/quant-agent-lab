import { useQuery } from '@tanstack/react-query'
import { Card, Table, Tag, Typography } from 'antd'
import type { ColumnsType } from 'antd/es/table'
import { api, type RunSummary } from '../api/client'

const statusColor: Record<string, string> = { ok: 'green', partial: 'gold', running: 'blue', error: 'red' }

const columns: ColumnsType<RunSummary> = [
  { title: 'Run ID', dataIndex: 'run_id', width: 220 },
  { title: '目标', dataIndex: 'goal' },
  {
    title: '状态',
    dataIndex: 'status',
    width: 100,
    render: (v: string) => <Tag color={statusColor[v] ?? 'default'}>{v}</Tag>,
  },
  { title: '编排器', dataIndex: 'orchestrator', width: 110 },
  {
    title: '开始时间',
    dataIndex: 'started_at',
    width: 200,
    render: (v: string | null) => v ?? '-',
  },
]

export default function Runs() {
  const { data, isLoading } = useQuery({ queryKey: ['runs'], queryFn: api.runs })

  return (
    <Card
      title="运行记录"
      extra={<Typography.Text type="secondary">每次运行都留有 Agent 轨迹与数据快照</Typography.Text>}
    >
      <Table<RunSummary>
        rowKey="run_id"
        loading={isLoading}
        columns={columns}
        dataSource={data ?? []}
        pagination={{ pageSize: 20 }}
        expandable={{
          expandedRowRender: (row) => (
            <Typography.Text type="secondary">
              {row.error ? `错误：${row.error}` : '无错误'}
            </Typography.Text>
          ),
        }}
      />
    </Card>
  )
}

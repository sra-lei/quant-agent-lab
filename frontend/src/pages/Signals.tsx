import { useQuery } from '@tanstack/react-query'
import { Card, Table, Tag, Typography } from 'antd'
import type { ColumnsType } from 'antd/es/table'
import { api, type Signal } from '../api/client'

const stanceColor: Record<string, string> = { long: 'green', watch: 'gold', avoid: 'red' }

const columns: ColumnsType<Signal> = [
  { title: '日期', dataIndex: 'as_of', width: 110 },
  { title: '代码', dataIndex: 'code', width: 100 },
  { title: '名称', dataIndex: 'name', width: 120 },
  {
    title: '方向',
    dataIndex: 'stance',
    width: 90,
    render: (v: string) => <Tag color={stanceColor[v]}>{v}</Tag>,
  },
  {
    title: '置信度',
    dataIndex: 'conviction',
    width: 100,
    render: (v: number) => `${(v * 100).toFixed(0)}%`,
  },
  {
    title: '来源',
    dataIndex: 'sources',
    width: 220,
    render: (v: string[]) => v.map((s) => <Tag key={s}>{s}</Tag>),
  },
  { title: '理由', dataIndex: 'rationale' },
]

export default function Signals() {
  const { data, isLoading } = useQuery({ queryKey: ['signals'], queryFn: api.signals })

  return (
    <Card
      title="信号列表"
      extra={
        <Typography.Text type="secondary">
          每条信号都可追溯到具体 run 与数据快照
        </Typography.Text>
      }
    >
      <Table<Signal>
        rowKey={(r) => `${r.run_id}-${r.code}`}
        loading={isLoading}
        columns={columns}
        dataSource={data ?? []}
        pagination={{ pageSize: 20 }}
        size="middle"
      />
    </Card>
  )
}

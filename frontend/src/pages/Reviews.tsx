import { useQuery } from '@tanstack/react-query'
import { Alert, Card, Empty, List, Space, Statistic, Tag, Typography } from 'antd'
import { api } from '../api/client'

export default function Reviews() {
  const { data, isLoading } = useQuery({ queryKey: ['reviews'], queryFn: api.reviews })
  const rows = data ?? []

  return (
    <Card
      title="复盘报告"
      extra={<Typography.Text type="secondary">样本不足时不出命中率，避免误导</Typography.Text>}
    >
      {!isLoading && rows.length === 0 && (
        <Empty description="还没有复盘数据：需要先积累历史结论" />
      )}

      <Space direction="vertical" size="large" style={{ width: '100%' }}>
        {rows.map((r) => (
          <Card key={r.review_id} type="inner" title={`${r.period} · 样本 ${r.samples}`}>
            {r.samples === 0 ? (
              <Alert type="info" message="样本不足，本次不出评分" showIcon />
            ) : (
              <Space size="large" wrap>
                <Statistic title="命中率" value={(r.hit_rate * 100).toFixed(1)} suffix="%" />
                <Statistic title="平均收益" value={(r.avg_return * 100).toFixed(2)} suffix="%" />
              </Space>
            )}
            {r.improvements?.length > 0 && (
              <>
                <Typography.Title level={5} style={{ marginTop: 16 }}>
                  改进项
                </Typography.Title>
                <List
                  size="small"
                  dataSource={r.improvements}
                  renderItem={(item) => (
                    <List.Item>
                      <Tag color="blue">待办</Tag> {item}
                    </List.Item>
                  )}
                />
              </>
            )}
          </Card>
        ))}
      </Space>
    </Card>
  )
}

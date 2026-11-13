import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Alert, Button, Card, Col, List, Row, Space, Statistic, Tag, Typography } from 'antd'
import { api, type RunResult } from '../api/client'

const stanceColor: Record<string, string> = { long: 'green', watch: 'gold', avoid: 'red' }

export default function Dashboard() {
  const qc = useQueryClient()
  const health = useQuery({ queryKey: ['health'], queryFn: api.health })
  const signals = useQuery({ queryKey: ['signals'], queryFn: api.signals })

  const runMutation = useMutation({
    mutationFn: () =>
      api.createRun({
        goal: '总览页手动触发',
        universe: ['600519', '000858', '300750'],
        capital: 100000,
        risk: 'medium',
      }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['signals'] })
      qc.invalidateQueries({ queryKey: ['runs'] })
    },
  })

  const result: RunResult | undefined = runMutation.data

  return (
    <Space direction="vertical" size="large" style={{ width: '100%' }}>
      {health.data?.demo_mode && (
        <Alert
          type="warning"
          showIcon
          message="当前为演示模式（mock 数据），结论不代表真实行情"
        />
      )}

      <Row gutter={16}>
        <Col xs={24} md={8}>
          <Card>
            <Statistic title="系统状态" value={health.data?.status ?? '-'} />
            <Typography.Text type="secondary">
              编排器：{health.data?.orchestrator ?? '-'} ｜ 数据源：
              {health.data?.provider.name ?? '-'}
            </Typography.Text>
          </Card>
        </Col>
        <Col xs={24} md={8}>
          <Card>
            <Statistic title="已注册 Agent" value={health.data?.agents.length ?? 0} />
            <Typography.Text type="secondary">
              {health.data?.agents.join(' · ') ?? '-'}
            </Typography.Text>
          </Card>
        </Col>
        <Col xs={24} md={8}>
          <Card>
            <Button
              type="primary"
              block
              loading={runMutation.isPending}
              onClick={() => runMutation.mutate()}
            >
              跑一次研究
            </Button>
            <Typography.Paragraph type="secondary" style={{ marginTop: 12, marginBottom: 0 }}>
              触发一次完整链路：取数 → 双分析师 → 合并结论
            </Typography.Paragraph>
          </Card>
        </Col>
      </Row>

      {result?.conclusion && (
        <Card title={`本次结论 · ${result.run_id}`}>
          <Typography.Paragraph>{result.conclusion.summary}</Typography.Paragraph>
          <List
            size="small"
            dataSource={result.conclusion.picks}
            renderItem={(p) => (
              <List.Item>
                <Space>
                  <Tag color={stanceColor[p.stance]}>{p.stance}</Tag>
                  <strong>{p.code}</strong>
                  <span>{p.name}</span>
                  <Typography.Text type="secondary">
                    置信度 {(p.conviction * 100).toFixed(0)}%
                  </Typography.Text>
                  <Typography.Text type="secondary">来源：{p.sources.join(', ')}</Typography.Text>
                </Space>
              </List.Item>
            )}
          />
          {result.conclusion.disagreements.length > 0 && (
            <Alert
              style={{ marginTop: 16 }}
              type="info"
              showIcon
              message="专家分歧（未被平均，单独列出）"
              description={
                <ul style={{ margin: 0, paddingLeft: 18 }}>
                  {result.conclusion.disagreements.map((d) => (
                    <li key={d.code}>
                      {d.code}：{d.summary}
                    </li>
                  ))}
                </ul>
              }
            />
          )}
        </Card>
      )}

      <Card title="最近信号">
        <List
          size="small"
          dataSource={(signals.data ?? []).slice(0, 10)}
          locale={{ emptyText: '还没有信号，先跑一次研究' }}
          renderItem={(s) => (
            <List.Item>
              <Space>
                <Tag color={stanceColor[s.stance]}>{s.stance}</Tag>
                <strong>{s.code}</strong>
                <span>{s.name}</span>
                <Typography.Text type="secondary">
                  {(s.conviction * 100).toFixed(0)}%
                </Typography.Text>
              </Space>
            </List.Item>
          )}
        />
      </Card>
    </Space>
  )
}

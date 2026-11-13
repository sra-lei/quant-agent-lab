import { useQuery } from '@tanstack/react-query'
import {
  Alert,
  Button,
  Card,
  Col,
  Empty,
  Progress,
  Row,
  Space,
  Statistic,
  Table,
  Tag,
  Tooltip,
  Typography,
} from 'antd'
import { ReloadOutlined } from '@ant-design/icons'
import type { ColumnsType } from 'antd/es/table'

import {
  api,
  type CapitalFlowData,
  type DashboardModule,
  type FlowItem,
  type ModuleStatus,
  type OpportunityData,
  type PanoramaData,
  type PortfolioData,
  type Position,
  type RiskItem,
  type SentimentData,
} from '../api/client'

const { Text, Title, Paragraph } = Typography

/** A 股配色：红涨绿跌，别用反 */
const UP = '#f5222d'
const DOWN = '#52c41a'
const MUTED = '#8c8c8c'

const STATUS_META: Record<ModuleStatus, { color: string; text: string }> = {
  ok: { color: 'green', text: '实时' },
  degraded: { color: 'orange', text: '占位数据' },
  missing: { color: 'red', text: '未接入' },
}

function StatusTag({
  status,
  source,
  note,
}: {
  status: ModuleStatus
  source: string
  note?: string
}) {
  const meta = STATUS_META[status]
  return (
    <Tooltip title={`来源：${source}${note ? `｜${note}` : ''}`}>
      <Tag color={meta.color} style={{ marginInlineEnd: 0 }}>
        {meta.text}
      </Tag>
    </Tooltip>
  )
}

function ModuleCard<T>({
  title,
  index,
  module,
  children,
}: {
  title: string
  index: string
  module: DashboardModule<T>
  children: React.ReactNode
}) {
  return (
    <Card
      size="small"
      title={
        <Space size={8}>
          <Text type="secondary" style={{ fontSize: 12 }}>
            {index}
          </Text>
          <span>{title}</span>
        </Space>
      }
      extra={<StatusTag status={module.status} source={module.source} note={module.note} />}
    >
      {children}
    </Card>
  )
}

// ------------------------------------------------------------------ 模块一
function Panorama({ module }: { module: DashboardModule<PanoramaData> }) {
  const d = module.data
  const up = d.sentiment_index.delta >= 0
  return (
    <ModuleCard index="01" title="全景态势图" module={module}>
      <Row gutter={16}>
        <Col xs={24} lg={13}>
          <Text type="secondary" style={{ fontSize: 12 }}>
            战略要览
          </Text>
          <Paragraph style={{ fontSize: 15, lineHeight: 1.75, marginTop: 6, marginBottom: 10 }}>
            {d.brief}
          </Paragraph>
          <Space size={6} wrap>
            <Tag color="volcano">阶段 · {d.phase.label}</Tag>
            {d.core_conflict.evidences.map((e) => (
              <Tag key={e.label}>
                {e.label} {e.value}
                <Text type="secondary" style={{ marginLeft: 6, fontSize: 11 }}>
                  {e.change}
                </Text>
              </Tag>
            ))}
          </Space>
        </Col>
        <Col xs={24} lg={11}>
          <Row gutter={12}>
            <Col span={12}>
              <Statistic
                title="综合情绪指数"
                value={d.sentiment_index.today}
                precision={1}
                suffix="/ 100"
                valueStyle={{ color: up ? UP : DOWN }}
              />
              <Text type="secondary" style={{ fontSize: 12 }}>
                昨 {d.sentiment_index.yesterday} ｜{' '}
                <span style={{ color: up ? UP : DOWN }}>
                  {up ? '+' : ''}
                  {d.sentiment_index.delta}
                </span>
              </Text>
            </Col>
            <Col span={12}>
              <Text type="secondary" style={{ fontSize: 12 }}>
                核心矛盾
              </Text>
              <Paragraph style={{ marginTop: 4, marginBottom: 0, fontWeight: 500 }}>
                {d.core_conflict.text}
              </Paragraph>
              <Text type="secondary" style={{ fontSize: 12 }}>
                自 {d.phase.since} 起第 {d.phase.days} 天
              </Text>
            </Col>
          </Row>
        </Col>
      </Row>
    </ModuleCard>
  )
}

// ------------------------------------------------------------------ 模块二
function FlowList({
  items,
  inflow,
}: {
  items: FlowItem[]
  inflow: boolean
}) {
  const max = Math.max(...items.map((i) => (inflow ? i.net_inflow_yi ?? 0 : i.net_outflow_yi ?? 0)), 1)
  return (
    <Space direction="vertical" size={8} style={{ width: '100%' }}>
      {items.map((item) => {
        const value = inflow ? item.net_inflow_yi ?? 0 : item.net_outflow_yi ?? 0
        const color = inflow ? UP : DOWN
        return (
          <div key={item.board}>
            <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 12 }}>
              <span>
                {item.board}
                <Text type="secondary" style={{ marginLeft: 6, fontSize: 11 }}>
                  {item.leader}
                </Text>
              </span>
              <span style={{ color }}>
                {inflow ? '+' : '-'}
                {value.toFixed(1)} 亿
              </span>
            </div>
            <div style={{ background: '#f5f5f5', height: 6, borderRadius: 3, marginTop: 4 }}>
              <div
                style={{
                  width: `${Math.max(4, (value / max) * 100)}%`,
                  background: color,
                  height: 6,
                  borderRadius: 3,
                  opacity: 0.85,
                }}
              />
            </div>
          </div>
        )
      })}
    </Space>
  )
}

function CapitalFlow({ module }: { module: DashboardModule<CapitalFlowData> }) {
  const d = module.data
  return (
    <ModuleCard index="02" title="资金博弈图" module={module}>
      <Row gutter={16}>
        <Col span={12}>
          <Text style={{ color: UP, fontSize: 12 }}>净流入前五</Text>
          <div style={{ marginTop: 8 }}>
            <FlowList items={d.net_inflow_top} inflow />
          </div>
        </Col>
        <Col span={12}>
          <Text style={{ color: DOWN, fontSize: 12 }}>净流出前五</Text>
          <div style={{ marginTop: 8 }}>
            <FlowList items={d.net_outflow_top} inflow={false} />
          </div>
        </Col>
      </Row>
    </ModuleCard>
  )
}

// ------------------------------------------------------------------ 模块三
function Sparkline({ module }: { module: DashboardModule<SentimentData> }) {
  const { series, ma20 } = module.data
  const W = 560
  const H = 150
  const P = 10

  const values = series.map((s) => s.value)
  const mean = values.reduce((a, b) => a + b, 0) / values.length
  const std = Math.sqrt(values.reduce((a, b) => a + (b - mean) ** 2, 0) / values.length)
  const lo = Math.min(...values, ma20) - 4
  const hi = Math.max(...values, ma20) + 4
  const x = (i: number) => P + (i * (W - 2 * P)) / Math.max(1, series.length - 1)
  const y = (v: number) => H - P - ((v - lo) / (hi - lo)) * (H - 2 * P)

  const line = series.map((s, i) => `${x(i).toFixed(1)},${y(s.value).toFixed(1)}`).join(' ')
  const areaPath =
    `M ${x(0).toFixed(1)},${(H - P).toFixed(1)} ` +
    series.map((s, i) => `L ${x(i).toFixed(1)},${y(s.value).toFixed(1)} `).join('') +
    `L ${x(series.length - 1).toFixed(1)},${(H - P).toFixed(1)} Z`

  return (
    <svg viewBox={`0 0 ${W} ${H}`} width="100%" height={150} style={{ display: 'block' }}>
      <defs>
        <linearGradient id="sentGrad" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor={UP} stopOpacity="0.22" />
          <stop offset="100%" stopColor={UP} stopOpacity="0.02" />
        </linearGradient>
      </defs>
      <path d={areaPath} fill="url(#sentGrad)" />
      <line
        x1={P}
        x2={W - P}
        y1={y(ma20)}
        y2={y(ma20)}
        stroke={MUTED}
        strokeDasharray="4 4"
        strokeWidth="1"
      />
      <polyline points={line} fill="none" stroke={UP} strokeWidth="2" strokeLinejoin="round" />
      {series.map((s, i) => {
        const z = std ? (s.value - mean) / std : 0
        if (Math.abs(z) < 1.5) return null
        return (
          <circle
            key={s.date}
            cx={x(i)}
            cy={y(s.value)}
            r={3.5}
            fill={z > 0 ? UP : DOWN}
            stroke="#fff"
            strokeWidth="1"
          />
        )
      })}
    </svg>
  )
}

function Sentiment({ module }: { module: DashboardModule<SentimentData> }) {
  const d = module.data
  return (
    <ModuleCard index="03" title="情绪脉搏图" module={module}>
      <Sparkline module={module} />
      <Row gutter={12} style={{ marginTop: 8 }}>
        <Col span={12}>
          <Text type="secondary" style={{ fontSize: 12 }}>
            今日情绪 {d.series[d.series.length - 1]?.value} ｜ 20 日均值 {d.ma20}
          </Text>
        </Col>
        <Col span={12} style={{ textAlign: 'right' }}>
          <Text type="secondary" style={{ fontSize: 12 }}>
            极端区标的 {d.extremes.length} 个
          </Text>
        </Col>
      </Row>
      <Space direction="vertical" size={4} style={{ width: '100%', marginTop: 8 }}>
        {d.extremes.slice(0, 3).map((e) => (
          <div key={`${e.type}-${e.code}`} style={{ fontSize: 12 }}>
            <Tag color={e.side === 'hot' ? 'red' : 'green'} style={{ marginInlineEnd: 6 }}>
              {e.type === 'stock' ? '个股' : '板块'}
            </Tag>
            <Text strong>{e.name}</Text>
            <Text type="secondary" style={{ marginLeft: 6 }}>
              {e.reason}
            </Text>
          </div>
        ))}
      </Space>
    </ModuleCard>
  )
}

// ------------------------------------------------------------------ 模块四
function RadarChart({ axes, today, ma5 }: { axes: string[]; today: number[]; ma5: number[] }) {
  const size = 210
  const c = size / 2
  const r = 62
  const point = (i: number, v: number) => {
    const angle = -Math.PI / 2 + (i * 2 * Math.PI) / axes.length
    const rr = (r * v) / 100
    return [c + rr * Math.cos(angle), c + rr * Math.sin(angle)] as const
  }
  const polygon = (values: number[]) =>
    values.map((v, i) => point(i, v).map((n) => n.toFixed(1)).join(',')).join(' ')

  return (
    <svg viewBox={`0 0 ${size} ${size}`} width="100%" height={size}>
      {[20, 40, 60, 80, 100].map((ring) => (
        <polygon
          key={ring}
          points={polygon(axes.map(() => ring))}
          fill="none"
          stroke="#f0f0f0"
          strokeWidth="1"
        />
      ))}
      {axes.map((_, i) => {
        const [px, py] = point(i, 100)
        return <line key={i} x1={c} y1={c} x2={px} y2={py} stroke="#f0f0f0" />
      })}
      <polygon points={polygon(ma5)} fill="rgba(140,140,140,0.12)" stroke={MUTED} strokeDasharray="4 4" />
      <polygon points={polygon(today)} fill="rgba(245,34,45,0.18)" stroke={UP} strokeWidth="2" />
      {axes.map((label, i) => {
        const [px, py] = point(i, 118)
        return (
          <text
            key={label}
            x={px}
            y={py}
            fontSize="9.5"
            fill="#595959"
            textAnchor="middle"
            dominantBaseline="middle"
          >
            {label}
          </text>
        )
      })}
    </svg>
  )
}

function Opportunity({ module }: { module: DashboardModule<OpportunityData> }) {
  const d = module.data
  return (
    <ModuleCard index="04" title="机会雷达图" module={module}>
      <Row gutter={8} align="middle">
        <Col span={12}>
          <RadarChart axes={d.axes} today={d.today} ma5={d.ma5} />
          <div style={{ textAlign: 'center', fontSize: 11, color: MUTED }}>
            <span style={{ color: UP }}>━ 今日</span> · <span>┄ 5 日均值</span>
          </div>
        </Col>
        <Col span={12}>
          <Text type="secondary" style={{ fontSize: 12 }}>
            推荐方向
          </Text>
          <Space direction="vertical" size={10} style={{ width: '100%', marginTop: 8 }}>
            {d.picks.map((p) => (
              <div key={p.direction}>
                <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 13 }}>
                  <Text strong style={{ fontSize: 13 }}>
                    {p.direction}
                  </Text>
                  <Text type="secondary">{Math.round(p.conviction * 100)}%</Text>
                </div>
                <Progress
                  percent={Math.round(p.conviction * 100)}
                  showInfo={false}
                  size="small"
                  strokeColor={UP}
                />
                <Text type="secondary" style={{ fontSize: 11 }}>
                  {p.reason}
                </Text>
              </div>
            ))}
          </Space>
        </Col>
      </Row>
    </ModuleCard>
  )
}

// ------------------------------------------------------------------ 模块五
const LEVEL_COLOR: Record<RiskItem['level'], string> = {
  high: '#f5222d',
  medium: '#fa8c16',
  low: '#faad14',
}

const LEVEL_LABEL: Record<RiskItem['level'], string> = {
  high: '高',
  medium: '中',
  low: '低',
}

function Risks({ module }: { module: DashboardModule<{ items: RiskItem[] }> }) {
  const items = module.data.items
  return (
    <ModuleCard index="05" title="风险预警列表" module={module}>
      <Space direction="vertical" size={0} style={{ width: '100%', maxHeight: 190, overflowY: 'auto' }}>
        {items.length === 0 && <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="暂无风险提示" />}
        {items.map((r, i) => (
          <div
            key={`${r.title}-${i}`}
            style={{
              display: 'flex',
              gap: 10,
              padding: '8px 4px',
              borderBottom: i === items.length - 1 ? 'none' : '1px solid #f5f5f5',
            }}
          >
            <span
              style={{
                flex: '0 0 4px',
                background: LEVEL_COLOR[r.level],
                borderRadius: 2,
                marginTop: 2,
              }}
            />
            <div style={{ flex: 1 }}>
              <Space size={6}>
                <Tag color={LEVEL_COLOR[r.level]} style={{ marginInlineEnd: 0 }}>
                  {LEVEL_LABEL[r.level]}
                </Tag>
                <Text strong>{r.title}</Text>
                <Text type="secondary" style={{ fontSize: 11 }}>
                  {r.source} · {r.time.slice(11)}
                </Text>
              </Space>
              <div>
                <Text type="secondary" style={{ fontSize: 12 }}>
                  {r.evidence}
                </Text>
              </div>
            </div>
          </div>
        ))}
      </Space>
    </ModuleCard>
  )
}

// ------------------------------------------------------------------ 模块六
const ACTION_META: Record<string, { color: string; label: string }> = {
  add: { color: 'red', label: '加仓' },
  reduce: { color: 'orange', label: '减仓' },
  hold: { color: 'default', label: '持有' },
  watch: { color: 'blue', label: '观察' },
  stop: { color: 'green', label: '止损' },
}

function Portfolio({ module }: { module: DashboardModule<PortfolioData> }) {
  const d = module.data
  const s = d.summary

  const columns: ColumnsType<Position> = [
    {
      title: '持仓',
      dataIndex: 'name',
      render: (name: string, row) => (
        <Space direction="vertical" size={0}>
          <Text strong style={{ fontSize: 13 }}>
            {name}
          </Text>
          <Text type="secondary" style={{ fontSize: 11 }}>
            {row.code} · {row.hot_board}
          </Text>
        </Space>
      ),
    },
    {
      title: '盈亏',
      dataIndex: 'pnl_pct',
      align: 'right',
      render: (v: number) => (
        <Text style={{ color: v >= 0 ? UP : DOWN, fontSize: 13 }}>
          {v >= 0 ? '+' : ''}
          {v.toFixed(2)}%
        </Text>
      ),
    },
    {
      title: '仓位',
      dataIndex: 'weight',
      align: 'right',
      width: 70,
      render: (v: number) => <Text type="secondary">{v}%</Text>,
    },
  ]

  return (
    <ModuleCard index="06" title="持仓仪表盘" module={module}>
      <Row gutter={8}>
        <Col span={8}>
          <Statistic
            title="总盈亏"
            value={s.total_pnl}
            precision={0}
            prefix="¥"
            valueStyle={{ color: s.total_pnl >= 0 ? UP : DOWN, fontSize: 20 }}
          />
        </Col>
        <Col span={8}>
          <Statistic
            title="今日"
            value={s.today_pnl}
            precision={0}
            prefix="¥"
            valueStyle={{ color: s.today_pnl >= 0 ? UP : DOWN, fontSize: 20 }}
          />
        </Col>
        <Col span={8}>
          <Statistic title="热点匹配" value={s.match_score} suffix="/ 100" valueStyle={{ fontSize: 20 }} />
        </Col>
      </Row>

      <Table<Position>
        style={{ marginTop: 8 }}
        size="small"
        rowKey="code"
        pagination={false}
        dataSource={d.positions.slice(0, 3)}
        columns={columns}
      />
      {d.positions.length > 3 && (
        <Text type="secondary" style={{ fontSize: 11 }}>
          共 {d.positions.length} 只持仓，已显示仓位最大的 3 只
        </Text>
      )}

      <div style={{ marginTop: 10 }}>
        <Text type="secondary" style={{ fontSize: 12 }}>
          调仓建议
        </Text>
        <Space direction="vertical" size={6} style={{ width: '100%', marginTop: 6 }}>
          {d.advices.slice(0, 3).map((a) => {
            const meta = ACTION_META[a.action] ?? ACTION_META.hold
            return (
              <div key={a.code} style={{ fontSize: 12 }}>
                <Tag color={meta.color} style={{ marginInlineEnd: 6 }}>
                  {meta.label}
                </Tag>
                <Text strong>{a.code}</Text>
                <Text type="secondary" style={{ marginLeft: 6 }}>
                  {a.reason}
                </Text>
              </div>
            )
          })}
        </Space>
      </div>
    </ModuleCard>
  )
}

// ------------------------------------------------------------------ page
export default function Dashboard() {
  const q = useQuery({ queryKey: ['dashboard'], queryFn: api.dashboard })

  if (q.isError) {
    return (
      <Alert
        type="error"
        showIcon
        message="总览数据加载失败"
        description={(q.error as Error).message}
      />
    )
  }

  const data = q.data
  if (!data) {
    return <Card loading />
  }

  const m = data.modules

  return (
    <Space direction="vertical" size={16} style={{ width: '100%' }}>
      <div style={{ display: 'flex', alignItems: 'baseline', justifyContent: 'space-between' }}>
        <div>
          <Title level={4} style={{ margin: 0 }}>
            市场总览
          </Title>
          <Text type="secondary" style={{ fontSize: 12 }}>
            数据截止 {data.as_of} · 生成于 {data.generated_at.replace('T', ' ')}
            {data.mock ? ' · 当前为占位数据' : ''}
          </Text>
        </div>
        <Space>
          {data.mock && <Tag color="orange">MOCK</Tag>}
          <Button icon={<ReloadOutlined />} loading={q.isFetching} onClick={() => q.refetch()}>
            刷新
          </Button>
        </Space>
      </div>

      <Row gutter={[16, 16]}>
        <Col xs={24} xl={16}>
          <Panorama module={m.panorama} />
        </Col>
        <Col xs={24} xl={8}>
          <Portfolio module={m.portfolio} />
        </Col>

        <Col xs={24} lg={12} xl={8}>
          <CapitalFlow module={m.capital_flow} />
        </Col>
        <Col xs={24} lg={12} xl={8}>
          <Sentiment module={m.sentiment} />
        </Col>
        <Col xs={24} lg={24} xl={8}>
          <Opportunity module={m.opportunity} />
        </Col>

        <Col span={24}>
          <Risks module={m.risks} />
        </Col>
      </Row>
    </Space>
  )
}

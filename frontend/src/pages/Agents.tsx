import { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import {
  Alert,
  Button,
  Card,
  Divider,
  Drawer,
  Form,
  Input,
  Modal,
  Popconfirm,
  Select,
  Space,
  Switch,
  Table,
  Tag,
  Tooltip,
  Typography,
  message,
} from 'antd'
import { DeleteOutlined, FileTextOutlined, HistoryOutlined, PlusOutlined, PlayCircleOutlined } from '@ant-design/icons'
import { Link } from 'react-router-dom'
import type { ColumnsType } from 'antd/es/table'
import {
  api,
  type AgentConfig,
  type AgentConfigPayload,
  type AgentRunResult,
  type AgentVersion,
  type AgentVersionDiff,
  type OutputFormatType,
} from '../api/client'

const { TextArea } = Input
const { Text } = Typography

interface FormValues {
  name: string
  role: string
  profile: string
  task: string
  workflow: Array<{ name: string; instruction: string }>
  tools: string[]
  output_format_type: OutputFormatType
  output_spec: string
  schema_text: string
  enabled: boolean
}

export default function Agents() {
  const qc = useQueryClient()
  const { data: agents, isLoading } = useQuery({ queryKey: ['agents'], queryFn: api.agents })
  const { data: meta } = useQuery({ queryKey: ['agent-meta'], queryFn: api.agentMeta })

  const [open, setOpen] = useState(false)
  const [editing, setEditing] = useState<AgentConfig | null>(null)
  const [runResult, setRunResult] = useState<AgentRunResult | null>(null)
  const [form] = Form.useForm<FormValues>()
  const formatType = Form.useWatch('output_format_type', form)

  const stepName = (index: number) => `第 ${index + 1} 步`

  // 只有「占位式」步骤名才重排；内置 Agent 自己起的名字（如「取标的池」）保留
  const isGenericStepName = (name?: string) =>
    !name || /^第\s*\d+\s*步$/.test(name) || /^第[一二三四五六七八九十]+步$/.test(name)

  const renumberSteps = () => {
    const list = (form.getFieldValue('workflow') as Array<{ name: string; instruction: string }> | undefined) ?? []
    form.setFieldValue(
      'workflow',
      list.map((s, i) => ({ ...s, name: isGenericStepName(s.name) ? stepName(i) : s.name })),
    )
  }

  const save = useMutation({
    mutationFn: async (values: FormValues) => {
      let schema: Record<string, unknown> | undefined
      if (values.output_format_type === 'json_schema') {
        try {
          schema = JSON.parse(values.schema_text || '{}')
        } catch {
          throw new Error('JSON Schema 不是合法 JSON')
        }
      }
      const payload: AgentConfigPayload = {
        name: values.name,
        role: values.role ?? '',
        profile: values.profile ?? '',
        task: values.task ?? '',
        workflow: (values.workflow ?? []).map((s, i) => ({ ...s, name: stepName(i) })),
        tools: values.tools ?? [],
        output_format:
          values.output_format_type === 'json_schema'
            ? { type: 'json_schema', schema }
            : { type: values.output_format_type },
        output_spec: values.output_spec ?? '',
        enabled: values.enabled ?? true,
      }
      return editing
        ? api.updateAgent(editing.agent_id, payload)
        : api.createAgent(payload)
    },
    onSuccess: () => {
      message.success(editing ? '已保存' : '已创建')
      qc.invalidateQueries({ queryKey: ['agents'] })
      setOpen(false)
      setEditing(null)
      form.resetFields()
    },
    onError: (err: Error) => message.error(err.message),
  })

  const remove = useMutation({
    mutationFn: api.deleteAgent,
    onSuccess: () => {
      message.success('已删除')
      qc.invalidateQueries({ queryKey: ['agents'] })
    },
    onError: (err: Error) => message.error(err.message),
  })

  const dryRun = useMutation({
    mutationFn: (id: string) => api.runAgent(id, { note: '编辑器试运行', universe: ['600519'] }),
    onSuccess: (res) => setRunResult(res),
    onError: (err: Error) => message.error(err.message),
  })

  // ------------------------------------------------------------- 版本历史
  const [historyAgent, setHistoryAgent] = useState<AgentConfig | null>(null)
  const [diff, setDiff] = useState<AgentVersionDiff | null>(null)
  const [diffLoading, setDiffLoading] = useState(false)

  const versionsQuery = useQuery({
    queryKey: ['agent-versions', historyAgent?.agent_id],
    queryFn: () => api.agentVersions(historyAgent!.agent_id),
    enabled: !!historyAgent,
  })

  const restore = useMutation({
    mutationFn: ({ id, version }: { id: string; version: number }) =>
      api.restoreAgentVersion(id, version),
    onSuccess: (row, vars) => {
      message.success(`已回滚至 v${vars.version}（生成 v${row.new_version ?? '?'}）`)
      qc.invalidateQueries({ queryKey: ['agents'] })
      qc.invalidateQueries({ queryKey: ['agent-versions', row.agent_id] })
      if (editing?.agent_id === row.agent_id) {
        setEditing(row)
        openEditor(row)
      }
    },
    onError: (err: Error) => message.error(err.message),
  })

  const showDiff = async (version: number) => {
    if (!historyAgent) return
    setDiffLoading(true)
    try {
      setDiff(await api.agentVersionDiff(historyAgent.agent_id, version))
    } catch (err) {
      message.error((err as Error).message)
    } finally {
      setDiffLoading(false)
    }
  }

  const openEditor = (row?: AgentConfig) => {
    setEditing(row ?? null)
    setRunResult(null)
    form.setFieldsValue(
      row
        ? {
            name: row.name,
            role: row.role,
            profile: row.profile ?? '',
            task: row.task ?? '',
            workflow: (row.workflow ?? []).map((s, i) => ({ ...s, name: stepName(i) })),
            tools: row.tools ?? [],
            output_format_type: row.output_format?.type ?? 'text',
            output_spec: row.output_spec ?? '',
            schema_text: row.output_format?.schema
              ? JSON.stringify(row.output_format.schema, null, 2)
              : JSON.stringify(meta?.default_schema ?? {}, null, 2),
            enabled: row.enabled,
          }
        : {
            name: '',
            role: '',
            profile: '',
            task: '',
            workflow: [{ name: stepName(0), instruction: '' }],
            tools: [],
            output_format_type: 'markdown_table',
            output_spec: '',
            schema_text: JSON.stringify(meta?.default_schema ?? {}, null, 2),
            enabled: true,
          },
    )
    setOpen(true)
  }

  const columns: ColumnsType<AgentConfig> = [
    {
      title: '名称',
      dataIndex: 'name',
      width: 200,
      render: (name: string, row) => (
        <Space>
          <strong>{name}</strong>
          {row.builtin && <Tag color="blue">内置</Tag>}
          {!row.enabled && <Tag>已停用</Tag>}
        </Space>
      ),
    },
    {
      title: '角色定位',
      dataIndex: 'role',
      width: 180,
      ellipsis: true,
      render: (role: string) => role || <Text type="secondary">未填写</Text>,
    },
    {
      title: '任务描述',
      dataIndex: 'task',
      width: 280,
      ellipsis: true,
      render: (task: string) =>
        task ? task : <Text type="secondary">未填写</Text>,
    },
    {
      title: '工作流',
      dataIndex: 'workflow',
      width: 80,
      render: (w: unknown[]) => `${w?.length ?? 0} 步`,
    },
    {
      title: '工具',
      dataIndex: 'tools',
      width: 220,
      render: (tools: string[]) =>
        tools.length ? (
          <Space size={[0, 4]} wrap>
            {tools.map((t) => (
              <Tag key={t}>{t}</Tag>
            ))}
          </Space>
        ) : (
          <Text type="secondary">无</Text>
        ),
    },
    {
      title: '输出格式',
      dataIndex: 'output_format',
      width: 130,
      render: (f: AgentConfig['output_format']) => <Tag>{f?.type ?? 'text'}</Tag>,
    },
    {
      title: '操作',
      width: 220,
      render: (_, row) => (
        <Space>
          <Button size="small" type="link" icon={<HistoryOutlined />} onClick={() => setHistoryAgent(row)}>
            版本
          </Button>
          <Button size="small" type="link" onClick={() => openEditor(row)}>
            编辑
          </Button>
          <Button
            size="small"
            type="link"
            icon={<PlayCircleOutlined />}
            loading={dryRun.isPending}
            onClick={() => dryRun.mutate(row.agent_id)}
          >
            试运行
          </Button>
          <Popconfirm
            title="确认删除该智能体？"
            disabled={row.builtin}
            onConfirm={() => remove.mutate(row.agent_id)}
          >
            <Tooltip title={row.builtin ? '内置智能体不可删除' : ''}>
              <Button size="small" type="link" danger disabled={row.builtin} icon={<DeleteOutlined />}>
                删除
              </Button>
            </Tooltip>
          </Popconfirm>
        </Space>
      ),
    },
  ]

  return (
    <Card
      title="智能体编辑"
      extra={
        <Button type="primary" icon={<PlusOutlined />} onClick={() => openEditor()}>
          新建智能体
        </Button>
      }
    >
      <Alert
        type="info"
        showIcon
        style={{ marginBottom: 16 }}
        message="内置智能体可以编辑角色、工作流、工具与输出格式，但不可删除；自定义智能体可自由增删。"
      />

      <Table<AgentConfig>
        rowKey="agent_id"
        loading={isLoading}
        columns={columns}
        dataSource={agents ?? []}
        pagination={false}
        scroll={{ x: 1320 }}
      />

      <Drawer
        title={historyAgent ? `版本历史：${historyAgent.name}` : '版本历史'}
        width={760}
        open={!!historyAgent}
        onClose={() => setHistoryAgent(null)}
      >
        <Alert
          type="info"
          showIcon
          style={{ marginBottom: 16 }}
          message="每次有效修改生成一个版本；内容未变不会新建。回滚会生成新版本，历史不会丢。"
        />
        <Table<AgentVersion>
          rowKey="version"
          loading={versionsQuery.isLoading}
          pagination={false}
          dataSource={versionsQuery.data ?? []}
          columns={[
            {
              title: '版本',
              dataIndex: 'version',
              width: 80,
              render: (v: number) => <Tag color="blue">v{v}</Tag>,
            },
            { title: '说明', dataIndex: 'note' },
            {
              title: '时间',
              dataIndex: 'created_at',
              width: 180,
              render: (v: string | null) => v?.replace('T', ' ').slice(0, 19) ?? '-',
            },
            {
              title: '操作',
              width: 170,
              render: (_, v) => (
                <Space>
                  <Button size="small" type="link" loading={diffLoading} onClick={() => showDiff(v.version)}>
                    对比当前
                  </Button>
                  <Popconfirm
                    title={`回滚到 v${v.version}？`}
                    description="会用该版本内容生成一个新版本"
                    onConfirm={() =>
                      historyAgent &&
                      restore.mutate({ id: historyAgent.agent_id, version: v.version })
                    }
                  >
                    <Button size="small" type="link" danger>
                      回滚
                    </Button>
                  </Popconfirm>
                </Space>
              ),
            },
          ]}
        />
      </Drawer>

      <Modal
        title={diff ? `差异：${diff.before_label} → ${diff.after_label}` : '差异'}
        open={!!diff}
        onCancel={() => setDiff(null)}
        footer={null}
        width={860}
      >
        {diff && diff.changes.length === 0 ? (
          <Alert type="success" showIcon message="两个版本内容一致，没有差异" />
        ) : (
          <Table
            rowKey={(r: { field: string }) => r.field}
            pagination={false}
            size="small"
            dataSource={diff?.changes ?? []}
            columns={[
              { title: '字段', dataIndex: 'label', width: 110 },
              {
                title: '变更前',
                dataIndex: 'before',
                render: (v: unknown) => <DiffValue value={v} />,
              },
              {
                title: '变更后',
                dataIndex: 'after',
                render: (v: unknown) => <DiffValue value={v} />,
              },
            ]}
          />
        )}
      </Modal>

      <Drawer
        title={editing ? `编辑：${editing.name}` : '新建智能体'}
        width={720}
        open={open}
        onClose={() => setOpen(false)}
        extra={
          <Space>
            <Button
              onClick={() => {
                if (!editing) {
                  message.info('请先保存，再试运行')
                  return
                }
                dryRun.mutate(editing.agent_id)
              }}
              loading={dryRun.isPending}
              icon={<PlayCircleOutlined />}
            >
              试运行
            </Button>
            <Button type="primary" loading={save.isPending} onClick={() => form.submit()}>
              保存
            </Button>
          </Space>
        }
      >
        <Form<FormValues> form={form} layout="vertical" onFinish={(v) => save.mutate(v)}>
          <Form.Item name="name" label="名称" rules={[{ required: true, message: '请输入名称' }]}>
            <Input placeholder="例如：宏观择时分析师" maxLength={80} />
          </Form.Item>

          <Form.Item
            name="role"
            label="角色定位"
            tooltip="一句话说清：它是什么身份、负责什么、边界在哪。不要把画像和输出模板塞进来"
          >
            <TextArea
              rows={2}
              placeholder="你是……，只负责……，不做……"
              maxLength={2000}
              showCount
            />
          </Form.Item>

          <Form.Item
            name="profile"
            label="角色画像"
            tooltip="性格权重、信念、偏好、忌讳。例如「历史规律 0.9（深信历史会重演）」，这些会作为独立段落进入提示词"
          >
            <TextArea
              rows={7}
              placeholder={'例如：\n- 历史规律：0.9（深信历史会重演，主动对比相似日）\n- 细节洞察力：0.85（关注炸板率、封成比）\n- 风险敏感度：0.95（对核按钮、天地板极度敏感）'}
              maxLength={4000}
              showCount
            />
          </Form.Item>

          <Form.Item
            name="task"
            label="任务描述"
            tooltip="这次/每天要完成什么：目标、口径、必须回答的问题。不要写排版要求——那些放输出规范"
          >
            <TextArea
              rows={5}
              placeholder={'例如：\n复盘当日情绪：统计连板梯队与封板率、计算情绪指数并与昨日对比、找出赚钱/亏钱效应所在，给出明日主线与防守锚点。'}
              maxLength={4000}
              showCount
            />
          </Form.Item>

          <Divider orientation="left" plain>
            工作流
          </Divider>
          <Form.List name="workflow">
            {(fields, { add, remove: removeStep }) => (
              <>
                {fields.map((field, index) => (
                  <Space key={field.key} align="start" style={{ display: 'flex', marginBottom: 8 }}>
                    <div style={{ width: 72, lineHeight: '32px', color: 'rgba(0,0,0,0.45)' }}>
                      第 {index + 1} 步
                    </div>
                    <Form.Item name={[field.name, 'name']} hidden>
                      <Input />
                    </Form.Item>
                    <Form.Item name={[field.name, 'instruction']} style={{ marginBottom: 0, width: 500 }}>
                      <TextArea rows={1} placeholder="这一步具体做什么" autoSize={{ minRows: 1, maxRows: 4 }} />
                    </Form.Item>
                    <Button
                      type="text"
                      danger
                      onClick={() => {
                        removeStep(field.name)
                        window.setTimeout(renumberSteps, 0)
                      }}
                    >
                      删除
                    </Button>
                  </Space>
                ))}
                <Button
                  type="dashed"
                  block
                  icon={<PlusOutlined />}
                  onClick={() => {
                    add({ name: stepName(fields.length), instruction: '' })
                    window.setTimeout(renumberSteps, 0)
                  }}
                >
                  添加步骤
                </Button>
              </>
            )}
          </Form.List>

          <Divider orientation="left" plain>
            可用工具
          </Divider>
          <Form.Item
            name="tools"
            tooltip="只能从注册表中选择，避免配置不存在的工具导致运行时失败"
          >
            <Select
              mode="multiple"
              allowClear
              placeholder="选择该智能体可以调用的工具"
              options={(meta?.tools ?? []).map((t) => ({
                value: t.key,
                label: `${t.label}（${t.key}）`,
                title: t.description,
              }))}
            />
          </Form.Item>

          <Divider orientation="left" plain>
            输出格式
          </Divider>
          <Form.Item
            name="output_spec"
            label="输出规范（报告模板）"
            tooltip="要什么结构、哪些段落必须有、用什么格式。留空则只按下面的类型提示"
          >
            <TextArea
              rows={8}
              placeholder={'例如：\n请生成一份《游资情绪复盘报告》：\n1. 核心数据（情绪指数、连板梯队、封板成功率）\n2. 周期定位与历史参考\n3. 明日作战预案（主推/防守 + 观察锚点）'}
              maxLength={8000}
              showCount
            />
          </Form.Item>

          <Form.Item name="output_format_type" label="类型">
            <Select
              options={(meta?.output_formats ?? []).map((f) => ({ value: f.type, label: f.label }))}
            />
          </Form.Item>

          {formatType === 'json_schema' && (
            <Form.Item
              name="schema_text"
              label="JSON Schema"
              tooltip="输出必须通过该 schema 校验，否则试运行会报格式错误"
              rules={[{ required: true, message: '请填写 schema' }]}
            >
              <TextArea rows={10} style={{ fontFamily: 'monospace', fontSize: 12 }} />
            </Form.Item>
          )}

          <Form.Item name="enabled" label="启用" valuePropName="checked">
            <Switch />
          </Form.Item>
        </Form>

        {runResult && (
          <>
            <Divider orientation="left" plain>
              试运行结果
            </Divider>
            {runResult.mock && (
              <Alert
                type="warning"
                showIcon
                style={{ marginBottom: 8 }}
                message="演示模式：未配置 LLM API Key，工具调用是真实执行的，但最终结论为样例输出"
              />
            )}
            {runResult.tool_calls?.length > 0 && (
              <>
                <Text strong>
                  工具调用：{runResult.tool_calls.length} 次 / {runResult.rounds} 轮
                </Text>
                <Table
                  style={{ marginBottom: 12 }}
                  rowKey={(r: { tool: string }, i) => `${r.tool}-${i ?? 0}`}
                  pagination={false}
                  size="small"
                  dataSource={runResult.tool_calls}
                  columns={[
                    { title: '工具', dataIndex: 'tool', width: 160 },
                    {
                      title: '参数',
                      dataIndex: 'args',
                      width: 220,
                      render: (v: unknown) => <DiffValue value={v} />,
                    },
                    {
                      title: '执行结果',
                      dataIndex: 'result',
                      render: (v: unknown) => <DiffValue value={v} />,
                    },
                  ]}
                />
              </>
            )}
            {runResult.format_ok ? (
              <Alert type="success" showIcon message="输出通过格式校验" style={{ marginBottom: 8 }} />
            ) : (
              <Alert
                type="error"
                showIcon
                message="输出未通过 schema 校验"
                description={runResult.error}
                style={{ marginBottom: 8 }}
              />
            )}
            <pre
              style={{
                background: '#fafafa',
                border: '1px solid #f0f0f0',
                borderRadius: 6,
                padding: 12,
                maxHeight: 260,
                overflow: 'auto',
                fontSize: 12,
              }}
            >
              {typeof runResult.output === 'string'
                ? runResult.output
                : JSON.stringify(runResult.output, null, 2)}
            </pre>
            <Text type="secondary">tokens ≈ {runResult.tokens}</Text>
            <div style={{ marginTop: 10 }}>
              {runResult.report_id ? (
                <Link to={`/reports?report=${runResult.report_id}`} target="_blank">
                  <Button size="small" type="primary" icon={<FileTextOutlined />}>
                    在线查看报告
                  </Button>
                </Link>
              ) : (
                <Text type="secondary">本次没有产出，未生成报告</Text>
              )}
            </div>
          </>
        )}
      </Drawer>
    </Card>
  )
}

function DiffValue({ value }: { value: unknown }) {
  if (value === null || value === undefined) return <Text type="secondary">—</Text>
  if (typeof value === 'string') {
    return <span style={{ whiteSpace: 'pre-wrap' }}>{value}</span>
  }
  return (
    <pre
      style={{
        margin: 0,
        fontSize: 12,
        maxHeight: 160,
        overflow: 'auto',
        background: '#fafafa',
        padding: 8,
        borderRadius: 4,
      }}
    >
      {JSON.stringify(value, null, 2)}
    </pre>
  )
}

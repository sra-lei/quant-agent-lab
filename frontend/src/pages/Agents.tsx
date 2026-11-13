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
import { DeleteOutlined, HistoryOutlined, PlusOutlined, PlayCircleOutlined } from '@ant-design/icons'
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
  workflow: Array<{ name: string; instruction: string }>
  tools: string[]
  output_format_type: OutputFormatType
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
        workflow: values.workflow ?? [],
        tools: values.tools ?? [],
        output_format:
          values.output_format_type === 'json_schema'
            ? { type: 'json_schema', schema }
            : { type: values.output_format_type },
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
            workflow: row.workflow ?? [],
            tools: row.tools ?? [],
            output_format_type: row.output_format?.type ?? 'text',
            schema_text: row.output_format?.schema
              ? JSON.stringify(row.output_format.schema, null, 2)
              : JSON.stringify(meta?.default_schema ?? {}, null, 2),
            enabled: row.enabled,
          }
        : {
            name: '',
            role: '',
            workflow: [{ name: '第一步', instruction: '' }],
            tools: [],
            output_format_type: 'markdown_table',
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
      title: '角色描述',
      dataIndex: 'role',
      ellipsis: true,
      render: (role: string) => role || <Text type="secondary">未填写</Text>,
    },
    {
      title: '工作流',
      dataIndex: 'workflow',
      width: 90,
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
            label="角色描述"
            tooltip="这是这个 Agent 的系统人格：它是什么身份、负责什么、边界在哪"
          >
            <TextArea
              rows={3}
              placeholder="你是……，只负责……，不做……"
              maxLength={2000}
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
                    <Form.Item
                      name={[field.name, 'name']}
                      rules={[{ required: true, message: '步骤名必填' }]}
                      style={{ marginBottom: 0, width: 160 }}
                    >
                      <Input placeholder={`第 ${index + 1} 步`} />
                    </Form.Item>
                    <Form.Item name={[field.name, 'instruction']} style={{ marginBottom: 0, width: 420 }}>
                      <TextArea rows={1} placeholder="这一步具体做什么" autoSize={{ minRows: 1, maxRows: 3 }} />
                    </Form.Item>
                    <Button type="text" danger onClick={() => removeStep(field.name)}>
                      删除
                    </Button>
                  </Space>
                ))}
                <Button type="dashed" block icon={<PlusOutlined />} onClick={() => add({ name: '', instruction: '' })}>
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

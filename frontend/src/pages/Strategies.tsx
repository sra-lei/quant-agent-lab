import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Button, Card, Form, Input, InputNumber, Modal, Popconfirm, Select, Space, Switch, Table, Tag } from 'antd'
import { useState } from 'react'
import type { ColumnsType } from 'antd/es/table'
import { api, type Strategy } from '../api/client'

export default function Strategies() {
  const qc = useQueryClient()
  const { data, isLoading } = useQuery({ queryKey: ['strategies'], queryFn: api.strategies })
  const [open, setOpen] = useState(false)
  const [form] = Form.useForm()

  const create = useMutation({
    mutationFn: api.createStrategy,
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['strategies'] })
      setOpen(false)
      form.resetFields()
    },
  })

  const remove = useMutation({
    mutationFn: api.deleteStrategy,
    onSuccess: () => qc.invalidateQueries({ queryKey: ['strategies'] }),
  })

  const columns: ColumnsType<Strategy> = [
    { title: 'ID', dataIndex: 'strategy_id', width: 70 },
    { title: '名称', dataIndex: 'name' },
    { title: '类型', dataIndex: 'kind', width: 120, render: (v: string) => <Tag>{v}</Tag> },
    {
      title: '参数',
      dataIndex: 'params',
      render: (v: Record<string, unknown>) => (
        <code style={{ fontSize: 12 }}>{JSON.stringify(v)}</code>
      ),
    },
    {
      title: '启用',
      dataIndex: 'enabled',
      width: 80,
      render: (v: boolean) => (v ? <Tag color="green">是</Tag> : <Tag>否</Tag>),
    },
    {
      title: '操作',
      width: 100,
      render: (_, row) => (
        <Popconfirm title="确认删除？" onConfirm={() => remove.mutate(row.strategy_id)}>
          <Button danger size="small" type="link">
            删除
          </Button>
        </Popconfirm>
      ),
    },
  ]

  return (
    <Card
      title="策略管理"
      extra={
        <Button type="primary" onClick={() => setOpen(true)}>
          新建策略
        </Button>
      }
    >
      <Table<Strategy>
        rowKey="strategy_id"
        loading={isLoading}
        columns={columns}
        dataSource={data ?? []}
        pagination={false}
      />

      <Modal
        title="新建策略"
        open={open}
        onCancel={() => setOpen(false)}
        onOk={() => form.submit()}
        confirmLoading={create.isPending}
      >
        <Form
          form={form}
          layout="vertical"
          initialValues={{ kind: 'value', enabled: true }}
          onFinish={(values) => create.mutate(values)}
        >
          <Form.Item name="name" label="名称" rules={[{ required: true }]}>
            <Input placeholder="例如：低估值高质量" />
          </Form.Item>
          <Form.Item name="kind" label="类型">
            <Select
              options={[
                { value: 'value', label: '价值（基本面）' },
                { value: 'momentum', label: '游资（情绪/量价）' },
              ]}
            />
          </Form.Item>
          <Space size="large">
            <Form.Item name="enabled" label="启用" valuePropName="checked">
              <Switch />
            </Form.Item>
            <Form.Item label="PE 上限（示例参数）">
              <InputNumber min={0} placeholder="25" />
            </Form.Item>
          </Space>
        </Form>
      </Modal>
    </Card>
  )
}

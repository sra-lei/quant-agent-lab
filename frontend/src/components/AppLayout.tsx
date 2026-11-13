import { Layout, Menu, Typography } from 'antd'
import {
  DashboardOutlined,
  ExperimentOutlined,
  FileSearchOutlined,
  FundOutlined,
  ProfileOutlined,
  RobotOutlined,
} from '@ant-design/icons'
import { Link, Outlet, useLocation } from 'react-router-dom'

const { Header, Sider, Content, Footer } = Layout

const items = [
  { key: '/', icon: <DashboardOutlined />, label: <Link to="/">总览</Link> },
  { key: '/signals', icon: <FundOutlined />, label: <Link to="/signals">信号</Link> },
  { key: '/strategies', icon: <ExperimentOutlined />, label: <Link to="/strategies">策略</Link> },
  { key: '/agents', icon: <RobotOutlined />, label: <Link to="/agents">智能体</Link> },
  { key: '/runs', icon: <ProfileOutlined />, label: <Link to="/runs">运行记录</Link> },
  { key: '/reviews', icon: <FileSearchOutlined />, label: <Link to="/reviews">复盘</Link> },
]

export default function AppLayout() {
  const { pathname } = useLocation()

  return (
    <Layout style={{ minHeight: '100vh' }}>
      <Sider breakpoint="lg" collapsedWidth="0" theme="dark">
        <div style={{ color: '#fff', padding: 16, fontWeight: 600 }}>
          quant-agent-lab
        </div>
        <Menu theme="dark" mode="inline" selectedKeys={[pathname]} items={items} />
      </Sider>
      <Layout>
        <Header style={{ background: '#fff', paddingInline: 24 }}>
          <Typography.Text type="secondary">
            多智能体 A 股投研 · 研究用途，不构成投资建议
          </Typography.Text>
        </Header>
        <Content style={{ margin: 24 }}>
          <Outlet />
        </Content>
        <Footer style={{ textAlign: 'center', color: '#999' }}>
          MIT License · 数据源与结论仅供研究
        </Footer>
      </Layout>
    </Layout>
  )
}

import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Layout, Button, Card, Space, Typography, message } from 'antd'
import { LogoutOutlined, UserOutlined, FileTextOutlined } from '@ant-design/icons'
import { useAuth } from '../hooks/useAuth'
import { authService } from '../services/auth'

const { Header, Content } = Layout
const { Title, Text } = Typography

const Dashboard = () => {
  const navigate = useNavigate()
  const { user, logout, isAuthenticated, loading } = useAuth()
  const [userInfo, setUserInfo] = useState(null)

  useEffect(() => {
    // 等待认证状态加载完成
    if (loading) {
      return
    }

    // 如果未认证，重定向到登录页
    if (!isAuthenticated) {
      navigate('/login')
      return
    }

    // 获取用户详细信息
    authService.getCurrentUser()
      .then(data => setUserInfo(data))
      .catch((error) => {
        console.error('获取用户信息失败:', error)
        message.error('获取用户信息失败')
        logout()
        navigate('/login')
      })
  }, [navigate, isAuthenticated, loading, logout])

  const handleLogout = () => {
    logout()
    message.success('已退出登录')
    navigate('/login')
  }

  return (
    <Layout style={{ minHeight: '100vh' }}>
      <Header style={{ 
        background: '#fff', 
        padding: '0 24px',
        display: 'flex',
        justifyContent: 'space-between',
        alignItems: 'center',
        boxShadow: '0 2px 8px rgba(0,0,0,0.1)'
      }}>
        <Title level={3} style={{ margin: 0 }}>合同智能解读系统</Title>
        <Space>
          <Text>{userInfo?.username || user?.username}</Text>
          <Button 
            type="primary" 
            icon={<LogoutOutlined />}
            onClick={handleLogout}
          >
            退出登录
          </Button>
        </Space>
      </Header>
      <Content style={{ padding: '24px', background: '#f0f2f5' }}>
        <Card>
          <Space direction="vertical" size="large" style={{ width: '100%' }}>
            <Title level={4}>
              <UserOutlined /> 欢迎，{userInfo?.username || user?.username}！
            </Title>
            <Card>
              <Title level={5}>用户信息</Title>
              <Space direction="vertical">
                <Text><strong>用户名：</strong>{userInfo?.username}</Text>
                <Text><strong>邮箱：</strong>{userInfo?.email}</Text>
                <Text><strong>注册时间：</strong>{userInfo?.created_at ? new Date(userInfo.created_at).toLocaleString('zh-CN') : '-'}</Text>
              </Space>
            </Card>
            <Card>
              <Title level={5}>功能导航</Title>
              <Space direction="vertical" size="middle" style={{ width: '100%' }}>
                <Button 
                  type="primary" 
                  size="large"
                  icon={<FileTextOutlined />}
                  onClick={() => navigate('/contracts')}
                  block
                >
                  合同管理
                </Button>
                <Text type="secondary">后续功能开发中：</Text>
                <ul>
                  <li>智能问答</li>
                  <li>历史对话记录</li>
                  <li>实体关系抽取</li>
                </ul>
              </Space>
            </Card>
          </Space>
        </Card>
      </Content>
    </Layout>
  )
}

export default Dashboard


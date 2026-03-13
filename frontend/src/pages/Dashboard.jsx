import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Layout, Button, Card, Space, Typography, message, Row, Col, Statistic } from 'antd'
import { LogoutOutlined, UserOutlined, SettingOutlined } from '@ant-design/icons'
import { useAuth } from '../hooks/useAuth'
import { authService } from '../services/auth'

const { Header, Content } = Layout
const { Title, Text } = Typography

const Dashboard = () => {
  const navigate = useNavigate()
  const { user, logout, isAuthenticated, loading } = useAuth()
  const [userInfo, setUserInfo] = useState(null)
  const [stats, setStats] = useState({
    contract_count: 0,
    compare_count: 0,
    conversation_count: 0,
    clause_complexity_count: 0,
  })

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

    // 获取用户统计
    authService.getStats()
      .then(data => setStats(data))
      .catch(err => console.error('获取统计数据失败:', err))
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
        <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
          <img
            src="/images/APP.png"
            alt="logo"
            style={{ height: 36, verticalAlign: 'middle' }}
          />
          <Title level={3} style={{ margin: 0 }}>合同智能解读系统</Title>
        </div>
        <Space>
          <Text>{userInfo?.username || user?.username}</Text>
          <Button
            icon={<SettingOutlined />}
            onClick={() => navigate('/profile')}
          >
            个人中心
          </Button>
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
            <Row gutter={[24, 24]} style={{ marginTop: 8 }}>
              <Col xs={24} md={12}>
                <Card
                  hoverable
                  onClick={() => navigate('/contracts')}
                  style={{
                    minHeight: 220,
                    cursor: 'pointer',
                    overflow: 'hidden',
                    background: '#69b1ff',
                  }}
                  bodyStyle={{ padding: 0, height: '100%' }}
                >
                  <div style={{ padding: 24, textAlign: 'center' }}>
                    <img
                      src="/images/contract_manage.png"
                      alt="合同管理"
                      style={{
                        width: '100%',
                        maxWidth: 200,
                        height: 140,
                        objectFit: 'contain',
                        marginBottom: 16,
                      }}
                    />
                    <Title level={4} style={{ margin: 0, color: '#fff' }}>合同管理</Title>
                    <Text style={{ fontSize: 13, color: 'rgba(255,255,255,0.8)' }}>上传、解析与智能问答</Text>
                  </div>
                </Card>
              </Col>
              <Col xs={24} md={12}>
                <Card
                  hoverable
                  onClick={() => navigate('/compare')}
                  style={{
                    minHeight: 220,
                    cursor: 'pointer',
                    overflow: 'hidden',
                    background: '#69b1ff',
                  }}
                  bodyStyle={{ padding: 0, height: '100%' }}
                >
                  <div style={{ padding: 24, textAlign: 'center' }}>
                    <img
                      src="/images/contract_compare.png"
                      alt="合同对比"
                      style={{
                        width: '100%',
                        maxWidth: 200,
                        height: 140,
                        objectFit: 'contain',
                        marginBottom: 16,
                      }}
                    />
                    <Title level={4} style={{ margin: 0, color: '#fff' }}>合同对比</Title>
                    <Text style={{ fontSize: 13, color: 'rgba(255,255,255,0.8)' }}>多份合同差异对比</Text>
                  </div>
                </Card>
              </Col>
            </Row>
          </Space>
        </Card>
        <Row gutter={[16, 16]} style={{ marginTop: 24 }}>
          <Col xs={24} sm={12} md={6}>
            <Card>
              <Statistic
                title="已上传合同"
                value={stats.contract_count}
                valueStyle={{ color: '#1677cc' }}
              />
            </Card>
          </Col>
          <Col xs={24} sm={12} md={6}>
            <Card>
              <Statistic
                title="已对比合同"
                value={stats.compare_count}
                valueStyle={{ color: '#52c41a' }}
              />
            </Card>
          </Col>
          <Col xs={24} sm={12} md={6}>
            <Card>
              <Statistic
                title="问答会话"
                value={stats.conversation_count}
                valueStyle={{ color: '#722ed1' }}
              />
            </Card>
          </Col>
          <Col xs={24} sm={12} md={6}>
            <Card>
              <Statistic
                title="已解析长难句"
                value={stats.clause_complexity_count}
                valueStyle={{ color: '#eb2f96' }}
              />
            </Card>
          </Col>
        </Row>
      </Content>
    </Layout>
  )
}

export default Dashboard


import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import {
  Layout,
  Card,
  Typography,
  Statistic,
  Row,
  Col,
  Input,
  Button,
  message,
  Tooltip,
} from 'antd'
import { EditOutlined, CheckOutlined, CloseOutlined } from '@ant-design/icons'
import { useAuth } from '../hooks/useAuth'
import { authService } from '../services/auth'

const { Header, Content } = Layout
const { Title, Text } = Typography

const PersonalCenter = () => {
  const navigate = useNavigate()
  const { user, isAuthenticated, loading, logout } = useAuth()
  const [stats, setStats] = useState({
    contract_count: 0,
    compare_count: 0,
    conversation_count: 0,
    clause_complexity_count: 0,
  })
  const [userInfo, setUserInfo] = useState(null)
  const [submitting, setSubmitting] = useState(false)

  // 行内编辑状态
  const [editingField, setEditingField] = useState(null)
  const [editValue, setEditValue] = useState('')
  // 密码修改：新密码、确认密码
  const [passwordEdit, setPasswordEdit] = useState({ newPassword: '', confirmPassword: '' })

  useEffect(() => {
    if (loading) return
    if (!isAuthenticated) {
      navigate('/login')
      return
    }

    // 获取用户统计
    authService
      .getStats()
      .then((data) => {
        setStats(data)
      })
      .catch((err) => {
        console.error('获取统计数据失败:', err)
      })

    // 获取当前用户信息
    authService
      .getCurrentUser()
      .then((data) => {
        setUserInfo(data)
      })
      .catch((err) => {
        console.error('获取用户信息失败:', err)
        message.error('获取用户信息失败，请重新登录')
        logout()
        navigate('/login')
      })
  }, [loading, isAuthenticated, navigate, logout])

  // 开始编辑
  const startEdit = (field, currentValue) => {
    setEditingField(field)
    setEditValue(currentValue || '')
  }

  // 取消编辑
  const cancelEdit = () => {
    setEditingField(null)
    setEditValue('')
  }

  // 保存编辑
  const saveEdit = async (field) => {
    if (!editValue.trim()) {
      message.error('值不能为空')
      return
    }

    try {
      setSubmitting(true)
      const payload = {
        username: userInfo.username,
        email: userInfo.email,
      }

      // 根据当前编辑的字段更新
      if (field === 'username') {
        payload.username = editValue.trim()
      } else if (field === 'email') {
        payload.email = editValue.trim()
      }

      const updated = await authService.updateProfile(payload)
      setUserInfo(updated)
      message.success('信息已更新')
      setEditingField(null)
      setEditValue('')
    } catch (err) {
      console.error('更新失败:', err)
      const detail =
        err?.response?.data?.detail ||
        err?.message ||
        '更新失败，请稍后重试'
      message.error(detail)
    } finally {
      setSubmitting(false)
    }
  }

  // 保存密码修改
  const savePassword = async () => {
    const { newPassword, confirmPassword } = passwordEdit
    if (!newPassword || newPassword.length < 8) {
      message.error('密码至少 8 位')
      return
    }
    if (!/[A-Za-z]/.test(newPassword) || !/\d/.test(newPassword)) {
      message.error('密码必须同时包含字母和数字')
      return
    }
    if (newPassword !== confirmPassword) {
      message.error('两次输入的密码不一致')
      return
    }

    try {
      setSubmitting(true)
      await authService.updateProfile({
        username: userInfo.username,
        email: userInfo.email,
        password: newPassword,
      })
      message.success('密码已更新')
      setEditingField(null)
      setPasswordEdit({ newPassword: '', confirmPassword: '' })
    } catch (err) {
      console.error('更新密码失败:', err)
      const detail =
        err?.response?.data?.detail ||
        err?.message ||
        '更新密码失败，请稍后重试'
      message.error(detail)
    } finally {
      setSubmitting(false)
    }
  }

  const cancelPasswordEdit = () => {
    setEditingField(null)
    setPasswordEdit({ newPassword: '', confirmPassword: '' })
  }

  const fieldFontSize = 16
  const labelStyle = { width: 100, marginRight: 16, fontSize: fieldFontSize }
  const valueStyle = { flex: 1, fontSize: fieldFontSize }

  // 渲染可编辑字段
  const renderEditableField = (field, label, value) => {
    const isEditing = editingField === field

    return (
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          marginBottom: 16,
          padding: '8px 12px',
          borderRadius: 6,
          transition: 'background-color 0.3s',
        }}
        onMouseEnter={(e) => (e.currentTarget.style.backgroundColor = '#f5f5f5')}
        onMouseLeave={(e) => (e.currentTarget.style.backgroundColor = 'transparent')}
      >
        <Text strong style={labelStyle}>
          {label}：
        </Text>
        {isEditing ? (
          <>
            <Input
              value={editValue}
              onChange={(e) => setEditValue(e.target.value)}
              onPressEnter={() => saveEdit(field)}
              style={{ width: 200, marginRight: 8, fontSize: fieldFontSize }}
              autoFocus
            />
            <Button
              type="text"
              size="small"
              icon={<CheckOutlined />}
              onClick={() => saveEdit(field)}
              loading={submitting}
              style={{ color: '#52c41a' }}
            />
            <Button
              type="text"
              size="small"
              icon={<CloseOutlined />}
              onClick={cancelEdit}
              style={{ color: '#ff4d4f' }}
            />
          </>
        ) : (
          <>
            <Text style={valueStyle}>{value || '-'}</Text>
            <Tooltip title="编辑">
              <Button
                type="text"
                size="small"
                icon={<EditOutlined />}
                onClick={() => startEdit(field, value)}
                style={{ opacity: 0.6 }}
              />
            </Tooltip>
          </>
        )}
      </div>
    )
  }

  return (
    <Layout style={{ minHeight: '100vh' }}>
      <Header
        style={{
          background: '#fff',
          padding: '0 24px',
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          boxShadow: '0 2px 8px rgba(0,0,0,0.1)',
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
          <img
            src="/images/APP.png"
            alt="logo"
            style={{ height: 36, verticalAlign: 'middle' }}
          />
          <Title level={3} style={{ margin: 0 }}>
            个人中心
          </Title>
        </div>
        <Button type="link" onClick={() => navigate('/dashboard')}>
          返回首页
        </Button>
      </Header>
      <Content style={{ padding: 24, background: '#f0f2f5' }}>
        <Row gutter={[16, 16]}>
          {/* 统计卡片 */}
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

        <Card style={{ marginTop: 16 }}>
          <Title level={4} style={{ fontSize: 18 }}>基本信息</Title>
          <div style={{ marginTop: 16 }}>
            {renderEditableField('username', '用户名', userInfo?.username || user?.username)}
            {renderEditableField('email', '邮箱', userInfo?.email)}
            <div
              style={{
                display: 'flex',
                alignItems: 'center',
                marginBottom: 16,
                padding: '8px 12px',
                borderRadius: 6,
                transition: 'background-color 0.3s',
              }}
              onMouseEnter={(e) => (e.currentTarget.style.backgroundColor = '#f5f5f5')}
              onMouseLeave={(e) => (e.currentTarget.style.backgroundColor = 'transparent')}
            >
              <Text strong style={labelStyle}>
                密码：
              </Text>
              {editingField === 'password' ? (
                <>
                  <div style={{ display: 'flex', flexDirection: 'column', gap: 8, flex: 1, maxWidth: 320 }}>
                    <Input.Password
                      placeholder="新密码（至少8位，含字母和数字）"
                      value={passwordEdit.newPassword}
                      onChange={(e) => setPasswordEdit((p) => ({ ...p, newPassword: e.target.value }))}
                      style={{ fontSize: fieldFontSize }}
                    />
                    <Input.Password
                      placeholder="确认新密码"
                      value={passwordEdit.confirmPassword}
                      onChange={(e) => setPasswordEdit((p) => ({ ...p, confirmPassword: e.target.value }))}
                      style={{ fontSize: fieldFontSize }}
                    />
                  </div>
                  <Button
                    type="text"
                    size="small"
                    icon={<CheckOutlined />}
                    onClick={savePassword}
                    loading={submitting}
                    style={{ color: '#52c41a', marginLeft: 8 }}
                  />
                  <Button
                    type="text"
                    size="small"
                    icon={<CloseOutlined />}
                    onClick={cancelPasswordEdit}
                    style={{ color: '#ff4d4f' }}
                  />
                </>
              ) : (
                <>
                  <Text style={valueStyle}>********</Text>
                  <Tooltip title="修改密码">
                    <Button
                      type="text"
                      size="small"
                      icon={<EditOutlined />}
                      onClick={() => setEditingField('password')}
                      style={{ opacity: 0.6 }}
                    />
                  </Tooltip>
                </>
              )}
            </div>
          </div>
        </Card>
      </Content>
    </Layout>
  )
}

export default PersonalCenter

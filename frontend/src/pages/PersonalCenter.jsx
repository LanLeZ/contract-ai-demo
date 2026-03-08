import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import {
  Layout,
  Card,
  Typography,
  Space,
  Form,
  Input,
  Button,
  message,
} from 'antd'
import { useAuth } from '../hooks/useAuth'
import { authService } from '../services/auth'
import { contractService } from '../services/contracts'

const { Header, Content } = Layout
const { Title, Text } = Typography

const PersonalCenter = () => {
  const navigate = useNavigate()
  const { user, isAuthenticated, loading, logout } = useAuth()
  const [userInfo, setUserInfo] = useState(null)
  const [contractCount, setContractCount] = useState(0)
  const [form] = Form.useForm()
  const [submitting, setSubmitting] = useState(false)

  useEffect(() => {
    if (loading) return
    if (!isAuthenticated) {
      navigate('/login')
      return
    }

    // 获取当前用户信息
    authService
      .getCurrentUser()
      .then((data) => {
        setUserInfo(data)
        form.setFieldsValue({
          username: data.username,
          email: data.email,
        })
      })
      .catch((err) => {
        console.error('获取用户信息失败:', err)
        message.error('获取用户信息失败，请重新登录')
        logout()
        navigate('/login')
      })

    // 获取当前用户已上传合同数量（后端接口已按 user_id 过滤）
    contractService
      .getContracts()
      .then((contracts) => {
        // 双重保险：再按 user_id 过滤一次
        const currentUserId = user?.id
        const filtered = currentUserId
          ? contracts.filter((c) => c.user_id === currentUserId)
          : contracts
        setContractCount(filtered.length)
      })
      .catch((err) => {
        console.error('获取合同列表失败:', err)
      })
  }, [loading, isAuthenticated, navigate, logout, form, user])

  const handleSubmit = async (values) => {
    try {
      setSubmitting(true)

      const payload = {
        username: values.username,
        email: values.email,
        password: values.password || undefined,
      }

      const updated = await authService.updateProfile(payload)
      message.success('信息已更新')
      setUserInfo(updated)
      form.setFieldsValue({
        username: updated.username,
        email: updated.email,
        password: undefined,
        confirmPassword: undefined,
      })
    } catch (err) {
      console.error('更新个人信息失败:', err)
      // 后端若返回 detail 字段，优先展示
      const detail =
        err?.response?.data?.detail ||
        err?.message ||
        '更新个人信息失败，请稍后重试'
      message.error(detail)
    } finally {
      setSubmitting(false)
    }
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
        <Title level={3} style={{ margin: 0 }}>
          个人中心
        </Title>
        <Button type="link" onClick={() => navigate('/dashboard')}>
          返回首页
        </Button>
      </Header>
      <Content style={{ padding: '24px', background: '#f0f2f5' }}>
        <Space direction="vertical" size="large" style={{ width: '100%' }}>
          <Card>
            <Title level={4}>基本信息</Title>
            <Space direction="vertical">
              <Text>
                <strong>用户名：</strong>
                {userInfo?.username || user?.username}
              </Text>
              <Text>
                <strong>邮箱：</strong>
                {userInfo?.email}
              </Text>
              <Text>
                <strong>密码：</strong>********
              </Text>
              <Text>
                <strong>已上传合同数：</strong>
                {contractCount}
              </Text>
            </Space>
          </Card>

          <Card>
            <Title level={4}>修改信息</Title>
            <Form form={form} layout="vertical" onFinish={handleSubmit}>
              <Form.Item
                label="用户名"
                name="username"
                rules={[
                  { required: true, message: '请输入用户名' },
                  { max: 50, message: '用户名过长' },
                ]}
              >
                <Input placeholder="请输入用户名" />
              </Form.Item>

              <Form.Item
                label="邮箱"
                name="email"
                rules={[
                  { required: true, message: '请输入邮箱' },
                  { type: 'email', message: '邮箱格式不正确' },
                ]}
              >
                <Input placeholder="请输入邮箱" />
              </Form.Item>

              <Form.Item
                label="新密码（可选）"
                name="password"
                rules={[
                  {
                    validator: (_, value) => {
                      if (!value) return Promise.resolve()
                      if (value.length < 8) {
                        return Promise.reject(new Error('密码至少 8 位'))
                      }
                      if (
                        !/[A-Za-z]/.test(value) ||
                        !/\d/.test(value)
                      ) {
                        return Promise.reject(
                          new Error('密码必须包含字母和数字'),
                        )
                      }
                      return Promise.resolve()
                    },
                  },
                ]}
              >
                <Input.Password placeholder="如需修改密码，请输入新密码" />
              </Form.Item>

              <Form.Item
                label="确认新密码"
                name="confirmPassword"
                dependencies={['password']}
                rules={[
                  ({ getFieldValue }) => ({
                    validator(_, value) {
                      const pwd = getFieldValue('password')
                      if (!pwd && !value) return Promise.resolve()
                      if (!value) {
                        return Promise.reject(
                          new Error('请再次输入新密码'),
                        )
                      }
                      if (pwd !== value) {
                        return Promise.reject(
                          new Error('两次输入的密码不一致'),
                        )
                      }
                      return Promise.resolve()
                    },
                  }),
                ]}
              >
                <Input.Password placeholder="请再次输入新密码" />
              </Form.Item>

              <Form.Item>
                <Button
                  type="primary"
                  htmlType="submit"
                  loading={submitting}
                >
                  保存修改
                </Button>
              </Form.Item>
            </Form>
          </Card>
        </Space>
      </Content>
    </Layout>
  )
}

export default PersonalCenter




























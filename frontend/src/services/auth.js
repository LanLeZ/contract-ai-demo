import api from './api'

export const authService = {
  // 注册
  async register(username, email, password) {
    const response = await api.post('/api/auth/register', {
      username,
      email,
      password,
    })
    return response.data
  },

  // 登录
  async login(username, password) {
    const formData = new FormData()
    formData.append('username', username)
    formData.append('password', password)
    
    const response = await api.post('/api/auth/login', formData, {
      headers: {
        'Content-Type': 'multipart/form-data',
      },
    })
    return response.data
  },

  // 获取当前用户信息
  async getCurrentUser() {
    const response = await api.get('/api/auth/me')
    return response.data
  },
}



import { useContext } from 'react'
import { AuthContext } from '../contexts/AuthContext'

// 将 useAuth hook 定义在这里，避免 Fast Refresh 警告
// AuthContext.jsx 只导出组件，hook 在这里定义
export const useAuth = () => {
  const context = useContext(AuthContext)
  if (!context) {
    throw new Error('useAuth must be used within AuthProvider')
  }
  return context
}


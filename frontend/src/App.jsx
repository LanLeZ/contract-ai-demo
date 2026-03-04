import { Routes, Route, Navigate } from 'react-router-dom'
import Login from './pages/Login'
import Register from './pages/Register'
import Dashboard from './pages/Dashboard'
import Contracts from './pages/Contracts'
import PersonalCenter from './pages/PersonalCenter'
import { useAuth } from './hooks/useAuth'
import './App.css'

function App() {
  const { isAuthenticated, loading } = useAuth()

  // 等待认证状态加载完成
  if (loading) {
    return <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', height: '100vh' }}>加载中...</div>
  }

  return (
    <Routes>
      <Route path="/login" element={<Login />} />
      <Route path="/register" element={<Register />} />
      <Route 
        path="/dashboard" 
        element={isAuthenticated ? <Dashboard /> : <Navigate to="/login" />} 
      />
      <Route 
        path="/contracts" 
        element={isAuthenticated ? <Contracts /> : <Navigate to="/login" />} 
      />
      <Route
        path="/profile"
        element={isAuthenticated ? <PersonalCenter /> : <Navigate to="/login" />}
      />
      <Route path="/" element={<Navigate to="/login" />} />
    </Routes>
  )
}

export default App


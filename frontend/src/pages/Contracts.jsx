import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { 
  Layout, 
  Upload, 
  Table, 
  Button, 
  message, 
  Space, 
  Typography, 
  Card,
  Input,
  Tag,
  Popconfirm,
  Row,
  Col,
  Descriptions,
  Spin
} from 'antd'
import { 
  DeleteOutlined, 
  FileOutlined,
  InboxOutlined,
  LogoutOutlined,
  HomeOutlined,
  ArrowLeftOutlined
} from '@ant-design/icons'
import { useAuth } from '../hooks/useAuth'
import { contractService } from '../services/contracts'

const { Header, Content } = Layout
const { Title, Text } = Typography
const { Dragger } = Upload

const Contracts = () => {
  const navigate = useNavigate()
  const { user, logout, isAuthenticated, loading } = useAuth()
  const [contracts, setContracts] = useState([])
  const [loadingContracts, setLoadingContracts] = useState(false)
  const [uploading, setUploading] = useState(false)
  const [searchText, setSearchText] = useState('')
  const [selectedContract, setSelectedContract] = useState(null)
  const [contractDetail, setContractDetail] = useState(null)
  const [loadingDetail, setLoadingDetail] = useState(false)

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

    // 加载合同列表
    loadContracts()
  }, [navigate, isAuthenticated, loading])

  const loadContracts = async () => {
    setLoadingContracts(true)
    try {
      const data = await contractService.getContracts()
      setContracts(data)
    } catch (error) {
      console.error('获取合同列表失败:', error)
      message.error('获取合同列表失败')
    } finally {
      setLoadingContracts(false)
    }
  }

  const loadContractDetail = async (contractId) => {
    setLoadingDetail(true)
    try {
      const data = await contractService.getContract(contractId)
      setContractDetail(data)
    } catch (error) {
      console.error('获取合同详情失败:', error)
      message.error('获取合同详情失败')
      setContractDetail(null)
    } finally {
      setLoadingDetail(false)
    }
  }

  const handleContractClick = (record) => {
    setSelectedContract(record.id)
    loadContractDetail(record.id)
  }

  const handleBackToUpload = () => {
    setSelectedContract(null)
    setContractDetail(null)
  }

  const handleUpload = async (file) => {
    // 验证文件类型
    const allowedTypes = ['.pdf', '.docx', '.md', '.markdown']
    const fileExt = '.' + file.name.split('.').pop().toLowerCase()
    
    if (!allowedTypes.includes(fileExt)) {
      message.error(`不支持的文件类型。支持的类型: ${allowedTypes.join(', ')}`)
      return false
    }

    // 验证文件大小（50MB）
    const maxSize = 50 * 1024 * 1024
    if (file.size > maxSize) {
      message.error('文件大小超过限制（最大50MB）')
      return false
    }

    setUploading(true)
    try {
      await contractService.uploadContract(file)
      message.success('文件上传成功！')
      // 重新加载合同列表
      await loadContracts()
    } catch (error) {
      console.error('上传失败:', error)
      message.error(error.response?.data?.detail || '文件上传失败')
    } finally {
      setUploading(false)
    }

    // 阻止默认上传行为
    return false
  }

  const handleDelete = async (contractId, e) => {
    e?.stopPropagation() // 阻止事件冒泡，避免触发行点击
    try {
      await contractService.deleteContract(contractId)
      message.success('合同删除成功')
      // 如果删除的是当前选中的合同，返回上传区域
      if (selectedContract === contractId) {
        handleBackToUpload()
      }
      // 重新加载合同列表
      await loadContracts()
    } catch (error) {
      console.error('删除失败:', error)
      message.error(error.response?.data?.detail || '删除失败')
    }
  }

  const handleLogout = () => {
    logout()
    message.success('已退出登录')
    navigate('/login')
  }

  // 过滤合同列表
  const filteredContracts = contracts.filter(contract => {
    if (!searchText) return true
    return contract.filename.toLowerCase().includes(searchText.toLowerCase())
  })

  // 表格列定义
  const columns = [
    {
      title: '文件名',
      dataIndex: 'filename',
      key: 'filename',
      render: (text) => (
        <Space>
          <FileOutlined />
          <span>{text}</span>
        </Space>
      ),
    },
    {
      title: '文件类型',
      dataIndex: 'filename',
      key: 'fileType',
      width: 120,
      render: (filename) => {
        const ext = filename.split('.').pop().toLowerCase()
        const typeMap = {
          pdf: { color: 'red', text: 'PDF' },
          docx: { color: 'blue', text: 'DOCX' },
          md: { color: 'green', text: 'Markdown' },
          markdown: { color: 'green', text: 'Markdown' },
        }
        const type = typeMap[ext] || { color: 'default', text: ext.toUpperCase() }
        return <Tag color={type.color}>{type.text}</Tag>
      },
    },
    {
      title: '上传时间',
      dataIndex: 'upload_time',
      key: 'upload_time',
      width: 180,
      render: (time) => time ? new Date(time).toLocaleString('zh-CN') : '-',
      sorter: (a, b) => new Date(a.upload_time) - new Date(b.upload_time),
    },
    {
      title: '操作',
      key: 'action',
      width: 120,
      render: (_, record) => (
        <Popconfirm
          title="确定要删除这个合同吗？"
          description="删除后将无法恢复，包括文件和相关向量数据。"
          onConfirm={(e) => handleDelete(record.id, e)}
          onCancel={(e) => e?.stopPropagation()}
          okText="确定"
          cancelText="取消"
          okButtonProps={{ danger: true }}
        >
          <Button 
            type="link" 
            danger 
            icon={<DeleteOutlined />}
            onClick={(e) => e.stopPropagation()}
          >
            删除
          </Button>
        </Popconfirm>
      ),
    },
  ]

  // 渲染右侧内容区域
  const renderRightContent = () => {
    if (selectedContract && contractDetail) {
      // 显示合同详情
      return (
        <Card
          title={
            <Space>
              <Button
                type="text"
                icon={<ArrowLeftOutlined />}
                onClick={handleBackToUpload}
                style={{ marginLeft: -16 }}
              >
                返回
              </Button>
              <span>合同详情</span>
            </Space>
          }
        >
          <Spin spinning={loadingDetail}>
            <Descriptions bordered column={1}>
              <Descriptions.Item label="文件名">
                <Space>
                  <FileOutlined />
                  <Text>{contractDetail.filename}</Text>
                </Space>
              </Descriptions.Item>
              <Descriptions.Item label="文件类型">
                {(() => {
                  const ext = contractDetail.filename?.split('.').pop().toLowerCase()
                  const typeMap = {
                    pdf: { color: 'red', text: 'PDF' },
                    docx: { color: 'blue', text: 'DOCX' },
                    md: { color: 'green', text: 'Markdown' },
                    markdown: { color: 'green', text: 'Markdown' },
                  }
                  const type = typeMap[ext] || { color: 'default', text: ext?.toUpperCase() || '-' }
                  return <Tag color={type.color}>{type.text}</Tag>
                })()}
              </Descriptions.Item>
              <Descriptions.Item label="文件ID">
                <Text code>{contractDetail.id}</Text>
              </Descriptions.Item>
              <Descriptions.Item label="上传时间">
                {contractDetail.upload_time 
                  ? new Date(contractDetail.upload_time).toLocaleString('zh-CN')
                  : '-'}
              </Descriptions.Item>
              {contractDetail.file_size && (
                <Descriptions.Item label="文件大小">
                  {(contractDetail.file_size / 1024 / 1024).toFixed(2)} MB
                </Descriptions.Item>
              )}
              {contractDetail.chunk_count !== undefined && (
                <Descriptions.Item label="分块数量">
                  {contractDetail.chunk_count}
                </Descriptions.Item>
              )}
            </Descriptions>
          </Spin>
        </Card>
      )
    }

    // 默认显示上传区域
    return (
      <Card title="上传合同文件">
        <Dragger
          name="file"
          multiple={false}
          accept=".pdf,.docx,.md,.markdown"
          beforeUpload={handleUpload}
          showUploadList={false}
          disabled={uploading}
        >
          <p className="ant-upload-drag-icon">
            <InboxOutlined />
          </p>
          <p className="ant-upload-text">
            {uploading ? '正在上传...' : '点击或拖拽文件到此区域上传'}
          </p>
          <p className="ant-upload-hint">
            支持 PDF、DOCX、Markdown 格式，最大 50MB
          </p>
        </Dragger>
      </Card>
    )
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
          <Button 
            type="text"
            icon={<HomeOutlined />}
            onClick={() => navigate('/dashboard')}
          >
            返回首页
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
        <Row gutter={24} style={{ height: 'calc(100vh - 112px)' }}>
          {/* 左侧：合同列表 */}
          <Col span={10}>
            <Card 
              title={
                <Space>
                  <span>合同列表</span>
                  <Tag>{filteredContracts.length}</Tag>
                </Space>
              }
              extra={
                <Input.Search
                  placeholder="搜索文件名"
                  allowClear
                  style={{ width: 200 }}
                  value={searchText}
                  onChange={(e) => setSearchText(e.target.value)}
                />
              }
              style={{ height: '100%', display: 'flex', flexDirection: 'column' }}
              bodyStyle={{ flex: 1, overflow: 'hidden', display: 'flex', flexDirection: 'column' }}
            >
              <Table
                columns={columns}
                dataSource={filteredContracts}
                rowKey="id"
                loading={loadingContracts}
                pagination={{
                  pageSize: 10,
                  showSizeChanger: true,
                  showTotal: (total) => `共 ${total} 条记录`,
                }}
                locale={{
                  emptyText: '暂无合同，请上传文件'
                }}
                onRow={(record) => ({
                  onClick: () => handleContractClick(record),
                  style: {
                    cursor: 'pointer',
                    backgroundColor: selectedContract === record.id ? '#e6f7ff' : 'transparent',
                  },
                })}
                scroll={{ y: 'calc(100vh - 280px)' }}
              />
            </Card>
          </Col>

          {/* 右侧：上传区域或合同详情 */}
          <Col span={14}>
            {renderRightContent()}
          </Col>
        </Row>
      </Content>
    </Layout>
  )
}

export default Contracts


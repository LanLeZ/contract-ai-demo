import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { 
  Layout, 
  Upload, 
  Table, 
  Button, 
  message, 
  Modal,
  Space, 
  Typography, 
  Card,
  Input,
  Tag,
  Popconfirm,
  Row,
  Col,
  Spin,
  Tabs,
  Alert
} from 'antd'
import ReactECharts from 'echarts-for-react'
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
  const [pendingImages, setPendingImages] = useState([])
  const [searchText, setSearchText] = useState('')
  const [selectedContract, setSelectedContract] = useState(null)
  const [contractDetail, setContractDetail] = useState(null)
  const [loadingDetail, setLoadingDetail] = useState(false)
  const [activeTab, setActiveTab] = useState('detail')
  // 智能问答相关状态
  const [qaMessages, setQaMessages] = useState([])
  const [qaInput, setQaInput] = useState('')
  const [qaLoading, setQaLoading] = useState(false)
  // 当前会话 ID，由后端生成，用于将多轮问答绑定到同一会话
  const [qaSessionId, setQaSessionId] = useState(null)
  // 会话列表 & 历史加载
  const [qaSessions, setQaSessions] = useState([])
  const [qaSessionsLoading, setQaSessionsLoading] = useState(false)
  const [qaActiveSessionId, setQaActiveSessionId] = useState(null)
  const [qaHistoryLoading, setQaHistoryLoading] = useState(false)
  // 知识图谱相关状态
  const [kgLoading, setKgLoading] = useState(false)
  const [kgTriples, setKgTriples] = useState([])
  const [kgError, setKgError] = useState(null)

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

  const loadSessions = async (contractId) => {
    if (!contractId) return
    setQaSessionsLoading(true)
    try {
      const data = await contractService.listSessions(contractId)
      setQaSessions(data.sessions || [])
    } catch (error) {
      console.error('获取会话列表失败:', error)
      message.error(error.response?.data?.detail || '获取会话列表失败')
    } finally {
      setQaSessionsLoading(false)
    }
  }

  const handleContractClick = (record) => {
    setSelectedContract(record.id)
    loadContractDetail(record.id)
    // 切换合同时，重置当前智能问答会话
    setQaMessages([])
    setQaSessionId(null)
    setQaActiveSessionId(null)
    setQaInput('')
    setQaSessions([])
    // 加载该合同下的历史会话
    loadSessions(record.id)
  }

  const handleBackToUpload = () => {
    setSelectedContract(null)
    setContractDetail(null)
    // 返回上传区域时，同步重置当前会话
    setQaMessages([])
    setQaSessionId(null)
    setQaActiveSessionId(null)
    setQaSessions([])
    // 重置知识图谱
    setKgTriples([])
    setKgError(null)
    setQaInput('')
  }

  const getFileExt = (fileName) => {
    if (!fileName) return ''
    return '.' + fileName.split('.').pop().toLowerCase()
  }

  const isImageFile = (file) => {
    const ext = getFileExt(file?.name)
    return ['.png', '.jpg', '.jpeg'].includes(ext)
  }

  const submitImagesAsOneContract = async (files) => {
    setUploading(true)
    try {
      const displayName = `图片合同_${Date.now()}.png`
      const contract = await contractService.uploadContractImages(files, displayName)
      message.success('图片合同上传成功！正在抽取知识图谱...')
      // 上传成功后自动触发知识图谱抽取（异步，无需阻塞）
      try {
        await contractService.extractContractKG(contract.id)
      } catch (e) {
        console.error('知识图谱抽取失败（图片合同）:', e)
      }
      setPendingImages([])
      await loadContracts()
    } catch (error) {
      console.error('图片合同上传失败:', error)
      message.error(error.response?.data?.detail || '图片合同上传失败')
    } finally {
      setUploading(false)
    }
  }

  const handleUpload = async (file) => {
    // 验证文件类型
    const allowedTypes = ['.pdf', '.docx', '.txt', '.png', '.jpg', '.jpeg']
    const fileExt = getFileExt(file?.name)
    
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

    // 如果正在收集图片页，禁止混传其他文件
    const isImage = isImageFile(file)
    if (pendingImages.length > 0 && !isImage) {
      message.warning('你正在添加图片页，请先“完成上传”或“清空”，再上传其他类型文件。')
      return false
    }

    // 图片：进入“收集页”模式
    if (isImage) {
      if (pendingImages.length === 0) {
        Modal.confirm({
          title: '检测到图片',
          content: '这是多页合同吗？如果是请继续添加图片，最后点击“完成上传”。',
          okText: '继续添加',
          cancelText: '直接上传这一张',
          onOk: () => {
            setPendingImages((prev) => [...prev, file])
          },
          onCancel: async () => {
            await submitImagesAsOneContract([file])
          },
        })
      } else {
        setPendingImages((prev) => [...prev, file])
        message.success(`已添加第 ${pendingImages.length + 1} 张图片`)
      }
      return false
    }

    setUploading(true)
    try {
      const contract = await contractService.uploadContract(file)
      message.success('文件上传成功！正在抽取知识图谱...')
      // 上传成功后自动触发知识图谱抽取（异步）
      try {
        await contractService.extractContractKG(contract.id)
      } catch (e) {
        console.error('知识图谱抽取失败:', e)
      }
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

  // 智能问答 Tab：接入后端合同问答接口
  const handleSendQuestion = async () => {
    if (!qaInput.trim()) {
      message.warning('请输入问题')
      return
    }

    if (!contractDetail?.id) {
      message.error('请先选择一个合同')
      return
    }

    const question = qaInput.trim()

    // 先把用户问题追加到对话中
    setQaMessages((prev) => [
      ...prev,
      { role: 'user', content: question },
    ])

    setQaLoading(true)
    setQaInput('')

    try {
      const data = await contractService.contractQA(contractDetail.id, {
        question,
        // 如果已有会话 ID，则继续该会话；否则由后端生成新会话 ID
        session_id: qaSessionId,
      })

      // 如果后端返回了 session_id，则更新当前会话 ID
      if (data.session_id) {
        setQaSessionId(data.session_id)
        setQaActiveSessionId((prev) => prev || data.session_id)
      }

      // 将后端回答加入对话
      setQaMessages((prev) => [
        ...prev,
        { role: 'assistant', content: data.answer || '（后端未返回 answer 字段）' },
      ])

      // 问答成功后刷新会话列表
      loadSessions(contractDetail.id)
    } catch (error) {
      console.error('智能问答失败:', error)
      message.error(error.response?.data?.detail || '智能问答失败')
    } finally {
      setQaLoading(false)
    }
  }

  // 加载某个会话的完整历史
  const handleLoadSessionHistory = async (sessionId) => {
    if (!contractDetail?.id || !sessionId) return

    setQaHistoryLoading(true)
    setQaActiveSessionId(sessionId)
    setQaSessionId(sessionId)

    try {
      const data = await contractService.getSessionHistory(contractDetail.id, sessionId)
      const messages = (data.messages || []).map((m) => ({
        role: m.role,
        content: m.content,
        created_at: m.created_at,
      }))
      setQaMessages(messages)
      // 历史记录加载时，不强制刷新 citations（可留空或后续扩展为“最近一轮的引用”）
    } catch (error) {
      console.error('获取会话历史失败:', error)
      message.error(error.response?.data?.detail || '获取会话历史失败')
    } finally {
      setQaHistoryLoading(false)
    }
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
          txt: { color: 'orange', text: 'TXT' },
          png: { color: 'purple', text: 'PNG' },
          jpg: { color: 'purple', text: 'JPG' },
          jpeg: { color: 'purple', text: 'JPEG' },
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
      render: (time) => time ? new Date(time).toLocaleDateString('zh-CN') : '-',
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
  const buildKGGraphData = (triples) => {
    // 将三元组转换为节点和边（力导向图数据结构）
    // 使用 label + type 统一生成节点 ID，保证同一实体在图中只出现一个节点
    const nodeMap = new Map()
    const links = []

    const makeNodeId = (label, type) => {
      const safeLabel = String(label ?? '').trim()
      const safeType = String(type ?? '').trim()
      return `${safeLabel}::${safeType}`
    }

    triples.forEach((t) => {
      const headId = makeNodeId(t.head, t.head_type)
      const tailId = makeNodeId(t.tail, t.tail_type)

      if (!nodeMap.has(headId)) {
        nodeMap.set(headId, {
          id: headId,
          label: t.head,
          type: t.head_type || '实体',
        })
      }
      if (!nodeMap.has(tailId)) {
        nodeMap.set(tailId, {
          id: tailId,
          label: t.tail,
          type: t.tail_type || '实体',
        })
      }

      links.push({
        source: headId,
        target: tailId,
        label: t.relation,
      })
    })

    return {
      nodes: Array.from(nodeMap.values()),
      links,
    }
  }

  const renderKGForceGraph = () => {
    if (kgLoading) {
      return (
        <div style={{ textAlign: 'center', padding: 24 }}>
          <Spin />
          <div style={{ marginTop: 8 }}>正在加载知识图谱...</div>
        </div>
      )
    }

    if (kgError) {
      return (
        <Alert
          type="error"
          message="知识图谱加载失败"
          description={kgError}
          showIcon
          style={{ marginBottom: 16 }}
        />
      )
    }

    if (!kgTriples || kgTriples.length === 0) {
      return (
        <div style={{ textAlign: 'center', padding: 24, color: '#999' }}>
          暂无可用的知识图谱三元组。
        </div>
      )
    }

    const { nodes, links } = buildKGGraphData(kgTriples)

    // 使用 echarts 的 graph 力导向布局
    const categories = Array.from(
      new Set(nodes.map((n) => n.type || '实体'))
    ).map((name) => ({ name }))

    const option = {
      tooltip: {
        trigger: 'item',
        formatter: (params) => {
          if (params.dataType === 'node') {
            const node = params.data
            return `
              <div>
                <div><strong>实体：</strong>${node.label || node.name}</div>
                <div><strong>类型：</strong>${node.type || '实体'}</div>
              </div>
            `
          }
          if (params.dataType === 'edge') {
            return `
              <div>
                <div><strong>关系：</strong>${params.data.label || params.data.name}</div>
                <div><strong>源：</strong>${params.data.source}</div>
                <div><strong>目标：</strong>${params.data.target}</div>
              </div>
            `
          }
          return ''
        },
      },
      legend: [
        {
          data: categories.map((c) => c.name),
          top: 10,
        },
      ],
      series: [
        {
          type: 'graph',
          layout: 'force',
          roam: true,
          draggable: true,
          focusNodeAdjacency: true,
          edgeSymbol: ['none', 'arrow'],
          edgeSymbolSize: 8,
          categories,
          data: nodes.map((n) => ({
            id: n.id,
            name: n.label,
            value: n.label,
            label: n.label,
            type: n.type,
            category: n.type || '实体',
            symbolSize: 40,
          })),
          links: links.map((l) => ({
            source: l.source,
            target: l.target,
            name: l.label,
            label: l.label,
            value: l.label,
          })),
          label: {
            show: true,
            position: 'right',
            formatter: (p) => {
              const text = p.data?.name || ''
              return text.length > 8 ? `${text.slice(0, 8)}…` : text
            },
          },
          edgeLabel: {
            show: true,
            formatter: (p) => p.data?.name || '',
            fontSize: 10,
          },
          lineStyle: {
            color: '#ccc',
            width: 1.2,
            curveness: 0.2,
          },
          force: {
            repulsion: 260,
            edgeLength: [80, 160],
            gravity: 0.1,
          },
        },
      ],
    }

    return (
      <div
        style={{
          border: '1px solid #f0f0f0',
          borderRadius: 4,
          padding: 12,
          background: '#fff',
        }}
      >
        <ReactECharts
          option={option}
          notMerge={true}
          lazyUpdate={true}
          style={{ height: 420, width: '100%' }}
        />
      </div>
    )
  }

  const loadKGForContract = async (contractId) => {
    if (!contractId) return
    setKgLoading(true)
    setKgError(null)
    try {
      // 先尝试直接获取现有三元组
      const triples = await contractService.getContractKG(contractId)
      if (!triples || triples.length === 0) {
        // 如果没有，则触发抽取
        const res = await contractService.extractContractKG(contractId)
        setKgTriples(res.triples || [])
      } else {
        setKgTriples(triples)
      }
    } catch (error) {
      console.error('加载知识图谱失败:', error)
      setKgError(error.response?.data?.detail || '加载知识图谱失败')
    } finally {
      setKgLoading(false)
    }
  }

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
              <span>{contractDetail.filename}</span>
            </Space>
          }
        >
          <Spin spinning={loadingDetail}>
            <Tabs
              activeKey={activeTab}
              onChange={(key) => {
                setActiveTab(key)
                if (key === 'kg' && contractDetail?.id) {
                  // 切换到知识图谱 Tab 时，懒加载抽取/加载
                  loadKGForContract(contractDetail.id)
                }
              }}
              items={[
                {
                  key: 'detail',
                  label: '合同详情',
                  children: (
                    <div>
                      {/* 文件内容预览 - 只显示合同文本内容 */}
                      <Card title="文件内容" style={{ marginTop: 16 }}>
                        <div
                          style={{
                            maxHeight: '500px',
                            overflow: 'auto',
                            padding: '16px',
                            background: '#fafafa',
                            border: '1px solid #d9d9d9',
                            borderRadius: '4px',
                            whiteSpace: 'pre-wrap',
                            wordBreak: 'break-word',
                            fontSize: '14px',
                            lineHeight: '1.8',
                          }}
                        >
                          {contractDetail.file_content || '暂无内容'}
                        </div>
                      </Card>
                    </div>
                  ),
                },
                {
                  key: 'qa',
                  label: '智能问答',
                  children: (
                    <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
                      <Row gutter={16}>
                        {/* 左侧：会话列表 */}
                        <Col span={8}>
                          <Card
                            title="历史会话"
                            extra={
                              <Button
                                type="link"
                                size="small"
                                onClick={() => loadSessions(contractDetail.id)}
                                loading={qaSessionsLoading}
                              >
                                刷新
                              </Button>
                            }
                            bodyStyle={{ padding: 8, maxHeight: 360, overflowY: 'auto' }}
                          >
                            <Button
                              type="dashed"
                              block
                              style={{ marginBottom: 8 }}
                              onClick={() => {
                                // 新建会话：清空对话内容 & 当前会话 ID
                                setQaMessages([])
                                setQaSessionId(null)
                                setQaActiveSessionId(null)
                              }}
                            >
                              新建会话
                            </Button>
                            {qaSessionsLoading ? (
                              <div style={{ textAlign: 'center', padding: 16 }}>
                                <Spin size="small" />
                              </div>
                            ) : qaSessions.length === 0 ? (
                              <Text type="secondary">暂无历史会话</Text>
                            ) : (
                              <Space direction="vertical" style={{ width: '100%' }}>
                                {qaSessions.map((s) => (
                                  <Card
                                    key={s.session_id}
                                    size="small"
                                    hoverable
                                    onClick={() => handleLoadSessionHistory(s.session_id)}
                                    style={{
                                      borderColor:
                                        qaActiveSessionId === s.session_id ? '#1890ff' : undefined,
                                    }}
                                  >
                                    <Space direction="vertical" size={4}>
                                      <Text strong ellipsis style={{ maxWidth: '100%' }}>
                                        {s.last_question || '（无问题内容）'}
                                      </Text>
                                      <Text type="secondary" style={{ fontSize: 12 }}>
                                        {s.last_time
                                          ? new Date(s.last_time).toLocaleString('zh-CN')
                                          : ''}
                                      </Text>
                                      <Text type="secondary" style={{ fontSize: 12 }}>
                                        {`轮数：${s.message_count}`}
                                      </Text>
                                    </Space>
                                  </Card>
                                ))}
                              </Space>
                            )}
                          </Card>
                        </Col>

                        {/* 右侧：当前会话对话区 */}
                        <Col span={16}>
                          <Card
                            title={
                              qaActiveSessionId
                                ? `当前会话（ID: ${qaActiveSessionId.slice(0, 8)}...）`
                                : '当前会话'
                            }
                            bodyStyle={{
                              padding: 16,
                              display: 'flex',
                              flexDirection: 'column',
                              gap: 8,
                              maxHeight: 360,
                              overflowY: 'auto',
                              background: '#fafafa',
                            }}
                          >
                            {(qaHistoryLoading || qaLoading) && (
                              <div style={{ textAlign: 'center', marginBottom: 8 }}>
                                <Spin size="small" />
                              </div>
                            )}
                            {qaMessages.length === 0 ? (
                              <div style={{ textAlign: 'center', color: '#999' }}>
                                暂无对话，输入问题开始咨询本合同相关内容。
                              </div>
                            ) : (
                              qaMessages.map((msg, index) => (
                                <div
                                  key={index}
                                  style={{
                                    display: 'flex',
                                    justifyContent: msg.role === 'user' ? 'flex-end' : 'flex-start',
                                  }}
                                >
                                  <div
                                    style={{
                                      maxWidth: '80%',
                                      padding: '8px 12px',
                                      borderRadius: 8,
                                      background:
                                        msg.role === 'user' ? '#e6f7ff' : '#f6ffed',
                                      border:
                                        msg.role === 'user'
                                          ? '1px solid #91d5ff'
                                          : '1px solid #b7eb8f',
                                      whiteSpace: 'pre-wrap',
                                      wordBreak: 'break-word',
                                      fontSize: 14,
                                      lineHeight: 1.7,
                                    }}
                                  >
                                    {msg.content}
                                  </div>
                                </div>
                              ))
                            )}
                          </Card>
                        </Col>
                      </Row>

                      {/* 输入区 */}
                      <Card bodyStyle={{ padding: 16 }}>
                        <Space direction="vertical" style={{ width: '100%' }}>
                          <Input.TextArea
                            rows={3}
                            placeholder="请输入你想咨询的内容，例如：这份合同的违约责任有哪些？"
                            value={qaInput}
                            onChange={(e) => setQaInput(e.target.value)}
                            disabled={qaLoading}
                          />
                          <div
                            style={{
                              display: 'flex',
                              justifyContent: 'space-between',
                              alignItems: 'center',
                            }}
                          >
                            <Text type="secondary">
                              当前问答会自动归入上方选中的会话；如未选中，则自动创建新会话。
                            </Text>
                            <Button
                              type="primary"
                              onClick={handleSendQuestion}
                              loading={qaLoading}
                            >
                              发送
                            </Button>
                          </div>
                        </Space>
                      </Card>
                    </div>
                  ),
                },
                {
                  key: 'kg',
                  label: '知识图谱',
                  children: (
                    <div style={{ marginTop: 8 }}>
                      {renderKGForceGraph()}
                    </div>
                  ),
                },
              ]}
            />
          </Spin>
        </Card>
      )
    }

    // 默认显示上传区域
    return (
      <Card title={pendingImages.length > 0 ? "已添加图片页" : "上传合同文件"}>
        {pendingImages.length > 0 && (
          <div style={{ marginBottom: 12 }}>
            <Space wrap>
              <Tag color="blue">已添加 {pendingImages.length} 张</Tag>
              <Button
                type="primary"
                onClick={() => submitImagesAsOneContract(pendingImages)}
                disabled={uploading || pendingImages.length === 0}
              >
                完成上传
              </Button>
              <Button
                onClick={() => setPendingImages([])}
                disabled={uploading}
              >
                清空
              </Button>
            </Space>
            <div style={{ marginTop: 8, color: '#666' }}>
              {pendingImages.slice(0, 5).map((f, idx) => (
                <div key={`${f.name}_${idx}`}>{idx + 1}. {f.name}</div>
              ))}
              {pendingImages.length > 5 && (
                <div>... 还有 {pendingImages.length - 5} 张</div>
              )}
            </div>
          </div>
        )}

        <Dragger
          name="file"
          multiple={true}
          accept=".pdf,.docx,.md,.markdown,.txt,.png,.jpg,.jpeg"
          beforeUpload={handleUpload}
          showUploadList={false}
          disabled={uploading}
        >
          <p className="ant-upload-drag-icon">
            <InboxOutlined />
          </p>
          <p className="ant-upload-text">
            {uploading ? '正在上传...' : pendingImages.length > 0 ? '继续拖拽图片页到此处追加' : '点击或拖拽文件到此区域上传'}
          </p>
          <p className="ant-upload-hint">
            支持 PDF、DOCX、Markdown、TXT、PNG/JPG/JPEG 格式；图片可多张合并上传；最大 50MB
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
                  showSizeChanger: false,
                  showTotal: false,
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


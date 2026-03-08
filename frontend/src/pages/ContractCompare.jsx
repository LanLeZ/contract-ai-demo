import { useEffect, useState, useMemo } from 'react'
import { useNavigate } from 'react-router-dom'
import {
  Layout,
  Button,
  Card,
  Space,
  Typography,
  Row,
  Col,
  Upload,
  Tag,
  Tooltip,
  Spin,
  message,
  List,
  Divider,
} from 'antd'
import {
  LogoutOutlined,
  HomeOutlined,
  HistoryOutlined,
  DoubleRightOutlined,
  FileAddOutlined,
  FileTextOutlined,
  ReloadOutlined,
  CompressOutlined,
} from '@ant-design/icons'
import { useAuth } from '../hooks/useAuth'
import { contractService } from '../services/contracts'
import { compareService } from '../services/compare'

const { Header, Content } = Layout
const { Title, Text } = Typography
const { Dragger } = Upload

const MAX_FILE_SIZE = 50 * 1024 * 1024 // 50MB
const ALLOWED_FILE_EXTS = ['.pdf', '.docx', '.txt', '.md', '.markdown']

// 工具方法：获取文件扩展名
const getFileExt = (fileName) => {
  if (!fileName) return ''
  return '.' + fileName.split('.').pop().toLowerCase()
}

// 根据差异类型和重要性返回高亮颜色
const getDiffColors = (changeType, importance = 'normal') => {
  const level = importance === 'vital' ? 'vital' : 'normal'
  const map = {
    add: {
      normal: { backgroundColor: '#f6ffed', borderColor: '#b7eb8f' },
      vital: { backgroundColor: '#d9f7be', borderColor: '#52c41a' },
    },
    delete: {
      normal: { backgroundColor: '#fff1f0', borderColor: '#ffa39e' },
      vital: { backgroundColor: '#ffccc7', borderColor: '#ff4d4f' },
    },
    alter: {
      normal: { backgroundColor: '#fffbe6', borderColor: '#ffe58f' },
      vital: { backgroundColor: '#ffe7ba', borderColor: '#fa8c16' },
    },
  }
  return map[changeType]?.[level] || { backgroundColor: '#fafafa', borderColor: '#d9d9d9' }
}

// 统一映射 change_type 到中文文案
const changeTypeLabel = {
  add: '新增条款',
  delete: '删除条款',
  alter: '修改条款',
}

const importanceLabel = {
  normal: '一般',
  vital: '重要',
}

const ContractCompare = () => {
  const navigate = useNavigate()
  const { user, logout, isAuthenticated, loading } = useAuth()

  // 历史列表
  const [historyItems, setHistoryItems] = useState([])
  const [historyLoading, setHistoryLoading] = useState(false)
  const [historyCollapsed, setHistoryCollapsed] = useState(false)
  const [selectedHistoryId, setSelectedHistoryId] = useState(null)

  // 左右合同
  const [leftContract, setLeftContract] = useState(null)
  const [rightContract, setRightContract] = useState(null)
  const [leftUploading, setLeftUploading] = useState(false)
  const [rightUploading, setRightUploading] = useState(false)
  const [leftLoadingDetail, setLeftLoadingDetail] = useState(false)
  const [rightLoadingDetail, setRightLoadingDetail] = useState(false)

  // 对比结果
  const [compareDetail, setCompareDetail] = useState(null)
  const [compareLoading, setCompareLoading] = useState(false)

  useEffect(() => {
    if (loading) return
    if (!isAuthenticated) {
      navigate('/login')
      return
    }
    loadHistory()
  }, [loading, isAuthenticated, navigate])

  const loadHistory = async () => {
    setHistoryLoading(true)
    try {
      const data = await compareService.listHistory()
      setHistoryItems(data.items || [])
    } catch (error) {
      const detail = error.response?.data?.detail
      console.error('获取对比历史失败 detail:', detail, 'raw error:', error)
      let msg = '获取对比历史失败'
      // FastAPI/Pydantic 422 通常是一个包含 {type, loc, msg, input, url} 的数组
      if (Array.isArray(detail)) {
        msg = detail.map((d) => d.msg || JSON.stringify(d)).join('; ')
      } else if (typeof detail === 'string') {
        msg = detail
      } else if (detail) {
        msg = JSON.stringify(detail)
      }
      message.error(msg)
    } finally {
      setHistoryLoading(false)
    }
  }

  const handleLogout = () => {
    logout()
    message.success('已退出登录')
    navigate('/login')
  }

  const validateFile = (file) => {
    const ext = getFileExt(file?.name)
    if (!ALLOWED_FILE_EXTS.includes(ext)) {
      message.error(`不支持的文件类型。支持: ${ALLOWED_FILE_EXTS.join(', ')}`)
      return false
    }
    if (file.size > MAX_FILE_SIZE) {
      message.error('文件大小超过限制（最大 50MB）')
      return false
    }
    return true
  }

  const uploadAndPreview = async (file, side) => {
    if (!validateFile(file)) {
      return Upload.LIST_IGNORE
    }

    if (side === 'left') {
      setLeftUploading(true)
    } else {
      setRightUploading(true)
    }

    try {
      const contract = await contractService.uploadContract(file)
      // 上传返回的结构中包含 id，再去拉一次详情以便拿到 file_content
      if (contract?.id) {
        if (side === 'left') {
          setLeftLoadingDetail(true)
        } else {
          setRightLoadingDetail(true)
        }
        const detail = await contractService.getContract(contract.id)
        if (side === 'left') {
          setLeftContract(detail)
        } else {
          setRightContract(detail)
        }
        message.success(`${side === 'left' ? '左侧' : '右侧'}合同上传成功`)
      } else {
        message.error('上传成功但未返回合同 ID')
      }
    } catch (error) {
      console.error('上传合同失败:', error)
      message.error(error.response?.data?.detail || '上传合同失败')
    } finally {
      if (side === 'left') {
        setLeftUploading(false)
        setLeftLoadingDetail(false)
      } else {
        setRightUploading(false)
        setRightLoadingDetail(false)
      }
    }

    // 阻止默认上传行为
    return Upload.LIST_IGNORE
  }

  const canStartCompare = useMemo(
    () => !!leftContract?.id && !!rightContract?.id && !compareLoading,
    [leftContract, rightContract, compareLoading],
  )

  const handleStartCompare = async () => {
    if (!leftContract?.id || !rightContract?.id) {
      message.warning('请先分别上传或选择左右两份合同')
      return
    }

    setCompareLoading(true)
    try {
      const detail = await compareService.createCompare(leftContract.id, rightContract.id)
      setCompareDetail(detail)
      setSelectedHistoryId(detail.id)
      message.success('合同对比完成')
      // 对比完成后刷新历史列表
      loadHistory()
    } catch (error) {
      console.error('合同对比失败:', error)
      message.error(error.response?.data?.detail || '合同对比失败')
    } finally {
      setCompareLoading(false)
    }
  }

  const loadCompareFromHistory = async (item) => {
    if (!item?.id) return
    setSelectedHistoryId(item.id)
    setCompareLoading(true)
    setLeftLoadingDetail(true)
    setRightLoadingDetail(true)
    try {
      const detail = await compareService.getCompareDetail(item.id)
      setCompareDetail(detail)

      // 同步加载左右合同详情用于预览
      if (detail.left_contract_id) {
        try {
          const left = await contractService.getContract(detail.left_contract_id)
          setLeftContract(left)
        } catch (e) {
          console.error('加载左侧合同详情失败:', e)
        }
      }
      if (detail.right_contract_id) {
        try {
          const right = await contractService.getContract(detail.right_contract_id)
          setRightContract(right)
        } catch (e) {
          console.error('加载右侧合同详情失败:', e)
        }
      }
    } catch (error) {
      console.error('获取对比详情失败:', error)
      message.error(error.response?.data?.detail || '获取对比详情失败')
    } finally {
      setCompareLoading(false)
      setLeftLoadingDetail(false)
      setRightLoadingDetail(false)
    }
  }

  const handleClearSide = (side) => {
    if (side === 'left') {
      setLeftContract(null)
    } else {
      setRightContract(null)
    }
  }

  const currentResult = compareDetail?.result || null

  const renderContractPanel = (side, contract, uploading, loadingDetail) => {
    const isLeft = side === 'left'
    const title = isLeft ? '左侧合同' : '右侧合同'
    const color = isLeft ? 'blue' : 'green'

    return (
      <Card
        title={
          <Space>
            <Tag color={color}>{title}</Tag>
            {contract?.filename && (
              <Space size={4}>
                <FileTextOutlined />
                <Text ellipsis style={{ maxWidth: 220 }}>
                  {contract.filename}
                </Text>
              </Space>
            )}
          </Space>
        }
        extra={
          <Space>
            {contract?.id && (
              <Tooltip title="清空本侧合同">
                <Button size="small" onClick={() => handleClearSide(side)}>
                  清空
                </Button>
              </Tooltip>
            )}
          </Space>
        }
        style={{ height: '100%', display: 'flex', flexDirection: 'column' }}
        bodyStyle={{ flex: 1, display: 'flex', flexDirection: 'column', gap: 8 }}
      >
        <Spin spinning={uploading || loadingDetail}>
          {!contract ? (
            <Dragger
              multiple={false}
              accept={ALLOWED_FILE_EXTS.join(',')}
              beforeUpload={(file) => uploadAndPreview(file, side)}
              showUploadList={false}
              disabled={uploading}
            >
              <p className="ant-upload-drag-icon">
                <FileAddOutlined />
              </p>
              <p className="ant-upload-text">
                {uploading ? '正在上传...' : `点击或拖拽文件到此区域，作为${title}`}
              </p>
              <p className="ant-upload-hint">
                支持 PDF、DOCX、Markdown、TXT 格式；最大 50MB
              </p>
            </Dragger>
          ) : (
            <>
              <div
                style={{
                  maxHeight: 260,
                  overflow: 'auto',
                  padding: 12,
                  background: '#fafafa',
                  border: '1px solid #d9d9d9',
                  borderRadius: 4,
                  whiteSpace: 'pre-wrap',
                  wordBreak: 'break-word',
                  fontSize: 13,
                  lineHeight: 1.7,
                }}
              >
                {contract.file_content || '暂无内容'}
              </div>
              <Text type="secondary" style={{ fontSize: 12 }}>
                仅预览文本内容，完整差异请查看下方对比结果
              </Text>
            </>
          )}
        </Spin>
      </Card>
    )
  }

  const renderSummary = () => {
    if (!currentResult) {
      return (
        <Text type="secondary">
          暂无对比结果，请先上传左右两份合同并点击「开始对比」，或从左侧历史记录中选择一条。
        </Text>
      )
    }

    const s = currentResult.summary || {}
    return (
      <Space size="large" wrap>
        <span>
          <Tag color="blue">仅左侧存在</Tag>
          <Text>{s.only_in_left_count ?? 0} 条</Text>
        </span>
        <span>
          <Tag color="green">仅右侧存在</Tag>
          <Text>{s.only_in_right_count ?? 0} 条</Text>
        </span>
        <span>
          <Tag color="gold">两侧均存在</Tag>
          <Text>{s.in_both_count ?? 0} 条</Text>
        </span>
        <span>
          <Tag color="orange">内容有差异</Tag>
          <Text>{s.changed_in_both_count ?? 0} 条</Text>
        </span>
      </Space>
    )
  }

  const renderDiffList = () => {
    if (!currentResult) return null

    const diffs = currentResult.all_differences || []
    if (!diffs.length) {
      return (
        <div style={{ textAlign: 'center', padding: 24, color: '#999' }}>
          未检测到条款级差异。
        </div>
      )
    }

    return (
      <List
        size="small"
        dataSource={diffs}
        rowKey={(item, index) => `${item.clause_marker || 'clause'}_${index}`}
        style={{ maxHeight: 'calc(100vh - 360px)', overflow: 'auto' }}
        renderItem={(item) => {
          const importance = item.importance || 'normal'
          const colors = getDiffColors(item.change_type, importance)
          const marker = item.clause_marker || '未标注编号'

          const tooltipContent = (
            <div style={{ maxWidth: 360 }}>
              <div>
                <strong>条款编号：</strong>
                {marker}
              </div>
              <div>
                <strong>变更类型：</strong>
                {changeTypeLabel[item.change_type] || item.change_type}
              </div>
              <div>
                <strong>重要性：</strong>
                {importanceLabel[importance] || importance}
              </div>
              <div style={{ marginTop: 4 }}>
                <strong>风险说明：</strong>
                {item.explanation || '暂无详细说明'}
              </div>
            </div>
          )

          return (
            <List.Item>
              <Row gutter={12} style={{ width: '100%' }}>
                <Col span={24}>
                  <Space size="small">
                    <Tag color="default">{marker}</Tag>
                    <Tag
                      color={
                        item.change_type === 'add'
                          ? 'green'
                          : item.change_type === 'delete'
                          ? 'red'
                          : 'orange'
                      }
                    >
                      {changeTypeLabel[item.change_type] || item.change_type}
                    </Tag>
                    <Tag color={importance === 'vital' ? 'red' : 'blue'}>
                      重要性：{importanceLabel[importance] || importance}
                    </Tag>
                  </Space>
                </Col>
                <Col span={12}>
                  {(item.change_type === 'delete' || item.change_type === 'alter') && (
                    <Tooltip title={tooltipContent} placement="topLeft">
                      <div
                        style={{
                          marginTop: 8,
                          padding: 8,
                          borderRadius: 4,
                          border: `1px solid ${colors.borderColor}`,
                          backgroundColor: colors.backgroundColor,
                          minHeight: 60,
                          whiteSpace: 'pre-wrap',
                          wordBreak: 'break-word',
                          fontSize: 13,
                        }}
                      >
                        <Text type="secondary" style={{ fontSize: 12 }}>
                          左侧合同
                        </Text>
                        <div>{item.left_text || '（该条款在左侧合同中不存在）'}</div>
                      </div>
                    </Tooltip>
                  )}
                </Col>
                <Col span={12}>
                  {(item.change_type === 'add' || item.change_type === 'alter') && (
                    <Tooltip title={tooltipContent} placement="topLeft">
                      <div
                        style={{
                          marginTop: 8,
                          padding: 8,
                          borderRadius: 4,
                          border: `1px solid ${colors.borderColor}`,
                          backgroundColor: colors.backgroundColor,
                          minHeight: 60,
                          whiteSpace: 'pre-wrap',
                          wordBreak: 'break-word',
                          fontSize: 13,
                        }}
                      >
                        <Text type="secondary" style={{ fontSize: 12 }}>
                          右侧合同
                        </Text>
                        <div>{item.right_text || '（该条款在右侧合同中不存在）'}</div>
                      </div>
                    </Tooltip>
                  )}
                </Col>
              </Row>
            </List.Item>
          )
        }}
      />
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
        <Title level={3} style={{ margin: 0 }}>
          合同智能解读系统 - 合同对比
        </Title>
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
        <Row gutter={16} style={{ height: 'calc(100vh - 112px)' }}>
          {/* 左侧：对比历史列表，可折叠 */}
          <Col
            span={historyCollapsed ? 1 : 6}
            style={{
              transition: 'all 0.2s',
              display: 'flex',
              flexDirection: 'column',
            }}
          >
            <Card
              size="small"
              title={
                <Space>
                  <HistoryOutlined />
                  <span>对比历史</span>
                </Space>
              }
              extra={
                <Space size={4}>
                  <Tooltip title={historyCollapsed ? '展开历史' : '收起历史'}>
                    <Button
                      size="small"
                      icon={historyCollapsed ? <DoubleRightOutlined /> : <CompressOutlined />}
                      onClick={() => setHistoryCollapsed((v) => !v)}
                    />
                  </Tooltip>
                  <Tooltip title="刷新历史">
                    <Button
                      size="small"
                      icon={<ReloadOutlined />}
                      loading={historyLoading}
                      onClick={loadHistory}
                    />
                  </Tooltip>
                </Space>
              }
              bodyStyle={{
                padding: historyCollapsed ? 4 : 8,
                height: '100%',
                overflow: 'hidden',
              }}
              style={{ height: '100%' }}
            >
              {historyCollapsed ? (
                <div
                  style={{
                    writingMode: 'vertical-rl',
                    textAlign: 'center',
                    height: '100%',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    color: '#999',
                    cursor: 'pointer',
                  }}
                  onClick={() => setHistoryCollapsed(false)}
                >
                  点击展开历史列表
                </div>
              ) : (
                <Spin spinning={historyLoading}>
                  {historyItems.length === 0 ? (
                    <div style={{ textAlign: 'center', padding: 12, color: '#999' }}>
                      暂无对比历史，先在右侧上传合同并开始对比。
                    </div>
                  ) : (
                    <List
                      size="small"
                      dataSource={historyItems}
                      rowKey={(item) => item.id}
                      style={{ maxHeight: '100%', overflowY: 'auto' }}
                      renderItem={(item) => {
                        const isActive = selectedHistoryId === item.id
                        return (
                          <List.Item
                            style={{
                              cursor: 'pointer',
                              backgroundColor: isActive ? '#e6f7ff' : 'transparent',
                              borderRadius: 4,
                            }}
                            onClick={() => loadCompareFromHistory(item)}
                          >
                            <Space direction="vertical" size={2} style={{ width: '100%' }}>
                              <Space size={4}>
                                <Tag color="blue">#{item.id}</Tag>
                                <Text style={{ fontSize: 12 }}>
                                  {item.status === 'success'
                                    ? '已完成'
                                    : item.status === 'failed'
                                    ? '失败'
                                    : item.status === 'running'
                                    ? '进行中'
                                    : item.status}
                                </Text>
                              </Space>
                              <Text type="secondary" style={{ fontSize: 11 }}>
                                {item.created_at
                                  ? new Date(item.created_at).toLocaleString('zh-CN')
                                  : ''}
                              </Text>
                              <Text type="secondary" style={{ fontSize: 11 }}>
                                左合同 ID: {item.left_contract_id} | 右合同 ID:{' '}
                                {item.right_contract_id}
                              </Text>
                            </Space>
                          </List.Item>
                        )
                      }}
                    />
                  )}
                </Spin>
              )}
            </Card>
          </Col>

          {/* 右侧：左右合同 + 对比结果 */}
          <Col
            span={historyCollapsed ? 23 : 18}
            style={{ height: '100%', display: 'flex', flexDirection: 'column', gap: 12 }}
          >
            {/* 上半部分：左右两份合同的上传 + 预览 */}
            <Row gutter={12} style={{ flex: '0 0 320px' }}>
              <Col span={12}>{renderContractPanel('left', leftContract, leftUploading, leftLoadingDetail)}</Col>
              <Col span={12}>{renderContractPanel('right', rightContract, rightUploading, rightLoadingDetail)}</Col>
            </Row>

            {/* 开始对比按钮 */}
            <div
              style={{
                marginTop: 8,
                marginBottom: 4,
                display: 'flex',
                justifyContent: 'space-between',
                alignItems: 'center',
              }}
            >
              <Button
                type="primary"
                onClick={handleStartCompare}
                disabled={!canStartCompare}
                loading={compareLoading}
              >
                开始对比
              </Button>
              <Text type="secondary" style={{ fontSize: 12 }}>
                提示：对比基于条款编号进行对齐，结果会按差异类型与重要性进行颜色高亮展示。
              </Text>
            </div>

            {/* 下半部分：对比结果 */}
            <Card
              title={
                <Space>
                  <FileTextOutlined />
                  <span>对比结果</span>
                </Space>
              }
              bodyStyle={{ padding: 12, display: 'flex', flexDirection: 'column', gap: 8 }}
              style={{ flex: 1, minHeight: 260 }}
            >
              <Spin spinning={compareLoading}>
                <div style={{ marginBottom: 8 }}>{renderSummary()}</div>
                <Divider style={{ margin: '8px 0' }} />
                {renderDiffList()}
              </Spin>
            </Card>
          </Col>
        </Row>
      </Content>
    </Layout>
  )
}

export default ContractCompare




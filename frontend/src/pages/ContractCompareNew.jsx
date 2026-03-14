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
  Collapse,
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
  WarningOutlined,
  ExclamationCircleOutlined,
  InfoCircleOutlined,
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
      normal: { backgroundColor: '#f6ffed', borderColor: '#b7eb8f', textColor: '#389e0d' },
      vital: { backgroundColor: '#d9f7be', borderColor: '#52c41a', textColor: '#135200' },
    },
    delete: {
      normal: { backgroundColor: '#fff1f0', borderColor: '#ffa39e', textColor: '#cf1322' },
      vital: { backgroundColor: '#ffccc7', borderColor: '#ff4d4f', textColor: '#a8071a' },
    },
    alter: {
      normal: { backgroundColor: '#fffbe6', borderColor: '#ffe58f', textColor: '#d48806' },
      vital: { backgroundColor: '#ffe7ba', borderColor: '#fa8c16', textColor: '#ad6800' },
    },
  }
  return map[changeType]?.[level] || { backgroundColor: '#fafafa', borderColor: '#d9d9d9', textColor: '#595959' }
}

// 统一映射 change_type 到中文文案
const changeTypeLabel = {
  add: '新增',
  delete: '删除',
  alter: '修改',
}

const importanceLabel = {
  normal: '一般',
  vital: '重要',
}

// 将 clause_marker 转为正则模式数组，用于匹配原文
const getMarkerPatterns = (marker) => {
  const patterns = []
  if (!marker) return patterns

  // 处理纯数字形式如 "1", "1.1", "3.3"
  if (/^\d+(\.\d+)*$/.test(marker)) {
    // 匹配 "第1条", "第1.1条", "第3.3条"
    patterns.push(new RegExp(`^第${marker}条`, 'gm'))
    // 匹配 "1.", "1.1.", "3.3."
    patterns.push(new RegExp(`^${marker}\\.`, 'gm'))
    // 匹配 "1、", "1.1、"
    patterns.push(new RegExp(`^${marker}、`, 'gm'))
  }

  // 处理前言形式如 "a1"
  if (/^a\d+$/.test(marker)) {
    patterns.push(new RegExp(`^${marker}[\\s\\S]*?`, 'gm'))
  }

  return patterns
}

// 在原文文本中查找条款内容，返回起始和结束位置
const findClauseInText = (fullText, marker) => {
  const patterns = getMarkerPatterns(marker)
  const lines = fullText.split('\n')

  for (let i = 0; i < lines.length; i++) {
    const line = lines[i].trim()
    if (!line) continue

    for (const pattern of patterns) {
      // 重置 lastIndex
      pattern.lastIndex = 0
      if (pattern.test(line)) {
        // 找到条款，从这一行开始，直到下一个条款或文件结束
        let clauseLines = [lines[i]]
        let j = i + 1

        // 继续读取后续行，直到遇到下一个条款编号
        while (j < lines.length) {
          const nextLine = lines[j].trim()
          // 检查是否是条款编号（新条款的开始）
          const isClauseStart = /^(第[一二三四五六七八九十百千万〇零两\d]+条|[\一二三四五六七八九十]+、|\d+\.\d+|\d+\.|（[一二三四五六七八九十]+）|\d+、|（\d+）|[a-zA-Z][\.\)、)])/.test(nextLine)
          if (isClauseStart && nextLine.length < 50) {
            break
          }
          clauseLines.push(lines[j])
          j++
        }

        return {
          startLine: i,
          endLine: j - 1,
          text: clauseLines.join('\n'),
        }
      }
    }
  }

  return null
}

// 解析全文为条款数组，标记有差异的条款
const parseClausesWithDiff = (fullText, diffs) => {
  if (!fullText) return []

  const lines = fullText.split('\n')
  const clauses = []
  let currentClause = null

  // 构建差异查找表
  const diffMap = {}
  ;(diffs || []).forEach((d) => {
    diffMap[d.clause_marker] = d
  })

  // 条款编号正则
  const clausePattern = /^(第[一二三四五六七八九十百千万〇零两\d]+条|[\一二三四五六七八九十]+、|\d+\.\d+|\d+\.|（[一二三四五六七八九十]+）|\d+、|（\d+）|[a-zA-Z][\.\)、)])(.*)/

  // 查找匹配的差异（通过文本相似度）
  const findMatchingDiff = (text) => {
    if (!text) return null
    for (const d of diffs || []) {
      const leftText = d.left_text || ''
      const rightText = d.right_text || ''
      // 如果文本中有超过 50% 的内容匹配，则认为是同一个条款
      if (leftText && text.includes(leftText.substring(0, Math.min(30, leftText.length)))) {
        return d
      }
      if (rightText && text.includes(rightText.substring(0, Math.min(30, rightText.length)))) {
        return d
      }
    }
    return null
  }

  for (let i = 0; i < lines.length; i++) {
    const line = lines[i]
    const trimmed = line.trim()

    // 跳过空行
    if (!trimmed) {
      if (currentClause) {
        currentClause.content += '\n'
      }
      continue
    }

    const match = clausePattern.exec(trimmed)

    if (match) {
      // 保存之前的条款
      if (currentClause) {
        clauses.push(currentClause)
      }

      // 提取 clause_marker
      const markerStr = match[1]
      let normalizedMarker = ''

      // 转换为统一格式
      const cnToNum = { '一': '1', '二': '2', '三': '3', '四': '4', '五': '5', '六': '6', '七': '7', '八': '8', '九': '9', '十': '10' }
      const numMatch = markerStr.match(/\d+/g)
      if (numMatch) {
        normalizedMarker = numMatch.join('.')
      } else if (/^a\d+$/.test(markerStr)) {
        normalizedMarker = markerStr
      }

      const restContent = match[2] || ''
      const fullContent = restContent ? `${restContent}` : ''

      // 优先用 clause_marker 匹配，其次用文本相似度
      const diff = diffMap[normalizedMarker] || findMatchingDiff(fullContent)

      currentClause = {
        marker: markerStr,
        clause_marker: normalizedMarker,
        content: fullContent,
        startLine: i,
        diff: diff || null,
      }
    } else {
      // 续行内容
      if (currentClause) {
        currentClause.content += (currentClause.content ? '\n' : '') + line
      } else {
        // 前言部分：检查是否匹配差异
        const matchedDiff = findMatchingDiff(line) || findMatchingDiff(lines.slice(i, i + 5).join('\n'))
        currentClause = {
          marker: '',
          clause_marker: matchedDiff?.clause_marker || '',
          content: line,
          startLine: i,
          diff: matchedDiff || null,
        }
      }
    }
  }

  // 保存最后一个条款
  if (currentClause) {
    clauses.push(currentClause)
  }

  return clauses
}

const ContractCompareNew = () => {
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

  // 鼠标悬停的差异条款
  const [hoveredDiff, setHoveredDiff] = useState(null)

  // 是否显示上传区域（从历史记录加载后隐藏上传区域）
  const [showUploadArea, setShowUploadArea] = useState(true)

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
      if (contract?.id) {
        if (side === 'left') {
          setLeftLoadingDetail(true)
        } else {
          setRightLoadingDetail(true)
        }
        const detail = await contractService.getContract(contract.id)

        if (detail?.id) {
          try {
            await contractService.extractContractKG(detail.id)
          } catch (e) {
            console.error('触发知识图谱抽取失败:', e)
          }
        }

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
    setShowUploadArea(false) // 从历史记录加载后隐藏上传区域
    setCompareLoading(true)
    setLeftLoadingDetail(true)
    setRightLoadingDetail(true)
    try {
      const detail = await compareService.getCompareDetail(item.id)
      setCompareDetail(detail)

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
  const allDiffs = currentResult?.all_differences || []

  // 解析原文为条款
  const leftClauses = useMemo(() => {
    return parseClausesWithDiff(leftContract?.file_content, allDiffs)
  }, [leftContract?.file_content, allDiffs])

  const rightClauses = useMemo(() => {
    return parseClausesWithDiff(rightContract?.file_content, allDiffs)
  }, [rightContract?.file_content, allDiffs])

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
        style={{ marginBottom: 16 }}
        bodyStyle={{ display: 'flex', flexDirection: 'column', gap: 8 }}
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

  // 概览统计
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
          <Text strong>{s.only_in_left_count ?? 0} 条</Text>
        </span>
        <span>
          <Tag color="green">仅右侧存在</Tag>
          <Text strong>{s.only_in_right_count ?? 0} 条</Text>
        </span>
        <span>
          <Tag color="gold">两侧均存在</Tag>
          <Text strong>{s.in_both_count ?? 0} 条</Text>
        </span>
        <span>
          <Tag color="orange">内容有差异</Tag>
          <Text strong>{s.changed_in_both_count ?? 0} 条</Text>
        </span>
      </Space>
    )
  }

  // 渲染单个差异条款（在原文中的显示）
  const renderDiffClause = (clause, side, colors) => {
    const { diff, content, clause_marker } = clause

    if (!diff) {
      return (
        <div
          style={{
            padding: '8px 12px',
            borderBottom: '1px solid #f0f0f0',
          }}
        >
          <Text style={{ whiteSpace: 'pre-wrap', wordBreak: 'break-word' }}>
            {content}
          </Text>
        </div>
      )
    }

    const isLeft = side === 'left'
    const showLeftText = isLeft && (diff.change_type === 'delete' || diff.change_type === 'alter')
    const showRightText = !isLeft && (diff.change_type === 'add' || diff.change_type === 'alter')

    // 风险提示内容
    const riskContent = (
      <div style={{ maxWidth: 400, padding: 4 }}>
        <div style={{ marginBottom: 8 }}>
          <Tag color={diff.importance === 'vital' ? 'red' : 'blue'}>
            {importanceLabel[diff.importance] || diff.importance}
          </Tag>
        </div>
        <div style={{ fontSize: 13, lineHeight: 1.6 }}>
          <strong>风险说明：</strong>
          {diff.explanation || '暂无详细说明'}
        </div>
      </div>
    )

    return (
      <div
        style={{
          borderBottom: '1px solid #f0f0f0',
          transition: 'all 0.2s',
        }}
        onMouseEnter={() => setHoveredDiff({ clause_marker, side })}
        onMouseLeave={() => setHoveredDiff(null)}
      >
        {/* 差异标注行 */}
        <div
          style={{
            padding: '4px 12px',
            backgroundColor: colors.backgroundColor,
            borderBottom: `1px solid ${colors.borderColor}`,
            display: 'flex',
            alignItems: 'center',
            gap: 8,
          }}
        >
          <Tag color={colors.textColor} style={{ margin: 0 }}>
            {changeTypeLabel[diff.change_type] || diff.change_type}
          </Tag>
          <Tag color={diff.importance === 'vital' ? 'red' : 'default'}>
            {importanceLabel[diff.importance] || diff.importance}
          </Tag>
          <Text strong style={{ color: colors.textColor, fontSize: 12 }}>
            {clause_marker || diff.clause_marker}
          </Text>
        </div>

        {/* 条款内容 */}
        <div
          style={{
            padding: '8px 12px',
            backgroundColor: hoveredDiff?.clause_marker === clause_marker && hoveredDiff?.side === side
              ? colors.backgroundColor
              : 'transparent',
          }}
        >
          {showLeftText && (
            <div>
              <Text type="secondary" style={{ fontSize: 11 }}>
                左侧：
              </Text>
              <div style={{ whiteSpace: 'pre-wrap', wordBreak: 'break-word', marginTop: 4 }}>
                {diff.left_text || '（该条款在左侧合同中不存在）'}
              </div>
            </div>
          )}
          {showRightText && (
            <div>
              <Text type="secondary" style={{ fontSize: 11 }}>
                右侧：
              </Text>
              <div style={{ whiteSpace: 'pre-wrap', wordBreak: 'break-word', marginTop: 4 }}>
                {diff.right_text || '（该条款在右侧合同中不存在）'}
              </div>
            </div>
          )}
          {!showLeftText && !showRightText && (
            <Text style={{ whiteSpace: 'pre-wrap', wordBreak: 'break-word' }}>
              {content}
            </Text>
          )}
        </div>

        {/* 悬停显示的风险提示 */}
        {hoveredDiff?.clause_marker === clause_marker && hoveredDiff?.side === side && (
          <div
            style={{
              padding: '8px 12px',
              backgroundColor: '#fff2e8',
              borderTop: `1px solid #ffbb96`,
              display: 'flex',
              alignItems: 'flex-start',
              gap: 8,
            }}
          >
            <WarningOutlined style={{ color: '#fa541c', marginTop: 4 }} />
            <div style={{ flex: 1 }}>
              <Text strong style={{ color: '#ad2800', fontSize: 12 }}>
                风险解析
              </Text>
              <div style={{ fontSize: 12, lineHeight: 1.6, marginTop: 4, color: '#595959' }}>
                {diff.explanation || '暂无详细说明'}
              </div>
            </div>
          </div>
        )}
      </div>
    )
  }

  // 渲染原文对照视图
  const renderDiffView = () => {
    if (!currentResult) {
      return (
        <div style={{ textAlign: 'center', padding: 48, color: '#999' }}>
          <InfoCircleOutlined style={{ fontSize: 48, marginBottom: 16 }} />
          <div>暂无对比结果</div>
          <Text type="secondary">请上传左右两份合同并点击「开始对比」</Text>
        </div>
      )
    }

    return (
      <Row gutter={16}>
        {/* 左侧原文 */}
        <Col span={12}>
          <Card
            title={
              <Space>
                <FileTextOutlined />
                <span>左侧合同原文</span>
                {leftContract?.filename && (
                  <Tag color="blue">{leftContract.filename}</Tag>
                )}
              </Space>
            }
            bodyStyle={{ padding: 0 }}
            style={{ marginBottom: 16 }}
          >
            {leftClauses.length > 0 ? (
                leftClauses.map((clause, idx) => {
                  const diff = clause.diff
                  const colors = diff ? getDiffColors(diff.change_type, diff.importance) : null
                  return (
                    <div key={idx}>
                      {renderDiffClause(clause, 'left', colors)}
                    </div>
                  )
                })
              ) : (
                <div style={{ padding: 24, textAlign: 'center', color: '#999' }}>
                  暂无合同内容
                </div>
              )}
          </Card>
        </Col>

        {/* 右侧原文 */}
        <Col span={12}>
          <Card
            title={
              <Space>
                <FileTextOutlined />
                <span>右侧合同原文</span>
                {rightContract?.filename && (
                  <Tag color="green">{rightContract.filename}</Tag>
                )}
              </Space>
            }
            bodyStyle={{ padding: 0 }}
            style={{ marginBottom: 16 }}
          >
            {rightClauses.length > 0 ? (
                rightClauses.map((clause, idx) => {
                  const diff = clause.diff
                  const colors = diff ? getDiffColors(diff.change_type, diff.importance) : null
                  return (
                    <div key={idx}>
                      {renderDiffClause(clause, 'right', colors)}
                    </div>
                  )
                })
              ) : (
                <div style={{ padding: 24, textAlign: 'center', color: '#999' }}>
                  暂无合同内容
                </div>
              )}
          </Card>
        </Col>
      </Row>
    )
  }

  // 差异列表（可选展开）
  const renderDiffList = () => {
    if (!currentResult) return null

    const diffs = allDiffs
    if (!diffs.length) {
      return (
        <div style={{ textAlign: 'center', padding: 24, color: '#999' }}>
          未检测到条款级差异。
        </div>
      )
    }

    return (
      <Collapse
        ghost
        items={[
          {
            key: '1',
            label: (
              <Text type="secondary">
                查看全部差异详情（{diffs.length} 条）
              </Text>
            ),
            children: (
              <List
                size="small"
                dataSource={diffs}
                rowKey={(item, index) => `${item.clause_marker || 'clause'}_${index}`}
                style={{ maxHeight: 300, overflow: 'auto' }}
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
                              {importanceLabel[importance] || importance}
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
            ),
          },
        ]}
      />
    )
  }

  return (
    <Layout style={{ minHeight: '100vh', overflow: 'auto' }}>
      <Header
        style={{
          background: '#fff',
          padding: '0 24px',
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          boxShadow: '0 2px 8px rgba(0,0,0,0.1)',
          flexShrink: 0,
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
          <img
            src="/images/APP.png"
            alt="logo"
            style={{ height: 36, verticalAlign: 'middle' }}
          />
          <Title level={3} style={{ margin: 0 }}>
            合同智能解读系统 - 合同对比（新）
          </Title>
        </div>
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

      <Content style={{ padding: '24px', background: '#f0f2f5', flex: 1, overflow: 'auto' }}>
        <Row gutter={16} style={{ width: '100%' }}>
          {/* 左侧：对比历史列表，可折叠 */}
          <Col
            span={historyCollapsed ? 1 : 6}
            style={{
              transition: 'all 0.2s',
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
              }}
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
                      renderItem={(item) => {
                        const isActive = selectedHistoryId === item.id
                        const leftName =
                          item.left_contract_filename ||
                          (item.left_contract_id ? `合同 ${item.left_contract_id}` : '未知合同')

                        const createdText = item.created_at
                          ? new Date(item.created_at).toLocaleString('zh-CN', {
                              year: 'numeric',
                              month: '2-digit',
                              day: '2-digit',
                              hour: '2-digit',
                              minute: '2-digit',
                              second: '2-digit',
                            })
                          : ''

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
                              <Space size={4} style={{ width: '100%' }}>
                                <Tag color="blue">#{item.id}</Tag>
                                <Text
                                  style={{
                                    fontSize: 12,
                                    fontWeight: 500,
                                    maxWidth: 190,
                                    whiteSpace: 'nowrap',
                                    overflow: 'hidden',
                                    textOverflow: 'ellipsis',
                                  }}
                                  title={`${leftName} 对比`}
                                >
                                  {leftName} 对比
                                </Text>
                              </Space>
                              <Text type="secondary" style={{ fontSize: 11, fontWeight: 500 }}>
                                {createdText}
                              </Text>
                              <Text type="secondary" style={{ fontSize: 11 }}>
                                左合同 ID: {item.left_contract_id} | 右合同 ID:{' '}
                                {item.right_contract_id} | 状态:{' '}
                                {item.status === 'success'
                                  ? '已完成'
                                  : item.status === 'failed'
                                  ? '失败'
                                  : item.status === 'running'
                                  ? '进行中'
                                  : item.status || '未知'}
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
            style={{ gap: 12 }}
          >
            {/* 上半部分：左右两份合同的上传 + 预览（根据 showUploadArea 显示/隐藏） */}
            {showUploadArea ? (
              <Row gutter={12} style={{ flex: '0 0 320px' }}>
                <Col span={12}>{renderContractPanel('left', leftContract, leftUploading, leftLoadingDetail)}</Col>
                <Col span={12}>{renderContractPanel('right', rightContract, rightUploading, rightLoadingDetail)}</Col>
              </Row>
            ) : (
              <Row gutter={12} style={{ flex: '0 0 auto', marginBottom: 8 }}>
                <Col span={24}>
                  <Card size="small" bodyStyle={{ padding: 12 }}>
                    <Space size="middle">
                      <Tag color="blue">左侧: {leftContract?.filename || '未知文件'}</Tag>
                      <Tag color="green">右侧: {rightContract?.filename || '未知文件'}</Tag>
                      <Button size="small" onClick={() => setShowUploadArea(true)}>
                        重新上传
                      </Button>
                      <Button
                        size="small"
                        type="primary"
                        onClick={handleStartCompare}
                        disabled={!canStartCompare}
                        loading={compareLoading}
                      >
                        重新对比
                      </Button>
                    </Space>
                  </Card>
                </Col>
              </Row>
            )}

            {/* 开始对比按钮（仅在上传区域显示时） */}

            {/* 下半部分：对比结果 */}
            <Card
              title={
                <Space>
                  <FileTextOutlined />
                  <span>对比结果</span>
                </Space>
              }
              bodyStyle={{ padding: 12, display: 'flex', flexDirection: 'column', gap: 8, flex: 1, minHeight: 0 }}
              style={{ flex: 1, minHeight: 300, display: 'flex', flexDirection: 'column' }}
            >
              <Spin spinning={compareLoading}>
                {/* 概览统计 */}
                <div style={{ marginBottom: 8 }}>{renderSummary()}</div>

                {/* 原文对照视图 */}
                <div style={{ flex: 1, minHeight: 0 }}>
                  {renderDiffView()}
                </div>

                {/* 可展开的差异详情列表 */}
                {renderDiffList()}
              </Spin>
            </Card>
          </Col>
        </Row>
      </Content>
    </Layout>
  )
}

export default ContractCompareNew

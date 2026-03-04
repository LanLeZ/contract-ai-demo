import api from './api'

export const contractService = {
  // 上传合同文件
  async uploadContract(file) {
    const formData = new FormData()
    formData.append('file', file)
    
    const response = await api.post('/api/documents/upload', formData, {
      headers: {
        'Content-Type': 'multipart/form-data',
      },
      // 添加上传进度支持
      onUploadProgress: (progressEvent) => {
        const percentCompleted = Math.round(
          (progressEvent.loaded * 100) / progressEvent.total
        )
        // 进度信息可以通过事件或回调传递，这里先不处理
        return percentCompleted
      },
    })
    return response.data
  },

  // 上传多张图片（合并为同一份合同）
  async uploadContractImages(files, displayName) {
    const formData = new FormData()
    files.forEach((file) => formData.append('files', file))
    if (displayName) {
      formData.append('display_name', displayName)
    }

    const response = await api.post('/api/documents/upload-images', formData, {
      headers: {
        'Content-Type': 'multipart/form-data',
      },
    })
    return response.data
  },

  // 获取合同列表
  async getContracts() {
    const response = await api.get('/api/documents/')
    return response.data
  },

  // 获取合同详情
  async getContract(id) {
    const response = await api.get(`/api/documents/${id}`)
    return response.data
  },

  // 删除合同
  async deleteContract(id) {
    const response = await api.delete(`/api/documents/${id}`)
    return response.data
  },

  // 合同智能问答
  async contractQA(id, payload) {
    const response = await api.post(`/api/documents/${id}/qa`, payload)
    return response.data
  },

  // 列出某合同下的会话列表
  async listSessions(contractId) {
    const response = await api.get(`/api/documents/${contractId}/sessions`)
    return response.data
  },

  // 获取某个会话的完整历史
  async getSessionHistory(contractId, sessionId) {
    const response = await api.get(
      `/api/documents/${contractId}/sessions/${encodeURIComponent(sessionId)}`
    )
    return response.data
  },

  // 获取某合同的知识图谱三元组
  async getContractKG(contractId) {
    const response = await api.get(`/api/contracts/${contractId}/kg`)
    return response.data
  },

  // 触发某合同的知识图谱抽取（分类 + 模板抽取）
  async extractContractKG(contractId) {
    const response = await api.post(`/api/contracts/${contractId}/kg-extract`)
    return response.data
  },
}


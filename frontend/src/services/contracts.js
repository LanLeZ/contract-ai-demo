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
}


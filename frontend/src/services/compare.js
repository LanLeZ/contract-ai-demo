import api from './api'

// 合同对比相关接口封装
export const compareService = {
  // 创建一次合同对比（同步执行，返回完整结果）
  async createCompare(leftContractId, rightContractId) {
    const response = await api.post('/api/documents/compare', {
      left_contract_id: leftContractId,
      right_contract_id: rightContractId,
    })
    return response.data
  },

  // 获取某次合同对比的详细结果
  async getCompareDetail(compareId) {
    const response = await api.get(`/api/documents/compare/${compareId}`)
    return response.data
  },

  // 获取当前用户的合同对比历史列表
  async listHistory() {
    const response = await api.get('/api/documents/compare/history')
    return response.data
  },
}




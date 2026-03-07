import axios from 'axios'

const api = axios.create({
  baseURL: '/api',
  timeout: 30000,
})

export const getStats = () => api.get('/stats').then(r => r.data)

export const getAlerts = (params) => api.get('/alerts', { params }).then(r => r.data)
export const getAlert = (id) => api.get(`/alerts/${id}`).then(r => r.data)
export const updateAlertStatus = (id, status) => api.patch(`/alerts/${id}/status`, null, { params: { status } }).then(r => r.data)
export const exportAlerts = (params) => {
  const query = new URLSearchParams(params).toString()
  window.open(`/api/alerts/export?${query}`)
}

export const getProcurements = (params) => api.get('/procurements', { params }).then(r => r.data)
export const getProcurement = (ocid) => api.get(`/procurements/${encodeURIComponent(ocid)}`).then(r => r.data)

export const getSuppliers = (params) => api.get('/suppliers', { params }).then(r => r.data)
export const getSupplier = (rut) => api.get(`/suppliers/${rut}`).then(r => r.data)
export const getSupplierNetwork = (rut) => api.get(`/suppliers/${rut}/network`).then(r => r.data)
export const refreshSupplierExternal = (rut) => api.post(`/suppliers/${rut}/refresh-external`).then(r => r.data)

export default api

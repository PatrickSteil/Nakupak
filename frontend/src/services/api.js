import axios from 'axios'

const API_BASE = import.meta.env.VITE_API_URL || ''

const api = axios.create({
  baseURL: API_BASE,
})

api.interceptors.request.use((config) => {
  const token = localStorage.getItem('token')
  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})

api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      localStorage.removeItem('token')
      window.location.href = '/login'
    }
    return Promise.reject(error)
  }
)

export const auth = {
  create: (name, password) => api.post('/api/auth/create', { name, password }),
  login: (name, password) => api.post('/api/auth/login', { name, password }),
  me: () => api.get('/api/auth/me'),
  update: (data) => api.patch('/api/auth/me', data),
}

export const categories = {
  list: () => api.get('/api/categories'),
  create: (data) => api.post('/api/categories', data),
  update: (id, data) => api.put(`/api/categories/${id}`, data),
  delete: (id) => api.delete(`/api/categories/${id}`),
  reorder: (ids) => api.post('/api/categories/reorder', { ids }),
}

export const items = {
  list: () => api.get('/api/items'),
  create: (data) => api.post('/api/items', data),
  update: (id, data) => api.put(`/api/items/${id}`, data),
  delete: (id) => api.delete(`/api/items/${id}`),
  merge: (targetId, sourceIds) => api.post(`/api/items/${targetId}/merge`, { source_ids: sourceIds }),
  bulkDelete: (ids) => api.post('/api/items/delete', { ids }),
  bulkSetCategory: (itemIds, categoryId) => api.post('/api/items/set-category', { item_ids: itemIds, category_id: categoryId }),
}

export const shoppingList = {
  get: () => api.get('/api/list'),
  add: (items) => api.post('/api/list/add', { items }),
  update: (id, data) => api.put(`/api/list/${id}`, data),
  remove: (id) => api.delete(`/api/list/${id}`),
  addRecipe: (recipeId) => api.post(`/api/list/add-recipe/${recipeId}`),
  bulkRemove: (ids) => api.post('/api/list/remove', { ids }),
  clear: () => api.delete('/api/list'),
  toggleCheck: (id) => api.put(`/api/list/${id}/check`),
  purchase: () => api.post('/api/list/purchase'),
}

export const pool = {
  get: () => api.get('/api/pool'),
}

export const recipes = {
  list: () => api.get('/api/recipes'),
  create: (data) => api.post('/api/recipes', data),
  update: (id, data) => api.put(`/api/recipes/${id}`, data),
  delete: (id) => api.delete(`/api/recipes/${id}`),
  exportAll: () => api.get('/api/recipes/export'),
  exportOne: (id) => api.get(`/api/recipes/${id}/export`),
  importJson: (doc) => api.post('/api/recipes/import-json', doc),
  uploadImage: (file) => {
    const formData = new FormData()
    formData.append('file', file)
    return api.post('/api/recipes/upload-image', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    })
  },
}

export const sessions = {
  list: () => api.get('/api/sessions'),
  delete: (id) => api.delete(`/api/sessions/${id}`),
}

export default api

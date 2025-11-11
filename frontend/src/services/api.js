import axios from 'axios'

const BASE = import.meta.env.VITE_API_URL || 'http://localhost:5000'

const api = axios.create({
  baseURL: BASE,
  withCredentials: true,
})

// Attach token to requests
api.interceptors.request.use((config) => {
  const token = localStorage.getItem('token')
  if (token) config.headers.Authorization = `Bearer ${token}`
  return config
})

// Global response handler: if 401, clear auth and redirect to login
api.interceptors.response.use(
  (res) => res,
  (err) => {
    const status = err?.response?.status
    if (status === 401) {
      try {
        // don't auto-redirect when we're already on the login route or
        // when the failing request was the login attempt itself. This
        // prevents the global handler from performing a hard reload and
        // clearing local error messages shown on the login page.
        const reqUrl = err?.config?.url || ''
        const isLoginAttempt = reqUrl.includes('/login') || window.location.pathname === '/login'

        localStorage.removeItem('token')
        localStorage.removeItem('usuario')

        if (!isLoginAttempt) {
          // redirect to login (hard reload ensures cleaned state)
          window.location.href = '/login'
        }
      } catch (e) {
        // ignore
      }
    }
    return Promise.reject(err)
  }
)

export default api

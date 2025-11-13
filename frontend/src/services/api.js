import axios from 'axios'

const BASE = import.meta.env.VITE_API_URL || 'http://localhost:5000'

const api = axios.create({
  baseURL: BASE,
  withCredentials: true,
})

// Anexar token às requisições
api.interceptors.request.use((config) => {
  const token = localStorage.getItem('token')
  if (token) config.headers.Authorization = `Bearer ${token}`
  return config
})

// Manipulador global de respostas: se 401, limpar auth e redirecionar para login
api.interceptors.response.use(
  (res) => res,
  (err) => {
    const status = err?.response?.status
    if (status === 401) {
      try {
        // não redirecionar automaticamente quando já estivermos na rota de login ou
        // quando a requisição com erro foi a tentativa de login. Isso
        // impede que o manipulador global realize um reload completo e
        // limpe as mensagens de erro locais mostradas na página de login.
        const reqUrl = err?.config?.url || ''
        const isLoginAttempt = reqUrl.includes('/login') || window.location.pathname === '/login'

        localStorage.removeItem('token')
        localStorage.removeItem('usuario')

        if (!isLoginAttempt) {
          // redirecionar para login (hard reload garante estado limpo)
          window.location.href = '/login'
        }
      } catch (e) {
        // ignorar
      }
    }
    return Promise.reject(err)
  }
)

export default api

import React, { useEffect, useState } from 'react'
import { Navigate, Outlet, useLocation } from 'react-router-dom'
import api from '../services/api'

export default function RequireAuth({ children }) {
  const [checking, setChecking] = useState(true)
  const [authenticated, setAuthenticated] = useState(false)
  const location = useLocation()

  useEffect(() => {
    let mounted = true
    const check = async () => {
      try {
        await api.get('/api/perfil')
        if (mounted) setAuthenticated(true)
      } catch (err) {
        if (mounted) setAuthenticated(false)
      } finally {
        if (mounted) setChecking(false)
      }
    }
    check()
    return () => { mounted = false }
  }, [])

  if (checking) return <div className='p-6'>Verificando autenticação...</div>

  if (!authenticated) {
    return <Navigate to='/login' state={{ from: location }} replace />
  }

  return children ? children : <Outlet />
}

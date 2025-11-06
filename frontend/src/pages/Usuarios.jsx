import React, { useEffect, useState } from 'react'
import api from '../services/api.js'
import { useNavigate } from 'react-router-dom'

export default function Usuarios() {
  const [usuarios, setUsuarios] = useState([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const navigate = useNavigate()

  useEffect(() => {
    const fetch = async () => {
      setLoading(true)
      setError('')
      try {
        const res = await api.get('/api/usuarios')
        setUsuarios(res.data.usuarios || [])
      } catch (err) {
        setError(err?.response?.data?.erro || err.message || 'Erro ao carregar usuários')
      } finally {
        setLoading(false)
      }
    }
    fetch()
  }, [])

  return (
    <div>
      <div className='flex items-center justify-between mb-4'>
        <h2 className='text-xl font-semibold'>Usuários cadastrados</h2>
      </div>

      {loading && <p className='muted'>Carregando...</p>}
      {error && <p className='text-red-400'>{error}</p>}

      {!loading && !error && (
        <div className='card p-4'>
          {usuarios.length === 0 ? (
            <p className='muted'>Nenhum usuário encontrado.</p>
          ) : (
            <ul className='space-y-2'>
              {usuarios.map(u => (
                <li key={u.id} className='p-3 rounded hover:bg-white/3 cursor-pointer flex items-center justify-between' onClick={() => navigate(`/usuarios/${u.id}`)}>
                  <div>
                    <div className='font-medium'>{u.nome}</div>
                    <div className='muted text-sm'>{u.email}</div>
                  </div>
                  <div className='text-sm muted'>ID: {u.id}</div>
                </li>
              ))}
            </ul>
          )}
        </div>
      )}
    </div>
  )
}

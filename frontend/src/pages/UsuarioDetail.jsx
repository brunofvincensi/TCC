import React, { useEffect, useState } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import api from '../services/api.js'

export default function UsuarioDetail() {
  const { id } = useParams()
  const navigate = useNavigate()
  const [usuario, setUsuario] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [editing, setEditing] = useState(false)
  const [form, setForm] = useState({ nome: '', email: '', senha: '' })
  const [success, setSuccess] = useState('')

  const current = (() => { try { return JSON.parse(localStorage.getItem('usuario')) } catch { return null } })()

  useEffect(() => {
    if (!id) return
    const fetch = async () => {
      setLoading(true); setError('')
      try {
        const res = await api.get(`/api/usuarios/${id}`)
        setUsuario(res.data)
        setForm({ nome: res.data.nome || '', email: res.data.email || '', senha: '' })
      } catch (err) {
        setError(err?.response?.data?.erro || err.message || 'Erro ao carregar usuário')
      } finally { setLoading(false) }
    }
    fetch()
  }, [id])

  const handleChange = (e) => setForm({ ...form, [e.target.name]: e.target.value })

  const handleSave = async (e) => {
    e.preventDefault()
    setError(''); setSuccess('')
    // backend only allows updating current user via PUT /api/usuarios
    if (!current || String(current.id) !== String(id)) {
      setError('Você só pode editar seu próprio perfil.')
      return
    }
    try {
      const payload = { nome: form.nome, email: form.email }
      if (form.senha && form.senha.length > 0) payload.senha = form.senha
      const res = await api.put('/api/usuarios', payload)
      setSuccess(res.data?.mensagem || 'Usuário atualizado')
      // update local storage usuario if current
      const perfil = await api.get('/api/perfil')
      localStorage.setItem('usuario', JSON.stringify(perfil.data))
      setUsuario(perfil.data)
      setEditing(false)
      setTimeout(() => setSuccess(''), 3000)
    } catch (err) {
      setError(err?.response?.data?.erro || 'Erro ao atualizar usuário')
    }
  }

  const handleDelete = async () => {
    if (!current || String(current.id) !== String(id)) {
      setError('Você só pode deletar seu próprio usuário.')
      return
    }
    if (!confirm('Tem certeza que deseja deletar seu usuário? Esta ação não pode ser desfeita.')) return
    try {
      await api.delete('/api/usuarios')
      // logged out
      localStorage.removeItem('token')
      localStorage.removeItem('usuario')
      navigate('/login')
    } catch (err) {
      setError(err?.response?.data?.erro || 'Erro ao deletar usuário')
    }
  }

  if (loading) return <p className='muted'>Carregando...</p>
  if (error) return <p className='text-red-400'>{error}</p>
  if (!usuario) return null

  return (
    <div>
      <div className='flex items-center justify-between mb-4'>
        <h2 className='text-xl font-semibold'>Usuário: {usuario.nome}</h2>
      </div>

      <div className='card p-4'>
        {!editing ? (
          <div>
            <p><strong>Nome:</strong> {usuario.nome}</p>
            <p><strong>Email:</strong> {usuario.email}</p>
            <p className='muted'><strong>Ativo:</strong> {usuario.ativo ? 'Sim' : 'Não'}</p>
            <div className='mt-4 flex gap-2'>
              {current && String(current.id) === String(id) && (
                <>
                  <button className='btn-accent py-2 px-3 rounded' onClick={() => setEditing(true)}>Editar</button>
                  <button className='py-2 px-3 rounded bg-red-600 text-white' onClick={handleDelete}>Deletar minha conta</button>
                </>
              )}
              <button className='py-2 px-3 rounded bg-white/5' onClick={() => navigate(-1)}>Voltar</button>
            </div>
          </div>
        ) : (
          <form onSubmit={handleSave} className='space-y-3'>
            {success && <p className='text-green-400'>{success}</p>}
            <div>
              <label className='block muted mb-1'>Nome</label>
              <input name='nome' value={form.nome} onChange={handleChange} className='w-full p-2 bg-white/3 rounded' />
            </div>
            <div>
              <label className='block muted mb-1'>Email</label>
              <input name='email' value={form.email} onChange={handleChange} className='w-full p-2 bg-white/3 rounded' />
            </div>
            <div>
              <label className='block muted mb-1'>Senha (deixe em branco para manter)</label>
              <input name='senha' type='password' value={form.senha} onChange={handleChange} className='w-full p-2 bg-white/3 rounded' />
            </div>
            <div className='flex gap-2'>
              <button type='submit' className='btn-accent py-2 px-3 rounded'>Salvar</button>
              <button type='button' className='py-2 px-3 rounded bg-white/5' onClick={() => setEditing(false)}>Cancelar</button>
            </div>
          </form>
        )}
      </div>
    </div>
  )
}

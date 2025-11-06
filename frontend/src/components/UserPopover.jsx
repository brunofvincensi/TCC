import React, { useEffect, useState, useRef } from 'react'
import api from '../services/api.js'
import { useNavigate } from 'react-router-dom'

export default function UserPopover() {
  const [open, setOpen] = useState(false)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [success, setSuccess] = useState('')
  const [editing, setEditing] = useState(false)
  const [form, setForm] = useState({ nome: '', email: '', senha: '' })
  const navigate = useNavigate()
  const ref = useRef(null)

  const current = (() => { try { return JSON.parse(localStorage.getItem('usuario')) } catch { return null } })()

  useEffect(() => {
    if (!open) return
    // load profile when opening
    let mounted = true
    ;(async () => {
      setLoading(true); setError('')
      try {
        const res = await api.get('/api/perfil')
        if (!mounted) return
        setForm({ nome: res.data.nome || '', email: res.data.email || '', senha: '' })
      } catch (err) {
        setError(err?.response?.data?.erro || 'Erro ao carregar perfil')
      } finally { setLoading(false) }
    })()
    return () => { mounted = false }
  }, [open])

  useEffect(() => {
    const onDoc = (e) => {
      if (ref.current && !ref.current.contains(e.target)) setOpen(false)
    }
    document.addEventListener('click', onDoc)
    return () => document.removeEventListener('click', onDoc)
  }, [])

  const handleChange = (e) => setForm({ ...form, [e.target.name]: e.target.value })

  const handleSave = async (e) => {
    e.preventDefault()
    setError(''); setSuccess('')
    try {
      const payload = { nome: form.nome, email: form.email }
      if (form.senha && form.senha.length > 0) payload.senha = form.senha
      const res = await api.put('/api/usuarios', payload)
      setSuccess(res.data?.mensagem || 'Perfil atualizado')
      // refresh local profile
      const perfil = await api.get('/api/perfil')
      localStorage.setItem('usuario', JSON.stringify(perfil.data))
      setTimeout(() => setSuccess(''), 3000)
      setEditing(false)
    } catch (err) {
      setError(err?.response?.data?.erro || 'Erro ao atualizar perfil')
    }
  }

  const handleDelete = async () => {
    if (!confirm('Tem certeza que deseja deletar sua conta? Esta ação não pode ser desfeita.')) return
    try {
      await api.delete('/api/usuarios')
      localStorage.removeItem('token')
      localStorage.removeItem('usuario')
      navigate('/login')
    } catch (err) {
      setError(err?.response?.data?.erro || 'Erro ao deletar usuário')
    }
  }

  return (
    <div className='relative' ref={ref}>
      <button onClick={() => setOpen(v => !v)} className='font-semibold mt-1'>{current?.nome ?? 'Usuário'}</button>

      {open && (
        <div className='absolute left-0 mt-2 w-80 bg-white/5 p-4 rounded shadow-lg z-50'>
          {loading ? (
            <div className='muted'>Carregando...</div>
          ) : (
            <div>
              {error && <div className='text-red-400 mb-2'>{error}</div>}
              {success && <div className='text-green-400 mb-2'>{success}</div>}

              {!editing ? (
                <div>
                  <div className='mb-2'><strong>{form.nome || current?.nome}</strong></div>
                  <div className='muted text-sm mb-3'>{form.email || current?.email}</div>
                  <div className='flex gap-2'>
                    <button className='btn-accent py-1 px-2 rounded text-sm' onClick={() => setEditing(true)}>Editar</button>
                    <button className='py-1 px-2 rounded bg-red-600 text-white text-sm' onClick={handleDelete}>Deletar</button>
                    <button className='py-1 px-2 rounded bg-white/5 text-sm' onClick={() => setOpen(false)}>Fechar</button>
                  </div>
                </div>
              ) : (
                <form onSubmit={handleSave} className='space-y-2'>
                  <div>
                    <label className='block muted mb-1 text-sm'>Nome</label>
                    <input name='nome' value={form.nome} onChange={handleChange} className='w-full p-2 bg-white/3 rounded text-sm' />
                  </div>
                  <div>
                    <label className='block muted mb-1 text-sm'>Email</label>
                    <input name='email' value={form.email} onChange={handleChange} className='w-full p-2 bg-white/3 rounded text-sm' />
                  </div>
                  <div>
                    <label className='block muted mb-1 text-sm'>Senha (deixe em branco para manter)</label>
                    <input name='senha' type='password' value={form.senha} onChange={handleChange} className='w-full p-2 bg-white/3 rounded text-sm' />
                  </div>
                  <div className='flex gap-2'>
                    <button type='submit' className='btn-accent py-1 px-2 rounded text-sm'>Salvar</button>
                    <button type='button' className='py-1 px-2 rounded bg-white/5 text-sm' onClick={() => setEditing(false)}>Cancelar</button>
                  </div>
                </form>
              )}
            </div>
          )}
        </div>
      )}
    </div>
  )
}

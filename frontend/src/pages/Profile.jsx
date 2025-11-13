import React, { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom'
import api from '../services/api';
import ConfirmDialog from '../components/ui/ConfirmDialog.jsx'

export default function Profile() {
  const [user, setUser] = useState(null);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false)
  const [editing, setEditing] = useState(false)
  const [form, setForm] = useState({ nome: '', email: '', senha: '' })
  const [success, setSuccess] = useState('')

  useEffect(() => {
    const fetchUser = async () => {
      setLoading(true)
      try {
        const res = await api.get('/api/perfil')
        setUser(res.data)
        setForm({ nome: res.data.nome || '', email: res.data.email || '', senha: '' })
      } catch (err) {
        setError('Erro ao carregar os dados do perfil.')
      } finally {
        setLoading(false)
      }
    }

    fetchUser()
  }, [])

  const handleChange = (e) => setForm({ ...form, [e.target.name]: e.target.value })

  const handleSave = async (e) => {
    e.preventDefault()
    setLoading(true)
    setError('')
    setSuccess('')
    try {
      const payload = { nome: form.nome, email: form.email }
      if (form.senha && form.senha.length > 0) payload.senha = form.senha
      const res = await api.put('/api/usuarios', payload)
      setSuccess(res.data?.mensagem || 'Perfil atualizado com sucesso')
  // atualizar perfil
      const perfil = await api.get('/api/perfil')
      setUser(perfil.data)
      setEditing(false)
      setTimeout(() => setSuccess(''), 4000)
    } catch (err) {
      setError(err?.response?.data?.erro || 'Erro ao atualizar perfil')
    } finally {
      setLoading(false)
    }
  }

  const navigate = useNavigate()

  const [confirmOpen, setConfirmOpen] = useState(false)
  const [deleting, setDeleting] = useState(false)

  const handleDelete = () => {
    setConfirmOpen(true)
  }

  const confirmDelete = async () => {
    setDeleting(true)
    setError('')
    try {
      await api.delete('/api/usuarios')
    // limpar auth local e redirecionar para login
      localStorage.removeItem('token')
      localStorage.removeItem('usuario')
      navigate('/login', { replace: true })
    } catch (err) {
      setError(err?.response?.data?.erro || 'Erro ao deletar usuário')
    } finally {
      setDeleting(false)
      setConfirmOpen(false)
    }
  }

  return (
    <div className="min-h-screen p-8">
      <div className='container-max'>
        <h1 className="text-3xl font-bold mb-6">Perfil do Usuário</h1>

        {loading && <p className='muted'>Carregando...</p>}
        {error && <p className="text-red-400 mb-4">{error}</p>}
        {success && <p className='text-green-400 mb-4'>{success}</p>}

        {user ? (
          <div className='space-y-4'>
            {!editing ? (
                <div className='card p-6'>
                <h2 className='text-2xl font-bold mb-2'>{user.nome}</h2>
                <p><strong>Email:</strong> {user.email}</p>
                <p className='muted'><strong>Ativo:</strong> {user.ativo ? 'Sim' : 'Não'}</p>
                <div className='mt-4 flex gap-2'>
                  <button className='btn-accent py-2 px-3 rounded' onClick={() => { setForm({ nome: user.nome || '', email: user.email || '', senha: '' }); setEditing(true) }}>Editar perfil</button>
                  <button className='py-2 px-3 rounded bg-red-600 text-white' onClick={handleDelete}>Deletar minha conta</button>
                </div>
              </div>
            ) : (
              <form onSubmit={handleSave} className='card p-6' autoComplete='off'>
                <div className='mb-3'>
                  <label className='block muted mb-1'>Nome</label>
                  <input name='nome' value={form.nome} onChange={handleChange} className='w-full p-2 bg-white/3 rounded text-black' />
                </div>
                <div className='mb-3'>
                  <label className='block muted mb-1'>Email</label>
                  <input name='email' type='email' value={form.email} onChange={handleChange} className='w-full p-2 bg-white/3 rounded text-black' />
                </div>
                <div className='mb-3'>
                  <label className='block muted mb-1'>Senha (deixe em branco para manter)</label>
                  <input name='senha' type='password' value={form.senha} onChange={handleChange} className='w-full p-2 bg-white/3 rounded text-black' autoComplete='new-password' />
                </div>
                <div className='flex gap-2'>
                  <button type='submit' disabled={loading} className='btn-accent py-2 px-3 rounded'>Salvar</button>
                  <button type='button' className='py-2 px-3 rounded bg-white/5' onClick={() => setEditing(false)}>Cancelar</button>
                  <button type='button' className='py-2 px-3 rounded bg-red-600 text-white' onClick={handleDelete}>Deletar minha conta</button>
                </div>
              </form>
            )}
          </div>
        ) : (
          <p className='muted'>Sem dados do usuário.</p>
        )}
        <ConfirmDialog open={confirmOpen} title='Confirmação' message='Tem certeza que deseja deletar sua conta? Esta ação não pode ser desfeita.' onCancel={() => setConfirmOpen(false)} onConfirm={confirmDelete} confirmLabel='Deletar' />
      </div>
    </div>
  )
}
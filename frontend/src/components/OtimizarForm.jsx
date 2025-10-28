import React, { useEffect, useState } from 'react'
import api from '../services/api.js'

export default function OtimizarForm({ onCreated }) {
  const [ativos, setAtivos] = useState([])
  const [loadingAtivos, setLoadingAtivos] = useState(false)
  const [form, setForm] = useState({
    nome: '',
    descricao: '',
    perfil_risco: 'medio',
    horizonte_tempo: 365,
    capital: 10000,
    objetivos: '',
    restricoes_ativos: []
  })
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState('')
  const [success, setSuccess] = useState('')

  useEffect(() => {
    const fetch = async () => {
      setLoadingAtivos(true)
      try {
        const res = await api.get('/api/ativos')
        setAtivos(res.data)
      } catch (err) {
        console.error('Erro ao buscar ativos', err)
      } finally {
        setLoadingAtivos(false)
      }
    }
    fetch()
  }, [])

  const handleChange = (e) => {
    const { name, value, type, checked } = e.target
    if (name === 'restricoes_ativos') {
      const id = parseInt(value)
      setForm((f) => ({
        ...f,
        restricoes_ativos: checked ? [...f.restricoes_ativos, id] : f.restricoes_ativos.filter((x) => x !== id)
      }))
    } else {
      setForm({ ...form, [name]: type === 'number' ? Number(value) : value })
    }
  }

  const handleSubmit = async (e) => {
    e.preventDefault()
    setSubmitting(true)
    setError('')
    setSuccess('')
    try {
      const payload = {
        parametros: {
          perfil_risco: form.perfil_risco,
          horizonte_tempo: form.horizonte_tempo,
          capital: form.capital,
          objetivos: form.objetivos,
          restricoes_ativos: form.restricoes_ativos
        },
        info_carteira: {
          nome: form.nome,
          descricao: form.descricao
        }
      }

      const res = await api.post('/api/carteiras/otimizar', payload)
      setSuccess(res.data.mensagem || 'Carteira criada')
      setForm({ nome: '', descricao: '', perfil_risco: 'medio', horizonte_tempo: 365, capital: 10000, objetivos: '', restricoes_ativos: [] })
      if (onCreated) onCreated()
    } catch (err) {
      setError(err?.response?.data?.erro || err.message || 'Erro ao otimizar')
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <form onSubmit={handleSubmit} className='bg-gray-800 p-4 rounded text-gray-200'>
      <div className='grid grid-cols-2 gap-3'>
        <input name='nome' value={form.nome} onChange={handleChange} placeholder='Nome da carteira' className='p-2 bg-gray-700 rounded' required />
        <input name='capital' type='number' value={form.capital} onChange={handleChange} placeholder='Capital (ex: 10000)' className='p-2 bg-gray-700 rounded' />
        <input name='horizonte_tempo' type='number' value={form.horizonte_tempo} onChange={handleChange} placeholder='Horizonte (dias)' className='p-2 bg-gray-700 rounded' />
        <select name='perfil_risco' value={form.perfil_risco} onChange={handleChange} className='p-2 bg-gray-700 rounded'>
          <option value='baixo'>Baixo</option>
          <option value='medio'>Médio</option>
          <option value='alto'>Alto</option>
        </select>
      </div>
      <textarea name='objetivos' value={form.objetivos} onChange={handleChange} placeholder='Objetivos (opcional)' className='w-full mt-3 p-2 bg-gray-700 rounded' />
      <input name='descricao' value={form.descricao} onChange={handleChange} placeholder='Descrição da carteira (opcional)' className='w-full mt-3 p-2 bg-gray-700 rounded' />

      <div className='mt-3'>
        <div className='text-sm font-semibold mb-1'>Restringir ativos (opcional)</div>
        {loadingAtivos && <p className='text-gray-300'>Carregando ativos...</p>}
        <div className='grid grid-cols-2 gap-2 max-h-40 overflow-auto'>
          {ativos.map((a) => (
            <label key={a.id} className='flex items-center gap-2 text-sm'>
              <input type='checkbox' name='restricoes_ativos' value={a.id} checked={form.restricoes_ativos.includes(a.id)} onChange={handleChange} />
              <span>{a.ticker} - {a.nome}</span>
            </label>
          ))}
        </div>
      </div>

      {error && <p className='text-red-400 mt-2'>{error}</p>}
      {success && <p className='text-green-400 mt-2'>{success}</p>}

      <div className='mt-3'>
        <button type='submit' disabled={submitting} className='bg-blue-600 hover:bg-blue-700 p-2 rounded'>
          {submitting ? 'Otimizarando...' : 'Otimizar e Criar'}
        </button>
      </div>
    </form>
  )
}

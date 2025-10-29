import React, { useEffect, useState, useRef } from 'react'
import api from '../services/api.js'
import AssetSelector from './AssetSelector.jsx'
import Spinner from './Spinner.jsx'

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

  const timeoutRef = useRef(null)

  useEffect(() => {
    return () => {
      if (timeoutRef.current) clearTimeout(timeoutRef.current)
    }
  }, [])

  const handleChange = (e) => {
    const { name, value, type } = e.target
    setForm({ ...form, [name]: type === 'number' ? Number(value) : value })
  }

  const handleAssetChange = (selected) => {
    setForm((f) => ({ ...f, restricoes_ativos: selected }))
  }

  const handleSubmit = async (e) => {
    e.preventDefault()
    setSubmitting(true)
    setError('')
    setSuccess('')
    try {
      // validação básica
      if (!form.nome || form.nome.trim().length < 3) {
        setError('Nome da carteira precisa ter ao menos 3 caracteres')
        setSubmitting(false)
        return
      }
      if (!form.capital || Number(form.capital) <= 0) {
        setError('Capital deve ser maior que 0')
        setSubmitting(false)
        return
      }
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
      // limpa mensagem de sucesso após 4s
      timeoutRef.current = setTimeout(() => setSuccess(''), 4000)
    } catch (err) {
      setError(err?.response?.data?.erro || err.message || 'Erro ao otimizar')
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <form onSubmit={handleSubmit} className='bg-gray-800 p-6 rounded text-gray-200 shadow'>
      <div className='grid grid-cols-1 md:grid-cols-2 gap-4'>
        <div>
          <label className='block text-sm text-gray-300 mb-1'>Nome da carteira</label>
          <input name='nome' value={form.nome} onChange={handleChange} className='w-full p-2 bg-gray-700 rounded border border-gray-700 focus:border-blue-500' required />
        </div>

        <div>
          <label className='block text-sm text-gray-300 mb-1'>Capital (R$)</label>
          <input name='capital' type='number' value={form.capital} onChange={handleChange} className='w-full p-2 bg-gray-700 rounded border border-gray-700 focus:border-blue-500' />
        </div>

        <div>
          <label className='block text-sm text-gray-300 mb-1'>Horizonte (dias)</label>
          <input name='horizonte_tempo' type='number' value={form.horizonte_tempo} onChange={handleChange} className='w-full p-2 bg-gray-700 rounded border border-gray-700 focus:border-blue-500' />
        </div>

        <div>
          <label className='block text-sm text-gray-300 mb-1'>Perfil de risco</label>
          <select name='perfil_risco' value={form.perfil_risco} onChange={handleChange} className='w-full p-2 bg-gray-700 rounded border border-gray-700 focus:border-blue-500'>
            <option value='baixo'>Baixo</option>
            <option value='medio'>Médio</option>
            <option value='alto'>Alto</option>
          </select>
        </div>
      </div>

      <div className='mt-4'>
        <label className='block text-sm text-gray-300 mb-1'>Objetivos (opcional)</label>
        <textarea name='objetivos' value={form.objetivos} onChange={handleChange} className='w-full p-2 bg-gray-700 rounded border border-gray-700 focus:border-blue-500' rows={3} />
      </div>

      <div className='mt-4'>
        <label className='block text-sm text-gray-300 mb-1'>Descrição (opcional)</label>
        <input name='descricao' value={form.descricao} onChange={handleChange} className='w-full p-2 bg-gray-700 rounded border border-gray-700 focus:border-blue-500' />
      </div>

      <div className='mt-4'>
        <div className='text-sm font-semibold text-gray-300 mb-2'>Restringir ativos (opcional)</div>
        <AssetSelector assets={ativos} selected={form.restricoes_ativos} onChange={handleAssetChange} loading={loadingAtivos} />
      </div>

      <div className='mt-4 flex items-center justify-between'>
        <div>
          {error && <p className='text-red-400'>{error}</p>}
          {success && <p className='text-green-400'>{success}</p>}
        </div>
        <div>
          <button type='submit' disabled={submitting} className='bg-blue-600 hover:bg-blue-700 p-2 rounded flex items-center gap-2'>
            {submitting && <Spinner size={1} />}
            <span>{submitting ? 'Otimizando...' : 'Otimizar e Criar'}</span>
          </button>
        </div>
      </div>
    </form>
  )
}

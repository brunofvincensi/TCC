import React, { useEffect, useState, useRef } from 'react'
import api from '../services/api.js'
import AssetSelector from './AssetSelector.jsx'
import Spinner from './Spinner.jsx'
import Input from './ui/Input.jsx'
import Button from './ui/Button.jsx'

export default function OtimizarForm({ onCreated }) {
  const [ativos, setAtivos] = useState([])
  const [loadingAtivos, setLoadingAtivos] = useState(false)
  const [form, setForm] = useState({
    nome: '',
    descricao: '',
    perfil_risco: '',
    horizonte_tempo: '',
    capital: '',
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
    if (type === 'number') {
      setForm({ ...form, [name]: value === '' ? '' : Number(value) })
    } else {
      setForm({ ...form, [name]: value })
    }
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
  const created = res.data.carteira
  setForm({ nome: '', descricao: '', perfil_risco: 'medio', horizonte_tempo: 365, capital: 10000, objetivos: '', restricoes_ativos: [] })
  if (onCreated) onCreated(created)
      // limpa mensagem de sucesso após 4s
      timeoutRef.current = setTimeout(() => setSuccess(''), 4000)
    } catch (err) {
      setError(err?.response?.data?.erro || err.message || 'Erro ao otimizar')
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <form onSubmit={handleSubmit} className='card p-6'>
      <div className='grid grid-cols-1 md:grid-cols-2 gap-4'>
        <Input label='Nome da carteira' name='nome' value={form.nome} onChange={handleChange} placeholder='Ex: Carteira Conservadora' />
        <Input label='Capital (R$)' name='capital' type='number' value={form.capital} onChange={handleChange} />
        <Input label='Horizonte (dias)' name='horizonte_tempo' type='number' value={form.horizonte_tempo} onChange={handleChange} />

        <div>
          <label className='block muted mb-1'>Perfil de risco</label>
          <select name='perfil_risco' value={form.perfil_risco} onChange={handleChange} className='w-full p-2 bg-white/3 rounded border border-white/5 focus:border-teal-300 text-black'>
            <option value=''>Selecione...</option>
            <option value='baixo'>Baixo</option>
            <option value='medio'>Médio</option>
            <option value='alto'>Alto</option>
          </select>
        </div>
      </div>

      <div className='mt-4 grid grid-cols-1 md:grid-cols-2 gap-4'>
        <div>
          <label className='block text-sm muted mb-1'>Objetivos (opcional)</label>
          <textarea name='objetivos' value={form.objetivos} onChange={handleChange} className='w-full p-2 bg-white/3 rounded border border-white/5 focus:border-teal-300 text-black placeholder:muted' rows={3} />
        </div>

        <Input label='Descrição (opcional)' name='descricao' value={form.descricao} onChange={handleChange} />
      </div>

      <div className='mt-4'>
        <div className='text-sm font-semibold muted mb-2'>Restringir ativos (opcional)</div>
        <AssetSelector assets={ativos} selected={form.restricoes_ativos} onChange={handleAssetChange} loading={loadingAtivos} />
      </div>

      <div className='mt-4 flex items-center justify-between'>
        <div>
          {error && <p className='text-red-400'>{error}</p>}
          {success && <p className='text-green-400'>{success}</p>}
        </div>
        <div>
          <Button type='submit' disabled={submitting} loading={submitting} className='flex items-center gap-2'>
            {submitting ? 'Otimizando...' : 'Otimizar e Criar'}
          </Button>
        </div>
      </div>
    </form>
  )
}

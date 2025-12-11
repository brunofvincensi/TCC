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
    quantidade_ativos: '',
    possiveis_ativos: []
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
  // padrão: marcar todos os ativos como possíveis (selecionados)
        if (res.data && res.data.length > 0) {
          setForm(f => ({ ...f, possiveis_ativos: res.data.map(a => a.id) }))
        }
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
    setForm((f) => ({ ...f, possiveis_ativos: selected }))
  }

  const getQuantidadeAtivosError = () => {
    if (form.quantidade_ativos === '') return ''
    const num = Number(form.quantidade_ativos)
    if (!Number.isInteger(num)) return 'Deve ser um número inteiro'
    if (num <= 4) return 'Mínimo 5 ativos'
    return ''
  }

  const getHorizonteError = () => {
    if (form.horizonte_tempo === '') return ''
    const num = Number(form.horizonte_tempo)
    if (num < 3) return 'O valor deve ser maior ou igual a 3.'
    return ''
  }

  const handleSubmit = async (e) => {
    e.preventDefault()
    setSubmitting(true)
    setError('')
    setSuccess('')
    try {
      // validação básica: nome, perfil, horizonte, capital e quantidade_ativos são obrigatórios
      if (!form.nome || form.nome.trim().length < 3) {
        setError('Nome da carteira precisa ter ao menos 3 caracteres')
        setSubmitting(false)
        return
      }
      if (!form.perfil_risco) {
        setError('Selecione o perfil de risco')
        setSubmitting(false)
        return
      }
      if (!form.horizonte_tempo || Number(form.horizonte_tempo) < 3) {
        setError('Horizonte (prazo) é obrigatório e deve ser no mínimo 3 anos')
        setSubmitting(false)
        return
      }
  // quantidade_ativos obrigatório e precisa ser inteiro > 4
      if (form.quantidade_ativos === '' || Number(form.quantidade_ativos) <= 4 || !Number.isInteger(Number(form.quantidade_ativos))) {
        setError('Quantidade de ativos é obrigatória e deve ser um número inteiro maior que 4 (mínimo 5)')
        setSubmitting(false)
        return
      }
  // capital é obrigatório e deve ser > 1
      if (form.capital === '' || Number(form.capital) <= 1) {
        setError('Capital (R$) é obrigatório e deve ser maior que 1')
        setSubmitting(false)
        return
      }

  // Construir restricoes como os ativos que NÃO estão selecionados como possíveis
      const possiveis = form.possiveis_ativos || []
      const restricoes = ativos
        .filter(a => !possiveis.includes(a.id))
        .map(a => a.id)

      const parametros = {
        perfil_risco: form.perfil_risco,
        horizonte_tempo: form.horizonte_tempo,
        capital: form.capital,
        restricoes_ativos: restricoes
      }
      parametros.max_ativos = form.quantidade_ativos

      const payload = {
        parametros,
        info_carteira: {
          nome: form.nome,
          descricao: form.descricao
        }
      }

      const res = await api.post('/api/carteiras/otimizar', payload)
      setSuccess(res.data.mensagem || 'Carteira criada')
      const created = res.data.carteira
  setForm({ nome: '', descricao: '', perfil_risco: 'medio', horizonte_tempo: 365, capital: '', quantidade_ativos: '', possiveis_ativos: ativos.map(a => a.id) })
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
      <p className='muted text-sm mb-4'>Campos obrigatórios: <span className='font-medium'>Nome</span>, <span className='font-medium'>Perfil de risco</span>, <span className='font-medium'>Horizonte (prazo)</span>, <span className='font-medium'>Capital (R$)</span> e <span className='font-medium'>Quantidade de ativos</span>.</p>

      <div className='grid grid-cols-1 md:grid-cols-3 gap-4'>
        <Input label={'Nome da carteira *'} name='nome' value={form.nome} onChange={handleChange} placeholder='Ex: Carteira Conservadora' required showError={error !== ''} />

        <div>
          <label className='block muted mb-1'>Perfil de risco *</label>
          <select name='perfil_risco' value={form.perfil_risco} onChange={handleChange} className={`w-full p-2 bg-white/3 rounded border focus:border-teal-300 text-black transition-colors ${
            error !== '' && !form.perfil_risco ? 'border-red-500' : 'border-white/5'
          }`}>
            <option value=''>Selecione...</option>
            <option value='conservador'>Conservador</option>
            <option value='moderado'>Moderado</option>
            <option value='arrojado'>Arrojado</option>
          </select>
        </div>

        <Input label={'Horizonte (anos) *'} name='horizonte_tempo' type='number' value={form.horizonte_tempo} onChange={handleChange} min='3' required showError={error !== ''} errorMessage={getHorizonteError()} />
      </div>

      <div className='mt-4 grid grid-cols-1 md:grid-cols-2 gap-4'>
        <Input label='Capital (R$) *' name='capital' type='number' value={form.capital} onChange={handleChange} min='1' required showError={error !== ''} />
        <Input label='Quantidade de ativos *' name='quantidade_ativos' type='number' value={form.quantidade_ativos} onChange={handleChange} placeholder='Ex: 10' min='5' required showError={error !== ''} errorMessage={getQuantidadeAtivosError()} />
      </div>

      <div className='mt-4'>
        <label className='block text-sm muted mb-1'>Descrição (opcional)</label>
        <textarea name='descricao' value={form.descricao} onChange={handleChange} className='w-full p-2 h-10 bg-white/3 rounded border border-white/5 focus:border-teal-300 text-black placeholder:muted' rows={1} />
      </div>

      <div className='mt-4'>
        <div className='text-sm font-semibold muted mb-2'>Possíveis ativos (marcados = permitidos)</div>
        <AssetSelector assets={ativos} selected={form.possiveis_ativos} onChange={handleAssetChange} loading={loadingAtivos} />
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

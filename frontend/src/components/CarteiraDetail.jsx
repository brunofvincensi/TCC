import React, { useEffect, useState } from 'react'
import api from '../services/api.js'
import PieChart from './PieChart.jsx'

export default function CarteiraDetail({ id }) {
  const [carteira, setCarteira] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  useEffect(() => {
    if (!id) return
    const fetch = async () => {
      setLoading(true)
      setError('')
      try {
        const res = await api.get(`/api/carteiras/${id}`)
        setCarteira(res.data)
      } catch (err) {
        setError(err?.response?.data?.erro || err.message || 'Erro ao carregar carteira')
      } finally {
        setLoading(false)
      }
    }
    fetch()
  }, [id])

  if (loading) return <p className='muted'>Carregando carteira...</p>
  if (error) return <p className='text-red-400'>{error}</p>
  if (!carteira) return null

  return (
    <div className='card p-4'>
      <h4 className='text-lg font-semibold'>{carteira.nome}</h4>
      {carteira.descricao && <p className='text-sm muted'>{carteira.descricao}</p>}
      <p className='text-xs muted mt-1'>Criada em: {new Date(carteira.data_criacao).toLocaleString()}</p>

      {carteira.parametros && (
        <div className='mt-4'>
          <h5 className='font-semibold'>Parâmetros</h5>
          <ul className='text-sm muted'>
            <li>Perfil de risco: {carteira.parametros.perfil_risco_usado}</li>
            <li>Horizonte (anos): {carteira.parametros.horizonte_tempo_usado}</li>
            <li>Capital: {carteira.parametros.capital_usado}</li>
            <li>Objetivos: {carteira.parametros.objetivos_usados}</li>
            {carteira.parametros.restricoes_ativos_ids && (
              <li>Ativos restringidos: {carteira.parametros.restricoes_ativos_ids.join(', ')}</li>
            )}
          </ul>
        </div>
      )}

      <div className='mt-4'>
        <h5 className='font-semibold'>Composição</h5>
        {carteira.composicao && carteira.composicao.length > 0 ? (
          <>
            <table className='w-full text-sm mt-2'>
            <thead>
              <tr className='text-left muted'>
                <th>Ticker</th>
                <th>Nome</th>
                <th>Peso</th>
              </tr>
            </thead>
            <tbody>
              {carteira.composicao.map((item, idx) => {
                const raw = item.peso
                let n = Number(String(raw).replace(',', '.')) || 0
                if (n > 1) n = n / 100
                return (
                  <tr key={idx} className='border-t border-white/5'>
                    <td className='py-2'>{item.ticker}</td>
                    <td className='py-2'>{item.nome_ativo}</td>
                    <td className='py-2'>{(n * 100).toFixed(2)}%</td>
                  </tr>
                )
              })}
            </tbody>
          </table>
            <div className='mt-4'>
              <PieChart items={carteira.composicao.map(a => {
                const raw = a.peso
                let n = Number(String(raw).replace(',', '.')) || 0
                if (n > 1) n = n / 100
                return { label: a.ticker || a.codigo || a.nome_ativo || a.nome, value: n }
              })} />
            </div>
          </>
        ) : (
          <p className='muted'>Sem composição disponível.</p>
        )}
      </div>
    </div>
  )
}

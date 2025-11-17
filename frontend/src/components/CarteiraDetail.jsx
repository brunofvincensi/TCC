import React, { useEffect, useState, useRef } from 'react'
import api from '../services/api.js'
import PieChart from './PieChart.jsx'

export default function CarteiraDetail({ id }) {
  const [carteira, setCarteira] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const containerRef = useRef(null)

  useEffect(() => {
    if (!id) return
    const fetch = async () => {
      setLoading(true)
      setError('')
      try {
        const res = await api.get(`/api/carteiras/${id}`)
        const data = res.data
  // ordenar composição por peso desc
        if (data.composicao && data.composicao.length > 0) {
          data.composicao = data.composicao.slice().sort((a,b) => {
            const pa = Number(String(a.peso).replace(',', '.')) || 0
            const pb = Number(String(b.peso).replace(',', '.')) || 0
            const na = pa > 1 ? pa/100 : pa
            const nb = pb > 1 ? pb/100 : pb
            return nb - na
          })
        }
        setCarteira(data)
  // buscar lista de ativos para mapear ids de restrições para tickers
        if (data.parametros && data.parametros.restricoes_ativos_ids && data.parametros.restricoes_ativos_ids.length > 0) {
          try {
            const r = await api.get('/api/ativos')
            const ativos = r.data || []
            const map = {}
            ativos.forEach(a => { map[a.id] = a.ticker })
            data.parametros.restricoes_ativos_tickers = data.parametros.restricoes_ativos_ids.map(i => map[i] || i)
            setCarteira(data)
          } catch (e) {
            // ignorar
          }
        }
      } catch (err) {
        setError(err?.response?.data?.erro || err.message || 'Erro ao carregar carteira')
      } finally {
        setLoading(false)
      }
    }
    fetch()
  }, [id])

  useEffect(() => {
  // quando a carteira for carregada, garantir que o cartão de detalhe fique visível acima do rodapé da página
    if (carteira && containerRef.current) {
      try {
        containerRef.current.scrollIntoView({ behavior: 'smooth', block: 'center' })
      } catch (e) {
        // ignorar
      }
    }
  }, [carteira])

  if (loading) return <p className='muted'>Carregando carteira...</p>
  if (error) return <p className='text-red-400'>{error}</p>
  if (!carteira) return null

  return (
    <div ref={containerRef} className='card p-4 mb-12 relative'>
      <div className='flex flex-col md:flex-row md:items-center md:justify-between gap-4'>
        <div>
          <h4 className='text-lg font-semibold'>{carteira.nome}</h4>
          {carteira.descricao && <p className='text-sm muted'>{carteira.descricao}</p>}
          <p className='text-xs muted mt-1'>Criada em: {new Date(carteira.data_criacao).toLocaleString()}</p>
        </div>

        {carteira.parametros && (
          <div className='mt-2 md:mt-0 text-sm muted md:text-right'>
            <div><strong>Perfil:</strong> {carteira.parametros.perfil_risco_usado}</div>
            <div><strong>Horizonte:</strong> {carteira.parametros.horizonte_tempo_usado} anos</div>
            <div><strong>Capital:</strong> {carteira.parametros.capital_usado}</div>
            {carteira.parametros.restricoes_ativos_tickers && carteira.parametros.restricoes_ativos_tickers.length > 0 && (
              <div className='mt-1'><strong>Ativos restringidos:</strong> {carteira.parametros.restricoes_ativos_tickers.join(', ')}</div>
            )}
          </div>
        )}
      </div>

      <div className='mt-6'>
          <h5 className='font-semibold mb-2'>Composição</h5>
          {carteira.composicao && carteira.composicao.length > 0 ? (
            <div>
              <div className='w-full overflow-auto max-h-64'>
                <table className='w-full text-sm'>
                  <thead>
                    <tr className='text-left muted'>
                      <th>Ticker</th>
                      <th>Nome</th>
                      <th>Peso</th>
                      <th>Valor (R$)</th>
                    </tr>
                  </thead>
                  <tbody>
                    {carteira.composicao.map((item, idx) => {
                      const raw = item.peso
                      let n = Number(String(raw).replace(',', '.')) || 0
                      if (n > 1) n = n / 100
                      const valorMonetario = item.valor_monetario ? Number(String(item.valor_monetario).replace(',', '.')) : null
                      return (
                        <tr key={idx} className='border-t border-white/5'>
                          <td className='py-2'>{item.ticker}</td>
                          <td className='py-2'>{item.nome_ativo}</td>
                          <td className='py-2'>{(n * 100).toFixed(2)}%</td>
                          <td className='py-2'>{valorMonetario !== null ? `R$ ${valorMonetario.toLocaleString('pt-BR', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}` : '-'}</td>
                        </tr>
                      )
                    })}
                  </tbody>
                </table>
              </div>

              <div className='mt-4 flex items-center justify-center'>
                <PieChart size={180} items={carteira.composicao.map(a => {
                  const raw = a.peso
                  let n = Number(String(raw).replace(',', '.')) || 0
                  if (n > 1) n = n / 100
                  return { label: a.ticker || a.codigo || a.nome_ativo || a.nome, value: n }
                })} />
              </div>
            </div>
          ) : (
            <p className='muted'>Sem composição disponível.</p>
          )}
        </div>
    </div>
  )
}

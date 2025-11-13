import React, { useEffect, useMemo, useState } from 'react'
import api from '../services/api'
import Card from '../components/ui/Card.jsx'
import Button from '../components/ui/Button.jsx'
import Spinner from '../components/Spinner.jsx'
import { useNavigate } from 'react-router-dom'

function PieChart({ items = [], size = 180 }) {
  const totalRaw = items.reduce((s, i) => s + (Number(i.value) || 0), 0)
  if (!items || items.length === 0 || totalRaw === 0) {
    return <div className='muted text-sm'>Sem dados suficientes para gerar o gráfico.</div>
  }
  const total = totalRaw || 1
  const cx = size / 2
  const cy = size / 2
  const radius = Math.min(cx, cy) - 4

  let cumulative = 0
  const slices = items.map((it, idx) => {
    const value = Number(it.value) || 0
    const start = cumulative / total * Math.PI * 2
    cumulative += value
    const end = cumulative / total * Math.PI * 2
    const largeArc = end - start > Math.PI ? 1 : 0
    const startX = cx + radius * Math.cos(start - Math.PI / 2)
    const startY = cy + radius * Math.sin(start - Math.PI / 2)
    const endX = cx + radius * Math.cos(end - Math.PI / 2)
    const endY = cy + radius * Math.sin(end - Math.PI / 2)
    const color = `hsl(${(idx * 65) % 360} 70% 55%)`
    const path = `M ${cx} ${cy} L ${startX} ${startY} A ${radius} ${radius} 0 ${largeArc} 1 ${endX} ${endY} Z`
    return { path, color, label: it.label, pct: total ? (value / total) : 0 }
  })

  return (
    <div className='flex items-center gap-4'>
      <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`} className='rounded'>
        {slices.map((s, i) => (
          <path key={i} d={s.path} fill={s.color} stroke='rgba(255,255,255,0.03)' strokeWidth={1} />
        ))}
        {/* removed inner circle to show full pie (no donut hole) */}
      </svg>

      <div className='text-sm'>
        {slices.map((s, i) => (
          <div key={i} className='flex items-center gap-2 mb-2'>
            <span style={{ width: 12, height: 12, background: s.color }} className='inline-block rounded-sm' />
            <span className='muted'>{s.label}</span>
            <span className='ml-2 font-medium'>{(s.pct * 100).toFixed(1)}%</span>
          </div>
        ))}
      </div>
    </div>
  )
}

export default function Dashboard() {
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [carteiras, setCarteiras] = useState([])
  const [previews, setPreviews] = useState([])
  const [mainPreview, setMainPreview] = useState(null)
  const [detailsCache, setDetailsCache] = useState({})
  const navigate = useNavigate()

  const fetchCarteiras = async () => {
    setLoading(true)
    setError('')
    try {
      const res = await api.get('/api/carteiras')
      const list = res.data || []
      setCarteiras(list)
  // buscar detalhes das primeiras carteiras para montar prévias e métricas
  // aumentar para as primeiras 6 para tornar 'Ativos preview' e topExposure mais representativos
  const firstIds = list.slice(0, 6).map((c) => c.id)
  const detailPromises = firstIds.map((id) => api.get(`/api/carteiras/${id}`).then(r => r.data).catch(() => null))
  const details = await Promise.all(detailPromises)
  const filt = details.filter(Boolean)
  setPreviews(filt)
  setMainPreview((prev) => prev || filt[0] || null)
  // cachear os detalhes
      const cache = {}
      filt.forEach(d => { if (d && d.id) cache[d.id] = d })
      setDetailsCache(cache)
    } catch (err) {
      setError(err?.response?.data?.erro || err.message || 'Erro ao carregar carteiras')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { fetchCarteiras() }, [])

  const totals = useMemo(() => {
    const totalCarteiras = carteiras.length
    const totalAtivos = previews.reduce((acc, p) => acc + (p.composicao ? p.composicao.length : 0), 0)
    const parsePeso = (raw) => {
      if (raw == null) return 0
      const n = Number(String(raw).replace(',', '.')) || 0
      return n > 1 ? n / 100 : n
    }
    const topExposure = previews.reduce((acc, p) => {
      if (!p.composicao || p.composicao.length === 0) return acc
      const maxPeso = Math.max(...p.composicao.map(a => parsePeso(a.peso)))
      return Math.max(acc, maxPeso)
    }, 0)
    return { totalCarteiras, totalAtivos, topExposure }
  }, [carteiras, previews])

  // estado mainPreview é gerenciado acima

  return (
    <div>
      <div className='flex items-center justify-end mb-6'>
        <div className='flex items-center gap-3'>
          <Button variant='ghost' onClick={() => fetchCarteiras()}>
            {loading ? <Spinner size={0.8} /> : 'Atualizar'}
          </Button>
          <Button onClick={() => navigate('/carteiras')}>Gerenciar carteiras</Button>
        </div>
      </div>

      {error && <p className='text-red-400 mb-4'>{error}</p>}

      <div className='grid grid-cols-1 md:grid-cols-3 gap-4 mb-6'>
        <Card className='p-4'>
          <div className='text-sm muted'>Carteiras</div>
          <div className='text-2xl font-semibold mt-2'>{totals.totalCarteiras}</div>
          <div className='muted text-sm mt-1'>Carteiras ativas na sua conta</div>
        </Card>

        <Card className='p-4'>
          <div className='text-sm muted'>Ativos preview</div>
          <div className='text-2xl font-semibold mt-2'>{totals.totalAtivos}</div>
          <div className='muted text-sm mt-1'>Ativos nas carteiras visualizadas</div>
        </Card>

        <Card className='p-4'>
          <div className='text-sm muted'>Maior exposição</div>
          <div className='text-2xl font-semibold mt-2'>{(totals.topExposure * 100).toFixed(1)}%</div>
          <div className='muted text-sm mt-1'>Maior peso de um ativo nas carteiras</div>
        </Card>
      </div>

      {loading && <div className='p-6'><Spinner /></div>}

      {!loading && !mainPreview && (
        <Card className='p-6'>
          <p className='muted'>Nenhuma carteira disponível para pré-visualização.</p>
          <div className='mt-4 flex gap-2'>
            <Button onClick={() => navigate('/carteiras')}>Criar carteira</Button>
          </div>
        </Card>
      )}

      {!loading && mainPreview && (
        <div className='grid grid-cols-1 md:grid-cols-2 gap-4'>
          <Card className='p-4'>
            <div className='flex items-center justify-between'>
              <div>
                <div className='font-semibold text-lg'>{mainPreview.nome}</div>
                {mainPreview.descricao && <div className='muted text-sm'>{mainPreview.descricao}</div>}
                {mainPreview.data_criacao && <div className='muted text-xs mt-2'>Criada em: {new Date(mainPreview.data_criacao).toLocaleDateString()}</div>}
              </div>
              <div className='text-xs muted text-right'>Ativos: <strong>{mainPreview.composicao ? mainPreview.composicao.length : 0}</strong></div>
            </div>

            <div className='mt-3'>
              <label className='block text-sm muted mb-2'>Mostrar carteira</label>
              <select
                className='w-full p-2 bg-white/3 rounded border border-white/5 focus:border-teal-300 text-black'
                value={mainPreview?.id || ''}
                onChange={async (e) => {
                  const id = Number(e.target.value)
                  if (!id) return
                  // se em cache, usar
                  if (detailsCache[id]) {
                    setMainPreview(detailsCache[id])
                    return
                  }
                  setLoading(true)
                  try {
                    const res = await api.get(`/api/carteiras/${id}`)
                    const data = res.data
                    setMainPreview(data)
                    setDetailsCache(prev => ({ ...prev, [id]: data }))
                  } catch (err) {
                    setError('Erro ao carregar carteira selecionada')
                  } finally {
                    setLoading(false)
                  }
                }}
              >
                {carteiras.map(c => (
                  <option key={c.id} value={c.id}>{c.nome}</option>
                ))}
              </select>
            </div>

            <div className='mt-4'>
              <div className='text-sm font-medium mb-2'>Composição (Top ativos)</div>
              {mainPreview.composicao && mainPreview.composicao.length > 0 ? (
                <PieChart items={mainPreview.composicao.slice().sort((x,y) => {
                  const pa = Number(String(x.peso).replace(',', '.')) || 0
                  const pb = Number(String(y.peso).replace(',', '.')) || 0
                  const na = pa > 1 ? pa/100 : pa
                  const nb = pb > 1 ? pb/100 : pb
                  return nb - na
                }).slice(0,8).map(a => {
                  const raw = a.peso
                  const n = Number(String(raw).replace(',', '.')) || 0
                  const value = n > 1 ? n / 100 : n
                  return { label: a.ticker || a.codigo || a.nome_ativo || a.nome, value }
                })} />
              ) : (
                <div className='muted text-sm'>Sem composição disponível</div>
              )}
            </div>

            <div className='mt-4 flex justify-end'>
              <Button onClick={() => navigate(`/carteiras?id=${mainPreview.id}`)}>Ver detalhes</Button>
            </div>
          </Card>

          <Card className='p-4'>
            <div className='text-sm muted'>Outras carteiras</div>
            <div className='mt-3 space-y-3'>
              {previews.slice(1).map(p => (
                <div key={p.id} className='flex items-center justify-between'>
                  <div>
                    <div className='font-medium'>{p.nome}</div>
                    {p.descricao && <div className='muted text-sm'>{p.descricao}</div>}
                  </div>
                  <div className='muted text-sm'>{p.composicao ? p.composicao.length : 0} ativos</div>
                </div>
              ))}
            </div>
          </Card>
        </div>
      )}
    </div>
  )
}

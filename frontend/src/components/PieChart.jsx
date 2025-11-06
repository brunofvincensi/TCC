import React from 'react'

export default function PieChart({ items = [], size = 180 }) {
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

import React, { useMemo, useState } from 'react'

export default function AssetSelector({ assets = [], selected = [], onChange, loading }) {
  const [q, setQ] = useState('')

  const filtered = useMemo(() => {
    const term = q.trim().toLowerCase()
    if (!term) return assets
    return assets.filter((a) => (a.ticker || '').toLowerCase().includes(term) || (a.nome || '').toLowerCase().includes(term))
  }, [assets, q])

  const toggle = (id) => {
    if (selected.includes(id)) onChange(selected.filter((x) => x !== id))
    else onChange([...selected, id])
  }

  const toggleAll = () => {
    const filteredIds = filtered.map((a) => a.id)
    const allSelected = filteredIds.every((id) => selected.includes(id))
    if (allSelected) {
      onChange(selected.filter((id) => !filteredIds.includes(id)))
    } else {
      const newSelected = new Set(selected)
      filteredIds.forEach((id) => newSelected.add(id))
      onChange(Array.from(newSelected))
    }
  }

  const filteredIds = filtered.map((a) => a.id)
  const allSelected = filteredIds.length > 0 && filteredIds.every((id) => selected.includes(id))
  const someSelected = filteredIds.some((id) => selected.includes(id))

  return (
    <div>
      <div className='flex items-center gap-2 mb-2'>
        <input
          aria-label='Pesquisar ativos'
          className='flex-1 p-2 bg-gray-700 rounded border border-gray-700 focus:border-blue-500'
          placeholder='Pesquisar por ticker ou nome'
          value={q}
          onChange={(e) => setQ(e.target.value)}
        />
        <div className='text-sm text-gray-400'>{selected.length} selecionados</div>
      </div>

      <div className='max-h-48 overflow-auto p-2 bg-gray-900 rounded border border-gray-800'>
        <label className='flex items-center gap-2 p-2 bg-gray-800 rounded hover:bg-gray-700 cursor-pointer mb-2'>
          <input
            type='checkbox'
            checked={allSelected}
            ref={(el) => {
              if (el) el.indeterminate = someSelected && !allSelected
            }}
            onChange={toggleAll}
            aria-checked={allSelected}
            className='w-4 h-4'
          />
          <div className='text-sm font-medium text-gray-100'>Selecionar todos</div>
        </label>

        <div className='grid grid-cols-1 sm:grid-cols-2 gap-2'>
          {loading && <div className='text-gray-300'>Carregando ativos...</div>}
          {!loading && filtered.length === 0 && <div className='text-gray-400'>Nenhum ativo encontrado.</div>}
          {!loading && filtered.map((a) => (
            <label key={a.id} className='flex items-center gap-2 p-2 bg-gray-800 rounded hover:bg-gray-700 cursor-pointer'>
              <input
                type='checkbox'
                checked={selected.includes(a.id)}
                onChange={() => toggle(a.id)}
                aria-checked={selected.includes(a.id)}
                className='w-4 h-4'
              />
              <div className='text-sm'>
                <div className='font-medium text-gray-100'>{a.ticker}</div>
                <div className='text-xs text-gray-400'>{a.nome}</div>
              </div>
            </label>
          ))}
        </div>
      </div>
    </div>
  )
}

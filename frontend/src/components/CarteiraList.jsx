import React from 'react'

export default function CarteiraList({ carteiras = [], onSelect, onDelete }) {
  if (!carteiras || carteiras.length === 0) {
    return <p className='muted'>Nenhuma carteira encontrada.</p>
  }

  return (
    <ul className='space-y-3'>
      {carteiras.map((c) => (
        <li key={c.id} className='card p-3 flex items-center justify-between'>
          <div>
            <button className='text-left' onClick={() => onSelect(c.id)}>
              <div className='font-semibold'>{c.nome}</div>
              {c.descricao && <div className='text-sm muted'>{c.descricao}</div>}
            </button>
          </div>
          <div className='flex gap-2'>
            <button
              onClick={() => onDelete(c.id)}
              className='text-sm text-red-400 hover:underline'
            >
              Deletar
            </button>
          </div>
        </li>
      ))}
    </ul>
  )
}

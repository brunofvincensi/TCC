import React from 'react'

export default function ConfirmDialog({ open, title, message, onCancel, onConfirm, confirmLabel = 'Confirmar', cancelLabel = 'Cancelar', dark = false }) {
  if (!open) return null
  return (
    <div className='fixed inset-0 z-50 flex items-center justify-center'>
      {/* sobreposição mais escura para garantir que o modal se destaque */}
      <div className='absolute inset-0 bg-black/80 backdrop-blur-sm' onClick={onCancel} />
      <div className={`${dark ? 'bg-black/95' : 'bg-card'} p-4 rounded shadow-lg w-full max-w-md z-10 border border-white/6` }>
        {title && <div className='text-lg font-semibold mb-2'>{title}</div>}
        <div className='muted mb-4'>{message}</div>
        <div className='flex justify-end gap-2'>
          <button className='py-2 px-3 rounded bg-white/5' onClick={onCancel}>{cancelLabel}</button>
          <button className='py-2 px-3 rounded bg-red-600 text-white' onClick={onConfirm}>{confirmLabel}</button>
        </div>
      </div>
    </div>
  )
}

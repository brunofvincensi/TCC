import React, { useRef, useState, useEffect } from 'react'
import { Link } from 'react-router-dom'

// O popover original usava edição/deleção inline com confirm do navegador.
// O app agora usa a página /perfil. Mantenha este componente como uma âncora leve
// de navegação para o perfil em vez de duplicar a UI de edição/deleção aqui.
export default function UserPopover() {
  const ref = useRef(null)
  const [open, setOpen] = useState(false)
  const current = (() => { try { return JSON.parse(localStorage.getItem('usuario')) } catch { return null } })()

  useEffect(() => {
    const onDoc = (e) => {
      if (ref.current && !ref.current.contains(e.target)) setOpen(false)
    }
    document.addEventListener('click', onDoc)
    return () => document.removeEventListener('click', onDoc)
  }, [])

  return (
    <div className='relative' ref={ref}>
      <button onClick={() => setOpen(v => !v)} className='font-semibold mt-1'>{current?.nome ?? 'Usuário'}</button>
      {open && (
        <div className='absolute left-0 mt-2 w-56 bg-white/5 p-3 rounded shadow-lg z-50'>
          <div className='mb-2'><strong>{current?.nome}</strong></div>
          <div className='muted text-sm mb-3'>{current?.email}</div>
          <div className='flex gap-2'>
            <Link to='/perfil' className='btn-accent py-1 px-2 rounded text-sm'>Ir para perfil</Link>
            <button className='py-1 px-2 rounded bg-white/5 text-sm' onClick={() => setOpen(false)}>Fechar</button>
          </div>
        </div>
      )}
    </div>
  )
}

import React, { useEffect, useState } from 'react'
import CarteiraList from '../components/CarteiraList.jsx'
import CarteiraDetail from '../components/CarteiraDetail.jsx'
import OtimizarForm from '../components/OtimizarForm.jsx'
import api from '../services/api.js'
import ConfirmDialog from '../components/ui/ConfirmDialog.jsx'
import { useLocation } from 'react-router-dom'

export default function Carteiras() {
  const [carteiras, setCarteiras] = useState([])
  const [selectedId, setSelectedId] = useState(null)
  const [showForm, setShowForm] = useState(false)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [confirmOpen, setConfirmOpen] = useState(false)
  const [deletingId, setDeletingId] = useState(null)
  const location = useLocation()

  const fetchCarteiras = async (preferredId = null) => {
    setLoading(true)
    setError('')
    try {
  const res = await api.get('/api/carteiras')
  setCarteiras(res.data)
  // se houver carteiras e nenhuma selecionada, selecionar a primeira
      if (res.data && res.data.length > 0) {
        if (preferredId) {
          // preferir o id passado pela URL/navegação
          const asNum = Number(preferredId)
          const exists = res.data.find(c => Number(c.id) === asNum)
          if (exists) setSelectedId(asNum)
          else setSelectedId(res.data[0].id)
        } else if (!selectedId) {
          setSelectedId(res.data[0].id)
        }
  // manter formulário oculto por padrão quando existirem carteiras
        setShowForm(false)
      } else {
        // sem carteiras: mostrar o formulário para criar uma
        setShowForm(true)
      }
    } catch (err) {
      setError(err?.response?.data?.erro || err.message || 'Erro ao buscar carteiras')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
  // checar param da URL para id selecionado e passar para fetch
    const params = new URLSearchParams(location.search)
    const idParam = params.get('id')
    fetchCarteiras(idParam)
  }, [location.search])

  const handleSelect = (id) => setSelectedId(id)

  const handleDelete = (id) => {
    setDeletingId(id)
    setConfirmOpen(true)
  }

  const confirmDelete = async () => {
    if (!deletingId) return
    try {
      await api.delete(`/api/carteiras/${deletingId}`)
      // refresh
      fetchCarteiras()
      setSelectedId(null)
    } catch (err) {
      setError(err?.response?.data?.erro || err.message || 'Erro ao deletar')
    } finally {
      setConfirmOpen(false)
      setDeletingId(null)
    }
  }

  const handleOptimizedCreated = (created) => {
    // called after otimizar creates a carteira
    fetchCarteiras()
    // if backend returned the created carteira, select it
    if (created && created.id) {
      setSelectedId(created.id)
    }
  }

  return (
    <div className='flex gap-6'>
      <div className='w-1/3'>
        <h2 className='text-xl font-bold mb-4'>Minhas Carteiras</h2>
        {loading && <p className='muted'>Carregando...</p>}
        {error && <p className='text-red-400'>{error}</p>}
        <div className='card p-3'>
            <CarteiraList carteiras={carteiras} onSelect={handleSelect} onDelete={handleDelete} />
        </div>
          <ConfirmDialog open={confirmOpen} title='Confirmação' message='Deseja realmente deletar esta carteira?' onCancel={() => setConfirmOpen(false)} onConfirm={confirmDelete} confirmLabel='Deletar' dark={true} />

          {/* Add new-carteira button placed below the list */}
          <div className='mt-4'>
            <button
              aria-label='Adicionar carteira'
              title='Adicionar carteira'
              onClick={() => setShowForm(true)}
              className='w-full py-2 rounded btn-accent flex items-center justify-center gap-2'
            >
              <svg xmlns='http://www.w3.org/2000/svg' className='h-4 w-4' viewBox='0 0 20 20' fill='currentColor'>
                <path fillRule='evenodd' d='M10 5a1 1 0 011 1v3h3a1 1 0 110 2h-3v3a1 1 0 11-2 0v-3H6a1 1 0 110-2h3V6a1 1 0 011-1z' clipRule='evenodd' />
              </svg>
              <span>Adicionar carteira</span>
            </button>
          </div>
      </div>

      <div className='flex-1'>
        <h2 className='text-xl font-bold mb-4'>Detalhes / Otimização</h2>

        {showForm ? (
          // When showing the form, hide the previous presentation and show only the form with a close button
          <div>
            <div className='flex justify-end mb-2'>
              <button
                aria-label='Fechar formulário'
                onClick={() => setShowForm(false)}
                className='p-2 rounded bg-white/5 hover:bg-white/8'
              >
                <svg xmlns='http://www.w3.org/2000/svg' className='h-4 w-4 text-white' fill='none' viewBox='0 0 24 24' stroke='currentColor'>
                  <path strokeLinecap='round' strokeLinejoin='round' strokeWidth={2} d='M6 18L18 6M6 6l12 12' />
                </svg>
              </button>
            </div>
            <OtimizarForm onCreated={(created) => { handleOptimizedCreated(created); setShowForm(false) }} />
          </div>
        ) : selectedId ? (
          <div className='space-y-4'>
            <CarteiraDetail id={selectedId} />

            {/* Button removed: use the 'Adicionar carteira' button in the left column instead */}
          </div>
        ) : (
          <div className='card p-4'>
            <p className='muted'>Nenhuma carteira selecionada.</p>
            {/* If there are no carteiras, show the form by default */}
                {showForm && (
              <div className='mt-4'>
                <OtimizarForm onCreated={(created) => { handleOptimizedCreated(created); setShowForm(false) }} />
              </div>
            )}
            {/* Empty state: creation button removed from right column; use left column button */}
            { !showForm && carteiras.length === 0 && (
              <div className='mt-4'>
                <p className='muted'>Crie sua primeira carteira usando o botão à esquerda.</p>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  )
}

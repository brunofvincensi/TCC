import React, { useEffect, useState } from 'react'
import CarteiraList from '../components/CarteiraList.jsx'
import CarteiraDetail from '../components/CarteiraDetail.jsx'
import OtimizarForm from '../components/OtimizarForm.jsx'
import api from '../services/api.js'

export default function Carteiras() {
  const [carteiras, setCarteiras] = useState([])
  const [selectedId, setSelectedId] = useState(null)
  const [showForm, setShowForm] = useState(false)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  const fetchCarteiras = async () => {
    setLoading(true)
    setError('')
    try {
      const res = await api.get('/api/carteiras')
      setCarteiras(res.data)
      // if there are carteiras and none selected, select the first
      if (res.data && res.data.length > 0) {
        if (!selectedId) {
          setSelectedId(res.data[0].id)
        }
        // keep form hidden by default when there are carteiras
        setShowForm(false)
      } else {
        // no carteiras: show the form to create one
        setShowForm(true)
      }
    } catch (err) {
      setError(err?.response?.data?.erro || err.message || 'Erro ao buscar carteiras')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    fetchCarteiras()
  }, [])

  const handleSelect = (id) => setSelectedId(id)

  const handleDelete = async (id) => {
    if (!confirm('Deseja realmente deletar esta carteira?')) return
    try {
      await api.delete(`/api/carteiras/${id}`)
      // refresh
      fetchCarteiras()
      setSelectedId(null)
    } catch (err) {
      alert(err?.response?.data?.erro || err.message || 'Erro ao deletar')
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

            <div className='flex justify-end'>
              <button
                aria-label='Adicionar nova carteira'
                className='p-2 rounded btn-accent'
                onClick={() => setShowForm(true)}
                title='Adicionar nova carteira'
              >
                <svg xmlns='http://www.w3.org/2000/svg' className='h-5 w-5' viewBox='0 0 20 20' fill='currentColor'>
                  <path fillRule='evenodd' d='M10 5a1 1 0 011 1v3h3a1 1 0 110 2h-3v3a1 1 0 11-2 0v-3H6a1 1 0 110-2h3V6a1 1 0 011-1z' clipRule='evenodd' />
                </svg>
              </button>
            </div>
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
            {!showForm && carteiras.length === 0 && (
              <div className='mt-4 flex justify-center'>
                <button aria-label='Criar primeira carteira' className='btn-accent p-3 rounded-full' onClick={() => setShowForm(true)}>
                  <svg xmlns='http://www.w3.org/2000/svg' className='h-5 w-5' viewBox='0 0 20 20' fill='currentColor'>
                    <path fillRule='evenodd' d='M10 5a1 1 0 011 1v3h3a1 1 0 110 2h-3v3a1 1 0 11-2 0v-3H6a1 1 0 110-2h3V6a1 1 0 011-1z' clipRule='evenodd' />
                  </svg>
                </button>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  )
}

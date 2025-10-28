import React, { useEffect, useState } from 'react'
import CarteiraList from '../components/CarteiraList.jsx'
import CarteiraDetail from '../components/CarteiraDetail.jsx'
import OtimizarForm from '../components/OtimizarForm.jsx'
import api from '../services/api.js'

export default function Carteiras() {
  const [carteiras, setCarteiras] = useState([])
  const [selectedId, setSelectedId] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  const fetchCarteiras = async () => {
    setLoading(true)
    setError('')
    try {
      const res = await api.get('/api/carteiras')
      setCarteiras(res.data)
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

  const handleOptimizedCreated = () => {
    // called after otimizar creates a carteira
    fetchCarteiras()
  }

  return (
    <div className='flex gap-6'>
      <div className='w-1/3'>
        <h2 className='text-xl font-bold mb-4 text-white'>Minhas Carteiras</h2>
        {loading && <p className='text-gray-300'>Carregando...</p>}
        {error && <p className='text-red-400'>{error}</p>}
        <CarteiraList carteiras={carteiras} onSelect={handleSelect} onDelete={handleDelete} />
      </div>

      <div className='flex-1'>
        <h2 className='text-xl font-bold mb-4 text-white'>Detalhes / Otimização</h2>
        {selectedId ? (
          <CarteiraDetail id={selectedId} />
        ) : (
          <div className='bg-gray-800 p-4 rounded text-gray-200'>
            <p>Selecione uma carteira à esquerda para ver os detalhes.</p>
          </div>
        )}

        <div className='mt-6'>
          <h3 className='text-lg font-semibold text-white mb-2'>Otimizar e criar nova carteira</h3>
          <OtimizarForm onCreated={handleOptimizedCreated} />
        </div>
      </div>
    </div>
  )
}

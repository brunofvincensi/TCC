export default function Dashboard() {
  return (
    <div>
      <h2 className='text-2xl font-semibold mb-4'>Bem-vindo ao painel</h2>
      <div className='grid grid-cols-1 md:grid-cols-3 gap-4'>
        <div className='bg-gray-800 p-4 rounded-lg shadow'>📈 Retorno esperado</div>
        <div className='bg-gray-800 p-4 rounded-lg shadow'>⚖️ Risco total</div>
        <div className='bg-gray-800 p-4 rounded-lg shadow'>💼 Diversificação</div>
      </div>
    </div>
  )
}

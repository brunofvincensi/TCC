import { Link, Outlet, useNavigate } from 'react-router-dom'
import logo from '../assets/walletai.png'

export default function Layout() {
  const navigate = useNavigate()
  const usuario = (() => {
    try {
      return JSON.parse(localStorage.getItem('usuario'))
    } catch (e) {
      return null
    }
  })()

  const handleLogout = () => {
    // Remove token and user info from localStorage and redirect to login
    localStorage.removeItem('token')
    localStorage.removeItem('usuario')
    navigate('/login', { replace: true })
  }

  return (
    <div className='flex min-h-screen'>
      <aside className='w-64 p-6'>
        <div className='card p-4'>
          <div className='mb-4'>
            <img src={logo} alt='Logo' className='w-full h-24 object-cover rounded-md shadow-sm' />
          </div>
          <nav className='space-y-3'>
            <Link to='/dashboard' className='block text-gray-200 hover:accent'>Dashboard</Link>
            <Link to='/carteiras' className='block text-gray-200 hover:accent'>Carteiras</Link>
          </nav>
          <div className='mt-4 border-t border-white/5 pt-4'>
            <div className='text-sm text-gray-300'>Conectado como</div>
            <div className='font-semibold mt-1'>{usuario?.nome ?? 'Usuário'}</div>
            <button
              onClick={handleLogout}
              className='mt-3 w-full py-2 rounded-md btn-accent text-sm font-medium'>
              Logout
            </button>
          </div>
        </div>
      </aside>

      <div className='flex-1 p-6 bg-transparent'>
        <header className='mb-6'>
          <div className='container-max'>
            <div className='flex items-center justify-between'>
              <h1 className='text-2xl font-semibold'>Painel</h1>
              <div className='flex items-center gap-3'>
                <input
                  type='search'
                  placeholder='Pesquisar...'
                  className='px-3 py-2 rounded-md bg-white/3 text-sm text-gray-100 placeholder:muted focus:outline-none focus:ring-2 focus:ring-teal-300'
                />
              </div>
            </div>
          </div>
        </header>

        <div className='container-max'>
          <Outlet />
        </div>
      </div>
    </div>
  )
}

import { Link, Outlet, useNavigate } from 'react-router-dom'
import logo from '../assets/walletai.png'
// Popover de usuário substituído por página de perfil dedicada

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
            <div className='mt-1'>
              <button onClick={() => navigate('/perfil')} className='font-semibold'>{usuario?.nome ?? 'Usuário'}</button>
            </div>
            <div className='mt-3'>
              <button
                onClick={handleLogout}
                className='w-full py-2 rounded-md btn-accent text-sm font-medium'>
                Logout
              </button>
            </div>
          </div>
        </div>
      </aside>

  <div className='flex-1 p-6 bg-transparent pb-20'>
        <header className='mb-6'>
          <div className='container-max'>
              <div className='flex items-center justify-between'>
                {/* Header removed: each page should render its own title */}
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

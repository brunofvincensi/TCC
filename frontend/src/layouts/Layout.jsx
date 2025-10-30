import { Link, Outlet, useNavigate } from 'react-router-dom'

export default function Layout() {
  const navigate = useNavigate()

  const handleLogout = () => {
    // Remove token and user info from localStorage and redirect to login
    localStorage.removeItem('token')
    localStorage.removeItem('usuario')
    navigate('/login', { replace: true })
  }

  return (
    <div className='flex min-h-screen bg-gray-900 text-gray-100'>
      <aside className='w-64 bg-gray-800 p-6'>
        <h1 className='text-xl font-bold mb-6'>Definir nome</h1>
        <nav className='space-y-3'>
          <Link to='/dashboard' className='block hover:text-blue-400'>Dashboard</Link>
          <Link to='/carteiras' className='block hover:text-blue-400'>Carteiras</Link>
          <button onClick={handleLogout} className='block text-left text-blue-400 hover:underline'>Logout</button>
        </nav>
      </aside>
      <main className='flex-1 p-6'>
        <Outlet />
      </main>
    </div>
  )
}

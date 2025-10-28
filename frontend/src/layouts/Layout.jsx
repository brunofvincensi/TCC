import { Link, Outlet } from 'react-router-dom'

export default function Layout() {
  return (
    <div className='flex min-h-screen bg-gray-900 text-gray-100'>
      <aside className='w-64 bg-gray-800 p-6'>
        <h1 className='text-xl font-bold mb-6'>Portfolio AI</h1>
        <nav className='space-y-3'>
          <Link to='/dashboard' className='block hover:text-blue-400'>Dashboard</Link>
          <Link to='/carteiras' className='block hover:text-blue-400'>Carteiras</Link>
          <Link to='/' className='block hover:text-blue-400'>Sair</Link>
        </nav>
      </aside>
      <main className='flex-1 p-6'>
        <Outlet />
      </main>
    </div>
  )
}

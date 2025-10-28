import { BrowserRouter, Routes, Route } from 'react-router-dom'
import Login from './pages/Login.jsx'
import Register from './pages/Register.jsx'
import Dashboard from './pages/Dashboard.jsx'
import Carteiras from './pages/Carteiras.jsx'
import Layout from './layouts/Layout.jsx'

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path='/' element={<Login />} />
        <Route path='/login' element={<Login />} />
        <Route path='/register' element={<Register />} />

        {/* Protected / app routes inside Layout */}
        <Route element={<Layout /> }>
          <Route path='/dashboard' element={<Dashboard />} />
          <Route path='/carteiras' element={<Carteiras />} />
        </Route>
      </Routes>
    </BrowserRouter>
  )
}

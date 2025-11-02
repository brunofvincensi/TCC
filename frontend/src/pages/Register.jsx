import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import api from '../services/api.js';
import Input from '../components/ui/Input.jsx'
import Button from '../components/ui/Button.jsx'
import Card from '../components/ui/Card.jsx'
import logo from '../assets/walletai.png'

export default function Register() {
  const navigate = useNavigate();
  const [formData, setFormData] = useState({
    nome: '',
    email: '',
    senha: '',
  });
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  const handleChange = (e) => {
    setFormData({ ...formData, [e.target.name]: e.target.value });
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setLoading(true);
    setError('');
    try {
  await api.post('/api/usuarios', formData);
      navigate('/login');
    } catch (err) {
      const backendError = err?.response?.data?.erro || err?.response?.data?.message || err?.message;
      setError(backendError || 'Erro ao registrar. Tente novamente.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className='relative min-h-screen flex items-center justify-center overflow-hidden'>
      <div className='absolute inset-0 -z-10'>
        <img src={logo} alt='' className='w-full h-full object-cover filter blur-lg opacity-60 scale-110' />
        <div className='absolute inset-0 bg-black/60'></div>
      </div>

      <form onSubmit={handleSubmit} className='w-96 relative z-10'>
        <div className='flex flex-col items-center mb-4'>
          <img src={logo} alt='Logo' className='w-20 h-20 object-cover rounded-full ring-2 ring-blue-600/40 shadow-md bg-white/5' />
          <div className='mt-2 text-center'>
            <div className='text-white font-semibold text-lg'>Criar conta</div>
            <div className='text-xs muted'>Bem-vindo(a)! Crie sua conta para começar</div>
          </div>
        </div>

        <Card className='p-6 backdrop-blur-sm bg-white/5'>
          <div className='space-y-3'>
            <Input label='Nome' name='nome' value={formData.nome} onChange={handleChange} required />
            <Input label='Email' name='email' type='email' value={formData.email} onChange={handleChange} required />
            <Input label='Senha' name='senha' type='password' value={formData.senha} onChange={handleChange} required />
          </div>
        </Card>
        {error && <p className="text-red-400 text-sm mb-2">{error}</p>}
        <div className='mt-4'>
          <Button type='submit' className='w-full py-2' loading={loading} disabled={loading}>Cadastrar</Button>
        </div>
      </form>
    </div>
  );
}
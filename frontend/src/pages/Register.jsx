import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import api from '../services/api.js';
import Input from '../components/ui/Input.jsx'
import Button from '../components/ui/Button.jsx'
import Card from '../components/ui/Card.jsx'

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
    <div className="flex items-center justify-center min-h-screen">
      <form onSubmit={handleSubmit} className="w-96">
        <h1 className="text-2xl font-bold text-center mb-6">Criar conta</h1>
        <Card className='p-6'>
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
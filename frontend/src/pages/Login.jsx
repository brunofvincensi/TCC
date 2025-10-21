import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import api from '../services/api.js';

export default function Login() {
  const navigate = useNavigate();
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  const handleLogin = async (e) => {
    e.preventDefault();
    setLoading(true);
    setError('');
    try {
      // O backend espera { email, senha } (campo 'senha' em PT-BR)
      const res = await api.post('http://localhost:5000/api/login', { email, senha: password });
      localStorage.setItem('token', res.data.token);
      // Salva também os dados do usuário retornados pelo backend
      if (res.data.usuario) {
        localStorage.setItem('usuario', JSON.stringify(res.data.usuario));
      }
      navigate('/dashboard');
    } catch (err) {
      // Mostrar mensagem de erro retornada pelo backend quando possível
      const backendError = err?.response?.data?.erro || err?.response?.data?.message || err?.message;
      console.error('Erro no login:', err?.response || err);
      setError(backendError || 'Login inválido. Verifique suas credenciais e tente novamente.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className='flex items-center justify-center min-h-screen bg-gray-900'>
      <form onSubmit={handleLogin} className='bg-gray-800 p-8 rounded-lg shadow-md w-96'>
        <h1 className='text-2xl font-bold text-center mb-6 text-white'>Login</h1>
        <input
          type='email'
          placeholder='Email'
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          className='w-full p-2 mb-4 bg-gray-700 text-white rounded focus:outline-none'
          required
        />
        <input
          type='password'
          placeholder='Senha'
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          className='w-full p-2 mb-4 bg-gray-700 text-white rounded focus:outline-none'
          required
        />
        {error && <p className='text-red-400 text-sm mb-2'>{error}</p>}
        <button
          type='submit'
          className='w-full bg-blue-600 hover:bg-blue-700 p-2 rounded text-white flex items-center justify-center'
          disabled={loading}
        >
          {loading ? 'Entrando...' : 'Entrar'}
        </button>
      </form>
    </div>
  );
}

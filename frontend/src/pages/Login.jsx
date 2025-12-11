import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import api from '../services/api.js';
import logo from '../assets/walletai.png'
import Button from '../components/ui/Button.jsx'
import Input from '../components/ui/Input.jsx'
import Card from '../components/ui/Card.jsx'

export default function Login() {
  const navigate = useNavigate();
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  const handleLogin = async (e) => {
    e.preventDefault();
    setLoading(true);
    // manter o erro anterior visível até um novo erro chegar ou o usuário navegar
    try {
      // O backend espera { email, senha } (campo 'senha' em PT-BR)
      const res = await api.post('/api/login', { email, senha: password });
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
    <div className='relative min-h-screen flex items-center justify-center overflow-hidden'>
      {/* background image blurred */}
      <div className='absolute inset-0 -z-10'>
        <img src={logo} alt='' className='w-full h-full object-cover filter blur-lg opacity-60 scale-110' />
        <div className='absolute inset-0 bg-black/60'></div>
      </div>

      <form onSubmit={handleLogin} className='w-96 relative z-10'>
        <div className='flex flex-col items-center mb-4'>
          <img src={logo} alt='Logo' className='w-20 h-20 object-cover rounded-full ring-2 ring-blue-600/40 shadow-md bg-white/5' />
          <div className='mt-2 text-center'>
            <div className='text-white font-semibold text-lg'>WalletAI</div>
          </div>
        </div>
        <Card className='p-6 backdrop-blur-sm bg-white/5'>
          <div className='space-y-3'>
            <Input label='Email' name='email' type='email' value={email} onChange={(e) => setEmail(e.target.value)} required />
            <Input label='Senha' name='senha' type='password' value={password} onChange={(e) => setPassword(e.target.value)} required />
          </div>
        </Card>
        {error && (
          <p role='alert' aria-live='assertive' className='text-red-400 text-sm mb-2'>
            {error}
          </p>
        )}
        <div className='mt-4'>
          <Button type='submit' className='w-full py-2' loading={loading} disabled={loading}>Entrar</Button>
        </div>
        <div className='mt-4 text-center'>
          <button
            type='button'
            onClick={() => navigate('/register')}
            className='text-sm muted hover:underline'
          >
            Cadastre-se
          </button>
        </div>
      </form>
    </div>
  );
}

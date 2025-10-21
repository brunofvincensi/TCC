import React, { useEffect, useState } from 'react';
import api from '../services/api';

export default function Profile() {
  const [user, setUser] = useState(null);
  const [error, setError] = useState('');

  useEffect(() => {
    const fetchUser = async () => {
      try {
        const res = await api.get('http://localhost:5000/api/usuarios'); // Substitua pelo endpoint correto
        setUser(res.data);
      } catch (err) {
        setError('Erro ao carregar os dados do perfil.');
      }
    };

    fetchUser();
  }, []);

  return (
    <div className="min-h-screen bg-gray-900 text-white p-8">
      <h1 className="text-3xl font-bold mb-6">Perfil do Usuário</h1>
      {error && <p className="text-red-400 mb-4">{error}</p>}
      {user ? (
        <div className="bg-gray-800 p-6 rounded shadow">
          <h2 className="text-2xl font-bold mb-4">{user.name}</h2>
          <p><strong>Email:</strong> {user.email}</p>
          <p><strong>Data de Cadastro:</strong> {new Date(user.createdAt).toLocaleDateString()}</p>
        </div>
      ) : (
        <p>Carregando...</p>
      )}
    </div>
  );
}
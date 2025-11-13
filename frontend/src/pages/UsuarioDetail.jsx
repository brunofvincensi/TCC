import React from 'react'
import { Navigate } from 'react-router-dom'

// Esta página era usada anteriormente para ver/editar outros usuários.
// O app agora usa /perfil para gerenciar o perfil. Mantenha esta rota
// como um redirecionamento seguro para evitar links obsoletos.
export default function UsuarioDetail() {
  return <Navigate to="/perfil" replace />
}

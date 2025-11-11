import React from 'react'
import { Navigate } from 'react-router-dom'

// This page was previously used to view/edit other users.
// The app now uses /perfil for profile management. Keep this route
// as a safe redirect to avoid stale links.
export default function UsuarioDetail() {
  return <Navigate to="/perfil" replace />
}

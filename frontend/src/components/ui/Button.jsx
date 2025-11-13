import React from 'react'
import Spinner from '../Spinner.jsx'

export default function Button({ children, variant = 'primary', className = '', loading = false, ...rest }) {
  // botão arredondado padronizado que combina com o estilo de logout do Layout
  const base = 'inline-flex items-center justify-center gap-2 py-2 px-3 rounded-md text-sm font-medium'
  const variants = {
    primary: 'btn-accent text-black',
    ghost: 'bg-white/5 text-white',
  }

  const classes = `${base} ${variants[variant] || variants.primary} ${className}`

  return (
    <button className={classes} {...rest}>
      {loading && <Spinner size={0.8} />}
      {children}
    </button>
  )
}

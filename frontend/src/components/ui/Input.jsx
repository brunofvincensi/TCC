import React from 'react'

export default function Input({ label, id, name, type = 'text', value, onChange, placeholder, className = '', ...rest }) {
  return (
    <div className={`w-full ${className}`}>
      {label && <label htmlFor={id || name} className='block muted mb-1'>{label}</label>}
      <input id={id || name} name={name} type={type} value={value} onChange={onChange} placeholder={placeholder}
        className='w-full p-2 bg-white/3 rounded border border-white/5 focus:border-teal-300 text-black placeholder:muted' {...rest} />
    </div>
  )
}

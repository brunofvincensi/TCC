import React from 'react'

export default function Input({ label, id, name, type = 'text', value, onChange, placeholder, className = '', required = false, showError = false, errorMessage = '', ...rest }) {
  const isEmpty = value === '' || value === null || value === undefined
  const hasError = required && showError && isEmpty
  
  return (
    <div className={`w-full ${className}`}>
      <div className='flex items-center justify-between mb-1'>
        {label && <label htmlFor={id || name} className='block muted'>{label}</label>}
      </div>
      <div className='relative'>
        <input id={id || name} name={name} type={type} value={value} onChange={onChange} placeholder={placeholder}
          className={`w-full p-2 bg-white/3 rounded border text-black placeholder:muted focus:border-teal-300 transition-colors ${
            hasError || errorMessage ? 'border-red-500' : 'border-white/5'
          }`} {...rest} />
        {errorMessage && (
          <div className='absolute left-0 top-full mt-2 bg-white/95 border border-orange-400 rounded px-3 py-2 text-sm text-black flex items-center gap-2 whitespace-nowrap z-10 shadow-lg'>
            <span className='text-orange-500 font-bold text-lg'>!</span>
            {errorMessage}
          </div>
        )}
      </div>
    </div>
  )
}

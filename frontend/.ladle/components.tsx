import '../src/styles/globals.css'
import type { GlobalProvider } from '@ladle/react'

export const Provider: GlobalProvider = ({ children }) => (
  <div style={{ background: 'var(--color-surface)', minHeight: '100vh', padding: '2rem' }}>
    {children}
  </div>
)

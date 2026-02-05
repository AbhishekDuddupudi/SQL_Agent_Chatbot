import React, { useState } from 'react'
import { login, type User } from './api/client'

interface LoginPageProps {
  onLoginSuccess: (user: User) => void
}

/**
 * Simple login page for the POC.
 * Only supports the seeded demo user.
 */
function LoginPage({ onLoginSuccess }: LoginPageProps) {
  const [email, setEmail] = useState('demo@example.com')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const [isLoading, setIsLoading] = useState(false)

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setError('')
    setIsLoading(true)

    try {
      const response = await login(email, password)
      
      if (response.success && response.user) {
        onLoginSuccess(response.user)
      } else {
        setError(response.message || 'Login failed')
      }
    } catch (err) {
      setError('Unable to connect to server')
    } finally {
      setIsLoading(false)
    }
  }

  return (
    <div style={styles.container}>
      <div style={styles.loginBox}>
        <h1 style={styles.title}>🧬 Pharma Analyst Bot</h1>
        <p style={styles.subtitle}>Sign in to continue</p>

        <form onSubmit={handleSubmit} style={styles.form}>
          <div style={styles.inputGroup}>
            <label style={styles.label}>Email</label>
            <input
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              style={styles.input}
              placeholder="demo@example.com"
              disabled={isLoading}
              required
            />
          </div>

          <div style={styles.inputGroup}>
            <label style={styles.label}>Password</label>
            <input
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              style={styles.input}
              placeholder="Enter password"
              disabled={isLoading}
              required
            />
          </div>

          {error && (
            <div style={styles.error}>
              {error}
            </div>
          )}

          <button
            type="submit"
            style={styles.button}
            disabled={isLoading}
          >
            {isLoading ? 'Signing in...' : 'Sign In'}
          </button>
        </form>

        <div style={styles.hint}>
          <strong>Demo credentials:</strong>
          <br />
          Email: demo@example.com
          <br />
          Password: demo123
        </div>
      </div>
    </div>
  )
}

const styles: { [key: string]: React.CSSProperties } = {
  container: {
    minHeight: '100vh',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    backgroundColor: '#f5f7fa',
    padding: '20px',
  },
  loginBox: {
    backgroundColor: 'white',
    borderRadius: '12px',
    boxShadow: '0 4px 20px rgba(0, 0, 0, 0.1)',
    padding: '40px',
    width: '100%',
    maxWidth: '400px',
  },
  title: {
    margin: 0,
    fontSize: '28px',
    textAlign: 'center',
    color: '#1a73e8',
  },
  subtitle: {
    margin: '8px 0 24px',
    fontSize: '14px',
    textAlign: 'center',
    color: '#666',
  },
  form: {
    display: 'flex',
    flexDirection: 'column',
    gap: '16px',
  },
  inputGroup: {
    display: 'flex',
    flexDirection: 'column',
    gap: '6px',
  },
  label: {
    fontSize: '14px',
    fontWeight: 500,
    color: '#333',
  },
  input: {
    padding: '12px 16px',
    border: '1px solid #ddd',
    borderRadius: '8px',
    fontSize: '16px',
    outline: 'none',
    transition: 'border-color 0.2s',
  },
  error: {
    padding: '12px',
    backgroundColor: '#fef2f2',
    border: '1px solid #fecaca',
    borderRadius: '8px',
    color: '#dc2626',
    fontSize: '14px',
    textAlign: 'center',
  },
  button: {
    padding: '14px',
    backgroundColor: '#1a73e8',
    color: 'white',
    border: 'none',
    borderRadius: '8px',
    fontSize: '16px',
    fontWeight: 600,
    cursor: 'pointer',
    marginTop: '8px',
  },
  hint: {
    marginTop: '24px',
    padding: '12px',
    backgroundColor: '#f0f9ff',
    borderRadius: '8px',
    fontSize: '13px',
    color: '#0369a1',
    textAlign: 'center',
    lineHeight: 1.6,
  },
}

export default LoginPage

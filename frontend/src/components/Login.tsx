import { useState } from 'react'
import type { FormEvent } from 'react'

interface Props { onLogin: (email: string) => void }

export default function Login({ onLogin }: Props) {
  const [email, setEmail] = useState('operator@naavaai.com')
  const [password, setPassword] = useState('')
  const [showPassword, setShowPassword] = useState(false)
  const [remember, setRemember] = useState(true)
  const [error, setError] = useState('')

  function submit(e: FormEvent) {
    e.preventDefault()
    if (!/^\S+@\S+\.\S+$/.test(email.trim())) { setError('Enter a valid email address.'); return }
    if (password.length < 6) { setError('Password must contain at least 6 characters.'); return }
    setError('')
    if (remember) localStorage.setItem('naavaai_user', email.trim())
    onLogin(email.trim())
  }

  return <main className="login-page"><div className="login-shell">
    <section className="login-story"><div className="brand-lockup"><span className="brand-mark">N</span><span>NAAVAAI</span></div><div className="eyebrow">MARITIME PROCUREMENT INTELLIGENCE</div><h1>Make the next chartering decision with confidence.</h1><p>Bring market conditions, vessel availability, port constraints and risk into one procurement workflow.</p><div className="login-proof-grid"><div><strong>Market</strong><span>Freight & commodity outlook</span></div><div><strong>Fleet</strong><span>Vessel feasibility & availability</span></div><div><strong>Ports</strong><span>Gateway & operational context</span></div><div><strong>Risk</strong><span>Scenario-aware decisioning</span></div></div></section>
    <section className="login-card"><div className="login-card-top"><span className="status-dot" /> Secure workspace</div><h2>Sign in</h2><p className="muted">Enter your workspace credentials to continue.</p><form onSubmit={submit} className="login-form"><label>Email address<input autoComplete="username" value={email} onChange={(e) => setEmail(e.target.value)} /></label><label>Password<div className="password-wrap"><input autoComplete="current-password" type={showPassword ? 'text' : 'password'} value={password} onChange={(e) => setPassword(e.target.value)} /><button type="button" onClick={() => setShowPassword(!showPassword)}>{showPassword ? 'Hide' : 'Show'}</button></div></label><label className="remember-row"><input type="checkbox" checked={remember} onChange={(e) => setRemember(e.target.checked)} /><span>Keep me signed in</span></label>{error && <div className="form-error">{error}</div>}<button className="primary-button" type="submit">Continue <span>→</span></button></form></section>
  </div></main>
}

import { useState } from 'react'
import type { FormEvent } from 'react'
import { Masthead } from './AppShell'

export default function Login({ onLogin }: { onLogin: (email: string) => void }) {
  const [email, setEmail] = useState('operator@naavaai.gov.in')
  const [password, setPassword] = useState('')
  const [show, setShow] = useState(false)
  const [error, setError] = useState('')

  function submit(e: FormEvent) {
    e.preventDefault()
    if (!/^\S+@\S+\.\S+$/.test(email.trim())) { setError('Enter an email address in the form name@example.gov.in'); return }
    if (password.length < 6) { setError('Your password needs at least 6 characters.'); return }
    setError('')
    localStorage.setItem('naavaai_user', email.trim())
    onLogin(email.trim())
  }

  return (
    <div className="login">
      <Masthead />
      <main className="login-main">
        <div className="login-copy">
          <h1>Charter with the market you might get, not the one you hope for.</h1>
          <p>
            Naavaai sizes up an overseas dry-bulk requirement against real vessel and port limits,
            prices every workable option across a range of freight futures, and tells you which
            charter to fix and why.
          </p>
          <ul className="login-points">
            <li>Physical feasibility checked before anything is costed</li>
            <li>Cost and tail risk weighed together, not separately</li>
            <li>Every recommendation traceable to the numbers behind it</li>
          </ul>
        </div>

        <div className="card login-panel">
          <h2>Sign in</h2>
          <p className="card-note">Prototype access for demonstration purposes.</p>
          <form onSubmit={submit} className="login-form">
            <label>
              Email address
              <input className="control" autoComplete="username" value={email} onChange={(e) => setEmail(e.target.value)} />
            </label>
            <label>
              Password
              <span className="pw">
                <input
                  className="control" autoComplete="current-password"
                  type={show ? 'text' : 'password'}
                  value={password} onChange={(e) => setPassword(e.target.value)}
                />
                <button type="button" onClick={() => setShow(!show)}>{show ? 'Hide' : 'Show'}</button>
              </span>
            </label>
            {error && <div className="notice notice--error" role="alert">{error}</div>}
            <button className="btn btn--primary" type="submit">Sign in</button>
          </form>
          <p className="login-help">
            Credentials are checked in the browser only and nothing is sent to a server. A live
            deployment would replace this with proper authentication, role-based access and an audit trail.
          </p>
        </div>
      </main>
      <footer className="sitefoot">
        <span>Naavaai maritime procurement portal — prototype built for SIH problem statement 26006.</span>
      </footer>
    </div>
  )
}

import { useEffect, useState } from 'react'

export type Page = 'home' | 'decision' | 'intelligence' | 'ports' | 'whatif' | 'history'

interface Props {
  page: Page
  onPage: (page: Page) => void
  user: string
  onLogout: () => void
  children: React.ReactNode
}

const NAV: [Page, string][] = [
  ['home', 'Overview'],
  ['decision', 'Decision desk'],
  ['intelligence', 'Market intelligence'],
  ['ports', 'Port intelligence'],
  ['whatif', 'What-if analysis'],
  ['history', 'Decision register'],
]

type Size = 'small' | 'normal' | 'large'

export function Masthead() {
  return (
    <>
      <div className="tricolour" aria-hidden="true"><span /><span /><span /></div>
      <header className="masthead">
        <div className="brand">
          <div className="emblem" aria-hidden="true">भारत</div>
          <div>
            <div className="brand-country">Government of India</div>
            <div className="brand-dept">Maritime procurement and freight intelligence</div>
          </div>
        </div>
        <div className="masthead-tools">
          <span className="portal-mark">Naavaai portal &middot; prototype</span>
          <TextSize />
        </div>
      </header>
    </>
  )
}

function TextSize() {
  const [size, setSize] = useState<Size>(() => (localStorage.getItem('naavaai_textsize') as Size) || 'normal')
  useEffect(() => {
    document.documentElement.dataset.textsize = size
    localStorage.setItem('naavaai_textsize', size)
  }, [size])
  return (
    <div className="textsize">
      <span>Text size</span>
      <button aria-pressed={size === 'small'} aria-label="Smaller text" onClick={() => setSize('small')}>A</button>
      <button aria-pressed={size === 'normal'} aria-label="Default text size" onClick={() => setSize('normal')}>A</button>
      <button aria-pressed={size === 'large'} aria-label="Larger text" onClick={() => setSize('large')}>A</button>
    </div>
  )
}

export default function AppShell({ page, onPage, user, onLogout, children }: Props) {
  const name = user.split('@')[0]
  const initials = name.split(/[._-]/).map((part) => part[0]).join('').slice(0, 2).toUpperCase()
  const current = NAV.find(([id]) => id === page)?.[1]

  return (
    <div>
      <a className="skip-link" href="#content">Skip to main content</a>
      <Masthead />
      <div className="layout">
        <aside className="sidenav">
          <h2 className="sidenav-heading">Portal sections</h2>
          <nav className="navlist" aria-label="Portal sections">
            {NAV.map(([id, label]) => (
              <button
                key={id}
                className="navlink"
                aria-current={page === id ? 'page' : undefined}
                onClick={() => onPage(id)}
              >
                {label}
              </button>
            ))}
          </nav>
          <div className="nav-status">
            <strong><span className="dot" aria-hidden="true" />Decision service running</strong>
            <span>Optimisation and what-if endpoints are reachable.</span>
          </div>
          <div className="nav-user">
            <div className="avatar" aria-hidden="true">{initials}</div>
            <div>
              <strong>{name}</strong>
              <span>Procurement operator</span>
            </div>
            <button onClick={onLogout}>Sign out</button>
          </div>
        </aside>

        <div className="main">
          <nav className="crumbs" aria-label="Breadcrumb">
            <span>Home</span>
            <span aria-hidden="true">›</span>
            <span>Naavaai</span>
            <span aria-hidden="true">›</span>
            <strong aria-current="page">{current}</strong>
          </nav>
          <main className="content" id="content" tabIndex={-1}>{children}</main>
          <footer className="sitefoot">
            <span>Naavaai maritime procurement portal — prototype built for SIH problem statement 26006.</span>
            <span>Content reviewed 18 September 2026</span>
          </footer>
        </div>
      </div>
    </div>
  )
}

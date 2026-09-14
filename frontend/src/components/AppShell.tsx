interface Props {
  page: 'decision' | 'intelligence' | 'ports'
  onPage: (page: Props['page']) => void
  user: string
  onLogout: () => void
  children: React.ReactNode
}

export default function AppShell({ page, onPage, user, onLogout, children }: Props) {
  const initials = user.split('@')[0].split(/[._-]/).map((part) => part[0]).join('').slice(0, 2).toUpperCase()
  return (
    <div className="app-shell">
      <aside className="sidebar">
        <div className="brand-lockup"><span className="brand-mark">N</span><span>NAAVAAI</span></div>
        <div className="workspace-label">PROCUREMENT WORKSPACE</div>
        <nav>
          <button className={page === 'decision' ? 'nav-item active' : 'nav-item'} onClick={() => onPage('decision')}><span>◈</span> Decision Desk</button>
          <button className={page === 'intelligence' ? 'nav-item active' : 'nav-item'} onClick={() => onPage('intelligence')}><span>⌁</span> Market Intelligence</button>
          <button className={page === 'ports' ? 'nav-item active' : 'nav-item'} onClick={() => onPage('ports')}><span>⚓</span> Port Intelligence</button>
        </nav>
        <div className="sidebar-bottom">
          <div className="system-health"><span className="status-dot" /> System operational <span className="font-data">LIVE</span></div>
          <div className="sidebar-user"><div className="avatar">{initials}</div><div><strong>{user.split('@')[0]}</strong><span>{user}</span></div><button title="Sign out" onClick={onLogout}>↪</button></div>
        </div>
      </aside>
      <div className="main-shell">
        <header className="topbar">
          <div><span className="topbar-kicker">NAAVAAI</span><span className="topbar-divider">/</span><span>Dry-bulk procurement</span></div>
          <div className="topbar-right"><span className="live-pill"><span className="status-dot" /> System online</span><span className="font-data">14 Sep 2026</span></div>
        </header>
        <main className="content">{children}</main>
      </div>
    </div>
  )
}

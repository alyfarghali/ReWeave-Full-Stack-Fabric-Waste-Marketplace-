import { NavLink } from 'react-router-dom'
import { useAuth } from '../features/auth/AuthContext.jsx'
import { CartButton } from '../features/marketplace/cart/CheckoutPanel.jsx'
import { ReweaveLogo } from '../shared/ReweaveMark.jsx'

export default function PortalNav() {
  const { user, logout } = useAuth()
  if (!user) return null

  const links = {
    factory: [
      { to: '/factory', label: 'Capture', end: true },
      { to: '/factory/bins', label: 'Live Bins' },
    ],
    admin: [
      { to: '/admin', label: 'Operations', end: true },
      { to: '/admin/network', label: 'Network' },
      { to: '/admin/lots', label: 'Inventory' },
      { to: '/admin/impact', label: 'Impact' },
    ],
    buyer: [
      { to: '/buyer', label: 'Marketplace', end: true },
      { to: '/buyer/orders', label: 'My Orders' },
    ],
  }

  const roleLabel = { factory: 'Factory', admin: 'Admin', buyer: 'Buyer' }

  return (
    <header className="nav">
      <div className="brand">
        <ReweaveLogo height={28} light />
        <span className="portal-badge">{roleLabel[user.role]}</span>
      </div>
      <nav>
        {(links[user.role] || []).map(l => (
          <NavLink key={l.to} to={l.to} end={l.end}>{l.label}</NavLink>
        ))}
      </nav>
      <div className="nav-right">
        {user.role === 'buyer' && <CartButton />}
        <button className="logout-btn" onClick={logout}>Sign out</button>
      </div>
    </header>
  )
}

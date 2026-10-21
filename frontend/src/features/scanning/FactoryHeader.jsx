// Factory portal header: replaces the shared portal nav on factory pages.
import { useState } from 'react'
import { Link } from 'react-router-dom'
import { useAuth } from '../auth/AuthContext.jsx'
import { ReweaveLogo } from '../../shared/ReweaveMark.jsx'
import { resetInventory } from './api.js'

export function FactoryHeader({ useContinuousServer = null, onUseContinuousServerChange = null }) {
  const { logout } = useAuth()
  const [resetting, setResetting] = useState(false)
  const [menuOpen, setMenuOpen] = useState(false)
  const showVisionToggle = typeof useContinuousServer === 'boolean' && onUseContinuousServerChange

  async function handleReset() {
    if (resetting) return
    if (!window.confirm('Reset inventory? This permanently deletes all scanned lots and clears the marketplace. Logins and buyers stay.')) return
    setResetting(true)
    try {
      await resetInventory()
      window.location.reload()
    } catch (err) {
      setResetting(false)
      alert('Reset failed: ' + (err?.message || 'unknown error'))
    }
  }

  return (
    <header className="fx-header">
      <Link className="fx-brand" to="/factory">
        <ReweaveLogo height={28} light />
      </Link>

      <div className="fx-header-actions">
        {showVisionToggle && (
          <VisionServerHeaderToggle enabled={useContinuousServer} onChange={onUseContinuousServerChange} />
        )}
        <button type="button" className="fx-reset" onClick={handleReset} disabled={resetting}>
          {resetting ? 'Resetting…' : 'Reset inventory'}
        </button>
        <button type="button" className="fx-signout" onClick={logout}>
          Sign out
        </button>
      </div>

      <button
        type="button"
        className="fx-menu-button"
        onClick={() => setMenuOpen((open) => !open)}
        aria-expanded={menuOpen}
        aria-label="Open factory menu"
      >
        <span />
        <span />
        <span />
      </button>

      {menuOpen && (
        <div className="fx-mobile-menu">
          {showVisionToggle && (
            <VisionServerToggle enabled={useContinuousServer} onChange={onUseContinuousServerChange} />
          )}
          <button type="button" className="fx-mobile-menu-item" onClick={handleReset} disabled={resetting}>
            {resetting ? 'Resetting…' : 'Reset inventory'}
          </button>
          <button type="button" className="fx-mobile-menu-item" onClick={logout}>
            Sign out
          </button>
        </div>
      )}
    </header>
  )
}

function VisionServerToggle({ enabled, onChange }) {
  return (
    <label className="fx-server-toggle">
      <input
        type="checkbox"
        checked={enabled}
        onChange={(event) => onChange(event.target.checked)}
      />
      <span className="fx-server-switch" aria-hidden="true">
        <span />
      </span>
      <span className="fx-server-copy">
        <strong>Continuous vision server</strong>
        <span>{enabled ? 'On: try fast server first' : 'Off: skip server wait'}</span>
      </span>
    </label>
  )
}

function VisionServerHeaderToggle({ enabled, onChange }) {
  return (
    <button
      type="button"
      className={`fx-server-pill ${enabled ? 'is-on' : ''}`}
      onClick={() => onChange(!enabled)}
      aria-pressed={enabled}
      title={enabled ? 'Continuous vision server on' : 'Continuous vision server off'}
    >
      <span>Vision server</span>
      <strong>{enabled ? 'On' : 'Off'}</strong>
    </button>
  )
}

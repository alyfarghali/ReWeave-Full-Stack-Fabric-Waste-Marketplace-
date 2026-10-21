import { useState, useRef } from 'react'
import { useNavigate } from 'react-router-dom'
import { useAuth } from '../auth/AuthContext.jsx'
import { login as apiLogin } from '../auth/api.js'
import { ReweaveLogo } from '../../shared/ReweaveMark.jsx'

const PORTAL_HOME = { factory: '/factory', admin: '/admin', buyer: '/buyer' }

// Fabric swatches shown in the hero visual panel
const SWATCHES = [
  { hex: '#2d3f5e', fabric: 'Denim Blue',    type: 'Cotton Twill',  price: '$44',  weight: '2.3 kg' },
  { hex: '#f0ece4', fabric: 'Natural',        type: '100% Cotton',   price: '$28',  weight: '1.8 kg' },
  { hex: '#1c1c1c', fabric: 'Charcoal',      type: 'Canvas',        price: '$61',  weight: '3.1 kg' },
  { hex: '#b8a48c', fabric: 'Warm Linen',    type: 'Linen Blend',   price: '$39',  weight: '1.4 kg' },
  { hex: '#3d5a40', fabric: 'Forest',        type: 'Cotton Twill',  price: '$47',  weight: '2.0 kg' },
  { hex: '#8b7355', fabric: 'Taupe',         type: 'Wool Blend',    price: '$55',  weight: '2.7 kg' },
]

const STEPS = [
  {
    num: '01',
    title: 'CV Capture',
    sub: 'Factory floor',
    body: 'Workers lay scraps on a sorting table and snap a photo. Computer vision reads fabric type, color, composition, and rough weight in a few seconds, so nobody has to label anything by hand.',
    detail: [
      'Finds color groups on its own',
      'Estimates weight for each group',
      'Calls out the bin each piece belongs in',
      'Lists lots to the marketplace right away',
    ],
    visual: 'cv',
  },
  {
    num: '02',
    title: 'AI Pricing',
    sub: 'Automatic',
    body: 'Each lot starts at a fair price that eases down a little every day it sits, with a hard floor at 35 percent of base. Material moves in weeks instead of months and suppliers stay profitable.',
    detail: [
      'Gentle daily decay after a 7 day grace period',
      'Never drops below 35 percent of base',
      'Flags lots that are aging for admins',
      'One click to delist or relist',
    ],
    visual: 'pricing',
  },
  {
    num: '03',
    title: 'Marketplace Claim',
    sub: 'Buyer portal',
    body: 'Recyclers and makers filter by fabric and color, then claim exactly the amount they need with a quantity slider. Every claim records where the material came from and what it saved.',
    detail: [
      'Filter by fabric type and color',
      'Quantity slider for partial lots',
      'CO₂ and water saved on every lot',
      'Live inventory as lots get claimed',
    ],
    visual: 'marketplace',
  },
]

// ── Step visuals ──────────────────────────────────────────────────────────────
function CVVisual() {
  return (
    <div className="lp-visual-cv">
      <div className="lp-cv-topbar">
        <span className="lp-cv-dot" style={{ background: '#ef4444' }} />
        <span className="lp-cv-dot" style={{ background: '#f59e0b' }} />
        <span className="lp-cv-dot" style={{ background: '#22c55e' }} />
        <span className="lp-cv-title">Reweave factory scan</span>
      </div>
      <div className="lp-cv-frame">
        <div className="lp-cv-table">
          {[
            { hex: '#2d3f5e', x: '8%',  y: '12%', w: '32%', h: '28%', label: 'A' },
            { hex: '#b8a48c', x: '48%', y: '10%', w: '22%', h: '22%', label: 'B' },
            { hex: '#1c1c1c', x: '12%', y: '52%', w: '28%', h: '24%', label: 'C' },
            { hex: '#3d5a40', x: '50%', y: '44%', w: '34%', h: '30%', label: 'D' },
            { hex: '#8b7355', x: '75%', y: '12%', w: '18%', h: '26%', label: 'E' },
          ].map(s => (
            <div key={s.label} className="lp-cv-scrap" style={{
              background: s.hex, left: s.x, top: s.y, width: s.w, height: s.h
            }}>
              <span className="lp-cv-scrap-label">{s.label}</span>
            </div>
          ))}
          <div className="lp-cv-scan-line" />
        </div>
        <div className="lp-cv-readout">
          <span className="lp-cv-readout-dot" />
          <span>Grouping colors, 5 groups found</span>
        </div>
      </div>
      <div className="lp-cv-groups">
        {[
          { hex: '#2d3f5e', name: 'Denim Blue', bin: 'Bin A', count: '3 pcs' },
          { hex: '#1c1c1c', name: 'Charcoal',   bin: 'Bin C', count: '2 pcs' },
          { hex: '#3d5a40', name: 'Forest',      bin: 'Bin B', count: '4 pcs' },
        ].map(g => (
          <div key={g.name} className="lp-cv-group-row">
            <span className="lp-cv-group-swatch" style={{ background: g.hex }} />
            <span className="lp-cv-group-name">{g.name}</span>
            <span className="lp-cv-group-bin">{g.bin}</span>
            <span className="lp-cv-group-count">{g.count}</span>
          </div>
        ))}
      </div>
    </div>
  )
}

function PricingVisual() {
  const pts = [100, 98, 95, 90, 83, 74, 63, 52, 43, 37, 35, 35, 35]
  const w = 260, h = 120
  const xStep = w / (pts.length - 1)
  const pathD = pts.map((p, i) => `${i === 0 ? 'M' : 'L'}${i * xStep},${h - (p / 100) * h}`).join(' ')
  const areaD = pathD + ` L${(pts.length - 1) * xStep},${h} L0,${h} Z`

  return (
    <div className="lp-visual-pricing">
      <div className="lp-cv-topbar">
        <span className="lp-cv-dot" style={{ background: '#ef4444' }} />
        <span className="lp-cv-dot" style={{ background: '#f59e0b' }} />
        <span className="lp-cv-dot" style={{ background: '#22c55e' }} />
        <span className="lp-cv-title">Reweave AI pricing</span>
      </div>
      <div className="lp-pricing-body">
        <div className="lp-pricing-header">
          <div>
            <div className="lp-pricing-lot-name">Navy Cotton Twill · Lot #038</div>
            <div className="lp-pricing-lot-meta">Listed 11 days ago · 2.3 kg · 4 pcs</div>
          </div>
          <div className="lp-pricing-badge">−37%</div>
        </div>
        <svg width={w} height={h + 20} viewBox={`0 0 ${w} ${h + 20}`} className="lp-pricing-chart">
          <defs>
            <linearGradient id="pg" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor="#166534" stopOpacity="0.18" />
              <stop offset="100%" stopColor="#166534" stopOpacity="0" />
            </linearGradient>
          </defs>
          <path d={areaD} fill="url(#pg)" />
          <path d={pathD} fill="none" stroke="#166534" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
          <line x1="0" y1={h - 0.35 * h} x2={w} y2={h - 0.35 * h} stroke="#dc2626" strokeWidth="1" strokeDasharray="4 3" opacity="0.5" />
          <text x={w - 4} y={h - 0.35 * h - 4} textAnchor="end" fontSize="9" fill="#dc2626" opacity="0.7">floor 35%</text>
        </svg>
        <div className="lp-pricing-price-row">
          <div>
            <span className="lp-pricing-current">$27.65</span>
            <span className="lp-pricing-original">was $44.00</span>
          </div>
          <div className="lp-pricing-decay-note">Drops daily until claimed</div>
        </div>
      </div>
    </div>
  )
}

function MarketplaceVisual() {
  return (
    <div className="lp-visual-marketplace">
      <div className="lp-cv-topbar">
        <span className="lp-cv-dot" style={{ background: '#ef4444' }} />
        <span className="lp-cv-dot" style={{ background: '#f59e0b' }} />
        <span className="lp-cv-dot" style={{ background: '#22c55e' }} />
        <span className="lp-cv-title">Reweave buyer marketplace</span>
      </div>
      <div className="lp-mkt-grid">
        {[
          { hex: '#2d3f5e', name: 'Navy Cotton Twill',  price: '$44',  decay: '-18%', type: 'Cotton' },
          { hex: '#3d5a40', name: 'Forest Canvas',      price: '$47',  decay: '-8%',  type: 'Canvas' },
          { hex: '#b8a48c', name: 'Warm Linen Blend',   price: '$28',  decay: '-33%', type: 'Linen'  },
          { hex: '#1c1c1c', name: 'Charcoal Cotton',    price: '$61',  decay: '-5%',  type: 'Cotton' },
        ].map(c => (
          <div key={c.name} className="lp-mkt-card">
            <div className="lp-mkt-swatch" style={{ background: c.hex }}>
              <span className="lp-mkt-type-tag">{c.type}</span>
            </div>
            <div className="lp-mkt-info">
              <div className="lp-mkt-name">{c.name}</div>
              <div className="lp-mkt-price-row">
                <span className="lp-mkt-price">{c.price}</span>
                <span className="lp-mkt-decay">{c.decay}</span>
              </div>
            </div>
          </div>
        ))}
      </div>
      <div className="lp-mkt-cta">
        <span className="lp-mkt-cta-btn">Add to Order</span>
        <span className="lp-mkt-impact">4.1 kg CO₂ saved</span>
      </div>
    </div>
  )
}

const VISUALS = { cv: CVVisual, pricing: PricingVisual, marketplace: MarketplaceVisual }

export default function LandingPage() {
  const { login } = useAuth()
  const navigate = useNavigate()
  const [email, setEmail]       = useState('')
  const [password, setPassword] = useState('')
  const [error, setError]       = useState(null)
  const [loading, setLoading]   = useState(false)
  const [modalOpen, setModalOpen] = useState(false)
  const [activeStep, setActiveStep] = useState(0)
  const touchStartX = useRef(null)

  async function handleSubmit(e) {
    e.preventDefault()
    setError(null)
    setLoading(true)
    try {
      const data = await apiLogin(email, password)
      login(data.access_token, data.role, data.name)
      navigate(PORTAL_HOME[data.role] ?? '/')
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  function fill(e, p) { setEmail(e); setPassword(p) }

  function onStepTouchStart(e) { touchStartX.current = e.touches[0].clientX }
  function onStepTouchEnd(e) {
    if (touchStartX.current === null) return
    const delta = e.changedTouches[0].clientX - touchStartX.current
    if (delta < -50) setActiveStep(s => Math.min(s + 1, STEPS.length - 1))
    if (delta > 50)  setActiveStep(s => Math.max(s - 1, 0))
    touchStartX.current = null
  }

  const StepVisual = VISUALS[STEPS[activeStep].visual]

  return (
    <div className="landing">

      {/* ── Nav ── */}
      <header className="landing-nav">
        <div className="landing-nav-inner">
          <div className="landing-brand">
            <ReweaveLogo height={30} />
          </div>
          <nav className="landing-nav-links">
            <a href="#how">How it works</a>
            <a href="#workflow">Workflow</a>
          </nav>
          <button className="landing-nav-signin" onClick={() => setModalOpen(true)}>
            Sign in
          </button>
        </div>
      </header>

      {/* ── Sign-in modal ── */}
      {modalOpen && (
        <>
          <div className="landing-modal-overlay" onClick={() => setModalOpen(false)} />
          <div className="landing-modal">
            <div className="landing-modal-header">
              <div className="landing-signin-title">Sign in to your portal</div>
              <button className="landing-modal-close" onClick={() => setModalOpen(false)}>✕</button>
            </div>
            {error && <div className="landing-signin-error">{error}</div>}
            <form onSubmit={handleSubmit} className="landing-signin-form">
              <input type="email" value={email} onChange={e => setEmail(e.target.value)}
                placeholder="Email address" required className="landing-input" autoFocus />
              <input type="password" value={password} onChange={e => setPassword(e.target.value)}
                placeholder="Password" required className="landing-input" />
              <button type="submit" disabled={loading} className="landing-signin-btn">
                {loading ? 'Signing in…' : 'Sign in →'}
              </button>
            </form>
            <div className="landing-demo-hints">
              <div className="landing-demo-label">Demo accounts, click to fill</div>
              <div className="landing-demo-row">
                <button className="landing-demo-fill" onClick={() => fill('factory@demo.com', 'factory123')}>Factory</button>
                <button className="landing-demo-fill" onClick={() => fill('admin@demo.com', 'admin123')}>Admin</button>
                <button className="landing-demo-fill" onClick={() => fill('buyer@demo.com', 'buyer123')}>Buyer</button>
              </div>
            </div>
          </div>
        </>
      )}

      {/* ── Hero ── */}
      <section className="landing-hero">
        <div className="landing-hero-inner">

          {/* Left copy */}
          <div className="landing-hero-copy">
            <div className="landing-hero-lockup">
              <ReweaveLogo height={48} light />
            </div>
            <h1 className="landing-h1">
              Turn textile offcuts into traceable supply.
            </h1>
            <p className="landing-hero-sub">
              Reweave helps factories scan scrap fabric, create priced lots, and
              route reusable material to recyclers and makers before it becomes waste.
            </p>
            <div className="landing-hero-actions">
              <button className="landing-hero-cta" onClick={() => setModalOpen(true)}>
                Sign in to your portal →
              </button>
              <a href="#how" className="landing-hero-ghost">See how it works</a>
            </div>
          </div>

          {/* Right visual — marketplace preview */}
          <div className="landing-visual-frame">
            <div className="landing-visual-topbar">
              <span className="landing-visual-title">Marketplace lot board</span>
            </div>
            <div className="landing-visual-grid">
              {SWATCHES.map((s, i) => (
                <div key={i} className="landing-visual-card">
                  <div className="landing-visual-swatch" style={{ background: s.hex }} />
                  <div className="landing-visual-info">
                    <div className="landing-visual-fabric">{s.fabric}</div>
                    <div className="landing-visual-meta">{s.type} · {s.weight}</div>
                    <div className="landing-visual-price">{s.price}</div>
                  </div>
                </div>
              ))}
            </div>
          </div>

        </div>
      </section>

      {/* ── Stats bar ── */}
      <section className="landing-stats-bar">
        <div className="landing-inner">
          <div className="landing-stats-grid">
            {[
              { value: 'Capture',  label: 'Factory workers photograph and register fabric offcuts.' },
              { value: 'Classify', label: 'Computer vision reads material, color, and approximate volume.' },
              { value: 'Price',    label: 'Lots receive a starting price and decay rules for faster movement.' },
              { value: 'Claim',    label: 'Buyers filter, reserve, and document the material they take.' },
            ].map((s, i) => (
              <div key={i} className="landing-stat">
                <div className="landing-stat-value">{s.value}</div>
                <div className="landing-stat-label">{s.label}</div>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* ── Platform overview carousel ── */}
      <section className="landing-section lp-carousel-section" id="how">
        <div className="landing-inner">
          <div className="landing-section-header">
            <div className="landing-section-eyebrow">Platform overview</div>
            <h2 className="landing-h2">From factory floor to circular supply chain</h2>
            <p className="lp-section-sub">Step through each stage with the arrows or dots below.</p>
          </div>
        </div>

        <div
          className="lp-carousel"
          onTouchStart={onStepTouchStart}
          onTouchEnd={onStepTouchEnd}
        >
          <div className="lp-carousel-track" style={{ transform: `translateX(-${activeStep * 100}%)` }}>
            {STEPS.map((step, i) => (
              <div key={step.num} className={`lp-carousel-slide ${i === activeStep ? 'lp-carousel-slide--active' : ''}`}>
                <div className="lp-carousel-inner">
                  <div className="lp-carousel-copy">
                    <div className="lp-carousel-num">{step.num}</div>
                    <div className="lp-carousel-sub">{step.sub}</div>
                    <h3 className="lp-carousel-title">{step.title}</h3>
                    <p className="lp-carousel-body">{step.body}</p>
                    <ul className="lp-carousel-features">
                      {step.detail.map(d => (
                        <li key={d}>
                          <span className="lp-carousel-check">✓</span>
                          {d}
                        </li>
                      ))}
                    </ul>
                  </div>
                  <div className="lp-carousel-visual">
                    {i === activeStep && <StepVisual />}
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>

        <div className="lp-carousel-controls">
          <button
            className="lp-carousel-arrow"
            onClick={() => setActiveStep(s => Math.max(s - 1, 0))}
            disabled={activeStep === 0}
          >←</button>
          <div className="lp-carousel-dots">
            {STEPS.map((_, i) => (
              <button
                key={i}
                className={`lp-carousel-dot ${i === activeStep ? 'lp-carousel-dot--active' : ''}`}
                onClick={() => setActiveStep(i)}
              />
            ))}
          </div>
          <button
            className="lp-carousel-arrow"
            onClick={() => setActiveStep(s => Math.min(s + 1, STEPS.length - 1))}
            disabled={activeStep === STEPS.length - 1}
          >→</button>
        </div>
      </section>

      {/* ── Workflow ── */}
      <section className="landing-pilot" id="workflow">
        <div className="landing-inner">
          <div className="landing-pilot-eyebrow">Operational workflow</div>
          <h2 className="landing-pilot-h2">One system for factories, operators, and buyers</h2>
          <p className="landing-pilot-body">
            Reweave keeps the handoff from a factory bin to a buyer-ready lot visible.
            Each role gets the information it needs without adding extra spreadsheet work
            to the factory floor.
          </p>
          <div className="landing-pilot-stats">
            {[
              { value: 'Factory',  label: 'Capture scrap fabric without spreadsheet work.' },
              { value: 'Admin',    label: 'Review lots, approve listings, and track movement.' },
              { value: 'Buyer',    label: 'Find reusable material by specs and claim it quickly.' },
              { value: 'Impact',   label: 'Keep source, weight, price, and diversion records together.' },
            ].map((s, i) => (
              <div key={i} className="landing-pilot-stat">
                <div className="landing-pilot-stat-value">{s.value}</div>
                <div className="landing-pilot-stat-label">{s.label}</div>
              </div>
            ))}
          </div>
          <div className="landing-pilot-chain">
            Scan offcuts &nbsp;&rarr;&nbsp; classify material &nbsp;&rarr;&nbsp; publish lot &nbsp;&rarr;&nbsp; record claim
          </div>
        </div>
      </section>

      {/* ── Footer ── */}
      <footer className="landing-footer">
        <div className="landing-inner">
          <div className="landing-footer-brand">
            <ReweaveLogo height={27} light />
          </div>
          <div className="landing-footer-links">
            <a href="#how">How it works</a>
            <a href="#workflow">Workflow</a>
          </div>
        </div>
      </footer>

    </div>
  )
}

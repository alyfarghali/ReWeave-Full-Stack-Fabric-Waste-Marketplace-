import { lazy, Suspense } from 'react'
import { Navigate, Route, Routes, useLocation } from 'react-router-dom'
import ChatBot from '../features/assistant/ChatBot.jsx'
import { AuthProvider, useAuth } from '../features/auth/AuthContext.jsx'
import LandingPage from '../features/landing/LandingPage.jsx'
import { CartProvider, useCart } from '../features/marketplace/cart/CartContext.jsx'
import { CheckoutPanel } from '../features/marketplace/cart/CheckoutPanel.jsx'
import OrderConfirmation from '../features/marketplace/cart/OrderConfirmation.jsx'
import ErrorBoundary from './ErrorBoundary.jsx'
import PortalNav from './PortalNav.jsx'
import ProtectedRoute from './ProtectedRoute.jsx'

// Portal pages load on demand so the landing page doesn't ship the charting
// and mapping libraries only signed-in users need.
const CapturePage = lazy(() => import('../features/scanning/CapturePage.jsx'))
const BinFeed = lazy(() => import('../features/scanning/BinFeed.jsx'))
const DashboardPage = lazy(() => import('../features/admin/DashboardPage.jsx'))
const NetworkPage = lazy(() => import('../features/admin/NetworkPage.jsx'))
const InventoryPage = lazy(() => import('../features/admin/InventoryPage.jsx'))
const ImpactPage = lazy(() => import('../features/admin/ImpactPage.jsx'))
const MarketplacePage = lazy(() => import('../features/marketplace/MarketplacePage.jsx'))
const OrdersPage = lazy(() => import('../features/marketplace/OrdersPage.jsx'))

function AppInner() {
  const { user } = useAuth()
  const location = useLocation()
  const { lastSuccess, lastOrder, clearLastOrder } = useCart()

  // Factory routes use their own full-screen operator shell (FactoryHeader + dark UI)
  const isFactory = location.pathname.startsWith('/factory')

  // Landing page gets its own full-screen layout — no portal chrome, no content wrapper
  const isLanding = !user && (location.pathname === '/' || location.pathname === '/login')
  if (isLanding) {
    return <LandingPage />
  }

  return (
    <div className="app">
      {!isFactory && <PortalNav />}
      {lastSuccess && (
        <div className="global-success-banner">{lastSuccess}</div>
      )}
      <main className={isFactory ? 'content content-bleed' : 'content'}>
        <ErrorBoundary key={location.pathname}>
          <Suspense fallback={<div className="dash-loading">Loading…</div>}>
            <Routes>
              <Route path="/login" element={user ? <Navigate to={`/${user.role}`} replace /> : <LandingPage />} />

              {/* Factory */}
              <Route path="/factory" element={<ProtectedRoute role="factory"><CapturePage /></ProtectedRoute>} />
              <Route path="/factory/bins" element={<ProtectedRoute role="factory"><BinFeed /></ProtectedRoute>} />

              {/* Admin */}
              <Route path="/admin" element={<ProtectedRoute role="admin"><DashboardPage /></ProtectedRoute>} />
              <Route path="/admin/network" element={<ProtectedRoute role="admin"><NetworkPage /></ProtectedRoute>} />
              <Route path="/admin/lots" element={<ProtectedRoute role="admin"><InventoryPage /></ProtectedRoute>} />
              <Route path="/admin/impact" element={<ProtectedRoute role="admin"><ImpactPage /></ProtectedRoute>} />

              {/* Buyer */}
              <Route path="/buyer" element={<ProtectedRoute role="buyer"><MarketplacePage /></ProtectedRoute>} />
              <Route path="/buyer/orders" element={<ProtectedRoute role="buyer"><OrdersPage /></ProtectedRoute>} />

              {/* Root: landing page for guests, portal home for authed users */}
              <Route path="/" element={user ? <Navigate to={`/${user.role}`} replace /> : <LandingPage />} />
              <Route path="*" element={<Navigate to={user ? `/${user.role}` : '/'} replace />} />
            </Routes>
          </Suspense>
        </ErrorBoundary>
      </main>
      <CheckoutPanel />
      {lastOrder && <OrderConfirmation order={lastOrder} onClose={clearLastOrder} />}
      {!isFactory && <ChatBot />}
    </div>
  )
}

export default function App() {
  return (
    <AuthProvider>
      <CartProvider>
        <AppInner />
      </CartProvider>
    </AuthProvider>
  )
}

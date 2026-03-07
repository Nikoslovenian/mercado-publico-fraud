import { useState, useEffect } from 'react'
import { Routes, Route, useLocation } from 'react-router-dom'
import Sidebar from './components/Sidebar'
import CommandPalette from './components/CommandPalette'
import Dashboard from './pages/Dashboard'
import Alerts from './pages/Alerts'
import AlertDetail from './pages/AlertDetail'
import Procurements from './pages/Procurements'
import ProcurementDetail from './pages/ProcurementDetail'
import Suppliers from './pages/Suppliers'
import SupplierDetail from './pages/SupplierDetail'
import NetworkPage from './pages/NetworkPage'

function StatusBar() {
  const [time, setTime] = useState(new Date())
  useEffect(() => {
    const id = setInterval(() => setTime(new Date()), 1000)
    return () => clearInterval(id)
  }, [])

  return (
    <div className="statusbar">
      <div className="flex items-center gap-1.5">
        <span className="statusbar-dot" style={{ background: '#00e5a0', color: '#00e5a0' }} />
        <span>OPERATIVO</span>
      </div>
      <span style={{ color: 'var(--border)' }}>|</span>
      <span>BASE: mercado_publico.db</span>
      <span style={{ color: 'var(--border)' }}>|</span>
      <span>FUENTE: OCDS 2025</span>
      <div className="ml-auto flex items-center gap-4">
        <span>v2.0.0</span>
        <span style={{ color: 'var(--text-dim)' }}>
          {time.toLocaleDateString('es-CL')} {time.toLocaleTimeString('es-CL', { hour: '2-digit', minute: '2-digit', second: '2-digit' })}
        </span>
      </div>
    </div>
  )
}

export default function App() {
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false)
  const [commandOpen, setCommandOpen] = useState(false)
  const location = useLocation()

  // Global keyboard shortcut for command palette
  useEffect(() => {
    const handler = (e) => {
      if ((e.ctrlKey || e.metaKey) && e.key === 'k') {
        e.preventDefault()
        setCommandOpen(o => !o)
      }
      if (e.key === 'Escape') setCommandOpen(false)
    }
    window.addEventListener('keydown', handler)
    return () => window.removeEventListener('keydown', handler)
  }, [])

  // Close command palette on navigation
  useEffect(() => { setCommandOpen(false) }, [location])

  return (
    <div className="h-screen flex flex-col overflow-hidden" style={{ background: 'var(--bg)' }}>
      {/* Classification banner */}
      <div className="classification-banner py-0.5 text-center font-mono text-[10px] font-semibold text-red-400 shrink-0">
        ▌ PLATAFORMA CLASIFICADA — DETECCION DE FRAUDE EN COMPRAS PUBLICAS · CHILE 2025 ▐
      </div>

      {/* Main layout */}
      <div className="flex flex-1 overflow-hidden">
        <Sidebar
          collapsed={sidebarCollapsed}
          onToggle={() => setSidebarCollapsed(c => !c)}
          onCommandPalette={() => setCommandOpen(true)}
        />

        {/* Content area */}
        <main className="flex-1 overflow-y-auto overflow-x-hidden" style={{ background: 'var(--bg)' }}>
          <div className="page-container">
            <Routes>
              <Route path="/" element={<Dashboard />} />
              <Route path="/alerts" element={<Alerts />} />
              <Route path="/alerts/:id" element={<AlertDetail />} />
              <Route path="/procurements" element={<Procurements />} />
              <Route path="/procurements/:ocid" element={<ProcurementDetail />} />
              <Route path="/suppliers" element={<Suppliers />} />
              <Route path="/suppliers/:rut" element={<SupplierDetail />} />
              <Route path="/network" element={<NetworkPage />} />
              <Route path="/network/:rut" element={<NetworkPage />} />
            </Routes>
          </div>
        </main>
      </div>

      {/* Status bar */}
      <StatusBar />

      {/* Command palette overlay */}
      <CommandPalette isOpen={commandOpen} onClose={() => setCommandOpen(false)} />
    </div>
  )
}

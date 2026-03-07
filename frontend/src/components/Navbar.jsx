import { Link, useLocation } from 'react-router-dom'
import { Shield, BarChart2, AlertTriangle, FileText, Users, Network } from 'lucide-react'

const links = [
  { to: '/', label: 'CENTRO DE CONTROL', icon: BarChart2 },
  { to: '/alerts', label: 'ALERTAS', icon: AlertTriangle },
  { to: '/procurements', label: 'LICITACIONES', icon: FileText },
  { to: '/suppliers', label: 'ENTIDADES', icon: Users },
  { to: '/network', label: 'RED', icon: Network },
]

export default function Navbar() {
  const { pathname } = useLocation()

  return (
    <nav className="sticky top-0 z-50">
      {/* Classification banner */}
      <div className="classification-banner py-1 text-center text-xs font-mono font-semibold tracking-widest text-red-400">
        ▌ SISTEMA CLASIFICADO — DETECCIÓN DE FRAUDE EN COMPRAS PÚBLICAS CHILE 2025 ▐
      </div>
      {/* Main nav */}
      <div style={{ background: '#0a1020', borderBottom: '1px solid #1a2535' }}>
        <div className="max-w-screen-2xl mx-auto px-4 flex items-center h-12 gap-6">
          <Link to="/" className="flex items-center gap-2 shrink-0 group">
            <div className="relative">
              <Shield size={20} className="text-red-400" style={{ filter: 'drop-shadow(0 0 6px rgba(255,51,85,0.5))' }} />
            </div>
            <div className="hidden sm:block">
              <span className="text-xs font-mono font-bold tracking-widest" style={{ color: '#c8d8e8' }}>
                ANTI<span style={{ color: '#ff3355' }}>·</span>FRAUDE
              </span>
              <span className="text-xs font-mono ml-1.5" style={{ color: '#5a7090' }}>MP2025</span>
            </div>
          </Link>

          <div className="w-px h-6 bg-intel-border ml-1 mr-1" style={{ background: '#1a2535' }} />

          <div className="flex items-center gap-0.5 overflow-x-auto">
            {links.map(({ to, label, icon: Icon }) => {
              const active = pathname === to || (to !== '/' && pathname.startsWith(to))
              return (
                <Link
                  key={to}
                  to={to}
                  className={`flex items-center gap-1.5 px-3 py-1.5 rounded text-xs font-semibold tracking-wider transition-all duration-150 whitespace-nowrap ${
                    active
                      ? 'text-white'
                      : 'hover:text-white'
                  }`}
                  style={active
                    ? { background: 'rgba(64,128,255,0.15)', color: '#80b0ff', border: '1px solid rgba(64,128,255,0.2)' }
                    : { color: '#5a7090', border: '1px solid transparent' }
                  }
                >
                  <Icon size={13} />
                  <span className="hidden md:inline">{label}</span>
                </Link>
              )
            })}
          </div>

          <div className="ml-auto flex items-center gap-3">
            <div className="flex items-center gap-1.5">
              <div className="w-2 h-2 rounded-full threat-dot" style={{ background: '#00e5a0' }} />
              <span className="text-xs font-mono" style={{ color: '#5a7090' }}>SISTEMA EN LÍNEA</span>
            </div>
          </div>
        </div>
      </div>
    </nav>
  )
}

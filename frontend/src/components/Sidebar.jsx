import { Link, useLocation } from 'react-router-dom'
import { useState, useEffect } from 'react'
import {
  Shield, BarChart3, AlertTriangle, FileText, Users, Network,
  ChevronLeft, ChevronRight, Search, Hexagon, Radio
} from 'lucide-react'

const navItems = [
  { to: '/', label: 'CENTRO DE CONTROL', icon: BarChart3, shortcut: '1' },
  { to: '/alerts', label: 'ALERTAS', icon: AlertTriangle, shortcut: '2' },
  { to: '/procurements', label: 'LICITACIONES', icon: FileText, shortcut: '3' },
  { to: '/suppliers', label: 'ENTIDADES', icon: Users, shortcut: '4' },
  { to: '/network', label: 'ANALISIS DE RED', icon: Network, shortcut: '5' },
]

export default function Sidebar({ collapsed, onToggle, onCommandPalette }) {
  const { pathname } = useLocation()

  return (
    <aside className={`sidebar ${collapsed ? 'collapsed' : ''}`}>
      {/* Logo */}
      <div className="flex items-center gap-2.5 px-3.5 py-3 border-b" style={{ borderColor: 'var(--border)' }}>
        <div className="relative shrink-0">
          <Hexagon size={24} style={{ color: '#ff3355', filter: 'drop-shadow(0 0 6px rgba(255,51,85,0.4))' }} />
          <Shield size={12} className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2"
                  style={{ color: '#ff3355' }} />
        </div>
        {!collapsed && (
          <div className="animate-slideIn">
            <div className="font-mono text-xs font-bold tracking-widest" style={{ color: 'var(--text-bright)' }}>
              ANTI<span style={{ color: '#ff3355' }}>·</span>FRAUDE
            </div>
            <div className="font-mono text-[9px] tracking-wider" style={{ color: 'var(--muted)' }}>
              GOTHAM v2.0 — MP2025
            </div>
          </div>
        )}
      </div>

      {/* Search trigger */}
      <div className="px-2 py-2">
        <button
          onClick={onCommandPalette}
          className="w-full flex items-center gap-2 px-2.5 py-1.5 rounded text-left transition-all"
          style={{ background: 'rgba(64,128,255,0.04)', border: '1px solid var(--border)', color: 'var(--muted)' }}
        >
          <Search size={12} />
          {!collapsed ? (
            <>
              <span className="text-[11px] flex-1">Buscar...</span>
              <kbd className="font-mono text-[9px] px-1 py-0.5 rounded"
                   style={{ background: 'var(--bg)', border: '1px solid var(--border)' }}>
                Ctrl+K
              </kbd>
            </>
          ) : null}
        </button>
      </div>

      {/* Section label */}
      {!collapsed && (
        <div className="px-4 pt-2 pb-1">
          <span className="font-mono text-[9px] font-semibold tracking-widest" style={{ color: 'var(--muted)', opacity: 0.6 }}>
            MODULOS
          </span>
        </div>
      )}

      {/* Navigation */}
      <nav className="flex-1 px-1 py-1 space-y-0.5">
        {navItems.map(({ to, label, icon: Icon, shortcut }) => {
          const active = pathname === to || (to !== '/' && pathname.startsWith(to))
          return (
            <Link key={to} to={to}
              className={`sidebar-link ${active ? 'active' : ''}`}
              title={collapsed ? label : undefined}
            >
              <Icon size={16} className="shrink-0" />
              {!collapsed && <span className="nav-label text-[11px]">{label}</span>}
              {!collapsed && active && (
                <Radio size={8} className="ml-auto shrink-0 data-stream" style={{ color: 'var(--blue)' }} />
              )}
            </Link>
          )
        })}
      </nav>

      {/* System status */}
      {!collapsed && (
        <div className="px-3 py-2 border-t" style={{ borderColor: 'var(--border)' }}>
          <div className="flex items-center gap-2 mb-2">
            <div className="statusbar-dot" style={{ background: '#00e5a0', color: '#00e5a0' }} />
            <span className="font-mono text-[9px] tracking-wider" style={{ color: 'var(--muted)' }}>
              SISTEMA OPERATIVO
            </span>
          </div>
          <div className="grid grid-cols-2 gap-x-3 gap-y-1">
            {[
              ['DB', 'ONLINE'],
              ['API', 'ACTIVE'],
              ['ETL', 'READY'],
              ['SCAN', 'IDLE'],
            ].map(([k, v]) => (
              <div key={k} className="flex items-center justify-between">
                <span className="font-mono text-[9px]" style={{ color: 'var(--muted)' }}>{k}</span>
                <span className="font-mono text-[9px]" style={{ color: '#00e5a0' }}>{v}</span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Collapse toggle */}
      <button
        onClick={onToggle}
        className="flex items-center justify-center py-2 border-t transition-colors hover:bg-white/[0.02]"
        style={{ borderColor: 'var(--border)', color: 'var(--muted)' }}
      >
        {collapsed ? <ChevronRight size={14} /> : <ChevronLeft size={14} />}
      </button>
    </aside>
  )
}

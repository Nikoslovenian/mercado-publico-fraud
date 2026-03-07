import { useState, useEffect, useRef } from 'react'
import { useNavigate } from 'react-router-dom'
import {
  BarChart3, AlertTriangle, FileText, Users, Network,
  Search, ArrowRight, Zap
} from 'lucide-react'

const COMMANDS = [
  { id: 'dashboard', label: 'Centro de Control', desc: 'Dashboard principal', icon: BarChart3, path: '/', keywords: 'dashboard inicio home' },
  { id: 'alerts', label: 'Alertas de Fraude', desc: 'Registro de alertas detectadas', icon: AlertTriangle, path: '/alerts', keywords: 'alertas fraude amenazas' },
  { id: 'alerts-criticas', label: 'Alertas Criticas', desc: 'Solo alertas de severidad alta', icon: AlertTriangle, path: '/alerts?severity=alta', keywords: 'criticas alta urgente' },
  { id: 'procurements', label: 'Licitaciones', desc: 'Base de datos OCDS', icon: FileText, path: '/procurements', keywords: 'licitaciones contratos ocds compras' },
  { id: 'suppliers', label: 'Proveedores', desc: 'Entidades bajo analisis', icon: Users, path: '/suppliers', keywords: 'proveedores entidades empresas rut' },
  { id: 'suppliers-alerts', label: 'Proveedores con Alertas', desc: 'Solo entidades flaggeadas', icon: Users, path: '/suppliers?has_alerts=true', keywords: 'proveedores alertas riesgo' },
  { id: 'network', label: 'Analisis de Red', desc: 'Grafo de relaciones entre proveedores', icon: Network, path: '/network', keywords: 'red grafo relaciones conexiones' },
]

export default function CommandPalette({ isOpen, onClose }) {
  const [query, setQuery] = useState('')
  const [selected, setSelected] = useState(0)
  const inputRef = useRef(null)
  const navigate = useNavigate()

  useEffect(() => {
    if (isOpen) {
      setQuery('')
      setSelected(0)
      setTimeout(() => inputRef.current?.focus(), 50)
    }
  }, [isOpen])

  const filtered = COMMANDS.filter(cmd => {
    if (!query) return true
    const q = query.toLowerCase()
    return cmd.label.toLowerCase().includes(q) ||
           cmd.desc.toLowerCase().includes(q) ||
           cmd.keywords.includes(q)
  })

  const execute = (cmd) => {
    navigate(cmd.path)
    onClose()
  }

  const handleKeyDown = (e) => {
    if (e.key === 'Escape') { onClose(); return }
    if (e.key === 'ArrowDown') { e.preventDefault(); setSelected(s => Math.min(s + 1, filtered.length - 1)) }
    if (e.key === 'ArrowUp') { e.preventDefault(); setSelected(s => Math.max(s - 1, 0)) }
    if (e.key === 'Enter' && filtered[selected]) { execute(filtered[selected]) }
  }

  if (!isOpen) return null

  return (
    <div className="command-overlay" onClick={onClose}>
      <div className="command-palette animate-fadeIn" onClick={e => e.stopPropagation()}>
        <div className="flex items-center gap-3 px-4 border-b" style={{ borderColor: 'var(--border)' }}>
          <Zap size={14} style={{ color: 'var(--blue)' }} />
          <input
            ref={inputRef}
            className="command-input"
            placeholder="Buscar modulo, proveedor, alerta..."
            value={query}
            onChange={e => { setQuery(e.target.value); setSelected(0) }}
            onKeyDown={handleKeyDown}
          />
        </div>
        <div className="overflow-y-auto" style={{ maxHeight: 320 }}>
          {filtered.length === 0 && (
            <div className="py-8 text-center font-mono text-xs" style={{ color: 'var(--muted)' }}>
              SIN RESULTADOS
            </div>
          )}
          {filtered.map((cmd, i) => {
            const Icon = cmd.icon
            return (
              <button
                key={cmd.id}
                className="w-full flex items-center gap-3 px-4 py-2.5 text-left transition-all"
                style={{
                  background: i === selected ? 'rgba(64,128,255,0.08)' : 'transparent',
                  borderLeft: i === selected ? '2px solid var(--blue)' : '2px solid transparent',
                }}
                onMouseEnter={() => setSelected(i)}
                onClick={() => execute(cmd)}
              >
                <Icon size={15} style={{ color: i === selected ? 'var(--blue)' : 'var(--muted)' }} />
                <div className="flex-1 min-w-0">
                  <div className="text-xs font-semibold" style={{ color: i === selected ? 'var(--text-bright)' : 'var(--text)' }}>
                    {cmd.label}
                  </div>
                  <div className="text-[10px]" style={{ color: 'var(--muted)' }}>{cmd.desc}</div>
                </div>
                {i === selected && <ArrowRight size={12} style={{ color: 'var(--blue)' }} />}
              </button>
            )
          })}
        </div>
        <div className="px-4 py-2 border-t flex items-center gap-4" style={{ borderColor: 'var(--border)' }}>
          <span className="font-mono text-[9px]" style={{ color: 'var(--muted)' }}>
            <kbd className="px-1 py-0.5 rounded" style={{ background: 'var(--bg)', border: '1px solid var(--border)' }}>↑↓</kbd> navegar
          </span>
          <span className="font-mono text-[9px]" style={{ color: 'var(--muted)' }}>
            <kbd className="px-1 py-0.5 rounded" style={{ background: 'var(--bg)', border: '1px solid var(--border)' }}>↵</kbd> seleccionar
          </span>
          <span className="font-mono text-[9px]" style={{ color: 'var(--muted)' }}>
            <kbd className="px-1 py-0.5 rounded" style={{ background: 'var(--bg)', border: '1px solid var(--border)' }}>esc</kbd> cerrar
          </span>
        </div>
      </div>
    </div>
  )
}

import { useState, useEffect } from 'react'
import { useQuery } from '@tanstack/react-query'
import { useSearchParams } from 'react-router-dom'
import { getAlerts, exportAlerts } from '../api/client'
import { Link } from 'react-router-dom'
import AlertBadge from '../components/AlertBadge'
import { TYPE_META } from '../components/TypeBadge'
import { Download, ChevronDown, ChevronUp, ShieldAlert, FileText, ArrowUpRight, Crosshair } from 'lucide-react'

const ALERT_TYPES = [
  { value: '', label: 'Todos los tipos' },
  { value: 'FRAC', label: 'FRAC — Compra Fraccionada' },
  { value: 'CONC', label: 'CONC — Concentracion' },
  { value: 'COLU', label: 'COLU — Shadow Bidding' },
  { value: 'COLU2', label: 'COLU2 — Rotacion Ganadores' },
  { value: 'PLAZ', label: 'PLAZ — Plazo Anomalo' },
  { value: 'RELA', label: 'RELA — Proveedores Relacionados' },
  { value: 'PREC', label: 'PREC — Precio Anomalo' },
  { value: 'NUEV', label: 'NUEV — Empresa Nueva Ganadora' },
  { value: 'TRAT', label: 'TRAT — Trato Directo Excesivo' },
  { value: 'DTDR', label: 'DTDR — Desierta + Trato Directo' },
  { value: 'CONF', label: 'CONF — Conflicto de Interes' },
  { value: 'UNIC', label: 'UNIC — Oferente Unico Recurrente' },
  { value: 'TEMP', label: 'TEMP — Patron Temporal Sospechoso' },
  { value: 'ADJU', label: 'ADJU — No Adjudica Menor Precio' },
  { value: 'DESC', label: 'DESC — Descalificacion Sistematica' },
  { value: 'GEOG', label: 'GEOG — Anomalia Geografica' },
  { value: 'UMBR', label: 'UMBR — Monto Cerca de Umbral' },
  { value: 'VELO', label: 'VELO — Adjudicacion Rapida' },
  { value: 'LOBB', label: 'LOBB — Relacion Pre-existente' },
  { value: 'PARE', label: 'PARE — Parentesco Apellidos' },
  { value: 'DIVI', label: 'DIVI — Division de Contratos' },
]

function AlertRow({ alert }) {
  const [expanded, setExpanded] = useState(false)
  const meta = TYPE_META[alert.alert_type] || { color: '#8090a8', bg: 'rgba(128,144,168,0.1)', border: 'rgba(128,144,168,0.2)' }

  return (
    <>
      <tr className="cursor-pointer transition-colors"
        onClick={() => setExpanded(e => !e)}
        onMouseEnter={e => { e.currentTarget.style.background = 'rgba(64,128,255,0.03)' }}
        onMouseLeave={e => { e.currentTarget.style.background = 'transparent' }}>
        <td className="px-3 py-2.5">
          <AlertBadge severity={alert.severity} />
        </td>
        <td className="px-3 py-2.5">
          <span className="intel-tag" style={{ color: meta.color, background: meta.bg, borderColor: meta.border }}>
            {alert.alert_type}
          </span>
        </td>
        <td className="px-3 py-2.5">
          <Link to={'/alerts/' + alert.id}
            className="text-[12px] font-medium hover:underline"
            style={{ color: 'var(--text)' }}
            onClick={e => e.stopPropagation()}>
            {alert.title}
          </Link>
        </td>
        <td className="px-3 py-2.5 text-[11px] hidden md:table-cell" style={{ color: 'var(--text-dim)' }}>
          {(alert.buyer_name || alert.buyer_rut || '—').slice(0, 30)}
        </td>
        <td className="px-3 py-2.5 text-[11px] hidden lg:table-cell" style={{ color: 'var(--text-dim)' }}>
          {(alert.supplier_name || alert.supplier_rut || '—').slice(0, 25)}
        </td>
        <td className="px-3 py-2.5 text-[11px] hidden xl:table-cell font-mono" style={{ color: 'var(--muted)' }}>
          {alert.region || '—'}
        </td>
        <td className="px-3 py-2.5 text-right hidden lg:table-cell">
          {alert.amount_involved ? (
            <span className="font-mono text-[11px] font-semibold" style={{ color: '#ffaa00' }}>
              ${Math.round(alert.amount_involved).toLocaleString('es-CL')}
            </span>
          ) : <span style={{ color: 'var(--muted)' }}>—</span>}
        </td>
        <td className="px-3 py-2.5 text-right w-8" style={{ color: 'var(--muted)' }}>
          {expanded ? <ChevronUp size={12} /> : <ChevronDown size={12} />}
        </td>
      </tr>
      {expanded && (
        <tr className="bg-[#0a0e18]">
          <td colSpan={8} className="p-0 border-b border-gray-800">
            <div className="flex flex-col md:flex-row p-6 gap-6 relative overflow-hidden" style={{ borderLeft: '3px solid ' + meta.color }}>
              <div className="absolute top-0 right-0 w-64 h-64 bg-opacity-5 rounded-full blur-3xl" style={{ background: meta.color, opacity: 0.1 }}></div>

              <div className="flex-1 relative z-10">
                <div className="text-[10px] font-mono tracking-widest mb-2 flex items-center gap-2" style={{ color: meta.color }}>
                  <span className="w-2 h-2 rounded-full animate-pulse" style={{ background: meta.color }}></span>
                  EXPEDIENTE DE INTELIGENCIA MATRIZ
                </div>
                <h4 className="text-[14px] font-bold mb-3" style={{ color: 'var(--text-bright)' }}>MOTIVO DE LA ALERTA DETALLADO</h4>
                <p className="text-[12px] leading-relaxed mb-4 bg-[#060a10] p-4 rounded border border-gray-800" style={{ color: 'var(--text)' }}>
                  {alert.description}
                </p>
                <div className="flex gap-2 flex-wrap mt-2">
                  {alert.ocid && (
                    <Link to={'/procurements/' + encodeURIComponent(alert.ocid)} className="btn-intel btn-blue">
                      <FileText size={10} /> PROCESO {alert.ocid.split('-').slice(-2).join('-')}
                    </Link>
                  )}
                  {alert.supplier_rut && (
                    <Link to={'/suppliers/' + alert.supplier_rut} className="btn-intel btn-cyan">
                      ENTIDAD: {alert.supplier_rut}
                    </Link>
                  )}
                  <Link to={'/alerts/' + alert.id} className="btn-intel btn-green">
                    ABRIR DOSSIER <ArrowUpRight size={10} />
                  </Link>
                </div>
              </div>

              {alert.evidence && Object.keys(alert.evidence).length > 0 && (
                <div className="w-full md:w-1/3 relative z-10 border-l border-gray-800 pl-6 space-y-3">
                  <div className="text-[10px] font-mono tracking-widest mb-3" style={{ color: 'var(--muted)' }}>
                    EXTRACTOS DE EVIDENCIA TÉCNICA
                  </div>
                  <div className="grid grid-cols-1 gap-2">
                    {Object.entries(alert.evidence).slice(0, 6).map(([k, v]) => (
                      <div key={k} className="bg-[#0e1628] border border-gray-800 rounded p-2 flex justify-between items-center transition-all hover:border-[#1e3050]">
                        <span className="text-[9px] font-mono uppercase text-gray-500">{k.replace(/_/g, ' ')}</span>
                        <span className="text-[11px] font-mono font-medium truncate max-w-[120px]" style={{ color: 'var(--text-bright)' }}>
                          {String(v)}
                        </span>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>
          </td>
        </tr>
      )}
    </>
  )
}

export default function Alerts() {
  const [searchParams] = useSearchParams()
  const [filters, setFilters] = useState({
    alert_type: searchParams.get('alert_type') || '',
    severity: searchParams.get('severity') || '',
    region: searchParams.get('region') || '',
    buyer_rut: searchParams.get('buyer_rut') || '',
    supplier_rut: searchParams.get('supplier_rut') || '',
    q: '',
    page: 1,
  })

  const [qVal, setQVal] = useState(filters.q)

  // Debounce search text

  const { data, isLoading, isFetching } = useQuery({
    queryKey: ['alerts', filters],
    queryFn: () => getAlerts({ ...filters, page_size: 25 }),
  })

  // Debounce text search
  useEffect(() => {
    const timer = setTimeout(() => {
      if (filters.q !== qVal) {
        setFilters(f => ({ ...f, q: qVal, page: 1 }))
      }
    }, 500)
    return () => clearTimeout(timer)
  }, [qVal, filters.q])

  const setFilter = (key, value) => setFilters(f => ({ ...f, [key]: value, page: 1 }))

  return (
    <div className="space-y-4 animate-fadeIn">
      <div className="flex items-center justify-between flex-wrap gap-3">
        <div>
          <div className="section-header mb-1">
            <ShieldAlert size={10} />
            <span>REGISTRO DE ALERTAS — OPERACION MP2025</span>
          </div>
          <h1 className="text-base font-bold" style={{ color: 'var(--text-bright)' }}>Alertas de Fraude</h1>
        </div>
        <button onClick={() => exportAlerts(filters)} className="btn-intel btn-green">
          <Download size={11} /> EXPORTAR CSV
        </button>
      </div>

      <div className="intel-card p-4 relative overflow-hidden">
        <div className="absolute top-0 right-0 w-64 h-full bg-[radial-gradient(ellipse_at_top_right,_var(--tw-gradient-stops))] from-blue-900/10 to-transparent"></div>
        <div className="section-header mb-4">
          <Crosshair size={10} />
          <span>FILTROS TÁCTICOS Y VECTORES DE BÚSQUEDA</span>
        </div>
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-5 gap-3">
          <div>
            <label className="text-[9px] font-mono text-gray-500 uppercase mb-1 block">Término General / Palabras Clave</label>
            <input type="text" placeholder="Ej: Municipalidad..."
              value={qVal} onChange={e => setQVal(e.target.value)}
              className="intel-input w-full" />
          </div>
          <div>
            <label className="text-[9px] font-mono text-gray-500 uppercase mb-1 block">Vector de Fraude (Patrón)</label>
            <select value={filters.alert_type} onChange={e => setFilter('alert_type', e.target.value)} className="intel-select w-full">
              {ALERT_TYPES.map(t => <option key={t.value} value={t.value}>{t.label}</option>)}
            </select>
          </div>
          <div>
            <label className="text-[9px] font-mono text-gray-500 uppercase mb-1 block">Umbral de Severidad</label>
            <select value={filters.severity} onChange={e => setFilter('severity', e.target.value)} className="intel-select w-full">
              <option value="">ALCANCE: TODOS</option>
              <option value="alta">CRITICA (ALTA)</option>
              <option value="media">MODERADA</option>
              <option value="baja">BAJA</option>
            </select>
          </div>
          <div>
            <label className="text-[9px] font-mono text-gray-500 uppercase mb-1 block">RUT Organismo (Comprador)</label>
            <input type="text" placeholder="RUT..." value={filters.buyer_rut || ''}
              onChange={e => setFilter('buyer_rut', e.target.value)} className="intel-input w-full" />
          </div>
          <div>
            <label className="text-[9px] font-mono text-gray-500 uppercase mb-1 block">RUT Proveedor (Sujeto)</label>
            <input type="text" placeholder="RUT..." value={filters.supplier_rut || ''}
              onChange={e => setFilter('supplier_rut', e.target.value)} className="intel-input w-full" />
          </div>
        </div>
      </div>

      {isLoading ? (
        <div className="text-center py-16 font-mono text-[11px]" style={{ color: 'var(--muted)' }}>CONSULTANDO BASE DE DATOS...</div>
      ) : (
        <div className="intel-card overflow-x-auto">
          <div className="px-3 py-2 border-b flex items-center justify-between" style={{ borderColor: 'var(--border)' }}>
            <span className="font-mono text-[10px]" style={{ color: 'var(--muted)' }}>
              {(data?.total || 0).toLocaleString('es-CL')} registros
            </span>
            <div className="flex gap-2">
              {filters.alert_type && (
                <span className="intel-tag" style={{
                  color: TYPE_META[filters.alert_type]?.color || 'var(--text-dim)',
                  background: 'rgba(64,128,255,0.06)', borderColor: 'rgba(64,128,255,0.15)'
                }}>
                  {filters.alert_type}
                </span>
              )}
              {filters.severity && (
                <span className="intel-tag" style={{
                  color: filters.severity === 'alta' ? '#ff3355' : filters.severity === 'media' ? '#ffaa00' : '#00c878',
                  background: 'rgba(64,128,255,0.06)', borderColor: 'rgba(64,128,255,0.15)'
                }}>
                  {filters.severity.toUpperCase()}
                </span>
              )}
            </div>
          </div>
          <table className="w-full min-w-[700px] intel-table">
            <thead>
              <tr>
                <th className="text-left w-20">SEV</th>
                <th className="text-left w-16">TIPO</th>
                <th className="text-left">DESCRIPCION</th>
                <th className="text-left hidden md:table-cell">ORGANISMO</th>
                <th className="text-left hidden lg:table-cell">PROVEEDOR</th>
                <th className="text-left hidden xl:table-cell">REGION</th>
                <th className="text-right hidden lg:table-cell">MONTO</th>
                <th className="w-8"></th>
              </tr>
            </thead>
            <tbody>
              {(data?.items || []).map(a => <AlertRow key={a.id} alert={a} />)}
            </tbody>
          </table>
          {(!data?.items || data.items.length === 0) && !isLoading && (
            <div className="text-center py-16 font-mono text-[11px]" style={{ color: 'var(--muted)' }}>
              SIN REGISTROS CON LOS FILTROS APLICADOS
            </div>
          )}
          {data?.items?.length > 0 && (
            <div className="flex justify-between items-center px-4 py-3 border-t" style={{ borderColor: 'var(--border)' }}>
              <span className="font-mono text-[10px]" style={{ color: 'var(--muted)' }}>
                PÁGINA {data.page} DE {data.total_pages}
              </span>
              <div className="flex gap-2">
                <button
                  onClick={() => setFilters(f => ({ ...f, page: Math.max(1, f.page - 1) }))}
                  disabled={data.page === 1}
                  className="btn-intel btn-gray disabled:opacity-50">
                  ANTERIOR
                </button>
                <button
                  onClick={() => setFilters(f => ({ ...f, page: Math.min(data.total_pages, f.page + 1) }))}
                  disabled={data.page >= data.total_pages}
                  className="btn-intel btn-gray disabled:opacity-50">
                  SIGUIENTE
                </button>
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  )
}

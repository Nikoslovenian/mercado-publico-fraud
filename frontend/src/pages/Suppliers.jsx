import { useState, useEffect } from 'react'
import { useQuery } from '@tanstack/react-query'
import { getSuppliers } from '../api/client'
import { Link, useSearchParams } from 'react-router-dom'
import AlertBadge from '../components/AlertBadge'
import { Users, ArrowUpRight, Network } from 'lucide-react'

export default function Suppliers() {
  const [searchParams] = useSearchParams()
  const [filters, setFilters] = useState({
    q: '',
    has_alerts: searchParams.get('has_alerts') || '',
    page: 1
  })
  const setFilter = (k, v) => setFilters(f => ({ ...f, [k]: v, page: 1 }))

  const [qVal, setQVal] = useState(filters.q)

  useEffect(() => {
    const timer = setTimeout(() => {
      if (filters.q !== qVal) setFilters(f => ({ ...f, q: qVal, page: 1 }))
    }, 500)
    return () => clearTimeout(timer)
  }, [qVal, filters.q])

  const params = { ...filters, has_alerts: filters.has_alerts === 'true' ? true : undefined }
  const { data, isLoading } = useQuery({
    queryKey: ['suppliers', filters],
    queryFn: () => getSuppliers({ ...params, page_size: 25 }),
  })

  const fmtAmount = (n) => n ? '$' + Math.round(n).toLocaleString('es-CL') : '—'

  return (
    <div className="space-y-4 animate-fadeIn">
      <div className="flex items-center justify-between">
        <div>
          <div className="section-header mb-1">
            <Users size={10} />
            <span>REGISTRO DE ENTIDADES — PROVEEDORES DEL ESTADO</span>
          </div>
          <h1 className="text-base font-bold" style={{ color: 'var(--text-bright)' }}>Proveedores y Entidades</h1>
        </div>
        <Link to="/network" className="btn-intel btn-cyan">
          <Network size={11} /> ANALISIS DE RED
        </Link>
      </div>

      <div className="intel-card p-3">
        <div className="grid grid-cols-2 md:grid-cols-3 gap-2">
          <input placeholder="Buscar por nombre o RUT..."
            value={qVal} onChange={e => setQVal(e.target.value)}
            className="intel-input w-full col-span-2 md:col-span-1" />
          <select value={filters.has_alerts} onChange={e => setFilter('has_alerts', e.target.value)}
            className="intel-select w-full">
            <option value="">Todos los proveedores</option>
            <option value="true">Solo con alertas</option>
          </select>
          <div className="hidden md:flex items-center justify-end">
            <span className="font-mono text-[10px]" style={{ color: 'var(--muted)' }}>
              {(data?.total || 0).toLocaleString('es-CL')} entidades
            </span>
          </div>
        </div>
      </div>

      {isLoading ? (
        <div className="text-center py-16 font-mono text-[11px]" style={{ color: 'var(--muted)' }}>CONSULTANDO REGISTROS...</div>
      ) : (
        <div className="intel-card overflow-x-auto">
          <table className="w-full min-w-[600px] intel-table">
            <thead>
              <tr>
                <th className="text-left">RUT</th>
                <th className="text-left">NOMBRE</th>
                <th className="text-left hidden md:table-cell">REGION</th>
                <th className="text-right hidden lg:table-cell">MONTO ADJUDICADO</th>
                <th className="text-center w-20">ALERTAS</th>
                <th className="text-center hidden md:table-cell w-20">SEV MAX</th>
                <th className="w-8"></th>
              </tr>
            </thead>
            <tbody>
              {(data?.items || []).map(s => (
                <tr key={s.rut}>
                  <td className="px-3 py-2.5">
                    <Link to={'/suppliers/' + s.rut}
                      className="font-mono text-[10px] hover:underline" style={{ color: 'var(--blue)' }}>
                      {s.rut}
                    </Link>
                  </td>
                  <td className="px-3 py-2.5">
                    <Link to={'/suppliers/' + s.rut}
                      className="text-[12px] font-medium hover:underline" style={{ color: 'var(--text)' }}>
                      {s.name || '(sin nombre)'}
                    </Link>
                  </td>
                  <td className="px-3 py-2.5 text-[11px] hidden md:table-cell" style={{ color: 'var(--text-dim)' }}>
                    {s.region || '—'}
                  </td>
                  <td className="px-3 py-2.5 text-right hidden lg:table-cell">
                    <span className="font-mono text-[11px]" style={{ color: 'var(--text)' }}>{fmtAmount(s.total_awarded)}</span>
                  </td>
                  <td className="px-3 py-2.5 text-center">
                    {s.alert_count > 0 ? (
                      <span className="font-mono text-[12px] font-bold" style={{ color: '#ff3355' }}>{s.alert_count}</span>
                    ) : (
                      <span className="font-mono text-[12px]" style={{ color: 'var(--border)' }}>0</span>
                    )}
                  </td>
                  <td className="px-3 py-2.5 text-center hidden md:table-cell">
                    {s.max_severity ? <AlertBadge severity={s.max_severity} /> : <span style={{ color: 'var(--border)' }}>—</span>}
                  </td>
                  <td className="px-3 py-2.5">
                    <Link to={'/suppliers/' + s.rut} style={{ color: 'var(--muted)' }}>
                      <ArrowUpRight size={12} />
                    </Link>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          {(!data?.items || data.items.length === 0) && !isLoading && (
            <div className="text-center py-16 font-mono text-[11px]" style={{ color: 'var(--muted)' }}>SIN REGISTROS</div>
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

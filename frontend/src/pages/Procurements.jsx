import { useState, useEffect } from 'react'
import { useQuery } from '@tanstack/react-query'
import { getProcurements } from '../api/client'
import { Link } from 'react-router-dom'
import { ShieldAlert, FileText, Database } from 'lucide-react'

export default function Procurements() {
  const [filters, setFilters] = useState({ q: '', region: '', has_alerts: '', page: 1 })
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
    queryKey: ['procurements', filters],
    queryFn: () => getProcurements({ ...params, page_size: 25 }),
  })

  const fmtDate = (d) => d ? new Date(d).toLocaleDateString('es-CL') : '—'
  const fmtAmount = (n) => n ? '$' + Math.round(n).toLocaleString('es-CL') : '—'

  return (
    <div className="space-y-4 animate-fadeIn">
      <div>
        <div className="section-header mb-1">
          <Database size={10} />
          <span>BASE DE DATOS — LICITACIONES OCDS 2025</span>
        </div>
        <h1 className="text-base font-bold" style={{ color: 'var(--text-bright)' }}>Licitaciones Publicas</h1>
      </div>

      <div className="intel-card p-3">
        <div className="grid grid-cols-2 md:grid-cols-4 gap-2">
          <input placeholder="Titulo, OCID, organismo..."
            value={qVal} onChange={e => setQVal(e.target.value)}
            className="intel-input w-full col-span-2 md:col-span-1" />
          <input placeholder="Region..."
            value={filters.region} onChange={e => setFilter('region', e.target.value)}
            className="intel-input w-full" />
          <select value={filters.has_alerts} onChange={e => setFilter('has_alerts', e.target.value)}
            className="intel-select w-full">
            <option value="">Todas</option>
            <option value="true">Solo con alertas</option>
          </select>
          <div className="flex items-center justify-end">
            <span className="font-mono text-[10px]" style={{ color: 'var(--muted)' }}>
              {(data?.total || 0).toLocaleString('es-CL')} procesos
            </span>
          </div>
        </div>
      </div>

      {isLoading ? (
        <div className="text-center py-16 font-mono text-[11px]" style={{ color: 'var(--muted)' }}>CONSULTANDO BASE DE DATOS...</div>
      ) : (
        <div className="intel-card overflow-x-auto">
          <table className="w-full min-w-[700px] intel-table">
            <thead>
              <tr>
                <th className="text-left">OCID</th>
                <th className="text-left">TITULO</th>
                <th className="text-left hidden md:table-cell">ORGANISMO</th>
                <th className="text-left hidden lg:table-cell">MODALIDAD</th>
                <th className="text-left hidden lg:table-cell">FECHA</th>
                <th className="text-right hidden xl:table-cell">MONTO</th>
                <th className="hidden md:table-cell w-16"></th>
              </tr>
            </thead>
            <tbody>
              {(data?.items || []).map(p => (
                <tr key={p.ocid}>
                  <td className="px-3 py-2.5">
                    <Link to={'/procurements/' + encodeURIComponent(p.ocid)}
                      className="font-mono text-[10px] hover:underline" style={{ color: 'var(--blue)' }}>
                      {p.ocid.split('-').slice(-2).join('-')}
                    </Link>
                  </td>
                  <td className="px-3 py-2.5">
                    <Link to={'/procurements/' + encodeURIComponent(p.ocid)}
                      className="text-[12px] hover:underline" style={{ color: 'var(--text)' }}>
                      {(p.title || '').slice(0, 55)}{(p.title || '').length > 55 ? '...' : ''}
                    </Link>
                  </td>
                  <td className="px-3 py-2.5 text-[11px] hidden md:table-cell" style={{ color: 'var(--text-dim)' }}>
                    {(p.buyer_name || p.buyer_rut || '').slice(0, 32)}
                  </td>
                  <td className="px-3 py-2.5 hidden lg:table-cell">
                    <span className="intel-tag" style={{
                      color: '#80a0ff', background: 'rgba(128,160,255,0.06)', borderColor: 'rgba(128,160,255,0.15)'
                    }}>
                      {p.method_details || p.method || '—'}
                    </span>
                  </td>
                  <td className="px-3 py-2.5 font-mono text-[10px] hidden lg:table-cell" style={{ color: 'var(--muted)' }}>
                    {fmtDate(p.tender_start)}
                  </td>
                  <td className="px-3 py-2.5 text-right hidden xl:table-cell">
                    <span className="font-mono text-[11px] font-semibold" style={{ color: 'var(--text)' }}>
                      {fmtAmount(p.total_amount)}
                    </span>
                  </td>
                  <td className="px-3 py-2.5 hidden md:table-cell">
                    {p.alert_count > 0 && (
                      <span className="intel-tag" style={{
                        color: '#ff6688', background: 'rgba(255,51,85,0.08)', borderColor: 'rgba(255,51,85,0.2)'
                      }}>
                        <ShieldAlert size={9} /> {p.alert_count}
                      </span>
                    )}
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

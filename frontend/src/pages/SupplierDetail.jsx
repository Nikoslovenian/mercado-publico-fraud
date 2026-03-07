import { useParams, Link } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { getSupplier, refreshSupplierExternal } from '../api/client'
import AlertBadge from '../components/AlertBadge'
import TypeBadge from '../components/TypeBadge'
import { ArrowLeft, RefreshCw, Network, ShieldAlert, Building2, FileText, Users, Gauge, Database } from 'lucide-react'

function Section({ title, icon: Icon, children, action }) {
  return (
    <div className="intel-card p-4">
      <div className="flex items-center justify-between mb-3">
        <div className="section-header flex-1">
          {Icon && <Icon size={10} />}
          <span>{title}</span>
        </div>
        {action}
      </div>
      {children}
    </div>
  )
}

function RiskScore({ alerts }) {
  if (!alerts || alerts.length === 0) return null
  const alta = alerts.filter(a => a.severity === 'alta').length
  const media = alerts.filter(a => a.severity === 'media').length
  const baja = alerts.filter(a => a.severity === 'baja').length
  const score = Math.min(100, alta * 30 + media * 15 + baja * 5)
  const color = score >= 70 ? '#ff3355' : score >= 40 ? '#ffaa00' : '#00e5a0'
  const label = score >= 70 ? 'CRITICO' : score >= 40 ? 'MODERADO' : 'BAJO'

  return (
    <div className="kpi-card" style={{ '--accent-color': color }}>
      <div className="flex items-center justify-between mb-2">
        <div className="section-header flex-1">
          <Gauge size={10} />
          <span>SCORE DE RIESGO</span>
        </div>
        <span className="intel-tag" style={{ color, background: color + '12', borderColor: color + '30' }}>
          {label}
        </span>
      </div>
      <div className="flex items-end gap-2">
        <span className="font-mono text-3xl font-bold" style={{ color }}>{score}</span>
        <span className="font-mono text-[10px] mb-1" style={{ color: 'var(--muted)' }}>/100</span>
      </div>
      <div className="intel-progress mt-3">
        <div className="intel-progress-bar" style={{ width: score + '%', background: color }} />
      </div>
      <div className="flex gap-4 mt-2 font-mono text-[10px]" style={{ color: 'var(--muted)' }}>
        <span><span style={{ color: '#ff3355' }}>{alta}</span> criticas</span>
        <span><span style={{ color: '#ffaa00' }}>{media}</span> moderadas</span>
        <span><span style={{ color: '#00e5a0' }}>{baja}</span> bajas</span>
      </div>
    </div>
  )
}

export default function SupplierDetail() {
  const { rut } = useParams()
  const qc = useQueryClient()
  const { data: s, isLoading } = useQuery({ queryKey: ['supplier', rut], queryFn: () => getSupplier(rut) })

  const refreshMutation = useMutation({
    mutationFn: () => refreshSupplierExternal(rut),
    onSuccess: () => qc.invalidateQueries(['supplier', rut]),
  })

  if (isLoading) return (
    <div className="flex items-center justify-center py-32">
      <div className="font-mono text-[11px]" style={{ color: 'var(--blue)' }}>CARGANDO PERFIL...</div>
    </div>
  )
  if (!s) return (
    <div className="flex items-center justify-center py-32">
      <div className="font-mono text-[11px]" style={{ color: '#ff3355' }}>PROVEEDOR NO ENCONTRADO</div>
    </div>
  )

  const fmtAmt = (n) => n ? `$${Math.round(n).toLocaleString('es-CL')} CLP` : '—'
  const fmtDate = (d) => d ? new Date(d).toLocaleDateString('es-CL') : '—'
  const totalAwarded = s.procurement_history?.reduce((sum, p) => sum + (p.amount || 0), 0) || 0

  return (
    <div className="max-w-5xl mx-auto space-y-4 animate-fadeIn">
      {/* Header */}
      <div className="flex items-start gap-3">
        <Link to="/suppliers" className="mt-1 transition-opacity hover:opacity-80" style={{ color: 'var(--muted)' }}>
          <ArrowLeft size={16} />
        </Link>
        <div className="flex-1">
          <h1 className="text-base font-bold" style={{ color: 'var(--text-bright)' }}>{s.name}</h1>
          {s.legal_name && s.legal_name !== s.name && (
            <p className="text-[12px]" style={{ color: 'var(--text-dim)' }}>{s.legal_name}</p>
          )}
          <p className="font-mono text-[10px] mt-0.5" style={{ color: 'var(--muted)' }}>RUT: {s.rut}</p>
        </div>
        <div className="flex gap-2 shrink-0">
          <Link to={`/network/${s.rut}`} className="btn-intel btn-cyan">
            <Network size={12} /> Red
          </Link>
          <button onClick={() => refreshMutation.mutate()} disabled={refreshMutation.isPending}
            className="btn-intel btn-blue">
            <RefreshCw size={12} className={refreshMutation.isPending ? 'animate-spin' : ''} />
            Actualizar
          </button>
        </div>
      </div>

      {/* Alerts */}
      {s.alerts?.length > 0 && (
        <div className="intel-card p-4" style={{ borderColor: 'rgba(255,51,85,0.2)' }}>
          <div className="flex items-center gap-2 mb-2">
            <ShieldAlert size={13} style={{ color: '#ff3355' }} />
            <span className="font-mono text-[10px] font-bold tracking-wider" style={{ color: '#ff6688' }}>
              {s.alerts.length} ALERTA(S)
            </span>
          </div>
          <div className="space-y-1.5">
            {s.alerts.slice(0, 5).map(a => (
              <div key={a.id} className="flex items-center gap-2 text-[12px]">
                <AlertBadge severity={a.severity} />
                <TypeBadge type={a.alert_type} />
                <Link to={`/alerts/${a.id}`} className="hover:underline" style={{ color: '#ff8899' }}>{a.title}</Link>
              </div>
            ))}
            {s.alerts.length > 5 && (
              <Link to={`/alerts?supplier_rut=${s.rut}`} className="font-mono text-[10px]" style={{ color: 'var(--blue)' }}>
                Ver todas las alertas →
              </Link>
            )}
          </div>
        </div>
      )}

      <div className="grid grid-cols-1 xl:grid-cols-3 gap-4">
        <div className="xl:col-span-2 space-y-4">
          <Section title="INFORMACION DEL PROVEEDOR" icon={Building2}>
            <div className="grid grid-cols-2 md:grid-cols-3 gap-x-6 gap-y-3 text-[12px]">
              {[
                ['Region', s.region],
                ['Direccion', s.address],
                ['Telefono', s.phone],
                ['Email', s.email],
                ['Contacto', s.contact_name],
                ['Total adjudicado', fmtAmt(totalAwarded)],
                ['Contratos ganados', s.procurement_history?.length || 0],
              ].map(([label, value]) => (
                <div key={label}>
                  <span className="font-mono text-[10px] block mb-0.5 tracking-wide" style={{ color: 'var(--muted)' }}>{label.toUpperCase()}</span>
                  <span className="font-medium" style={{ color: 'var(--text)' }}>{value || '—'}</span>
                </div>
              ))}
            </div>
            {s.is_public_employee && (
              <div className="mt-3 p-2.5 rounded text-[11px]"
                   style={{ background: 'rgba(255,51,85,0.06)', border: '1px solid rgba(255,51,85,0.15)', color: '#ff8899' }}>
                ALERTA: Posible funcionario publico en: {s.public_employee_org}
              </div>
            )}
          </Section>

          {s.sii_status && (
            <Section title="DATOS SII (SERVICIO DE IMPUESTOS INTERNOS)">
              <div className="grid grid-cols-2 md:grid-cols-3 gap-x-6 gap-y-3 text-[12px]">
                <div>
                  <span className="font-mono text-[10px] block mb-0.5 tracking-wide" style={{ color: 'var(--muted)' }}>ESTADO</span>
                  <span className="font-medium" style={{ color: s.sii_status === 'activo' ? '#00e5a0' : '#ff6688' }}>
                    {s.sii_status}
                  </span>
                </div>
                <div>
                  <span className="font-mono text-[10px] block mb-0.5 tracking-wide" style={{ color: 'var(--muted)' }}>INICIO ACTIVIDADES</span>
                  <span className="font-mono" style={{ color: 'var(--text)' }}>{fmtDate(s.sii_start_date)}</span>
                </div>
                <div>
                  <span className="font-mono text-[10px] block mb-0.5 tracking-wide" style={{ color: 'var(--muted)' }}>GIRO</span>
                  <span style={{ color: 'var(--text)' }}>{s.sii_activity_code || '—'}</span>
                </div>
              </div>
            </Section>
          )}

          {s.external_data?.length > 0 && (
            <Section title="DATOS EXTERNOS CRUZADOS" icon={Database}>
              {s.external_data.map((ext, i) => {
                const sourceColors = {
                  sii: '#00e5a0', transparencia: '#4080ff', infolobby: '#ffaa00',
                  contraloria: '#ff80aa', mercadopublico: '#9060ff',
                }
                const color = sourceColors[ext.source] || '#8090a8'
                return (
                  <div key={i} className="mb-3 last:mb-0">
                    <div className="flex items-center gap-2 mb-1.5">
                      <span className="intel-tag" style={{ color, background: color + '12', borderColor: color + '25' }}>
                        {ext.source.toUpperCase()}
                      </span>
                      <span className="font-mono text-[10px]" style={{ color: 'var(--muted)' }}>
                        {ext.last_updated ? new Date(ext.last_updated).toLocaleDateString('es-CL') : '—'}
                      </span>
                    </div>
                    <pre className="text-[10px] rounded p-2.5 overflow-x-auto font-mono"
                         style={{ background: 'var(--bg)', border: '1px solid var(--border)', color: 'var(--text-dim)' }}>
                      {JSON.stringify(ext.data, null, 2)}
                    </pre>
                  </div>
                )
              })}
            </Section>
          )}
        </div>

        <div className="space-y-4">
          <RiskScore alerts={s.alerts} />

          {s.related_suppliers?.length > 0 && (
            <Section title="PROVEEDORES RELACIONADOS" icon={Users}>
              <div className="space-y-2">
                {s.related_suppliers.map((r, i) => (
                  <div key={i} className="pb-2 last:pb-0 border-b last:border-0" style={{ borderColor: 'rgba(22,32,56,0.6)' }}>
                    <Link to={`/suppliers/${r.supplier_rut}`}
                          className="text-[12px] font-medium hover:underline" style={{ color: 'var(--blue)' }}>
                      {r.supplier_name || r.supplier_rut}
                    </Link>
                    <p className="font-mono text-[10px] mt-0.5" style={{ color: 'var(--muted)' }}>RUT: {r.supplier_rut}</p>
                    <div className="flex flex-wrap gap-1 mt-1">
                      {r.evidence?.shared_attributes?.map((attr, j) => (
                        <span key={j} className="intel-tag" style={{
                          color: '#ff8899', background: 'rgba(255,51,85,0.06)', borderColor: 'rgba(255,51,85,0.15)'
                        }}>
                          {attr.type}: {String(attr.value).slice(0, 20)}
                        </span>
                      ))}
                    </div>
                  </div>
                ))}
              </div>
            </Section>
          )}
        </div>
      </div>

      {/* Procurement history */}
      <Section title={`CONTRATOS ADJUDICADOS (${s.procurement_history?.length || 0})`} icon={FileText}>
        {s.procurement_history?.length === 0 ? (
          <p className="font-mono text-[11px]" style={{ color: 'var(--muted)' }}>SIN CONTRATOS REGISTRADOS</p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full intel-table">
              <thead>
                <tr>
                  <th className="text-left">ORGANISMO</th>
                  <th className="text-left">TITULO</th>
                  <th className="text-left">MODALIDAD</th>
                  <th className="text-left">FECHA</th>
                  <th className="text-right">MONTO</th>
                </tr>
              </thead>
              <tbody>
                {s.procurement_history.slice(0, 50).map((p, i) => (
                  <tr key={i}>
                    <td className="px-3 py-2 text-[11px]" style={{ color: 'var(--text-dim)' }}>
                      {p.buyer_name?.slice(0, 28) || p.buyer_rut}
                    </td>
                    <td className="px-3 py-2">
                      <Link to={`/procurements/${encodeURIComponent(p.ocid)}`}
                            className="text-[12px] hover:underline" style={{ color: 'var(--blue)' }}>
                        {p.title?.slice(0, 45) || p.ocid}
                      </Link>
                    </td>
                    <td className="px-3 py-2 font-mono text-[10px]" style={{ color: 'var(--muted)' }}>{p.method}</td>
                    <td className="px-3 py-2 font-mono text-[10px]" style={{ color: 'var(--muted)' }}>{fmtDate(p.date)}</td>
                    <td className="px-3 py-2 text-right">
                      {p.amount ? (
                        <span className="font-mono text-[11px] font-semibold" style={{ color: '#ffaa00' }}>
                          ${Math.round(p.amount).toLocaleString('es-CL')}
                        </span>
                      ) : '—'}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Section>
    </div>
  )
}

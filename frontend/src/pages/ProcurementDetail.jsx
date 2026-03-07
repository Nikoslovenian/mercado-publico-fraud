import { useParams, Link } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { getProcurement } from '../api/client'
import AlertBadge from '../components/AlertBadge'
import TypeBadge from '../components/TypeBadge'
import { ArrowLeft, FileText, ShieldAlert, Users, Package, Gavel, Building2 } from 'lucide-react'

function Section({ title, icon: Icon, children }) {
  return (
    <div className="intel-card p-5">
      <div className="section-header mb-4">
        {Icon && <Icon size={11} />}
        <span>{title}</span>
      </div>
      {children}
    </div>
  )
}

export default function ProcurementDetail() {
  const { ocid } = useParams()
  const { data: p, isLoading } = useQuery({
    queryKey: ['procurement', ocid],
    queryFn: () => getProcurement(decodeURIComponent(ocid)),
  })

  if (isLoading) return (
    <div className="flex items-center justify-center py-32">
      <div className="font-mono text-xs" style={{ color: 'var(--blue)' }}>CARGANDO PROCESO...</div>
    </div>
  )
  if (!p) return (
    <div className="flex items-center justify-center py-32">
      <div className="font-mono text-xs" style={{ color: '#ff3355' }}>PROCESO NO ENCONTRADO</div>
    </div>
  )

  const fmtDate = (d) => d ? new Date(d).toLocaleDateString('es-CL') : '—'
  const fmtAmt = (n) => n ? `$${Math.round(n).toLocaleString('es-CL')} CLP` : '—'

  return (
    <div className="max-w-5xl mx-auto space-y-4 animate-fadeIn">
      {/* Breadcrumb */}
      <div className="flex items-center gap-3">
        <Link to="/procurements" className="flex items-center gap-1 text-[11px] hover:underline transition-opacity" style={{ color: 'var(--muted)' }}>
          <ArrowLeft size={12} /> LICITACIONES
        </Link>
        <span style={{ color: 'var(--border)' }}>/</span>
        <span className="font-mono text-[11px]" style={{ color: 'var(--text-dim)' }}>
          {p.ocid.split('-').slice(-2).join('-')}
        </span>
      </div>

      {/* Header */}
      <div className="intel-card p-5">
        <div className="flex items-center gap-2 mb-2">
          <FileText size={14} style={{ color: 'var(--blue)' }} />
          <span className="font-mono text-[10px] tracking-widest" style={{ color: 'var(--muted)' }}>
            PROCESO DE LICITACION
          </span>
        </div>
        <h1 className="text-base font-bold mb-1" style={{ color: 'var(--text-bright)' }}>{p.title || p.ocid}</h1>
        <p className="font-mono text-[11px]" style={{ color: 'var(--muted)' }}>{p.ocid}</p>
      </div>

      {/* Alerts */}
      {p.alerts?.length > 0 && (
        <div className="intel-card p-4" style={{ borderColor: 'rgba(255,51,85,0.25)' }}>
          <div className="flex items-center gap-2 mb-3">
            <ShieldAlert size={13} style={{ color: '#ff3355' }} />
            <span className="font-mono text-[10px] font-bold tracking-wider" style={{ color: '#ff6688' }}>
              {p.alerts.length} ALERTA(S) EN ESTE PROCESO
            </span>
          </div>
          <div className="space-y-1.5">
            {p.alerts.map(a => (
              <div key={a.id} className="flex items-center gap-2 text-[12px]">
                <AlertBadge severity={a.severity} />
                <TypeBadge type={a.alert_type} />
                <Link to={`/alerts/${a.id}`} className="hover:underline" style={{ color: '#ff8899' }}>{a.title}</Link>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Info grid */}
      <Section title="INFORMACION DEL PROCESO" icon={Building2}>
        <div className="grid grid-cols-2 md:grid-cols-3 gap-x-6 gap-y-4 text-[12px]">
          {[
            ['Modalidad', p.method_details || p.method],
            ['Estado', p.status],
            ['Region', p.region],
            ['Inicio licitacion', fmtDate(p.tender_start)],
            ['Cierre licitacion', fmtDate(p.tender_end)],
            ['Fecha adjudicacion', fmtDate(p.award_date)],
          ].map(([label, value]) => (
            <div key={label}>
              <span className="text-[10px] block mb-0.5 font-mono tracking-wide" style={{ color: 'var(--muted)' }}>{label.toUpperCase()}</span>
              <span className="font-medium" style={{ color: 'var(--text)' }}>{value || '—'}</span>
            </div>
          ))}
          <div className="col-span-2 md:col-span-3">
            <span className="text-[10px] block mb-0.5 font-mono tracking-wide" style={{ color: 'var(--muted)' }}>ORGANISMO COMPRADOR</span>
            <span className="font-medium" style={{ color: 'var(--text)' }}>{p.buyer_name}</span>
            <span className="font-mono text-[10px] ml-2" style={{ color: 'var(--muted)' }}>RUT: {p.buyer_rut}</span>
          </div>
          <div className="col-span-2 md:col-span-3">
            <span className="text-[10px] block mb-0.5 font-mono tracking-wide" style={{ color: 'var(--muted)' }}>MONTO TOTAL</span>
            <span className="font-mono text-xl font-bold" style={{ color: '#ffaa00' }}>{fmtAmt(p.total_amount)}</span>
          </div>
        </div>
        {p.description && (
          <div className="mt-4 pt-3 border-t" style={{ borderColor: 'var(--border)' }}>
            <span className="text-[10px] block mb-1 font-mono tracking-wide" style={{ color: 'var(--muted)' }}>DESCRIPCION</span>
            <p className="text-[12px] leading-relaxed" style={{ color: 'var(--text-dim)' }}>{p.description}</p>
          </div>
        )}
      </Section>

      {/* Parties */}
      {p.parties?.length > 0 && (
        <Section title="PARTES INVOLUCRADAS" icon={Users}>
          <div className="space-y-2">
            {p.parties.map((party, i) => {
              const roleColors = {
                buyer: { color: '#4080ff', bg: 'rgba(64,128,255,0.1)', border: 'rgba(64,128,255,0.2)' },
                supplier: { color: '#00e5a0', bg: 'rgba(0,229,160,0.1)', border: 'rgba(0,229,160,0.2)' },
                tenderer: { color: '#ffaa00', bg: 'rgba(255,170,0,0.1)', border: 'rgba(255,170,0,0.2)' },
              }
              const rc = roleColors[party.role] || { color: 'var(--muted)', bg: 'rgba(255,255,255,0.03)', border: 'var(--border)' }
              return (
                <div key={i} className="flex items-center gap-3 py-2 border-b last:border-0 text-[12px]"
                     style={{ borderColor: 'rgba(22,32,56,0.6)' }}>
                  <span className="intel-tag shrink-0" style={{ color: rc.color, background: rc.bg, borderColor: rc.border }}>
                    {party.role.toUpperCase()}
                  </span>
                  {party.role === 'supplier' || party.role === 'tenderer' ? (
                    <Link to={`/suppliers/${party.rut}`} className="font-medium hover:underline" style={{ color: 'var(--blue)' }}>
                      {party.name}
                    </Link>
                  ) : (
                    <span className="font-medium" style={{ color: 'var(--text)' }}>{party.name}</span>
                  )}
                  <span className="font-mono text-[10px]" style={{ color: 'var(--muted)' }}>RUT: {party.rut}</span>
                  {party.region && <span className="text-[10px]" style={{ color: 'var(--muted)' }}>{party.region}</span>}
                </div>
              )
            })}
          </div>
        </Section>
      )}

      {/* Bids */}
      {p.bids?.length > 0 && (
        <Section title={`OFERTAS RECIBIDAS (${p.bids.length})`} icon={Gavel}>
          <div className="overflow-x-auto">
            <table className="w-full intel-table">
              <thead>
                <tr>
                  <th className="text-left">PROVEEDOR</th>
                  <th className="text-left">RUT</th>
                  <th className="text-right">MONTO</th>
                  <th className="text-left">ESTADO</th>
                </tr>
              </thead>
              <tbody>
                {p.bids.map((bid, i) => {
                  const isWinner = p.awards?.some(a => a.supplier_rut === bid.supplier_rut)
                  return (
                    <tr key={i} style={isWinner ? { background: 'rgba(0,229,160,0.04)' } : {}}>
                      <td className="px-3 py-2.5 text-[12px]">
                        <span className="font-medium" style={{ color: 'var(--text)' }}>
                          {bid.supplier_name || bid.supplier_rut}
                        </span>
                        {isWinner && (
                          <span className="ml-2 font-mono text-[9px] font-bold px-1.5 py-0.5 rounded"
                                style={{ color: '#00e5a0', background: 'rgba(0,229,160,0.1)', border: '1px solid rgba(0,229,160,0.2)' }}>
                            ADJUDICADO
                          </span>
                        )}
                      </td>
                      <td className="px-3 py-2.5">
                        <Link to={`/suppliers/${bid.supplier_rut}`} className="font-mono text-[10px] hover:underline" style={{ color: 'var(--blue)' }}>
                          {bid.supplier_rut}
                        </Link>
                      </td>
                      <td className="px-3 py-2.5 text-right">
                        <span className="font-mono text-[12px] font-semibold" style={{ color: 'var(--text)' }}>
                          {bid.amount ? `$${Math.round(bid.amount).toLocaleString('es-CL')}` : '—'}
                        </span>
                      </td>
                      <td className="px-3 py-2.5 font-mono text-[10px]" style={{ color: 'var(--muted)' }}>
                        {bid.status || '—'}
                      </td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
        </Section>
      )}

      {/* Items */}
      {p.items?.length > 0 && (
        <Section title={`ITEMS DEL PROCESO (${p.items.length})`} icon={Package}>
          <div className="overflow-x-auto">
            <table className="w-full intel-table">
              <thead>
                <tr>
                  <th className="text-left">DESCRIPCION</th>
                  <th className="text-left">UNSPSC</th>
                  <th className="text-right">CANT.</th>
                  <th className="text-left">UNIDAD</th>
                  <th className="text-right">P. UNIT.</th>
                  <th className="text-right">TOTAL</th>
                </tr>
              </thead>
              <tbody>
                {p.items.map((item, i) => (
                  <tr key={i}>
                    <td className="px-3 py-2.5 text-[12px]" style={{ color: 'var(--text)' }}>{item.description}</td>
                    <td className="px-3 py-2.5 font-mono text-[10px]" style={{ color: 'var(--muted)' }}>{item.unspsc_code || '—'}</td>
                    <td className="px-3 py-2.5 text-right font-mono text-[12px]" style={{ color: 'var(--text)' }}>{item.quantity}</td>
                    <td className="px-3 py-2.5 text-[11px]" style={{ color: 'var(--muted)' }}>{item.unit || '—'}</td>
                    <td className="px-3 py-2.5 text-right font-mono text-[12px]" style={{ color: 'var(--text)' }}>
                      {item.unit_price ? `$${Math.round(item.unit_price).toLocaleString('es-CL')}` : '—'}
                    </td>
                    <td className="px-3 py-2.5 text-right">
                      <span className="font-mono text-[12px] font-semibold" style={{ color: '#ffaa00' }}>
                        {item.total_price ? `$${Math.round(item.total_price).toLocaleString('es-CL')}` : '—'}
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Section>
      )}
    </div>
  )
}

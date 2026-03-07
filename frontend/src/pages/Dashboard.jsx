import { useQuery } from '@tanstack/react-query'
import { getStats } from '../api/client'
import {
  BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer,
  CartesianGrid, AreaChart, Area, Cell, PieChart, Pie
} from 'recharts'
import {
  ShieldAlert, TrendingUp, Building2, DollarSign,
  AlertTriangle, Activity, Target, Eye, Crosshair,
  Radar, Zap, BarChart3, ArrowUpRight
} from 'lucide-react'
import { Link } from 'react-router-dom'
import AlertBadge from '../components/AlertBadge'
import { TYPE_META } from '../components/TypeBadge'

function fmt(n) {
  if (!n || isNaN(n)) return '$0'
  if (n >= 1e12) return '$' + (n / 1e12).toFixed(2) + 'T'
  if (n >= 1e9) return '$' + (n / 1e9).toFixed(1) + 'B'
  if (n >= 1e6) return '$' + (n / 1e6).toFixed(0) + 'M'
  return '$' + Math.round(n).toLocaleString('es-CL')
}

const TYPE_COLORS_MAP = {
  FRAC: '#9060ff', CONC: '#4080ff', COLU: '#ff3355', COLU2: '#ff6680',
  PLAZ: '#ffaa00', RELA: '#00c8e0', PREC: '#ffd060', NUEV: '#00e5a0',
  TRAT: '#80a0ff', DTDR: '#ff80aa', CONF: '#ff9944',
  UNIC: '#e060c0', TEMP: '#60d0ff',
}

const TYPE_DESC = {
  FRAC: 'Compras divididas para evadir licitacion publica',
  CONC: 'Mercado dominado por un proveedor (HHI elevado)',
  COLU: 'Shadow bidding: perdedor pierde por margen minimo',
  COLU2: 'Grupo de proveedores rota adjudicaciones',
  PLAZ: 'Plazos inferiores a los minimos legales',
  RELA: 'Proveedores con datos compartidos compiten entre si',
  PREC: 'Precios superiores a 2 desviaciones estandar',
  NUEV: 'Empresa recien constituida gana alto contrato',
  TRAT: 'Uso excesivo de trato directo (>30%)',
  DTDR: 'Desierta seguida de trato directo a participante',
  CONF: 'Proveedor vinculado a funcionario del organismo',
  UNIC: 'Licitaciones con sistematico oferente unico',
  TEMP: 'Patrones temporales anomalos detectados',
}

function ChartTooltip({ active, payload, label }) {
  if (!active || !payload?.length) return null
  return (
    <div className="intel-tooltip">
      <p style={{ color: 'var(--muted)', marginBottom: 3, fontSize: 10 }}>{label}</p>
      {payload.map((p, i) => (
        <p key={i} style={{ color: p.color || 'var(--text)', fontSize: 11 }}>
          {p.name}: <strong>{typeof p.value === 'number' ? p.value.toLocaleString('es-CL') : p.value}</strong>
        </p>
      ))}
    </div>
  )
}

function KPI({ label, value, sub, color, icon: Icon, delay = 0, glow }) {
  const accentColors = {
    red: '#ff3355', amber: '#ffaa00', green: '#00e5a0', blue: '#4080ff', cyan: '#00c8e0', purple: '#9060ff'
  }
  const c = accentColors[color] || accentColors.blue
  return (
    <div className="kpi-card hover:translate-y-[-2px] transition-transform duration-300 animate-countUp bg-[#0a0e18]" style={{ '--accent-color': c, animationDelay: delay + 'ms' }}>
      <div className="absolute top-0 right-0 w-32 h-32 bg-opacity-20 rounded-full blur-2xl" style={{ background: c, opacity: 0.05 }}></div>
      <div className="flex items-start justify-between mb-2 relative z-10">
        <div className="p-1.5 rounded" style={{ background: c + '12', border: '1px solid ' + c + '25' }}>
          <Icon size={15} style={{ color: c }} />
        </div>
        {glow && <div className="w-2 h-2 rounded-full threat-dot relative"><div className="w-full h-full rounded-full animate-ping" style={{ background: c }}></div></div>}
      </div>
      <div className="kpi-value relative z-10" style={{ color: glow ? c : 'var(--text-bright)', textShadow: glow ? `0 0 10px ${c}55` : 'none' }}>{value}</div>
      <div className="kpi-label relative z-10">{label}</div>
      {sub && <div className="font-mono text-[10px] mt-1 relative z-10" style={{ color: 'var(--muted)' }}>{sub}</div>}
    </div>
  )
}

function ThreatRow({ type, count, percent, maxCount }) {
  const meta = TYPE_META[type] || { color: '#8090a8' }
  const barPct = maxCount ? (count / maxCount) * 100 : 0
  return (
    <Link to={'/alerts?alert_type=' + type} className="block group">
      <div className="flex items-center gap-2.5 py-2 border-b last:border-0 transition-all group-hover:bg-white/[0.01]"
        style={{ borderColor: 'rgba(22,32,56,0.6)' }}>
        <span className="font-mono text-[10px] font-bold w-11 shrink-0" style={{ color: meta.color }}>{type}</span>
        <div className="flex-1 min-w-0">
          <div className="intel-progress">
            <div className="intel-progress-bar"
              style={{ width: barPct + '%', background: meta.color, boxShadow: '0 0 6px ' + meta.color + '40' }} />
          </div>
        </div>
        <span className="font-mono text-[11px] font-semibold w-9 text-right" style={{ color: 'var(--text-bright)' }}>
          {count.toLocaleString()}
        </span>
        <span className="font-mono text-[10px] w-11 text-right" style={{ color: 'var(--muted)' }}>{percent}%</span>
      </div>
    </Link>
  )
}

export default function Dashboard() {
  const { data, isLoading, error } = useQuery({ queryKey: ['stats'], queryFn: getStats })

  if (isLoading) return (
    <div className="flex items-center justify-center py-32">
      <div className="text-center">
        <Radar size={28} className="mx-auto mb-3 radar-sweep" style={{ color: 'var(--blue)' }} />
        <div className="font-mono text-xs mb-2" style={{ color: 'var(--blue)' }}>INICIANDO SISTEMA...</div>
        <div className="intel-progress mx-auto" style={{ width: 200 }}>
          <div className="intel-progress-bar" style={{ width: '60%', background: 'var(--blue)' }} />
        </div>
      </div>
    </div>
  )

  if (error) return (
    <div className="flex items-center justify-center py-32">
      <div className="intel-card p-8 text-center" style={{ borderColor: 'rgba(255,51,85,0.3)' }}>
        <AlertTriangle size={28} className="mx-auto mb-3" style={{ color: '#ff3355' }} />
        <p className="font-mono text-xs" style={{ color: '#ff6688' }}>ERROR: CONEXION RECHAZADA</p>
        <p className="text-[11px] mt-1" style={{ color: 'var(--muted)' }}>Backend no disponible en puerto 8000</p>
      </div>
    </div>
  )

  const s = data.summary
  const totalAlerts = s.total_alerts || 0

  const byTypeMap = {}
    ; (data.alerts_by_type || []).forEach(r => { byTypeMap[r.type] = (byTypeMap[r.type] || 0) + r.count })
  const typeRows = Object.entries(byTypeMap).sort((a, b) => b[1] - a[1])
  const maxTypeCount = typeRows.length ? typeRows[0][1] : 1

  const sevMap = {}
    ; (data.alerts_by_severity || []).forEach(r => { sevMap[r.severity] = r.count })

  const monthlyData = (data.alerts_by_month || []).map(r => ({
    month: r.month ? r.month.slice(5) : '',
    alertas: r.count,
  }))

  const sevData = [
    { name: 'CRITICA', value: sevMap['alta'] || 0, color: '#ff3355' },
    { name: 'MODERADA', value: sevMap['media'] || 0, color: '#ffaa00' },
    { name: 'BAJA', value: sevMap['baja'] || 0, color: '#00c878' },
  ].filter(d => d.value > 0)

  return (
    <div className="space-y-4 animate-fadeIn">

      {/* Header */}
      <div className="flex items-start justify-between gap-4">
        <div>
          <div className="section-header mb-1">
            <Crosshair size={11} style={{ color: '#ff3355' }} />
            <span style={{ color: '#ff3355' }}>OPERACION MP2025 — ANALISIS DE INTELIGENCIA</span>
          </div>
          <h1 className="text-xl font-bold tracking-tight uppercase text-glow-blue" style={{ color: 'var(--text-bright)' }}>
            Centro Global de Operaciones (SOC)
          </h1>
        </div>
        <div className="flex gap-2 shrink-0">
          <Link to="/alerts?severity=alta" className="btn-intel btn-red">
            <AlertTriangle size={11} /> {(sevMap['alta'] || 0).toLocaleString()} CRITICAS
          </Link>
          <Link to="/alerts" className="btn-intel btn-blue">
            <Eye size={11} /> VER TODAS
          </Link>
        </div>
      </div>

      {/* KPIs */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3 stagger-children">
        <KPI icon={Building2} label="PROCESOS ANALIZADOS" value={(s.total_procurements || 0).toLocaleString('es-CL')} color="blue" delay={0} />
        <KPI icon={ShieldAlert} label="ALERTAS GENERADAS" value={(s.total_alerts || 0).toLocaleString('es-CL')} color="red" delay={50} glow />
        <KPI icon={TrendingUp} label="ENTIDADES MONITOREADAS" value={(s.total_suppliers || 0).toLocaleString('es-CL')} color="green" delay={100} />
        <KPI icon={DollarSign} label="MONTO ANALIZADO" value={fmt(s.total_amount_clp)} sub="CLP · Ene-Nov 2025" color="amber" delay={150} />
      </div>

      {/* Severity breakdown */}
      <div className="intel-card p-4">
        <div className="section-header mb-3">
          <Zap size={10} />
          <span>NIVEL DE AMENAZA POR SEVERIDAD</span>
        </div>
        <div className="grid grid-cols-3 gap-3">
          {[
            { key: 'alta', label: 'CRITICA', color: '#ff3355', icon: '!' },
            { key: 'media', label: 'MODERADA', color: '#ffaa00', icon: '▲' },
            { key: 'baja', label: 'BAJA', color: '#00c878', icon: '●' },
          ].map(({ key, label, color, icon }) => {
            const cnt = sevMap[key] || 0
            const pct = totalAlerts > 0 ? ((cnt / totalAlerts) * 100).toFixed(1) : '0.0'
            return (
              <Link key={key} to={'/alerts?severity=' + key}
                className="rounded p-3 block transition-all hover:brightness-110"
                style={{ background: color + '0a', border: '1px solid ' + color + '20' }}>
                <div className="flex items-center gap-2 mb-1.5">
                  <span className="font-mono text-sm font-bold" style={{ color }}>{icon}</span>
                  <span className="font-mono text-[10px] font-bold tracking-wider" style={{ color }}>{label}</span>
                </div>
                <p className="font-mono text-2xl font-bold" style={{ color: 'var(--text-bright)' }}>{cnt.toLocaleString()}</p>
                <div className="flex items-center gap-2 mt-1.5">
                  <div className="intel-progress flex-1">
                    <div className="intel-progress-bar" style={{ width: pct + '%', background: color }} />
                  </div>
                  <span className="font-mono text-[10px]" style={{ color: 'var(--muted)' }}>{pct}%</span>
                </div>
              </Link>
            )
          })}
        </div>
      </div>

      {/* Main grid: 2 cols left + 3 cols right */}
      <div className="grid grid-cols-1 xl:grid-cols-5 gap-4">

        {/* Left column */}
        <div className="xl:col-span-2 space-y-4">

          {/* Threat types */}
          <div className="intel-card p-4">
            <div className="flex items-center justify-between mb-3">
              <div className="section-header flex-1">
                <Target size={10} />
                <span>TIPOS DE FRAUDE DETECTADOS</span>
              </div>
              <span className="font-mono text-[10px] ml-2" style={{ color: 'var(--blue)' }}>{typeRows.length} activos</span>
            </div>
            <div>
              {typeRows.map(([type, count]) => (
                <ThreatRow key={type} type={type} count={count}
                  percent={totalAlerts > 0 ? ((count / totalAlerts) * 100).toFixed(1) : '0'}
                  maxCount={maxTypeCount} />
              ))}
              {typeRows.length === 0 && (
                <p className="text-[11px] py-6 text-center" style={{ color: 'var(--muted)' }}>
                  Sin alertas detectadas. Ejecute el motor de fraude.
                </p>
              )}
            </div>
          </div>

          {/* Top entities */}
          <div className="intel-card p-4">
            <div className="flex items-center justify-between mb-3">
              <div className="section-header flex-1">
                <Crosshair size={10} />
                <span>ENTIDADES DE MAYOR RIESGO</span>
              </div>
              <Link to="/suppliers?has_alerts=true" className="font-mono text-[10px]" style={{ color: 'var(--blue)' }}>
                ver todas <ArrowUpRight size={9} className="inline" />
              </Link>
            </div>
            {(data.top_suppliers_with_alerts || []).slice(0, 8).map((sup, i) => (
              <Link key={sup.rut} to={'/suppliers/' + sup.rut}
                className="flex items-center gap-2.5 py-2 border-b block transition-all hover:bg-white/[0.01]"
                style={{ borderColor: 'rgba(22,32,56,0.6)' }}>
                <span className="font-mono text-[10px] w-4 text-center shrink-0" style={{ color: 'var(--muted)' }}>
                  {String(i + 1).padStart(2, '0')}
                </span>
                <div className="flex-1 min-w-0">
                  <p className="text-[12px] font-medium truncate" style={{ color: 'var(--text)' }}>{sup.name || sup.rut}</p>
                  <p className="font-mono text-[10px]" style={{ color: 'var(--muted)' }}>{sup.rut}</p>
                </div>
                <AlertBadge severity={sup.max_severity} />
                <span className="font-mono text-[12px] font-bold w-6 text-right" style={{ color: 'var(--text-bright)' }}>
                  {sup.alert_count}
                </span>
              </Link>
            ))}
          </div>
        </div>

        {/* Right column */}
        <div className="xl:col-span-3 space-y-4">

          {/* Timeline */}
          <div className="intel-card p-4">
            <div className="flex items-center justify-between mb-3">
              <div className="section-header flex-1">
                <Activity size={10} />
                <span>EVOLUCION TEMPORAL DE ALERTAS 2025</span>
              </div>
              <span className="font-mono text-[10px]" style={{ color: 'var(--blue)' }}>MENSUAL</span>
            </div>
            <ResponsiveContainer width="100%" height={170}>
              <AreaChart data={monthlyData} margin={{ top: 4, right: 4, left: -10, bottom: 0 }}>
                <defs>
                  <linearGradient id="alertGrad" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor="#4080ff" stopOpacity={0.25} />
                    <stop offset="95%" stopColor="#4080ff" stopOpacity={0} />
                  </linearGradient>
                </defs>
                <CartesianGrid strokeDasharray="3 3" stroke="rgba(22,32,56,0.6)" vertical={false} />
                <XAxis dataKey="month" tick={{ fill: '#4a6080', fontSize: 10, fontFamily: 'JetBrains Mono' }} axisLine={false} tickLine={false} />
                <YAxis tick={{ fill: '#4a6080', fontSize: 10, fontFamily: 'JetBrains Mono' }} axisLine={false} tickLine={false} width={30} />
                <Tooltip content={<ChartTooltip />} />
                <Area dataKey="alertas" stroke="#4080ff" strokeWidth={2} fill="url(#alertGrad)"
                  dot={{ fill: '#4080ff', r: 2.5, strokeWidth: 0 }}
                  activeDot={{ fill: '#80b0ff', r: 4, strokeWidth: 2, stroke: '#4080ff' }} />
              </AreaChart>
            </ResponsiveContainer>
          </div>

          {/* Bar chart + donut side by side */}
          <div className="grid grid-cols-1 lg:grid-cols-5 gap-4">
            <div className="lg:col-span-3 intel-card p-4">
              <div className="section-header mb-3">
                <BarChart3 size={10} />
                <span>DISTRIBUCION POR TIPO</span>
              </div>
              <ResponsiveContainer width="100%" height={190}>
                <BarChart data={typeRows.map(([type, count]) => ({ type, count }))} layout="vertical"
                  margin={{ left: -5, right: 12, top: 0, bottom: 0 }}>
                  <XAxis type="number" tick={{ fill: '#4a6080', fontSize: 9, fontFamily: 'JetBrains Mono' }} axisLine={false} tickLine={false} />
                  <YAxis type="category" dataKey="type" width={40}
                    tick={{ fill: '#8090a8', fontSize: 10, fontFamily: 'JetBrains Mono', fontWeight: 600 }} axisLine={false} tickLine={false} />
                  <Tooltip content={<ChartTooltip />} />
                  <Bar dataKey="count" radius={[0, 3, 3, 0]} barSize={14}>
                    {typeRows.map(([type]) => (
                      <Cell key={type} fill={TYPE_COLORS_MAP[type] || '#4080ff'} fillOpacity={0.8} />
                    ))}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            </div>

            <div className="lg:col-span-2 intel-card p-4 flex flex-col items-center justify-center">
              <div className="section-header mb-2 w-full">
                <Radar size={10} />
                <span>SEVERIDAD</span>
              </div>
              <ResponsiveContainer width="100%" height={140}>
                <PieChart>
                  <Pie data={sevData} cx="50%" cy="50%" innerRadius={35} outerRadius={55}
                    dataKey="value" stroke="none" paddingAngle={3}>
                    {sevData.map((d, i) => <Cell key={i} fill={d.color} fillOpacity={0.85} />)}
                  </Pie>
                  <Tooltip content={<ChartTooltip />} />
                </PieChart>
              </ResponsiveContainer>
              <div className="flex gap-3 mt-1">
                {sevData.map(d => (
                  <div key={d.name} className="flex items-center gap-1.5">
                    <div className="w-2 h-2 rounded-full" style={{ background: d.color }} />
                    <span className="font-mono text-[9px]" style={{ color: 'var(--muted)' }}>{d.name}</span>
                  </div>
                ))}
              </div>
            </div>
          </div>

          {/* Region chart */}
          <div className="intel-card p-4">
            <div className="section-header mb-3">
              <Target size={10} />
              <span>DISTRIBUCION GEOGRAFICA — ALERTAS POR REGION</span>
            </div>
            <ResponsiveContainer width="100%" height={160}>
              <BarChart
                data={(data.alerts_by_region || []).slice(0, 10).map(r => ({
                  region: (r.region || '').split(' ').slice(-1)[0],
                  count: r.count
                }))}
                margin={{ top: 4, right: 4, left: -10, bottom: 24 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="rgba(22,32,56,0.6)" horizontal={false} />
                <XAxis dataKey="region" tick={{ fill: '#4a6080', fontSize: 9, fontFamily: 'JetBrains Mono' }}
                  axisLine={false} tickLine={false} angle={-35} textAnchor="end" />
                <YAxis tick={{ fill: '#4a6080', fontSize: 9, fontFamily: 'JetBrains Mono' }} axisLine={false} tickLine={false} width={28} />
                <Tooltip content={<ChartTooltip />} />
                <Bar dataKey="count" fill="#00c8e0" fillOpacity={0.7} radius={[2, 2, 0, 0]} barSize={18} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>
      </div>

      {/* Fraud indicators detail grid */}
      <div>
        <div className="section-header mb-3">
          <Target size={10} />
          <span>INDICADORES DE FRAUDE — CLASIFICACION Y ESTADO</span>
        </div>
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-3 stagger-children">
          {typeRows.map(([type, count]) => {
            const meta = TYPE_META[type]
            if (!meta) return null
            const desc = TYPE_DESC[type] || ''
            return (
              <Link key={type} to={'/alerts?alert_type=' + type}
                className="intel-card intel-card-accent p-3.5 block transition-all hover:brightness-105">
                <div className="flex items-start justify-between gap-2 mb-2">
                  <span className="font-mono text-xs font-bold" style={{ color: meta.color }}>{type}</span>
                  <span className="font-mono text-lg font-bold" style={{ color: 'var(--text-bright)' }}>{count.toLocaleString()}</span>
                </div>
                <p className="text-[11px] leading-relaxed" style={{ color: 'var(--text-dim)' }}>{desc}</p>
                <div className="mt-2.5 pt-2 border-t flex items-center gap-2" style={{ borderColor: 'var(--border)' }}>
                  <div className="intel-progress flex-1">
                    <div className="intel-progress-bar"
                      style={{ width: (maxTypeCount ? (count / maxTypeCount) * 100 : 0) + '%', background: meta.color }} />
                  </div>
                  <span className="font-mono text-[10px]" style={{ color: 'var(--blue)' }}>
                    {totalAlerts > 0 ? ((count / totalAlerts) * 100).toFixed(1) : '0'}%
                  </span>
                </div>
              </Link>
            )
          })}
        </div>
      </div>

      {/* Top buyers */}
      <div className="intel-card p-4">
        <div className="section-header mb-3">
          <Building2 size={10} />
          <span>ORGANISMOS CON MAYOR CONCENTRACION DE ALERTAS</span>
        </div>
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-5 gap-2">
          {(data.top_buyers_with_alerts || []).slice(0, 5).map((b, i) => (
            <Link key={b.rut} to={'/alerts?buyer_rut=' + b.rut}
              className="rounded p-3 block transition-all hover:brightness-110"
              style={{ background: 'var(--bg)', border: '1px solid var(--border)' }}>
              <span className="font-mono text-[10px]" style={{ color: 'var(--muted)' }}>#{i + 1}</span>
              <p className="text-[12px] font-medium leading-tight mt-1 mb-2" style={{ color: 'var(--text)' }}>
                {(b.name || b.rut).slice(0, 40)}
              </p>
              <p className="font-mono text-xl font-bold" style={{ color: '#ffaa00' }}>{b.alert_count}</p>
              <p className="text-[10px]" style={{ color: 'var(--muted)' }}>alertas detectadas</p>
            </Link>
          ))}
        </div>
      </div>
    </div>
  )
}

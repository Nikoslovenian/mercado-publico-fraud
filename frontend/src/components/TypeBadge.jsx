const TYPE_META = {
  FRAC:  { label: 'FRAC · Compra Fraccionada',     color: '#9060ff', bg: 'rgba(144,96,255,0.12)', border: 'rgba(144,96,255,0.3)' },
  CONC:  { label: 'CONC · Concentración',           color: '#4080ff', bg: 'rgba(64,128,255,0.12)',  border: 'rgba(64,128,255,0.3)' },
  COLU:  { label: 'COLU · Shadow Bidding',          color: '#ff3355', bg: 'rgba(255,51,85,0.12)',   border: 'rgba(255,51,85,0.3)' },
  COLU2: { label: 'COLU2 · Rotación Ganadores',     color: '#ff6680', bg: 'rgba(255,80,100,0.12)',  border: 'rgba(255,80,100,0.3)' },
  PLAZ:  { label: 'PLAZ · Plazo Anómalo',           color: '#ffaa00', bg: 'rgba(255,170,0,0.12)',   border: 'rgba(255,170,0,0.3)' },
  RELA:  { label: 'RELA · Prov. Relacionados',      color: '#00c8e0', bg: 'rgba(0,200,224,0.12)',   border: 'rgba(0,200,224,0.3)' },
  PREC:  { label: 'PREC · Precio Anómalo',          color: '#ffd060', bg: 'rgba(255,208,96,0.1)',   border: 'rgba(255,208,96,0.3)' },
  NUEV:  { label: 'NUEV · Empresa Nueva',           color: '#00e5a0', bg: 'rgba(0,229,160,0.1)',    border: 'rgba(0,229,160,0.25)' },
  TRAT:  { label: 'TRAT · Trato Directo Excesivo',  color: '#80a0ff', bg: 'rgba(128,160,255,0.1)',  border: 'rgba(128,160,255,0.25)' },
  DTDR:  { label: 'DTDR · Desierta + Trato Dir.',   color: '#ff80aa', bg: 'rgba(255,128,170,0.1)',  border: 'rgba(255,128,170,0.25)' },
  CONF:  { label: 'CONF · Conflicto de Interés',    color: '#ff9944', bg: 'rgba(255,153,68,0.1)',   border: 'rgba(255,153,68,0.25)' },
  UNIC:  { label: 'UNIC · Oferente Único',           color: '#e060c0', bg: 'rgba(224,96,192,0.1)',   border: 'rgba(224,96,192,0.25)' },
  TEMP:  { label: 'TEMP · Patrón Temporal',           color: '#60d0ff', bg: 'rgba(96,208,255,0.1)',   border: 'rgba(96,208,255,0.25)' },
  ADJU:  { label: 'ADJU · No Menor Precio',           color: '#ff6040', bg: 'rgba(255,96,64,0.1)',    border: 'rgba(255,96,64,0.25)' },
  DESC:  { label: 'DESC · Descalificación Sist.',     color: '#c070ff', bg: 'rgba(192,112,255,0.1)',  border: 'rgba(192,112,255,0.25)' },
  GEOG:  { label: 'GEOG · Anomalía Geográfica',       color: '#40d0a0', bg: 'rgba(64,208,160,0.1)',   border: 'rgba(64,208,160,0.25)' },
  UMBR:  { label: 'UMBR · Monto Cerca Umbral',        color: '#ffcc40', bg: 'rgba(255,204,64,0.1)',   border: 'rgba(255,204,64,0.25)' },
  VELO:  { label: 'VELO · Adjudicación Rápida',       color: '#ff4080', bg: 'rgba(255,64,128,0.1)',   border: 'rgba(255,64,128,0.25)' },
  LOBB:  { label: 'LOBB · Relación Pre-existente',    color: '#a0a0ff', bg: 'rgba(160,160,255,0.1)',  border: 'rgba(160,160,255,0.25)' },
  PARE:  { label: 'PARE · Parentesco Apellido',        color: '#ff9090', bg: 'rgba(255,144,144,0.1)',  border: 'rgba(255,144,144,0.25)' },
  DIVI:  { label: 'DIVI · División Contratos',         color: '#80e060', bg: 'rgba(128,224,96,0.1)',   border: 'rgba(128,224,96,0.25)' },
}

export default function TypeBadge({ type, label, short = false }) {
  const meta = TYPE_META[type] || { label: type, color: '#8090a8', bg: 'rgba(128,144,168,0.1)', border: 'rgba(128,144,168,0.25)' }
  const text = short ? type : (label || meta.label)
  return (
    <span
      className="rounded px-2 py-0.5 text-xs font-mono font-semibold whitespace-nowrap"
      style={{ color: meta.color, background: meta.bg, border: `1px solid ${meta.border}` }}
    >
      {text}
    </span>
  )
}

export { TYPE_META }

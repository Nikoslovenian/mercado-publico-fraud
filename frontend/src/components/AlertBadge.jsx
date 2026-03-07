export default function AlertBadge({ severity, size = 'sm' }) {
  const labels = { alta: 'ALTA', media: 'MEDIA', baja: 'BAJA' }
  const sz = size === 'lg' ? 'px-2.5 py-1 text-[11px]' : 'px-1.5 py-0.5 text-[10px]'
  const cls = { alta: 'severity-alta', media: 'severity-media', baja: 'severity-baja' }
  const dots = { alta: '#ff3355', media: '#ffaa00', baja: '#00c878' }
  return (
    <span className={`inline-flex items-center gap-1 rounded font-mono font-bold tracking-wider ${sz} ${cls[severity] || ''}`}
          style={!cls[severity] ? { background: 'rgba(74,96,128,0.1)', color: '#8090a8', border: '1px solid rgba(74,96,128,0.2)' } : {}}>
      <span className="w-1.5 h-1.5 rounded-full shrink-0" style={{ background: dots[severity] || '#8090a8' }} />
      {labels[severity] || severity?.toUpperCase()}
    </span>
  )
}

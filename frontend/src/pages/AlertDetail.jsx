import { useParams, Link } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { getAlert, updateAlertStatus } from '../api/client'
import AlertBadge from '../components/AlertBadge'
import { TYPE_META } from '../components/TypeBadge'
import { ArrowLeft, CheckCircle, XCircle, Eye, Shield, FileText, Database, Scale, AlertTriangle } from 'lucide-react'

const FRAUD_EXPLANATIONS = {
  FRAC: {
    title: 'Compra Fraccionada (Art. 8 Ley 19.886)',
    why: 'La ley de compras publicas establece que las entidades deben licitar cuando superan ciertos umbrales. Dividir compras artificialmente para mantenerse bajo el umbral es ilegal. Este patron sugiere evasion deliberada del proceso competitivo.',
    risk: 'Contratacion directa elude competencia, favoreciendo a un proveedor especifico sin proceso transparente.',
    legal: 'Art. 8 Ley 19.886; Res. Ex. N°1165 ChileCompra; Circular N°8 Contraloria.',
  },
  CONC: {
    title: 'Concentracion de Mercado (HHI Elevado)',
    why: 'El Indice Herfindahl-Hirschman (HHI) mide concentracion de mercado. Un HHI > 0.25 en un segmento indica que un proveedor controla mas del 25% del mercado, lo que puede indicar colusion o barreras de entrada artificiales.',
    risk: 'Falta de competencia efectiva puede inflar precios y reducir calidad. Posible captura regulatoria.',
    legal: 'Art. 4 DL 211 Libre Competencia; Guia TDLC sobre mercados concentrados.',
  },
  COLU: {
    title: 'Colusion / Shadow Bidding',
    why: 'En shadow bidding, proveedores acuerdan secretamente quien ganara la licitacion. El perdedor presenta oferta deliberadamente inferior para dar apariencia de competencia.',
    risk: 'Precios artificialmente altos. Cartel entre proveedores. Dano directo al erario publico.',
    legal: 'Art. 3 DL 211; Art. 285 Codigo Penal (fraude al Fisco).',
  },
  COLU2: {
    title: 'Rotacion de Ganadores (Bid Rotation)',
    why: 'Un grupo acotado de empresas se turna en ganar contratos de la misma categoria con el mismo organismo, sugiriendo coordinacion previa.',
    risk: 'Practica anticompetitiva que elimina la competencia real manteniendo los precios elevados.',
    legal: 'Art. 3 DL 211; Directrices OCDE sobre competencia en contratacion publica.',
  },
  PLAZ: {
    title: 'Plazo Irregular de Licitacion',
    why: 'La ley establece plazos minimos segun el tipo de licitacion (LP: 20 dias, LE: 10 dias, L1: 5 dias). Plazos menores impiden que proveedores calificados presenten ofertas.',
    risk: 'Restriccion artificial de competencia. Posible licitacion a medida para proveedor predeterminado.',
    legal: 'Art. 25 Reglamento Ley 19.886 (DS 250/2004); Circular ChileCompra N°9.',
  },
  RELA: {
    title: 'Proveedores Relacionados que Compiten',
    why: 'Cuando empresas con directivos, direccion o telefono comunes presentan ofertas en la misma licitacion, la competencia es simulada.',
    risk: 'Aparencia de competencia sin sustancia real. Posible fraude al proceso de seleccion.',
    legal: 'Art. 100 Ley 18.045 (personas relacionadas); Art. 285 Codigo Penal.',
  },
  PREC: {
    title: 'Precio Anomalo (Sobreprecio Estadistico)',
    why: 'El precio pagado supera en mas de 2 desviaciones estandar el promedio historico del mismo bien/servicio (codigo UNSPSC + unidad).',
    risk: 'Pago en exceso con fondos publicos. Posible kickback entre proveedor y funcionario.',
    legal: 'Art. 9 Ley 19.886 (precio de mercado como criterio); Normas de control interno CGR.',
  },
  NUEV: {
    title: 'Empresa Recien Constituida Gana Alto Contrato',
    why: 'Una empresa creada hace menos de 6 meses gana un contrato de alto valor. Puede indicar empresa creada especificamente para ganar esta licitacion.',
    risk: 'Empresa sin historial verificable de capacidad tecnica o financiera. Posible empresa de fachada.',
    legal: 'Art. 4 Ley 19.886 (requisitos de idoneidad); Bases de licitacion tipo ChileCompra.',
  },
  TRAT: {
    title: 'Uso Excesivo de Trato Directo',
    why: 'El organismo usa trato directo en mas del 30% de sus contratos, muy por encima del promedio nacional.',
    risk: 'Evasion del control preventivo. Contratos sin competencia ni transparencia.',
    legal: 'Art. 8 Ley 19.886; Art. 10 DS 250/2004 (causales trato directo).',
  },
  DTDR: {
    title: 'Licitacion Desierta + Trato Directo al Mismo Participante',
    why: 'Una licitacion se declara desierta y luego se contrata directamente a un proveedor que habia participado. Puede indicar manipulacion.',
    risk: 'Manipulacion del proceso: la declaratoria de desierta como mecanismo para justificar trato directo.',
    legal: 'Art. 8 Ley 19.886; Dictamen N°40.000 CGR sobre procedencia del trato directo.',
  },
  CONF: {
    title: 'Posible Conflicto de Interes',
    why: 'Se detecta potencial vinculacion entre el proveedor adjudicado y funcionarios del organismo comprador.',
    risk: 'Favoritismo en adjudicacion. Violacion de deberes funcionarios. Posible cohecho.',
    legal: 'Art. 62 N°6 Estatuto Administrativo; Art. 250 Codigo Penal (cohecho); Ley 20.880 sobre probidad.',
  },
  UNIC: {
    title: 'Oferente Unico Recurrente',
    why: 'Licitaciones que sistematicamente reciben un solo oferente, indicando posibles bases dirigidas o barreras de entrada artificiales.',
    risk: 'Ausencia de competencia real. Posibles bases de licitacion diseñadas para excluir competidores.',
    legal: 'Art. 9 Ley 19.886 (principio de libre concurrencia); Jurisprudencia TDLC.',
  },
  TEMP: {
    title: 'Patron Temporal Sospechoso',
    why: 'Publicaciones en horarios no laborales, concentracion excesiva al fin de año fiscal, o uso injustificado de clausulas de urgencia.',
    risk: 'Manipulacion de plazos para limitar competencia. Gasto acelerado de presupuesto sin control adecuado.',
    legal: 'Art. 25 DS 250/2004; Circular CGR sobre ejecucion presupuestaria.',
  },
  ADJU: {
    title: 'Adjudicacion a Oferente Mas Caro',
    why: 'La licitacion se adjudica a un oferente cuya oferta no es la mas economica, sin justificacion tecnica aparente. En licitaciones de bienes estandarizados, el precio deberia ser determinante.',
    risk: 'Favoritismo hacia un proveedor especifico. Posible pago de sobornos incluido en el precio inflado.',
    legal: 'Art. 6 Ley 19.886 (evaluacion objetiva); Art. 38 DS 250/2004 (criterios de evaluacion).',
  },
  DESC: {
    title: 'Descalificacion Sistematica de Oferentes',
    why: 'Organismos que descalifican un porcentaje anormalmente alto de oferentes pueden estar usando bases tecnicas restrictivas para dirigir la adjudicacion.',
    risk: 'Bases de licitacion diseñadas para excluir competidores legitimos. Restriccion artificial de competencia.',
    legal: 'Art. 9 Ley 19.886 (libre concurrencia); Art. 20 DS 250 (requisitos proporcionales).',
  },
  GEOG: {
    title: 'Anomalia Geografica - Proveedor Lejano',
    why: 'Un proveedor registrado en una region muy distante gana un contrato local sin presencia en la zona, sugiriendo posible empresa de fachada o relacion indebida.',
    risk: 'Empresa sin capacidad logistica real para cumplir. Posible proveedor vinculado al comprador.',
    legal: 'Art. 4 Ley 19.886 (idoneidad del proveedor); Criterios evaluacion capacidad tecnica.',
  },
  UMBR: {
    title: 'Monto Cercano a Umbral Legal',
    why: 'El monto se ubica sospechosamente cerca (90-100%) del umbral que cambiaria el tipo de licitacion requerida, sugiriendo manipulacion del monto para evitar mayor fiscalizacion.',
    risk: 'Evasion del proceso competitivo mas exigente. Posible subdeclaracion del monto real.',
    legal: 'Art. 5 Ley 19.886 (umbrales de licitacion); Res. ChileCompra sobre metodologias.',
  },
  VELO: {
    title: 'Adjudicacion Anomalamente Rapida',
    why: 'La evaluacion de ofertas se resuelve en horas o el mismo dia del cierre, cuando procesos complejos requieren analisis tecnico y economico detallado.',
    risk: 'Evaluacion pre-determinada. Las ofertas no fueron realmente analizadas. Adjudicatario decidido antes del cierre.',
    legal: 'Art. 37 DS 250/2004 (evaluacion de ofertas); Principio de transparencia.',
  },
  LOBB: {
    title: 'Relacion Pre-existente Proveedor-Comprador',
    why: 'Patron de tratos directos repetitivos al mismo proveedor o uso sistematico de urgencia para adjudicar al mismo proveedor, sugiriendo relacion indebida.',
    risk: 'Captura del organismo por proveedor. Uso de excepciones como mecanismo habitual de contratacion.',
    legal: 'Art. 8 Ley 19.886 (excepcionalidad del trato directo); Ley 20.730 (lobby).',
  },
  PARE: {
    title: 'Coincidencia de Apellidos Comprador-Proveedor',
    why: 'Se detecta coincidencia de apellidos entre el contacto del organismo comprador y el representante del proveedor, sugiriendo posible relacion familiar.',
    risk: 'Conflicto de interes por parentesco. Violacion del deber de abstension. Posible nepotismo.',
    legal: 'Art. 62 N°6 Estatuto Administrativo; Ley 20.880 sobre probidad publica.',
  },
  DIVI: {
    title: 'Division Artificial de Contratos',
    why: 'Multiples adjudicaciones al mismo proveedor en periodo corto, donde cada una esta bajo el umbral pero el total lo supera, sugiriendo fraccionamiento deliberado.',
    risk: 'Evasion de licitacion competitiva. Identico al fraccionamiento pero detectado por patron temporal buyer-supplier.',
    legal: 'Art. 8 Ley 19.886; Dictamen CGR N°36.620 sobre fraccionamiento.',
  },
}

function Field({ label, value, mono }) {
  if (!value) return null
  return (
    <div>
      <p className="font-mono text-[10px] tracking-wider mb-0.5" style={{ color: 'var(--muted)' }}>{label}</p>
      <p className={`text-[12px] ${mono ? 'font-mono' : ''}`} style={{ color: 'var(--text)' }}>{value}</p>
    </div>
  )
}

function EvidenceView({ evidence }) {
  if (!evidence) return <p className="font-mono text-[11px] py-4" style={{ color: 'var(--muted)' }}>Sin evidencia registrada.</p>
  return (
    <div className="rounded p-3 overflow-x-auto" style={{ background: 'var(--bg)', border: '1px solid var(--border)' }}>
      <pre className="text-[10px] leading-relaxed font-mono" style={{ color: 'var(--text-dim)', whiteSpace: 'pre-wrap' }}>
        {JSON.stringify(evidence, null, 2)}
      </pre>
    </div>
  )
}

export default function AlertDetail() {
  const { id } = useParams()
  const qc = useQueryClient()
  const { data: alert, isLoading } = useQuery({ queryKey: ['alert', id], queryFn: () => getAlert(id) })
  const mutation = useMutation({
    mutationFn: (status) => updateAlertStatus(id, status),
    onSuccess: () => qc.invalidateQueries(['alert', id]),
  })

  if (isLoading) return (
    <div className="flex items-center justify-center py-32">
      <div className="font-mono text-[11px]" style={{ color: 'var(--blue)' }}>CARGANDO EXPEDIENTE...</div>
    </div>
  )
  if (!alert) return (
    <div className="flex items-center justify-center py-32">
      <div className="font-mono text-[11px]" style={{ color: '#ff3355' }}>EXPEDIENTE NO ENCONTRADO</div>
    </div>
  )

  const meta = TYPE_META[alert.alert_type] || { color: '#8090a8' }
  const expl = FRAUD_EXPLANATIONS[alert.alert_type]

  const statusColors = {
    open:      { color: '#ffaa00', bg: 'rgba(255,170,0,0.08)',   border: 'rgba(255,170,0,0.2)' },
    reviewed:  { color: '#4080ff', bg: 'rgba(64,128,255,0.08)',  border: 'rgba(64,128,255,0.2)' },
    confirmed: { color: '#ff3355', bg: 'rgba(255,51,85,0.08)',   border: 'rgba(255,51,85,0.2)' },
    dismissed: { color: '#4a6080', bg: 'rgba(74,96,128,0.06)', border: 'rgba(74,96,128,0.15)' },
  }
  const sc = statusColors[alert.status] || statusColors.open

  return (
    <div className="max-w-5xl mx-auto space-y-4 animate-fadeIn">

      {/* Breadcrumb */}
      <div className="flex items-center gap-3">
        <Link to="/alerts" className="flex items-center gap-1 text-[11px] hover:underline" style={{ color: 'var(--muted)' }}>
          <ArrowLeft size={12} /> ALERTAS
        </Link>
        <span style={{ color: 'var(--border)' }}>/</span>
        <span className="font-mono text-[11px]" style={{ color: 'var(--text-dim)' }}>EXPEDIENTE #{alert.id}</span>
      </div>

      {/* Header */}
      <div className="intel-card p-5">
        <div className="flex items-start justify-between gap-4 mb-3">
          <div className="flex items-center gap-2">
            <Shield size={16} style={{ color: meta.color, filter: `drop-shadow(0 0 4px ${meta.color}40)` }} />
            <span className="font-mono text-[10px] font-bold tracking-widest" style={{ color: meta.color }}>
              ALERTA {alert.alert_type} — #{alert.id}
            </span>
          </div>
          <div className="flex items-center gap-2 shrink-0">
            <span className="intel-tag" style={{ color: sc.color, background: sc.bg, borderColor: sc.border }}>
              {(alert.status || 'open').toUpperCase()}
            </span>
            <AlertBadge severity={alert.severity} size="lg" />
          </div>
        </div>
        <h1 className="text-base font-bold mb-2" style={{ color: 'var(--text-bright)' }}>{alert.title}</h1>
        <p className="text-[12px] leading-relaxed" style={{ color: 'var(--text-dim)' }}>{alert.description}</p>
      </div>

      {/* Metadata */}
      <div className="intel-card p-5">
        <div className="section-header mb-4">
          <Database size={10} />
          <span>DATOS DEL EXPEDIENTE</span>
        </div>
        <div className="grid grid-cols-2 md:grid-cols-3 gap-x-6 gap-y-4">
          <Field label="ORGANISMO" value={alert.buyer_name} />
          {alert.buyer_rut && <Field label="RUT ORGANISMO" value={alert.buyer_rut} mono />}
          <Field label="PROVEEDOR" value={alert.supplier_name} />
          {alert.supplier_rut && <Field label="RUT PROVEEDOR" value={alert.supplier_rut} mono />}
          <Field label="REGION" value={alert.region} />
          {alert.amount_involved && (
            <div>
              <p className="font-mono text-[10px] tracking-wider mb-0.5" style={{ color: 'var(--muted)' }}>MONTO INVOLUCRADO</p>
              <p className="font-mono text-lg font-bold" style={{ color: '#ffaa00' }}>
                ${Math.round(alert.amount_involved).toLocaleString('es-CL')}
              </p>
            </div>
          )}
          {alert.ocid && (
            <div>
              <p className="font-mono text-[10px] tracking-wider mb-0.5" style={{ color: 'var(--muted)' }}>OCID</p>
              <Link to={'/procurements/' + encodeURIComponent(alert.ocid)}
                className="font-mono text-[11px] hover:underline" style={{ color: 'var(--blue)' }}>
                {alert.ocid}
              </Link>
            </div>
          )}
          <Field label="FECHA DETECCION"
            value={alert.created_at ? new Date(alert.created_at).toLocaleDateString('es-CL', { day: '2-digit', month: 'long', year: 'numeric' }) : null} />
        </div>

        {(alert.ocid || alert.supplier_rut) && (
          <div className="mt-4 pt-3 border-t flex flex-wrap gap-2" style={{ borderColor: 'var(--border)' }}>
            {alert.ocid && (
              <Link to={'/procurements/' + encodeURIComponent(alert.ocid)} className="btn-intel btn-blue">
                <FileText size={11} /> Ver proceso
              </Link>
            )}
            {alert.supplier_rut && (
              <Link to={'/suppliers/' + alert.supplier_rut} className="btn-intel btn-cyan">
                Ver proveedor
              </Link>
            )}
          </div>
        )}
      </div>

      {/* Fraud explanation */}
      {expl && (
        <div className="intel-card p-5" style={{ borderColor: 'rgba(255,170,0,0.15)' }}>
          <div className="section-header mb-3">
            <AlertTriangle size={10} style={{ color: '#ffaa00' }} />
            <span style={{ color: '#ffaa00' }}>POR QUE ES UN INDICADOR DE FRAUDE</span>
          </div>
          <h3 className="text-[13px] font-bold mb-2" style={{ color: 'var(--text-bright)' }}>{expl.title}</h3>
          <p className="text-[12px] leading-relaxed mb-4" style={{ color: 'var(--text-dim)' }}>{expl.why}</p>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
            <div className="rounded p-3" style={{ background: 'rgba(255,51,85,0.04)', border: '1px solid rgba(255,51,85,0.12)' }}>
              <p className="font-mono text-[10px] font-bold mb-1 tracking-wider" style={{ color: '#ff6688' }}>RIESGO IDENTIFICADO</p>
              <p className="text-[11px] leading-relaxed" style={{ color: 'var(--text-dim)' }}>{expl.risk}</p>
            </div>
            <div className="rounded p-3" style={{ background: 'rgba(64,128,255,0.04)', border: '1px solid rgba(64,128,255,0.12)' }}>
              <p className="font-mono text-[10px] font-bold mb-1 tracking-wider" style={{ color: '#80b0ff' }}>MARCO LEGAL</p>
              <p className="text-[11px] leading-relaxed font-mono" style={{ color: 'var(--text-dim)' }}>{expl.legal}</p>
            </div>
          </div>
        </div>
      )}

      {/* Evidence */}
      <div className="intel-card p-5">
        <div className="section-header mb-3">
          <Scale size={10} />
          <span>EVIDENCIA — FUENTE OCDS MERCADO PUBLICO</span>
        </div>
        <p className="text-[10px] italic mb-3" style={{ color: 'var(--muted)' }}>
          Datos directos de archivos JSON OCDS del repositorio oficial.
        </p>
        <EvidenceView evidence={alert.evidence} />
      </div>

      {/* Actions */}
      <div className="intel-card p-5">
        <div className="section-header mb-3">
          <CheckCircle size={10} />
          <span>ACCIONES</span>
        </div>
        <div className="flex flex-wrap gap-2">
          <button onClick={() => mutation.mutate('reviewed')} className="btn-intel btn-blue">
            <Eye size={11} /> Marcar revisada
          </button>
          <button onClick={() => mutation.mutate('confirmed')} className="btn-intel btn-red">
            <CheckCircle size={11} /> Confirmar fraude
          </button>
          <button onClick={() => mutation.mutate('dismissed')} className="btn-intel btn-gray">
            <XCircle size={11} /> Descartar
          </button>
        </div>
      </div>
    </div>
  )
}

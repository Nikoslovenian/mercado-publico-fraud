import { useEffect, useRef, useState } from 'react'
import { useParams, useNavigate, Link } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { getSupplierNetwork } from '../api/client'
import * as d3 from 'd3'
import { ArrowLeft, Share2, Search, Radar } from 'lucide-react'

function ForceGraph({ nodes, edges, onNodeClick }) {
  const svgRef = useRef(null)

  useEffect(() => {
    if (!nodes?.length || !svgRef.current) return

    const width = svgRef.current.clientWidth || 800
    const height = 500

    const svg = d3.select(svgRef.current)
    svg.selectAll('*').remove()

    // Background
    svg.append('rect')
      .attr('width', width)
      .attr('height', height)
      .attr('fill', '#060a10')

    // Grid dots
    const gridG = svg.append('g').attr('class', 'grid')
    for (let x = 0; x < width; x += 30) {
      for (let y = 0; y < height; y += 30) {
        gridG.append('circle')
          .attr('cx', x).attr('cy', y).attr('r', 0.5)
          .attr('fill', 'rgba(64,128,255,0.08)')
      }
    }

    const g = svg.append('g')

    svg.call(d3.zoom().scaleExtent([0.3, 3]).on('zoom', e => g.attr('transform', e.transform)))

    const d3Nodes = nodes.map(n => ({ ...n }))
    const d3Links = edges.map(e => ({
      source: e.source,
      target: e.target,
      relations: e.relations,
      shared: e.shared_procurements,
    }))

    const simulation = d3.forceSimulation(d3Nodes)
      .force('link', d3.forceLink(d3Links).id(d => d.id).distance(120))
      .force('charge', d3.forceManyBody().strength(-300))
      .force('center', d3.forceCenter(width / 2, height / 2))
      .force('collision', d3.forceCollide(40))

    const maxAlerts = Math.max(...nodes.map(n => n.alert_count), 1)
    const colorScale = d3.scaleSequential()
      .domain([0, maxAlerts])
      .interpolator(t => d3.interpolateRgb('#162038', '#ff2244')(t))

    // Links
    const link = g.selectAll('line')
      .data(d3Links)
      .join('line')
      .attr('stroke', d => d.shared > 0 ? '#ff3355' : '#1e3050')
      .attr('stroke-width', d => d.shared > 0 ? 2 : 1)
      .attr('stroke-dasharray', d => d.shared > 0 ? null : '4,3')
      .attr('stroke-opacity', d => d.shared > 0 ? 0.8 : 0.4)

    // Nodes
    const node = g.selectAll('g.node')
      .data(d3Nodes)
      .join('g')
      .attr('class', 'node')
      .style('cursor', 'pointer')
      .call(d3.drag()
        .on('start', (e, d) => { if (!e.active) simulation.alphaTarget(0.3).restart(); d.fx = d.x; d.fy = d.y })
        .on('drag', (e, d) => { d.fx = e.x; d.fy = e.y })
        .on('end', (e, d) => { if (!e.active) simulation.alphaTarget(0); d.fx = null; d.fy = null })
      )
      .on('click', (e, d) => onNodeClick(d.id))

    // Center node glow
    node.filter(d => d.level === 0)
      .append('circle')
      .attr('r', 28)
      .attr('fill', 'none')
      .attr('stroke', '#4080ff')
      .attr('stroke-width', 1)
      .attr('stroke-opacity', 0.2)

    node.append('circle')
      .attr('r', d => d.level === 0 ? 22 : 16)
      .attr('fill', d => d.alert_count > 0 ? colorScale(d.alert_count) : '#0e1628')
      .attr('stroke', d => d.level === 0 ? '#4080ff' : (d.alert_count > 0 ? '#ff3355' : '#1e3050'))
      .attr('stroke-width', d => d.level === 0 ? 2 : 1.5)

    node.append('text')
      .attr('text-anchor', 'middle')
      .attr('dy', '0.35em')
      .attr('font-size', '8px')
      .attr('font-family', 'JetBrains Mono, monospace')
      .attr('fill', '#8090a8')
      .text(d => (d.name || d.id).split(' ').slice(0, 2).join(' '))

    // Tooltip
    const tooltip = d3.select('body').append('div')
      .attr('class', 'intel-tooltip')
      .style('visibility', 'hidden')

    node.on('mouseenter', (e, d) => {
      const relEdges = d3Links.filter(l =>
        (l.source.id || l.source) === d.id || (l.target.id || l.target) === d.id
      )
      const relTypes = new Set()
      relEdges.forEach(l => {
        if (l.relations) l.relations.forEach(r => relTypes.add(r.type || r))
      })
      const relStr = relTypes.size > 0
        ? '<br><span style="color:#4a6080">Relaciones:</span> ' + [...relTypes].join(', ')
        : ''
      const alertStr = d.alert_count > 0
        ? '<br><span style="color:#ff6688">' + d.alert_count + ' alertas</span>'
        : '<br><span style="color:#00e5a0">Sin alertas</span>'

      tooltip.html(
        '<span style="color:var(--text-bright);font-weight:bold">' + (d.name || d.id) + '</span>' +
        '<br><span style="color:#4a6080">RUT:</span> ' + d.id +
        alertStr + relStr
      )
      tooltip.style('visibility', 'visible')
    })
    .on('mousemove', (e) => {
      tooltip.style('top', (e.pageY - 10) + 'px').style('left', (e.pageX + 15) + 'px')
    })
    .on('mouseleave', () => {
      tooltip.style('visibility', 'hidden')
    })

    simulation.on('tick', () => {
      link
        .attr('x1', d => d.source.x).attr('y1', d => d.source.y)
        .attr('x2', d => d.target.x).attr('y2', d => d.target.y)
      node.attr('transform', d => `translate(${d.x},${d.y})`)
    })

    return () => {
      simulation.stop()
      tooltip.remove()
    }
  }, [nodes, edges])

  return (
    <svg ref={svgRef} className="w-full" style={{ height: 500, background: '#060a10', display: 'block' }} />
  )
}

export default function NetworkPage() {
  const { rut } = useParams()
  const navigate = useNavigate()
  const [selectedRut, setSelectedRut] = useState(rut || '')
  const [searchInput, setSearchInput] = useState(rut || '')

  const { data, isLoading, error } = useQuery({
    queryKey: ['network', selectedRut],
    queryFn: () => getSupplierNetwork(selectedRut),
    enabled: !!selectedRut,
  })

  const handleSearch = () => {
    if (searchInput.trim()) {
      setSelectedRut(searchInput.trim())
      navigate('/network/' + searchInput.trim())
    }
  }

  return (
    <div className="space-y-4 animate-fadeIn">
      <div className="flex items-center gap-3">
        <Link to="/suppliers" className="hover:opacity-80 transition-opacity" style={{ color: 'var(--muted)' }}>
          <ArrowLeft size={16} />
        </Link>
        <div>
          <div className="section-header mb-0.5">
            <Share2 size={10} />
            <span>ANALISIS DE RED — ENTIDADES RELACIONADAS</span>
          </div>
          <h1 className="text-base font-bold" style={{ color: 'var(--text-bright)' }}>Red de Proveedores</h1>
        </div>
      </div>

      <div className="intel-card p-3">
        <p className="text-[11px] mb-2" style={{ color: 'var(--muted)' }}>
          Ingrese el RUT de un proveedor para visualizar su red de relaciones.
        </p>
        <div className="flex gap-2">
          <input
            type="text"
            placeholder="Ej: 77070170-8"
            value={searchInput}
            onChange={e => setSearchInput(e.target.value)}
            onKeyDown={e => e.key === 'Enter' && handleSearch()}
            className="intel-input flex-1 max-w-xs"
          />
          <button onClick={handleSearch} className="btn-intel btn-blue">
            <Search size={12} /> ANALIZAR
          </button>
        </div>
      </div>

      {!selectedRut && (
        <div className="text-center py-20">
          <Radar size={28} className="mx-auto mb-3" style={{ color: 'var(--border)' }} />
          <p className="font-mono text-[11px]" style={{ color: 'var(--border)' }}>
            INGRESA UN RUT PARA INICIAR EL ANALISIS
          </p>
        </div>
      )}

      {selectedRut && isLoading && (
        <div className="text-center py-20">
          <Radar size={28} className="mx-auto mb-3 radar-sweep" style={{ color: 'var(--blue)' }} />
          <p className="font-mono text-[11px]" style={{ color: 'var(--blue)' }}>MAPEANDO RED...</p>
        </div>
      )}

      {selectedRut && error && (
        <div className="intel-card p-4 text-center" style={{ borderColor: 'rgba(255,51,85,0.2)' }}>
          <p className="font-mono text-[11px]" style={{ color: '#ff6688' }}>PROVEEDOR NO ENCONTRADO</p>
        </div>
      )}

      {data && (
        <>
          {data.nodes?.length <= 1 && (
            <div className="intel-card p-4 text-[12px] font-mono" style={{ color: '#00e5a0', borderColor: 'rgba(0,229,160,0.2)' }}>
              SIN RELACIONES DETECTADAS
            </div>
          )}
          {data.nodes?.length > 1 && (
            <>
              <div className="intel-card p-3">
                <div className="flex flex-wrap items-center gap-4 font-mono text-[11px]" style={{ color: 'var(--text-dim)' }}>
                  <span><span style={{ color: 'var(--blue)' }}>{data.nodes.length}</span> nodos</span>
                  <span style={{ color: 'var(--border)' }}>|</span>
                  <span><span style={{ color: '#80a0ff' }}>{data.edges.length}</span> relaciones</span>
                  {data.edges.some(e => e.shared_procurements > 0) && (
                    <>
                      <span style={{ color: 'var(--border)' }}>|</span>
                      <span style={{ color: '#ff3355' }}>ALERTA: Lineas rojas = competencia en mismo proceso</span>
                    </>
                  )}
                </div>
              </div>

              <div className="intel-card overflow-hidden" style={{ padding: 0 }}>
                <div className="px-3 py-2 border-b flex items-center gap-2" style={{ borderColor: 'var(--border)' }}>
                  <span className="font-mono text-[10px]" style={{ color: 'var(--muted)' }}>GRAFO DE RELACIONES — ZOOM/ARRASTRAR</span>
                </div>
                <ForceGraph
                  nodes={data.nodes}
                  edges={data.edges}
                  onNodeClick={(rutClick) => {
                    setSearchInput(rutClick)
                    setSelectedRut(rutClick)
                    navigate('/network/' + rutClick)
                  }}
                />
                <div className="px-3 py-2 border-t flex flex-wrap items-center gap-x-5 gap-y-1" style={{ borderColor: 'var(--border)' }}>
                  {[
                    [{ w: 20, h: 2, bg: '#ff3355' }, 'Compiten en misma licitacion'],
                    [{ w: 20, h: 2, bg: '#1e3050', dash: true }, 'Comparten datos'],
                    [{ w: 12, h: 12, rounded: true, bg: '#0e1628', border: '#4080ff' }, 'Nodo buscado'],
                    [{ w: 12, h: 12, rounded: true, bg: '#ff2244', border: '#ff3355' }, 'Con alertas'],
                  ].map(([style, label], i) => (
                    <div key={i} className="flex items-center gap-2">
                      <div style={{
                        width: style.w, height: style.h,
                        borderRadius: style.rounded ? '50%' : 0,
                        background: style.bg,
                        border: style.border ? `1.5px solid ${style.border}` : 'none',
                        borderTop: style.dash ? `2px dashed ${style.bg}` : undefined,
                      }} />
                      <span className="font-mono text-[9px]" style={{ color: 'var(--muted)' }}>{label}</span>
                    </div>
                  ))}
                </div>
              </div>

              <div className="grid grid-cols-1 md:grid-cols-2 gap-2">
                {data.nodes.map(n => (
                  <div key={n.id} className="intel-card p-3 flex items-center justify-between">
                    <div>
                      <Link to={'/suppliers/' + n.id}
                            className="text-[12px] font-medium hover:underline" style={{ color: 'var(--blue)' }}>
                        {n.name}
                      </Link>
                      <p className="font-mono text-[10px] mt-0.5" style={{ color: 'var(--muted)' }}>RUT: {n.id}</p>
                    </div>
                    {n.alert_count > 0 && (
                      <span className="intel-tag" style={{
                        color: '#ff6688', background: 'rgba(255,51,85,0.08)', borderColor: 'rgba(255,51,85,0.2)'
                      }}>
                        {n.alert_count} ALERTAS
                      </span>
                    )}
                  </div>
                ))}
              </div>
            </>
          )}
        </>
      )}
    </div>
  )
}

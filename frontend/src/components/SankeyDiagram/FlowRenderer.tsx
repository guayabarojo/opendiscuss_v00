import React, { useEffect, useRef } from 'react'
import * as d3 from 'd3'
import {
  sankey as d3Sankey,
  sankeyLinkHorizontal,
  SankeyNode as D3SankeyNode,
  SankeyLink as D3SankeyLink,
} from 'd3-sankey'
import type { Flow, ThoughtSpace, SankeyColumn } from '../../types/api'

interface SankeyNodeData {
  id: string
  name: string
  value: number
  round: number
  cluster_id: string
  percentage: number
  color: string
}

interface SankeyLinkData {
  flow_id: string
  sourceClusterId: string
  targetClusterId: string
  value: number
  color: string
}

type SankeyNode = D3SankeyNode<SankeyNodeData, SankeyLinkData> & SankeyNodeData
type SankeyLink = D3SankeyLink<SankeyNodeData, SankeyLinkData> &
  SankeyLinkData

interface FlowRendererProps {
  columns: SankeyColumn[]
  flows: Flow[]
  width: number
  height: number
  onNodeHover?: (node: SankeyNode | null) => void
  onLinkHover?: (link: SankeyLink | null) => void
}

/**
 * FlowRenderer Component
 *
 * Renders multi-column Sankey diagram with flow edges between thought spaces:
 * - Draws edges (flows) between thought spaces across rounds
 * - Edge width proportional to participant_count
 * - Edge color matches source cluster color
 * - On hover: Highlight full path and show participant count
 * - Smooth curves using D3 path generators
 * - Animate edge rendering on mount
 *
 * Uses D3.js sankey layout for positioning and rendering.
 */
export const FlowRenderer: React.FC<FlowRendererProps> = ({
  columns,
  flows,
  width,
  height,
  onNodeHover,
  onLinkHover,
}) => {
  const svgRef = useRef<SVGSVGElement>(null)

  useEffect(() => {
    if (!svgRef.current || columns.length === 0) return

    // Clear previous rendering
    d3.select(svgRef.current).selectAll('*').remove()

    // Create SVG group
    const svg = d3.select(svgRef.current)
    const g = svg.append('g').attr('class', 'sankey-diagram')

    // Color scale for thought spaces
    const colorScale = d3.scaleOrdinal(d3.schemeTableau10)

    // Build nodes map
    const nodesMap = new Map<string, SankeyNode>()
    const nodes: SankeyNode[] = []

    columns.forEach((column, colIdx) => {
      column.thought_spaces.forEach((space: ThoughtSpace, spaceIdx) => {
        const node: SankeyNodeData = {
          id: space.cluster_id,
          name: space.label,
          value: space.member_count,
          round: column.round_num,
          cluster_id: space.cluster_id,
          percentage: space.member_pct * 100,
          color: colorScale(`${colIdx}-${spaceIdx}`),
        }
        nodes.push(node as any)
        nodesMap.set(space.cluster_id, node as any)
      })
    })

    // Build links from flows
    const links: any[] = flows
      .map((flow: Flow) => {
        const sourceNode = nodesMap.get(flow.source_cluster_id)
        const targetNode = nodesMap.get(flow.target_cluster_id)

        if (!sourceNode || !targetNode) {
          console.warn(
            `Flow ${flow.flow_id}: Could not find nodes for clusters`,
            flow
          )
          return null
        }

        return {
          source: flow.source_cluster_id,
          target: flow.target_cluster_id,
          value: flow.participant_count,
          flow_id: flow.flow_id,
          sourceClusterId: flow.source_cluster_id,
          targetClusterId: flow.target_cluster_id,
          color: sourceNode.color,
        }
      })
      .filter((link): link is any => link !== null)

    // Configure D3 Sankey layout
    const sankey = d3Sankey<any, any>()
      .nodeWidth(20)
      .nodePadding(15)
      .extent([
        [50, 50],
        [width - 50, height - 50],
      ])
      .nodeId((d: any) => d.id)

    // Generate layout
    const { nodes: layoutNodes, links: layoutLinks } = sankey({
      nodes: nodes,
      links: links,
    })

    // Draw links (flows) first so they're behind nodes
    const linkGroup = g
      .append('g')
      .attr('class', 'links')
      .attr('fill', 'none')

    const linkPaths = linkGroup
      .selectAll<SVGPathElement, any>('path')
      .data(layoutLinks)
      .enter()
      .append('path')
      .attr('class', 'link')
      .attr('d', sankeyLinkHorizontal())
      .attr('stroke', (d: any) => d.color)
      .attr('stroke-opacity', 0.3)
      .attr('stroke-width', (d: any) => Math.max(1, d.width || 0))
      .style('transition', 'stroke-opacity 0.2s, stroke-width 0.2s')
      .on('mouseenter', function (_event, d: any) {
        // Highlight this link
        d3.select(this)
          .attr('stroke-opacity', 0.7)
          .attr('stroke-width', Math.max(2, (d.width || 0) * 1.2))

        // Notify parent
        if (onLinkHover) {
          onLinkHover(d)
        }
      })
      .on('mouseleave', function (_event, d: any) {
        // Reset link appearance
        d3.select(this)
          .attr('stroke-opacity', 0.3)
          .attr('stroke-width', Math.max(1, d.width || 0))

        if (onLinkHover) {
          onLinkHover(null)
        }
      })

    // Animate links on mount
    linkPaths
      .attr('stroke-dasharray', function () {
        const length = this.getTotalLength()
        return `${length} ${length}`
      })
      .attr('stroke-dashoffset', function () {
        return this.getTotalLength()
      })
      .transition()
      .duration(800)
      .ease(d3.easeQuadInOut)
      .attr('stroke-dashoffset', 0)
      .on('end', function () {
        d3.select(this).attr('stroke-dasharray', 'none')
      })

    // Draw nodes
    const nodeGroup = g.append('g').attr('class', 'nodes')

    const nodeGroups = nodeGroup
      .selectAll<SVGGElement, any>('g')
      .data(layoutNodes)
      .enter()
      .append('g')
      .attr('class', 'node')
      .on('mouseenter', function (_event, d: any) {
        // Highlight node
        d3.select(this).select('rect').attr('stroke-width', 3)

        // Highlight connected links
        linkGroup
          .selectAll('path')
          .attr('stroke-opacity', (link: any) => {
            return link.source === d || link.target === d ? 0.7 : 0.1
          })
          .attr('stroke-width', (link: any) => {
            return link.source === d || link.target === d
              ? Math.max(2, (link.width || 0) * 1.2)
              : Math.max(1, link.width || 0)
          })

        if (onNodeHover) {
          onNodeHover(d)
        }
      })
      .on('mouseleave', function (_event, _d: any) {
        // Reset node
        d3.select(this).select('rect').attr('stroke-width', 2)

        // Reset links
        linkGroup
          .selectAll('path')
          .attr('stroke-opacity', 0.3)
          .attr('stroke-width', (link: any) => Math.max(1, link.width || 0))

        if (onNodeHover) {
          onNodeHover(null)
        }
      })

    // Node rectangles
    nodeGroups
      .append('rect')
      .attr('x', (d: any) => d.x0 || 0)
      .attr('y', (d: any) => d.y0 || 0)
      .attr('height', (d: any) => Math.max(0, (d.y1 || 0) - (d.y0 || 0)))
      .attr('width', (d: any) => Math.max(0, (d.x1 || 0) - (d.x0 || 0)))
      .attr('fill', (d: any) => d.color)
      .attr('stroke', '#fff')
      .attr('stroke-width', 2)
      .attr('rx', 4)
      .style('cursor', 'pointer')
      .style('transition', 'stroke-width 0.2s')

    // Node labels (on the right side of nodes)
    nodeGroups
      .append('text')
      .attr('x', (d: any) => (d.x1 || 0) + 6)
      .attr('y', (d: any) => ((d.y0 || 0) + (d.y1 || 0)) / 2)
      .attr('dy', '0.35em')
      .attr('text-anchor', 'start')
      .attr('font-size', '12px')
      .attr('font-weight', '500')
      .attr('fill', '#333')
      .text((d: any) => {
        const maxLength = 25
        const label =
          d.name.length > maxLength
            ? d.name.substring(0, maxLength) + '...'
            : d.name
        return `${label} (${d.value})`
      })
      .style('pointer-events', 'none')

    // Round labels at the top
    const roundXPositions = new Map<number, number>()
    layoutNodes.forEach((node: any) => {
      if (!roundXPositions.has(node.round)) {
        roundXPositions.set(node.round, ((node.x0 || 0) + (node.x1 || 0)) / 2)
      }
    })

    g.append('g')
      .attr('class', 'round-labels')
      .selectAll('text')
      .data(Array.from(roundXPositions.entries()))
      .enter()
      .append('text')
      .attr('x', d => d[1])
      .attr('y', 25)
      .attr('text-anchor', 'middle')
      .attr('font-size', '14px')
      .attr('font-weight', '600')
      .attr('fill', '#333')
      .text(d => `Round ${d[0]}`)
  }, [columns, flows, width, height, onNodeHover, onLinkHover])

  return (
    <svg
      ref={svgRef}
      width={width}
      height={height}
      className="flow-renderer"
      role="img"
      aria-label="Sankey diagram showing participant flow between thought spaces"
    />
  )
}

export default FlowRenderer

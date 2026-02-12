import React, { useEffect, useRef, useState } from 'react';
import * as d3 from 'd3';
import type { SankeyGraph, SankeyNode as SankeyNodeType, SankeyColumn } from '../../services/sankeyApi';
import { SankeyNode } from '../SankeyNode/SankeyNode';
import { SankeyEdge } from '../SankeyEdge/SankeyEdge';
import './SankeyDiagram.css';

interface SankeyDiagramProps {
  sankeyGraph: SankeyGraph;
  width?: number;
  height?: number;
  onNodeHover?: (node: SankeyNodeType | null) => void;
  minClusterSize?: number;  // Filter clusters by minimum size
}

interface LayoutNode extends SankeyNodeType {
  x: number;
  y: number;
  width: number;
  height: number;
  color: string;
  columnIndex: number;
}

/**
 * Group small clusters into "Other" category while preserving ALL participants
 * CONSTITUTIONAL REQUIREMENT: 100% participant representation at all granularity levels
 */
function filterClustersBySize(graph: SankeyGraph, minSize: number): SankeyGraph {
  if (minSize <= 0 || minSize <= 2) {
    return graph;  // No grouping needed - show all detail
  }

  const groupedColumns = graph.columns.map(column => {
    // Separate clusters into "show individually" vs "group as Other"
    const largeNodes = column.nodes.filter(node => node.user_count >= minSize);
    const smallNodes = column.nodes.filter(node => node.user_count < minSize);

    // If no small nodes, return column as-is
    if (smallNodes.length === 0) {
      return column;
    }

    // Create "Other" node that combines all small clusters
    const otherTotalCount = smallNodes.reduce((sum, n) => sum + n.user_count, 0);
    const otherNode: SankeyNodeType = {
      node_id: `other-round-${column.round_index}`,
      cluster_id: `other-round-${column.round_index}`,
      label_summary: `Other clusters (${smallNodes.length} smaller groups)`,
      user_count: otherTotalCount,
      user_pct: otherTotalCount / column.total_participants,
      display_group_id: null
    };

    // Combine large nodes + Other node
    const combinedNodes = [...largeNodes, otherNode];

    return {
      ...column,
      nodes: combinedNodes,
      total_participants: column.total_participants  // CRITICAL: Keep original count
    };
  });

  // Update edges: edges pointing to/from small clusters now point to "Other" node
  const smallClusterIds = new Set<string>();
  const roundToOtherId = new Map<number, string>();

  graph.columns.forEach((column) => {
    column.nodes.forEach(node => {
      if (node.user_count < minSize) {
        smallClusterIds.add(node.cluster_id);
      }
    });
    roundToOtherId.set(column.round_index, `other-round-${column.round_index}`);
  });

  // Remap edges
  const edgeMap = new Map<string, number>();  // key: from-to pair, value: user_count

  graph.edges.forEach(edge => {
    let fromId = edge.from_cluster_id;
    let toId = edge.to_cluster_id;

    // Remap small clusters to "Other" nodes
    if (smallClusterIds.has(fromId)) {
      fromId = roundToOtherId.get(edge.from_round_index) || fromId;
    }
    if (smallClusterIds.has(toId)) {
      toId = roundToOtherId.get(edge.to_round_index) || toId;
    }

    const key = `${fromId}->${toId}`;
    edgeMap.set(key, (edgeMap.get(key) || 0) + edge.user_count);
  });

  // Convert edge map back to array
  const groupedEdges = Array.from(edgeMap.entries()).map(([key, user_count]) => {
    const [fromId, toId] = key.split('->');

    // Find round indices from cluster IDs
    const fromRound = fromId.startsWith('other-round-')
      ? parseInt(fromId.replace('other-round-', ''))
      : graph.edges.find(e => e.from_cluster_id === fromId)?.from_round_index || 0;

    const toRound = toId.startsWith('other-round-')
      ? parseInt(toId.replace('other-round-', ''))
      : graph.edges.find(e => e.to_cluster_id === toId)?.to_round_index || 0;

    return {
      from_round_index: fromRound,
      to_round_index: toRound,
      from_cluster_id: fromId,
      to_cluster_id: toId,
      user_count,
      pct_of_from: null,
      pct_of_to: null
    };
  });

  return {
    ...graph,
    columns: groupedColumns,
    edges: groupedEdges
  };
}

/**
 * SankeyDiagram Component
 *
 * Main visualization component for Spec 005 Sankey diagrams.
 *
 * Features:
 * - Renders columns as vertical sections (one per round)
 * - Uses SankeyNode component for each node
 * - Renders edges (flows) between nodes in adjacent columns (Phase 4)
 * - Calculates positions and heights proportional to user_pct
 * - Responsive sizing (uses container dimensions)
 * - Color assignment using consistent hash function for display_group_id
 * - Round labels at top of each column
 *
 * Aligned with Spec 005 T029 and T041 requirements
 */
export const SankeyDiagram: React.FC<SankeyDiagramProps> = ({
  sankeyGraph,
  width: providedWidth,
  height: providedHeight,
  onNodeHover,
  minClusterSize = 0,  // Default to showing all clusters
}) => {
  const containerRef = useRef<HTMLDivElement>(null);
  const [dimensions, setDimensions] = useState({ width: 800, height: 600 });
  const [layoutNodes, setLayoutNodes] = useState<LayoutNode[]>([]);
  const [nodesByClusterId, setNodesByClusterId] = useState<Map<string, LayoutNode>>(new Map());

  // Constants for layout calculation - VERY WIDE for 10 rounds
  const MIN_COLUMN_SPACING = 600;  // Much wider - only 2-3 rounds visible at once
  const MARGIN_LEFT = 200;  // More space on left
  const MARGIN_RIGHT = 500;  // More space for labels on right
  const MIN_SVG_WIDTH = 2000;  // Minimum width to force scroll

  // Calculate dynamic SVG width based on number of columns
  // Always use MIN_COLUMN_SPACING regardless of container width to force scroll
  const calculateSVGWidth = (numColumns: number): number => {
    const minWidth = MARGIN_LEFT + MARGIN_RIGHT + (numColumns - 1) * MIN_COLUMN_SPACING;
    // Force horizontal scroll by always using the minimum width needed
    return Math.max(minWidth, MIN_SVG_WIDTH);
  };

  // Use calculated dimensions
  const height = providedHeight || dimensions.height;
  const width = calculateSVGWidth(sankeyGraph?.columns?.length || 1);

  // Handle responsive sizing
  useEffect(() => {
    if (!containerRef.current || providedWidth || providedHeight) return;

    const resizeObserver = new ResizeObserver((entries) => {
      for (const entry of entries) {
        const { width, height } = entry.contentRect;
        setDimensions({
          width: Math.max(width, 400),
          height: Math.max(height, 300),
        });
      }
    });

    resizeObserver.observe(containerRef.current);

    return () => {
      resizeObserver.disconnect();
    };
  }, [providedWidth, providedHeight]);

  // Calculate layout when graph or dimensions change
  useEffect(() => {
    if (!sankeyGraph || sankeyGraph.columns.length === 0) {
      setLayoutNodes([]);
      setNodesByClusterId(new Map());
      return;
    }

    // Apply cluster size filtering
    const filteredGraph = filterClustersBySize(sankeyGraph, minClusterSize);

    const { nodes, nodeMap } = calculateLayout(filteredGraph, height);
    setLayoutNodes(nodes);
    setNodesByClusterId(nodeMap);
  }, [sankeyGraph, height, minClusterSize]);

  // Color scale for nodes (using d3 color schemes)
  // Note: Color generation is handled in calculateLayout function

  if (!sankeyGraph || sankeyGraph.columns.length === 0) {
    return (
      <div className="sankey-diagram-empty">
        <p>No Sankey data available</p>
      </div>
    );
  }

  // Apply cluster size filtering for rendering
  const filteredGraph = filterClustersBySize(sankeyGraph, minClusterSize);

  return (
    <div ref={containerRef} className="sankey-diagram-container">
      <svg
        width={width}
        height={height}
        className="sankey-diagram-svg"
        role="img"
        aria-label="Sankey diagram showing participant distribution and movement across rounds"
        style={{ minWidth: `${width}px`, minHeight: `${height}px` }}
      >
        <g className="sankey-content">
          {/* Round labels */}
          {filteredGraph.columns.map((column) => {
            const columnX = getColumnX(column.round_index);
            const roundId = filteredGraph.rounds[column.round_index];
            const questionText = filteredGraph.round_questions?.[roundId] || `Round ${column.round_index + 1}`;

            return (
              <foreignObject
                key={`round-label-${column.round_index}`}
                x={columnX - 250}
                y={5}
                width={500}
                height={100}
              >
                <div
                  style={{
                    fontSize: '14px',
                    fontWeight: '600',
                    color: '#1e293b',
                    textAlign: 'center',
                    wordWrap: 'break-word',
                    lineHeight: '1.4',
                    cursor: 'help',
                    padding: '10px',
                    backgroundColor: 'rgba(255, 255, 255, 0.9)',
                    borderRadius: '6px',
                  }}
                  className="round-label"
                  title={questionText}
                >
                  {questionText}
                </div>
              </foreignObject>
            );
          })}

          {/* Edges (render first so they appear behind nodes) */}
          {filteredGraph.edges && filteredGraph.edges.length > 0 && (
            <g className="sankey-edges">
              {filteredGraph.edges.map((edge, index) => {
                const fromNode = nodesByClusterId.get(edge.from_cluster_id);
                const toNode = nodesByClusterId.get(edge.to_cluster_id);

                // Skip edge if nodes not found (defensive programming)
                if (!fromNode || !toNode) {
                  console.warn(
                    `Edge ${index} references missing nodes: ` +
                    `from ${edge.from_cluster_id} to ${edge.to_cluster_id}`
                  );
                  return null;
                }

                // Calculate edge split positions
                const sourceOffsets = calculateEdgeOffsets(
                  fromNode,
                  filteredGraph.edges.filter(e => e.from_cluster_id === edge.from_cluster_id),
                  edge,
                  'source'
                );

                const targetOffsets = calculateEdgeOffsets(
                  toNode,
                  filteredGraph.edges.filter(e => e.to_cluster_id === edge.to_cluster_id),
                  edge,
                  'target'
                );

                return (
                  <SankeyEdge
                    key={`edge-${edge.from_cluster_id}-${edge.to_cluster_id}-${index}`}
                    edge={edge}
                    fromNode={fromNode}
                    toNode={toNode}
                    sourceYOffset={sourceOffsets.yOffset}
                    sourceHeight={sourceOffsets.height}
                    targetYOffset={targetOffsets.yOffset}
                    targetHeight={targetOffsets.height}
                    sourceColor={fromNode.color}
                    targetColor={toNode.color}
                    opacity={0.7}
                  />
                );
              })}
            </g>
          )}

          {/* Nodes (render on top of edges) */}
          {layoutNodes.map((node, index) => (
            <SankeyNode
              key={`node-${node.node_id}-${index}`}
              node={node}
              x={node.x}
              y={node.y}
              width={node.width}
              height={node.height}
              color={node.color}
              onHover={onNodeHover}
            />
          ))}

          {/* Participant count labels */}
          {filteredGraph.columns.map((column) => {
            const columnX = getColumnX(column.round_index);
            return (
              <text
                key={`participant-count-${column.round_index}`}
                x={columnX}
                y={height - 10}
                textAnchor="middle"
                fontSize="12px"
                fontWeight="500"
                fill="#666666"
                className="participant-count-label"
              >
                {column.total_participants} participant{column.total_participants !== 1 ? 's' : ''}
              </text>
            );
          })}
        </g>
      </svg>
    </div>
  );
};

/**
 * Calculate X position for a column
 */
function getColumnX(columnIndex: number): number {
  const MARGIN_LEFT = 200;
  const MIN_COLUMN_SPACING = 600;  // Match the constant above

  // Use fixed spacing instead of dividing available width
  return MARGIN_LEFT + columnIndex * MIN_COLUMN_SPACING;
}

/**
 * Calculate layout positions for all nodes
 * Returns both the array of layout nodes and a map for edge lookups
 */
function calculateLayout(
  sankeyGraph: SankeyGraph,
  height: number
): { nodes: LayoutNode[]; nodeMap: Map<string, LayoutNode> } {
  const nodes: LayoutNode[] = [];
  const nodeMap = new Map<string, LayoutNode>();
  const margin = { top: 120, right: 200, bottom: 60, left: 200 };
  const availableHeight = height - margin.top - margin.bottom;
  const nodeWidth = 80;  // MUCH thicker nodes - very visible
  const nodePadding = 1;  // Minimal padding - traditional Sankey style

  const colorScale = d3.scaleOrdinal(d3.schemeTableau10);

  sankeyGraph.columns.forEach((column: SankeyColumn, columnIndex: number) => {
    const columnX = getColumnX(columnIndex);

    // Calculate total height needed for nodes + padding
    const totalPaddingHeight = (column.nodes.length - 1) * nodePadding;
    const availableForNodes = availableHeight - totalPaddingHeight;

    let currentY = margin.top;

    column.nodes.forEach((node, nodeIndex) => {
      // Height proportional to user_pct
      const nodeHeight = Math.max(availableForNodes * node.user_pct, 2);

      // Generate color - use gray for "Other" nodes
      let color: string;
      if (node.cluster_id.startsWith('other-round-')) {
        color = '#9e9e9e';  // Gray color for "Other" grouped nodes
      } else if (node.display_group_id) {
        color = colorScale(node.display_group_id);
      } else {
        color = colorScale(`${columnIndex}-${nodeIndex}`);
      }

      const layoutNode: LayoutNode = {
        ...node,
        x: columnX - nodeWidth / 2,
        y: currentY,
        width: nodeWidth,
        height: nodeHeight,
        color,
        columnIndex,
      };

      nodes.push(layoutNode);

      // Add to map for edge lookups (keyed by cluster_id)
      nodeMap.set(node.cluster_id, layoutNode);

      currentY += nodeHeight + nodePadding;
    });
  });

  return { nodes, nodeMap };
}

/**
 * Calculate vertical offset and height for an edge within its source/target node
 * Edges should split proportionally across the node height
 */
function calculateEdgeOffsets(
  node: LayoutNode,
  allEdgesForNode: SankeyGraph['edges'],
  currentEdge: SankeyGraph['edges'][0],
  direction: 'source' | 'target'
): { yOffset: number; height: number } {
  // Sort edges by target/source cluster_id for consistent ordering
  const sortedEdges = [...allEdgesForNode].sort((a, b) => {
    const aKey = direction === 'source' ? a.to_cluster_id : a.from_cluster_id;
    const bKey = direction === 'source' ? b.to_cluster_id : b.from_cluster_id;
    return aKey.localeCompare(bKey);
  });

  // Find position of current edge in sorted list
  const edgeIndex = sortedEdges.findIndex(e =>
    direction === 'source'
      ? e.from_cluster_id === currentEdge.from_cluster_id && e.to_cluster_id === currentEdge.to_cluster_id
      : e.from_cluster_id === currentEdge.from_cluster_id && e.to_cluster_id === currentEdge.to_cluster_id
  );

  // Calculate cumulative participant count before this edge
  let participantsBefore = 0;
  for (let i = 0; i < edgeIndex; i++) {
    participantsBefore += sortedEdges[i].user_count;
  }

  // Calculate total participants through this node
  const totalParticipants = node.user_count;

  // Calculate proportion
  const startProportion = totalParticipants > 0 ? participantsBefore / totalParticipants : 0;
  const edgeProportion = totalParticipants > 0 ? currentEdge.user_count / totalParticipants : 1;

  // Calculate actual pixel offsets
  const yOffset = node.height * startProportion;
  const height = node.height * edgeProportion;

  return { yOffset, height };
}

export default SankeyDiagram;

import React from 'react';
import type { SankeyEdge as SankeyEdgeType } from '../../services/sankeyApi';
import './SankeyEdge.css';

interface LayoutNode {
  x: number;
  y: number;
  width: number;
  height: number;
  cluster_id: string;
  user_count: number;
}

interface SankeyEdgeProps {
  edge: SankeyEdgeType;
  fromNode: LayoutNode;
  toNode: LayoutNode;
  sourceYOffset?: number;
  sourceHeight?: number;
  targetYOffset?: number;
  targetHeight?: number;
  sourceColor?: string;  // Source cluster color for gradient
  targetColor?: string;  // Target cluster color for gradient
  color?: string;  // Fallback single color (deprecated)
  opacity?: number;
}

/**
 * SankeyEdge Component
 *
 * Renders a flow path between two nodes (clusters) in adjacent rounds.
 *
 * Features:
 * - Bezier curve connecting source node to destination node
 * - Width proportional to user_count (number of participants who moved)
 * - Smooth cubic bezier path for visual clarity
 * - Optional color and opacity for styling
 * - Tooltip showing movement details on hover
 *
 * Aligned with Spec 005 T040 requirements
 */
export const SankeyEdge: React.FC<SankeyEdgeProps> = ({
  edge,
  fromNode,
  toNode,
  sourceYOffset = 0,
  sourceHeight,
  targetYOffset = 0,
  targetHeight,
  sourceColor = '#94a3b8',
  targetColor = '#94a3b8',
  color,  // Legacy prop, fallback to sourceColor/targetColor
  opacity = 0.7,  // Higher opacity for better visibility
}) => {
  const [isHovered, setIsHovered] = React.useState(false);

  // Use color prop as fallback if gradient colors not provided
  const effectiveSourceColor = color || sourceColor;
  const effectiveTargetColor = color || targetColor;

  // Generate unique gradient ID for this edge
  const gradientId = `gradient-${edge.from_cluster_id}-${edge.to_cluster_id}`;

  // Calculate source coordinates
  // Source: right edge of from node, at the vertical position corresponding to this edge's slice
  const sourceX = fromNode.x + fromNode.width;
  const sourceY1 = fromNode.y + sourceYOffset;
  const sourceY2 = fromNode.y + sourceYOffset + (sourceHeight || fromNode.height);
  const sourceYCenter = (sourceY1 + sourceY2) / 2;

  // Target: left edge of to node, at the vertical position corresponding to this edge's slice
  const targetX = toNode.x;
  const targetY1 = toNode.y + targetYOffset;
  const targetY2 = toNode.y + targetYOffset + (targetHeight || toNode.height);
  const targetYCenter = (targetY1 + targetY2) / 2;

  // Calculate control points for Bezier curves
  // Use midpoint for smooth horizontal transition
  const midX = (sourceX + targetX) / 2;

  // Generate SVG path as a filled shape (ribbon) from source slice to target slice
  // This creates the proper Sankey flow appearance where edge width is proportional
  const pathData = `
    M ${sourceX},${sourceY1}
    C ${midX},${sourceY1} ${midX},${targetY1} ${targetX},${targetY1}
    L ${targetX},${targetY2}
    C ${midX},${targetY2} ${midX},${sourceY2} ${sourceX},${sourceY2}
    Z
  `;

  // Format percentage for tooltip
  const pctOfFromDisplay = edge.pct_of_from
    ? `${(edge.pct_of_from * 100).toFixed(1)}%`
    : 'N/A';
  const pctOfToDisplay = edge.pct_of_to
    ? `${(edge.pct_of_to * 100).toFixed(1)}%`
    : 'N/A';

  return (
    <g
      className="sankey-edge"
      onMouseEnter={() => setIsHovered(true)}
      onMouseLeave={() => setIsHovered(false)}
    >
      {/* Define gradient */}
      <defs>
        <linearGradient id={gradientId} x1="0%" y1="0%" x2="100%" y2="0%">
          <stop offset="0%" stopColor={effectiveSourceColor} stopOpacity={opacity} />
          <stop offset="100%" stopColor={effectiveTargetColor} stopOpacity={opacity * 0.7} />
        </linearGradient>
      </defs>

      {/* Main edge path - now a filled ribbon with gradient */}
      <path
        d={pathData}
        fill={isHovered ? '#3b82f6' : `url(#${gradientId})`}
        fillOpacity={isHovered ? 0.7 : 1}
        stroke="none"
        className="sankey-edge-path"
        style={{
          transition: 'all 0.2s ease-in-out',
          cursor: 'pointer',
        }}
      />

      {/* Tooltip on hover */}
      {isHovered && (
        <foreignObject
          x={midX - 100}
          y={(sourceYCenter + targetYCenter) / 2 - 40}
          width={200}
          height={80}
          className="sankey-edge-tooltip-container"
          style={{ pointerEvents: 'none' }}
        >
          <div className="sankey-edge-tooltip">
            <div className="tooltip-header">
              <strong>Participant Movement</strong>
            </div>
            <div className="tooltip-body">
              <div className="tooltip-stat">
                <span className="stat-label">Count:</span>
                <span className="stat-value">{edge.user_count} participant{edge.user_count !== 1 ? 's' : ''}</span>
              </div>
              <div className="tooltip-stat">
                <span className="stat-label">From cluster:</span>
                <span className="stat-value">{pctOfFromDisplay} of source</span>
              </div>
              <div className="tooltip-stat">
                <span className="stat-label">To cluster:</span>
                <span className="stat-value">{pctOfToDisplay} of destination</span>
              </div>
            </div>
          </div>
        </foreignObject>
      )}
    </g>
  );
};

export default SankeyEdge;

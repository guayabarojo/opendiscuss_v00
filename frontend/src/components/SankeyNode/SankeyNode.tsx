import React, { useState } from 'react';
import type { SankeyNode as SankeyNodeType } from '../../services/sankeyApi';
import './SankeyNode.css';

interface SankeyNodeProps {
  node: SankeyNodeType;
  x: number;
  y: number;
  width: number;
  height: number;
  color: string;
  onHover?: (node: SankeyNodeType | null) => void;
}

/**
 * Extract first few words from cluster label for quick scanning
 * Truncates to maxWords for visual simplicity
 */
function getShortLabel(text: string, maxWords: number = 4): string {
  if (!text) return '';

  const words = text.trim().split(/\s+/);

  if (words.length <= maxWords) {
    return text;
  }

  return words.slice(0, maxWords).join(' ') + '...';
}

/**
 * SankeyNode Component
 *
 * Renders a single node (thought space/cluster) in the Sankey diagram.
 *
 * Features:
 * - Rectangle with height proportional to user_pct
 * - Color from display_group_id (consistent hash) or default color
 * - Label text from label_summary (truncated if needed)
 * - Tooltip showing full label + user_count
 * - Hover effects with callback to parent
 *
 * Aligned with Spec 005 T030 requirements
 */
export const SankeyNode: React.FC<SankeyNodeProps> = ({
  node,
  x,
  y,
  width,
  height,
  color,
  onHover,
}) => {
  const [showTooltip, setShowTooltip] = useState(false);

  const handleMouseEnter = () => {
    setShowTooltip(true);
    if (onHover) {
      onHover(node);
    }
  };

  const handleMouseLeave = () => {
    setShowTooltip(false);
    if (onHover) {
      onHover(null);
    }
  };

  // Shorten label to first 4 words for quick scanning
  const displayLabel = getShortLabel(node.label_summary, 4);

  // Format percentage for display
  const percentageDisplay = `${(node.user_pct * 100).toFixed(1)}%`;

  return (
    <g
      className="sankey-node"
      onMouseEnter={handleMouseEnter}
      onMouseLeave={handleMouseLeave}
      style={{ cursor: 'pointer' }}
    >
      {/* Node rectangle */}
      <rect
        x={x}
        y={y}
        width={width}
        height={height}
        fill={color}
        stroke="#ffffff"
        strokeWidth={3}
        rx={6}
        ry={6}
        className="sankey-node-rect"
        opacity={showTooltip ? 1 : 0.9}
        style={{ transition: 'opacity 0.2s ease' }}
      />

      {/* Node label - ALWAYS visible, positioned INSIDE the node */}
      {height > 15 && (
        <text
          x={x + width / 2}
          y={y + height / 2}
          dy="0.35em"
          textAnchor="middle"
          fontSize="11px"
          fontWeight="600"
          fill="#ffffff"
          className="sankey-node-label-inside"
          style={{
            pointerEvents: 'none',
            textShadow: '0 1px 2px rgba(0,0,0,0.5)'
          }}
        >
          {displayLabel}
        </text>
      )}

      {/* Participant count - inside node, below label */}
      {height > 30 && (
        <text
          x={x + width / 2}
          y={y + height / 2 + 14}
          dy="0.35em"
          textAnchor="middle"
          fontSize="10px"
          fontWeight="700"
          fill="#ffffff"
          className="sankey-node-count-inside"
          style={{
            pointerEvents: 'none',
            textShadow: '0 1px 2px rgba(0,0,0,0.5)',
            opacity: 0.9
          }}
        >
          {node.user_count}
        </text>
      )}

      {/* Tooltip */}
      {showTooltip && (
        <foreignObject
          x={x + width + 15}
          y={y}
          width={250}
          height={100}
          className="sankey-node-tooltip-container"
          style={{ pointerEvents: 'none' }}
        >
          <div className="sankey-node-tooltip">
            <div className="tooltip-label">{node.label_summary}</div>
            <div className="tooltip-stats">
              <span className="tooltip-count">
                {node.user_count} participant{node.user_count !== 1 ? 's' : ''}
              </span>
              <span className="tooltip-percentage"> ({percentageDisplay})</span>
            </div>
            {node.display_group_id && (
              <div className="tooltip-group">
                Group: {node.display_group_id.substring(0, 8)}...
              </div>
            )}
          </div>
        </foreignObject>
      )}
    </g>
  );
};

export default SankeyNode;

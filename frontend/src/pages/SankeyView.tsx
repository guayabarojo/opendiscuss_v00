import React, { useEffect, useState } from 'react';
import { useParams } from 'react-router-dom';
import { SankeyDiagram } from '../components/SankeyDiagram/SankeyDiagram';
import { fetchSankeyGraph, constructSankeyGraph, type SankeyGraph, type SankeyNode } from '../services/sankeyApi';
import { ClusteringInspectorModal } from '../components/ClusteringInspectorModal';
import { ParticipantDataTable } from '../components/ParticipantDataTable';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { cn } from '@/lib/utils';
import './SankeyView.css';

/**
 * SankeyView Page Component
 *
 * Page component for viewing Sankey diagrams for completed discussions.
 *
 * Features:
 * - Extracts discussion_id from URL params
 * - Fetches SankeyGraph on mount (tries fetch first, then construct if not found)
 * - Loading, error, and success states
 * - Renders SankeyDiagram component
 * - Shows metadata (construction time, round count, participant counts)
 * - Node hover state management
 *
 * Route: /discussions/:discussionId/sankey
 *
 * Aligned with Spec 005 T031 requirements
 */
export const SankeyView: React.FC = () => {
  const { discussionId } = useParams<{ discussionId: string }>();
  const [sankeyGraph, setSankeyGraph] = useState<SankeyGraph | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);
  const [hoveredNode, setHoveredNode] = useState<SankeyNode | null>(null);
  const [constructing, setConstructing] = useState<boolean>(false);
  const [minClusterSize, setMinClusterSize] = useState<number>(5);  // Default to medium detail
  const [inspectorOpen, setInspectorOpen] = useState(false);

  useEffect(() => {
    if (!discussionId) {
      setError('No discussion ID provided');
      setLoading(false);
      return;
    }

    loadSankeyGraph(discussionId);
  }, [discussionId]);

  const loadSankeyGraph = async (id: string) => {
    setLoading(true);
    setError(null);

    try {
      // First, try to fetch existing Sankey diagram
      const graph = await fetchSankeyGraph(id);
      setSankeyGraph(graph);
      setLoading(false);
    } catch (fetchError: any) {
      // If not found, try to construct it
      if (fetchError.message.includes('not found')) {
        try {
          setConstructing(true);
          const graph = await constructSankeyGraph(id);
          setSankeyGraph(graph);
          setLoading(false);
          setConstructing(false);
        } catch (constructError: any) {
          setError(
            constructError.message ||
            'Failed to construct Sankey diagram. The discussion may not have cluster data available yet.'
          );
          setLoading(false);
          setConstructing(false);
        }
      } else {
        setError(fetchError.message || 'Failed to load Sankey diagram');
        setLoading(false);
      }
    }
  };

  const handleRetry = () => {
    if (discussionId) {
      loadSankeyGraph(discussionId);
    }
  };

  if (loading) {
    return (
      <div className="sankey-view-container">
        <div className="sankey-view-loading">
          <div className="loading-spinner"></div>
          <p>
            {constructing
              ? 'Constructing Sankey diagram...'
              : 'Loading Sankey diagram...'}
          </p>
          {constructing && (
            <p className="loading-subtext">
              This may take a few seconds for large discussions
            </p>
          )}
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="sankey-view-container">
        <Card className="max-w-2xl mx-auto mt-8">
          <CardHeader>
            <div className="flex items-center gap-3">
              <div className="text-4xl">⚠️</div>
              <div>
                <CardTitle className="text-destructive">Failed to Load Sankey Diagram</CardTitle>
                <CardDescription className="mt-2">{error}</CardDescription>
              </div>
            </div>
          </CardHeader>
          <CardContent className="flex gap-3">
            <Button onClick={handleRetry}>
              Retry
            </Button>
            <Button variant="outline" asChild>
              <a href={`/discussions/${discussionId}/report`}>
                View Discussion Report
              </a>
            </Button>
          </CardContent>
        </Card>
      </div>
    );
  }

  if (!sankeyGraph) {
    return (
      <div className="sankey-view-container">
        <div className="sankey-view-empty">
          <p>No Sankey data available for this discussion</p>
        </div>
      </div>
    );
  }

  // Calculate metadata
  const totalRounds = sankeyGraph.columns.length;
  const totalParticipantsInitial = sankeyGraph.columns[0]?.total_participants || 0;
  const totalParticipantsFinal =
    sankeyGraph.columns[sankeyGraph.columns.length - 1]?.total_participants || 0;
  const dropoutRate =
    totalParticipantsInitial > 0
      ? ((totalParticipantsInitial - totalParticipantsFinal) / totalParticipantsInitial) * 100
      : 0;

  const createdDate = new Date(sankeyGraph.created_at);
  const constructionTime = sankeyGraph.metadata?.construction_time_ms
    ? `${sankeyGraph.metadata.construction_time_ms}ms`
    : 'Unknown';

  return (
    <div className="sankey-view-container">
      {/* Header */}
      <Card className="mb-6">
        <CardHeader>
          <div className="flex items-center justify-between">
            <div className="space-y-1">
              <CardTitle className="text-2xl">Discussion Flow Visualization</CardTitle>
              <CardDescription className="flex items-center gap-2">
                Participant movement across <Badge variant="secondary">{totalRounds} round{totalRounds !== 1 ? 's' : ''}</Badge>
              </CardDescription>
            </div>
            {import.meta.env.DEV && (
              <Button variant="outline" onClick={() => setInspectorOpen(true)}>
                🔍 Inspect Clustering
              </Button>
            )}
          </div>
        </CardHeader>
      </Card>

      {/* Metadata Panel */}
      <Card className="mb-6">
        <CardHeader>
          <CardTitle className="text-lg">Discussion Metadata</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            <div className="space-y-1">
              <p className="text-sm text-muted-foreground">Discussion ID</p>
              <p className="font-mono text-sm truncate">{sankeyGraph.discussion_id}</p>
            </div>
            <div className="space-y-1">
              <p className="text-sm text-muted-foreground">Total Rounds</p>
              <Badge variant="default">{totalRounds}</Badge>
            </div>
            <div className="space-y-1">
              <p className="text-sm text-muted-foreground">Initial Participants</p>
              <Badge variant="secondary">{totalParticipantsInitial}</Badge>
            </div>
            <div className="space-y-1">
              <p className="text-sm text-muted-foreground">Final Participants</p>
              <Badge variant="secondary">{totalParticipantsFinal}</Badge>
            </div>
            <div className="space-y-1">
              <p className="text-sm text-muted-foreground">Dropout Rate</p>
              <Badge variant={dropoutRate > 10 ? "destructive" : "outline"}>
                {dropoutRate.toFixed(1)}%
              </Badge>
            </div>
            <div className="space-y-1">
              <p className="text-sm text-muted-foreground">Created</p>
              <p className="text-sm">{createdDate.toLocaleString()}</p>
            </div>
            <div className="space-y-1">
              <p className="text-sm text-muted-foreground">Construction Time</p>
              <Badge variant="outline">{constructionTime}</Badge>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Cluster Granularity Control */}
      <Card className="mb-6">
        <CardHeader>
          <CardTitle className="text-lg">Cluster Detail Level</CardTitle>
          <CardDescription>
            {minClusterSize <= 2
              ? 'All clusters shown individually'
              : `Clusters with ${minClusterSize}+ participants shown separately, smaller ones grouped as "Other"`
            }
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <input
            id="cluster-slider"
            type="range"
            min="2"
            max={sankeyGraph.metadata?.cluster_granularity_suggestions?.low_detail || 15}
            value={minClusterSize}
            onChange={(e) => setMinClusterSize(parseInt(e.target.value))}
            className="w-full h-2 bg-gray-200 rounded-lg appearance-none cursor-pointer dark:bg-gray-700"
          />
          <div className="flex justify-between text-xs text-muted-foreground">
            <span className="text-center">Maximum Detail<br/>(All clusters)</span>
            <span className="text-center">Balanced<br/>(Group smallest)</span>
            <span className="text-center">High Level<br/>(Group smaller clusters)</span>
          </div>
          <p className="text-sm text-muted-foreground">
            ℹ️ All {sankeyGraph.columns[0]?.total_participants || 0} participants are always represented at every detail level
          </p>
        </CardContent>
      </Card>

      {/* Hovered Node Info */}
      {hoveredNode && (
        <Card className="mb-6 border-primary">
          <CardHeader>
            <CardTitle className="text-lg">Selected Cluster</CardTitle>
            <CardDescription>{hoveredNode.label_summary}</CardDescription>
          </CardHeader>
          <CardContent>
            <div className="flex items-center gap-2">
              <Badge variant="default">
                {hoveredNode.user_count} participant{hoveredNode.user_count !== 1 ? 's' : ''}
              </Badge>
              <Badge variant="secondary">
                {(hoveredNode.user_pct * 100).toFixed(1)}%
              </Badge>
            </div>
          </CardContent>
        </Card>
      )}

      {/* Sankey Diagram */}
      <div className="sankey-diagram-wrapper">
        <SankeyDiagram
          sankeyGraph={sankeyGraph}
          onNodeHover={setHoveredNode}
          minClusterSize={minClusterSize}
        />
      </div>

      {/* Legend */}
      <Card className="mt-6">
        <CardHeader>
          <CardTitle className="text-lg">How to Read This Diagram</CardTitle>
        </CardHeader>
        <CardContent>
          <ul className="space-y-2 text-sm">
            <li>
              <strong>Columns:</strong> Each vertical column represents one discussion round
            </li>
            <li>
              <strong>Nodes (Rectangles):</strong> Each rectangle represents a cluster of similar participant responses (thought space)
            </li>
            <li>
              <strong>Node Height:</strong> The height of each node is proportional to the percentage of participants in that cluster
            </li>
            <li>
              <strong>Edges (Flows):</strong> Curved lines between nodes show participant movement between clusters across rounds
            </li>
            <li>
              <strong>Edge Width:</strong> The width of each flow is proportional to the number of participants who made that transition
            </li>
            <li>
              <strong>Colors:</strong> Node colors indicate alignment groups across rounds (same topic/theme maintained across rounds)
            </li>
            <li>
              <strong>Hover:</strong> Hover over any node or edge to see detailed information and participant counts
            </li>
          </ul>
          <p className="mt-4 text-sm text-muted-foreground">
            💡 Tip: The diagram naturally narrows if participants drop out between rounds, providing an honest view of engagement over time.
          </p>
        </CardContent>
      </Card>

      {/* Clustering Inspector Modal */}
      {inspectorOpen && (
        <ClusteringInspectorModal
          discussionId={discussionId!}
          onClose={() => setInspectorOpen(false)}
        />
      )}

      {/* Participant Data Table */}
      <ParticipantDataTable discussionId={discussionId!} />
    </div>
  );
};

export default SankeyView;

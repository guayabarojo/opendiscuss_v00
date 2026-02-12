/**
 * Clustering Inspector Modal
 *
 * Popup modal for inspecting clustering results without leaving Sankey view
 */

import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import {
  fetchInspectorData,
  fetchDiscussionRounds,
  exportAsCSV,
  exportAsJSON,
  type ClusterInspectorResponse
} from '../services/clusteringInspectorApi';

interface Props {
  discussionId: string;
  initialRoundId?: string;
  onClose: () => void;
}

export function ClusteringInspectorModal({ discussionId, initialRoundId, onClose }: Props) {
  const [selectedRoundId, setSelectedRoundId] = useState<string | null>(initialRoundId || null);
  const [searchText, setSearchText] = useState('');
  const [clusterFilter, setClusterFilter] = useState<string>('all');
  const [sortBy, setSortBy] = useState<'participant' | 'cluster' | 'similarity'>('participant');
  const [expandedRows, setExpandedRows] = useState<Set<number>>(new Set());

  // Fetch discussion rounds
  const { data: roundsData } = useQuery({
    queryKey: ['discussion-rounds', discussionId],
    queryFn: async () => fetchDiscussionRounds(discussionId),
    enabled: !!discussionId
  });

  const rounds = roundsData?.rounds || [];

  // Auto-select first round
  if (rounds && rounds.length > 0 && !selectedRoundId) {
    setSelectedRoundId(rounds[0].round_id);
  }

  // Fetch inspector data
  const { data: inspectorData, isLoading } = useQuery<ClusterInspectorResponse>({
    queryKey: ['clustering-inspector', selectedRoundId],
    queryFn: () => fetchInspectorData(selectedRoundId!),
    enabled: !!selectedRoundId
  });

  // Filter and sort rows
  const filteredRows = inspectorData?.rows
    .filter(row => {
      if (searchText) {
        const search = searchText.toLowerCase();
        return (
          row.summary_text.toLowerCase().includes(search) ||
          row.original_submission?.toLowerCase().includes(search) ||
          row.cluster_label?.toLowerCase().includes(search)
        );
      }
      return true;
    })
    .filter(row => {
      if (clusterFilter === 'all') return true;
      if (clusterFilter === 'singletons') return row.is_singleton;
      return row.cluster_id === clusterFilter;
    })
    .sort((a, b) => {
      if (sortBy === 'participant') return a.participant_number - b.participant_number;
      if (sortBy === 'cluster') return (a.cluster_id || '').localeCompare(b.cluster_id || '');
      if (sortBy === 'similarity') return (b.similarity_to_centroid || 0) - (a.similarity_to_centroid || 0);
      return 0;
    }) || [];

  const uniqueClusters = Array.from(
    new Set(inspectorData?.rows.map(r => r.cluster_id).filter(Boolean))
  );

  const getSimilarityColor = (similarity?: number) => {
    if (similarity === undefined) return 'text-gray-400';
    if (similarity < 0.4) return 'text-red-600 font-semibold';
    if (similarity < 0.7) return 'text-yellow-600';
    return 'text-green-600';
  };

  const toggleRowExpansion = (participantNum: number) => {
    setExpandedRows(prev => {
      const next = new Set(prev);
      if (next.has(participantNum)) {
        next.delete(participantNum);
      } else {
        next.add(participantNum);
      }
      return next;
    });
  };

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-4">
      <div className="bg-white rounded-lg shadow-2xl w-full max-w-7xl max-h-[90vh] flex flex-col">
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b">
          <div>
            <h2 className="text-2xl font-bold text-gray-900">🔍 Clustering Inspector</h2>
            <p className="text-sm text-gray-600 mt-1">Inspect clustering quality and participant assignments</p>
          </div>
          <button
            onClick={onClose}
            className="text-gray-400 hover:text-gray-600 text-2xl font-bold px-3"
          >
            ×
          </button>
        </div>

        {/* Warning */}
        <div className="bg-yellow-50 px-6 py-3 border-b">
          <p className="text-sm text-yellow-800">
            <span className="font-semibold">⚠️ Developer Tool:</span> This shows anonymous participant data for debugging purposes
          </p>
        </div>

        {/* Content */}
        <div className="flex-1 overflow-auto px-6 py-4">
          {/* Round Selector */}
          <div className="mb-4">
            <label className="block text-sm font-medium text-gray-700 mb-2">Select Round</label>
            <select
              value={selectedRoundId || ''}
              onChange={(e) => setSelectedRoundId(e.target.value)}
              className="w-full px-4 py-2 border border-gray-300 rounded-lg"
            >
              {rounds?.map((round: any) => (
                <option key={round.round_id} value={round.round_id}>
                  Round {round.round_number}: {round.question_text?.substring(0, 80)}...
                </option>
              ))}
            </select>
          </div>

          {isLoading && (
            <div className="text-center py-12">
              <div className="inline-block animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600"></div>
              <p className="mt-4 text-gray-600">Loading inspector data...</p>
            </div>
          )}

          {inspectorData && (
            <>
              {/* Metrics */}
              <div className="bg-gray-50 rounded-lg p-4 mb-4">
                <div className="grid grid-cols-3 md:grid-cols-5 gap-4 text-center">
                  <div>
                    <p className="text-xs text-gray-600">Participants</p>
                    <p className="text-xl font-bold">{inspectorData.total_participants}</p>
                  </div>
                  <div>
                    <p className="text-xs text-gray-600">Clusters</p>
                    <p className="text-xl font-bold">{inspectorData.cluster_count}</p>
                  </div>
                  {inspectorData.quality_metrics && (
                    <>
                      <div>
                        <p className="text-xs text-gray-600">Silhouette</p>
                        <p className="text-xl font-bold">
                          {inspectorData.quality_metrics.silhouette_score?.toFixed(3) || 'N/A'}
                        </p>
                      </div>
                      <div>
                        <p className="text-xs text-gray-600">Singletons</p>
                        <p className="text-xl font-bold">{inspectorData.quality_metrics.singleton_count}</p>
                      </div>
                      <div>
                        <p className="text-xs text-gray-600">Avg Size</p>
                        <p className="text-xl font-bold">{inspectorData.quality_metrics.avg_cluster_size.toFixed(1)}</p>
                      </div>
                    </>
                  )}
                </div>

                {inspectorData.near_duplicate_pairs.length > 0 && (
                  <div className="mt-3 p-3 bg-yellow-50 border border-yellow-200 rounded text-sm">
                    <p className="font-semibold text-yellow-900">
                      ⚠️ {inspectorData.near_duplicate_pairs.length} Near-Duplicate Pairs
                    </p>
                  </div>
                )}
              </div>

              {/* Filters */}
              <div className="grid grid-cols-1 md:grid-cols-4 gap-3 mb-4">
                <input
                  type="text"
                  value={searchText}
                  onChange={(e) => setSearchText(e.target.value)}
                  placeholder="Search..."
                  className="px-3 py-2 border rounded"
                />
                <select
                  value={clusterFilter}
                  onChange={(e) => setClusterFilter(e.target.value)}
                  className="px-3 py-2 border rounded"
                >
                  <option value="all">All Clusters</option>
                  <option value="singletons">Singletons Only</option>
                  {uniqueClusters.map(id => (
                    <option key={id} value={id}>{id?.substring(0, 8)}...</option>
                  ))}
                </select>
                <select
                  value={sortBy}
                  onChange={(e) => setSortBy(e.target.value as any)}
                  className="px-3 py-2 border rounded"
                >
                  <option value="participant">By Participant</option>
                  <option value="cluster">By Cluster</option>
                  <option value="similarity">By Similarity</option>
                </select>
                <div className="flex gap-2">
                  <button
                    onClick={() => exportAsCSV(inspectorData)}
                    className="flex-1 px-3 py-2 bg-green-600 text-white rounded hover:bg-green-700 text-sm"
                  >
                    CSV
                  </button>
                  <button
                    onClick={() => exportAsJSON(inspectorData)}
                    className="flex-1 px-3 py-2 bg-blue-600 text-white rounded hover:bg-blue-700 text-sm"
                  >
                    JSON
                  </button>
                </div>
              </div>

              {/* Table */}
              <div className="border rounded-lg overflow-hidden">
                <table className="min-w-full divide-y divide-gray-200">
                  <thead className="bg-gray-50">
                    <tr>
                      <th className="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase">
                        Participant
                      </th>
                      <th className="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase">
                        Summary
                      </th>
                      <th className="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase">
                        Similarity
                      </th>
                      <th className="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase">
                        Type
                      </th>
                    </tr>
                  </thead>
                  <tbody className="bg-white divide-y divide-gray-200">
                    {filteredRows.map((row) => {
                      const isExpanded = expandedRows.has(row.participant_number);
                      return (
                        <tr key={row.participant_number} className="hover:bg-gray-50">
                          <td className="px-4 py-2 text-sm font-semibold">
                            P{row.participant_number}
                          </td>
                          <td className="px-4 py-2 text-sm">
                            <button
                              onClick={() => toggleRowExpansion(row.participant_number)}
                              className="text-left hover:text-blue-600 w-full"
                            >
                              {isExpanded ? row.summary_text : `${row.summary_text.substring(0, 60)}...`}
                            </button>
                          </td>
                          <td className="px-4 py-2 text-sm">
                            <span className={getSimilarityColor(row.similarity_to_centroid)}>
                              {row.similarity_to_centroid?.toFixed(3) || 'N/A'}
                            </span>
                          </td>
                          <td className="px-4 py-2 text-sm">
                            {row.is_singleton ? (
                              <span className="px-2 py-1 bg-yellow-100 text-yellow-800 rounded text-xs">
                                Singleton
                              </span>
                            ) : (
                              <span className="px-2 py-1 bg-blue-100 text-blue-800 rounded text-xs">
                                Cluster
                              </span>
                            )}
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
                <div className="px-4 py-3 bg-gray-50 text-sm text-gray-600">
                  Showing {filteredRows.length} of {inspectorData.rows.length} participants
                </div>
              </div>
            </>
          )}
        </div>
      </div>
    </div>
  );
}

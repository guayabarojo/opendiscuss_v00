/**
 * Clustering Inspector API Service
 *
 * Developer tool for inspecting clustering results and validating quality.
 */

import axios from 'axios';

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000/api/v1';

export interface InspectorRow {
  participant_number: number;
  original_submission?: string;
  summary_text: string;
  cluster_id?: string;
  cluster_label?: string;
  similarity_to_centroid?: number;
  is_singleton: boolean;
}

export interface ClusterQualityMetrics {
  silhouette_score?: number;
  davies_bouldin_index?: number;
  near_duplicate_count: number;
  singleton_count: number;
  avg_cluster_size: number;
}

export interface NearDuplicatePair {
  cluster_id_1: string;
  cluster_id_2: string;
  similarity: number;
  label_1: string;
  label_2: string;
}

export interface ClusterInspectorResponse {
  round_id: string;
  round_number: number;
  question_text: string;
  total_participants: number;
  cluster_count: number;
  rows: InspectorRow[];
  quality_metrics?: ClusterQualityMetrics;
  near_duplicate_pairs: NearDuplicatePair[];
}

/**
 * Fetch all rounds for a discussion (for round selector)
 */
export async function fetchDiscussionRounds(
  discussionId: string
): Promise<{ rounds: { round_id: string; round_number: number; question_text: string }[] }> {
  const response = await axios.get(
    `${API_BASE_URL}/clusters/inspector/discussions/${discussionId}/rounds`
  );
  return response.data;
}

/**
 * Fetch clustering inspector data for a round
 */
export async function fetchInspectorData(
  roundId: string
): Promise<ClusterInspectorResponse> {
  const response = await axios.get<ClusterInspectorResponse>(
    `${API_BASE_URL}/clusters/inspector/rounds/${roundId}`
  );
  return response.data;
}

/**
 * Export inspector data as CSV
 */
export function exportAsCSV(data: ClusterInspectorResponse): void {
  const headers = [
    'Participant',
    'Original Submission',
    'Summary Text',
    'Cluster ID',
    'Cluster Label',
    'Similarity to Centroid',
    'Is Singleton'
  ];

  const rows = data.rows.map(row => [
    `Participant ${row.participant_number}`,
    row.original_submission || 'N/A',
    `"${row.summary_text.replace(/"/g, '""')}"`,
    row.cluster_id || 'N/A',
    row.cluster_label ? `"${row.cluster_label.replace(/"/g, '""')}"` : 'N/A',
    row.similarity_to_centroid?.toFixed(3) || 'N/A',
    row.is_singleton ? 'Yes' : 'No'
  ]);

  const csv = [
    headers.join(','),
    ...rows.map(row => row.join(','))
  ].join('\n');

  const blob = new Blob([csv], { type: 'text/csv' });
  const url = window.URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = `clustering-inspector-round-${data.round_number}.csv`;
  a.click();
  window.URL.revokeObjectURL(url);
}

/**
 * Export inspector data as JSON
 */
export function exportAsJSON(data: ClusterInspectorResponse): void {
  const json = JSON.stringify(data, null, 2);
  const blob = new Blob([json], { type: 'application/json' });
  const url = window.URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = `clustering-inspector-round-${data.round_number}.json`;
  a.click();
  window.URL.revokeObjectURL(url);
}

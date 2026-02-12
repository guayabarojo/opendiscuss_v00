import axios from 'axios';

/**
 * Sankey API Client
 *
 * Provides typed methods for interacting with Spec 005 Sankey diagram endpoints.
 * Aligned with backend models from src/models/sankey_*.py
 */

// Type definitions matching backend Pydantic models

export interface SankeyNode {
  node_id: string;
  cluster_id: string;
  label_summary: string;
  user_count: number;
  user_pct: number;
  display_group_id?: string | null;
}

export interface SankeyColumn {
  round_index: number;
  nodes: SankeyNode[];
  total_participants: number;
}

export interface SankeyEdge {
  from_round_index: number;
  to_round_index: number;
  from_cluster_id: string;
  to_cluster_id: string;
  user_count: number;
  pct_of_from?: number | null;
  pct_of_to?: number | null;
}

export interface SankeyGraph {
  discussion_id: string;
  rounds: string[];
  round_questions?: Record<string, string>;  // round_id -> question_text
  columns: SankeyColumn[];
  edges: SankeyEdge[];
  created_at: string;
  metadata?: {
    construction_time_ms?: number;
    cluster_size_distribution?: {
      min: number;
      max: number;
      median: number;
      total_clusters: number;
    };
    cluster_granularity_suggestions?: {
      high_detail: number;
      medium_detail: number;
      low_detail: number;
    };
    [key: string]: any;
  } | null;
}

export interface SankeyConstructResponse {
  sankey_graph: SankeyGraph;
  construction_time_ms: number;
  message: string;
}

export interface SankeyRetrievalResponse {
  sankey_graph: SankeyGraph;
  cached: boolean;
  round_questions?: Record<string, string>;  // round_id -> question_text
}

/**
 * Fetch an existing Sankey diagram for a discussion
 *
 * GET /api/v1/sankey/{discussion_id}
 *
 * @param discussionId - Discussion UUID
 * @returns SankeyGraph object
 * @throws Error if diagram not found or request fails
 */
export async function fetchSankeyGraph(discussionId: string): Promise<SankeyGraph> {
  try {
    const baseURL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000/api/v1';
    const response = await axios.get<SankeyRetrievalResponse>(
      `${baseURL}/sankey/${discussionId}`
    );

    // Merge round_questions into sankey_graph
    const sankeyGraph = response.data.sankey_graph;
    if (response.data.round_questions) {
      sankeyGraph.round_questions = response.data.round_questions;
    }

    return sankeyGraph;
  } catch (error) {
    if (axios.isAxiosError(error)) {
      if (error.response?.status === 404) {
        throw new Error(`Sankey diagram not found for discussion ${discussionId}`);
      }
      throw new Error(
        error.response?.data?.detail ||
        'Failed to fetch Sankey diagram'
      );
    }
    throw error;
  }
}

/**
 * Construct a new Sankey diagram for a discussion
 *
 * POST /api/v1/sankey/construct
 *
 * Idempotent: Returns existing diagram if already constructed
 *
 * @param discussionId - Discussion UUID
 * @param includeAlignment - Whether to include alignment metadata (default: true)
 * @returns SankeyGraph object with construction metadata
 * @throws Error if construction fails
 */
export async function constructSankeyGraph(
  discussionId: string,
  includeAlignment: boolean = true
): Promise<SankeyGraph> {
  try {
    const baseURL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000/api/v1';
    const response = await axios.post<SankeyConstructResponse>(
      `${baseURL}/sankey/construct`,
      {
        discussion_id: discussionId,
        include_alignment: includeAlignment
      }
    );
    return response.data.sankey_graph;
  } catch (error) {
    if (axios.isAxiosError(error)) {
      if (error.response?.status === 400) {
        throw new Error(
          error.response?.data?.detail ||
          'Invalid discussion or no cluster data available'
        );
      }
      if (error.response?.status === 500) {
        throw new Error(
          error.response?.data?.detail ||
          'Sankey construction failed on server'
        );
      }
      throw new Error(
        error.response?.data?.detail ||
        'Failed to construct Sankey diagram'
      );
    }
    throw error;
  }
}

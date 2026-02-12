/**
 * API client for participant data endpoints
 *
 * Provides typed API calls for fetching participant submission data
 * including raw inputs, summaries, and cluster assignments.
 */

import axios from 'axios';

const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000/api/v1';

export interface ParticipantDataRow {
  round_num: number;
  round_id: string;
  participant_id: string;
  submission_id: string | null;
  raw_input: string | null;
  summary: string;
  cluster_id: string;
  cluster_label: string;
  cluster_size: number;
}

export interface ParticipantDataResponse {
  data: ParticipantDataRow[];
  total: number;
  discussion_id: string;
  rounds: number;
}

export interface ParticipantDataFilters {
  round_num?: number;
  search?: string;
  limit?: number;
  offset?: number;
}

/**
 * Fetch participant data for a discussion
 *
 * @param discussionId - Discussion UUID
 * @param filters - Optional filters (round_num, search, pagination)
 * @returns Promise resolving to participant data response
 */
export async function fetchParticipantData(
  discussionId: string,
  filters?: ParticipantDataFilters
): Promise<ParticipantDataResponse> {
  try {
    const params = new URLSearchParams();

    if (filters?.round_num !== undefined) {
      params.append('round_num', filters.round_num.toString());
    }

    if (filters?.search && filters.search.trim() !== '') {
      params.append('search', filters.search.trim());
    }

    if (filters?.limit !== undefined) {
      params.append('limit', filters.limit.toString());
    }

    if (filters?.offset !== undefined) {
      params.append('offset', filters.offset.toString());
    }

    const queryString = params.toString();
    const url = `${API_BASE_URL}/participant-data/${discussionId}${queryString ? `?${queryString}` : ''}`;

    const response = await axios.get<ParticipantDataResponse>(url);

    return response.data;
  } catch (error: any) {
    console.error('Failed to fetch participant data:', error);

    if (error.response?.status === 404) {
      throw new Error('Discussion not found');
    }

    throw new Error(
      error.response?.data?.detail ||
      error.message ||
      'Failed to fetch participant data'
    );
  }
}

import axios, { AxiosInstance, AxiosError } from 'axios';
import type {
  CreateDiscussionRequest,
  Discussion,
  DiscussionReport,
  RoundStatusResponse,
  SubmitRequest,
  SubmissionResponse,
  SubmissionHistoryResponse,
  ApiError,
} from '../types/api';

/**
 * Discussion API Client
 *
 * Provides typed methods for interacting with the OpenDiscuss Discussion Protocol API.
 * All methods include proper error handling with try/catch and typed responses.
 */
class DiscussionApiClient {
  private client: AxiosInstance;

  constructor() {
    // Base URL from environment variable with fallback
    const baseURL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000/api/v1';

    this.client = axios.create({
      baseURL,
      headers: {
        'Content-Type': 'application/json',
      },
      timeout: 30000, // 30 second timeout
    });

    // Request interceptor for authentication
    this.client.interceptors.request.use(
      (config) => {
        // Add auth token if available
        const token = localStorage.getItem('auth_token');
        if (token) {
          config.headers.Authorization = `Bearer ${token}`;
        }
        return config;
      },
      (error) => {
        return Promise.reject(error);
      }
    );

    // Response interceptor for error handling
    this.client.interceptors.response.use(
      (response) => response,
      (error: AxiosError<ApiError>) => {
        // Enhanced error handling
        if (error.response) {
          // Server responded with error status
          const apiError: ApiError = error.response.data || {
            error: 'Unknown Error',
            message: 'An unexpected error occurred',
          };
          console.error('API Error:', apiError);
          throw apiError;
        } else if (error.request) {
          // Request made but no response received
          const networkError: ApiError = {
            error: 'Network Error',
            message: 'Unable to reach the server. Please check your connection.',
          };
          console.error('Network Error:', error.request);
          throw networkError;
        } else {
          // Something else happened
          const generalError: ApiError = {
            error: 'Request Error',
            message: error.message || 'An error occurred setting up the request',
          };
          console.error('Request Error:', error.message);
          throw generalError;
        }
      }
    );
  }

  /**
   * Create a new discussion
   * @param data Discussion creation parameters
   * @returns Created discussion object
   * @throws ApiError on failure
   */
  async createDiscussion(data: CreateDiscussionRequest): Promise<Discussion> {
    try {
      const response = await this.client.post<Discussion>('/discussions', data);
      return response.data;
    } catch (error) {
      console.error('Failed to create discussion:', error);
      throw error;
    }
  }

  /**
   * Get discussion details by ID
   * @param discussionId UUID of the discussion
   * @returns Discussion details
   * @throws ApiError on failure
   */
  async getDiscussion(discussionId: string): Promise<Discussion> {
    try {
      const response = await this.client.get<Discussion>(
        `/discussions/${discussionId}`
      );
      return response.data;
    } catch (error) {
      console.error(`Failed to get discussion ${discussionId}:`, error);
      throw error;
    }
  }

  /**
   * Start a discussion (opens Round 1 submission window)
   * @param discussionId UUID of the discussion
   * @returns Updated discussion with ACTIVE status
   * @throws ApiError on failure
   */
  async startDiscussion(discussionId: string): Promise<Discussion> {
    try {
      const response = await this.client.post<Discussion>(
        `/discussions/${discussionId}/start`
      );
      return response.data;
    } catch (error) {
      console.error(`Failed to start discussion ${discussionId}:`, error);
      throw error;
    }
  }

  /**
   * Get real-time round status with timing information
   * @param roundId UUID of the round
   * @returns Round status including remaining time and participant stats
   * @throws ApiError on failure
   */
  async getRoundStatus(roundId: string): Promise<RoundStatusResponse> {
    try {
      const response = await this.client.get<RoundStatusResponse>(
        `/rounds/${roundId}/status`
      );
      return response.data;
    } catch (error) {
      console.error(`Failed to get round status ${roundId}:`, error);
      throw error;
    }
  }

  /**
   * Get final discussion report with Sankey diagram
   * @param discussionId UUID of the discussion
   * @returns Discussion report with visualization data
   * @throws ApiError on failure (400 if discussion not completed)
   */
  async getReport(discussionId: string): Promise<DiscussionReport> {
    try {
      const response = await this.client.get<DiscussionReport>(
        `/discussions/${discussionId}/report`
      );
      return response.data;
    } catch (error) {
      console.error(`Failed to get report for discussion ${discussionId}:`, error);
      throw error;
    }
  }

  /**
   * Advance to the next round (host action)
   * @param discussionId UUID of the discussion
   * @returns Next round details
   * @throws ApiError on failure
   */
  async advanceRound(discussionId: string): Promise<Discussion> {
    try {
      const response = await this.client.post<Discussion>(
        `/discussions/${discussionId}/advance`
      );
      return response.data;
    } catch (error) {
      console.error(`Failed to advance discussion ${discussionId}:`, error);
      throw error;
    }
  }

  /**
   * Submit a participant response (T073)
   * @param data Submission request data
   * @returns Submission response with remaining count
   * @throws ApiError on failure (429 if rate limit exceeded)
   */
  async submitResponse(data: SubmitRequest): Promise<SubmissionResponse> {
    try {
      const response = await this.client.post<SubmissionResponse>('/submissions', data);
      return response.data;
    } catch (error) {
      console.error('Failed to submit response:', error);
      throw error;
    }
  }

  /**
   * Get submission history for a participant in a round (T072)
   * @param participantId UUID of the participant
   * @param roundId UUID of the round
   * @returns Submission history with status and remaining count
   * @throws ApiError on failure
   */
  async getSubmissionHistory(
    participantId: string,
    roundId: string
  ): Promise<SubmissionHistoryResponse> {
    try {
      const response = await this.client.get<SubmissionHistoryResponse>(
        `/submissions/history?participant_id=${participantId}&round_id=${roundId}`
      );
      return response.data;
    } catch (error) {
      console.error(
        `Failed to get submission history for participant ${participantId}, round ${roundId}:`,
        error
      );
      throw error;
    }
  }

  /**
   * Manually close async round submission window (host action)
   * @param roundId UUID of the round
   * @returns Updated round with SUBMISSION_CLOSED status
   * @throws ApiError on failure (403 if not host, 400 if invalid mode)
   */
  async closeRound(roundId: string): Promise<any> {
    try {
      const response = await this.client.post<any>(
        `/rounds/${roundId}/close`
      );
      return response.data;
    } catch (error) {
      console.error(`Failed to close round ${roundId}:`, error);
      throw error;
    }
  }
}

// Export singleton instance
export const discussionApi = new DiscussionApiClient();

// Export class for testing purposes
export { DiscussionApiClient };

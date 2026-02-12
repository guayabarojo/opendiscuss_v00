// API Types - Generated from OpenAPI spec

export type DiscussionMode = 'HOST_DEFINED' | 'AUTO_GENERATED';

export type DiscussionStatus = 'CREATED' | 'ACTIVE' | 'COMPLETED' | 'TERMINATED';

export type RoundStatus =
  | 'PENDING'
  | 'QUESTION_READY'
  | 'SUBMISSION_OPEN'
  | 'SUBMISSION_CLOSED'
  | 'SUMMARIZING'
  | 'APPROVING'
  | 'CLUSTERING'
  | 'SANKEY_BUILDING'
  | 'COMPLETE'
  | 'FAILED';

export type DropoutReason = 'APPROVAL_TIMEOUT' | 'NO_SUBMISSION' | 'VOLUNTARY';

export interface CreateDiscussionRequest {
  community_id: string;
  mode: DiscussionMode;
  total_rounds: number;
  questions?: string[];
  seed_question?: string;
  timing_mode?: 'SYNCHRONOUS' | 'ASYNCHRONOUS';
  round_duration_hours?: number;
  min_submissions_for_advance?: number;
  auto_advance_enabled?: boolean;
}

export interface RoundInfo {
  round_id: string;
  round_num: number;
  status: string;
}

export interface Discussion {
  discussion_id: string;
  community_id: string;
  mode: DiscussionMode;
  total_rounds: number;
  current_round_num: number;
  status: DiscussionStatus;
  created_at: string;
  started_at: string | null;
  completed_at: string | null;
  terminated_reason: string | null;
  host_user_id: string;
  rounds?: RoundInfo[];
  timing_mode?: 'SYNCHRONOUS' | 'ASYNCHRONOUS';
  round_duration_hours?: number;
  min_submissions_for_advance?: number;
  auto_advance_enabled?: boolean;
}

export interface Round {
  round_id: string;
  discussion_id: string;
  round_num: number;
  question_text: string;
  status: RoundStatus;
  submission_window_duration_sec: number;
  submission_window_start: string | null;
  submission_window_end: string | null;
  approval_deadline: string | null;
  completed_at: string | null;
}

export interface RoundStatusResponse {
  round_id: string;
  status?: RoundStatus;
  round_status?: string;
  question_text?: string;
  current_time: string;
  window_start?: string | null;
  window_end?: string | null;
  submission_window_end?: string | null;
  approval_deadline?: string | null;
  time_remaining_seconds?: number | null;
  remaining_time_sec?: number | null;
  is_open?: boolean;
  participant_stats?: {
    submitted_count: number;
    approved_count: number;
    pending_approval_count: number;
  };
}

export interface Participant {
  participant_id: string;
  discussion_id: string;
  first_round: number;
  last_round: number | null;
  dropout_reason: DropoutReason | null;
  created_at: string;
}

export interface ThoughtSpace {
  cluster_id: string;
  label: string;
  member_count: number;
  member_pct: number;
}

export interface SankeyColumn {
  round_num: number;
  thought_spaces: ThoughtSpace[];
}

export interface Flow {
  flow_id: string;
  source_cluster_id: string;
  target_cluster_id: string;
  participant_count: number;
}

export interface SankeyDiagram {
  columns: SankeyColumn[];
  flows: Flow[];
}

export interface DiscussionReport {
  discussion_id: string;
  sankey_diagram: SankeyDiagram;
  metadata: {
    total_rounds: number;
    total_participants: number;
    duration_minutes: number;
    questions: string[];
  };
}

export interface ApiError {
  error: string;
  message: string;
  details?: Record<string, unknown>;
}

// Submission Types (T072, T073)

export type SummaryStatus =
  | 'PENDING'
  | 'APPROVED'
  | 'SUPERSEDED'
  | 'REJECTED'
  | 'APPROVAL_TIMEOUT';

export interface SubmitRequest {
  participant_id: string;
  round_id: string;
  submission_text: string;
  modality: string;
}

export interface SubmissionResponse {
  submission_id: string;
  participant_id: string;
  round_id: string;
  submission_text: string;
  modality: string;
  submitted_at: string;
  summary_status: SummaryStatus;
  remaining_submissions: number;
}

export interface SubmissionHistoryItem {
  submission_id: string;
  submission_text: string;
  modality: string;
  submitted_at: string;
  summary_status: SummaryStatus;
  is_currently_approved: boolean;
}

export interface SubmissionHistoryResponse {
  participant_id: string;
  round_id: string;
  submissions: SubmissionHistoryItem[];
  total_submissions: number;
  remaining_submissions: number;
}

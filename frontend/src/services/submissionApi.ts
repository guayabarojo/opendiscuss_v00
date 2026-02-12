import axios from 'axios';

const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

export interface SubmissionRequest {
  participant_id: string;
  round_id: string;
  text: string;
  modality?: 'TEXT' | 'VOICE';
}

export interface SubmissionResponse {
  submission_id: string;
  participant_id: string;
  round_id: string;
  timestamp: string;
  modality: 'TEXT' | 'VOICE';
  counted: boolean;
}

export interface TranscriptResponse {
  transcript_id: string;
  recording_id: string;
  transcript_text: string;
  latency_ms: number;
}

export interface SubmissionListResponse {
  submissions: SubmissionResponse[];
  total_count: number;
  max_allowed: number;
  can_submit_more: boolean;
}

export const submitText = async (
  participantId: string,
  roundId: string,
  text: string
): Promise<SubmissionResponse> => {
  const response = await axios.post(`${API_BASE_URL}/api/v1/submissions/`, {
    participant_id: participantId,
    round_id: roundId,
    text,
    modality: 'TEXT'
  });
  return response.data;
};

export const transcribeVoice = async (
  participantId: string,
  roundId: string,
  audioBlob: Blob
): Promise<TranscriptResponse> => {
  const formData = new FormData();
  formData.append('audio', audioBlob, 'recording.webm');
  formData.append('participant_id', participantId);
  formData.append('round_id', roundId);

  const response = await axios.post(
    `${API_BASE_URL}/api/v1/voice/transcribe`,
    formData,
    {
      headers: {
        'Content-Type': 'multipart/form-data',
      },
    }
  );

  return response.data;
};

export const deleteRecording = async (recordingId: string): Promise<void> => {
  await axios.delete(`${API_BASE_URL}/api/v1/voice/${recordingId}`);
};

export const acceptTranscript = async (
  participantId: string,
  roundId: string,
  transcriptText: string
): Promise<SubmissionResponse> => {
  // Accept transcript by submitting it as text with VOICE modality
  const response = await axios.post(`${API_BASE_URL}/api/v1/submissions/`, {
    participant_id: participantId,
    round_id: roundId,
    text: transcriptText,
    modality: 'VOICE'
  });
  return response.data;
};

export const getParticipantSubmissions = async (
  participantId: string,
  roundId: string
): Promise<SubmissionListResponse> => {
  const response = await axios.get(
    `${API_BASE_URL}/api/v1/submissions/participant/${participantId}/round/${roundId}`
  );
  return response.data;
};

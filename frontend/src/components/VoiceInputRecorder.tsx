import React, { useState, useRef, useEffect } from 'react';
import { transcribeVoice, deleteRecording, acceptTranscript, TranscriptResponse } from '../services/submissionApi';

interface VoiceInputRecorderProps {
  participantId: string;
  roundId: string;
  onSubmissionComplete: (submissionId: string) => void;
  disabled?: boolean;
}

type RecorderState = 'idle' | 'recording' | 'transcribing' | 'reviewing' | 'accepting';

const VoiceInputRecorder: React.FC<VoiceInputRecorderProps> = ({
  participantId,
  roundId,
  onSubmissionComplete,
  disabled = false
}) => {
  const [state, setState] = useState<RecorderState>('idle');
  const [transcript, setTranscript] = useState<TranscriptResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [recordingDuration, setRecordingDuration] = useState(0);
  const [latencyWarning, setLatencyWarning] = useState(false);

  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const audioChunksRef = useRef<Blob[]>([]);
  const timerRef = useRef<NodeJS.Timeout | null>(null);

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      if (timerRef.current) {
        clearInterval(timerRef.current);
      }
      if (mediaRecorderRef.current && mediaRecorderRef.current.state === 'recording') {
        mediaRecorderRef.current.stop();
      }
    };
  }, []);

  const startRecording = async () => {
    try {
      setError(null);
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });

      const mediaRecorder = new MediaRecorder(stream, {
        mimeType: 'audio/webm;codecs=opus'
      });

      mediaRecorderRef.current = mediaRecorder;
      audioChunksRef.current = [];

      mediaRecorder.ondataavailable = (event) => {
        if (event.data.size > 0) {
          audioChunksRef.current.push(event.data);
        }
      };

      mediaRecorder.onstop = async () => {
        stream.getTracks().forEach(track => track.stop());
        if (timerRef.current) {
          clearInterval(timerRef.current);
        }

        // Create audio blob and transcribe
        const audioBlob = new Blob(audioChunksRef.current, { type: 'audio/webm' });
        await transcribeAudio(audioBlob);
      };

      mediaRecorder.start();
      setState('recording');
      setRecordingDuration(0);

      // Start timer
      timerRef.current = setInterval(() => {
        setRecordingDuration(prev => prev + 1);
      }, 1000);

    } catch (err) {
      setError('Failed to access microphone. Please grant permission and try again.');
      console.error('Recording error:', err);
    }
  };

  const stopRecording = () => {
    if (mediaRecorderRef.current && mediaRecorderRef.current.state === 'recording') {
      mediaRecorderRef.current.stop();
    }
  };

  const transcribeAudio = async (audioBlob: Blob) => {
    setState('transcribing');
    setError(null);

    try {
      const response = await transcribeVoice(participantId, roundId, audioBlob);
      setTranscript(response);
      setState('reviewing');

      // Check latency (SC-002: target < 3 seconds)
      if (response.latency_ms > 3000) {
        setLatencyWarning(true);
      } else {
        setLatencyWarning(false);
      }
    } catch (err: any) {
      console.error('Transcription error:', err);

      const errorDetail = err.response?.data?.detail;
      const isRetryable = errorDetail?.retryable !== false;

      setError(
        isRetryable
          ? 'Transcription failed. Please try recording again.'
          : 'Transcription service unavailable. Please try text input instead.'
      );
      setState('idle');
    }
  };

  const handleReRecord = async () => {
    if (transcript) {
      try {
        // Delete previous recording
        await deleteRecording(transcript.recording_id);
        setTranscript(null);
        setLatencyWarning(false);
        setState('idle');
      } catch (err) {
        console.error('Failed to delete recording:', err);
        // Continue anyway - allow user to record again
        setTranscript(null);
        setLatencyWarning(false);
        setState('idle');
      }
    }
  };

  const handleAcceptTranscript = async () => {
    if (!transcript) return;

    setState('accepting');
    setError(null);

    try {
      // Submit transcript as text with VOICE modality
      const response = await acceptTranscript(
        participantId,
        roundId,
        transcript.transcript_text
      );

      // Clean up: delete recording and transcript
      try {
        await deleteRecording(transcript.recording_id);
      } catch (err) {
        console.error('Failed to delete recording after acceptance:', err);
        // Not critical - submission succeeded
      }

      onSubmissionComplete(response.submission_id);

      // Reset state
      setTranscript(null);
      setLatencyWarning(false);
      setState('idle');
    } catch (err: any) {
      console.error('Submission error:', err);
      setError('Failed to submit transcript. Please try again.');
      setState('reviewing');
    }
  };

  const formatDuration = (seconds: number): string => {
    const mins = Math.floor(seconds / 60);
    const secs = seconds % 60;
    return `${mins}:${secs.toString().padStart(2, '0')}`;
  };

  return (
    <div className="voice-input-recorder" style={{ padding: '20px', border: '1px solid #ddd', borderRadius: '8px' }}>
      <h3>Voice Input</h3>

      {error && (
        <div style={{ padding: '10px', backgroundColor: '#fee', color: '#c00', borderRadius: '4px', marginBottom: '10px' }}>
          {error}
        </div>
      )}

      {state === 'idle' && (
        <div>
          <button
            onClick={startRecording}
            disabled={disabled}
            style={{
              padding: '12px 24px',
              fontSize: '16px',
              backgroundColor: disabled ? '#ccc' : '#007bff',
              color: 'white',
              border: 'none',
              borderRadius: '4px',
              cursor: disabled ? 'not-allowed' : 'pointer'
            }}
          >
            🎤 Start Recording
          </button>
        </div>
      )}

      {state === 'recording' && (
        <div>
          <div style={{ marginBottom: '10px' }}>
            <div style={{ fontSize: '24px', fontWeight: 'bold', color: '#dc3545' }}>
              ● Recording... {formatDuration(recordingDuration)}
            </div>
            <div style={{ marginTop: '10px', fontSize: '12px', color: '#666' }}>
              Audio waveform visualization would go here
            </div>
          </div>
          <button
            onClick={stopRecording}
            style={{
              padding: '12px 24px',
              fontSize: '16px',
              backgroundColor: '#dc3545',
              color: 'white',
              border: 'none',
              borderRadius: '4px',
              cursor: 'pointer'
            }}
          >
            ⏹ Stop Recording
          </button>
        </div>
      )}

      {state === 'transcribing' && (
        <div style={{ textAlign: 'center', padding: '20px' }}>
          <div style={{ fontSize: '18px', marginBottom: '10px' }}>
            Transcribing audio...
          </div>
          <div style={{ fontSize: '14px', color: '#666' }}>
            This should take less than 3 seconds
          </div>
        </div>
      )}

      {state === 'reviewing' && transcript && (
        <div>
          {latencyWarning && (
            <div style={{ padding: '10px', backgroundColor: '#fff3cd', color: '#856404', borderRadius: '4px', marginBottom: '10px' }}>
              ⚠️ Transcription took {(transcript.latency_ms / 1000).toFixed(1)}s (target: &lt;3s)
            </div>
          )}

          <div style={{ marginBottom: '15px' }}>
            <div style={{ fontWeight: 'bold', marginBottom: '5px' }}>Transcript:</div>
            <div style={{
              padding: '15px',
              backgroundColor: '#f8f9fa',
              border: '1px solid #dee2e6',
              borderRadius: '4px',
              minHeight: '80px',
              whiteSpace: 'pre-wrap'
            }}>
              {transcript.transcript_text}
            </div>
            <div style={{ fontSize: '12px', color: '#666', marginTop: '5px' }}>
              Transcribed in {transcript.latency_ms.toFixed(0)}ms
            </div>
          </div>

          <div style={{ display: 'flex', gap: '10px' }}>
            <button
              onClick={handleReRecord}
              style={{
                padding: '10px 20px',
                backgroundColor: '#6c757d',
                color: 'white',
                border: 'none',
                borderRadius: '4px',
                cursor: 'pointer'
              }}
            >
              🔄 Re-record
            </button>
            <button
              onClick={handleAcceptTranscript}
              style={{
                padding: '10px 20px',
                backgroundColor: '#28a745',
                color: 'white',
                border: 'none',
                borderRadius: '4px',
                cursor: 'pointer',
                flex: 1
              }}
            >
              ✓ Accept Transcript
            </button>
          </div>
        </div>
      )}

      {state === 'accepting' && (
        <div style={{ textAlign: 'center', padding: '20px' }}>
          <div style={{ fontSize: '18px' }}>
            Submitting...
          </div>
        </div>
      )}
    </div>
  );
};

export default VoiceInputRecorder;

"""
Example usage of voice input API for Input Collection Protocol.

This demonstrates the complete voice input flow:
1. Record audio
2. Transcribe via Whisper API
3. Review transcript
4. Accept or re-record
5. Submit as text with VOICE modality
"""

import asyncio
from pathlib import Path


async def example_voice_flow():
    """
    Example voice input workflow.

    This is a conceptual example - in production, the frontend
    would handle recording and the API would handle transcription.
    """

    print("Voice Input Flow Example")
    print("=" * 50)

    # Step 1: Participant records audio (browser MediaRecorder)
    print("\n1. Recording audio...")
    print("   - Browser captures microphone input")
    print("   - Creates WebM audio blob")
    print("   - Duration: 10 seconds")

    # Step 2: Upload and transcribe
    print("\n2. Uploading to /api/v1/voice/transcribe...")
    print("   POST /api/v1/voice/transcribe")
    print("   Content-Type: multipart/form-data")
    print("   Body:")
    print("     - audio: <WebM file>")
    print("     - participant_id: 550e8400-e29b-41d4-a716-446655440000")
    print("     - round_id: 660e8400-e29b-41d4-a716-446655440000")

    # Simulated response
    print("\n   Response (200 OK):")
    print("   {")
    print('     "transcript_id": "770e8400-e29b-41d4-a716-446655440000",')
    print('     "recording_id": "880e8400-e29b-41d4-a716-446655440000",')
    print('     "transcript_text": "I think we should focus on improving our communication process.",')
    print('     "latency_ms": 1250.5')
    print("   }")

    # Step 3: Review transcript
    print("\n3. Participant reviews transcript...")
    print("   Text: 'I think we should focus on improving our communication process.'")
    print("   Options:")
    print("     - Accept transcript")
    print("     - Re-record (delete and start over)")

    # Step 4a: Re-record scenario
    print("\n4a. Re-record scenario:")
    print("    DELETE /api/v1/voice/880e8400-e29b-41d4-a716-446655440000")
    print("    Response: 204 No Content")
    print("    (Go back to step 1)")

    # Step 4b: Accept transcript scenario
    print("\n4b. Accept transcript scenario:")
    print("    POST /api/v1/submissions/")
    print("    Body:")
    print("    {")
    print('      "participant_id": "550e8400-e29b-41d4-a716-446655440000",')
    print('      "round_id": "660e8400-e29b-41d4-a716-446655440000",')
    print('      "text": "I think we should focus on improving our communication process.",')
    print('      "modality": "VOICE"')
    print("    }")

    print("\n   Response (201 Created):")
    print("   {")
    print('     "submission_id": "990e8400-e29b-41d4-a716-446655440000",')
    print('     "participant_id": "550e8400-e29b-41d4-a716-446655440000",')
    print('     "round_id": "660e8400-e29b-41d4-a716-446655440000",')
    print('     "timestamp": "2026-02-01T20:15:30Z",')
    print('     "modality": "VOICE",')
    print('     "counted": false')
    print("   }")

    # Step 5: Cleanup
    print("\n5. Backend cleanup:")
    print("   - AudioRecording deleted from ephemeral storage")
    print("   - Transcript deleted from ephemeral storage")
    print("   - SubmissionMetadata persisted to database")
    print("   - RawSubmission stored ephemeral (for summarization)")
    print("   - submission.created event published")

    print("\n" + "=" * 50)
    print("Voice input flow complete!")
    print("\nKey Success Criteria (SC-002):")
    print("✓ Transcription completed in 1250ms (target: <3000ms)")
    print("✓ Transcript displayed for review")
    print("✓ Re-record option available")
    print("✓ Submitted with VOICE modality")
    print("✓ Audio not persisted long-term")


def print_api_reference():
    """Print API reference for voice endpoints."""
    print("\n\nAPI Reference: Voice Input Endpoints")
    print("=" * 50)

    print("\n1. POST /api/v1/voice/transcribe")
    print("   Purpose: Transcribe audio to text")
    print("   Request: multipart/form-data")
    print("     - audio: File (WebM, MP3, WAV)")
    print("     - participant_id: UUID")
    print("     - round_id: UUID")
    print("   Response: 200 OK")
    print("     - transcript_id: UUID")
    print("     - recording_id: UUID")
    print("     - transcript_text: string")
    print("     - latency_ms: float")
    print("   Errors:")
    print("     - 400: Invalid audio")
    print("     - 500: Transcription failed (includes retryable flag)")

    print("\n2. DELETE /api/v1/voice/{recording_id}")
    print("   Purpose: Delete recording and transcript (for re-record)")
    print("   Response: 204 No Content")
    print("   Errors:")
    print("     - 404: Recording not found")

    print("\n3. POST /api/v1/submissions/")
    print("   Purpose: Submit transcript as text (with modality=VOICE)")
    print("   Request: application/json")
    print("     - participant_id: UUID")
    print("     - round_id: UUID")
    print("     - text: string (transcript)")
    print("     - modality: 'VOICE'")
    print("   Response: 201 Created")
    print("     - submission_id: UUID")
    print("     - ...other fields")


if __name__ == "__main__":
    asyncio.run(example_voice_flow())
    print_api_reference()

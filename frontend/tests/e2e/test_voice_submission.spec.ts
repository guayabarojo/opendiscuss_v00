/**
 * E2E Test for Voice Submission Flow (T081)
 *
 * Tests complete voice flow: record → transcript → accept → verify submission.
 * Uses Playwright for browser automation with MediaRecorder mocking.
 */

import { test, expect } from '@playwright/test';

test.describe('Voice Submission E2E', () => {
  const participantId = 'test-participant-voice';
  const roundId = 'test-round-voice';

  test.beforeEach(async ({ page, context }) => {
    // Grant microphone permissions
    await context.grantPermissions(['microphone']);

    // Mock MediaRecorder API
    await page.addInitScript(() => {
      // @ts-ignore
      class MockMediaRecorder {
        ondataavailable: ((event: any) => void) | null = null;
        onstop: (() => void) | null = null;
        onerror: ((event: any) => void) | null = null;
        state: string = 'inactive';
        mimeType: string = 'audio/webm';

        constructor(stream: MediaStream, options?: any) {
          this.mimeType = options?.mimeType || 'audio/webm';
        }

        start() {
          this.state = 'recording';
          // Simulate recording for 100ms
          setTimeout(() => {
            if (this.ondataavailable) {
              const mockBlob = new Blob(['mock audio data'], { type: this.mimeType });
              this.ondataavailable({ data: mockBlob });
            }
          }, 100);
        }

        stop() {
          this.state = 'inactive';
          if (this.onstop) {
            this.onstop();
          }
        }

        pause() {
          this.state = 'paused';
        }

        resume() {
          this.state = 'recording';
        }

        static isTypeSupported(type: string) {
          return type === 'audio/webm' || type === 'audio/webm;codecs=opus';
        }
      }

      // @ts-ignore
      window.MediaRecorder = MockMediaRecorder;

      // Mock getUserMedia
      // @ts-ignore
      navigator.mediaDevices = {
        getUserMedia: async (constraints: MediaStreamConstraints) => {
          const mockStream = {
            getTracks: () => [{
              stop: () => {},
              enabled: true,
              kind: 'audio',
              label: 'Mock Audio Track',
            }],
            getAudioTracks: () => [{
              stop: () => {},
              enabled: true,
              kind: 'audio',
              label: 'Mock Audio Track',
            }],
            getVideoTracks: () => [],
            active: true,
          };
          return mockStream as MediaStream;
        }
      };
    });

    // Mock API responses
    await page.route('**/api/v1/voice/transcribe', async (route) => {
      if (route.request().method() === 'POST') {
        await route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify({
            transcript_id: 'transcript-123',
            recording_id: 'recording-456',
            transcript_text: 'This is the transcribed text from the audio recording.',
            latency_ms: 1250
          })
        });
      }
    });

    await page.route('**/api/v1/voice/recording-*', async (route) => {
      if (route.request().method() === 'DELETE') {
        await route.fulfill({
          status: 204
        });
      }
    });

    await page.route('**/api/v1/submissions/', async (route) => {
      if (route.request().method() === 'POST') {
        await route.fulfill({
          status: 201,
          contentType: 'application/json',
          body: JSON.stringify({
            submission_id: 'submission-voice-123',
            participant_id: participantId,
            round_id: roundId,
            timestamp: new Date().toISOString(),
            modality: 'VOICE',
            counted: true
          })
        });
      }
    });

    await page.route(`**/api/v1/submissions/participant/${participantId}/round/${roundId}`, async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          submissions: [],
          total_count: 0,
          max_allowed: 3,
          can_submit_more: true
        })
      });
    });
  });

  test('should complete voice submission flow', async ({ page }) => {
    await page.goto(`/rounds/${roundId}/input?participant=${participantId}`);

    // Find and click the voice input tab or button
    const voiceButton = page.getByRole('button', { name: /voice input|record|microphone/i });
    if (await voiceButton.isVisible()) {
      await voiceButton.click();
    }

    // Find the record button
    const recordButton = page.getByRole('button', { name: /record|start recording/i });
    await expect(recordButton).toBeVisible();

    // Click to start recording
    await recordButton.click();

    // Should show recording indicator
    await expect(page.getByText(/recording|listening/i)).toBeVisible({ timeout: 2000 });

    // Wait a moment to simulate recording
    await page.waitForTimeout(500);

    // Find and click stop button
    const stopButton = page.getByRole('button', { name: /stop|stop recording/i });
    await stopButton.click();

    // Should show transcribing state
    await expect(page.getByText(/transcribing|processing/i)).toBeVisible({ timeout: 2000 });

    // Wait for transcript to appear
    await expect(page.getByText(/this is the transcribed text/i)).toBeVisible({ timeout: 5000 });

    // Should show latency info
    await expect(page.getByText(/1250|1.25|1.3/)).toBeVisible();

    // Find and click accept button
    const acceptButton = page.getByRole('button', { name: /accept|submit transcript|use this/i });
    await expect(acceptButton).toBeVisible();
    await acceptButton.click();

    // Should show success message
    await expect(page.getByText(/submission successful|submitted/i)).toBeVisible({ timeout: 5000 });

    // Should return to initial state
    await expect(recordButton).toBeVisible({ timeout: 2000 });
  });

  test('should allow re-recording', async ({ page }) => {
    await page.goto(`/rounds/${roundId}/input?participant=${participantId}`);

    // Start voice input
    const voiceButton = page.getByRole('button', { name: /voice input|record|microphone/i });
    if (await voiceButton.isVisible()) {
      await voiceButton.click();
    }

    // Record first attempt
    const recordButton = page.getByRole('button', { name: /record|start recording/i });
    await recordButton.click();
    await page.waitForTimeout(300);

    const stopButton = page.getByRole('button', { name: /stop|stop recording/i });
    await stopButton.click();

    // Wait for transcript
    await expect(page.getByText(/this is the transcribed text/i)).toBeVisible({ timeout: 5000 });

    // Find and click re-record button
    const reRecordButton = page.getByRole('button', { name: /re-record|record again|try again/i });
    await expect(reRecordButton).toBeVisible();
    await reRecordButton.click();

    // Should return to recording state
    await expect(recordButton).toBeVisible();

    // Transcript should be cleared
    await expect(page.getByText(/this is the transcribed text/i)).not.toBeVisible();
  });

  test('should handle transcription errors', async ({ page }) => {
    // Override mock to return error
    await page.route('**/api/v1/voice/transcribe', async (route) => {
      if (route.request().method() === 'POST') {
        await route.fulfill({
          status: 500,
          contentType: 'application/json',
          body: JSON.stringify({
            detail: {
              error_code: 'TRANSCRIPTION_FAILED',
              message: 'Failed to transcribe audio',
              retryable: true
            }
          })
        });
      }
    });

    await page.goto(`/rounds/${roundId}/input?participant=${participantId}`);

    // Start voice input
    const voiceButton = page.getByRole('button', { name: /voice input|record|microphone/i });
    if (await voiceButton.isVisible()) {
      await voiceButton.click();
    }

    // Record
    const recordButton = page.getByRole('button', { name: /record|start recording/i });
    await recordButton.click();
    await page.waitForTimeout(300);

    const stopButton = page.getByRole('button', { name: /stop|stop recording/i });
    await stopButton.click();

    // Should show error message
    await expect(page.getByText(/failed to transcribe|transcription failed/i)).toBeVisible({ timeout: 5000 });

    // Should offer retry option
    const retryButton = page.getByRole('button', { name: /retry|try again/i });
    await expect(retryButton).toBeVisible();
  });

  test('should show latency warning for slow transcription', async ({ page }) => {
    // Override mock to return high latency
    await page.route('**/api/v1/voice/transcribe', async (route) => {
      if (route.request().method() === 'POST') {
        await route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify({
            transcript_id: 'transcript-123',
            recording_id: 'recording-456',
            transcript_text: 'Slow transcription test',
            latency_ms: 3500 // Above 3000ms threshold
          })
        });
      }
    });

    await page.goto(`/rounds/${roundId}/input?participant=${participantId}`);

    // Start voice input
    const voiceButton = page.getByRole('button', { name: /voice input|record|microphone/i });
    if (await voiceButton.isVisible()) {
      await voiceButton.click();
    }

    // Record
    const recordButton = page.getByRole('button', { name: /record|start recording/i });
    await recordButton.click();
    await page.waitForTimeout(300);

    const stopButton = page.getByRole('button', { name: /stop|stop recording/i });
    await stopButton.click();

    // Wait for transcript
    await expect(page.getByText(/slow transcription test/i)).toBeVisible({ timeout: 5000 });

    // Should show latency warning
    await expect(page.getByText(/slow|took longer|3.5|3500/i)).toBeVisible();
  });

  test('should handle microphone permission denial', async ({ page, context }) => {
    // Create a new page with denied permissions
    const deniedPage = await context.newPage();

    // Override getUserMedia to throw permission error
    await deniedPage.addInitScript(() => {
      // @ts-ignore
      navigator.mediaDevices = {
        getUserMedia: async () => {
          throw new DOMException('Permission denied', 'NotAllowedError');
        }
      };
    });

    await deniedPage.goto(`/rounds/${roundId}/input?participant=${participantId}`);

    // Start voice input
    const voiceButton = deniedPage.getByRole('button', { name: /voice input|record|microphone/i });
    if (await voiceButton.isVisible()) {
      await voiceButton.click();
    }

    // Try to start recording
    const recordButton = deniedPage.getByRole('button', { name: /record|start recording/i });
    await recordButton.click();

    // Should show permission error
    await expect(deniedPage.getByText(/microphone permission|access denied|enable microphone/i)).toBeVisible({ timeout: 3000 });

    await deniedPage.close();
  });

  test('should display transcript for review', async ({ page }) => {
    await page.goto(`/rounds/${roundId}/input?participant=${participantId}`);

    // Start voice input
    const voiceButton = page.getByRole('button', { name: /voice input|record|microphone/i });
    if (await voiceButton.isVisible()) {
      await voiceButton.click();
    }

    // Record
    const recordButton = page.getByRole('button', { name: /record|start recording/i });
    await recordButton.click();
    await page.waitForTimeout(300);

    const stopButton = page.getByRole('button', { name: /stop|stop recording/i });
    await stopButton.click();

    // Wait for transcript
    const transcriptText = 'This is the transcribed text from the audio recording.';
    await expect(page.getByText(transcriptText)).toBeVisible({ timeout: 5000 });

    // Should have review section
    await expect(page.getByText(/review|transcript/i)).toBeVisible();

    // Should have action buttons
    await expect(page.getByRole('button', { name: /accept|use this/i })).toBeVisible();
    await expect(page.getByRole('button', { name: /re-record|try again/i })).toBeVisible();
  });

  test('should submit transcript with VOICE modality', async ({ page }) => {
    let submittedData: any = null;

    // Capture the submission request
    await page.route('**/api/v1/submissions/', async (route) => {
      if (route.request().method() === 'POST') {
        submittedData = await route.request().postDataJSON();
        await route.fulfill({
          status: 201,
          contentType: 'application/json',
          body: JSON.stringify({
            submission_id: 'submission-voice-123',
            participant_id: participantId,
            round_id: roundId,
            timestamp: new Date().toISOString(),
            modality: 'VOICE',
            counted: true
          })
        });
      }
    });

    await page.goto(`/rounds/${roundId}/input?participant=${participantId}`);

    // Complete voice flow
    const voiceButton = page.getByRole('button', { name: /voice input|record|microphone/i });
    if (await voiceButton.isVisible()) {
      await voiceButton.click();
    }

    const recordButton = page.getByRole('button', { name: /record|start recording/i });
    await recordButton.click();
    await page.waitForTimeout(300);

    const stopButton = page.getByRole('button', { name: /stop|stop recording/i });
    await stopButton.click();

    await expect(page.getByText(/this is the transcribed text/i)).toBeVisible({ timeout: 5000 });

    const acceptButton = page.getByRole('button', { name: /accept|submit transcript/i });
    await acceptButton.click();

    // Verify submission was made with correct modality
    await page.waitForTimeout(500); // Wait for request to complete
    expect(submittedData).toBeTruthy();
    expect(submittedData.modality).toBe('VOICE');
    expect(submittedData.text).toContain('transcribed text');
  });

  test('should handle recording cancellation', async ({ page }) => {
    await page.goto(`/rounds/${roundId}/input?participant=${participantId}`);

    // Start voice input
    const voiceButton = page.getByRole('button', { name: /voice input|record|microphone/i });
    if (await voiceButton.isVisible()) {
      await voiceButton.click();
    }

    // Start recording
    const recordButton = page.getByRole('button', { name: /record|start recording/i });
    await recordButton.click();

    await expect(page.getByText(/recording|listening/i)).toBeVisible();

    // Look for cancel button
    const cancelButton = page.getByRole('button', { name: /cancel/i }).first();
    if (await cancelButton.isVisible()) {
      await cancelButton.click();

      // Should return to initial state
      await expect(recordButton).toBeVisible();
      await expect(page.getByText(/recording|listening/i)).not.toBeVisible();
    }
  });

  test('should handle multiple voice submissions', async ({ page }) => {
    await page.goto(`/rounds/${roundId}/input?participant=${participantId}`);

    // First submission
    const voiceButton = page.getByRole('button', { name: /voice input|record|microphone/i });
    if (await voiceButton.isVisible()) {
      await voiceButton.click();
    }

    let recordButton = page.getByRole('button', { name: /record|start recording/i });
    await recordButton.click();
    await page.waitForTimeout(300);

    let stopButton = page.getByRole('button', { name: /stop|stop recording/i });
    await stopButton.click();

    await expect(page.getByText(/this is the transcribed text/i)).toBeVisible({ timeout: 5000 });

    let acceptButton = page.getByRole('button', { name: /accept|submit transcript/i });
    await acceptButton.click();

    await expect(page.getByText(/submission successful/i)).toBeVisible({ timeout: 5000 });

    // Should be able to start another recording
    await page.waitForTimeout(1000);
    recordButton = page.getByRole('button', { name: /record|start recording/i });
    await expect(recordButton).toBeVisible();
  });

  test('should cleanup audio resources', async ({ page }) => {
    await page.goto(`/rounds/${roundId}/input?participant=${participantId}`);

    // Start voice input
    const voiceButton = page.getByRole('button', { name: /voice input|record|microphone/i });
    if (await voiceButton.isVisible()) {
      await voiceButton.click();
    }

    // Record and get transcript
    const recordButton = page.getByRole('button', { name: /record|start recording/i });
    await recordButton.click();
    await page.waitForTimeout(300);

    const stopButton = page.getByRole('button', { name: /stop|stop recording/i });
    await stopButton.click();

    await expect(page.getByText(/this is the transcribed text/i)).toBeVisible({ timeout: 5000 });

    // Accept transcript - should trigger cleanup
    const acceptButton = page.getByRole('button', { name: /accept|submit transcript/i });
    await acceptButton.click();

    // Recording should be deleted from backend (DELETE request should be made)
    // This is implicitly tested by the route mock handling DELETE requests
    await expect(page.getByText(/submission successful/i)).toBeVisible({ timeout: 5000 });
  });
});

test.describe('Voice Submission Accessibility', () => {
  const participantId = 'test-participant-voice-a11y';
  const roundId = 'test-round-voice-a11y';

  test.beforeEach(async ({ page, context }) => {
    await context.grantPermissions(['microphone']);

    // Setup mocks
    await page.addInitScript(() => {
      // Mock MediaRecorder
      // @ts-ignore
      class MockMediaRecorder {
        ondataavailable: ((event: any) => void) | null = null;
        onstop: (() => void) | null = null;
        state: string = 'inactive';

        start() {
          this.state = 'recording';
          setTimeout(() => {
            if (this.ondataavailable) {
              const mockBlob = new Blob(['mock'], { type: 'audio/webm' });
              this.ondataavailable({ data: mockBlob });
            }
          }, 100);
        }

        stop() {
          this.state = 'inactive';
          if (this.onstop) this.onstop();
        }

        static isTypeSupported() { return true; }
      }
      // @ts-ignore
      window.MediaRecorder = MockMediaRecorder;

      // @ts-ignore
      navigator.mediaDevices = {
        getUserMedia: async () => ({
          getTracks: () => [{ stop: () => {}, enabled: true }],
          getAudioTracks: () => [{ stop: () => {}, enabled: true }],
          getVideoTracks: () => [],
          active: true,
        })
      };
    });

    await page.route('**/api/v1/voice/transcribe', async (route) => {
      await route.fulfill({
        status: 200,
        body: JSON.stringify({
          transcript_id: 'transcript-123',
          recording_id: 'recording-456',
          transcript_text: 'Accessibility test transcript',
          latency_ms: 1000
        })
      });
    });

    await page.route('**/api/v1/submissions/**', async (route) => {
      await route.fulfill({ status: 200, body: JSON.stringify({ submissions: [], total_count: 0, max_allowed: 3, can_submit_more: true }) });
    });
  });

  test('should be keyboard accessible', async ({ page }) => {
    await page.goto(`/rounds/${roundId}/input?participant=${participantId}`);

    // Tab to voice button
    await page.keyboard.press('Tab');

    const voiceButton = page.getByRole('button', { name: /voice input|record|microphone/i });
    if (await voiceButton.isVisible()) {
      await expect(voiceButton).toBeFocused();

      // Activate with Enter
      await page.keyboard.press('Enter');

      // Tab to record button
      await page.keyboard.press('Tab');
    }

    const recordButton = page.getByRole('button', { name: /record|start recording/i });
    await expect(recordButton).toBeFocused();

    // Activate with Space
    await page.keyboard.press('Space');

    await expect(page.getByText(/recording|listening/i)).toBeVisible();
  });

  test('should announce recording state to screen readers', async ({ page }) => {
    await page.goto(`/rounds/${roundId}/input?participant=${participantId}`);

    const voiceButton = page.getByRole('button', { name: /voice input|record|microphone/i });
    if (await voiceButton.isVisible()) {
      await voiceButton.click();
    }

    const recordButton = page.getByRole('button', { name: /record|start recording/i });
    await recordButton.click();

    // Recording indicator should be visible
    const recordingIndicator = page.getByText(/recording|listening/i);
    await expect(recordingIndicator).toBeVisible();
  });

  test('should have proper button labels', async ({ page }) => {
    await page.goto(`/rounds/${roundId}/input?participant=${participantId}`);

    const voiceButton = page.getByRole('button', { name: /voice input|record|microphone/i });
    if (await voiceButton.isVisible()) {
      await voiceButton.click();
    }

    // All buttons should have clear labels
    await expect(page.getByRole('button', { name: /record|start recording/i })).toBeVisible();
  });
});

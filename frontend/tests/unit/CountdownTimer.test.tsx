/**
 * Unit Tests for CountdownTimer Component (T079)
 *
 * Tests countdown display, color changes, WebSocket connection and updates.
 */

import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import { CountdownTimer } from '../../src/components/CountdownTimer';
import type { TimerUpdate } from '../../src/services/websocketClient';

// Mock WebSocket
class MockWebSocket {
  onopen: ((event: Event) => void) | null = null;
  onmessage: ((event: MessageEvent) => void) | null = null;
  onerror: ((event: Event) => void) | null = null;
  onclose: ((event: CloseEvent) => void) | null = null;
  readyState: number = WebSocket.CONNECTING;

  constructor(public url: string) {
    // Simulate connection opening
    setTimeout(() => {
      this.readyState = WebSocket.OPEN;
      if (this.onopen) {
        this.onopen(new Event('open'));
      }
    }, 10);
  }

  send(data: string) {
    // Mock send
  }

  close() {
    this.readyState = WebSocket.CLOSED;
    if (this.onclose) {
      this.onclose(new CloseEvent('close'));
    }
  }
}

// Mock the WebSocket client
vi.mock('../../src/services/websocketClient', () => {
  return {
    WebSocketTimerClient: vi.fn().mockImplementation((roundId, onUpdate, onError, onClose) => {
      return {
        connect: vi.fn(() => {
          // Simulate connection
          setTimeout(() => {
            // Send initial update
            onUpdate({
              round_id: roundId,
              remaining_seconds: 300,
              is_open: true,
              status: 'OPEN' as const,
              current_time: new Date().toISOString()
            });
          }, 50);
        }),
        disconnect: vi.fn(),
        isConnected: vi.fn(() => true),
        getConnectionStatus: vi.fn(() => 'open')
      };
    })
  };
});

describe('CountdownTimer', () => {
  const defaultProps = {
    roundId: 'round-123',
  };

  beforeEach(() => {
    vi.clearAllMocks();
  });

  afterEach(() => {
    vi.clearAllTimers();
  });

  describe('Initial Rendering', () => {
    it('displays loading state initially', () => {
      render(<CountdownTimer {...defaultProps} />);

      expect(screen.getByText(/connecting to server/i)).toBeInTheDocument();
    });

    it('displays timer spinner while connecting', () => {
      render(<CountdownTimer {...defaultProps} />);

      expect(screen.getByText('⏳')).toBeInTheDocument();
    });
  });

  describe('Time Formatting', () => {
    it('formats time as MM:SS', async () => {
      render(<CountdownTimer {...defaultProps} />);

      await waitFor(() => {
        expect(screen.getByText(/05:00/)).toBeInTheDocument();
      });
    });

    it('pads single digits with zeros', async () => {
      const { WebSocketTimerClient } = await import('../../src/services/websocketClient');
      const mockClient = vi.mocked(WebSocketTimerClient);

      render(<CountdownTimer {...defaultProps} />);

      // Get the onUpdate callback from the mock
      const onUpdateCallback = mockClient.mock.calls[0][1];

      // Send update with 65 seconds (1:05)
      onUpdateCallback({
        round_id: 'round-123',
        remaining_seconds: 65,
        is_open: true,
        status: 'OPEN',
        current_time: new Date().toISOString()
      });

      await waitFor(() => {
        expect(screen.getByText('01:05')).toBeInTheDocument();
      });
    });

    it('displays 00:00 when time is zero', async () => {
      const { WebSocketTimerClient } = await import('../../src/services/websocketClient');
      const mockClient = vi.mocked(WebSocketTimerClient);

      render(<CountdownTimer {...defaultProps} />);

      const onUpdateCallback = mockClient.mock.calls[0][1];
      onUpdateCallback({
        round_id: 'round-123',
        remaining_seconds: 0,
        is_open: false,
        status: 'CLOSED',
        current_time: new Date().toISOString()
      });

      await waitFor(() => {
        expect(screen.getByText('00:00')).toBeInTheDocument();
      });
    });

    it('handles double-digit minutes', async () => {
      const { WebSocketTimerClient } = await import('../../src/services/websocketClient');
      const mockClient = vi.mocked(WebSocketTimerClient);

      render(<CountdownTimer {...defaultProps} />);

      const onUpdateCallback = mockClient.mock.calls[0][1];
      onUpdateCallback({
        round_id: 'round-123',
        remaining_seconds: 720, // 12:00
        is_open: true,
        status: 'OPEN',
        current_time: new Date().toISOString()
      });

      await waitFor(() => {
        expect(screen.getByText('12:00')).toBeInTheDocument();
      });
    });
  });

  describe('Color Coding', () => {
    it('displays green color when more than 60 seconds remain', async () => {
      render(<CountdownTimer {...defaultProps} />);

      await waitFor(() => {
        const timerDisplay = screen.getByText('05:00');
        expect(timerDisplay).toHaveClass('green');
      });
    });

    it('displays yellow color when 31-60 seconds remain', async () => {
      const { WebSocketTimerClient } = await import('../../src/services/websocketClient');
      const mockClient = vi.mocked(WebSocketTimerClient);

      render(<CountdownTimer {...defaultProps} />);

      const onUpdateCallback = mockClient.mock.calls[0][1];
      onUpdateCallback({
        round_id: 'round-123',
        remaining_seconds: 45,
        is_open: true,
        status: 'OPEN',
        current_time: new Date().toISOString()
      });

      await waitFor(() => {
        const timerDisplay = screen.getByText('00:45');
        expect(timerDisplay).toHaveClass('yellow');
      });
    });

    it('displays red color when 30 or fewer seconds remain', async () => {
      const { WebSocketTimerClient } = await import('../../src/services/websocketClient');
      const mockClient = vi.mocked(WebSocketTimerClient);

      render(<CountdownTimer {...defaultProps} />);

      const onUpdateCallback = mockClient.mock.calls[0][1];
      onUpdateCallback({
        round_id: 'round-123',
        remaining_seconds: 15,
        is_open: true,
        status: 'OPEN',
        current_time: new Date().toISOString()
      });

      await waitFor(() => {
        const timerDisplay = screen.getByText('00:15');
        expect(timerDisplay).toHaveClass('red');
      });
    });

    it('displays gray color when window is not open', async () => {
      const { WebSocketTimerClient } = await import('../../src/services/websocketClient');
      const mockClient = vi.mocked(WebSocketTimerClient);

      render(<CountdownTimer {...defaultProps} />);

      const onUpdateCallback = mockClient.mock.calls[0][1];
      onUpdateCallback({
        round_id: 'round-123',
        remaining_seconds: null,
        is_open: false,
        status: 'BEFORE_WINDOW',
        current_time: new Date().toISOString()
      });

      await waitFor(() => {
        const timerDisplay = screen.getByText('--:--');
        expect(timerDisplay).toHaveClass('gray');
      });
    });
  });

  describe('Status Messages', () => {
    it('displays "Submission window is open" when status is OPEN', async () => {
      render(<CountdownTimer {...defaultProps} />);

      await waitFor(() => {
        expect(screen.getByText(/submission window is open/i)).toBeInTheDocument();
      });
    });

    it('displays "Submission window has closed" when status is CLOSED', async () => {
      const { WebSocketTimerClient } = await import('../../src/services/websocketClient');
      const mockClient = vi.mocked(WebSocketTimerClient);

      render(<CountdownTimer {...defaultProps} />);

      const onUpdateCallback = mockClient.mock.calls[0][1];
      onUpdateCallback({
        round_id: 'round-123',
        remaining_seconds: 0,
        is_open: false,
        status: 'CLOSED',
        current_time: new Date().toISOString()
      });

      await waitFor(() => {
        expect(screen.getByText(/submission window has closed/i)).toBeInTheDocument();
      });
    });

    it('displays "Submission window will open soon" when status is BEFORE_WINDOW', async () => {
      const { WebSocketTimerClient } = await import('../../src/services/websocketClient');
      const mockClient = vi.mocked(WebSocketTimerClient);

      render(<CountdownTimer {...defaultProps} />);

      const onUpdateCallback = mockClient.mock.calls[0][1];
      onUpdateCallback({
        round_id: 'round-123',
        remaining_seconds: null,
        is_open: false,
        status: 'BEFORE_WINDOW',
        current_time: new Date().toISOString()
      });

      await waitFor(() => {
        expect(screen.getByText(/submission window will open soon/i)).toBeInTheDocument();
      });
    });

    it('displays "Submission window not yet configured" when status is NOT_OPEN', async () => {
      const { WebSocketTimerClient } = await import('../../src/services/websocketClient');
      const mockClient = vi.mocked(WebSocketTimerClient);

      render(<CountdownTimer {...defaultProps} />);

      const onUpdateCallback = mockClient.mock.calls[0][1];
      onUpdateCallback({
        round_id: 'round-123',
        remaining_seconds: null,
        is_open: false,
        status: 'NOT_OPEN',
        current_time: new Date().toISOString()
      });

      await waitFor(() => {
        expect(screen.getByText(/submission window not yet configured/i)).toBeInTheDocument();
      });
    });
  });

  describe('Warnings', () => {
    it('displays warning when less than 1 minute remains', async () => {
      const { WebSocketTimerClient } = await import('../../src/services/websocketClient');
      const mockClient = vi.mocked(WebSocketTimerClient);

      render(<CountdownTimer {...defaultProps} />);

      const onUpdateCallback = mockClient.mock.calls[0][1];
      onUpdateCallback({
        round_id: 'round-123',
        remaining_seconds: 30,
        is_open: true,
        status: 'OPEN',
        current_time: new Date().toISOString()
      });

      await waitFor(() => {
        expect(screen.getByText(/less than 1 minute remaining/i)).toBeInTheDocument();
      });
    });

    it('does not display warning when more than 1 minute remains', async () => {
      render(<CountdownTimer {...defaultProps} />);

      await waitFor(() => {
        expect(screen.queryByText(/less than 1 minute remaining/i)).not.toBeInTheDocument();
      });
    });

    it('does not display warning when window is closed', async () => {
      const { WebSocketTimerClient } = await import('../../src/services/websocketClient');
      const mockClient = vi.mocked(WebSocketTimerClient);

      render(<CountdownTimer {...defaultProps} />);

      const onUpdateCallback = mockClient.mock.calls[0][1];
      onUpdateCallback({
        round_id: 'round-123',
        remaining_seconds: 30,
        is_open: false,
        status: 'CLOSED',
        current_time: new Date().toISOString()
      });

      await waitFor(() => {
        expect(screen.queryByText(/less than 1 minute remaining/i)).not.toBeInTheDocument();
      });
    });
  });

  describe('WebSocket Connection', () => {
    it('shows connected status when WebSocket is open', async () => {
      render(<CountdownTimer {...defaultProps} />);

      await waitFor(() => {
        expect(screen.getByText(/connected/i)).toBeInTheDocument();
      });
    });

    it('initializes WebSocket client with correct round ID', () => {
      const { WebSocketTimerClient } = require('../../src/services/websocketClient');
      const mockClient = vi.mocked(WebSocketTimerClient);

      render(<CountdownTimer roundId="test-round-789" />);

      expect(mockClient).toHaveBeenCalledWith(
        'test-round-789',
        expect.any(Function),
        expect.any(Function),
        expect.any(Function)
      );
    });

    it('calls disconnect when component unmounts', async () => {
      const { WebSocketTimerClient } = await import('../../src/services/websocketClient');
      const mockDisconnect = vi.fn();
      vi.mocked(WebSocketTimerClient).mockImplementation((roundId, onUpdate) => ({
        connect: vi.fn(() => {
          setTimeout(() => {
            onUpdate({
              round_id: roundId,
              remaining_seconds: 100,
              is_open: true,
              status: 'OPEN',
              current_time: new Date().toISOString()
            });
          }, 10);
        }),
        disconnect: mockDisconnect,
        isConnected: vi.fn(() => true),
        getConnectionStatus: vi.fn(() => 'open')
      }));

      const { unmount } = render(<CountdownTimer {...defaultProps} />);

      await waitFor(() => {
        expect(screen.getByText('01:40')).toBeInTheDocument();
      });

      unmount();

      expect(mockDisconnect).toHaveBeenCalled();
    });
  });

  describe('Error Handling', () => {
    it('displays error message when WebSocket connection fails', async () => {
      const { WebSocketTimerClient } = await import('../../src/services/websocketClient');
      const mockClient = vi.mocked(WebSocketTimerClient);

      render(<CountdownTimer {...defaultProps} />);

      const onErrorCallback = mockClient.mock.calls[0][2];
      onErrorCallback(new Error('Connection failed'));

      await waitFor(() => {
        expect(screen.getByText(/connection issue: connection failed/i)).toBeInTheDocument();
      });
    });

    it('clears error when successful update is received', async () => {
      const { WebSocketTimerClient } = await import('../../src/services/websocketClient');
      const mockClient = vi.mocked(WebSocketTimerClient);

      render(<CountdownTimer {...defaultProps} />);

      const onErrorCallback = mockClient.mock.calls[0][2];
      const onUpdateCallback = mockClient.mock.calls[0][1];

      // First, trigger error
      onErrorCallback(new Error('Connection error'));

      await waitFor(() => {
        expect(screen.getByText(/connection issue/i)).toBeInTheDocument();
      });

      // Then, receive successful update
      onUpdateCallback({
        round_id: 'round-123',
        remaining_seconds: 200,
        is_open: true,
        status: 'OPEN',
        current_time: new Date().toISOString()
      });

      await waitFor(() => {
        expect(screen.queryByText(/connection issue/i)).not.toBeInTheDocument();
      });
    });
  });

  describe('Window Close Callback', () => {
    it('calls onWindowClose when window closes', async () => {
      const onWindowClose = vi.fn();
      const { WebSocketTimerClient } = await import('../../src/services/websocketClient');
      const mockClient = vi.mocked(WebSocketTimerClient);

      render(<CountdownTimer {...defaultProps} onWindowClose={onWindowClose} />);

      const onUpdateCallback = mockClient.mock.calls[0][1];

      // Send update with window closed at 0 seconds
      onUpdateCallback({
        round_id: 'round-123',
        remaining_seconds: 0,
        is_open: false,
        status: 'CLOSED',
        current_time: new Date().toISOString()
      });

      await waitFor(() => {
        expect(onWindowClose).toHaveBeenCalled();
      });
    });

    it('does not call onWindowClose when time reaches zero but status is not CLOSED', async () => {
      const onWindowClose = vi.fn();
      const { WebSocketTimerClient } = await import('../../src/services/websocketClient');
      const mockClient = vi.mocked(WebSocketTimerClient);

      render(<CountdownTimer {...defaultProps} onWindowClose={onWindowClose} />);

      const onUpdateCallback = mockClient.mock.calls[0][1];

      onUpdateCallback({
        round_id: 'round-123',
        remaining_seconds: 0,
        is_open: true,
        status: 'OPEN',
        current_time: new Date().toISOString()
      });

      await waitFor(() => {
        expect(screen.getByText('00:00')).toBeInTheDocument();
      });

      expect(onWindowClose).not.toHaveBeenCalled();
    });
  });

  describe('Time Display Labels', () => {
    it('displays "Time Remaining" label when window is open', async () => {
      render(<CountdownTimer {...defaultProps} />);

      await waitFor(() => {
        expect(screen.getByText(/time remaining/i)).toBeInTheDocument();
      });
    });

    it('displays "Window Status" label when window is not open', async () => {
      const { WebSocketTimerClient } = await import('../../src/services/websocketClient');
      const mockClient = vi.mocked(WebSocketTimerClient);

      render(<CountdownTimer {...defaultProps} />);

      const onUpdateCallback = mockClient.mock.calls[0][1];
      onUpdateCallback({
        round_id: 'round-123',
        remaining_seconds: null,
        is_open: false,
        status: 'BEFORE_WINDOW',
        current_time: new Date().toISOString()
      });

      await waitFor(() => {
        expect(screen.getByText(/window status/i)).toBeInTheDocument();
      });
    });
  });

  describe('Edge Cases', () => {
    it('handles null remaining_seconds', async () => {
      const { WebSocketTimerClient } = await import('../../src/services/websocketClient');
      const mockClient = vi.mocked(WebSocketTimerClient);

      render(<CountdownTimer {...defaultProps} />);

      const onUpdateCallback = mockClient.mock.calls[0][1];
      onUpdateCallback({
        round_id: 'round-123',
        remaining_seconds: null,
        is_open: false,
        status: 'NOT_OPEN',
        current_time: new Date().toISOString()
      });

      await waitFor(() => {
        expect(screen.getByText('--:--')).toBeInTheDocument();
      });
    });

    it('handles negative remaining_seconds', async () => {
      const { WebSocketTimerClient } = await import('../../src/services/websocketClient');
      const mockClient = vi.mocked(WebSocketTimerClient);

      render(<CountdownTimer {...defaultProps} />);

      const onUpdateCallback = mockClient.mock.calls[0][1];
      onUpdateCallback({
        round_id: 'round-123',
        remaining_seconds: -5,
        is_open: false,
        status: 'CLOSED',
        current_time: new Date().toISOString()
      });

      await waitFor(() => {
        expect(screen.getByText('00:00')).toBeInTheDocument();
      });
    });

    it('handles very large time values', async () => {
      const { WebSocketTimerClient } = await import('../../src/services/websocketClient');
      const mockClient = vi.mocked(WebSocketTimerClient);

      render(<CountdownTimer {...defaultProps} />);

      const onUpdateCallback = mockClient.mock.calls[0][1];
      onUpdateCallback({
        round_id: 'round-123',
        remaining_seconds: 7200, // 2 hours
        is_open: true,
        status: 'OPEN',
        current_time: new Date().toISOString()
      });

      await waitFor(() => {
        expect(screen.getByText('120:00')).toBeInTheDocument();
      });
    });
  });
});

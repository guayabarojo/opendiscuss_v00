/**
 * Unit Tests for TextInputForm Component (T078)
 *
 * Tests character count, validation, submit disabled states, rate limiting.
 */

import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { TextInputForm } from '../../src/components/TextInputForm';

describe('TextInputForm', () => {
  const defaultProps = {
    participantId: 'participant-123',
    roundId: 'round-456',
    onSubmit: vi.fn(),
  };

  beforeEach(() => {
    vi.clearAllMocks();
  });

  describe('Character Count', () => {
    it('displays initial character count as 0/5000', () => {
      render(<TextInputForm {...defaultProps} />);
      expect(screen.getByText(/0 \/ 5000 characters/i)).toBeInTheDocument();
    });

    it('updates character count as user types', async () => {
      const user = userEvent.setup();
      render(<TextInputForm {...defaultProps} />);

      const textarea = screen.getByPlaceholderText(/enter your response/i);
      await user.type(textarea, 'Hello World');

      expect(screen.getByText(/11 \/ 5000 characters/i)).toBeInTheDocument();
    });

    it('displays warning color when approaching character limit', async () => {
      const user = userEvent.setup();
      render(<TextInputForm {...defaultProps} />);

      const textarea = screen.getByPlaceholderText(/enter your response/i);
      const longText = 'a'.repeat(4950); // 50 chars remaining
      await user.type(textarea, longText);

      const charCount = screen.getByText(/4950 \/ 5000 characters/i);
      expect(charCount).toHaveClass('warning');
    });

    it('does not apply warning class with more than 100 characters remaining', async () => {
      const user = userEvent.setup();
      render(<TextInputForm {...defaultProps} />);

      const textarea = screen.getByPlaceholderText(/enter your response/i);
      await user.type(textarea, 'Short text');

      const charCount = screen.getByText(/10 \/ 5000 characters/i);
      expect(charCount).not.toHaveClass('warning');
    });
  });

  describe('Validation', () => {
    it('shows validation error when text is empty', async () => {
      const user = userEvent.setup();
      render(<TextInputForm {...defaultProps} />);

      const textarea = screen.getByPlaceholderText(/enter your response/i);
      await user.type(textarea, '   '); // Whitespace only

      expect(screen.getByText(/text cannot be empty or whitespace only/i)).toBeInTheDocument();
    });

    it('shows validation error when text exceeds max length', async () => {
      const user = userEvent.setup();
      render(<TextInputForm {...defaultProps} />);

      const textarea = screen.getByPlaceholderText(/enter your response/i);
      const tooLongText = 'a'.repeat(5001);

      // Using fireEvent for performance with very long strings
      fireEvent.change(textarea, { target: { value: tooLongText } });

      expect(screen.getByText(/text exceeds maximum length/i)).toBeInTheDocument();
    });

    it('does not show validation error for valid text', async () => {
      const user = userEvent.setup();
      render(<TextInputForm {...defaultProps} />);

      const textarea = screen.getByPlaceholderText(/enter your response/i);
      await user.type(textarea, 'Valid text input');

      expect(screen.queryByText(/text cannot be empty/i)).not.toBeInTheDocument();
      expect(screen.queryByText(/text exceeds maximum length/i)).not.toBeInTheDocument();
    });

    it('validates trimmed text', async () => {
      const user = userEvent.setup();
      render(<TextInputForm {...defaultProps} />);

      const textarea = screen.getByPlaceholderText(/enter your response/i);
      await user.type(textarea, '  \n  \t  '); // Only whitespace

      expect(screen.getByText(/text cannot be empty or whitespace only/i)).toBeInTheDocument();
    });
  });

  describe('Submit Button States', () => {
    it('disables submit button when text is empty', () => {
      render(<TextInputForm {...defaultProps} />);

      const submitButton = screen.getByRole('button', { name: /submit/i });
      expect(submitButton).toBeDisabled();
    });

    it('disables submit button when text is only whitespace', async () => {
      const user = userEvent.setup();
      render(<TextInputForm {...defaultProps} />);

      const textarea = screen.getByPlaceholderText(/enter your response/i);
      await user.type(textarea, '   ');

      const submitButton = screen.getByRole('button', { name: /submit/i });
      expect(submitButton).toBeDisabled();
    });

    it('disables submit button when text exceeds max length', async () => {
      render(<TextInputForm {...defaultProps} />);

      const textarea = screen.getByPlaceholderText(/enter your response/i);
      const tooLongText = 'a'.repeat(5001);
      fireEvent.change(textarea, { target: { value: tooLongText } });

      const submitButton = screen.getByRole('button', { name: /submit/i });
      expect(submitButton).toBeDisabled();
    });

    it('enables submit button when text is valid', async () => {
      const user = userEvent.setup();
      render(<TextInputForm {...defaultProps} />);

      const textarea = screen.getByPlaceholderText(/enter your response/i);
      await user.type(textarea, 'Valid submission');

      const submitButton = screen.getByRole('button', { name: /submit/i });
      expect(submitButton).not.toBeDisabled();
    });

    it('disables submit button when disabled prop is true', async () => {
      const user = userEvent.setup();
      render(<TextInputForm {...defaultProps} disabled={true} />);

      const textarea = screen.getByPlaceholderText(/enter your response/i);
      await user.type(textarea, 'Valid text');

      const submitButton = screen.getByRole('button', { name: /submit/i });
      expect(submitButton).toBeDisabled();
    });

    it('shows "Submitting..." while submission is in progress', async () => {
      const user = userEvent.setup();
      const onSubmit = vi.fn(() => new Promise(resolve => setTimeout(resolve, 100)));
      render(<TextInputForm {...defaultProps} onSubmit={onSubmit} />);

      const textarea = screen.getByPlaceholderText(/enter your response/i);
      await user.type(textarea, 'Test submission');

      const submitButton = screen.getByRole('button', { name: /submit/i });
      await user.click(submitButton);

      expect(screen.getByRole('button', { name: /submitting/i })).toBeInTheDocument();
    });
  });

  describe('Form Submission', () => {
    it('calls onSubmit with text when form is submitted', async () => {
      const user = userEvent.setup();
      const onSubmit = vi.fn().mockResolvedValue(undefined);
      render(<TextInputForm {...defaultProps} onSubmit={onSubmit} />);

      const textarea = screen.getByPlaceholderText(/enter your response/i);
      await user.type(textarea, 'My submission text');

      const submitButton = screen.getByRole('button', { name: /submit/i });
      await user.click(submitButton);

      expect(onSubmit).toHaveBeenCalledWith('My submission text');
    });

    it('clears form after successful submission', async () => {
      const user = userEvent.setup();
      const onSubmit = vi.fn().mockResolvedValue(undefined);
      render(<TextInputForm {...defaultProps} onSubmit={onSubmit} />);

      const textarea = screen.getByPlaceholderText(/enter your response/i);
      await user.type(textarea, 'Test text');

      const submitButton = screen.getByRole('button', { name: /submit/i });
      await user.click(submitButton);

      await waitFor(() => {
        expect(textarea).toHaveValue('');
      });
    });

    it('displays error message when submission fails', async () => {
      const user = userEvent.setup();
      const errorMessage = 'Submission window has closed';
      const onSubmit = vi.fn().mockRejectedValue({
        response: { data: { detail: { message: errorMessage } } }
      });
      render(<TextInputForm {...defaultProps} onSubmit={onSubmit} />);

      const textarea = screen.getByPlaceholderText(/enter your response/i);
      await user.type(textarea, 'Test text');

      const submitButton = screen.getByRole('button', { name: /submit/i });
      await user.click(submitButton);

      await waitFor(() => {
        expect(screen.getByText(errorMessage)).toBeInTheDocument();
      });
    });

    it('displays generic error when error has no message', async () => {
      const user = userEvent.setup();
      const onSubmit = vi.fn().mockRejectedValue(new Error('Network error'));
      render(<TextInputForm {...defaultProps} onSubmit={onSubmit} />);

      const textarea = screen.getByPlaceholderText(/enter your response/i);
      await user.type(textarea, 'Test text');

      const submitButton = screen.getByRole('button', { name: /submit/i });
      await user.click(submitButton);

      await waitFor(() => {
        expect(screen.getByText(/submission failed/i)).toBeInTheDocument();
      });
    });
  });

  describe('Rate Limiting', () => {
    it('displays remaining submissions count', () => {
      render(<TextInputForm {...defaultProps} remainingSubmissions={2} />);

      expect(screen.getByText(/2 submissions remaining/i)).toBeInTheDocument();
    });

    it('displays singular "submission" when count is 1', () => {
      render(<TextInputForm {...defaultProps} remainingSubmissions={1} />);

      expect(screen.getByText(/1 submission remaining/i)).toBeInTheDocument();
    });

    it('disables textarea when no submissions remaining', () => {
      render(<TextInputForm {...defaultProps} remainingSubmissions={0} />);

      const textarea = screen.getByPlaceholderText(/enter your response/i);
      expect(textarea).toBeDisabled();
    });

    it('disables submit button when no submissions remaining', () => {
      render(<TextInputForm {...defaultProps} remainingSubmissions={0} />);

      const submitButton = screen.getByRole('button', { name: /submit/i });
      expect(submitButton).toBeDisabled();
    });

    it('shows rate limit warning when no submissions remaining', () => {
      render(<TextInputForm {...defaultProps} remainingSubmissions={0} />);

      expect(screen.getByText(/you have reached the maximum number of submissions/i)).toBeInTheDocument();
    });

    it('does not show rate limit warning when submissions available', () => {
      render(<TextInputForm {...defaultProps} remainingSubmissions={1} />);

      expect(screen.queryByText(/you have reached the maximum/i)).not.toBeInTheDocument();
    });

    it('applies warning badge class when no submissions remaining', () => {
      render(<TextInputForm {...defaultProps} remainingSubmissions={0} />);

      const badge = screen.getByText(/0 submission/i);
      expect(badge).toHaveClass('badge-warning');
    });

    it('applies info badge class when submissions available', () => {
      render(<TextInputForm {...defaultProps} remainingSubmissions={2} />);

      const badge = screen.getByText(/2 submissions/i);
      expect(badge).toHaveClass('badge-info');
    });
  });

  describe('Initial Text', () => {
    it('loads initial text when provided', () => {
      render(<TextInputForm {...defaultProps} initialText="Previous submission" />);

      const textarea = screen.getByPlaceholderText(/enter your response/i);
      expect(textarea).toHaveValue('Previous submission');
    });

    it('updates text when initialText prop changes', () => {
      const { rerender } = render(<TextInputForm {...defaultProps} initialText="First text" />);

      let textarea = screen.getByPlaceholderText(/enter your response/i);
      expect(textarea).toHaveValue('First text');

      rerender(<TextInputForm {...defaultProps} initialText="Updated text" />);

      textarea = screen.getByPlaceholderText(/enter your response/i);
      expect(textarea).toHaveValue('Updated text');
    });

    it('displays character count for initial text', () => {
      render(<TextInputForm {...defaultProps} initialText="Initial text" />);

      expect(screen.getByText(/12 \/ 5000 characters/i)).toBeInTheDocument();
    });
  });

  describe('Textarea Interactions', () => {
    it('allows user to type in textarea', async () => {
      const user = userEvent.setup();
      render(<TextInputForm {...defaultProps} />);

      const textarea = screen.getByPlaceholderText(/enter your response/i);
      await user.type(textarea, 'User input');

      expect(textarea).toHaveValue('User input');
    });

    it('disables textarea during submission', async () => {
      const user = userEvent.setup();
      const onSubmit = vi.fn(() => new Promise(resolve => setTimeout(resolve, 100)));
      render(<TextInputForm {...defaultProps} onSubmit={onSubmit} />);

      const textarea = screen.getByPlaceholderText(/enter your response/i);
      await user.type(textarea, 'Test');

      const submitButton = screen.getByRole('button', { name: /submit/i });
      await user.click(submitButton);

      expect(textarea).toBeDisabled();
    });
  });

  describe('Edge Cases', () => {
    it('handles exactly 5000 characters', async () => {
      const user = userEvent.setup();
      render(<TextInputForm {...defaultProps} />);

      const textarea = screen.getByPlaceholderText(/enter your response/i);
      const exactText = 'a'.repeat(5000);
      fireEvent.change(textarea, { target: { value: exactText } });

      const submitButton = screen.getByRole('button', { name: /submit/i });
      expect(submitButton).not.toBeDisabled();

      expect(screen.queryByText(/text exceeds maximum length/i)).not.toBeInTheDocument();
    });

    it('handles multiline text', async () => {
      const user = userEvent.setup();
      render(<TextInputForm {...defaultProps} />);

      const textarea = screen.getByPlaceholderText(/enter your response/i);
      const multilineText = 'Line 1\nLine 2\nLine 3';
      await user.type(textarea, multilineText);

      expect(textarea).toHaveValue(multilineText);
    });

    it('handles special characters', async () => {
      const user = userEvent.setup();
      render(<TextInputForm {...defaultProps} />);

      const textarea = screen.getByPlaceholderText(/enter your response/i);
      const specialText = 'Test with @#$%^&*() symbols';
      await user.type(textarea, specialText);

      expect(textarea).toHaveValue(specialText);
    });

    it('handles unicode characters', async () => {
      const user = userEvent.setup();
      render(<TextInputForm {...defaultProps} />);

      const textarea = screen.getByPlaceholderText(/enter your response/i);
      const unicodeText = 'Test with emoji 😀 and accents éàü';
      await user.type(textarea, unicodeText);

      expect(textarea).toHaveValue(unicodeText);
    });
  });
});

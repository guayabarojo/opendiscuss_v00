import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useForm, useFieldArray } from 'react-hook-form';
import { useMutation } from '@tanstack/react-query';
import { discussionApi } from '../services/discussionApi';
import type { CreateDiscussionRequest } from '../types/api';
import './DiscussionCreate.css';

interface DiscussionFormData {
  community_id: string;
  total_rounds: number;
  questions: { text: string }[];
  timing_mode: 'SYNCHRONOUS' | 'ASYNCHRONOUS';
  round_duration_hours?: number;
  min_submissions_for_advance?: number;
  auto_advance_enabled: boolean;
}

/**
 * DiscussionCreate Component
 *
 * Form for creating a HOST_DEFINED mode discussion.
 * Allows host to specify:
 * - Community selection (dropdown)
 * - Questions (1-10 questions, each 10-200 characters)
 * - Total rounds
 *
 * Submits to POST /discussions API endpoint.
 * Redirects to live view on successful creation.
 */
export const DiscussionCreate: React.FC = () => {
  const navigate = useNavigate();
  const [apiError, setApiError] = useState<string | null>(null);

  // Mock communities - in production, fetch from communities API
  const communities = [
    { id: '00000000-0000-0000-0000-000000000001', name: 'General Discussion' },
    { id: '00000000-0000-0000-0000-000000000002', name: 'Technology' },
    { id: '00000000-0000-0000-0000-000000000003', name: 'Philosophy' },
    { id: '00000000-0000-0000-0000-000000000004', name: 'Science' },
  ];

  const {
    register,
    control,
    handleSubmit,
    formState: { errors },
    watch,
  } = useForm<DiscussionFormData>({
    defaultValues: {
      community_id: '',
      total_rounds: 3,
      questions: [{ text: '' }],
      timing_mode: 'SYNCHRONOUS',
      round_duration_hours: 24,
      min_submissions_for_advance: undefined,
      auto_advance_enabled: false,
    },
  });

  const { fields, append, remove } = useFieldArray({
    control,
    name: 'questions',
  });

  const questions = watch('questions');
  const timingMode = watch('timing_mode');

  // Mutation for creating discussion
  const createMutation = useMutation({
    mutationFn: async (data: CreateDiscussionRequest) => {
      return await discussionApi.createDiscussion(data);
    },
    onSuccess: (discussion) => {
      // Redirect to live view on success
      navigate(`/discussions/${discussion.discussion_id}/live`);
    },
    onError: (error: any) => {
      console.error('Create discussion error:', error);
      // Handle different error formats
      if (error?.message) {
        setApiError(error.message);
      } else if (error?.detail) {
        // Backend FastAPI error format
        if (typeof error.detail === 'string') {
          setApiError(error.detail);
        } else if (error.detail?.message) {
          setApiError(error.detail.message);
        } else {
          setApiError(JSON.stringify(error.detail));
        }
      } else if (typeof error === 'string') {
        setApiError(error);
      } else {
        setApiError('Failed to create discussion. Please check your inputs.');
      }
    },
  });

  const onSubmit = (data: DiscussionFormData) => {
    setApiError(null);

    // Transform form data to API request format
    const request: CreateDiscussionRequest = {
      community_id: data.community_id,
      mode: 'HOST_DEFINED',
      total_rounds: data.total_rounds,
      questions: data.questions.map((q) => q.text.trim()),
      timing_mode: data.timing_mode,
      round_duration_hours: data.timing_mode === 'ASYNCHRONOUS' ? data.round_duration_hours : undefined,
      min_submissions_for_advance: data.timing_mode === 'ASYNCHRONOUS' ? data.min_submissions_for_advance : undefined,
      auto_advance_enabled: data.timing_mode === 'ASYNCHRONOUS' ? data.auto_advance_enabled : false,
    };

    createMutation.mutate(request);
  };

  const addQuestion = () => {
    if (fields.length < 10) {
      append({ text: '' });
    }
  };

  const removeQuestion = (index: number) => {
    if (fields.length > 1) {
      remove(index);
    }
  };

  return (
    <div className="discussion-create-container">
      <div className="discussion-create-card">
        <h1 className="discussion-create-title">Create New Discussion</h1>
        <p className="discussion-create-subtitle">
          Set up a structured discussion with predefined questions
        </p>

        <form onSubmit={handleSubmit(onSubmit)} className="discussion-create-form">
          {/* Community Selection */}
          <div className="form-group">
            <label htmlFor="community_id" className="form-label">
              Community <span className="required">*</span>
            </label>
            <select
              id="community_id"
              {...register('community_id', {
                required: 'Please select a community',
              })}
              className={`form-select ${errors.community_id ? 'error' : ''}`}
            >
              <option value="">Select a community...</option>
              {communities.map((community) => (
                <option key={community.id} value={community.id}>
                  {community.name}
                </option>
              ))}
            </select>
            {errors.community_id && (
              <span className="error-message">{errors.community_id.message}</span>
            )}
          </div>

          {/* Total Rounds */}
          <div className="form-group">
            <label htmlFor="total_rounds" className="form-label">
              Total Rounds <span className="required">*</span>
            </label>
            <input
              id="total_rounds"
              type="number"
              {...register('total_rounds', {
                required: 'Total rounds is required',
                min: { value: 1, message: 'Minimum 1 round' },
                max: { value: 10, message: 'Maximum 10 rounds' },
                valueAsNumber: true,
              })}
              className={`form-input ${errors.total_rounds ? 'error' : ''}`}
            />
            {errors.total_rounds && (
              <span className="error-message">{errors.total_rounds.message}</span>
            )}
            <span className="form-hint">Recommended: 3-5 rounds for MVP</span>
          </div>

          {/* Timing Mode */}
          <div className="form-group">
            <label htmlFor="timing_mode" className="form-label">
              Discussion Type <span className="required">*</span>
            </label>
            <select
              id="timing_mode"
              {...register('timing_mode')}
              className="form-select"
            >
              <option value="SYNCHRONOUS">Live Discussion (Timed Rounds)</option>
              <option value="ASYNCHRONOUS">Async Discussion (Flexible)</option>
            </select>
            <span className="form-hint">
              {timingMode === 'SYNCHRONOUS'
                ? 'Strict time windows with automatic closures'
                : 'Flexible submission periods with manual control'}
            </span>
          </div>

          {/* Async Mode Settings */}
          {timingMode === 'ASYNCHRONOUS' && (
            <div className="async-settings">
              <div className="form-group">
                <label htmlFor="round_duration_hours" className="form-label">
                  Round Duration (hours)
                </label>
                <input
                  id="round_duration_hours"
                  type="number"
                  {...register('round_duration_hours', {
                    valueAsNumber: true,
                    min: { value: 1, message: 'Minimum 1 hour' },
                    max: { value: 168, message: 'Maximum 168 hours (1 week)' },
                  })}
                  className={`form-input ${errors.round_duration_hours ? 'error' : ''}`}
                  placeholder="24"
                />
                {errors.round_duration_hours && (
                  <span className="error-message">{errors.round_duration_hours.message}</span>
                )}
                <span className="form-hint">Soft deadline for each round (e.g., 24 hours)</span>
              </div>

              <div className="form-group">
                <label htmlFor="min_submissions_for_advance" className="form-label">
                  Minimum Submissions for Auto-Advance
                </label>
                <input
                  id="min_submissions_for_advance"
                  type="number"
                  {...register('min_submissions_for_advance', {
                    valueAsNumber: true,
                    min: { value: 1, message: 'Minimum 1 submission' },
                  })}
                  className={`form-input ${errors.min_submissions_for_advance ? 'error' : ''}`}
                  placeholder="Optional"
                />
                {errors.min_submissions_for_advance && (
                  <span className="error-message">{errors.min_submissions_for_advance.message}</span>
                )}
                <span className="form-hint">Leave empty for manual advance only</span>
              </div>

              <div className="form-group">
                <label className="checkbox-label">
                  <input
                    type="checkbox"
                    {...register('auto_advance_enabled')}
                  />
                  <span>Enable auto-advance when conditions met</span>
                </label>
                <span className="form-hint">
                  Automatically close round when minimum submissions reached
                </span>
              </div>
            </div>
          )}

          {/* Questions */}
          <div className="form-group">
            <label className="form-label">
              Discussion Questions <span className="required">*</span>
            </label>
            <p className="form-hint">
              Add 1-10 questions (10-200 characters each). These will be presented in order
              across rounds.
            </p>

            <div className="questions-list">
              {fields.map((field, index) => (
                <div key={field.id} className="question-item">
                  <div className="question-header">
                    <span className="question-number">Question {index + 1}</span>
                    {fields.length > 1 && (
                      <button
                        type="button"
                        onClick={() => removeQuestion(index)}
                        className="btn-remove"
                        aria-label={`Remove question ${index + 1}`}
                      >
                        Remove
                      </button>
                    )}
                  </div>
                  <textarea
                    {...register(`questions.${index}.text`, {
                      required: 'Question cannot be empty',
                      minLength: {
                        value: 10,
                        message: 'Question must be at least 10 characters',
                      },
                      maxLength: {
                        value: 200,
                        message: 'Question must not exceed 200 characters',
                      },
                    })}
                    className={`form-textarea ${
                      errors.questions?.[index]?.text ? 'error' : ''
                    }`}
                    placeholder="Enter your question here..."
                    rows={3}
                  />
                  <div className="question-footer">
                    {errors.questions?.[index]?.text && (
                      <span className="error-message">
                        {errors.questions[index].text?.message}
                      </span>
                    )}
                    <span
                      className={`char-count ${
                        questions[index]?.text.length > 200 ? 'error' : ''
                      }`}
                    >
                      {questions[index]?.text.length || 0} / 200
                    </span>
                  </div>
                </div>
              ))}
            </div>

            {fields.length < 10 && (
              <button type="button" onClick={addQuestion} className="btn-add-question">
                + Add Another Question
              </button>
            )}
          </div>

          {/* API Error Display */}
          {apiError && (
            <div className="alert alert-error" role="alert">
              <strong>Error:</strong> {typeof apiError === 'string' ? apiError : JSON.stringify(apiError)}
            </div>
          )}

          {/* Submit Buttons */}
          <div className="form-actions">
            <button
              type="button"
              onClick={() => navigate(-1)}
              className="btn btn-secondary"
              disabled={createMutation.isPending}
            >
              Cancel
            </button>
            <button
              type="submit"
              className="btn btn-primary"
              disabled={createMutation.isPending}
            >
              {createMutation.isPending ? 'Creating...' : 'Create Discussion'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
};

export default DiscussionCreate;

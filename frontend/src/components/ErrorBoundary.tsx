import React, { Component, ErrorInfo, ReactNode } from 'react';
import './ErrorBoundary.css';

/**
 * Error boundary props interface.
 */
interface ErrorBoundaryProps {
  /**
   * Child components to wrap with error boundary.
   */
  children: ReactNode;

  /**
   * Optional fallback UI to render on error.
   */
  fallback?: (error: Error, resetError: () => void) => ReactNode;

  /**
   * Optional callback when error occurs.
   */
  onError?: (error: Error, errorInfo: ErrorInfo) => void;

  /**
   * Enable error logging to backend (POST /errors endpoint).
   * Default: true
   */
  logToBackend?: boolean;
}

/**
 * Error boundary state interface.
 */
interface ErrorBoundaryState {
  hasError: boolean;
  error: Error | null;
  errorInfo: ErrorInfo | null;
}

/**
 * ErrorBoundary Component
 *
 * Catches React errors gracefully to prevent full app crashes.
 * Provides user-friendly error messages and retry/reset functionality.
 *
 * Features:
 * - Catches rendering errors in child components
 * - Displays user-friendly error UI
 * - Logs errors to backend (optional)
 * - Provides reset/retry functionality
 * - Preserves error details for debugging
 *
 * Constitutional Compliance:
 * - Ensures app remains usable during errors (Principle VI: Synchronous Deliberation)
 * - Maintains temporal context even during failures
 *
 * Task: T093 - Frontend error boundary
 *
 * @example
 * ```tsx
 * <ErrorBoundary>
 *   <DiscussionLive discussionId="..." />
 * </ErrorBoundary>
 * ```
 */
export class ErrorBoundary extends Component<ErrorBoundaryProps, ErrorBoundaryState> {
  constructor(props: ErrorBoundaryProps) {
    super(props);
    this.state = {
      hasError: false,
      error: null,
      errorInfo: null,
    };
  }

  /**
   * Static method called when error occurs during rendering.
   *
   * @param error - Error thrown
   * @returns Updated state
   */
  static getDerivedStateFromError(error: Error): Partial<ErrorBoundaryState> {
    return {
      hasError: true,
      error,
    };
  }

  /**
   * Lifecycle method called after error is caught.
   *
   * Logs error to console and optionally sends to backend.
   *
   * @param error - Error thrown
   * @param errorInfo - Component stack trace
   */
  componentDidCatch(error: Error, errorInfo: ErrorInfo): void {
    // Log to console for debugging
    console.error('ErrorBoundary caught error:', error);
    console.error('Component stack:', errorInfo.componentStack);

    // Store error info in state
    this.setState({
      errorInfo,
    });

    // Call optional error callback
    if (this.props.onError) {
      this.props.onError(error, errorInfo);
    }

    // Log to backend if enabled
    if (this.props.logToBackend !== false) {
      this.logErrorToBackend(error, errorInfo);
    }
  }

  /**
   * Logs error to backend POST /errors endpoint.
   *
   * Sends error details for monitoring and debugging.
   * Fails silently if backend is unreachable.
   *
   * @param error - Error thrown
   * @param errorInfo - Component stack trace
   */
  private async logErrorToBackend(error: Error, errorInfo: ErrorInfo): Promise<void> {
    try {
      const errorPayload = {
        error_type: 'react_error_boundary',
        error_message: error.message,
        error_stack: error.stack,
        component_stack: errorInfo.componentStack,
        timestamp: new Date().toISOString(),
        user_agent: navigator.userAgent,
        url: window.location.href,
      };

      await fetch('/api/v1/errors', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(errorPayload),
      });
    } catch (loggingError) {
      // Fail silently - don't crash app if logging fails
      console.warn('Failed to log error to backend:', loggingError);
    }
  }

  /**
   * Resets error boundary state to allow retry.
   *
   * Clears error and allows child components to re-render.
   */
  private resetError = (): void => {
    this.setState({
      hasError: false,
      error: null,
      errorInfo: null,
    });
  };

  /**
   * Renders error UI when error occurs, otherwise renders children.
   *
   * @returns React element
   */
  render(): ReactNode {
    if (this.state.hasError && this.state.error) {
      // Use custom fallback if provided
      if (this.props.fallback) {
        return this.props.fallback(this.state.error, this.resetError);
      }

      // Default error UI
      return (
        <div className="error-boundary">
          <div className="error-boundary__container">
            <div className="error-boundary__icon">⚠️</div>

            <h1 className="error-boundary__title">Something went wrong</h1>

            <p className="error-boundary__message">
              We encountered an unexpected error. This has been logged and our team will investigate.
            </p>

            <div className="error-boundary__details">
              <details>
                <summary>Error Details (for debugging)</summary>
                <div className="error-boundary__details-content">
                  <p>
                    <strong>Error:</strong> {this.state.error.message}
                  </p>
                  {this.state.error.stack && (
                    <pre className="error-boundary__stack">
                      {this.state.error.stack}
                    </pre>
                  )}
                  {this.state.errorInfo && (
                    <>
                      <p>
                        <strong>Component Stack:</strong>
                      </p>
                      <pre className="error-boundary__stack">
                        {this.state.errorInfo.componentStack}
                      </pre>
                    </>
                  )}
                </div>
              </details>
            </div>

            <div className="error-boundary__actions">
              <button
                className="error-boundary__button error-boundary__button--primary"
                onClick={this.resetError}
              >
                Try Again
              </button>
              <button
                className="error-boundary__button error-boundary__button--secondary"
                onClick={() => window.location.href = '/'}
              >
                Go to Home
              </button>
            </div>

            <p className="error-boundary__help">
              If this problem persists, please{' '}
              <a href="mailto:support@opendiscuss.example">contact support</a>.
            </p>
          </div>
        </div>
      );
    }

    return this.props.children;
  }
}

/**
 * Hook-based error boundary wrapper for functional components.
 *
 * @example
 * ```tsx
 * const ProtectedComponent = withErrorBoundary(MyComponent);
 * ```
 */
export function withErrorBoundary<P extends object>(
  Component: React.ComponentType<P>,
  errorBoundaryProps?: Omit<ErrorBoundaryProps, 'children'>
): React.FC<P> {
  const WrappedComponent: React.FC<P> = (props) => (
    <ErrorBoundary {...errorBoundaryProps}>
      <Component {...props} />
    </ErrorBoundary>
  );

  WrappedComponent.displayName = `withErrorBoundary(${Component.displayName || Component.name})`;

  return WrappedComponent;
}

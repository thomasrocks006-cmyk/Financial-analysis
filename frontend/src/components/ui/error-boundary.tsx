"use client";

import React from "react";
import { AlertTriangle } from "lucide-react";

interface ErrorBoundaryProps {
  children: React.ReactNode;
  fallback?: React.ReactNode;
}

interface ErrorBoundaryState {
  hasError: boolean;
  error: Error | null;
}

export class ErrorBoundary extends React.Component<
  ErrorBoundaryProps,
  ErrorBoundaryState
> {
  constructor(props: ErrorBoundaryProps) {
    super(props);
    this.state = { hasError: false, error: null };
  }

  static getDerivedStateFromError(error: Error): ErrorBoundaryState {
    return { hasError: true, error };
  }

  componentDidCatch(error: Error, info: React.ErrorInfo) {
    console.error("[ErrorBoundary] Caught:", error, info.componentStack);
  }

  handleReset = () => {
    this.setState({ hasError: false, error: null });
  };

  render() {
    if (this.state.hasError) {
      if (this.props.fallback) return this.props.fallback;

      return (
        <div className="flex min-h-[200px] flex-col items-center justify-center gap-4 rounded-xl border border-red-500/20 bg-red-500/5 p-8 text-center">
          <AlertTriangle className="h-8 w-8 text-red-400" />
          <div>
            <p className="text-sm font-semibold text-red-400">
              Something went wrong
            </p>
            <p className="mt-1 text-xs text-[var(--text-muted)]">
              {this.state.error?.message || "An unexpected error occurred."}
            </p>
          </div>
          <button
            onClick={this.handleReset}
            className="rounded-lg border border-red-500/30 px-4 py-1.5 text-xs text-red-400 hover:bg-red-500/10 transition-colors"
          >
            Try again
          </button>
        </div>
      );
    }

    return this.props.children;
  }
}

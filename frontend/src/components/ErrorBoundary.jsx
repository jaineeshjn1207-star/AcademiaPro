import React from 'react';
import { AlertTriangle, Home, RefreshCw } from 'lucide-react';

export default class ErrorBoundary extends React.Component {
  constructor(props) {
    super(props);
    this.state = { hasError: false, error: null };
  }

  static getDerivedStateFromError(error) {
    return { hasError: true, error };
  }

  componentDidCatch(error, info) {
    // Keep production UI friendly while still surfacing useful details in dev.
    if (import.meta.env.DEV) console.error('Unhandled UI error:', error, info);
  }

  render() {
    if (!this.state.hasError) return this.props.children;

    return (
      <div className="flex min-h-screen items-center justify-center bg-slate-50 dark:bg-slate-950 p-6">
        <div className="w-full max-w-lg rounded-3xl border border-rose-200 dark:border-rose-500 bg-white dark:bg-slate-900 p-8 text-center shadow-xl">
          <div className="mx-auto mb-4 flex h-16 w-16 items-center justify-center rounded-2xl bg-rose-100 dark:bg-rose-900/30 text-rose-600 dark:text-rose-300">
            <AlertTriangle className="h-8 w-8" />
          </div>
          <h1 className="text-2xl font-black text-slate-950 dark:text-white">Something went wrong</h1>
          <p className="mt-2 text-sm leading-relaxed text-slate-600 dark:text-slate-400">
            The page hit an unexpected error. Your session is still safe; refresh the page or return to the dashboard.
          </p>
          {import.meta.env.DEV && this.state.error?.message && (
            <pre className="mt-4 max-h-36 overflow-auto rounded-xl bg-slate-950 dark:bg-slate-800 p-3 text-left text-xs text-rose-200 dark:text-rose-100">
              {this.state.error.message}
            </pre>
          )}
          <div className="mt-6 flex flex-col gap-3 sm:flex-row sm:justify-center">
            <button
              type="button"
              onClick={() => window.location.reload()}
              className="inline-flex items-center justify-center gap-2 rounded-xl bg-blue-600 px-5 py-2.5 text-sm font-black text-white shadow transition hover:bg-blue-700"
            >
              <RefreshCw className="h-4 w-4" /> Refresh
            </button>
            <a
              href="/"
              className="inline-flex items-center justify-center gap-2 rounded-xl bg-slate-100 dark:bg-slate-800 px-5 py-2.5 text-sm font-bold text-slate-700 dark:text-slate-100 transition hover:bg-slate-200 dark:hover:bg-slate-700"
            >
              <Home className="h-4 w-4" /> Dashboard
            </a>
          </div>
        </div>
      </div>
    );
  }
}



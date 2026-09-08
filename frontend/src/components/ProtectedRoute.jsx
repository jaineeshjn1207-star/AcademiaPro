import React from 'react';
import { Navigate, useLocation, Link } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { ShieldAlert, ArrowLeft } from 'lucide-react';

export default function ProtectedRoute({ children, allowedRole }) {
  const { user } = useAuth();
  const location = useLocation();

  if (!user) {
    return <Navigate to="/login" state={{ from: location }} replace />;
  }

  const hasAllowedRole = !allowedRole || user.user_type === allowedRole || (allowedRole === 'faculty' && user.user_type === 'admin');

  if (!hasAllowedRole) {
    return (
      <div className="flex min-h-[80vh] items-center justify-center px-4 bg-slate-50 dark:bg-slate-950">
        <div className="w-full max-w-md rounded-2xl border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-900 p-8 text-center shadow-xl">
          <div className="mx-auto mb-4 flex h-16 w-16 items-center justify-center rounded-full bg-rose-100 dark:bg-rose-900/30 text-rose-600 dark:text-rose-300">
            <ShieldAlert className="h-8 w-8" />
          </div>
          <h2 className="mb-2 text-xl font-bold text-slate-800 dark:text-slate-100">Access Restricted</h2>
          <p className="mb-6 text-sm text-slate-600 dark:text-slate-400">
            This area is reserved for{' '}
            {allowedRole === 'admin' ? 'admins' : allowedRole === 'faculty' ? 'faculty/admin users' : 'student candidates'}. Your account is
            signed in as a {user.user_type}.
          </p>
          {/* Client-side navigation — a raw <a> would blow away the SPA state */}
          <Link
            to="/"
            className="inline-flex items-center gap-2 rounded-lg bg-blue-600 px-6 py-2.5 font-medium text-white transition hover:bg-blue-700"
          >
            <ArrowLeft className="h-4 w-4" /> Return to Dashboard
          </Link>
        </div>
      </div>
    );
  }

  return children;
}



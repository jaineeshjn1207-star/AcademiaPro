import React, { Suspense, lazy } from 'react';
import {
  BrowserRouter as Router, Routes, Route, Navigate, useLocation,
} from 'react-router-dom';
import { AuthProvider, useAuth } from './context/AuthContext';
import WorkspaceNav from './components/WorkspaceNav';
import ProtectedRoute from './components/ProtectedRoute';
import ErrorBoundary from './components/ErrorBoundary';
import { ToastProvider } from './components/ToastProvider';
import { ThemeProvider } from './context/ThemeContext';

// Lazily load page bundles for faster initial load.
const Login = lazy(() => import('./pages/Login'));
const StudentDashboard = lazy(() => import('./pages/StudentDashboard'));
const ExamRoom = lazy(() => import('./pages/ExamRoom'));
const ExamResult = lazy(() => import('./pages/ExamResult'));
const Analytics = lazy(() => import('./pages/Analytics'));
const Home = lazy(() => import('./pages/Home'));
const FacultyDashboard = lazy(() => import('./pages/FacultyDashboard'));
const CreateExam = lazy(() => import('./pages/CreateExam'));
const ManageExam = lazy(() => import('./pages/ManageExam'));
const FacultyNotes = lazy(() => import('./pages/FacultyNotes'));
const MyNotes = lazy(() => import('./pages/MyNotes'));
const Results = lazy(() => import('./pages/Results'));
const StudentAnalysis = lazy(() => import('./pages/StudentAnalysis'));
const AITutor = lazy(() => import('./pages/AITutor'));
const AdminDashboard = lazy(() => import('./pages/AdminDashboard'));
const Appeals = lazy(() => import('./pages/Appeals'));
const Insights = lazy(() => import('./pages/Insights'));
const PasswordReset = lazy(() => import('./pages/PasswordReset'));


function AppLoading() {
  return (
    <div className="flex min-h-screen items-center justify-center bg-slate-50 dark:bg-slate-950">
      <div className="rounded-3xl border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-900 px-6 py-5 text-center shadow-xl">
        <div className="mx-auto mb-3 h-10 w-10 animate-spin rounded-full border-4 border-blue-100 dark:border-slate-700 border-t-blue-600" />
        <p className="text-sm font-bold text-slate-600 dark:text-slate-300">Loading Academia Pro…</p>
      </div>
    </div>
  );
}

function HomeOrDashboard() {
  const { user } = useAuth();
  if (!user) return <Home />;
  if (user.user_type === 'admin') return <Navigate to="/admin" replace />;
  return user.user_type === 'faculty' ? <FacultyDashboard /> : <StudentDashboard />;
}

/**
 * Shell renders the persistent left sidebar around every page except the
 * login screen and the exam room (which must stay chrome-free and locked down).
 */
function Shell() {
  const location = useLocation();
  const { user } = useAuth();

  const isExamRoom = /^\/exam\/[^/]+\/room$/.test(location.pathname);
  const isLogin = location.pathname === '/login';
  const showSidebar = Boolean(user) && !isExamRoom && !isLogin;

  return (
    <div className={showSidebar ? 'workspace-frame' : 'min-h-screen'}>
      {showSidebar && <WorkspaceNav />}

      <main className={showSidebar ? 'workspace-main' : ''}>
        <Suspense fallback={<AppLoading />}><Routes>
          <Route path="/login" element={<Login />} />
          <Route path="/reset-password" element={<PasswordReset />} />
          <Route path="/insights" element={<ProtectedRoute><Insights /></ProtectedRoute>} />
          <Route path="/appeals" element={<ProtectedRoute><Appeals /></ProtectedRoute>} />
          <Route path="/" element={<HomeOrDashboard />} />

          {/* ---------- Notes ---------- */}
          <Route path="/notes" element={<ProtectedRoute><FacultyNotes /></ProtectedRoute>} />
          <Route
            path="/my-notes"
            element={<ProtectedRoute allowedRole="student"><MyNotes /></ProtectedRoute>}
          />
          <Route
            path="/faculty/notes"
            element={<ProtectedRoute allowedRole="faculty"><FacultyNotes /></ProtectedRoute>}
          />

          {/* ---------- Student exam ---------- */}
          <Route
            path="/exam/:examId/room"
            element={<ProtectedRoute allowedRole="student"><ExamRoom /></ProtectedRoute>}
          />
          <Route path="/exam/:examId/result" element={<ProtectedRoute><ExamResult /></ProtectedRoute>} />

          {/* ---------- Shared reporting ---------- */}
          <Route path="/results" element={<ProtectedRoute><Results /></ProtectedRoute>} />
          <Route path="/ai-tutor" element={<ProtectedRoute allowedRole="student"><AITutor /></ProtectedRoute>} />
          <Route path="/exam/:examId/analytics" element={<ProtectedRoute><Analytics /></ProtectedRoute>} />

          {/* ---------- Admin ---------- */}
          <Route path="/admin" element={<ProtectedRoute allowedRole="admin"><AdminDashboard /></ProtectedRoute>} />
          <Route path="/admin/users" element={<ProtectedRoute allowedRole="admin"><AdminDashboard section="users" /></ProtectedRoute>} />
          <Route path="/admin/security" element={<ProtectedRoute allowedRole="admin"><AdminDashboard section="security" /></ProtectedRoute>} />
          <Route path="/admin/audit" element={<ProtectedRoute allowedRole="admin"><AdminDashboard section="audit" /></ProtectedRoute>} />

          {/* ---------- Faculty ---------- */}
          <Route
            path="/faculty/create-exam"
            element={<ProtectedRoute allowedRole="faculty"><CreateExam /></ProtectedRoute>}
          />
          <Route
            path="/faculty/exam/:examId/manage"
            element={<ProtectedRoute allowedRole="faculty"><ManageExam /></ProtectedRoute>}
          />
          <Route
            path="/faculty/exam/:examId/otps"
            element={<ProtectedRoute allowedRole="faculty"><ManageExam /></ProtectedRoute>}
          />
          <Route
            path="/faculty/exam/:examId/live-status"
            element={<ProtectedRoute allowedRole="faculty"><ManageExam /></ProtectedRoute>}
          />
          <Route
            path="/faculty/exam/:examId/student/:studentId/analysis"
            element={<ProtectedRoute allowedRole="faculty"><StudentAnalysis /></ProtectedRoute>}
          />

          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes></Suspense>
      </main>
    </div>
  );
}

export default function App() {
  return (
    <ErrorBoundary>
      <ThemeProvider>
        <AuthProvider>
          <ToastProvider>
            <Router>
              <Shell />
            </Router>
          </ToastProvider>
        </AuthProvider>
      </ThemeProvider>
    </ErrorBoundary>
  );
}

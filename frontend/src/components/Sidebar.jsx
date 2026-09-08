import React, { useState, useEffect } from 'react';
import { NavLink, useNavigate, useLocation } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import {
  BookOpen, LogOut, BarChart2, LayoutDashboard, FileText,
  Settings, ChevronLeft, ChevronRight, Menu, X, ShieldCheck,
  GraduationCap, NotebookPen,
} from 'lucide-react';

/**
 * Persistent left sidebar navigation.
 * - Collapsible on desktop (state persisted in localStorage)
 * - Slide-over drawer on mobile
 * - Automatically hidden inside the secure exam room
 */
export default function Sidebar() {
  const { user, activeExam, logout } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();

  const [collapsed, setCollapsed] = useState(
    () => localStorage.getItem('sidebar_collapsed') === 'true'
  );
  const [mobileOpen, setMobileOpen] = useState(false);

  useEffect(() => {
    localStorage.setItem('sidebar_collapsed', String(collapsed));
  }, [collapsed]);

  // Close the mobile drawer whenever the route changes
  useEffect(() => {
    setMobileOpen(false);
  }, [location.pathname]);

  if (!user) return null;

  const isFaculty = user.user_type === 'faculty';
  const routeExamId = location.pathname.match(/(?:\/faculty)?\/exam\/(\d+)/)?.[1];
  const examId = routeExamId || activeExam?.id;

  const handleLogout = () => {
    logout();
    navigate('/login');
  };

  const studentLinks = [
    { to: '/', icon: LayoutDashboard, label: 'Dashboard', end: true },
    { to: '/notes', icon: BookOpen, label: 'Faculty Notes' },
    { to: '/my-notes', icon: NotebookPen, label: 'My Notes' },
    { to: '/results', icon: FileText, label: 'All Exams' },
    ...(examId
      ? [{ to: `/exam/${examId}/analytics`, icon: BarChart2, label: 'Marks Analysis' }]
      : []),
  ];

  const facultyLinks = [
    { to: '/', icon: LayoutDashboard, label: 'Dashboard', end: true },
    { to: '/faculty/create-exam', icon: Settings, label: 'Exam Settings' },
    { to: '/faculty/notes', icon: BookOpen, label: 'Manage Notes' },
    { to: '/results', icon: FileText, label: 'Results Center' },
    ...(examId
      ? [
          { to: `/faculty/exam/${examId}/manage`, icon: Settings, label: 'Questions & Publish' },
          { to: `/exam/${examId}/analytics`, icon: BarChart2, label: 'Analytics' },
        ]
      : []),
  ];

  const links = isFaculty ? facultyLinks : studentLinks;

  const linkClass = ({ isActive }) =>
    [
      'group relative flex items-center gap-3 rounded-xl px-3 py-2.5 text-sm font-medium transition-all',
      collapsed ? 'justify-center' : '',
      isActive
        ? 'bg-gradient-to-r from-blue-600 to-indigo-600 text-white shadow-lg shadow-blue-600/20'
        : 'text-slate-400 hover:bg-slate-800/80 hover:text-white',
    ].join(' ');

  const SidebarBody = (
    <div className="flex h-full flex-col border-r border-slate-800 bg-slate-950 bg-[radial-gradient(circle_at_top_left,rgba(37,99,235,0.18),transparent_16rem)]">
      {/* Brand */}
      <div className={`flex items-center gap-2.5 border-b border-slate-800 px-4 ${collapsed ? 'justify-center' : ''} h-16 flex-shrink-0`}>
        <div className="flex h-9 w-9 flex-shrink-0 items-center justify-center rounded-xl bg-gradient-to-br from-blue-500 to-indigo-600 text-white">
          <GraduationCap className="h-5 w-5" />
        </div>
        {!collapsed && (
          <div className="min-w-0">
            <div className="truncate text-sm font-bold tracking-tight text-white">
              ExamVault <span className="text-blue-400">Pro</span>
            </div>
            <div className="truncate text-[10px] uppercase tracking-wider text-slate-500">
              Exam Portal
            </div>
          </div>
        )}
      </div>

      {/* Role badge */}
      {!collapsed && (
        <div className="px-4 pt-4">
          <div
            className={`flex items-center gap-2 rounded-xl border px-3 py-2 text-[11px] font-semibold uppercase tracking-wide ${
              isFaculty
                ? 'border-amber-500/25 bg-amber-500/10 text-amber-300'
                : 'border-emerald-500/25 bg-emerald-500/10 text-emerald-300'
            }`}
          >
            <ShieldCheck className="h-3.5 w-3.5 flex-shrink-0" />
            <span className="truncate">{isFaculty ? 'Faculty Portal' : 'Student Portal'}</span>
          </div>
        </div>
      )}

      {/* Navigation */}
      <nav className="flex-1 space-y-1 overflow-y-auto px-3 py-4">
        {!collapsed && (
          <div className="px-3 pb-2 text-[10px] font-bold uppercase tracking-widest text-slate-600">
            Menu
          </div>
        )}
        {links.map(({ to, icon: Icon, label, end }) => (
          <NavLink key={to} to={to} end={end} className={linkClass} title={collapsed ? label : undefined}>
            <Icon className="h-4.5 w-4.5 flex-shrink-0" style={{ width: 18, height: 18 }} />
            {!collapsed && <span className="truncate">{label}</span>}
            {collapsed && (
              <span className="pointer-events-none absolute left-full z-50 ml-3 whitespace-nowrap rounded-lg bg-slate-800 px-2.5 py-1.5 text-xs font-medium text-white opacity-0 shadow-xl transition-opacity group-hover:opacity-100">
                {label}
              </span>
            )}
          </NavLink>
        ))}

        {/* Active exam context card */}
        {!collapsed && activeExam && (
          <div className="mt-6 rounded-xl border border-slate-800 bg-slate-900/60 p-3">
            <div className="mb-1 flex items-center gap-1.5 text-[10px] font-bold uppercase tracking-wider text-slate-500">
              <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-emerald-400" />
              Current Exam
            </div>
            <div className="line-clamp-2 text-xs font-semibold leading-snug text-slate-200">
              {routeExamId && String(activeExam?.id) !== String(routeExamId) ? `Exam #${routeExamId}` : activeExam.title}
            </div>
          </div>
        )}
      </nav>

      {/* User footer */}
      <div className="flex-shrink-0 border-t border-slate-800 p-3">
        <div className={`mb-2 flex items-center gap-3 rounded-xl px-2 py-2 ${collapsed ? 'justify-center' : ''}`}>
          <div className="flex h-9 w-9 flex-shrink-0 items-center justify-center rounded-full bg-gradient-to-br from-blue-500 via-indigo-500 to-violet-600 text-xs font-bold text-white">
            {(user.name || 'U').slice(0, 2).toUpperCase()}
          </div>
          {!collapsed && (
            <div className="min-w-0 flex-1">
              <div className="truncate text-xs font-semibold text-slate-100">{user.name}</div>
              <div className="truncate font-mono text-[10px] text-slate-500">
                {user.enrollment_no || user.username}
              </div>
            </div>
          )}
        </div>

        <button
          onClick={handleLogout}
          title="Sign out"
          className={`flex w-full items-center gap-2 rounded-xl border border-rose-500/20 bg-rose-500/10 px-3 py-2 text-xs font-semibold text-rose-300 transition hover:bg-rose-600 hover:text-white ${
            collapsed ? 'justify-center' : ''
          }`}
        >
          <LogOut className="h-4 w-4 flex-shrink-0" />
          {!collapsed && <span>Logout</span>}
        </button>

        {/* Collapse toggle (desktop only) */}
        <button
          onClick={() => setCollapsed((c) => !c)}
          className="mt-2 hidden w-full items-center justify-center gap-1.5 rounded-xl px-3 py-2 text-[11px] font-medium text-slate-500 transition hover:bg-slate-800 hover:text-slate-300 lg:flex"
        >
          {collapsed ? <ChevronRight className="h-3.5 w-3.5" /> : <ChevronLeft className="h-3.5 w-3.5" />}
          {!collapsed && <span>{collapsed ? '' : 'Collapse'}</span>}
        </button>
      </div>
    </div>
  );

  return (
    <>
      {/* Mobile top bar */}
      <div className="sticky top-0 z-40 flex h-14 items-center justify-between border-b border-slate-800 bg-slate-950 px-4 lg:hidden">
        <button
          onClick={() => setMobileOpen(true)}
          className="rounded-lg p-2 text-slate-300 transition hover:bg-slate-800"
          aria-label="Open navigation"
        >
          <Menu className="h-5 w-5" />
        </button>
        <div className="flex items-center gap-2 text-sm font-bold text-white">
          <GraduationCap className="h-4 w-4 text-blue-400" />
          ExamVault<span className="-ml-1 text-blue-400"> Pro</span>
        </div>
        <div className="flex h-8 w-8 items-center justify-center rounded-full bg-blue-600 text-[10px] font-bold text-white">
          {(user.name || 'U').slice(0, 2).toUpperCase()}
        </div>
      </div>

      {/* Mobile drawer */}
      {mobileOpen && (
        <div className="fixed inset-0 z-50 lg:hidden">
          <div
            className="absolute inset-0 bg-black/60 backdrop-blur-sm"
            onClick={() => setMobileOpen(false)}
          />
          <div className="absolute left-0 top-0 h-full w-64 shadow-2xl">
            <button
              onClick={() => setMobileOpen(false)}
              className="absolute -right-11 top-3 rounded-lg bg-slate-800 p-2 text-white"
              aria-label="Close navigation"
            >
              <X className="h-5 w-5" />
            </button>
            {SidebarBody}
          </div>
        </div>
      )}

      {/* Desktop sidebar */}
      <aside
        className={`hidden flex-shrink-0 transition-all duration-200 lg:block ${
          collapsed ? 'w-[76px]' : 'w-64'
        }`}
      >
        <div className={`fixed inset-y-0 left-0 ${collapsed ? 'w-[76px]' : 'w-64'} transition-all duration-200`}>
          {SidebarBody}
        </div>
      </aside>
    </>
  );
}

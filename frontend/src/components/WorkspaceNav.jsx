import React, { useEffect, useState } from 'react';
import { NavLink, useLocation, useNavigate } from 'react-router-dom';
import {
  BarChart3, BookOpen, Bot, ChevronDown, ClipboardList, FileText, GraduationCap,
  LayoutDashboard, LogOut, Menu, Moon, NotebookPen, Plus, ShieldAlert, Sun, X,
} from 'lucide-react';
import { useAuth } from '../context/AuthContext';
import { useTheme } from '../context/ThemeContext';
import NotificationBell from './NotificationBell';

const studentPrimaryLinks = [
  { to: '/', label: 'Overview', icon: LayoutDashboard, end: true },
  { to: '/results', label: 'Results', icon: FileText },
  { to: '/ai-tutor', label: 'Tutor', icon: Bot },
];
const studentMoreLinks = [
  { to: '/notes', label: 'Library', icon: BookOpen },
  { to: '/my-notes', label: 'Notebook', icon: NotebookPen },
  { to: '/appeals', label: 'Tickets', icon: ClipboardList },
];

const facultyPrimaryLinks = [
  { to: '/', label: 'Overview', icon: LayoutDashboard, end: true },
  { to: '/faculty/create-exam', label: 'New assessment', icon: Plus },
  { to: '/results', label: 'Results', icon: FileText },
];
const facultyMoreLinks = [
  { to: '/appeals', label: 'Tickets', icon: ClipboardList },
  { to: '/faculty/notes', label: 'Materials', icon: BookOpen },
];

const adminPrimaryLinks = [
  { to: '/admin', label: 'Overview', icon: ShieldAlert, end: true },
  { to: '/admin/users', label: 'Users', icon: GraduationCap },
  { to: '/admin/security', label: 'Security', icon: ClipboardList },
  { to: '/admin/audit', label: 'Audit log', icon: FileText },
];
const adminMoreLinks = [];

function Initials({ name }) {
  return <span className="workspace-avatar" aria-hidden="true">{(name || 'U').split(/\s+/).slice(0, 2).map((part) => part[0]).join('').toUpperCase()}</span>;
}

export default function WorkspaceNav() {
  const { user, activeExam, logout } = useAuth();
  const { theme, toggleTheme } = useTheme();
  const navigate = useNavigate();
  const location = useLocation();
  const [menuOpen, setMenuOpen] = useState(false);
  const [mobileOpen, setMobileOpen] = useState(false);
  const isAdmin = user?.user_type === 'admin';
  const isFaculty = user?.user_type === 'faculty';
  const primaryLinks = isAdmin ? adminPrimaryLinks : (isFaculty ? facultyPrimaryLinks : studentPrimaryLinks);
  const moreLinks = isAdmin ? adminMoreLinks : (isFaculty ? facultyMoreLinks : studentMoreLinks);
  const links = [...primaryLinks, ...moreLinks];

  useEffect(() => {
    setMobileOpen(false);
    setMenuOpen(false);
  }, [location.pathname]);

  const signOut = () => {
    logout();
    navigate('/login');
  };

  const routeExamId = location.pathname.match(/(?:\/faculty)?\/exam\/(\d+)/)?.[1];
  const showAnalytics = routeExamId || activeExam?.id;

  return (
    <>
      <header className="workspace-nav">
        <NavLink to="/" className="workspace-brand" aria-label="Academia Pro home">
          <span className="workspace-brand-mark"><GraduationCap size={18} strokeWidth={2.4} /></span>
          <span><strong>Academia Pro</strong><small>assessment studio</small></span>
        </NavLink>

        <nav className="workspace-links" aria-label="Primary navigation">
          {links.map(({ to, label, icon: Icon, end }) => (
            <NavLink key={to} to={to} end={end} className={({ isActive }) => `workspace-link${isActive ? ' is-active' : ''}`}>
              <Icon size={16} /> <span>{label}</span>
            </NavLink>
          ))}
          <NavLink to="/insights" className={({ isActive }) => `workspace-link${isActive ? ' is-active' : ''}`}>
              <BarChart3 size={16} /> <span>Insights</span>
          </NavLink>
        </nav>

        <div className="workspace-tools">
          <NotificationBell />
          <button type="button" className="workspace-icon-button" onClick={toggleTheme} aria-label={`Switch to ${theme === 'dark' ? 'light' : 'dark'} mode`} title="Toggle colour mode">
            {theme === 'dark' ? <Sun size={18} /> : <Moon size={18} />}
          </button>
          <div className="workspace-account">
            <button type="button" className="workspace-account-trigger" onClick={() => setMenuOpen((open) => !open)} aria-expanded={menuOpen} aria-haspopup="menu">
              <Initials name={user?.name} />
              <span className="workspace-account-name"><strong>{user?.name}</strong><small>{isAdmin ? 'Admin' : isFaculty ? 'Faculty' : user?.enrollment_no || 'Student'}</small></span>
              <ChevronDown size={15} />
            </button>
            {menuOpen && (
              <div className="workspace-popover" role="menu">
                <div className="workspace-popover-head"><Initials name={user?.name} /><div><strong>{user?.name}</strong><small>{user?.branch ? `${user.branch} branch` : (isAdmin ? 'Admin account' : isFaculty ? 'Faculty account' : 'Student account')}</small></div></div>
                <button type="button" role="menuitem" onClick={toggleTheme}>{theme === 'dark' ? <Sun size={16} /> : <Moon size={16} />} Use {theme === 'dark' ? 'light' : 'dark'} mode</button>
                <button type="button" className="is-danger" role="menuitem" onClick={signOut}><LogOut size={16} /> Sign out</button>
              </div>
            )}
          </div>
          <button type="button" className="workspace-menu-button" onClick={() => setMobileOpen(true)} aria-label="Open navigation"><Menu size={21} /></button>
        </div>
      </header>

      {mobileOpen && (
        <div className="workspace-mobile-overlay" role="dialog" aria-modal="true" aria-label="Navigation">
          <button type="button" className="workspace-scrim" onClick={() => setMobileOpen(false)} aria-label="Close navigation" />
          <div className="workspace-mobile-panel">
            <div className="workspace-mobile-head"><span>Navigate</span><button type="button" onClick={() => setMobileOpen(false)} aria-label="Close navigation"><X size={20} /></button></div>
            <div className="workspace-mobile-user"><Initials name={user?.name} /><div><strong>{user?.name}</strong><small>{isAdmin ? 'Admin workspace' : isFaculty ? 'Faculty workspace' : 'Student workspace'}</small></div></div>
            <nav aria-label="Mobile navigation">{links.map(({ to, label, icon: Icon, end }) => <NavLink key={to} to={to} end={end} className={({ isActive }) => `workspace-mobile-link${isActive ? ' is-active' : ''}`}><Icon size={18} />{label}</NavLink>)}<NavLink to="/insights" className="workspace-mobile-link"><BarChart3 size={18} />Insights</NavLink></nav>
            <div className="workspace-mobile-actions"><button type="button" onClick={toggleTheme}>{theme === 'dark' ? <Sun size={17} /> : <Moon size={17} />} Appearance</button><button type="button" onClick={signOut}><LogOut size={17} /> Sign out</button></div>
          </div>
        </div>
      )}

      <nav className="workspace-dock" aria-label="Quick navigation">
        {links.slice(0, 5).map(({ to, label, icon: Icon, end }) => <NavLink key={to} to={to} end={end} className={({ isActive }) => `workspace-dock-link${isActive ? ' is-active' : ''}`}><Icon size={18} /><span>{label}</span></NavLink>)}
      </nav>
    </>
  );
}

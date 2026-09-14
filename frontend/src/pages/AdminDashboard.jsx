import React, { useEffect, useState } from 'react';
import {
  AlertTriangle, BarChart3, ChevronLeft, ChevronRight, Copy, Eye,
  GraduationCap, KeyRound, Pencil, RefreshCw, ShieldAlert, Trash2, Unlock, UserPlus, Users,
} from 'lucide-react';
import api from '../api/axios';
import './faculty-tools.css';

const BRANCHES = ['CE', 'IT', 'AIML', 'ME', 'EC'];
const emptyForm = { user_type: 'student', username: '', password: '', name: '', email: '', branch: '', enrollment_no: '', faculty_subjects: '' };

export default function AdminDashboard({ section = 'overview' }) {
  const [overview, setOverview] = useState(null);
  const [users, setUsers] = useState([]);
  const [role, setRole] = useState('student');
  const [form, setForm] = useState(emptyForm);
  const [message, setMessage] = useState('');
  const [tempCredential, setTempCredential] = useState(null);
  const [unblockingId, setUnblockingId] = useState(null);
  const [editingUser, setEditingUser] = useState(null);

  // Proctor & academic-integrity reports (admin-only).
  const [exams, setExams] = useState([]);
  const [examId, setExamId] = useState('');
  const [proctorReport, setProctorReport] = useState([]);
  const [proctorLoading, setProctorLoading] = useState(false);
  const [expandedSession, setExpandedSession] = useState(null);

  // Full, paginated audit log (admin-only).
  const [auditLogs, setAuditLogs] = useState([]);
  const [auditPage, setAuditPage] = useState({ page: 1, page_count: 1, has_next: false, has_previous: false });
  const [auditActionFilter, setAuditActionFilter] = useState('');
  const [auditLoading, setAuditLoading] = useState(false);

  const load = async () => {
    try {
      const [o, u, e] = await Promise.all([
        api.get('admin/overview/'),
        api.get('admin/users/', { params: { role } }),
        api.get('exams/'),
      ]);
      setOverview(o.data);
      setUsers(u.data.users || []);
      const examList = Array.isArray(e.data) ? e.data : e.data.results || [];
      setExams(examList);
      setExamId((current) => current || String(examList[0]?.id || ''));
    } catch (e) {
      setMessage(e.response?.data?.error || 'Could not load admin panel.');
    }
  };
  useEffect(() => { load(); /* eslint-disable-next-line */ }, [role]);

  const loadAuditLogs = async (page = 1) => {
    setAuditLoading(true);
    try {
      const params = { page };
      if (auditActionFilter.trim()) params.action = auditActionFilter.trim();
      const res = await api.get('audit-logs/', { params });
      setAuditLogs(res.data.logs || []);
      setAuditPage({
        page: res.data.page, page_count: res.data.page_count,
        has_next: res.data.has_next, has_previous: res.data.has_previous,
      });
    } catch (e) {
      setMessage(e.response?.data?.error || 'Could not load the audit log.');
    } finally {
      setAuditLoading(false);
    }
  };
  useEffect(() => { loadAuditLogs(1); /* eslint-disable-next-line */ }, []);

  const loadProctorReport = async (id) => {
    const targetId = id || examId;
    if (!targetId) return;
    setProctorLoading(true);
    try {
      const res = await api.get(`exams/${targetId}/proctor-report/`);
      setProctorReport(res.data.report || []);
    } catch (e) {
      setMessage(e.response?.data?.error || 'Could not load the proctor report.');
      setProctorReport([]);
    } finally {
      setProctorLoading(false);
    }
  };

  const resetPassword = async (userId) => {
    try {
      const res = await api.post(`admin/users/${userId}/reset-password/`, {});
      const credential = { username: res.data.username, temp_password: res.data.temp_password };
      await load();
      setTempCredential(credential);
      setMessage('Temporary password generated. Copy it now and share it securely with the user.');
    } catch (e) {
      setMessage(e.response?.data?.error || 'Could not reset password.');
    }
  };

  const copyTempPassword = async () => {
    if (!tempCredential?.temp_password) return;
    try {
      await navigator.clipboard.writeText(tempCredential.temp_password);
      setMessage('Temporary password copied to clipboard.');
    } catch {
      setMessage('Could not copy automatically. Select and copy the password manually.');
    }
  };

  const createUser = async (event) => {
    event.preventDefault();
    try {
      await api.post('admin/users/', form);
      setTempCredential({ username: form.username, temp_password: form.password });
      setForm({ ...emptyForm, user_type: form.user_type });
      setMessage('User created with a temporary password. The user must create a permanent password on first login.');
      load();
    } catch (e) {
      setMessage(e.response?.data?.error || 'Could not create user.');
    }
  };

  const unblockStudent = async (studentId) => {
    if (unblockingId) return;
    setUnblockingId(studentId);
    try {
      await api.post(`students/${studentId}/unblock/`);
      setMessage('Student access restored. They can sign in again.');
      load();
    } catch (e) {
      setMessage(e.response?.data?.error || 'Could not unblock this student.');
    } finally {
      setUnblockingId(null);
    }
  };

  const saveUser = async (event) => {
    event.preventDefault();
    try {
      await api.patch(`admin/users/${editingUser.id}/`, editingUser);
      setEditingUser(null);
      setMessage('User details updated.');
      load();
    } catch (e) {
      setMessage(e.response?.data?.error || 'Could not update user.');
    }
  };

  const deleteUser = async (user) => {
    if (!window.confirm(`Delete ${user.name || user.username}? This cannot be undone.`)) return;
    try {
      await api.delete(`admin/users/${user.id}/`);
      setMessage('User deleted.');
      load();
    } catch (e) {
      setMessage(e.response?.data?.error || 'Could not delete user.');
    }
  };

  const refreshAll = () => { load(); loadAuditLogs(auditPage.page); if (examId) loadProctorReport(examId); };

  const counts = overview?.counts || {};

  return (
    <section className={`app-page faculty-tools-page admin-section-${section}`}>
      <header className="page-heading">
        <div>
          <p className="eyebrow">Platform admin</p>
          <h1>Admin control panel</h1>
          <p>Security, users, blocked accounts, proctoring oversight and audit activity — kept separate from faculty tools.</p>
        </div>
        <button className="button button-secondary" onClick={refreshAll}><RefreshCw size={16} /> Refresh</button>
      </header>

      {message && <div className="tool-message" role="status">{message}</div>}
      {tempCredential && (
        <div className="tool-message admin-temp-password" role="status">
          <div>
            <strong>Temporary password for {tempCredential.username}</strong>
            <p>This password is shown here only for the admin to copy. The user must create a permanent password before portal access.</p>
            <code>{tempCredential.temp_password}</code>
          </div>
          <button type="button" className="button button-secondary" onClick={copyTempPassword}><Copy size={16} /> Copy</button>
        </div>
      )}

      <div className="faculty-tools-grid">
        <article className="tool-panel">
          <div className="tool-panel__head">
            <span className="tool-icon"><BarChart3 /></span>
            <div><h2>Platform summary</h2><p>Common admin metrics.</p></div>
          </div>
          <div className="tool-list">
            {[
              ['Students', counts.students], ['Faculty', counts.faculty], ['Admins', counts.admins],
              ['Exams', counts.exams], ['Blocked students', counts.blocked_students],
              ['Open appeals', counts.open_appeals], ['Proctor events', counts.proctor_events],
            ].map(([k, v]) => (
              <div key={k}><span><GraduationCap size={16} /></span><p><strong>{v ?? 0}</strong><small>{k}</small></p></div>
            ))}
          </div>
        </article>

        <article className="tool-panel">
          <div className="tool-panel__head">
            <span className="tool-icon tool-icon--rose"><AlertTriangle /></span>
            <div><h2>Blocked students</h2><p>Accounts locked by UFM/proctoring. Restoring access is an admin-only action.</p></div>
          </div>
          <div className="tool-list">
            {overview?.blocked_students?.length ? overview.blocked_students.map((u) => (
              <div key={u.id}>
                <span><AlertTriangle size={16} /></span>
                <p><strong>{u.name || u.username}</strong><small>{u.enrollment_no || u.username} · {u.blocked_reason || 'Blocked'}</small></p>
                <button type="button" className="text-button" disabled={unblockingId === u.id} onClick={() => unblockStudent(u.id)}>
                  <Unlock size={14} /> {unblockingId === u.id ? 'Restoring…' : 'Unblock'}
                </button>
              </div>
            )) : <p className="tool-empty">No blocked students.</p>}
          </div>
        </article>

        <article className="tool-panel">
          <div className="tool-panel__head">
            <span className="tool-icon tool-icon--mint"><UserPlus /></span>
            <div><h2>Create user</h2><p>Add a student, faculty or admin account.</p></div>
          </div>
          <form className="tool-form tool-form--stack" onSubmit={createUser}>
            <select value={form.user_type} onChange={(e) => setForm((f) => ({ ...f, user_type: e.target.value }))}>
              <option value="student">Student</option>
              <option value="faculty">Faculty</option>
              <option value="admin">Admin</option>
            </select>
            <input value={form.username} onChange={(e) => setForm((f) => ({ ...f, username: e.target.value }))} placeholder="Username" required />
            <input type="password" value={form.password} onChange={(e) => setForm((f) => ({ ...f, password: e.target.value }))} placeholder="Temporary password" required />
            <input value={form.name} onChange={(e) => setForm((f) => ({ ...f, name: e.target.value }))} placeholder="Full name" />
            <input value={form.email} onChange={(e) => setForm((f) => ({ ...f, email: e.target.value }))} placeholder="Email" />
            {form.user_type === 'student' && (
              <input value={form.enrollment_no} onChange={(e) => setForm((f) => ({ ...f, enrollment_no: e.target.value }))} placeholder="Enrollment no" />
            )}
            {['student', 'faculty'].includes(form.user_type) && <select value={form.branch} onChange={(e) => setForm((f) => ({ ...f, branch: e.target.value }))} required>
              <option value="">Branch</option>
              {BRANCHES.map((branch) => <option key={branch} value={branch}>{branch}</option>)}
            </select>}
            
          {form.user_type === 'faculty' && <select value={form.faculty_subjects} onChange={(e) => setForm((f) => ({ ...f, faculty_subjects: e.target.value }))} required>
            <option value="">Subject</option>
              <option value="Python">Python</option>
              <option value="Java">Java</option>
              <option value="C++">C++</option>
              <option value="JavaScript">JavaScript</option>
            </select>}
            <button className="button" type="submit"><UserPlus size={16} /> Create user</button>
          </form>
        </article>

        <article className="tool-panel">
          <div className="tool-panel__head">
            <span className="tool-icon tool-icon--rose"><ShieldAlert /></span>
            <div><h2>Proctor reports</h2><p>Anti-cheat violations per assessment. Admin-only — no longer visible to faculty.</p></div>
          </div>
          <select
            className="tool-select"
            value={examId}
            onChange={(e) => { setExamId(e.target.value); loadProctorReport(e.target.value); }}
          >
            <option value="">Choose an assessment…</option>
            {exams.map((exam) => <option key={exam.id} value={exam.id}>{exam.title}</option>)}
          </select>
          {proctorLoading ? (
            <p className="tool-empty">Loading proctor report…</p>
          ) : proctorReport.length === 0 ? (
            <p className="tool-empty">{examId ? 'No proctoring data for this assessment yet.' : 'Pick an assessment to view its proctor report.'}</p>
          ) : (
            <div className="tool-list">
              {proctorReport.map((r) => (
                <div key={r.session_id} style={{ flexDirection: 'column', alignItems: 'stretch' }}>
                  <p>
                    <strong>{r.student_name}</strong>
                    <small>{r.enrollment_no} · {r.status} · {r.violation_count} violation{r.violation_count === 1 ? '' : 's'}{r.is_auto_submitted ? ' · auto-submitted' : ''}</small>
                  </p>
                  {(r.events.length > 0 || (r.recordings || []).length > 0) && (
                    <button
                      type="button"
                      className="text-button"
                      style={{ marginLeft: 0, justifySelf: 'start' }}
                      onClick={() => setExpandedSession(expandedSession === r.session_id ? null : r.session_id)}
                    >
                      <Eye size={14} /> {expandedSession === r.session_id ? 'Hide details' : `View ${r.events.length} event(s)`}
                    </button>
                  )}
                  {expandedSession === r.session_id && (
                    <div className="tool-list" style={{ marginTop: 6 }}>
                      {(r.recordings || []).map((rec) => (
                        <div key={rec.id}><span><Eye size={14} /></span><p><a href={rec.clip_url} target="_blank" rel="noreferrer">{rec.event_type} clip</a><small>{new Date(rec.created_at).toLocaleString()}</small></p></div>
                      ))}
                      {r.events.map((ev) => (
                        <div key={ev.id}><span><AlertTriangle size={14} /></span><p><strong>{ev.event_type}</strong><small>{ev.severity} · {ev.details} · {new Date(ev.created_at).toLocaleString()}</small></p></div>
                      ))}
                    </div>
                  )}
                </div>
              ))}
            </div>
          )}
        </article>
      </div>

      <article className="tool-panel tool-panel--wide">
        <div className="tool-panel__head">
          <span className="tool-icon"><Users /></span>
          <div><h2>User directory</h2><p>Switch role filter to review accounts. Reset generates a temporary password and marks the user as needing password creation.</p></div>
        </div>
        <select className="tool-select" value={role} onChange={(e) => setRole(e.target.value)}>
          <option value="student">Students</option>
          <option value="faculty">Faculty</option>
          <option value="admin">Admins</option>
        </select>
        {editingUser && (
          <form className="tool-form tool-form--stack" onSubmit={saveUser} style={{ marginBottom: 16 }}>
            <input value={editingUser.username} onChange={(e) => setEditingUser((u) => ({ ...u, username: e.target.value }))} placeholder="Username" required />
            <input value={editingUser.name || ''} onChange={(e) => setEditingUser((u) => ({ ...u, name: e.target.value }))} placeholder="Full name" />
            <input value={editingUser.email || ''} onChange={(e) => setEditingUser((u) => ({ ...u, email: e.target.value }))} placeholder="Email" />
            {editingUser.user_type === 'student' && <input value={editingUser.enrollment_no || ''} onChange={(e) => setEditingUser((u) => ({ ...u, enrollment_no: e.target.value }))} placeholder="Enrollment no" />}
            {['student', 'faculty'].includes(editingUser.user_type) && <select value={editingUser.branch || ''} onChange={(e) => setEditingUser((u) => ({ ...u, branch: e.target.value }))} required><option value="">Branch</option>{BRANCHES.map((branch) => <option key={branch} value={branch}>{branch}</option>)}</select>}
            {editingUser.user_type === 'faculty' && <select value={editingUser.faculty_subjects || ''} onChange={(e) => setEditingUser((u) => ({ ...u, faculty_subjects: e.target.value }))} required><option value="">Subject</option><option value="Python">Python</option><option value="Java">Java</option><option value="C++">C++</option><option value="JavaScript">JavaScript</option></select>}
            <div className="flex gap-2"><button className="button" type="submit"><Pencil size={16} /> Save user</button><button className="button button-secondary" type="button" onClick={() => setEditingUser(null)}>Cancel</button></div>
          </form>
        )}
        <div className="tool-list">
          {users.map((u) => (
            <div key={u.id}>
              <span><Users size={16} /></span>
              <p><strong>{u.name || u.username}</strong><small>{u.username} · {u.email || 'no email'} · {u.user_type}{u.must_change_password ? ' · must create password' : ''}</small></p>
              <div className="flex gap-3">
                <button type="button" className="text-button" onClick={() => resetPassword(u.id)}><KeyRound size={14} /> Reset password</button>
                <button type="button" className="text-button" onClick={() => setEditingUser({ ...u })}><Pencil size={14} /> Edit</button>
                <button type="button" className="text-button text-rose-600" onClick={() => deleteUser(u)}><Trash2 size={14} /> Delete</button>
              </div>
            </div>
          ))}
        </div>
      </article>

      <article className="tool-panel tool-panel--wide">
        <div className="tool-panel__head">
          <span className="tool-icon tool-icon--rose"><ShieldAlert /></span>
          <div><h2>Audit log</h2><p>Every security- and marks-sensitive action, admin-only. Routine login/password-reset noise is filtered out.</p></div>
        </div>
        <div className="my-4 flex flex-wrap gap-2">
          <input
            className="tool-select my-0 flex-1 min-w-[200px]"
            value={auditActionFilter}
            onChange={(e) => setAuditActionFilter(e.target.value)}
            onKeyDown={(e) => { if (e.key === 'Enter') loadAuditLogs(1); }}
            placeholder="Filter by action (e.g. admin_user_created)"
          />
          <button type="button" className="button button-secondary" onClick={() => loadAuditLogs(1)}>Filter</button>
        </div>
        {auditLoading ? (
          <p className="tool-empty">Loading audit log…</p>
        ) : auditLogs.length === 0 ? (
          <p className="tool-empty">No audit entries match.</p>
        ) : (
          <div className="tool-list">
            {auditLogs.map((log) => (
              <div key={log.id}>
                <span><ShieldAlert size={16} /></span>
                <p>
                  <strong>{log.action.replaceAll('_', ' ')}</strong>
                  <small>{log.actor} · {log.target_type || 'general'} {log.target_id ? `#${log.target_id}` : ''} · {new Date(log.created_at).toLocaleString()}{log.ip_address ? ` · ${log.ip_address}` : ''}</small>
                </p>
              </div>
            ))}
          </div>
        )}
        <div className="mt-4 flex flex-wrap items-center justify-end gap-2.5">
          <button type="button" className="button button-secondary" disabled={!auditPage.has_previous} onClick={() => loadAuditLogs(auditPage.page - 1)}><ChevronLeft size={16} /> Prev</button>
          <small className="text-xs font-bold text-slate-500" style={{ margin: 0 }}>Page {auditPage.page} of {auditPage.page_count}</small>
          <button type="button" className="button button-secondary" disabled={!auditPage.has_next} onClick={() => loadAuditLogs(auditPage.page + 1)}>Next <ChevronRight size={16} /></button>
        </div>
      </article>
    </section>
  );
}

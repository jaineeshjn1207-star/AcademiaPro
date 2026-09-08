import React, { useEffect, useMemo, useState } from 'react';
import { Link } from 'react-router-dom';
import { ArrowUpRight, BarChart3, BookOpen, CalendarDays, CheckCircle2, ClipboardList, KeyRound, Loader2, Plus, Radio, Search, Settings2, Users, X } from 'lucide-react';
import api from '../api/axios';
import { useAuth } from '../context/AuthContext';

function ExamRow({ exam, onSelect }) {
  const scheduled = new Date(exam.start_time);
  const ends = new Date(exam.end_time);
  const state = exam.is_live ? { label: 'Live', tone: 'is-live' } : !exam.is_active ? { label: 'Draft', tone: 'is-draft' } : !exam.can_publish ? { label: 'Needs marks', tone: 'is-review' } : { label: 'Published', tone: 'is-ready' };
  return (
    <article className="faculty-exam-row">
      <div className="faculty-exam-date"><strong>{scheduled.toLocaleDateString('en-IN', { day: '2-digit' })}</strong><span>{scheduled.toLocaleDateString('en-IN', { month: 'short' })}</span></div>
      <div className="faculty-exam-summary"><div className="faculty-exam-meta"><span className={`faculty-state ${state.tone}`}>{state.label}</span><span>{exam.duration_minutes} min</span><span>{exam.total_marks} marks</span></div><h2>{exam.title}</h2><p>{exam.description || 'No assessment description added.'}</p><div className="faculty-exam-time"><CalendarDays size={14} /> {scheduled.toLocaleString('en-IN', { dateStyle: 'medium', timeStyle: 'short' })} <span>→</span> {ends.toLocaleString('en-IN', { dateStyle: 'medium', timeStyle: 'short' })}</div></div>
      <div className="faculty-exam-progress"><small>Paper allocation</small><strong>{exam.allocated_marks ?? 0}<em> / {exam.total_marks}</em></strong><div><span style={{ width: `${Math.min(100, ((exam.allocated_marks || 0) / Math.max(1, exam.total_marks)) * 100)}%` }} /></div><p>{exam.mcq_count} MCQ · {exam.coding_count} coding</p></div>
      <div className="faculty-exam-actions"><Link to={`/faculty/exam/${exam.id}/manage`} onClick={onSelect} className="app-button"><Settings2 size={15} /> Build</Link><Link to={`/faculty/exam/${exam.id}/otps`} onClick={onSelect} className="faculty-link-action"><KeyRound size={15} /> Access</Link><div className="faculty-mini-actions"><Link to={`/faculty/exam/${exam.id}/live-status`} onClick={onSelect} title="Live status"><Radio size={18} /></Link><Link to={`/exam/${exam.id}/analytics`} onClick={onSelect} title="Analytics"><BarChart3 size={18} /></Link></div></div>
    </article>
  );
}

export default function FacultyDashboard() {
  const { activeExam, setActiveExam } = useAuth();
  const [exams, setExams] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [query, setQuery] = useState('');
  const [statusFilter, setStatusFilter] = useState('all');

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const response = await api.get('exams/');
        if (cancelled) return;
        const list = Array.isArray(response.data) ? response.data : response.data.results || [];
        setExams(list);
        if (list.length && !activeExam) setActiveExam(list[0]);
      } catch (requestError) {
        if (!cancelled) setError(requestError.response?.data?.error || 'Your assessment workspace could not be loaded.');
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => { cancelled = true; };
  }, []);

  const figures = useMemo(() => ({
    all: exams.length,
    live: exams.filter((exam) => exam.is_live).length,
    ready: exams.filter((exam) => exam.is_active && exam.can_publish).length,
    drafts: exams.filter((exam) => !exam.is_active || !exam.can_publish).length,
  }), [exams]);

  const filteredExams = useMemo(() => {
    let list = exams;
    if (statusFilter === 'live') list = list.filter((exam) => exam.is_live);
    else if (statusFilter === 'ready') list = list.filter((exam) => exam.is_active && exam.can_publish);
    else if (statusFilter === 'drafts') list = list.filter((exam) => !exam.is_active || !exam.can_publish);
    const q = query.trim().toLowerCase();
    if (q) list = list.filter((exam) => exam.title.toLowerCase().includes(q) || (exam.description || '').toLowerCase().includes(q));
    return list;
  }, [exams, query, statusFilter]);

  if (loading) return <div className="app-loading" role="status"><span /><p>Opening your faculty workspace</p></div>;

  return (
    <div className="app-page faculty-studio">
      <header className="faculty-intro"><div><p className="app-eyebrow">Faculty assessment studio</p><h1 className="app-title">Make every evaluation count.</h1><p className="app-subtitle">Build papers, govern secure access, follow activity, and release outcomes without switching context.</p></div><div className="faculty-intro-actions"><Link to="/faculty/notes" className="app-button app-button--quiet"><BookOpen size={16} /> Materials</Link><Link to="/faculty/create-exam" className="app-button"><Plus size={17} /> New assessment</Link></div></header>
      {error && <div className="app-error" role="alert">{error}</div>}
      <section className="faculty-figures" aria-label="Assessment figures">
        <button type="button" className={statusFilter === 'all' ? 'is-active-filter' : ''} onClick={() => setStatusFilter('all')}><span className="figure-glyph coral"><ClipboardList size={18} /></span><p>Total assessments</p><strong>{figures.all}</strong><small>In your workspace</small></button>
        <button type="button" className={statusFilter === 'live' ? 'is-active-filter' : ''} onClick={() => setStatusFilter(statusFilter === 'live' ? 'all' : 'live')}><span className="figure-glyph mint"><Radio size={18} /></span><p>Live activity</p><strong>{figures.live}</strong><small>Assessment windows open</small></button>
        <button type="button" className={statusFilter === 'ready' ? 'is-active-filter' : ''} onClick={() => setStatusFilter(statusFilter === 'ready' ? 'all' : 'ready')}><span className="figure-glyph yellow"><CheckCircle2 size={18} /></span><p>Ready to run</p><strong>{figures.ready}</strong><small>Published and complete</small></button>
        <button type="button" className={statusFilter === 'drafts' ? 'is-active-filter' : ''} onClick={() => setStatusFilter(statusFilter === 'drafts' ? 'all' : 'drafts')}><span className="figure-glyph ink"><Settings2 size={18} /></span><p>In preparation</p><strong>{figures.drafts}</strong><small>Need attention</small></button>
      </section>
      <div className="faculty-workspace">
        <section className="faculty-list">
          <div className="faculty-list-heading">
            <div><p className="app-eyebrow">Assessment register</p><h2>All assessments</h2></div>
            <Link to="/results">Open results <ArrowUpRight size={15} /></Link>
          </div>
          {exams.length > 0 && (
            <div className="faculty-search-bar">
              <Search size={15} />
              <input type="search" value={query} onChange={(e) => setQuery(e.target.value)} placeholder="Search by title or description…" aria-label="Search assessments" />
              {query && <button type="button" onClick={() => setQuery('')} aria-label="Clear search"><X size={14} /></button>}
            </div>
          )}
          {exams.length === 0 ? (
            <div className="faculty-empty"><ClipboardList size={34} /><h2>Start with your first assessment</h2><p>Create the paper, assign its time window, and add questions when you are ready.</p><Link to="/faculty/create-exam" className="app-button"><Plus size={16} /> Create assessment</Link></div>
          ) : filteredExams.length === 0 ? (
            <div className="faculty-empty"><Search size={30} /><h2>No assessments match your filters</h2><p>Try a different search term, or clear the status filter above.</p><button type="button" className="app-button app-button--quiet" onClick={() => { setQuery(''); setStatusFilter('all'); }}>Clear filters</button></div>
          ) : filteredExams.map((exam) => <ExamRow key={exam.id} exam={exam} onSelect={() => setActiveExam(exam)} />)}
        </section>
        <aside className="faculty-aside">
          <section className="faculty-aside-card"><span className="app-badge">Control room</span><h2>One calm workflow.</h2><p>Questions, OTP access, monitoring, analysis, and results stay connected to every assessment.</p><Link to="/faculty/create-exam">Configure an assessment <ArrowUpRight size={15} /></Link></section>
          <section className="faculty-aside-card faculty-aside-links"><p className="app-eyebrow">Shortcuts</p><Link to="/faculty/notes"><BookOpen size={17} /><span><strong>Resource library</strong><small>Notes and study materials</small></span></Link><Link to="/results"><Users size={17} /><span><strong>Results centre</strong><small>Every student outcome</small></span></Link></section>
        </aside>
      </div>
    </div>
  );
}

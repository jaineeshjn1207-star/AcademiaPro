import React, { useEffect, useMemo, useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { BookOpen, CalendarDays, CalendarPlus, CheckCircle2, Clock3, FileText, LockKeyhole, Play, ShieldCheck, Sparkles, Timer, XCircle } from 'lucide-react';
import api from '../api/axios';
import { useAuth } from '../context/AuthContext';

const stateMeta = {
  live: { label: 'Live now', icon: Play, tone: 'is-live' },
  upcoming: { label: 'Scheduled', icon: CalendarDays, tone: 'is-upcoming' },
  completed: { label: 'Completed', icon: CheckCircle2, tone: 'is-complete' },
  pending: { label: 'Results pending', icon: Clock3, tone: 'is-pending' },
  closed: { label: 'Window closed', icon: XCircle, tone: 'is-closed' },
  ufm: { label: 'Voided', icon: XCircle, tone: 'is-closed' },
};

const formatCountdown = (target, now) => {
  const seconds = Math.max(0, Math.floor((new Date(target).getTime() - now.getTime()) / 1000));
  const hours = Math.floor(seconds / 3600);
  const minutes = Math.floor((seconds % 3600) / 60);
  const remaining = seconds % 60;
  return [hours, minutes, remaining].map((part) => String(part).padStart(2, '0')).join(':');
};

function ExamCard({ item, now }) {
  const navigate = useNavigate();
  const { exam, state, session_status: sessionStatus, total_score: totalScore, is_passed: isPassed, is_ufm: isUfm, otp_active: otpActive, results_released: resultsReleased } = item;
  const done = state === 'completed';
  const key = isUfm ? 'ufm' : done && !resultsReleased ? 'pending' : state;
  const meta = stateMeta[key] || stateMeta.upcoming;
  const Icon = meta.icon;
  const startsAt = new Date(exam.start_time);
  const endsAt = new Date(exam.end_time);
  const timer = state === 'live' && !done ? formatCountdown(endsAt, now) : state === 'upcoming' ? formatCountdown(startsAt, now) : null;

  const addToCalendar = async () => {
    try {
      const response = await api.get(`exams/${exam.id}/calendar.ics`, { responseType: 'blob' });
      const url = URL.createObjectURL(response.data);
      const link = document.createElement('a');
      link.href = url;
      link.download = `${exam.title.replace(/[^A-Za-z0-9]+/g, '-')}.ics`;
      link.click();
      URL.revokeObjectURL(url);
    } catch {
      // Silent: calendar export is a convenience action, not a critical path.
    }
  };

  return (
    <article className="exam-ticket">
      <div className="exam-ticket-stripe" />
      <div className="exam-ticket-main">
        <div className="exam-ticket-topline"><span className={`exam-status ${meta.tone}`}><Icon size={13} /> {meta.label}</span><span className="exam-ticket-code">ASSESSMENT #{String(exam.id).padStart(3, '0')}</span></div>
        <h2>{exam.title}</h2>
        <p className="exam-ticket-description">{exam.description || 'An online assessment prepared by your faculty.'}</p>
        <div className="exam-ticket-schedule"><span><CalendarDays size={15} /> {startsAt.toLocaleDateString('en-IN', { day: 'numeric', month: 'short', year: 'numeric' })}</span><span><Clock3 size={15} /> {startsAt.toLocaleTimeString('en-IN', { hour: 'numeric', minute: '2-digit' })} – {endsAt.toLocaleTimeString('en-IN', { hour: 'numeric', minute: '2-digit' })}</span></div>
        <div className="exam-facts">
          <span><small>Duration</small><strong>{exam.duration_minutes} min</strong></span>
          <span><small>Marks</small><strong>{exam.total_marks}</strong></span>
          <span><small>Pass mark</small><strong>{exam.passing_marks}</strong></span>
          <span><small>Paper</small><strong>{exam.mcq_count} MCQ · {exam.coding_count} Code</strong></span>
        </div>
        {exam.enforce_fullscreen && !done && <p className="exam-ticket-notice"><ShieldCheck size={15} /> This is a proctored assessment. Fullscreen and secure-browser checks apply.</p>}
      </div>
      <aside className="exam-ticket-action">
        {timer && <div className="exam-countdown"><small>{state === 'live' ? 'Closes in' : 'Starts in'}</small><strong>{timer}</strong></div>}
        {state === 'upcoming' && <button type="button" className="app-button app-button--quiet exam-ticket-calendar" onClick={addToCalendar}><CalendarPlus size={15} /> Add to calendar</button>}
        {state === 'live' && !done && <button type="button" className="app-button" onClick={() => navigate(`/exam/${exam.id}/room`)}><Play size={16} fill="currentColor" /> Enter secure room</button>}
        {done && <div className="exam-result-state"><CheckCircle2 size={22} /><strong>{isUfm ? 'Attempt voided' : resultsReleased ? `${totalScore}/${exam.total_marks}` : 'Submitted'}</strong><span>{isUfm ? 'Faculty review required' : resultsReleased ? (isPassed ? 'Passed assessment' : 'Result available') : 'Waiting for result release'}</span></div>}
        {done && !isUfm && <div className="exam-ticket-links"><Link to={`/exam/${exam.id}/result`}><FileText size={15} /> Review result</Link><Link to={`/exam/${exam.id}/analytics`}>See insights</Link></div>}
        {!otpActive && state === 'live' && !done && <p className="exam-ticket-warning"><LockKeyhole size={14} /> Your temporary OTP is no longer active.</p>}
      </aside>
    </article>
  );
}

export default function StudentDashboard() {
  const { user, activeExam, setActiveExam } = useAuth();
  const [items, setItems] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [now, setNow] = useState(() => new Date());

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const response = await api.get('my-exams/');
        if (cancelled) return;
        const list = response.data.exams || [];
        setItems(list);
        const relevant = list.find((item) => item.state === 'live') || list.find((item) => item.state === 'completed') || list[0];
        if (relevant?.exam && relevant.exam.id !== activeExam?.id) setActiveExam(relevant.exam);
      } catch {
        if (!cancelled) setError('Your assessment desk could not be loaded. Please refresh and try again.');
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => { cancelled = true; };
  }, []); // active exam is a navigation convenience, not a loading dependency

  useEffect(() => {
    const interval = window.setInterval(() => setNow(new Date()), 1000);
    return () => window.clearInterval(interval);
  }, []);

  const overview = useMemo(() => ({
    live: items.filter((item) => item.state === 'live' && item.session_status !== 'submitted').length,
    upcoming: items.filter((item) => item.state === 'upcoming').length,
    completed: items.filter((item) => item.state === 'completed').length,
  }), [items]);

  if (loading) return <div className="app-loading" role="status"><span /><p>Opening your assessment desk</p></div>;

  return (
    <div className="app-page student-desk">
      <header className="desk-intro">
        <div><p className="app-eyebrow">Student workspace</p><h1 className="app-title">Good day, {user?.name?.split(' ')[0]}.</h1><p className="app-subtitle">Everything you need for your upcoming assessments, study material, and published outcomes—kept in one calm space.</p></div>
        <div className="desk-intro-actions"><Link to="/ai-tutor" className="app-button app-button--quiet"><Sparkles size={16} /> Ask the tutor</Link></div>
      </header>

      {error && <div className="app-error" role="alert">{error}</div>}

      <section className="desk-metrics" aria-label="Assessment overview">
        <div className="desk-metric"><span className="metric-index">01</span><div><small>Open right now</small><strong>{overview.live}</strong></div><Play size={19} /></div>
        <div className="desk-metric"><span className="metric-index">02</span><div><small>On your schedule</small><strong>{overview.upcoming}</strong></div><CalendarDays size={19} /></div>
        <div className="desk-metric"><span className="metric-index">03</span><div><small>Completed</small><strong>{overview.completed}</strong></div><CheckCircle2 size={19} /></div>
      </section>

      <div className="desk-layout">
        <section className="desk-assessments"><div className="desk-section-title"><div><p className="app-eyebrow">Your timetable</p><h2>Assessments</h2></div><span>{items.length} total</span></div>{items.length ? items.map((item) => <ExamCard key={item.exam.id} item={item} now={now} />) : <div className="desk-empty"><CalendarDays size={32} /><h2>No assessments yet</h2><p>Your faculty will add an assessment here when it is ready for you.</p><Link className="app-button app-button--quiet" to="/notes">Browse study materials</Link></div>}</section>
        <aside className="desk-sidebar"><section className="desk-side-card desk-identity"><span className="app-badge">Student profile</span><h2>{user?.name}</h2><p>{user?.branch ? `${user.branch} branch` : 'Branch not set'}</p><code>{user?.enrollment_no}</code></section><section className="desk-side-card"><p className="app-eyebrow">Quick access</p><Link to="/notes"><BookOpen size={17} /><span><strong>Study library</strong><small>Faculty-published resources</small></span></Link><Link to="/my-notes"><FileText size={17} /><span><strong>My notebook</strong><small>Personal revision notes</small></span></Link><Link to="/results"><CheckCircle2 size={17} /><span><strong>All results</strong><small>Review completed work</small></span></Link></section><section className="desk-side-card desk-help"><Timer size={19} /><div><strong>Before you enter</strong><p>Keep your OTP ready and allow the required proctoring permissions.</p></div></section></aside>
      </div>
    </div>
  );
}

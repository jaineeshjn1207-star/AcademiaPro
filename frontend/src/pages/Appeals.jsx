import React, { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { CheckCircle2, ClipboardList, Loader2, MessageSquare, Send } from 'lucide-react';
import api from '../api/axios';
import { useAuth } from '../context/AuthContext';
import './appeals.css';

const statusStyle = { open: 'bg-amber-100 text-amber-800', reviewing: 'bg-blue-100 text-blue-800', resolved: 'bg-emerald-100 text-emerald-800', rejected: 'bg-rose-100 text-rose-800' };

export default function Appeals() {
  const { user } = useAuth();
  const isFaculty = user?.user_type === 'faculty';
  const [appeals, setAppeals] = useState([]);
  const [results, setResults] = useState([]);
  const [examId, setExamId] = useState('');
  const [reason, setReason] = useState('');
  const [responses, setResponses] = useState({});
  const [loading, setLoading] = useState(true);
  const [message, setMessage] = useState('');

  const load = async () => {
    setLoading(true);
    try {
      const [inbox, resultList] = await Promise.all([api.get('appeals/'), isFaculty ? Promise.resolve({ data: { results: [] } }) : api.get('results/')]);
      setAppeals(inbox.data.appeals || []);
      const rows = resultList.data.results || [];
      setResults(rows.filter((row) => row.results_released));
      setExamId((current) => current || String(rows.find((row) => row.results_released)?.exam_id || ''));
    } catch (err) { setMessage(err.response?.data?.error || 'Could not load tickets.'); }
    finally { setLoading(false); }
  };
  useEffect(() => { load(); }, [isFaculty]);

  const submit = async (event) => {
    event.preventDefault();
    if (!examId) return setMessage('Choose a released result first.');
    try {
      await api.post(`exams/${examId}/appeals/`, { reason });
      setReason(''); setMessage('Ticket submitted and marked In review.'); load();
    } catch (err) { setMessage(err.response?.data?.error || 'Could not submit ticket.'); }
  };
  const update = async (ticket, status) => {
    const response = (responses[ticket.id] ?? ticket.faculty_response ?? '').trim();
    if (status === 'resolved' && !response) {
      setMessage('Write a response for the student before resolving this ticket.');
      return;
    }
    try {
      await api.patch(`exams/${ticket.exam_id}/appeals/${ticket.id}/`, { status, faculty_response: response });
      setMessage(`Ticket marked ${status}. The student has been notified.`); load();
    } catch (err) { setMessage(err.response?.data?.error || 'Could not update ticket.'); }
  };

  return <section className="app-page max-w-6xl appeals-page">
    <header className="mb-8 flex flex-wrap items-start justify-between gap-4"><div><p className="eyebrow">{isFaculty ? 'Department review queue' : 'Student requests'}</p><h1 className="text-3xl font-black text-slate-900">Appeals & tickets</h1><p className="mt-2 text-sm text-slate-600">{isFaculty ? 'Review department submissions, record a clear decision, and keep students informed.' : 'Request a review of a released result and follow every response here.'}</p></div><ClipboardList className="h-8 w-8 text-blue-600" /></header>
    {message && <div className="mb-5 rounded-lg border border-blue-200 bg-blue-50 px-4 py-3 text-sm text-blue-900">{message}</div>}
    {!isFaculty && <form onSubmit={submit} className="mb-8 grid gap-4 rounded-lg border border-slate-200 bg-white p-5 shadow-sm md:grid-cols-[minmax(12rem,0.4fr)_1fr_auto]">
      <select value={examId} onChange={(e) => setExamId(e.target.value)} className="rounded-lg border border-slate-300 px-3 py-2 text-sm"><option value="">Select result</option>{results.map((row) => <option key={row.exam_id} value={row.exam_id}>{row.exam_title}</option>)}</select>
      <textarea value={reason} onChange={(e) => setReason(e.target.value)} minLength="10" required placeholder="Describe the concern and the outcome you are requesting." className="min-h-20 rounded-lg border border-slate-300 px-3 py-2 text-sm" />
      <button type="submit" className="app-button self-end"><Send size={16} /> Submit ticket</button>
    </form>}
    {loading ? <div className="flex justify-center p-10"><Loader2 className="animate-spin text-blue-600" /></div> : <div className="space-y-4">{appeals.length ? appeals.map((ticket) => <article key={ticket.id} className="rounded-lg border border-slate-200 bg-white p-5 shadow-sm"><div className="flex flex-wrap justify-between gap-3"><div><h2 className="font-bold text-slate-900">{ticket.exam_title}</h2>{isFaculty && <p className="mt-1 text-sm text-slate-600">{ticket.student?.name} · {ticket.student?.enrollment_no}</p>}</div><span className={`h-fit rounded-full px-3 py-1 text-xs font-bold capitalize ${statusStyle[ticket.status]}`}>{ticket.status === 'open' ? 'In review' : ticket.status}</span></div><p className="mt-4 text-sm text-slate-700"><b>Request:</b> {ticket.reason}</p>{isFaculty ? <><textarea value={responses[ticket.id] ?? ticket.faculty_response ?? ''} onChange={(e) => setResponses((old) => ({ ...old, [ticket.id]: e.target.value }))} placeholder="Decision, reason, and next steps for the student" className="mt-4 min-h-20 w-full rounded-lg border border-slate-300 px-3 py-2 text-sm" /><div className="mt-3 flex flex-wrap gap-2"><button type="button" className="button" onClick={() => update(ticket, 'resolved')}><CheckCircle2 size={16} /> Resolve</button><Link className="button button-secondary" to={`/faculty/exam/${ticket.exam_id}/student/${ticket.student?.id}/analysis`}>Open student analysis</Link></div></> : ticket.faculty_response && <div className="mt-4 rounded-lg bg-slate-50 p-3 text-sm text-slate-700"><MessageSquare className="mr-2 inline h-4 w-4 text-blue-600" /><b>Faculty response:</b> {ticket.faculty_response}</div>}</article>) : <div className="rounded-lg border border-dashed border-slate-300 p-10 text-center text-sm text-slate-500">No tickets to show.</div>}</div>}
  </section>;
}

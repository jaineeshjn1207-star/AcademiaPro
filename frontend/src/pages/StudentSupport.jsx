import React, { useEffect, useState } from 'react';
import api from '../api/axios';
import './faculty-tools.css';

export default function StudentSupport() {
  const [exams, setExams] = useState([]); const [examId, setExamId] = useState(''); const [appeals, setAppeals] = useState([]); const [reason, setReason] = useState(''); const [message, setMessage] = useState('');
  const load = async () => { const result = await api.get('results/'); const rows = result.data.results || []; setExams(rows); if (!examId && rows[0]) setExamId(String(rows[0].exam_id)); };
  useEffect(() => { load().catch(() => setMessage('Unable to load results.')); }, []);
  useEffect(() => { if (examId) api.get(`exams/${examId}/appeals/`).then((r) => setAppeals(r.data.appeals || [])).catch(() => {}); }, [examId]);
  const submit = async (e) => { e.preventDefault(); try { await api.post(`exams/${examId}/appeals/`, { reason }); setReason(''); setMessage('Appeal submitted for faculty review.'); const r = await api.get(`exams/${examId}/appeals/`); setAppeals(r.data.appeals || []); } catch (err) { setMessage(err.response?.data?.error || 'Unable to submit appeal.'); } };
  return <section className="app-page faculty-tools-page"><header className="page-heading"><div><p className="eyebrow">Student support</p><h1>Appeals & review</h1><p>Request a review after results are released.</p></div></header><article className="tool-panel"><form className="tool-form tool-form--stack" onSubmit={submit}><select value={examId} onChange={(e) => setExamId(e.target.value)}>{exams.map((x) => <option key={x.exam_id} value={x.exam_id}>{x.exam_title}</option>)}</select><textarea value={reason} onChange={(e) => setReason(e.target.value)} minLength="10" required placeholder="Explain what should be reviewed (minimum 10 characters)." /><button className="button">Submit appeal</button></form>{message && <p className="tool-message">{message}</p>}<div className="tool-list">{appeals.map((x) => <div key={x.id}><p><strong>{x.status}</strong><small>{x.reason}{x.faculty_response ? ` — ${x.faculty_response}` : ''}</small></p></div>)}</div></article></section>;
}



import React, { useEffect, useState } from 'react';
import { Bell, BookCopy, Check, ClipboardList, Copy, FileUp, RefreshCw, ShieldAlert } from 'lucide-react';
import api from '../api/axios';
import './faculty-tools.css';

export default function FacultyTools() {
  const [notifications, setNotifications] = useState([]);
  const [bank, setBank] = useState([]);
  const [title, setTitle] = useState('');
  const [kind, setKind] = useState('mcq');
  const [bankOptions, setBankOptions] = useState({ a: '', b: '', c: '', d: '' });
  const [bankCorrect, setBankCorrect] = useState('A');
  const [message, setMessage] = useState('');
  const [exams, setExams] = useState([]);
  const [examId, setExamId] = useState('');
  const [cloneTitle, setCloneTitle] = useState('');
  const [quality, setQuality] = useState([]);
  const [pdfFile, setPdfFile] = useState(null);

  const load = async () => {
    try {
      const [inbox, questions, assessmentList] = await Promise.all([
        api.get('notifications/'), api.get('question-bank/'), api.get('exams/'),
      ]);
      setNotifications(inbox.data.notifications || []);
      setBank(questions.data.items || []);
      setExams(assessmentList.data || []);
      setExamId((current) => current || String(assessmentList.data?.[0]?.id || ''));
      setMessage('');
    } catch { setMessage('Unable to load faculty tools. Please refresh.'); }
  };
  useEffect(() => { load(); }, []);

  useEffect(() => {
    if (!examId) return;
    api.get(`exams/${examId}/question-quality/`).then((r) => setQuality(r.data.questions || [])).catch(() => setQuality([]));
  }, [examId]);

  const addQuestion = async (event) => {
    event.preventDefault();
    if (!title.trim()) return;
    const isMcqComplete = kind !== 'mcq' || (bankOptions.a.trim() && bankOptions.b.trim() && bankOptions.c.trim() && bankOptions.d.trim());
    if (!isMcqComplete) { setMessage('Fill in all four options before saving an MCQ.'); return; }
    const payload = kind === 'mcq'
      ? { question_text: title, option_a: bankOptions.a, option_b: bankOptions.b, option_c: bankOptions.c, option_d: bankOptions.d, correct_option: bankCorrect }
      : { title, problem_statement: title };
    try {
      await api.post('question-bank/', { kind, title, payload });
      setTitle(''); setBankOptions({ a: '', b: '', c: '', d: '' }); setBankCorrect('A');
      setMessage('Saved to your reusable question bank.'); load();
    } catch (error) { setMessage(error.response?.data?.error || 'Could not save the question.'); }
  };

  const importPdf = async (event) => {
    event.preventDefault();
    if (!pdfFile) return;
    try {
      const form = new FormData(); form.append('file', pdfFile);
      const res = await api.post('question-bank/import-pdf/', form);
      setPdfFile(null);
      setMessage(`Imported ${res.data.created || 0} question-bank item(s) from PDF.`);
      load();
    } catch (error) { setMessage(error.response?.data?.error || 'Could not import PDF.'); }
  };

  const markRead = async () => { await api.patch('notifications/', {}); load(); };

  const cloneExam = async (event) => {
    event.preventDefault(); const source = exams.find((exam) => String(exam.id) === examId); if (!source) return;
    const now = new Date(); const end = new Date(now.getTime() + 7200000);
    try { const res = await api.post(`exams/${examId}/clone/`, { title: cloneTitle || `${source.title} (copy)`, start_time: now.toISOString(), end_time: end.toISOString() }); setMessage(`${res.data.exam.title} was created as a draft.`); setCloneTitle(''); load(); }
    catch (error) { setMessage(error.response?.data?.error || 'Could not clone this assessment.'); }
  };

  return <section className="app-page faculty-tools-page">
    <header className="page-heading"><div><p className="eyebrow">Faculty workspace</p><h1>Assessment tools</h1><p>Question bank, assessment cloning, quality insight, and faculty notifications.</p></div><button className="button button-secondary" onClick={load}><RefreshCw size={16} /> Refresh</button></header>
    {message && <div className="tool-message" role="status">{message}</div>}
    <div className="faculty-tools-grid">
      <article className="tool-panel"><div className="tool-panel__head"><span className="tool-icon"><BookCopy /></span><div><h2>Question bank</h2><p>Save draft MCQs/coding prompts to reuse while authoring an exam.</p></div></div>
        <form className="tool-form tool-form--stack" onSubmit={addQuestion}>
          <select value={kind} onChange={(e) => setKind(e.target.value)} aria-label="Question kind"><option value="mcq">Multiple choice</option><option value="coding">Coding problem</option></select>
          <input value={title} onChange={(e) => setTitle(e.target.value)} placeholder={kind === 'mcq' ? 'Question text' : 'Problem title / statement'} />
          {kind === 'mcq' && <div className="tool-mcq-options">{['a', 'b', 'c', 'd'].map((k) => <label key={k} className={bankCorrect === k.toUpperCase() ? 'is-correct' : ''}><input type="radio" name="bank-correct" checked={bankCorrect === k.toUpperCase()} onChange={() => setBankCorrect(k.toUpperCase())} /><span>{k.toUpperCase()}</span><input type="text" value={bankOptions[k]} onChange={(e) => setBankOptions((prev) => ({ ...prev, [k]: e.target.value }))} placeholder={`Option ${k.toUpperCase()}`} /></label>)}<small className="tool-empty" style={{ margin: 0 }}>Select the radio button next to the correct option.</small></div>}
          <button className="button" type="submit"><Check size={16} /> Save item</button>
        </form>
        <form className="tool-form tool-form--stack tool-form--soft" onSubmit={importPdf}>
          <strong>Import question bank from PDF</strong>
          <small className="tool-empty" style={{ margin: 0 }}>PDF parser supports numbered MCQs with A-D options + Answer, and coding/problem statements.</small>
          <input type="file" accept="application/pdf,.pdf" onChange={(e) => setPdfFile(e.target.files?.[0] || null)} />
          <button className="button" type="submit" disabled={!pdfFile}><FileUp size={16} /> Import PDF</button>
        </form>
        <div className="tool-list">{bank.length ? bank.slice(0, 6).map((item) => <div key={item.id}><span>{item.kind === 'mcq' ? <ClipboardList size={16} /> : <BookCopy size={16} />}</span><p><strong>{item.title || 'Untitled item'}</strong><small>{item.kind} · {item.subject || 'No subject'}</small></p></div>) : <p className="tool-empty">Your saved questions will appear here.</p>}</div>
      </article>

      <article className="tool-panel"><div className="tool-panel__head"><span className="tool-icon tool-icon--mint"><Copy /></span><div><h2>Clone an assessment</h2><p>Copy a prior paper into a new unpublished draft.</p></div></div><form className="tool-form tool-form--stack" onSubmit={cloneExam}><select value={examId} onChange={(e) => setExamId(e.target.value)}>{exams.map((exam) => <option key={exam.id} value={exam.id}>{exam.title}</option>)}</select><input value={cloneTitle} onChange={(e) => setCloneTitle(e.target.value)} placeholder="New assessment title (optional)" /><button className="button" type="submit"><Copy size={16} /> Create draft</button></form></article>

      <article className="tool-panel"><div className="tool-panel__head"><span className="tool-icon"><ClipboardList /></span><div><h2>Question quality</h2><p>Difficulty and discrimination for the selected assessment.</p></div></div><select className="tool-select" value={examId} onChange={(e) => setExamId(e.target.value)}>{exams.map((exam) => <option key={exam.id} value={exam.id}>{exam.title}</option>)}</select><div className="tool-list">{quality.length ? quality.map(q => <div key={q.id}><p><strong>{q.label}</strong><small>Correct: {q.difficulty_percent}% · Discrimination: {q.discrimination}</small></p></div>) : <p className="tool-empty">No quality data yet.</p>}</div></article>

      <article className="tool-panel"><div className="tool-panel__head tool-panel__head--inbox"><span className="tool-icon tool-icon--rose"><Bell /></span><div><h2>Faculty inbox</h2><p>Results, appeals, and proctoring updates.</p></div>{notifications.some((n) => !n.is_read) && <button className="text-button" onClick={markRead}>Mark all read</button>}</div>
        <div className="tool-list tool-list--inbox">{notifications.length ? notifications.slice(0, 8).map((note) => <div key={note.id} className={note.is_read ? '' : 'is-unread'}><span><ShieldAlert size={16} /></span><p><strong>{note.title}</strong><small>{note.body || 'Open the related assessment for details.'}</small></p></div>) : <p className="tool-empty">No new faculty notifications.</p>}</div>
      </article>
    </div>

  </section>;
}

import React, { useEffect, useState } from 'react';
import { useParams, Link } from 'react-router-dom';
import api from '../api/axios';
import { useToast } from '../components/ToastProvider';
import './workflow-page.css';
import {
  ArrowLeft, Ban, CheckCircle2, XCircle, Loader2, AlertCircle, Save,
  ShieldAlert, Video, Code, HelpCircle, User, ClipboardCheck,
} from 'lucide-react';

const STATUS_LABEL = { correct: 'Correct', partial: 'Partial', incorrect: 'Incorrect', pending: 'Pending' };
const STATUS_TONE = {
  correct: 'bg-emerald-100 text-emerald-700', partial: 'bg-amber-100 text-amber-700',
  incorrect: 'bg-rose-100 text-rose-700', pending: 'bg-slate-100 text-slate-600',
};

function CodeReview({ submission }) {
  const needsAttention = ['incorrect', 'partial'].includes(submission.logic_status);
  const hasCorrection = Boolean(submission.ai_corrected_code?.trim());

  return (
    <div className={`mt-4 grid gap-4 ${hasCorrection ? 'xl:grid-cols-2' : ''}`}>
      <div className={`overflow-hidden rounded-2xl border ${needsAttention ? 'border-rose-300 bg-rose-50' : 'border-slate-200 bg-slate-50'}`}>
        <div className={`flex items-center gap-2 border-b px-4 py-2.5 text-xs font-black uppercase tracking-wide ${needsAttention ? 'border-rose-200 text-rose-800' : 'border-slate-200 text-slate-600'}`}>
          {needsAttention ? <XCircle className="h-4 w-4" /> : <Code className="h-4 w-4" />}
          Student submission{needsAttention ? ' — review highlighted' : ''}
        </div>
        <pre className={`max-h-80 overflow-auto p-4 font-mono text-xs leading-6 ${needsAttention ? 'bg-rose-950 text-rose-100' : 'bg-slate-950 text-slate-200'}`}>{submission.submitted_code || '// No code submitted'}</pre>
      </div>

      {hasCorrection && (
        <div className="overflow-hidden rounded-2xl border border-emerald-300 bg-emerald-50">
          <div className="flex items-center gap-2 border-b border-emerald-200 px-4 py-2.5 text-xs font-black uppercase tracking-wide text-emerald-800">
            <CheckCircle2 className="h-4 w-4" /> Corrected code — recommended fix
          </div>
          <pre className="max-h-80 overflow-auto bg-emerald-950 p-4 font-mono text-xs leading-6 text-emerald-100">{submission.ai_corrected_code}</pre>
        </div>
      )}
    </div>
  );
}

function FixedDurationVideo({ src }) {
  // Chrome's MediaRecorder writes an unseekable/Infinity duration into WebM
  // blobs it produces, so the native player shows "0:00" even though the
  // clip has real, playable content. Forcing a seek past the end and back
  // to 0 makes Chrome recompute the real duration from the data itself.
  const handleLoadedMetadata = (e) => {
    const video = e.target;
    if (video.duration === Infinity || Number.isNaN(video.duration)) {
      video.currentTime = 1e101;
      const onTimeUpdate = () => {
        video.currentTime = 0;
        video.removeEventListener('timeupdate', onTimeUpdate);
      };
      video.addEventListener('timeupdate', onTimeUpdate);
    }
  };
  return (
    <video
      src={src}
      controls
      preload="metadata"
      onLoadedMetadata={handleLoadedMetadata}
      className="w-full rounded-xl bg-black"
    />
  );
}

export default function StudentAnalysis() {
  const { toast } = useToast();
  const { examId, studentId } = useParams();
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [notStarted, setNotStarted] = useState(false);
  const [mcqEdits, setMcqEdits] = useState({});     // responseId -> marks string
  const [codingEdits, setCodingEdits] = useState({}); // submissionId -> marks string
  const [saving, setSaving] = useState(false);
  const [verifying, setVerifying] = useState(false);

  const load = async () => {
    setLoading(true);
    setError('');
    setNotStarted(false);
    try {
      const res = await api.get(`exams/${examId}/students/${studentId}/analysis/`);
      setData(res.data);
      setMcqEdits({});
      setCodingEdits({});
    } catch (err) {
      if (err.response?.data?.not_started) setNotStarted(true);
      setError(err.response?.data?.error || 'Could not load this student\'s analysis.');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { load(); /* eslint-disable-next-line */ }, [examId, studentId]);

  const hasEdits = Object.keys(mcqEdits).length > 0 || Object.keys(codingEdits).length > 0;

  const handleSaveMarks = async () => {
    setSaving(true);
    try {
      await api.patch(`exams/${examId}/students/${studentId}/marks/`, {
        mcq_overrides: mcqEdits,
        coding_overrides: codingEdits,
      });
      toast({ type: 'success', title: 'Marks saved & verified', message: 'This student attempt is now marked reviewed for result publishing.' });
      await load();
    } catch (err) {
      toast({ type: 'error', title: 'Could not save marks', message: err.response?.data?.error || 'Please try again.' });
    } finally {
      setSaving(false);
    }
  };

  const handleVerifySession = async () => {
    setVerifying(true);
    try {
      await api.post(`exams/${examId}/students/${studentId}/verify/`, {});
      toast({ type: 'success', title: 'Student verified', message: 'This attempt is now marked reviewed for result publishing.' });
      await load();
    } catch (err) {
      toast({ type: 'error', title: 'Could not verify student', message: err.response?.data?.error || 'Please try again.' });
    } finally {
      setVerifying(false);
    }
  };

  if (loading) {
    return <div className="flex min-h-[70vh] items-center justify-center"><Loader2 className="h-12 w-12 animate-spin text-indigo-600" /></div>;
  }

  if (error || !data) {
    return (
      <div className="mx-auto max-w-xl px-4 py-16">
        <div className="rounded-3xl border border-rose-200 bg-rose-50 p-8 text-center">
          <AlertCircle className="mx-auto mb-3 h-12 w-12 text-rose-500" />
          <p className="text-sm text-rose-700">{error}</p>
          {notStarted && <p className="mt-1 text-xs text-rose-500">There is nothing to analyze until they begin the exam.</p>}
          <Link to={`/faculty/exam/${examId}/live-status`} className="mt-5 inline-flex items-center gap-2 rounded-xl bg-rose-600 px-6 py-2.5 text-sm font-bold text-white">
            <ArrowLeft className="h-4 w-4" /> Back to Live Status
          </Link>
        </div>
      </div>
    );
  }

  return (
    <div className="app-page workflow-page student-analysis-page">
      <Link to={`/faculty/exam/${examId}/live-status`} className="inline-flex items-center gap-2 text-sm font-semibold text-slate-500 hover:text-slate-800">
        <ArrowLeft className="h-4 w-4" /> Back to Live Status
      </Link>

      <header className="overflow-hidden rounded-2xl border border-slate-200 bg-white p-6 text-slate-900 shadow-sm sm:p-8">
        <div className="flex flex-col justify-between gap-6 md:flex-row md:items-center">
          <div className="flex items-center gap-4">
            <div className="flex h-14 w-14 items-center justify-center rounded-2xl bg-white/10"><User className="h-7 w-7" /></div>
            <div>
              <h1 className="text-2xl font-black">{data.student_name}</h1>
          <p className="text-sm text-slate-500">{data.student_enrollment} · {data.exam_title}</p>
            </div>
          </div>
          <div className="flex flex-wrap items-center gap-3">
            {data.faculty_verified ? (
              <span className="rounded-full bg-emerald-100 px-4 py-2 text-sm font-black text-emerald-800">Faculty Verified</span>
            ) : (
              <span className="rounded-full bg-amber-100 px-4 py-2 text-sm font-black text-amber-800">Needs Faculty Verification</span>
            )}
            {data.is_ufm ? (
              <span className="flex items-center gap-1.5 rounded-full bg-rose-100 px-4 py-2 text-sm font-black text-rose-800">
                <Ban className="h-4 w-4" /> Unfair Means — Voided
              </span>
            ) : data.is_passed ? (
              <span className="flex items-center gap-1.5 rounded-full bg-emerald-100 px-4 py-2 text-sm font-black text-emerald-800">
                <CheckCircle2 className="h-4 w-4" /> Passed
              </span>
            ) : (
              <span className="flex items-center gap-1.5 rounded-full bg-rose-100 px-4 py-2 text-sm font-black text-rose-800">
                <XCircle className="h-4 w-4" /> Failed
              </span>
            )}
          </div>
        </div>
        {data.is_ufm && data.ufm_reason && (
          <p className="mt-4 rounded-xl bg-rose-50 p-3 text-xs text-rose-800">{data.ufm_reason}</p>
        )}
      </header>

      <div className="grid grid-cols-2 gap-4 md:grid-cols-5">
        {[
          ['MCQ', data.mcq_score, 'text-blue-600'],
          ['Coding', data.coding_score, 'text-purple-600'],
          ['Total', data.total_score, 'text-slate-700'],
          ['%', data.percentage, 'text-emerald-600'],
          ['Violations', data.violation_count, 'text-rose-600'],
        ].map(([label, val, toneClass]) => (
          <div key={label} className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
            <div className="text-xs font-bold uppercase text-slate-500">{label}</div>
            <div className={`mt-1 text-2xl font-black ${toneClass}`}>{val}</div>
          </div>
        ))}
      </div>

      {data.can_manage === false && (
        <div className="rounded-2xl border border-blue-200 bg-blue-50 px-5 py-3 text-sm font-semibold text-blue-800">View-only: only faculty from this student&apos;s branch can change marks or verify this attempt.</div>
      )}

      {data.can_manage !== false && (hasEdits || !data.faculty_verified) && (
        <div className={`sticky top-4 z-10 flex flex-col gap-3 rounded-2xl border px-5 py-3 shadow-lg md:flex-row md:items-center md:justify-between ${
          hasEdits ? 'border-amber-300 bg-amber-50' : 'border-emerald-300 bg-emerald-50'
        }`}>
          <div>
            <div className={`text-sm font-black ${hasEdits ? 'text-amber-800' : 'text-emerald-800'}`}>
              {hasEdits ? 'You have unsaved marks overrides.' : 'Marks look correct? Verify this student without editing marks.'}
            </div>
            <p className={`mt-0.5 text-xs font-semibold ${hasEdits ? 'text-amber-700' : 'text-emerald-700'}`}>
              {hasEdits
                ? 'Saving marks will also mark this attempt as faculty verified.'
                : 'This button is enough to unlock result publishing for this student attempt.'}
            </p>
          </div>
          {hasEdits ? (
            <button onClick={handleSaveMarks} disabled={saving}
              className="flex items-center justify-center gap-2 rounded-xl bg-amber-600 px-5 py-2 text-sm font-black text-white hover:bg-amber-700 disabled:opacity-50">
              {saving ? <Loader2 className="h-4 w-4 animate-spin" /> : <Save className="h-4 w-4" />} Save Marks &amp; Verify
            </button>
          ) : (
            <button onClick={handleVerifySession} disabled={verifying}
              className="flex items-center justify-center gap-2 rounded-xl bg-emerald-600 px-5 py-2 text-sm font-black text-white hover:bg-emerald-700 disabled:opacity-50">
              {verifying ? <Loader2 className="h-4 w-4 animate-spin" /> : <ClipboardCheck className="h-4 w-4" />} Mark Student Verified
            </button>
          )}
        </div>
      )}

      {/* MCQ responses */}
      <section className="overflow-hidden rounded-3xl border border-slate-200 bg-white shadow-sm">
        <div className="flex items-center gap-2 border-b border-slate-200 p-6">
          <HelpCircle className="h-5 w-5 text-blue-600" />
          <h3 className="text-base font-black text-slate-900">MCQ Responses ({data.mcq_responses?.length || 0})</h3>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full text-left text-sm">
            <thead className="bg-slate-50 text-xs font-bold uppercase text-slate-500">
              <tr>
                <th className="px-5 py-3">Question</th>
                <th className="px-5 py-3">Selected</th>
                <th className="px-5 py-3">Correct</th>
                <th className="px-5 py-3 text-center">Result</th>
                <th className="px-5 py-3 text-right">Marks (editable)</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {(data.mcq_responses || []).map((r) => {
                const isMulti = r.question_type === 'multi';
                const selectedDisplay = isMulti ? (r.selected_options || []).join(', ') || '—' : (r.selected_option || '—');
                const correctDisplay = isMulti ? (r.correct_options || []).join(', ') : r.correct_option;
                return (
                  <tr key={r.id}>
                    <td className="px-5 py-3 max-w-sm text-slate-700">{r.question_text}</td>
                    <td className="px-5 py-3 font-mono font-bold text-slate-800">{selectedDisplay}</td>
                    <td className="px-5 py-3 font-mono font-bold text-emerald-700">{correctDisplay}</td>
                    <td className="px-5 py-3 text-center">
                      {r.is_correct
                        ? <CheckCircle2 className="mx-auto h-4 w-4 text-emerald-600" />
                        : <XCircle className="mx-auto h-4 w-4 text-rose-500" />}
                    </td>
                    <td className="px-5 py-3 text-right">
                      <input
                        type="number" step="0.5"
                        min={-(r.negative_marks || 0)} max={r.max_marks}
                        defaultValue={r.marks_awarded}
                        onChange={(e) => setMcqEdits((p) => ({ ...p, [r.id]: e.target.value }))}
                        disabled={data.can_manage === false}
                        className="w-20 rounded-lg border border-slate-300 px-2 py-1 text-right font-mono text-sm"
                      />
                      <div className="mt-0.5 text-[11px] text-slate-400">/ {r.max_marks}</div>
                      {r.marks_overridden && <div className="mt-0.5 text-[11px] font-bold text-amber-600">Overridden</div>}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </section>

      {/* Coding submissions */}
      <section className="space-y-4">
        <div className="flex items-center gap-2">
          <Code className="h-5 w-5 text-purple-600" />
          <h3 className="text-base font-black text-slate-900">Coding Submissions ({data.coding_submissions?.length || 0})</h3>
        </div>
        {(data.coding_submissions || []).map((c) => (
          <div key={c.id} className="rounded-3xl border border-slate-200 bg-white p-6 shadow-sm">
            <div className="flex flex-wrap items-center justify-between gap-3 border-b border-slate-100 pb-4">
              <div>
                <h4 className="font-black text-slate-900">{c.problem_title}</h4>
                <p className="text-xs text-slate-400">{c.language} · Evaluated by {c.evaluated_by?.startsWith('gemini:') ? `Gemini (${c.evaluated_by.split(':')[1] || 'model'})` : c.evaluated_by === 'gemini-unavailable' ? 'Gemini unavailable — faculty review required' : 'Faculty/manual review'}</p>
              </div>
              <div className="flex items-center gap-3">
                <span className={`rounded-full px-3 py-1 text-xs font-bold ${STATUS_TONE[c.logic_status]}`}>{STATUS_LABEL[c.logic_status]}</span>
                <div className="text-right">
                  <input
                    type="number" step="0.5" max={c.max_marks}
                    defaultValue={c.marks_awarded}
                    onChange={(e) => setCodingEdits((p) => ({ ...p, [c.id]: e.target.value }))}
                    disabled={data.can_manage === false}
                    className="w-20 rounded-lg border border-slate-300 px-2 py-1 text-right font-mono text-sm"
                  />
                  <span className="ml-1 text-xs text-slate-400">/ {c.max_marks}</span>
                  {c.marks_overridden && <div className="mt-0.5 text-[11px] font-bold text-amber-600">Overridden</div>}
                </div>
              </div>
            </div>
            <CodeReview submission={c} />
            {c.faculty_feedback && <p className={`mt-3 rounded-xl border p-3 text-xs font-medium ${['incorrect', 'partial'].includes(c.logic_status) ? 'border-rose-200 bg-rose-50 text-rose-800' : 'border-slate-200 bg-slate-50 text-slate-600'}`}>{c.faculty_feedback}</p>}
            {(c.test_total_count > 0 || c.ai_logic_summary || c.ai_mistake_explanation || c.ai_corrected_code) && (
              <div className="mt-4 rounded-2xl border border-blue-200 bg-blue-50 p-4 text-xs text-blue-950">
                <div className="mb-2 flex flex-wrap items-center gap-2">
                  <span className="rounded-full bg-blue-600 px-2.5 py-1 font-black uppercase tracking-wide text-white">Evaluation</span>
                  {c.test_total_count > 0 && <span className="rounded-full bg-white px-2.5 py-1 font-bold border border-blue-200">Tests {c.test_passed_count}/{c.test_total_count}</span>}
                  {c.hidden_failed_count > 0 && <span className="rounded-full bg-white px-2.5 py-1 font-bold border border-blue-200">Hidden failed: {c.hidden_failed_count}</span>}
                </div>
                {c.ai_detected_approach && <p><b>Approach:</b> {c.ai_detected_approach}</p>}
                {c.ai_logic_summary && <p className="mt-2 rounded-lg bg-white p-2.5 text-slate-700"><b>Approach summary:</b> {c.ai_logic_summary}</p>}
                {c.ai_mistake_explanation && <p className="mt-2 rounded-lg border border-rose-200 bg-rose-50 p-2.5 font-semibold text-rose-900"><b>What is wrong:</b> {c.ai_mistake_explanation}</p>}
                {c.ai_predicted_output && <p className="mt-1"><b>Current output/behavior:</b> {c.ai_predicted_output}</p>}
                {(c.failed_visible_tests || []).length > 0 && (
                  <div className="mt-2 space-y-2">
                    {(c.failed_visible_tests || []).map((tc) => (
                      <div key={tc.case_number} className="rounded-xl bg-white p-3 font-mono text-[12px] text-slate-700 border border-blue-100">
                        <div><b>Input:</b> {tc.input_data || '—'}</div>
                        <div><b>Expected:</b> {tc.expected_output || '—'}</div>
                        <div><b>Output:</b> {tc.actual_output || '—'}</div>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            )}
          </div>
        ))}
        {(!data.coding_submissions || data.coding_submissions.length === 0) && (
          <div className="rounded-3xl border border-dashed border-slate-300 bg-slate-50 p-10 text-center text-sm text-slate-400">
            No coding submissions.
          </div>
        )}
      </section>

      {/* Proctoring */}
      <section className="overflow-hidden rounded-3xl border border-slate-200 bg-white shadow-sm">
        <div className="flex items-center gap-2 border-b border-slate-200 p-6">
          <ShieldAlert className="h-5 w-5 text-rose-600" />
          <h3 className="text-base font-black text-slate-900">Proctoring Events ({data.proctor_events?.length || 0})</h3>
        </div>
        <div className="max-h-80 divide-y divide-slate-100 overflow-y-auto">
          {(data.proctor_events || []).map((e) => (
            <div key={e.id} className="flex items-center justify-between px-6 py-3 text-sm">
              <div>
                <span className="font-semibold text-slate-800">{e.event_type}</span>
                <span className="ml-2 text-xs text-slate-400">{new Date(e.created_at).toLocaleString()}</span>
              </div>
              <span className="text-xs text-slate-500">{e.details}</span>
            </div>
          ))}
          {(!data.proctor_events || data.proctor_events.length === 0) && (
            <div className="p-6 text-center text-sm text-slate-400">No proctoring events recorded.</div>
          )}
        </div>
      </section>

      {data.proctor_recordings?.length > 0 && (
        <section className="overflow-hidden rounded-3xl border border-slate-200 bg-white shadow-sm">
          <div className="flex items-center gap-2 border-b border-slate-200 p-6">
            <Video className="h-5 w-5 text-indigo-600" />
            <h3 className="text-base font-black text-slate-900">Violation Clips ({data.proctor_recordings.length})</h3>
          </div>
          <div className="grid grid-cols-1 gap-4 p-6 md:grid-cols-2">
            {data.proctor_recordings.map((r) => (
              <FixedDurationVideo key={r.id} src={r.clip_url} />
            ))}
          </div>
        </section>
      )}
    </div>
  );
}

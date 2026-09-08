import React, { useState, useEffect } from 'react';
import { useParams, Link } from 'react-router-dom';
import api from '../api/axios';
import './workflow-page.css';
import { CheckCircle2, XCircle, AlertTriangle, BarChart2, Home, Code, HelpCircle, BookOpen, Lock, Medal, Users, Loader2, Clock, Download } from 'lucide-react';

function RankingSnapshot({ examId }) {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const res = await api.get(`exams/${examId}/leaderboard/`);
        if (!cancelled) setData(res.data);
      } catch {
        if (!cancelled) setData(null);
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => { cancelled = true; };
  }, [examId]);

  if (loading) {
    return (
      <div className="flex items-center justify-center rounded-3xl border border-slate-200 bg-white p-8">
        <Loader2 className="h-6 w-6 animate-spin text-slate-300" />
      </div>
    );
  }
  if (!data || !data.leaderboard?.length) return null;

  const me = data.leaderboard.find((r) => r.is_you);
  // Pin your own row at the top, then show the rest in rank order underneath.
  const rest = data.leaderboard.filter((r) => !r.is_you).slice(0, 7);

  return (
    <section className="overflow-hidden rounded-3xl border border-slate-200 bg-white shadow-sm">
      <div className="flex items-center justify-between border-b border-slate-200 p-6">
        <h3 className="flex items-center gap-2 text-base font-black text-slate-900">
          <Medal className="h-5 w-5 text-amber-500" /> Class Ranking Snapshot
        </h3>
        <span className="flex items-center gap-1.5 text-xs font-semibold text-slate-500">
          <Users className="h-3.5 w-3.5" /> {data.total_participants} evaluated
        </span>
      </div>
      <div className="divide-y divide-slate-100">
        {me && (
          <div className="flex items-center justify-between bg-blue-50 px-6 py-3">
            <div className="flex items-center gap-3">
              <span className="flex h-8 w-8 items-center justify-center rounded-full bg-blue-600 text-xs font-black text-white">#{me.rank}</span>
              <span className="text-sm font-black text-blue-900">You{me.student_name ? ` — ${me.student_name}` : ''}</span>
              <span className="rounded-full bg-blue-200 px-2 py-0.5 text-[11px] font-bold uppercase text-blue-800">Pinned</span>
            </div>
            {me.total_score !== null && (
              <span className="font-mono text-sm font-black text-blue-900">{me.total_score} ({me.percentage}%)</span>
            )}
          </div>
        )}
        {rest.map((r) => (
          <div key={r.session_id || r.rank + r.student_name} className="flex items-center justify-between px-6 py-3">
            <div className="flex items-center gap-3">
              <span className="flex h-8 w-8 items-center justify-center rounded-full bg-slate-100 text-xs font-black text-slate-600">#{r.rank}</span>
              <span className="text-sm font-semibold text-slate-700">{r.student_name}</span>
            </div>
            {r.total_score !== null ? (
              <span className="font-mono text-sm font-bold text-slate-700">{r.total_score} ({r.percentage}%)</span>
            ) : (
              <span className="text-xs text-slate-400">Marks hidden</span>
            )}
          </div>
        ))}
      </div>
      {data.is_masked_view && (
        <p className="border-t border-slate-100 px-6 py-3 text-[12px] text-slate-400">
          Other candidates are anonymised — only your own marks are ever shown to you.
        </p>
      )}
    </section>
  );
}

function ResultPending({ sessionData }) {
  const endTime = sessionData.exam_end_time ? new Date(sessionData.exam_end_time) : null;
  const [now, setNow] = useState(() => new Date());

  useEffect(() => {
    if (!endTime) return undefined;
    const id = setInterval(() => setNow(new Date()), 1000);
    return () => clearInterval(id);
  }, [endTime]);

  const remainingLabel = (() => {
    if (!endTime) return null;
    const totalSeconds = Math.floor((endTime.getTime() - now.getTime()) / 1000);
    if (totalSeconds <= 0) return 'Any moment now…';
    const h = Math.floor(totalSeconds / 3600);
    const m = Math.floor((totalSeconds % 3600) / 60);
    const s = totalSeconds % 60;
    const pad = (n) => String(n).padStart(2, '0');
    return h > 0 ? `${h}h ${pad(m)}m ${pad(s)}s` : `${pad(m)}m ${pad(s)}s`;
  })();

  const voided = sessionData.is_ufm;

  return (
    <div className="max-w-2xl mx-auto py-16 px-4 text-center">
      <div className="rounded-3xl border border-slate-200 bg-white p-10 shadow-xl">
        <div className={`mx-auto flex h-16 w-16 items-center justify-center rounded-full ${voided ? 'bg-rose-100' : 'bg-emerald-100'}`}>
          {voided ? <Lock className="h-8 w-8 text-rose-600" /> : <CheckCircle2 className="h-8 w-8 text-emerald-600" />}
        </div>
        <h1 className="mt-5 text-2xl font-extrabold text-slate-900">
          {voided ? 'Attempt Voided — Unfair Means' : 'Submitted Successfully'}
        </h1>
        <p className="mt-2 text-slate-600">{sessionData.exam_title}</p>
        {voided && sessionData.ufm_reason && (
          <p className="mt-2 text-sm text-rose-700">{sessionData.ufm_reason}</p>
        )}

        <div className={`mt-8 rounded-2xl border p-6 ${voided ? 'border-rose-200 bg-rose-50' : 'border-blue-200 bg-blue-50'}`}>
          <Clock className={`mx-auto h-6 w-6 ${voided ? 'text-rose-600' : 'text-blue-600'}`} />
          <p className={`mt-3 text-sm font-semibold ${voided ? 'text-rose-900' : 'text-blue-900'}`}>
            {voided
              ? 'Final confirmation will be available once the exam window closes for everyone.'
              : 'Results will be available once the exam window closes for everyone.'}
          </p>
          {endTime && (
            <>
              <p className={`mt-1 text-xs ${voided ? 'text-rose-700' : 'text-blue-700'}`}>
                {endTime.toLocaleString()}
              </p>
              {remainingLabel && (
                <p className={`mt-3 font-mono text-lg font-black ${voided ? 'text-rose-900' : 'text-blue-900'}`}>
                  {remainingLabel}
                </p>
              )}
            </>
          )}
        </div>

        <p className="mt-6 text-xs text-slate-500">
          This keeps things fair — nobody can see marks, including their own, while other candidates are still taking the exam.
        </p>

        <Link
          to="/"
          className="mt-8 inline-flex items-center gap-2 rounded-xl bg-blue-600 px-6 py-2.5 text-sm font-bold text-white transition hover:bg-blue-700"
        >
          <Home className="h-4 w-4" /> Back to Dashboard
        </Link>
      </div>
    </div>
  );
}

export default function ExamResult() {
  const { examId } = useParams();
  const [sessionData, setSessionData] = useState(null);
  const downloadPdf = async () => { const response = await api.get(`exams/${examId}/result-card.pdf`, { responseType: 'blob' }); const url = URL.createObjectURL(response.data); const link = document.createElement('a'); link.href = url; link.download = 'exam-result.pdf'; link.click(); URL.revokeObjectURL(url); };
  const [loading, setLoading] = useState(true);
  const [activeTab, setActiveTab] = useState('coding'); // 'coding' or 'mcq'

  useEffect(() => {
    const fetchResult = async () => {
      try {
        const res = await api.get(`exams/${examId}/result/`);
        setSessionData(res.data);
      } catch (err) {
        console.error(err);
      } finally {
        setLoading(false);
      }
    };
    fetchResult();
  }, [examId]);

  if (loading) {
    return (
      <div className="min-h-[70vh] flex items-center justify-center">
        <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600"></div>
      </div>
    );
  }

  if (!sessionData) {
    return (
      <div className="max-w-4xl mx-auto py-12 px-4 text-center">
        <div className="bg-white p-8 rounded-2xl shadow border border-slate-200">
          <h2 className="text-xl font-bold text-slate-800">Result Not Available</h2>
          <p className="text-slate-600 mt-2">Could not load evaluation results. You may not have completed this examination yet.</p>
          <Link to="/" className="mt-4 inline-block px-6 py-2 bg-blue-600 text-white rounded-xl">Back to Dashboard</Link>
        </div>
      </div>
    );
  }

  if (sessionData.results_released === false) {
    return <ResultPending sessionData={sessionData} />;
  }

  return (
    <div className="app-page workflow-page result-review-page">

      {sessionData.is_ufm && (
        <div className="flex items-start gap-3 rounded-3xl border-2 border-rose-300 bg-rose-100 p-6 text-rose-900 shadow-lg">
          <Lock className="mt-0.5 h-6 w-6 flex-shrink-0 text-rose-600" />
          <div>
            <h2 className="text-lg font-black">Result Voided — Unfair Means</h2>
            <p className="mt-1 text-sm leading-relaxed">
              This attempt was locked and all marks zeroed after exceeding the proctoring violation limit.
              {sessionData.ufm_reason ? ` ${sessionData.ufm_reason}` : ''} Your account cannot sign back in
              to the portal until your faculty restores access — contact them if you believe this was a mistake.
            </p>
          </div>
        </div>
      )}

      {/* Top Banner Card */}
      <div className="bg-white rounded-3xl shadow-xl border border-slate-200 p-8 overflow-hidden relative">
        <div className="flex flex-col md:flex-row items-center justify-between gap-6">
          <div>
            <div className="flex items-center gap-3">
              <span className={`px-3 py-1 text-xs font-bold rounded-full uppercase tracking-wider ${
                sessionData.is_ufm ? 'bg-rose-100 text-rose-800' : 'bg-emerald-100 text-emerald-800'
              }`}>
                {sessionData.is_ufm ? 'Voided — Unfair Means' : 'Evaluation Completed'}
              </span>
              <span className="text-xs text-slate-500 font-medium">
                Submitted at: {new Date(sessionData.submitted_at || sessionData.started_at).toLocaleString()}
              </span>
            </div>
            <h1 className="text-3xl font-extrabold text-slate-900 mt-2">{sessionData.exam_title}</h1>
            <p className="text-slate-600 mt-1">Candidate: <span className="font-semibold text-slate-800">{sessionData.student_name}</span> ({sessionData.student_enrollment})</p>
          </div>
          <button type="button" onClick={downloadPdf} className="inline-flex items-center gap-2 rounded-xl bg-slate-900 px-4 py-3 font-bold text-white"><Download size={17}/> Download PDF</button>

          <div className={`p-6 rounded-2xl border text-center min-w-[220px] ${
            sessionData.is_ufm
              ? 'bg-rose-50 border-rose-200 text-rose-900'
              : sessionData.is_passed
              ? 'bg-emerald-50 border-emerald-200 text-emerald-900'
              : 'bg-rose-50 border-rose-200 text-rose-900'
          }`}>
            <div className="text-xs font-bold uppercase tracking-wider">Total Score Awarded</div>
            <div className="text-4xl font-black mt-1">
              {sessionData.total_score}
              <span className="text-lg font-bold opacity-60">/{sessionData.total_marks}</span>
            </div>
            <div className="text-sm font-bold opacity-75">{sessionData.percentage}%</div>
            <div className="mt-2 flex items-center justify-center gap-1.5 text-sm font-bold">
              {sessionData.is_ufm ? (
                <>
                  <Lock className="w-5 h-5 text-rose-600" /> VOIDED
                </>
              ) : sessionData.is_passed ? (
                <>
                  <CheckCircle2 className="w-5 h-5 text-emerald-600" /> PASSED
                </>
              ) : (
                <>
                  <XCircle className="w-5 h-5 text-rose-600" /> NEEDS IMPROVEMENT
                </>
              )}
            </div>
          </div>
        </div>

        {/* Breakdown bar */}
        <div className="grid grid-cols-2 sm:grid-cols-3 gap-4 mt-8 pt-6 border-t border-slate-200">
          <div className="bg-slate-50 p-4 rounded-xl border border-slate-200">
            <div className="text-xs text-slate-500 font-medium">MCQ Score</div>
            <div className="text-xl font-bold text-slate-800 mt-0.5">{sessionData.mcq_score} Marks</div>
          </div>
          <div className="bg-slate-50 p-4 rounded-xl border border-slate-200">
            <div className="text-xs text-slate-500 font-medium">Coding & Algorithm Score</div>
            <div className="text-xl font-bold text-slate-800 mt-0.5">{sessionData.coding_score} Marks</div>
          </div>
          <div className="col-span-2 sm:col-span-1 bg-amber-50 p-4 rounded-xl border border-amber-200">
            <div className="text-xs text-amber-800 font-medium">Temporary OTP Security Status</div>
            <div className="text-sm font-bold text-amber-900 mt-0.5 flex items-center gap-1">
              <Lock className="w-4 h-4 text-amber-700" /> Cleared & Deactivated
            </div>
          </div>
        </div>

        {/* Proctoring summary */}
        {(sessionData.is_auto_submitted || sessionData.violation_count > 0) && (
          <div className="mt-4 rounded-2xl border border-rose-200 bg-rose-50 p-4 text-sm text-rose-900">
            <div className="flex items-start gap-3">
              <AlertTriangle className="mt-0.5 h-5 w-5 flex-shrink-0 text-rose-600" />
              <div>
                <b>Proctoring report:</b>{' '}
                {sessionData.violation_count} violation{sessionData.violation_count === 1 ? '' : 's'} were recorded during this attempt.
                {sessionData.is_auto_submitted && ' Your paper was submitted automatically by the system.'}
              </div>
            </div>
          </div>
        )}
      </div>

      {/* Navigation Buttons */}
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div className="flex items-center space-x-2 bg-slate-200 p-1 rounded-xl">
          <button
            onClick={() => setActiveTab('coding')}
            className={`px-5 py-2.5 rounded-lg text-sm font-bold transition flex items-center gap-2 ${
              activeTab === 'coding' ? 'bg-white text-purple-700 shadow-sm' : 'text-slate-600 hover:text-slate-900'
            }`}
          >
            <Code className="w-4 h-4" />
            <span>Algorithm Logic & Reference Solutions ({sessionData.coding_submissions?.length || 0})</span>
          </button>
          <button
            onClick={() => setActiveTab('mcq')}
            className={`px-5 py-2.5 rounded-lg text-sm font-bold transition flex items-center gap-2 ${
              activeTab === 'mcq' ? 'bg-white text-blue-700 shadow-sm' : 'text-slate-600 hover:text-slate-900'
            }`}
          >
            <HelpCircle className="w-4 h-4" />
            <span>MCQ Breakdown ({sessionData.mcq_responses?.length || 0})</span>
          </button>
        </div>

        <div className="flex items-center gap-3">
          <Link
            to={`/exam/${sessionData.exam}/analytics`}
            className="px-5 py-2.5 bg-blue-600 hover:bg-blue-700 text-white font-bold rounded-xl text-sm transition flex items-center gap-2"
          >
            <BarChart2 className="w-4 h-4" /> Performance Analytics
          </Link>
          <Link
            to="/"
            className="px-4 py-2.5 bg-slate-200 hover:bg-slate-300 text-slate-800 font-bold rounded-xl text-sm transition flex items-center gap-1.5"
          >
            <Home className="w-4 h-4" /> Home
          </Link>
        </div>
      </div>

      {/* Class Ranking Snapshot — anonymised, your own row pinned at the top */}
      <RankingSnapshot examId={sessionData.exam} />

      {/* Main Tab Content */}
      {activeTab === 'coding' ? (
        <div className="space-y-8">
          <div className="bg-purple-900 text-white p-6 rounded-2xl shadow-md flex items-start gap-4">
            <BookOpen className="w-8 h-8 text-purple-300 flex-shrink-0 mt-1" />
            <div>
              <h3 className="text-lg font-bold">Automated Logic Evaluation & Reference Unlock</h3>
              <p className="text-sm text-purple-200 mt-1">
                When your submitted algorithm logic is marked incorrect or requires improvement, our evaluation engine automatically unlocks the faculty's reference solutions below. Compare your logic against the optimal solutions to improve your problem-solving skills!
              </p>
            </div>
          </div>

          {sessionData.coding_submissions?.map((sub, idx) => {
            const isLogicCorrect = sub.logic_status === 'correct';
            const isPartial = sub.logic_status === 'partial';
            const isPending = sub.logic_status === 'pending';
            const hasReferenceSolutions = sub.reference_solutions && sub.reference_solutions.length > 0;
            const badgeCls = isLogicCorrect
              ? 'bg-emerald-500/20 text-emerald-300 border border-emerald-500/40'
              : isPartial
                ? 'bg-amber-500/20 text-amber-300 border border-amber-500/40'
                : isPending
                  ? 'bg-slate-500/20 text-slate-300 border border-slate-500/40'
                  : 'bg-rose-500/20 text-rose-300 border border-rose-500/40';
            const badgeLabel = isLogicCorrect ? 'Correct Logic' : isPartial ? 'Partially Correct' : isPending ? 'Pending Faculty Review' : 'Incorrect Logic';

            return (
              <div key={sub.id} className="bg-white rounded-3xl shadow-xl border border-slate-200 overflow-hidden">
                <div className="p-6 bg-slate-900 text-white flex flex-wrap items-center justify-between gap-4">
                  <div>
                    <span className="text-xs text-purple-400 font-semibold uppercase tracking-wider">Coding Problem {idx + 1}</span>
                    <h3 className="text-xl font-bold mt-0.5">{sub.problem_title}</h3>
                  </div>

                  <div className="flex items-center gap-3">
                    <span className={`px-3 py-1.5 rounded-xl text-xs font-bold uppercase tracking-wider flex items-center gap-1.5 ${badgeCls}`}>
                      {isLogicCorrect ? <CheckCircle2 className="w-4 h-4" /> : isPartial ? <AlertTriangle className="w-4 h-4" /> : isPending ? <Clock className="w-4 h-4" /> : <XCircle className="w-4 h-4" />}
                      {badgeLabel}
                    </span>
                    {false && sub.similarity_score > 0 && (
                      <span className="px-3 py-1.5 bg-slate-800 text-slate-300 text-xs font-semibold rounded-xl border border-slate-700">
                        {Math.round(sub.similarity_score * 100)}% match
                        {sub.matched_reference ? ` · ${sub.matched_reference}` : ''}
                      </span>
                    )}
                    <span className="px-3 py-1.5 bg-slate-800 text-amber-400 font-bold text-sm rounded-xl border border-slate-700">
                      {sub.marks_awarded} / {sub.max_marks} Marks
                    </span>
                  </div>
                </div>

                <div className="p-6 space-y-6">
                  {/* Candidate Submitted Code */}
                  <div>
                    <h4 className="mb-2 text-xs font-bold uppercase tracking-wider text-slate-500">
                      Your Submitted Logic ({sub.language})
                    </h4>
                    {sub.faculty_feedback && (
                      <div className={`mb-3 rounded-xl border p-3 text-xs leading-relaxed ${
                        isLogicCorrect
                          ? 'border-emerald-200 bg-emerald-50 text-emerald-900'
                          : isPartial
                            ? 'border-amber-200 bg-amber-50 text-amber-900'
                            : 'border-rose-200 bg-rose-50 text-rose-900'
                      }`}>
                        <b>Feedback:</b> {sub.faculty_feedback}
                      </div>
                    )}

                    {(sub.test_total_count > 0 || sub.ai_logic_summary || sub.ai_mistake_explanation || sub.ai_corrected_code) && (
                      <div className="mb-4 rounded-2xl border border-blue-200 bg-blue-50 p-4 text-sm text-blue-950">
                        <div className="mb-2 flex flex-wrap items-center gap-2">
                          <span className="rounded-full bg-blue-600 px-3 py-1 text-xs font-black uppercase tracking-wide text-white">Evaluation Feedback</span>
                          {sub.test_total_count > 0 && (
                            <span className="rounded-full bg-white px-3 py-1 text-xs font-bold text-blue-800 border border-blue-200">
                              Tests passed: {sub.test_passed_count}/{sub.test_total_count}
                              {sub.hidden_failed_count > 0 ? ` · ${sub.hidden_failed_count} hidden failed` : ''}
                            </span>
                          )}
                        </div>
                        {sub.ai_detected_approach && <p><b>Detected approach:</b> {sub.ai_detected_approach}</p>}
                        {sub.ai_logic_summary && <p className="mt-1"><b>Logic summary:</b> {sub.ai_logic_summary}</p>}
                        {sub.ai_mistake_explanation && <p className="mt-1"><b>What to fix:</b> {sub.ai_mistake_explanation}</p>}
                        {sub.ai_predicted_output && <p className="mt-1"><b>What your code currently does/outputs:</b> {sub.ai_predicted_output}</p>}
                        {(sub.failed_visible_tests || []).length > 0 && (
                          <div className="mt-3 space-y-2">
                            <b className="text-xs uppercase tracking-wide text-blue-800">Visible failed tests</b>
                            {(sub.failed_visible_tests || []).map((tc) => (
                              <div key={tc.case_number} className="rounded-xl border border-blue-100 bg-white p-3 font-mono text-xs text-slate-700">
                                <div><b>Input:</b> {tc.input_data || '—'}</div>
                                <div><b>Expected:</b> {tc.expected_output || '—'}</div>
                                <div><b>Your output:</b> {tc.actual_output || '—'}</div>
                              </div>
                            ))}
                          </div>
                        )}
                        {sub.ai_corrected_code && (
                          <details className="mt-3 rounded-xl border border-blue-100 bg-white p-3">
                            <summary className="cursor-pointer text-xs font-black uppercase tracking-wide text-blue-800">Corrected code based on your approach</summary>
                            <pre className="mt-3 max-h-80 overflow-auto rounded-xl bg-slate-950 p-4 font-mono text-xs text-emerald-300">{sub.ai_corrected_code}</pre>
                          </details>
                        )}
                      </div>
                    )}
                    <pre className="p-4 bg-slate-950 text-slate-200 font-mono text-xs rounded-2xl overflow-x-auto border border-slate-800 leading-relaxed max-h-64">
                      {sub.submitted_code}
                    </pre>
                  </div>

                  {/* Reference Solutions Unlocked Section */}
                  {hasReferenceSolutions ? (
                    <div className="mt-8 pt-8 border-t-2 border-dashed border-purple-200 space-y-6">
                      <div className="flex items-center space-x-3 text-purple-900">
                        <div className="w-10 h-10 rounded-xl bg-purple-100 flex items-center justify-center">
                          <Code className="w-6 h-6 text-purple-600" />
                        </div>
                        <div>
                          <h4 className="text-lg font-black tracking-tight">Faculty Reference Answers & Optimal Logic Unlocked</h4>
                          <p className="text-xs text-slate-600">Because your logic {isPartial ? 'was only partially correct' : 'required correction'}, review these {sub.reference_solutions.length} reference solutions uploaded by your faculty:</p>
                        </div>
                      </div>

                      <div className="grid grid-cols-1 gap-6">
                        {sub.reference_solutions.map((refSol, rIdx) => (
                          <div key={refSol.id} className="bg-purple-50/50 border border-purple-200 rounded-2xl p-6 space-y-4">
                            <div className="flex items-center justify-between">
                              <h5 className="font-bold text-slate-900 text-base flex items-center gap-2">
                                <span className="px-2.5 py-0.5 bg-purple-600 text-white rounded-lg text-xs">Solution #{rIdx + 1}</span>
                                {refSol.title}
                              </h5>
                              <span className="text-xs font-mono uppercase bg-purple-100 text-purple-800 px-2.5 py-1 rounded-md font-bold">
                                {refSol.language}
                              </span>
                            </div>

                            {refSol.logic_explanation && (
                              <div className="bg-white p-4 rounded-xl border border-purple-100 text-xs text-slate-700 leading-relaxed shadow-sm">
                                <span className="font-bold text-purple-900 block mb-1">Why this logic works:</span>
                                {refSol.logic_explanation}
                              </div>
                            )}

                            <pre className="p-4 bg-slate-900 text-emerald-300 font-mono text-xs rounded-xl overflow-x-auto border border-slate-800 leading-relaxed">
                              {refSol.code}
                            </pre>
                          </div>
                        ))}
                      </div>
                    </div>
                  ) : isLogicCorrect ? (
                    <div className="p-4 bg-emerald-50 border border-emerald-200 rounded-2xl text-emerald-800 text-sm flex items-center gap-3">
                      <CheckCircle2 className="w-6 h-6 text-emerald-600 flex-shrink-0" />
                      <span>Great job! Your algorithm logic was verified as correct. Reference solutions are shown only when logic needs correction or upon faculty review.</span>
                    </div>
                  ) : (
                    <div className="p-4 bg-amber-50 border border-amber-200 rounded-2xl text-amber-900 text-sm flex items-start gap-3">
                      <Lock className="w-6 h-6 text-amber-700 flex-shrink-0 mt-0.5" />
                      <span>Reference solutions are locked until the exam window finishes, so students still writing the exam cannot access answers. They will unlock after {sub.reference_unlock_at ? new Date(sub.reference_unlock_at).toLocaleString() : 'the exam end time'} if your logic needs correction.</span>
                    </div>
                  )}
                </div>
              </div>
            );
          })}
        </div>
      ) : (
        /* MCQ Responses Breakdown */
        <div className="bg-white rounded-3xl shadow-xl border border-slate-200 p-8 space-y-6">
          <h3 className="text-xl font-bold text-slate-800 border-b border-slate-200 pb-4">Multiple Choice Responses Evaluation</h3>

          <div className="space-y-4">
            {sessionData.mcq_responses?.map((resp, idx) => {
              const isMulti = resp.question_type === 'multi';
              const selectedDisplay = isMulti
                ? (resp.selected_options?.length ? resp.selected_options.join(', ') : 'Not Answered')
                : (resp.selected_option || 'Not Answered');
              const correctDisplay = isMulti ? (resp.correct_options || []).join(', ') : resp.correct_option;
              return (
                <div key={resp.id} className={`p-5 rounded-2xl border transition ${
                  resp.is_correct ? 'bg-emerald-50/40 border-emerald-200' : 'bg-rose-50/40 border-rose-200'
                }`}>
                  <div className="flex items-start justify-between gap-4">
                    <div className="flex items-start gap-3">
                      <span className={`w-7 h-7 rounded-lg flex items-center justify-center text-xs font-bold flex-shrink-0 ${
                        resp.is_correct ? 'bg-emerald-600 text-white' : 'bg-rose-600 text-white'
                      }`}>
                        {idx + 1}
                      </span>
                      <div>
                        <div className="flex items-center gap-2">
                          <h4 className="font-semibold text-slate-900 text-sm leading-relaxed">{resp.question_text}</h4>
                          {isMulti && (
                            <span className="rounded-md bg-indigo-100 px-1.5 py-0.5 text-[11px] font-bold uppercase text-indigo-700">Multi-select</span>
                          )}
                        </div>

                        <div className="mt-3 flex flex-wrap items-center gap-4 text-xs">
                          <span className="font-medium text-slate-600">
                            Your Selected Option{isMulti ? 's' : ''}: <span className={`font-bold px-2 py-0.5 rounded ${
                              resp.is_correct ? 'bg-emerald-200 text-emerald-900' : 'bg-rose-200 text-rose-900'
                            }`}>{selectedDisplay}</span>
                          </span>

                          {!resp.is_correct && (
                            <span className="font-medium text-slate-600">
                              Correct Option{isMulti ? 's' : ''}: <span className="font-bold bg-emerald-200 text-emerald-900 px-2 py-0.5 rounded">{correctDisplay}</span>
                            </span>
                          )}
                        </div>
                      </div>
                    </div>

                    <span className={`px-3 py-1 rounded-lg text-xs font-bold flex-shrink-0 ${
                      resp.is_correct ? 'bg-emerald-100 text-emerald-800' : 'bg-rose-100 text-rose-800'
                    }`}>
                      {resp.marks_awarded} Marks
                    </span>
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      )}

    </div>
  );
}

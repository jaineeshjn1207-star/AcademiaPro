import React, { useEffect, useMemo, useState } from 'react';
import { Link, useNavigate, useParams } from 'react-router-dom';
import api from '../api/axios';
import { useAuth } from '../context/AuthContext';
import './analytics-page.css';
import {
  Activity, AlertCircle, ArrowLeft, Award, BarChart2, BarChart3, CheckCircle2, Home,
  ImageOff, Loader2, Lock, PieChart as PieIcon, Search, Target, TrendingUp, Users, XCircle,
} from 'lucide-react';

const fmt = (n, decimals = 0) => {
  const num = Number(n || 0);
  return Number.isInteger(num) || decimals === 0 ? num.toFixed(decimals).replace(/\.0$/, '') : num.toFixed(decimals);
};

function ChartCard({ title, subtitle, icon: Icon, children, className = '' }) {
  return (
    <section className={`analytics-card ${className}`}>
      <div className="analytics-card-head">
        <div className="flex items-start gap-3">
          {Icon && (
            <div className="analytics-card-icon">
              <Icon className="h-5 w-5" />
            </div>
          )}
          <div>
            <h3>{title}</h3>
            {subtitle && <p>{subtitle}</p>}
          </div>
        </div>
      </div>
      {children}
    </section>
  );
}

function StatCard({ label, value, suffix, icon: Icon, tone = 'slate' }) {
  const tones = {
    slate: 'bg-slate-100 text-slate-600',
    blue: 'bg-blue-100 text-blue-600',
    emerald: 'bg-emerald-100 text-emerald-600',
    rose: 'bg-rose-100 text-rose-600',
    amber: 'bg-amber-100 text-amber-600',
    purple: 'bg-purple-100 text-purple-600',
  };
  return (
    <div className={`analytics-stat is-${tone}`}>
      <div className="analytics-stat-head">
        <span>{label}</span>
        {Icon && <span><Icon size={16} /></span>}
      </div>
      <div className="analytics-stat-value">
        {value}
        {suffix && <span>{suffix}</span>}
      </div>
    </div>
  );
}

function NoData({ label = 'Not enough evaluated submissions to draw this chart yet.' }) {
  return (
    <div className="flex h-64 flex-col items-center justify-center rounded-2xl border-2 border-dashed border-slate-200 bg-slate-50 text-center">
      <BarChart2 className="mb-2 h-10 w-10 text-slate-300" />
      <p className="text-sm font-semibold text-slate-500">{label}</p>
    </div>
  );
}

function MetricBars({ data, percent = false, emptyLabel }) {
  const usable = (data || []).filter((item) => Number(item.value) > 0 || item.showZero);
  if (!usable.length) return <NoData label={emptyLabel} />;
  const max = percent ? 100 : Math.max(...usable.map((item) => Number(item.value)), 1);
  return (
    <div className="space-y-4">
      {usable.map((item) => {
        const value = Number(item.value || 0);
        const width = Math.max(value ? 5 : 0, Math.min(100, (value / max) * 100));
        return (
          <div key={item.label}>
            <div className="mb-1.5 flex items-center justify-between gap-4 text-xs">
              <span className="font-semibold text-slate-600 dark:text-slate-300">{item.label}</span>
              <span className="font-mono font-bold text-slate-900 dark:text-white">{item.display ?? `${fmt(value, percent ? 1 : 0)}${percent ? '%' : ''}`}</span>
            </div>
            <div className="h-2.5 overflow-hidden rounded-full bg-slate-100 dark:bg-slate-700">
              <div className={`h-full rounded-full ${item.color || 'bg-indigo-500'}`} style={{ width: `${width}%` }} />
            </div>
          </div>
        );
      })}
    </div>
  );
}

function DonutChart({ data, centerLabel = 'Total', emptyLabel }) {
  const total = data.reduce((sum, item) => sum + Number(item.value || 0), 0);
  if (!total) return <NoData label={emptyLabel} />;
  let cursor = 0;
  const gradient = data.filter((item) => item.value > 0).map((item) => {
    const start = (cursor / total) * 100;
    cursor += Number(item.value);
    return `${item.hex} ${start}% ${(cursor / total) * 100}%`;
  }).join(', ');
  return (
    <div className="flex flex-col items-center gap-6 sm:flex-row sm:justify-center">
      <div className="relative h-44 w-44 rounded-full" style={{ background: `conic-gradient(${gradient})` }}>
        <div className="absolute inset-4 flex flex-col items-center justify-center rounded-full bg-white dark:bg-slate-800">
          <strong className="text-2xl font-bold text-slate-900 dark:text-white">{total}</strong>
          <span className="text-[11px] font-semibold uppercase tracking-wide text-slate-500">{centerLabel}</span>
        </div>
      </div>
      <div className="min-w-[9rem] space-y-3">
        {data.map((item) => (
          <div key={item.label} className="flex items-center justify-between gap-5 text-xs">
            <span className="flex items-center gap-2 text-slate-600 dark:text-slate-300"><i className="h-2.5 w-2.5 rounded-full" style={{ backgroundColor: item.hex }} />{item.label}</span>
            <strong className="font-mono text-slate-900 dark:text-white">{item.value}</strong>
          </div>
        ))}
      </div>
    </div>
  );
}

/**
 * Renders a chart image rendered server-side (matplotlib/seaborn).
 *
 * Important: chart URLs are authenticated API endpoints. A plain <img src>
 * cannot send the JWT Authorization header, so we fetch the PNG as a blob via
 * the shared axios client and then render a temporary object URL.
 */
function ChartImage({ src, alt, noDataLabel }) {
  const [status, setStatus] = useState(src ? 'loading' : 'empty');
  const [objectUrl, setObjectUrl] = useState('');

  useEffect(() => {
    let cancelled = false;
    let localUrl = '';
    setObjectUrl('');
    setStatus(src ? 'loading' : 'empty');

    if (!src) return () => {};

    (async () => {
      try {
        const res = await api.get(src, { responseType: 'blob' });
        if (cancelled) return;
        localUrl = URL.createObjectURL(res.data);
        setObjectUrl(localUrl);
        setStatus('loaded');
      } catch (err) {
        if (!cancelled) setStatus('error');
      }
    })();

    return () => {
      cancelled = true;
      if (localUrl) URL.revokeObjectURL(localUrl);
    };
  }, [src]);

  if (status === 'empty' || status === 'error') {
    return status === 'error'
      ? (
        <div className="flex h-64 flex-col items-center justify-center rounded-2xl border-2 border-dashed border-rose-200 bg-rose-50 text-center">
          <ImageOff className="mb-2 h-10 w-10 text-rose-400" />
          <p className="text-sm font-semibold text-rose-500">Chart image failed to load.</p>
        </div>
      )
      : <NoData label={noDataLabel} />;
  }

  return (
    <div className="relative">
      {status === 'loading' && (
        <div className="flex h-64 items-center justify-center rounded-2xl bg-slate-50">
          <Loader2 className="h-8 w-8 animate-spin text-slate-300" />
        </div>
      )}
      {objectUrl && (
        <img
          src={objectUrl}
          alt={alt}
          className="w-full rounded-2xl"
        />
      )}
    </div>
  );
}

function AnalyticsPending({ stats }) {
  const endTime = stats.exam_end_time ? new Date(stats.exam_end_time) : null;
  return (
    <div className="mx-auto max-w-2xl px-4 py-16 text-center">
      <div className="rounded-3xl border border-blue-200 bg-blue-50 p-10">
        <Lock className="mx-auto h-10 w-10 text-blue-600" />
        <h2 className="mt-4 text-xl font-black text-blue-950">Analytics Not Available Yet</h2>
        <p className="mt-2 text-sm leading-relaxed text-blue-800">
          {stats.exam_title ? `“${stats.exam_title}”` : 'This exam'} is still in progress. Class-wide stats and
          charts unlock once the exam window closes for everyone, so nobody can learn anything about the exam
          while other candidates are still taking it.
        </p>
        {endTime && (
          <p className="mt-3 text-xs font-semibold text-blue-700">Available after {endTime.toLocaleString()}</p>
        )}
        <Link
          to="/"
          className="mt-6 inline-flex items-center gap-2 rounded-xl bg-blue-600 px-6 py-2.5 text-sm font-bold text-white transition hover:bg-blue-700"
        >
          <ArrowLeft className="h-4 w-4" /> Back to Dashboard
        </Link>
      </div>
    </div>
  );
}

export default function Analytics() {
  const { examId } = useParams();
  const navigate = useNavigate();
  const { user } = useAuth();
  const isFaculty = user?.user_type === 'faculty';

  const [stats, setStats] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [insightExams, setInsightExams] = useState([]);

  // Faculty-only filterable student list (same filter idea as the Result tab)
  const [roster, setRoster] = useState([]);
  const [rosterLoading, setRosterLoading] = useState(false);
  const [minScore, setMinScore] = useState('');
  const [maxScore, setMaxScore] = useState('');
  const [studentSearch, setStudentSearch] = useState('');

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const res = await api.get(`exams/${examId}/analytics/`);
        if (!cancelled) setStats(res.data);
      } catch (err) {
        if (!cancelled) setError(err.response?.data?.error || 'Could not load analytics.');
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => { cancelled = true; };
  }, [examId]);

  useEffect(() => {
    api.get('results/').then((res) => {
      const byExam = new Map((res.data.results || []).map((row) => [row.exam_id, row]));
      setInsightExams([...byExam.values()]);
    }).catch(() => setInsightExams([]));
  }, []);

  useEffect(() => {
    if (!isFaculty) return;
    let cancelled = false;
    setRosterLoading(true);
    (async () => {
      try {
        const res = await api.get(`exams/${examId}/roster/`);
        if (!cancelled) setRoster(res.data.roster || []);
      } catch {
        if (!cancelled) setRoster([]);
      } finally {
        if (!cancelled) setRosterLoading(false);
      }
    })();
    return () => { cancelled = true; };
  }, [examId, isFaculty]);

  const filteredRoster = useMemo(() => {
    return roster.filter((r) => {
      if (r.total_score === null || r.total_score === undefined) return false; // only evaluated students
      if (minScore !== '' && r.total_score < Number(minScore)) return false;
      if (maxScore !== '' && r.total_score > Number(maxScore)) return false;
      if (studentSearch.trim()) {
        const q = studentSearch.trim().toLowerCase();
        if (!r.name?.toLowerCase().includes(q) && !r.enrollment_no?.toLowerCase().includes(q)) return false;
      }
      return true;
    });
  }, [roster, minScore, maxScore, studentSearch]);

  const prepared = useMemo(() => {
    if (!stats) return null;
    const appeared = stats.total_appeared || 0;
    return {
      appeared,
      totalMarks: Number(stats.total_marks || 0),
      passRate: appeared ? Math.round(((stats.passed_count || 0) / appeared) * 100) : 0,
      questions: stats.question_stats || [],
      charts: stats.chart_images || {},
    };
  }, [stats]);

  if (loading) {
    return (
      <div className="flex min-h-[70vh] items-center justify-center">
        <Loader2 className="h-12 w-12 animate-spin text-blue-600" />
      </div>
    );
  }

  if (error || !stats || !prepared) {
    return (
      <div className="mx-auto max-w-2xl px-4 py-16">
        <div className="rounded-3xl border border-rose-200 bg-rose-50 p-8 text-center">
          <AlertCircle className="mx-auto mb-3 h-12 w-12 text-rose-500" />
          <h2 className="text-lg font-bold text-rose-900">Analytics Unavailable</h2>
          <p className="mt-1 text-sm text-rose-700">{error || 'No data returned.'}</p>
          <Link to="/" className="mt-5 inline-flex items-center gap-2 rounded-xl bg-rose-600 px-6 py-2.5 text-sm font-bold text-white">
            <ArrowLeft className="h-4 w-4" /> Back to Dashboard
          </Link>
        </div>
      </div>
    );
  }

  if (stats.results_released === false) {
    return <AnalyticsPending stats={stats} />;
  }

  const { appeared, totalMarks, charts } = prepared;
  const completionRate = stats.total_registered ? Math.round((appeared / stats.total_registered) * 100) : 0;

  return (
    <div className="app-page analytics-page">
      <header className="analytics-hero">
        <div className="analytics-hero-top">
          <span className="app-badge">
            Live Analytics
          </span>
          <Link to="/" className="analytics-hero-back">
            <Home className="h-4 w-4" /> Home
          </Link>
        </div>
        <div>
          <h1>{stats.exam_title}</h1>
          <p>
            {isFaculty
              ? 'Cohort performance dashboard — every chart below is rendered server-side with matplotlib/seaborn.'
              : 'Anonymous cohort-level charts. Other students’ marks and identities remain hidden.'}
          </p>
          <div className="mt-4 flex flex-wrap items-center gap-2">
            <label htmlFor="insight-exam" className="analytics-exam-label">Assessment</label>
            <select id="insight-exam" value={examId} onChange={(event) => navigate(`/exam/${event.target.value}/analytics`)} className="analytics-exam-select">
              {insightExams.map((item) => <option key={item.exam_id} value={item.exam_id}>{item.exam_title} {item.subject ? `(${item.subject})` : ''}</option>)}
            </select>
          </div>
        </div>
      </header>

      {!isFaculty && (
        <div className="flex items-start gap-3 rounded-2xl border border-blue-200 bg-blue-50 p-4">
          <Lock className="mt-0.5 h-5 w-5 flex-shrink-0 text-blue-600" />
          <p className="text-sm text-blue-900">
            <b>Privacy:</b> charts are aggregate-only. Other candidates’ names and marks are never exposed;
            your own score is shown separately below.
          </p>
        </div>
      )}

      {appeared === 0 ? (
        <div className="rounded-3xl border border-slate-200 bg-white p-16 text-center shadow-sm">
          <BarChart2 className="mx-auto mb-3 h-14 w-14 text-slate-300" />
          <p className="text-lg font-semibold text-slate-700">No evaluated submissions yet.</p>
          <p className="mt-1 text-sm text-slate-400">The dashboard will populate immediately after candidates submit.</p>
        </div>
      ) : (
        <>
          {!isFaculty && stats.my_scores && (
            <section className="rounded-3xl border border-blue-200 bg-gradient-to-r from-blue-50 to-indigo-50 p-6 shadow-sm">
              <h2 className="mb-4 flex items-center gap-2 text-base font-black text-slate-900">
                <Target className="h-5 w-5 text-blue-600" /> Your Performance Snapshot
              </h2>
              <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
                <StatCard label="Your Score" value={stats.my_scores.total_score} suffix={`/${totalMarks}`} icon={Award} tone={stats.my_scores.is_passed ? 'emerald' : 'rose'} />
                <StatCard label="Your %" value={stats.my_scores.percentage} suffix="%" icon={TrendingUp} tone="blue" />
                <StatCard label="Result" value={stats.my_scores.is_passed ? 'Passed' : 'Failed'} icon={stats.my_scores.is_passed ? CheckCircle2 : XCircle} tone={stats.my_scores.is_passed ? 'emerald' : 'rose'} />
              </div>
            </section>
          )}

          {isFaculty && (
            <div className="grid grid-cols-2 gap-4 md:grid-cols-3 xl:grid-cols-6">
              <StatCard label="Registered" value={stats.total_registered} icon={Users} tone="slate" />
              <StatCard label="Appeared" value={appeared} icon={Users} tone="blue" />
              <StatCard label="Passed" value={stats.passed_count} icon={CheckCircle2} tone="emerald" />
              <StatCard label="Failed" value={stats.failed_count} icon={XCircle} tone="rose" />
              <StatCard label="Average" value={stats.avg_score} icon={Activity} tone="purple" />
              <StatCard label="Median" value={stats.median_score} icon={Target} tone="amber" />
            </div>
          )}

          {/* Simple non-chart stat rail — completion rate + score markers */}
          <div className="grid grid-cols-1 gap-6 lg:grid-cols-4">
            {isFaculty && (
              <div className="rounded-3xl border border-slate-200 bg-white p-6 shadow-sm lg:col-span-1">
                <h3 className="mb-3 flex items-center gap-2 text-base font-black text-slate-900">
                  <Activity className="h-5 w-5 text-slate-600" /> Completion
                </h3>
                <div className="mt-2 text-3xl font-black text-blue-600">{completionRate}%</div>
                <div className="mt-3 h-2.5 w-full overflow-hidden rounded-full bg-slate-100">
                  <div className="h-full rounded-full bg-blue-600 transition-all" style={{ width: `${completionRate}%` }} />
                </div>
                <p className="mt-2 text-xs text-slate-500">{appeared} of {stats.total_registered || appeared} registered candidates evaluated</p>
              </div>
            )}

            <div className={`rounded-3xl border border-slate-200 bg-white p-6 shadow-sm ${isFaculty ? 'lg:col-span-3' : 'lg:col-span-4'}`}>
              <h3 className="mb-4 flex items-center gap-2 text-base font-black text-slate-900">
                <TrendingUp className="h-5 w-5 text-slate-600" /> Score Markers
              </h3>
              <div className="grid grid-cols-2 gap-4 sm:grid-cols-5">
                {[
                  ['Lowest', stats.lowest_score, 'rose'],
                  ['Average', stats.avg_score, 'slate'],
                  ['Median', stats.median_score, 'purple'],
                  ...(stats.my_scores ? [['You', stats.my_scores.total_score, 'blue']] : []),
                  ['Highest', stats.highest_score, 'emerald'],
                ].map(([label, value, tone]) => {
                  const tones = {
                    rose: 'text-rose-600', slate: 'text-slate-700', purple: 'text-purple-600',
                    blue: 'text-blue-600', emerald: 'text-emerald-600',
                  };
                  return (
                    <div key={label} className="rounded-2xl bg-slate-50 p-4 text-center">
                      <div className="text-[11px] font-bold uppercase tracking-wide text-slate-500">{label}</div>
                      <div className={`mt-1 text-xl font-black ${tones[tone]}`}>{fmt(value, 1)}</div>
                      <div className="text-[11px] text-slate-400">/ {totalMarks}</div>
                    </div>
                  );
                })}
              </div>
            </div>
          </div>

          <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
            <ChartCard className="lg:col-span-2" title="Score Distribution" subtitle="Candidates grouped by total percentage bands." icon={BarChart2}>
              <ChartImage src={charts.score_distribution} alt="Matplotlib score distribution chart" noDataLabel="No evaluated submissions yet." />
            </ChartCard>

            <ChartCard title="Pass vs Fail" subtitle={`${prepared.passRate}% pass rate`} icon={PieIcon}>
              <ChartImage src={charts.pass_fail} alt="Matplotlib pass versus fail chart" noDataLabel="No evaluated submissions yet." />
            </ChartCard>
          </div>

          <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
            <ChartCard title="Section Performance" subtitle="Average achievement as a percentage of each section’s maximum marks." icon={Activity}>
              <ChartImage src={charts.section_comparison} alt="Matplotlib section performance chart" noDataLabel="No section performance data yet." />
            </ChartCard>

            <ChartCard title="Coding Logic Verdicts" subtitle="Automated evaluator outcomes across all coding submissions." icon={PieIcon}>
              <ChartImage src={charts.coding_breakdown} alt="Matplotlib coding verdict chart" noDataLabel="No coding submissions evaluated yet." />
            </ChartCard>
          </div>

          <ChartCard title="Per-Question Accuracy" subtitle="MCQ accuracy by question." icon={Target}>
            <MetricBars
              percent
              data={(prepared.questions || []).map((row) => ({
                label: `${row.label} · ${row.question_text}`, value: row.accuracy_percent,
                color: row.accuracy_percent >= 70 ? 'bg-emerald-500' : row.accuracy_percent >= 40 ? 'bg-amber-500' : 'bg-rose-500',
              }))}
              emptyLabel="No MCQ responses evaluated yet."
            />
          </ChartCard>

          {stats.problem_stats?.length > 0 && (
            <ChartCard title="Coding Problem Breakdown" subtitle="Stacked verdict counts per problem." icon={BarChart2}>
              <div className="space-y-5">
                {stats.problem_stats.map((problem) => {
                  const total = Math.max(problem.submissions || 0, 1);
                  return <div key={problem.id}><div className="mb-2 flex items-center justify-between gap-4 text-xs"><span className="font-semibold text-slate-700 dark:text-slate-200">{problem.title}</span><span className="text-slate-500">{problem.submissions} submissions</span></div><div className="flex h-3 overflow-hidden rounded-full bg-slate-100 dark:bg-slate-700"><span className="bg-emerald-500" style={{ width: `${(problem.correct / total) * 100}%` }} /><span className="bg-amber-500" style={{ width: `${(problem.partial / total) * 100}%` }} /><span className="bg-rose-500" style={{ width: `${(problem.incorrect / total) * 100}%` }} /></div></div>;
                })}
                <div className="flex flex-wrap gap-4 text-xs text-slate-500"><span><i className="mr-1 inline-block h-2 w-2 rounded-full bg-emerald-500" />Correct</span><span><i className="mr-1 inline-block h-2 w-2 rounded-full bg-amber-500" />Partial</span><span><i className="mr-1 inline-block h-2 w-2 rounded-full bg-rose-500" />Incorrect</span></div>
              </div>
            </ChartCard>
          )}

          {prepared.questions.length > 0 && (
            <section className="overflow-hidden rounded-3xl border border-slate-200 bg-white shadow-sm">
              <div className="border-b border-slate-200 p-6">
                <h3 className="text-base font-black text-slate-900">Question-Level Detail</h3>
                <p className="mt-0.5 text-xs text-slate-500">Faculty can see the answer key; students only see aggregate accuracy.</p>
              </div>
              <div className="overflow-x-auto">
                <table className="w-full text-left text-sm">
                  <thead className="bg-slate-50 text-xs font-bold uppercase tracking-wide text-slate-600">
                    <tr>
                      <th className="px-6 py-3">#</th>
                      <th className="px-6 py-3">Question</th>
                      {isFaculty && <th className="px-6 py-3 text-center">Key</th>}
                      <th className="px-6 py-3 text-center">Attempted</th>
                      <th className="px-6 py-3 text-center">Correct</th>
                      <th className="px-6 py-3 text-center">Incorrect</th>
                      <th className="px-6 py-3 text-right">Accuracy</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-100">
                    {prepared.questions.map((q) => (
                      <tr key={q.id} className={Number(q.accuracy_percent || 0) < 40 ? 'bg-rose-50/50' : ''}>
                        <td className="px-6 py-3 font-black text-slate-500">{q.label}</td>
                        <td className="max-w-md px-6 py-3 text-slate-800">{q.question_text}</td>
                        {isFaculty && (
                          <td className="px-6 py-3 text-center">
                            <span className="rounded-lg bg-slate-900 px-2.5 py-1 font-mono text-xs font-black text-white">{q.correct_option}</span>
                          </td>
                        )}
                        <td className="px-6 py-3 text-center font-semibold text-slate-700">{q.attempted}</td>
                        <td className="px-6 py-3 text-center font-semibold text-emerald-700">{q.correct_responses}</td>
                        <td className="px-6 py-3 text-center font-semibold text-rose-700">{q.incorrect_responses}</td>
                        <td className="px-6 py-3 text-right font-mono font-black text-slate-900">{fmt(q.accuracy_percent, 1)}%</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </section>
          )}
          {isFaculty && (
            <section className="overflow-hidden rounded-3xl border border-slate-200 bg-white shadow-sm">
              <div className="border-b border-slate-200 p-6">
                <h3 className="flex items-center gap-2 text-base font-black text-slate-900">
                  <Users className="h-5 w-5 text-indigo-600" /> Student List
                </h3>
                <p className="mt-0.5 text-xs text-slate-500">Filter this exam's evaluated candidates, then open a full analysis for any one of them.</p>
                <div className="mt-4 flex flex-wrap items-center gap-3">
                  <input type="number" placeholder="Min score" value={minScore} onChange={(e) => setMinScore(e.target.value)}
                    className="w-28 rounded-xl border border-slate-300 px-3 py-2 text-sm font-mono" />
                  <input type="number" placeholder="Max score" value={maxScore} onChange={(e) => setMaxScore(e.target.value)}
                    className="w-28 rounded-xl border border-slate-300 px-3 py-2 text-sm font-mono" />
                  <div className="relative flex-1 min-w-[200px]">
                    <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400" />
                    <input type="text" placeholder="Search name or enrollment no." value={studentSearch}
                      onChange={(e) => setStudentSearch(e.target.value)}
                      className="w-full rounded-xl border border-slate-300 py-2 pl-9 pr-3 text-sm" />
                  </div>
                </div>
              </div>
              {rosterLoading ? (
                <div className="flex items-center justify-center p-10"><Loader2 className="h-6 w-6 animate-spin text-indigo-600" /></div>
              ) : filteredRoster.length === 0 ? (
                <div className="p-10 text-center text-sm text-slate-400">No evaluated students match these filters.</div>
              ) : (
                <div className="overflow-x-auto">
                  <table className="w-full text-left text-sm">
                    <thead className="bg-slate-50 text-xs font-bold uppercase tracking-wide text-slate-500">
                      <tr>
                        <th className="px-6 py-3">Student</th>
                        <th className="px-6 py-3 text-right">Score</th>
                        <th className="px-6 py-3 text-right">%</th>
                        <th className="px-6 py-3 text-center">Result</th>
                        <th className="px-6 py-3 text-center">Analysis</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-slate-100">
                      {filteredRoster.map((r) => (
                        <tr key={r.student_id} className={r.status === 'ufm' ? 'bg-rose-50/50' : ''}>
                          <td className="px-6 py-3">
                            <div className="font-semibold text-slate-800">{r.name}</div>
                            <div className="text-xs text-slate-400">{r.enrollment_no}</div>
                          </td>
                          <td className="px-6 py-3 text-right font-mono font-bold">{r.total_score}</td>
                          <td className="px-6 py-3 text-right font-mono font-bold text-blue-600">{r.percentage}%</td>
                          <td className="px-6 py-3 text-center">
                            {r.status === 'ufm' ? (
                              <span className="rounded-full bg-rose-100 px-2.5 py-1 text-xs font-bold text-rose-700">UFM</span>
                            ) : r.is_passed ? (
                              <span className="rounded-full bg-emerald-100 px-2.5 py-1 text-xs font-bold text-emerald-700">Pass</span>
                            ) : (
                              <span className="rounded-full bg-rose-100 px-2.5 py-1 text-xs font-bold text-rose-700">Fail</span>
                            )}
                          </td>
                          <td className="px-6 py-3 text-center">
                            <Link
                              to={`/faculty/exam/${examId}/student/${r.student_id}/analysis`}
                              className="inline-flex items-center gap-1 rounded-lg bg-indigo-50 px-2.5 py-1.5 text-xs font-bold text-indigo-700 hover:bg-indigo-100"
                            >
                              <BarChart3 className="h-3.5 w-3.5" /> Analysis
                            </Link>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </section>
          )}
        </>
      )}
    </div>
  );
}

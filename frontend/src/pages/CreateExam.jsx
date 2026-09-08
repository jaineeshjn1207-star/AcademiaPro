import React, { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import api from '../api/axios';
import { useAuth } from '../context/AuthContext';
import { PlusCircle, ArrowLeft, ShieldCheck, AlertCircle, FileEdit, Calendar, Award, BookOpen } from 'lucide-react';
import './workflow-page.css';

const PHASES = ['T1', 'T2', 'T3', 'T4'];

export default function CreateExam() {
  const navigate = useNavigate();
  const { user } = useAuth();

  const [title, setTitle] = useState('');
  const [description, setDescription] = useState('');
  const [subject, setSubject] = useState('');
  const [phase, setPhase] = useState('');
  const [audience, setAudience] = useState('all');
  const [passingMarks, setPassingMarks] = useState(35);
  const [totalMarks, setTotalMarks] = useState(80);
  const assignedSubjects = (user?.faculty_subjects || '')
    .split(',').map((item) => item.trim()).filter(Boolean);

  // Faculty accounts receive their assignment after login, so set the
  // subject once that profile information is available.
  useEffect(() => {
    if (assignedSubjects.length === 1) setSubject(assignedSubjects[0]);
    else if (assignedSubjects.length && !assignedSubjects.includes(subject)) setSubject('');
  }, [user?.faculty_subjects]);
  
  // Format datetime for datetime-local input
  const getDatetimeStr = (offsetHours = 0) => {
    const now = new Date(Date.now() + offsetHours * 3600 * 1000);
    now.setMinutes(now.getMinutes() - now.getTimezoneOffset());
    return now.toISOString().slice(0, 16);
  };

  const initialStart = getDatetimeStr(0);
  const initialEnd = getDatetimeStr(5);
  const windowMinutesBetween = (startStr, endStr) => {
    const diffMs = new Date(endStr) - new Date(startStr);
    if (Number.isNaN(diffMs) || diffMs <= 0) return 0;
    return Math.round(diffMs / 60000);
  };

  const [startTime, setStartTime] = useState(initialStart);
  const [endTime, setEndTime] = useState(initialEnd);
  // Duration defaults to (and stays in sync with) the start→end window, unless
  // the faculty member explicitly overrides it to give a shorter fixed duration.
  const [duration, setDuration] = useState(windowMinutesBetween(initialStart, initialEnd) || 90);
  const [durationTouched, setDurationTouched] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  const handleStartTimeChange = (value) => {
    setStartTime(value);
    if (!durationTouched) {
      const mins = windowMinutesBetween(value, endTime);
      if (mins > 0) setDuration(mins);
    }
  };

  const handleEndTimeChange = (value) => {
    setEndTime(value);
    if (!durationTouched) {
      const mins = windowMinutesBetween(startTime, value);
      if (mins > 0) setDuration(mins);
    }
  };

  const handleDurationChange = (value) => {
    setDurationTouched(true);
    setDuration(value);
  };

  const resetDurationToWindow = () => {
    const mins = windowMinutesBetween(startTime, endTime);
    if (mins > 0) setDuration(mins);
    setDurationTouched(false);
  };

  const currentWindowMinutes = windowMinutesBetween(startTime, endTime);

  // Proctoring / anti-cheat configuration
  const [enforceFullscreen, setEnforceFullscreen] = useState(true);
  const [blockShortcuts, setBlockShortcuts] = useState(true);
  const [blockCopyPaste, setBlockCopyPaste] = useState(true);
  const [requireScreenRecording, setRequireScreenRecording] = useState(true);
  const [autoSubmitOnViolation, setAutoSubmitOnViolation] = useState(true);
  const [maxViolations, setMaxViolations] = useState(3);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');

    // ---- client-side validation ----
    const start = new Date(startTime);
    const end = new Date(endTime);
    if (Number.isNaN(start.getTime()) || Number.isNaN(end.getTime())) {
      setError('Please provide a valid start and end time.');
      return;
    }
    if (end <= start) {
      setError('The exam end time must be after the start time.');
      return;
    }
    const windowMinutes = (end - start) / 60000;
    if (Number(duration) > windowMinutes) {
      setError(`Duration (${duration} min) cannot exceed the exam window (${Math.floor(windowMinutes)} min).`);
      return;
    }
    if (Number(passingMarks) > Number(totalMarks)) {
      setError('Passing marks cannot be greater than total marks.');
      return;
    }
    if (Number(duration) <= 0 || Number(totalMarks) <= 0) {
      setError('Duration and total marks must be greater than zero.');
      return;
    }

    setLoading(true);
    try {
      const res = await api.post('exams/', {
        title,
        description,
        subject: subject.trim(),
        audience,
        target_branch: audience === 'department' ? (user?.branch || '') : '',
        phase,
        duration_minutes: parseInt(duration),
        passing_marks: parseFloat(passingMarks),
        total_marks: parseFloat(totalMarks),
        start_time: new Date(startTime).toISOString(),
        end_time: new Date(endTime).toISOString(),
        requires_otp: true,
        enforce_fullscreen: enforceFullscreen,
        block_shortcuts: blockShortcuts,
        block_copy_paste: blockCopyPaste,
        require_screen_recording: requireScreenRecording,
        auto_submit_on_violation: autoSubmitOnViolation,
        max_violations: parseInt(maxViolations, 10) || 0,
      });
      navigate(`/faculty/exam/${res.data.id}/manage`);
    } catch (err) {
      const d = err.response?.data;
      setError(
        d?.error ||
        (d && typeof d === 'object'
          ? Object.entries(d).map(([k, v]) => `${k}: ${Array.isArray(v) ? v.join(', ') : v}`).join(' | ')
          : 'Failed to create examination.')
      );
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="app-page workflow-page create-exam-page">

      <div className="flex items-center space-x-4">
        <button
          onClick={() => navigate('/')}
          className="p-2 bg-white rounded-xl shadow-sm border border-slate-200 hover:bg-slate-50 transition"
        >
          <ArrowLeft className="w-5 h-5 text-slate-600" />
        </button>
        <div>
          <h1 className="flex items-center gap-2 text-2xl font-black text-slate-900">
            <FileEdit className="h-6 w-6 text-amber-600" /> Exam Settings
          </h1>
          <p className="text-sm text-slate-500">Set up the exam here, then add questions and publish once marks add up exactly.</p>
        </div>
      </div>

      <div className="rounded-3xl border border-slate-200 bg-white p-8 shadow-xl">
        {error && (
          <div className="mb-6 flex items-start gap-3 rounded-xl border border-rose-200 bg-rose-50 p-4 text-sm text-rose-700">
            <AlertCircle className="mt-0.5 h-4 w-4 flex-shrink-0" />
            <span>{error}</span>
          </div>
        )}

        <form onSubmit={handleSubmit} className="space-y-8">
          {/* ---------- Basics ---------- */}
          <div className="space-y-5">
            <div className="flex items-center gap-2 text-sm font-black uppercase tracking-wide text-slate-400">
              <BookOpen className="h-4 w-4" /> Basics
            </div>

            <div>
              <label className="block text-sm font-semibold text-slate-700">Examination Title</label>
              <input
                type="text"
                required
                value={title}
                onChange={(e) => setTitle(e.target.value)}
                placeholder="e.g. End-Semester Advanced Algorithms & Data Structures Exam"
                className="mt-1 block w-full px-4 py-3 border border-slate-300 rounded-xl focus:ring-2 focus:ring-amber-500 focus:border-amber-500 text-sm"
              />
            </div>

            <div>
              <label className="block text-sm font-semibold text-slate-700">Description &amp; Instructions</label>
              <textarea
                rows="3"
                value={description}
                onChange={(e) => setDescription(e.target.value)}
                placeholder="Provide instructions regarding randomized MCQs and algorithm code evaluation policy..."
                className="mt-1 block w-full px-4 py-3 border border-slate-300 rounded-xl focus:ring-2 focus:ring-amber-500 focus:border-amber-500 text-sm"
              />
            </div>

            <div className="grid grid-cols-1 gap-6 md:grid-cols-2">
              <div>
                <label className="block text-sm font-semibold text-slate-700">Subject</label>
                {assignedSubjects.length ? (
                  <select
                    required
                    value={subject}
                    onChange={(e) => setSubject(e.target.value)}
                    className="mt-1 block w-full rounded-xl border border-slate-300 px-4 py-2.5 text-sm focus:border-amber-500 focus:ring-2 focus:ring-amber-500"
                  >
                    {assignedSubjects.length > 1 && <option value="">Choose your assigned subject</option>}
                    {assignedSubjects.map((item) => <option key={item} value={item}>{item}</option>)}
                  </select>
                ) : (
                  <input
                    type="text"
                    required
                    value={subject}
                    onChange={(e) => setSubject(e.target.value)}
                    placeholder="e.g. Data Structures"
                    className="mt-1 block w-full px-4 py-2.5 border border-slate-300 rounded-xl focus:ring-2 focus:ring-amber-500 focus:border-amber-500 text-sm"
                  />
                )}
                <p className="mt-1 text-xs text-slate-400">
                  {assignedSubjects.length ? 'This exam is limited to your assigned subject.' : 'No subject is assigned to this faculty account yet.'}
                </p>
              </div>
              <div>
                <label className="block text-sm font-semibold text-slate-700">Test Phase</label>
                <div className="mt-1 grid grid-cols-4 gap-2">
                  {PHASES.map((p) => (
                    <button key={p} type="button" onClick={() => setPhase(phase === p ? '' : p)}
                      className={`rounded-xl border py-2.5 text-sm font-bold transition ${
                        phase === p
                          ? 'border-amber-500 bg-amber-50 text-amber-700'
                          : 'border-slate-300 text-slate-500 hover:border-amber-300'
                      }`}>
                      {p}
                    </button>
                  ))}
                </div>
              </div>
            </div>
            <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
              <div>
                <label className="block text-sm font-semibold text-slate-700">Student audience</label>
                <select value={audience} onChange={(e) => setAudience(e.target.value)} className="mt-1 block w-full rounded-xl border border-slate-300 px-4 py-2.5 text-sm">
                  <option value="all">All students</option><option value="department">My branch only</option>
                </select>
              </div>
              {audience === 'department' && <div><label className="block text-sm font-semibold text-slate-700">Branch</label><input value={user?.branch || ''} readOnly className="mt-1 block w-full rounded-xl border border-slate-300 bg-slate-100 px-4 py-2.5 text-sm" /></div>}
            </div>
          </div>

          {/* ---------- Schedule ---------- */}
          <div className="space-y-5 border-t border-slate-100 pt-6">
            <div className="flex items-center gap-2 text-sm font-black uppercase tracking-wide text-slate-400">
              <Calendar className="h-4 w-4" /> Schedule
            </div>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
              <div>
                <label className="block text-sm font-semibold text-slate-700">Start Time (Exam Window Opens)</label>
                <input
                  type="datetime-local"
                  required
                  value={startTime}
                  onChange={(e) => handleStartTimeChange(e.target.value)}
                  className="mt-1 block w-full px-4 py-2.5 border border-slate-300 rounded-xl focus:ring-2 focus:ring-amber-500 focus:border-amber-500 text-sm"
                />
              </div>

              <div>
                <label className="block text-sm font-semibold text-slate-700">End Time (Exam Window Closes)</label>
                <input
                  type="datetime-local"
                  required
                  value={endTime}
                  onChange={(e) => handleEndTimeChange(e.target.value)}
                  className="mt-1 block w-full px-4 py-2.5 border border-slate-300 rounded-xl focus:ring-2 focus:ring-amber-500 focus:border-amber-500 text-sm"
                />
              </div>
            </div>
          </div>

          {/* ---------- Marks ---------- */}
          <div className="space-y-5 border-t border-slate-100 pt-6">
            <div className="flex items-center gap-2 text-sm font-black uppercase tracking-wide text-slate-400">
              <Award className="h-4 w-4" /> Marks &amp; Duration
            </div>
            <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
              <div>
                <label className="block text-sm font-semibold text-slate-700">Duration (Minutes)</label>
                <input
                  type="number"
                  required
                  value={duration}
                  onChange={(e) => handleDurationChange(e.target.value)}
                  className="mt-1 block w-full px-4 py-2.5 border border-slate-300 rounded-xl focus:ring-2 focus:ring-amber-500 focus:border-amber-500 text-sm font-mono font-bold"
                />
                <p className="mt-1 text-xs text-slate-400">
                  {durationTouched
                    ? `Custom duration — your window is ${currentWindowMinutes} min. `
                    : `Auto-matched to your ${currentWindowMinutes} min window. `}
                  {durationTouched && (
                    <button type="button" onClick={resetDurationToWindow} className="font-semibold text-amber-600 hover:underline">
                      Reset to window length
                    </button>
                  )}
                </p>
              </div>

              <div>
                <label className="block text-sm font-semibold text-slate-700">Total Marks</label>
                <input
                  type="number"
                  required
                  value={totalMarks}
                  onChange={(e) => setTotalMarks(e.target.value)}
                  className="mt-1 block w-full px-4 py-2.5 border border-slate-300 rounded-xl focus:ring-2 focus:ring-amber-500 focus:border-amber-500 text-sm font-mono font-bold"
                />
              </div>

              <div>
                <label className="block text-sm font-semibold text-slate-700">Passing Marks</label>
                <input
                  type="number"
                  required
                  value={passingMarks}
                  onChange={(e) => setPassingMarks(e.target.value)}
                  className="mt-1 block w-full px-4 py-2.5 border border-slate-300 rounded-xl focus:ring-2 focus:ring-amber-500 focus:border-amber-500 text-sm font-mono font-bold"
                />
              </div>
            </div>
          </div>

          {/* ---------- Proctoring & Anti-Cheat ---------- */}
          <div className="rounded-2xl border border-slate-200 bg-slate-50 p-6">
            <div className="mb-4 flex items-center gap-2">
              <ShieldCheck className="h-5 w-5 text-emerald-600" />
              <h3 className="text-base font-bold text-slate-800">Proctoring &amp; Anti-Cheat</h3>
            </div>

            <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
              {[
                [enforceFullscreen, setEnforceFullscreen, 'Enforce fullscreen', 'Exam auto-enters fullscreen; exiting is blocked and logged.'],
                [requireScreenRecording, setRequireScreenRecording, 'Require compulsory screen recording',
                  (on) => on
                    ? 'Student must share their entire screen before the exam can start; refusing blocks entry.'
                    : 'Off — students go straight into the exam. No screen-share prompt will appear.'],
                [blockShortcuts, setBlockShortcuts, 'Block keyboard shortcuts', 'Disables Esc, F11, F12, Ctrl+T/N/W/R/P, Alt+Tab and DevTools.'],
                [blockCopyPaste, setBlockCopyPaste, 'Block copy / paste / right-click', 'Prevents copying questions or pasting external solutions.'],
                [autoSubmitOnViolation, setAutoSubmitOnViolation, 'Void & lock on violation limit', 'Zeroes marks as unfair means and locks the account once the limit is reached.'],
              ].map(([value, setter, label, help]) => (
                <label key={label} className={`flex cursor-pointer items-start gap-3 rounded-xl border p-4 transition ${
                  value ? 'border-emerald-200 bg-emerald-50/40 hover:border-emerald-300' : 'border-slate-200 bg-white hover:border-emerald-300'
                }`}>
                  <input
                    type="checkbox"
                    checked={value}
                    onChange={(e) => setter(e.target.checked)}
                    className="mt-0.5 h-4 w-4 flex-shrink-0 rounded accent-emerald-600"
                  />
                  <span>
                    <span className="flex items-center gap-1.5 text-sm font-semibold text-slate-800">
                      {label}
                      <span className={`rounded-full px-1.5 py-0.5 text-[10px] font-black uppercase tracking-wide ${
                        value ? 'bg-emerald-100 text-emerald-700' : 'bg-slate-100 text-slate-400'
                      }`}>
                        {value ? 'On' : 'Off'}
                      </span>
                    </span>
                    <span className="mt-0.5 block text-xs leading-relaxed text-slate-500">
                      {typeof help === 'function' ? help(value) : help}
                    </span>
                  </span>
                </label>
              ))}
            </div>

            <div className="mt-4 flex flex-wrap items-end gap-4">
              <div>
                <label className="block text-sm font-semibold text-slate-700">Violation limit</label>
                <input
                  type="number"
                  min="0"
                  value={maxViolations}
                  onChange={(e) => setMaxViolations(e.target.value)}
                  disabled={!autoSubmitOnViolation}
                  className="mt-1 w-32 rounded-xl border border-slate-300 px-4 py-2.5 font-mono text-sm font-bold focus:border-emerald-500 focus:ring-2 focus:ring-emerald-100 disabled:bg-slate-100"
                />
              </div>
              <p className="flex items-start gap-1.5 pb-2 text-xs text-slate-500">
                <AlertCircle className="mt-0.5 h-3.5 w-3.5 flex-shrink-0" />
                Set to 0 for unlimited. Fullscreen exits and tab switches count as high-severity violations. Hitting
                the limit voids the paper to zero and locks the student's account until faculty restores it.
              </p>
            </div>
          </div>

          <div className="pt-4 flex justify-end gap-3">
            <button
              type="button"
              onClick={() => navigate('/')}
              className="px-6 py-3 bg-slate-100 hover:bg-slate-200 text-slate-700 font-bold rounded-xl text-sm transition"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={loading}
              className="px-8 py-3 bg-amber-600 hover:bg-amber-700 text-white font-bold rounded-xl shadow-lg transition flex items-center gap-2 text-sm disabled:opacity-60"
            >
              <PlusCircle className="w-4 h-4" /> {loading ? 'Saving...' : 'Save & Add Questions'}
            </button>
          </div>
        </form>
      </div>

    </div>
  );
}

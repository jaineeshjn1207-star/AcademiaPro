import React, { useState, useEffect, useCallback, useRef } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import api from '../api/axios';
import { useAuth } from '../context/AuthContext';
import useProctoring from '../hooks/useProctoring';
import useScreenRecording from '../hooks/useScreenRecording';
import './secure-exam.css';
import {
  Clock, CheckCircle2, AlertCircle, Code, HelpCircle, Send, Terminal,
  Maximize, ShieldAlert, ShieldCheck, Eye, Loader2, Save, ChevronLeft,
  ChevronRight, ListChecks, Play, Lock, FilePlus, FolderPlus, Folder,
  FileText, Trash2,
} from 'lucide-react';

const AUTOSAVE_MS = 15000;

const DEFAULT_FILE_BY_LANGUAGE = {
  python: 'main.py', javascript: 'index.js', cpp: 'main.cpp', java: 'Main.java',
};

const starterCodeForProblem = (p) => {
  const stubs = {
    python: `# ${p.title}\n# Write your solution below.\n\ndef solution():\n    `,
    javascript: `// ${p.title}\n// Write your solution below.\n\nfunction solution() {\n  \n}\n`,
    cpp: `// ${p.title}\n#include <bits/stdc++.h>\nusing namespace std;\n\nint main() {\n    \n    return 0;\n}\n`,
    java: `// ${p.title}\npublic class Main {\n    public static void main(String[] args) {\n        \n    }\n}\n`,
  };
  return stubs[p.language] || stubs.python;
};

const normalizeWorkspacePath = (value) => String(value || '')
  .replace(/\\/g, '/')
  .split('/')
  .map((part) => part.trim())
  .filter(Boolean)
  .join('/');

const parentFoldersForPath = (path) => {
  const parts = normalizeWorkspacePath(path).split('/').filter(Boolean);
  parts.pop();
  const folders = [];
  parts.reduce((prefix, part) => {
    const next = prefix ? `${prefix}/${part}` : part;
    folders.push(next);
    return next;
  }, '');
  return folders;
};

const normalizeWorkspaceFiles = (items = []) => {
  const byPath = new Map();
  (Array.isArray(items) ? items : []).forEach((item) => {
    if (!item || typeof item !== 'object') return;
    const path = normalizeWorkspacePath(item.path);
    if (!path) return;
    const type = item.type === 'folder' ? 'folder' : 'file';
    byPath.set(path, { type, path, content: type === 'file' ? String(item.content || '') : '' });
  });
  Array.from(byPath.values()).forEach((item) => {
    if (item.type === 'file') {
      parentFoldersForPath(item.path).forEach((folderPath) => {
        if (!byPath.has(folderPath)) byPath.set(folderPath, { type: 'folder', path: folderPath, content: '' });
      });
    }
  });
  return Array.from(byPath.values()).sort((a, b) => {
    const aDepth = a.path.split('/').length;
    const bDepth = b.path.split('/').length;
    if (a.path === b.path) return 0;
    if (aDepth !== bDepth && (a.path.startsWith(`${b.path}/`) || b.path.startsWith(`${a.path}/`))) {
      return aDepth - bDepth;
    }
    return a.path.localeCompare(b.path);
  });
};

const serializeWorkspaceFiles = (items = []) => normalizeWorkspaceFiles(items)
  .filter((item) => item.type === 'file')
  .map((item) => `===== FILE: ${item.path} =====\n${item.content || ''}`)
  .join('\n\n');

const buildWorkspaceAnswer = (problem, saved = {}) => {
  const defaultPath = DEFAULT_FILE_BY_LANGUAGE[problem?.language] || 'main.txt';
  let files = normalizeWorkspaceFiles(saved.files || []);
  if (!files.some((item) => item.type === 'file')) {
    files = normalizeWorkspaceFiles([{
      type: 'file',
      path: defaultPath,
      content: saved.code && !String(saved.code).includes('===== FILE:') ? String(saved.code) : starterCodeForProblem(problem || { title: 'Solution', language: 'python' }),
    }]);
  }
  const preferredActive = normalizeWorkspacePath(saved.activeFilePath);
  const activeFilePath = files.some((item) => item.type === 'file' && item.path === preferredActive)
    ? preferredActive
    : files.find((item) => item.type === 'file')?.path || defaultPath;
  return {
    ...(saved || {}),
    language: problem?.language || saved.language || 'python',
    files,
    activeFilePath,
    code: serializeWorkspaceFiles(files),
  };
};

const isCodingWorkspaceAttempted = (problem, answer = {}) => {
  const normalized = buildWorkspaceAnswer(problem, answer);
  const defaultPath = DEFAULT_FILE_BY_LANGUAGE[problem?.language] || 'main.txt';
  const starter = starterCodeForProblem(problem || { title: 'Solution', language: 'python' }).trim();
  return normalized.files.some((item) => {
    if (item.type !== 'file') return false;
    const content = String(item.content || '').trim();
    if (!content) return false;
    if (item.path === defaultPath && content === starter) return false;
    return true;
  });
};

export default function ExamRoom() {
  const { examId } = useParams();
  const navigate = useNavigate();
  const { logout } = useAuth();

  // ---- exam data ----
  const [examData, setExamData] = useState(null);
  const [mcqs, setMcqs] = useState([]);
  const [codingProblems, setCodingProblems] = useState([]);
  const [proctorConfig, setProctorConfig] = useState({});

  // ---- answers ----
  const [mcqAnswers, setMcqAnswers] = useState({});
  const [codingAnswers, setCodingAnswers] = useState({});
  const [runResults, setRunResults] = useState({});   // problemId -> {stdout, stderr, ...}
  const [runningId, setRunningId] = useState(null);    // problemId currently running, or null
  const [customStdin, setCustomStdin] = useState({});  // problemId -> string

  // ---- ui ----
  const [activeSection, setActiveSection] = useState('mcq');
  const [activeProblemIdx, setActiveProblemIdx] = useState(0);
  const [timeLeft, setTimeLeft] = useState(null);
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [showConfirmModal, setShowConfirmModal] = useState(false);
  const [workspaceModal, setWorkspaceModal] = useState(null); // { type, problemId, item?, title?, message? }
  const [workspacePathInput, setWorkspacePathInput] = useState('');
  const [workspaceModalError, setWorkspaceModalError] = useState('');
  const [error, setError] = useState('');
  const [gateError, setGateError] = useState('');
  const [savedAt, setSavedAt] = useState(null);
  const [starting, setStarting] = useState(false);

  // ---- proctoring ----
  const [tempOtp, setTempOtp] = useState(() => sessionStorage.getItem(`exam_${examId}_temp_otp`) || '');
  const [armed, setArmed] = useState(false);            // student clicked "Enter secure mode"
  const [violations, setViolations] = useState(0);
  const [maxViolations, setMaxViolations] = useState(3);

  const submittedRef = useRef(false);
  const startingRef = useRef(false);
  const {
    isRecording, recordingError, startRecording, stopRecording, uploadViolationClip,
    beginFocusLossClip, finishFocusLossClip,
  } = useScreenRecording({ examId, enabled: true });
  const answersRef = useRef({ mcq: {}, coding: {} });
  useEffect(() => { answersRef.current = { mcq: mcqAnswers, coding: codingAnswers }; }, [mcqAnswers, codingAnswers]);

  // ================================================================ submit
  const doSubmit = useCallback(async (auto = false, reason = '') => {
    if (submittedRef.current) return;
    submittedRef.current = true;
    setSubmitting(true);
    try {
      await api.post(`exams/${examId}/submit/`, {
        mcq_answers: answersRef.current.mcq,
        coding_answers: answersRef.current.coding,
        auto_submitted: auto,
        reason,
      });
      sessionStorage.removeItem(`exam_${examId}_temp_otp`);
      stopRecording();
      // Release the lockdown before navigating away
      if (document.fullscreenElement) {
        try { await document.exitFullscreen(); } catch { /* ignore */ }
      }
      navigate(`/exam/${examId}/result`, { replace: true });
    } catch (err) {
      submittedRef.current = false;
      setError(err.response?.data?.error || 'Submission failed. Please try again.');
      setSubmitting(false);
      setShowConfirmModal(false);
    }
  }, [examId, navigate, stopRecording]);

  // ============================================================ violations
  const handleUfmLockout = useCallback(async (violationCount, limit) => {
    if (submittedRef.current) return;
    submittedRef.current = true;
    try { stopRecording(); } catch { /* ignore */ }
    if (document.fullscreenElement) {
      try { await document.exitFullscreen(); } catch { /* ignore */ }
    }
    sessionStorage.removeItem(`exam_${examId}_temp_otp`);
    logout();
    navigate('/login', {
      replace: true,
      state: {
        blockedMessage: `Your account has been locked after exceeding the ${limit}-violation proctoring limit `
          + `(${violationCount} recorded) in "${examData?.title || 'this exam'}". Your marks for this exam have `
          + `been voided as unfair means. You cannot sign back in until your faculty restores access.`,
      },
    });
  }, [examId, examData, navigate, logout, stopRecording]);

  const handleViolation = useCallback(async (eventType, details) => {
    try {
      const res = await api.post(`exams/${examId}/proctor-event/`, {
        event_type: eventType, details,
      });
      setViolations(res.data.violation_count);
      setMaxViolations(res.data.max_violations || 0);
      uploadViolationClip(eventType, details);
      if (res.data.is_ufm || res.data.blocked) {
        handleUfmLockout(res.data.violation_count, res.data.max_violations);
      }
    } catch {
      /* never let proctoring reporting break the exam */
    }
  }, [examId, uploadViolationClip, handleUfmLockout]);

  // Record the COMPLETE period while the student is away from the exam window.
  // The normal proctoring hook reports the violation at the moment of blur/tab
  // switch; this separate recorder marker keeps collecting chunks and uploads
  // the full interval only after the student comes back.
  useEffect(() => {
    if (!armed || submitting || error) return;

    const awayRef = { current: false };
    const beginAway = (reason, eventType = 'blur') => {
      if (awayRef.current || submittedRef.current) return;
      awayRef.current = true;
      beginFocusLossClip(reason, eventType);
    };
    const finishAway = () => {
      if (!awayRef.current || submittedRef.current) return;
      // Wait a tick so visibility/focus state has settled after the browser returns.
      window.setTimeout(() => {
        if (submittedRef.current) return;
        if (!document.hidden && document.hasFocus()) {
          awayRef.current = false;
          finishFocusLossClip('The student came back to the exam window.');
        }
      }, 250);
    };

    const onBlur = () => beginAway('The exam window lost focus.', 'blur');
    const onFocus = () => finishAway();
    const onVisibility = () => {
      if (document.hidden) beginAway('The student switched away from the exam tab.', 'tab_switch');
      else finishAway();
    };

    window.addEventListener('blur', onBlur, true);
    window.addEventListener('focus', onFocus, true);
    document.addEventListener('visibilitychange', onVisibility, true);

    return () => {
      window.removeEventListener('blur', onBlur, true);
      window.removeEventListener('focus', onFocus, true);
      document.removeEventListener('visibilitychange', onVisibility, true);
      if (awayRef.current && !submittedRef.current) {
        finishFocusLossClip('Focus-loss tracking ended because the exam page closed or re-rendered.');
      }
    };
  }, [armed, submitting, error, beginFocusLossClip, finishFocusLossClip]);

  // Clipboard/shortcut lockdown must be live on the consent gate too — otherwise a
  // student can copy the paper before clicking "Enter Fullscreen". Fullscreen
  // enforcement stays gated behind `armed` because it needs a user gesture.
  const {
    isFullscreen, requestFullscreen, showWarning, warningMessage,
  } = useProctoring({
    enabled: !loading && !submitting && !error,
    enforceFullscreenActive: armed,
    config: proctorConfig,
    onViolation: handleViolation,
    isSubmitting: submitting,
    // Don't spam the server with violations before the exam has actually started.
    reportToServer: armed,
  });

  // ================================================================= load exam info
  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const res = await api.get(`exams/${examId}/`);
        if (cancelled) return;
        setExamData(res.data);
        setProctorConfig({
          enforce_fullscreen: res.data.enforce_fullscreen ?? true,
          block_shortcuts: res.data.block_shortcuts ?? true,
          block_copy_paste: res.data.block_copy_paste ?? true,
          // Was missing here, so the pre-start gate screen below always fell
          // back to showing the "share your screen" copy/button even when
          // the faculty had turned screen recording off for this exam.
          require_screen_recording: res.data.require_screen_recording ?? true,
          max_violations: res.data.max_violations ?? 3,
          auto_submit_on_violation: res.data.auto_submit_on_violation ?? true,
        });
        setMaxViolations(res.data.max_violations ?? 3);
      } catch (err) {
        if (!cancelled) setError(err.response?.data?.error || 'Failed to load exam info.');
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => { cancelled = true; };
  }, [examId]);

  // ================================================================ timer
  useEffect(() => {
    if (loading || error || timeLeft === null || submittedRef.current) return;
    if (timeLeft <= 0) {
      doSubmit(true, 'Time expired.');
      return;
    }
    const id = setInterval(() => setTimeLeft((t) => (t === null ? t : Math.max(0, t - 1))), 1000);
    return () => clearInterval(id);
  }, [loading, error, timeLeft, doSubmit]);

  // ============================================================= autosave
  useEffect(() => {
    if (loading || error || !armed || submittedRef.current) return;
    const id = setInterval(async () => {
      if (submittedRef.current) return;
      try {
        const res = await api.post(`exams/${examId}/autosave/`, {
          mcq_answers: answersRef.current.mcq,
          coding_answers: answersRef.current.coding,
        });
        setSavedAt(new Date(res.data.saved_at));
        if (typeof res.data.remaining_seconds === 'number') {
          // Re-sync with the server clock so a paused tab cannot buy extra time.
          setTimeLeft(res.data.remaining_seconds);
        }
      } catch { /* keep going offline */ }
    }, AUTOSAVE_MS);
    return () => clearInterval(id);
  }, [loading, error, armed, examId]);

  // ============================================================== helpers
  const formatTime = (s) => {
    if (s === null) return '--:--';
    const h = Math.floor(s / 3600);
    const m = Math.floor((s % 3600) / 60);
    const sec = s % 60;
    return `${h > 0 ? `${h}:` : ''}${String(m).padStart(2, '0')}:${String(sec).padStart(2, '0')}`;
  };

  const selectMcq = (qid, opt) => setMcqAnswers((p) => ({ ...p, [qid]: opt }));
  const toggleMcqMulti = (qid, opt) => setMcqAnswers((p) => {
    const current = Array.isArray(p[qid]) ? p[qid] : [];
    const next = current.includes(opt) ? current.filter((o) => o !== opt) : [...current, opt].sort();
    return { ...p, [qid]: next };
  });

  const updateWorkspace = (problem, updater) => {
    setCodingAnswers((prev) => {
      const base = buildWorkspaceAnswer(problem, prev[problem.id] || {});
      const draft = updater(base) || base;
      const files = normalizeWorkspaceFiles(draft.files || base.files);
      const activeFilePath = files.some((item) => item.type === 'file' && item.path === draft.activeFilePath)
        ? draft.activeFilePath
        : files.find((item) => item.type === 'file')?.path;
      return {
        ...prev,
        [problem.id]: {
          ...base,
          ...draft,
          files,
          activeFilePath,
          code: serializeWorkspaceFiles(files),
        },
      };
    });
  };

  const changeCoding = (pid, field, value) => {
    if (field !== 'code') {
      setCodingAnswers((p) => ({ ...p, [pid]: { ...(p[pid] || {}), [field]: value } }));
      return;
    }
    const problem = codingProblems.find((p) => p.id === pid) || currentProblem || { id: pid, title: 'Solution', language: 'python' };
    updateWorkspace(problem, (answer) => ({
      ...answer,
      files: answer.files.map((item) => (
        item.type === 'file' && item.path === answer.activeFilePath ? { ...item, content: value } : item
      )),
    }));
  };

  const selectWorkspaceFile = (problem, path) => {
    updateWorkspace(problem, (answer) => ({ ...answer, activeFilePath: path }));
  };

  const openWorkspaceModal = (type, problem, item = null) => {
    setWorkspaceModal({ type, problemId: problem.id, item });
    setWorkspacePathInput('');
    setWorkspaceModalError('');
  };

  const closeWorkspaceModal = () => {
    setWorkspaceModal(null);
    setWorkspacePathInput('');
    setWorkspaceModalError('');
  };

  const addWorkspaceFile = (problem) => {
    openWorkspaceModal('file', problem);
  };

  const addWorkspaceFolder = (problem) => {
    openWorkspaceModal('folder', problem);
  };

  const deleteWorkspaceItem = (problem, item) => {
    const fileCount = normalizeWorkspaceFiles(codingAnswers[problem.id]?.files || []).filter((f) => f.type === 'file').length;
    if (item.type === 'file' && fileCount <= 1) {
      setWorkspaceModal({
        type: 'message',
        problemId: problem.id,
        title: 'Cannot delete the last file',
        message: 'At least one code file is required in the workspace.',
      });
      setWorkspaceModalError('');
      return;
    }
    openWorkspaceModal('delete', problem, item);
  };

  const submitWorkspaceModal = () => {
    if (!workspaceModal) return;
    if (workspaceModal.type === 'message') {
      closeWorkspaceModal();
      return;
    }
    const problem = codingProblems.find((p) => p.id === workspaceModal.problemId);
    if (!problem) {
      closeWorkspaceModal();
      return;
    }

    if (workspaceModal.type === 'delete') {
      const item = workspaceModal.item;
      updateWorkspace(problem, (answer) => {
        const nextFiles = answer.files.filter((f) => (
          item.type === 'folder' ? f.path !== item.path && !f.path.startsWith(`${item.path}/`) : f.path !== item.path
        ));
        return { ...answer, files: nextFiles };
      });
      closeWorkspaceModal();
      return;
    }

    const path = normalizeWorkspacePath(workspacePathInput);
    if (!path) {
      setWorkspaceModalError('Enter a valid path. Example: main.py or src/components.');
      return;
    }
    if (path.includes('..')) {
      setWorkspaceModalError('Parent directory segments (..) are not allowed.');
      return;
    }

    const type = workspaceModal.type === 'folder' ? 'folder' : 'file';
    const existing = normalizeWorkspaceFiles(codingAnswers[problem.id]?.files || []);
    if (existing.some((item) => item.path === path)) {
      setWorkspaceModalError('A file or folder with this path already exists.');
      return;
    }

    updateWorkspace(problem, (answer) => ({
      ...answer,
      activeFilePath: type === 'file' ? path : answer.activeFilePath,
      files: [...answer.files, { type, path, content: '' }],
    }));
    closeWorkspaceModal();
  };

  const runCode = async (problem) => {
    if (runningId) return;
    const answer = buildWorkspaceAnswer(problem, codingAnswers[problem.id] || {});
    const activeFile = answer.files.find((item) => item.type === 'file' && item.path === answer.activeFilePath);
    const code = activeFile?.content || '';
    if (!code.trim()) {
      setRunResults((p) => ({ ...p, [problem.id]: { error: 'Write some code in the active file before running it.' } }));
      return;
    }
    setRunningId(problem.id);
    setRunResults((p) => ({ ...p, [problem.id]: null }));
    try {
      const res = await api.post(`exams/${examId}/coding/${problem.id}/run/`, {
        code,
        stdin: customStdin[problem.id] || '',
      });
      setRunResults((p) => ({ ...p, [problem.id]: res.data }));
    } catch (err) {
      setRunResults((p) => ({
        ...p,
        [problem.id]: { error: err.response?.data?.error || 'Could not run your code. Try again.' },
      }));
    } finally {
      setRunningId(null);
    }
  };

  const LANGUAGE_LABELS = {
    python: 'Python 3', javascript: 'JavaScript (Node.js)', cpp: 'C++', java: 'Java',
  };

  const enterSecureMode = async () => {
    if (startingRef.current) return;
    startingRef.current = true;
    setStarting(true);
    setGateError('');
    try {
      const res = await api.post(`exams/${examId}/start/`, { temp_otp: tempOtp.trim() });
      const {
        exam, mcqs: shuffled, coding_problems: probs,
        remaining_seconds, mcq_draft, coding_draft,
        violation_count, proctor_config,
      } = res.data;

      setExamData(exam);
      setMcqs(shuffled || []);
      setCodingProblems(probs || []);
      setProctorConfig(proctor_config || {});
      setMaxViolations(proctor_config?.max_violations ?? 3);
      setViolations(violation_count || 0);
      setTimeLeft(typeof remaining_seconds === 'number' ? remaining_seconds : exam.duration_minutes * 60);
      setMcqAnswers(mcq_draft || {});

      const coding = {};
      (probs || []).forEach((p) => {
        const saved = coding_draft?.[String(p.id)] || coding_draft?.[p.id] || {};
        coding[p.id] = buildWorkspaceAnswer(p, saved);
      });
      setCodingAnswers(coding);

      sessionStorage.setItem(`exam_${examId}_temp_otp`, tempOtp.trim());
      const recordingRequired = proctor_config?.require_screen_recording ?? true;
      const recordingOk = await startRecording(recordingRequired);
      if (!recordingOk) {
        setGateError(recordingError || 'Screen recording permission is required. Please share your entire screen and start again.');
        startingRef.current = false;
        setStarting(false);
        return;
      }
      const ok = await requestFullscreen();
      setArmed(true);
      if (!ok) {
        handleViolation('fullscreen_exit', 'Fullscreen was blocked by the browser at exam start.');
      }
      // Once armed the gate unmounts, so there's no button left to guard —
      // but reset defensively in case armed is later flipped back.
      startingRef.current = false;
      setStarting(false);
    } catch (err) {
      setError(err.response?.data?.error || 'Failed to start exam. Check your temporary OTP and try again.');
      startingRef.current = false;
      setStarting(false);
    }
  };

  // ============================================================== renders
  if (loading) {
    return (
      <div className="secure-exam-room flex min-h-screen items-center justify-center bg-slate-950 text-white">
        <div className="space-y-4 text-center">
          <Loader2 className="mx-auto h-12 w-12 animate-spin text-blue-500" />
          <p className="font-medium text-slate-400">Preparing your secure examination room…</p>
        </div>
      </div>
    );
  }

  if (error && !submitting) {
    return (
      <div className="secure-exam-room flex min-h-screen items-center justify-center bg-slate-950 p-4">
        <div className="w-full max-w-md rounded-3xl border border-slate-800 bg-slate-900 p-8 text-center">
          <AlertCircle className="mx-auto mb-4 h-16 w-16 text-rose-500" />
          <h3 className="mb-2 text-xl font-bold text-white">Examination Room Unavailable</h3>
          <p className="mb-6 text-sm text-slate-400">{error}</p>
          <button onClick={() => navigate('/')}
            className="rounded-xl bg-blue-600 px-6 py-2.5 font-medium text-white transition hover:bg-blue-700">
            Return to Dashboard
          </button>
        </div>
      </div>
    );
  }

  // ---- Gate: fullscreen must be entered from a user gesture ----
  const screenRecordingRequired = proctorConfig.require_screen_recording ?? true;

  if (!armed) {
    return (
      <div className="secure-exam-room flex min-h-screen items-center justify-center bg-slate-950 p-4">
        <div className="w-full max-w-4xl rounded-3xl border border-slate-800 bg-slate-900 p-8 sm:p-10 shadow-2xl">
          <div className="mb-6 flex items-center gap-4">
            <div className="flex h-14 w-14 items-center justify-center rounded-2xl bg-blue-600/20 text-blue-400">
              <ShieldCheck className="h-7 w-7" />
            </div>
            <div>
              <h2 className="text-2xl font-bold text-white">Secure Examination Mode</h2>
              <p className="text-sm text-slate-400">{examData?.title}</p>
            </div>
          </div>

          <div className="mb-6 space-y-3 rounded-2xl border border-amber-500/20 bg-amber-500/5 p-5">
            <div className="flex items-center gap-2 text-sm font-bold uppercase tracking-wide text-amber-400">
              <ShieldAlert className="h-4 w-4" /> Before you begin — read carefully
            </div>
            <ul className="space-y-2.5 text-sm leading-relaxed text-slate-300">
              {proctorConfig.enforce_fullscreen && (
                <li className="flex items-start gap-3">
                  <span className="mt-2 h-1.5 w-1.5 flex-shrink-0 rounded-full bg-amber-400" />
                  <span>The exam runs in <b className="text-white">enforced fullscreen</b>. Exiting fullscreen is recorded as a violation and fullscreen is re-applied automatically.</span>
                </li>
              )}
              {proctorConfig.block_shortcuts && (
                <li className="flex items-start gap-3">
                  <span className="mt-2 h-1.5 w-1.5 flex-shrink-0 rounded-full bg-amber-400" />
                  <span><b className="text-white">Keyboard shortcuts are disabled</b> — Escape, F11, F12, Ctrl+T/N/W/R/P, Alt+Tab and developer tools will not work.</span>
                </li>
              )}
              {proctorConfig.block_copy_paste && (
                <li className="flex items-start gap-3">
                  <span className="mt-2 h-1.5 w-1.5 flex-shrink-0 rounded-full bg-amber-400" />
                  <span><b className="text-white">Copy, cut, paste and right-click are blocked</b> across the exam room.</span>
                </li>
              )}
              <li className="flex items-start gap-3">
                <span className="mt-2 h-1.5 w-1.5 flex-shrink-0 rounded-full bg-amber-400" />
                <span><b className="text-white">Switching tabs or applications is detected</b> and logged for your faculty.</span>
              </li>
              {proctorConfig.auto_submit_on_violation ? (
                <li className="flex items-start gap-3">
                  <span className="mt-2 h-1.5 w-1.5 flex-shrink-0 rounded-full bg-amber-400" />
                  <span>After <b className="text-white">{maxViolations || '∞'} violations</b> your paper is submitted automatically.</span>
                </li>
              ) : (
                <li className="flex items-start gap-3">
                  <span className="mt-2 h-1.5 w-1.5 flex-shrink-0 rounded-full bg-amber-400" />
                  <span>Violations are recorded and shared with your faculty, but <b className="text-white">will not auto-submit</b> your paper.</span>
                </li>
              )}
              <li className="flex items-start gap-3">
                <span className="mt-2 h-1.5 w-1.5 flex-shrink-0 rounded-full bg-emerald-400" />
                <span>Your answers <b className="text-white">auto-save to the server every 15 seconds</b>, so an accidental disconnect will not lose your work.</span>
              </li>
              {screenRecordingRequired && (
                <li className="flex items-start gap-3">
                  <span className="mt-2 h-1.5 w-1.5 flex-shrink-0 rounded-full bg-rose-400" />
                  <span><b className="text-white">Screen recording consent is required</b>. Clips are saved only for focus loss or tab/window switching, from the moment you leave until you return.</span>
                </li>
              )}
            </ul>
          </div>

          {screenRecordingRequired && (gateError || recordingError) && (
            <div className="mb-6 rounded-2xl border border-rose-500/30 bg-rose-500/10 p-4 text-sm text-rose-100">
              <div className="mb-1 font-bold text-rose-300">Screen recording is not enabled</div>
              <p>{recordingError || gateError}</p>
              <p className="mt-2 text-xs text-rose-200">
                Choose <b>Entire Screen</b>. Browser-tab or application-window sharing is not accepted.
              </p>
            </div>
          )}

          <div className="mb-6 grid grid-cols-3 gap-3 text-center">
            {[
              ['Duration', `${examData?.duration_minutes || '--'} min`],
              ['MCQs', examData?.mcq_count || 0],
              ['Coding', examData?.coding_count || 0],
            ].map(([k, v]) => (
              <div key={k} className="rounded-2xl border border-slate-800 bg-slate-950 p-4">
                <div className="text-[11px] font-bold uppercase tracking-wider text-slate-500">{k}</div>
                <div className="mt-1 text-lg font-bold text-white">{v}</div>
              </div>
            ))}
          </div>

          {/* Temporary OTP input */}
          <div className="mb-6">
            <label htmlFor="temp-otp" className="block text-xs font-bold uppercase tracking-wider text-slate-400 mb-2">
              Temporary Exam OTP (required to enter)
            </label>
            <input
              id="temp-otp"
              type="text"
              value={tempOtp}
              onChange={(e) => setTempOtp(e.target.value)}
              placeholder="Enter your 6-digit temporary exam OTP"
              className="w-full rounded-xl border border-slate-700 bg-slate-950 px-4 py-3 text-sm font-mono tracking-widest text-white placeholder:text-slate-600 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
            />
            <p className="mt-2 text-xs text-slate-500">
              This temporary OTP was issued by your faculty and is only active during the exam window. It clears after submission.
            </p>
            <p className={`mt-2 text-xs font-semibold ${recordingError ? 'text-rose-400' : 'text-slate-500'}`}>
              {screenRecordingRequired
                ? (recordingError || 'When you start, your browser will ask you to share your entire screen. Only focus-loss/tab-switch clips are uploaded, and only after you return.')
                : 'This exam does not require screen recording — click Start Exam to begin right away.'}
            </p>
          </div>

          <div className="flex flex-col gap-3 sm:flex-row">
            <button onClick={() => navigate('/')} disabled={starting}
              className="rounded-xl bg-slate-800 px-6 py-3.5 text-sm font-semibold text-slate-300 transition hover:bg-slate-700 disabled:opacity-50">
              Not yet — go back
            </button>
            <button onClick={enterSecureMode} disabled={starting}
              className="flex flex-1 items-center justify-center gap-2 rounded-xl bg-blue-600 px-6 py-3.5 font-bold text-white shadow-lg transition hover:bg-blue-700 disabled:cursor-not-allowed disabled:opacity-60">
              {starting ? (
                <>
                  <Loader2 className="h-5 w-5 animate-spin" /> Starting…
                </>
              ) : screenRecordingRequired ? (
                <>
                  <Maximize className="h-5 w-5" /> Share Entire Screen &amp; Start Exam
                </>
              ) : (
                <>
                  <Play className="h-5 w-5" /> Start Exam
                </>
              )}
            </button>
          </div>
        </div>
      </div>
    );
  }

  const currentProblem = codingProblems[activeProblemIdx];
  const currentAnswer = currentProblem ? buildWorkspaceAnswer(currentProblem, codingAnswers[currentProblem.id] || {}) : null;
  const currentWorkspaceFiles = currentAnswer?.files || [];
  const currentActiveFile = currentAnswer
    ? currentWorkspaceFiles.find((item) => item.type === 'file' && item.path === currentAnswer.activeFilePath)
    : null;
  const currentEditorValue = currentActiveFile?.content || '';
  const answeredCount = Object.keys(mcqAnswers).filter((k) => {
    const v = mcqAnswers[k];
    return Array.isArray(v) ? v.length > 0 : !!v;
  }).length;
  const lowTime = timeLeft !== null && timeLeft < 300;

  return (
    <div className="secure-exam-room flex min-h-screen select-none flex-col text-slate-100">

      {/* Fullscreen breach overlay — blocks the paper until fullscreen is restored */}
      {proctorConfig.enforce_fullscreen && !isFullscreen && !submitting && (
        <div className="fixed inset-0 z-[100] flex items-center justify-center bg-slate-950/98 p-4 backdrop-blur-md">
          <div className="w-full max-w-lg rounded-3xl border-2 border-rose-500/40 bg-slate-900 p-10 text-center shadow-2xl">
            <div className="mx-auto mb-5 flex h-16 w-16 animate-pulse items-center justify-center rounded-2xl bg-rose-500/20 text-rose-400">
              <ShieldAlert className="h-9 w-9" />
            </div>
            <h3 className="mb-2 text-2xl font-bold text-white">Fullscreen Required</h3>
            <p className="mb-1 text-sm leading-relaxed text-slate-300">
              You have left fullscreen mode. This has been recorded and reported to your faculty.
            </p>
            <p className="mb-6 text-sm font-semibold text-rose-300">
              Violations: {violations}{maxViolations ? ` / ${maxViolations}` : ''}
              {maxViolations > 0 && violations >= maxViolations - 1 && ' — one more will auto-submit your paper.'}
            </p>
            <button onClick={requestFullscreen}
              className="mx-auto flex items-center justify-center gap-2 rounded-xl bg-rose-600 px-8 py-3.5 font-bold text-white shadow-lg transition hover:bg-rose-700">
              <Maximize className="h-5 w-5" /> Return to Fullscreen
            </button>
            <p className="mt-4 text-xs text-slate-500">Your timer is still running.</p>
          </div>
        </div>
      )}

      {/* Transient violation toast */}
      {showWarning && (
        <div className="fixed left-1/2 top-4 z-[90] flex -translate-x-1/2 items-center gap-2.5 rounded-xl border border-rose-500/40 bg-rose-950/95 px-5 py-3 text-sm font-semibold text-rose-200 shadow-2xl backdrop-blur">
          <ShieldAlert className="h-4 w-4 flex-shrink-0" />
          {warningMessage}
        </div>
      )}

      {/* Header */}
      <header className="sticky top-0 z-40 flex flex-wrap items-center justify-between gap-4 border-b border-slate-800 bg-slate-950 px-6 py-3.5">
        <div className="min-w-0">
          <h1 className="truncate text-base font-bold text-white">{examData?.title}</h1>
          <div className="flex items-center gap-3 text-[12px] text-slate-400">
            <span className="flex items-center gap-1 text-emerald-400">
              <ShieldCheck className="h-3 w-3" /> Secure mode active
            </span>
            {savedAt && (
              <span className="flex items-center gap-1">
                <Save className="h-3 w-3" /> Saved {savedAt.toLocaleTimeString('en-IN', { hour: '2-digit', minute: '2-digit' })}
              </span>
            )}
          </div>
        </div>

        <div className="flex flex-wrap items-center gap-3">
          {/* Violation counter */}
          {violations > 0 && (
            <div className="flex items-center gap-1.5 rounded-xl border border-rose-800 bg-rose-950/60 px-3 py-2 text-xs font-bold text-rose-300">
              <Eye className="h-3.5 w-3.5" />
              {violations}{maxViolations ? `/${maxViolations}` : ''} violations
            </div>
          )}

          {/* Section switch */}
          <div className="flex items-center gap-1 rounded-xl border border-slate-800 bg-slate-900 p-1">
            <button onClick={() => setActiveSection('mcq')}
              className={`flex items-center gap-2 rounded-lg px-4 py-2 text-sm font-semibold transition ${
                activeSection === 'mcq' ? 'bg-blue-600 text-white shadow' : 'text-slate-400 hover:text-white'
              }`}>
              <HelpCircle className="h-4 w-4" /> MCQs ({answeredCount}/{mcqs.length})
            </button>
            <button onClick={() => setActiveSection('coding')}
              className={`flex items-center gap-2 rounded-lg px-4 py-2 text-sm font-semibold transition ${
                activeSection === 'coding' ? 'bg-purple-600 text-white shadow' : 'text-slate-400 hover:text-white'
              }`}>
              <Code className="h-4 w-4" /> Coding ({codingProblems.length})
            </button>
          </div>

          <div className={`flex items-center gap-2 rounded-xl border px-4 py-2 font-mono text-base font-bold ${
            lowTime ? 'animate-pulse border-rose-800 bg-rose-950 text-rose-300' : 'border-slate-800 bg-slate-900 text-amber-400'
          }`}>
            <Clock className="h-5 w-5" /> {formatTime(timeLeft)}
          </div>

          <button onClick={() => setShowConfirmModal(true)} disabled={submitting}
            className="flex items-center gap-2 rounded-xl bg-emerald-600 px-5 py-2.5 text-sm font-bold text-white shadow-lg transition hover:bg-emerald-700 disabled:opacity-60">
            <Send className="h-4 w-4" /> Finish &amp; Submit
          </button>
        </div>
      </header>

      {/* Body */}
      <main className="mx-auto w-full max-w-7xl flex-1 p-6">
        {activeSection === 'mcq' ? (
          <div className="space-y-6">
            <div className="flex flex-wrap items-center justify-between gap-3 rounded-2xl border border-slate-800 bg-slate-800/40 p-4 text-sm text-slate-300">
              <span className="flex items-center gap-2">
                <ListChecks className="h-4 w-4 text-blue-400" />
                Question order and answer options are randomised uniquely for you.
              </span>
              <span className="font-semibold">Answered: {answeredCount} / {mcqs.length}</span>
            </div>

            {mcqs.map((q, idx) => {
              const isMulti = q.question_type === 'multi';
              const selected = mcqAnswers[q.id];
              const selectedArr = isMulti ? (Array.isArray(selected) ? selected : []) : null;
              const isAnswered = isMulti ? selectedArr.length > 0 : !!selected;
              return (
                <div key={q.id} className="rounded-2xl border border-slate-700/80 bg-slate-800/80 p-6 shadow-md transition hover:border-slate-600">
                  <div className="mb-4 flex items-start justify-between gap-4">
                    <div className="flex items-start gap-3">
                      <span className={`flex h-8 w-8 flex-shrink-0 items-center justify-center rounded-lg text-sm font-bold ${
                        isAnswered ? 'bg-emerald-600/20 text-emerald-400' : 'bg-blue-600/20 text-blue-400'
                      }`}>{idx + 1}</span>
                      <div className="pt-0.5">
                        <h3 className="text-base font-semibold leading-relaxed text-white">{q.question_text}</h3>
                        {isMulti && (
                          <span className="mt-1 inline-flex items-center gap-1 rounded-md bg-indigo-500/15 px-2 py-0.5 text-[12px] font-bold uppercase tracking-wide text-indigo-300">
                            <ListChecks className="h-3 w-3" /> Select all that apply
                          </span>
                        )}
                      </div>
                    </div>
                    <span className="flex-shrink-0 rounded-lg bg-slate-700 px-2.5 py-1 text-xs font-semibold text-slate-300">
                      {q.marks} Marks
                    </span>
                  </div>

                  <div className="grid grid-cols-1 gap-3 pl-11 md:grid-cols-2">
                    {['A', 'B', 'C', 'D'].map((k) => {
                      const text = q[`option_${k.toLowerCase()}`];
                      const isSel = isMulti ? selectedArr.includes(k) : selected === k;
                      return (
                        <button key={k} type="button"
                          onClick={() => (isMulti ? toggleMcqMulti(q.id, k) : selectMcq(q.id, k))}
                          className={`flex items-center justify-between rounded-xl border p-4 text-left text-sm transition ${
                            isSel
                              ? 'border-blue-500 bg-blue-600/20 font-medium text-white shadow-sm'
                              : 'border-slate-800 bg-slate-900/60 text-slate-300 hover:border-slate-700 hover:bg-slate-900'
                          }`}>
                          <span className="flex items-center gap-3">
                            <span className={`flex h-6 w-6 flex-shrink-0 items-center justify-center text-xs font-bold ${
                              isMulti ? 'rounded-md' : 'rounded-full'
                            } ${isSel ? 'bg-blue-500 text-white' : 'bg-slate-800 text-slate-400'}`}>{k}</span>
                            <span>{text}</span>
                          </span>
                          {isSel && <CheckCircle2 className="h-5 w-5 flex-shrink-0 text-blue-400" />}
                        </button>
                      );
                    })}
                  </div>

                  {isAnswered && (
                    <button onClick={() => setMcqAnswers((p) => { const n = { ...p }; delete n[q.id]; return n; })}
                      className="ml-11 mt-3 text-xs font-medium text-slate-500 hover:text-rose-400">
                      Clear response
                    </button>
                  )}
                </div>
              );
            })}
          </div>
        ) : codingProblems.length === 0 ? (
          <div className="rounded-2xl border border-slate-800 bg-slate-800/40 p-16 text-center text-slate-400">
            No coding problems in this exam.
          </div>
        ) : (
          <div className="grid grid-cols-1 gap-6 lg:grid-cols-12">
            {/* Problem statement */}
            <div className="flex flex-col space-y-4 lg:col-span-5">
              <div className="flex items-center gap-2 overflow-x-auto pb-1">
                {codingProblems.map((p, i) => (
                  <button key={p.id} onClick={() => setActiveProblemIdx(i)}
                    className={`whitespace-nowrap rounded-xl px-4 py-2 text-sm font-semibold transition ${
                      activeProblemIdx === i ? 'bg-purple-600 text-white' : 'bg-slate-800 text-slate-400 hover:text-white'
                    }`}>
                    Problem {i + 1}
                  </button>
                ))}
              </div>

              {currentProblem && (
                <div className="max-h-[70vh] flex-1 space-y-5 overflow-y-auto rounded-2xl border border-slate-700/80 bg-slate-800/80 p-6">
                  <div className="flex items-center justify-between border-b border-slate-700 pb-4">
                    <h2 className="text-lg font-bold text-white">{currentProblem.title}</h2>
                    <span className="rounded-full border border-purple-500/30 bg-purple-500/20 px-3 py-1 text-xs font-bold text-purple-300">
                      {currentProblem.marks} Marks
                    </span>
                  </div>

                  <div>
                    <h4 className="mb-1 text-xs font-bold uppercase tracking-wider text-slate-400">Problem Statement</h4>
                    <p className="whitespace-pre-line text-sm leading-relaxed text-slate-200">
                      {currentProblem.problem_statement}
                    </p>
                  </div>

                  {currentProblem.input_format && (
                    <div>
                      <h4 className="mb-1 text-xs font-bold uppercase tracking-wider text-slate-400">Input Format</h4>
                      <p className="rounded-xl border border-slate-800 bg-slate-900/60 p-3 text-xs text-slate-300">
                        {currentProblem.input_format}
                      </p>
                    </div>
                  )}

                  {currentProblem.output_format && (
                    <div>
                      <h4 className="mb-1 text-xs font-bold uppercase tracking-wider text-slate-400">Output Format</h4>
                      <p className="rounded-xl border border-slate-800 bg-slate-900/60 p-3 text-xs text-slate-300">
                        {currentProblem.output_format}
                      </p>
                    </div>
                  )}

                  {currentProblem.sample_input && (
                    <div className="grid grid-cols-2 gap-3">
                      <div>
                        <h4 className="mb-1 text-xs font-bold uppercase tracking-wider text-slate-400">Sample Input</h4>
                        <pre className="overflow-x-auto rounded-xl border border-slate-800 bg-slate-950 p-3 font-mono text-xs text-emerald-400">
                          {currentProblem.sample_input}
                        </pre>
                      </div>
                      <div>
                        <h4 className="mb-1 text-xs font-bold uppercase tracking-wider text-slate-400">Sample Output</h4>
                        <pre className="overflow-x-auto rounded-xl border border-slate-800 bg-slate-950 p-3 font-mono text-xs text-blue-400">
                          {currentProblem.sample_output}
                        </pre>
                      </div>
                    </div>
                  )}
                </div>
              )}
            </div>

            {/* Editor */}
            <div className="flex flex-col overflow-hidden rounded-2xl border border-slate-700/80 bg-slate-800/90 shadow-xl lg:col-span-7">
              {currentProblem && (
                <>
                  <div className="flex flex-wrap items-center justify-between gap-3 border-b border-slate-800 bg-slate-900 px-6 py-3">
                    <span className="flex items-center gap-2 text-sm font-semibold text-slate-300">
                      <Terminal className="h-4 w-4 text-purple-400" /> Candidate Code Workspace
                    </span>
                    <div className="flex flex-wrap items-center gap-2">
                      <button
                        type="button"
                        onClick={() => addWorkspaceFolder(currentProblem)}
                        className="inline-flex items-center gap-1.5 rounded-lg border border-slate-700 bg-slate-800 px-3 py-1.5 text-xs font-bold text-slate-200 hover:border-purple-500 hover:text-white">
                        <FolderPlus className="h-3.5 w-3.5" /> Folder
                      </button>
                      <button
                        type="button"
                        onClick={() => addWorkspaceFile(currentProblem)}
                        className="inline-flex items-center gap-1.5 rounded-lg border border-slate-700 bg-slate-800 px-3 py-1.5 text-xs font-bold text-slate-200 hover:border-purple-500 hover:text-white">
                        <FilePlus className="h-3.5 w-3.5" /> File
                      </button>
                      <span
                        title="This problem's language is fixed by your faculty and cannot be changed."
                        className="flex items-center gap-1.5 rounded-lg border border-purple-500/30 bg-purple-500/15 px-3 py-1.5 text-xs font-bold text-purple-300">
                        <Lock className="h-3 w-3" /> {LANGUAGE_LABELS[currentProblem.language] || currentProblem.language}
                      </span>
                    </div>
                  </div>

                  <div className="grid min-h-[360px] flex-1 grid-cols-1 md:grid-cols-[220px_minmax(0,1fr)]">
                    <aside className="border-b border-slate-800 bg-slate-950/80 p-3 md:border-b-0 md:border-r">
                      <div className="mb-2 flex items-center justify-between text-[12px] font-black uppercase tracking-wider text-slate-500">
                        <span>Project Files</span>
                        <span>{currentWorkspaceFiles.filter((item) => item.type === 'file').length}</span>
                      </div>
                      <div className="max-h-80 space-y-1 overflow-y-auto pr-1">
                        {currentWorkspaceFiles.map((item) => {
                          const isActive = item.type === 'file' && item.path === currentAnswer?.activeFilePath;
                          const depth = Math.max(0, item.path.split('/').length - 1);
                          return (
                            <div key={`${item.type}-${item.path}`} className={`group flex items-center gap-1 rounded-lg text-xs ${isActive ? 'bg-purple-600/25 text-white' : 'text-slate-300 hover:bg-slate-800/80'}`}>
                              <button
                                type="button"
                                onClick={() => item.type === 'file' && selectWorkspaceFile(currentProblem, item.path)}
                                className="flex min-w-0 flex-1 items-center gap-2 px-2 py-2 text-left"
                                style={{ paddingLeft: `${8 + depth * 14}px` }}>
                                {item.type === 'folder' ? <Folder className="h-3.5 w-3.5 flex-shrink-0 text-amber-400" /> : <FileText className="h-3.5 w-3.5 flex-shrink-0 text-blue-300" />}
                                <span className="truncate font-semibold">{item.path.split('/').pop()}</span>
                              </button>
                              <button
                                type="button"
                                onClick={() => deleteWorkspaceItem(currentProblem, item)}
                                className="mr-1 rounded p-1 text-slate-500 opacity-0 hover:bg-rose-500/20 hover:text-rose-300 group-hover:opacity-100"
                                title={`Delete ${item.path}`}>
                                <Trash2 className="h-3 w-3" />
                              </button>
                            </div>
                          );
                        })}
                      </div>
                      <p className="mt-3 rounded-lg border border-slate-800 bg-slate-900 p-2 text-[12px] leading-relaxed text-slate-500">
                        Submit stores the full file tree for Gemini/faculty review. Run Code executes the active file only.
                      </p>
                    </aside>

                    <textarea
                      data-exam-editor="true"
                      value={currentEditorValue}
                      onChange={(e) => changeCoding(currentProblem.id, 'code', e.target.value)}
                      onKeyDown={(e) => {
                        // Tab inserts 4 spaces instead of moving focus
                        if (e.key === 'Tab') {
                          e.preventDefault();
                          const el = e.target;
                          const { selectionStart: s, selectionEnd: en, value } = el;
                          const next = `${value.slice(0, s)}    ${value.slice(en)}`;
                          changeCoding(currentProblem.id, 'code', next);
                          requestAnimationFrame(() => { el.selectionStart = el.selectionEnd = s + 4; });
                        }
                      }}
                      spellCheck="false"
                      placeholder="Write your solution here..."
                      className="min-h-[360px] flex-1 resize-none bg-slate-950 p-6 font-mono text-sm leading-relaxed text-slate-100 outline-none"
                    />
                  </div>

                  {/* Run Code panel */}
                  <div className="border-t border-slate-800 bg-slate-900">
                    <div className="flex flex-wrap items-center gap-3 px-6 py-3">
                      <button
                        type="button"
                        onClick={() => runCode(currentProblem)}
                        disabled={runningId === currentProblem.id}
                        className="flex items-center gap-2 rounded-xl bg-emerald-600 px-4 py-2 text-xs font-bold text-white shadow transition hover:bg-emerald-700 disabled:cursor-not-allowed disabled:opacity-60">
                        {runningId === currentProblem.id ? (
                          <><Loader2 className="h-3.5 w-3.5 animate-spin" /> Running…</>
                        ) : (
                          <><Play className="h-3.5 w-3.5" /> Run Code</>
                        )}
                      </button>
                      <input
                        type="text"
                        value={customStdin[currentProblem.id] || ''}
                        onChange={(e) => setCustomStdin((p) => ({ ...p, [currentProblem.id]: e.target.value }))}
                        placeholder="Custom input (optional — defaults to the sample input above)"
                        className="min-w-0 flex-1 rounded-lg border border-slate-700 bg-slate-800 px-3 py-2 text-xs text-slate-200 placeholder:text-slate-500 outline-none focus:border-emerald-500"
                      />
                    </div>

                    {runResults[currentProblem.id] && (
                      <div className="max-h-56 overflow-y-auto border-t border-slate-800 px-6 py-3 font-mono text-xs">
                        {runResults[currentProblem.id].error ? (
                          <div className="flex items-start gap-2 text-rose-400">
                            <AlertCircle className="mt-0.5 h-3.5 w-3.5 flex-shrink-0" />
                            <span>{runResults[currentProblem.id].error}</span>
                          </div>
                        ) : (
                          <>
                            {runResults[currentProblem.id].compile_error && (
                              <div className="mb-1 font-bold text-amber-400">Compile error:</div>
                            )}
                            {runResults[currentProblem.id].stdout && (
                              <pre className="whitespace-pre-wrap text-emerald-400">{runResults[currentProblem.id].stdout}</pre>
                            )}
                            {runResults[currentProblem.id].stderr && (
                              <pre className="mt-1 whitespace-pre-wrap text-rose-400">{runResults[currentProblem.id].stderr}</pre>
                            )}
                            {!runResults[currentProblem.id].stdout && !runResults[currentProblem.id].stderr && (
                              <span className="text-slate-500">(no output)</span>
                            )}
                            {runResults[currentProblem.id].timed_out && (
                              <div className="mt-1 font-bold text-amber-400">Execution timed out.</div>
                            )}
                          </>
                        )}
                      </div>
                    )}
                  </div>

                  <div className="flex items-center justify-between border-t border-slate-800 bg-slate-900 px-6 py-3 text-xs text-slate-400">
                    <span>Running code never affects your marks — only what you submit is graded.</span>
                    <span className="font-semibold text-emerald-400">Auto-saving to server</span>
                  </div>
                </>
              )}
            </div>
          </div>
        )}
      </main>

      {/* Workspace file/folder modal — custom in-app modal avoids browser prompt/confirm dialogs that exit fullscreen. */}
      {workspaceModal && (
        <div className="fixed inset-0 z-[94] flex items-center justify-center bg-black/70 p-4 backdrop-blur-sm">
          <div className="w-full max-w-lg space-y-5 rounded-3xl border border-slate-700 bg-slate-900 p-7 shadow-2xl">
            <div className="flex items-center gap-3">
              <div className="flex h-11 w-11 items-center justify-center rounded-2xl bg-purple-500/20 text-purple-300">
                {workspaceModal.type === 'folder' ? <FolderPlus className="h-6 w-6" />
                  : workspaceModal.type === 'file' ? <FilePlus className="h-6 w-6" />
                    : workspaceModal.type === 'delete' ? <Trash2 className="h-6 w-6" />
                      : <AlertCircle className="h-6 w-6" />}
              </div>
              <div>
                <h3 className="text-lg font-black text-white">
                  {workspaceModal.type === 'folder' ? 'Create Folder'
                    : workspaceModal.type === 'file' ? 'Create File'
                      : workspaceModal.type === 'delete' ? 'Delete Workspace Item'
                        : workspaceModal.title || 'Workspace Notice'}
                </h3>
                <p className="text-xs font-semibold text-slate-400">
                  This dialog stays inside fullscreen, so it will not create a proctoring violation.
                </p>
              </div>
            </div>

            {workspaceModal.type === 'message' ? (
              <p className="rounded-2xl border border-amber-500/30 bg-amber-500/10 p-4 text-sm font-semibold text-amber-100">
                {workspaceModal.message}
              </p>
            ) : workspaceModal.type === 'delete' ? (
              <p className="rounded-2xl border border-rose-500/30 bg-rose-500/10 p-4 text-sm text-rose-100">
                Delete <b>{workspaceModal.item?.type === 'folder' ? 'folder and nested files' : 'file'}</b>{' '}
                <span className="font-mono font-bold">{workspaceModal.item?.path}</span>?
              </p>
            ) : (
              <form onSubmit={(e) => { e.preventDefault(); submitWorkspaceModal(); }} className="space-y-3">
                <label className="block text-xs font-black uppercase tracking-wider text-slate-400">
                  {workspaceModal.type === 'folder' ? 'Folder path' : 'File path'}
                </label>
                <input
                  data-exam-editor="true"
                  autoFocus
                  value={workspacePathInput}
                  onChange={(e) => setWorkspacePathInput(e.target.value)}
                  placeholder={workspaceModal.type === 'folder' ? 'src/components' : 'src/utils.py'}
                  className="w-full rounded-xl border border-slate-700 bg-slate-950 px-4 py-3 font-mono text-sm text-white outline-none focus:border-purple-500 focus:ring-2 focus:ring-purple-500/30"
                />
                <p className="text-xs text-slate-500">
                  Use `/` for folders. Examples: <span className="font-mono text-slate-300">main.py</span>, <span className="font-mono text-slate-300">src/App.jsx</span>.
                </p>
                {workspaceModalError && <p className="text-xs font-bold text-rose-300">{workspaceModalError}</p>}
              </form>
            )}

            <div className="grid grid-cols-2 gap-3">
              <button type="button" onClick={closeWorkspaceModal}
                className="rounded-xl bg-slate-800 px-4 py-3 text-sm font-semibold text-white transition hover:bg-slate-700">
                Cancel
              </button>
              <button type="button" onClick={submitWorkspaceModal}
                className={`rounded-xl px-4 py-3 text-sm font-black text-white shadow transition ${workspaceModal.type === 'delete' ? 'bg-rose-600 hover:bg-rose-700' : 'bg-purple-600 hover:bg-purple-700'}`}>
                {workspaceModal.type === 'delete' ? 'Delete' : workspaceModal.type === 'message' ? 'OK' : 'Create'}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Submit confirmation */}
      {showConfirmModal && (
        <div className="fixed inset-0 z-[95] flex items-center justify-center bg-black/70 p-4 backdrop-blur-sm">
          <div className="w-full max-w-md space-y-6 rounded-3xl border border-slate-700 bg-slate-900 p-8 shadow-2xl">
            <div className="mx-auto flex h-14 w-14 items-center justify-center rounded-2xl bg-amber-500/20 text-amber-400">
              <AlertCircle className="h-8 w-8" />
            </div>
            <div className="space-y-2 text-center">
              <h3 className="text-xl font-bold text-white">Submit Examination?</h3>
              <p className="text-sm leading-relaxed text-slate-300">
                Once submitted your <b className="text-amber-400">temporary OTP is cleared</b> and your
                answers are evaluated immediately. This cannot be undone.
              </p>
            </div>

            <div className="space-y-2 rounded-2xl border border-slate-800 bg-slate-950 p-4 text-xs text-slate-400">
              <div className="flex justify-between">
                <span>MCQs answered</span>
                <b className={answeredCount < mcqs.length ? 'text-amber-400' : 'text-emerald-400'}>
                  {answeredCount} / {mcqs.length}
                </b>
              </div>
              <div className="flex justify-between">
                <span>Coding problems attempted</span>
                <b className="text-white">
                  {codingProblems.filter((p) => isCodingWorkspaceAttempted(p, codingAnswers[p.id])).length} / {codingProblems.length}
                </b>
              </div>
              <div className="flex justify-between">
                <span>Time remaining</span>
                <b className="font-mono text-white">{formatTime(timeLeft)}</b>
              </div>
              {violations > 0 && (
                <div className="flex justify-between border-t border-slate-800 pt-2">
                  <span>Proctoring violations</span>
                  <b className="text-rose-400">{violations}</b>
                </div>
              )}
            </div>

            <div className="grid grid-cols-2 gap-3">
              <button type="button" disabled={submitting} onClick={() => setShowConfirmModal(false)}
                className="rounded-xl bg-slate-800 px-4 py-3 text-sm font-semibold text-white transition hover:bg-slate-700 disabled:opacity-50">
                Continue Exam
              </button>
              <button type="button" disabled={submitting} onClick={() => doSubmit(false)}
                className="flex items-center justify-center gap-2 rounded-xl bg-emerald-600 px-4 py-3 text-sm font-bold text-white shadow transition hover:bg-emerald-700 disabled:opacity-60">
                {submitting ? <><Loader2 className="h-4 w-4 animate-spin" /> Submitting…</> : 'Confirm Submit'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}



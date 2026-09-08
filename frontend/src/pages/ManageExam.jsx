import React, { useState, useEffect } from 'react';
import { useParams, Link, useLocation } from 'react-router-dom';
import api from '../api/axios';
import { useAuth } from '../context/AuthContext';
import { useToast } from '../components/ToastProvider';
import './workflow-page.css';
import { PlusCircle, Trash2, Code, HelpCircle, Key, ArrowLeft, ShieldCheck, Lock, AlertTriangle, Loader2, Radio, Ban, BarChart3 } from 'lucide-react';

const tabFromPath = (pathname) => {
  if (/\/otps\/?$/.test(pathname)) return 'otps';
  if (/\/live-status\/?$/.test(pathname)) return 'roster';
  return 'mcqs';
};

export default function ManageExam() {
  const { examId } = useParams();
  const location = useLocation();
  const { setActiveExam, user } = useAuth();
  const { toast, confirm } = useToast();
  const [examData, setExamData] = useState(null);
  const [mcqs, setMcqs] = useState([]);
  const [codingProblems, setCodingProblems] = useState([]);
  const [otps, setOtps] = useState([]);
  const [activeTab, setActiveTab] = useState(() => tabFromPath(location.pathname));
  const [publishing, setPublishing] = useState(false);
  const [otpBusy, setOtpBusy] = useState(false);
  const [bankItems, setBankItems] = useState([]);
  const [bankPick, setBankPick] = useState('');
  const [codingBankItems, setCodingBankItems] = useState([]);
  const [codingBankPick, setCodingBankPick] = useState('');
  const [bulkFile, setBulkFile] = useState(null);
  const [bulkImporting, setBulkImporting] = useState(false);
  const [bulkResult, setBulkResult] = useState(null);

  // New MCQ form state
  const [qText, setQText] = useState('');
  const [optA, setOptA] = useState('');
  const [optB, setOptB] = useState('');
  const [optC, setOptC] = useState('');
  const [optD, setOptD] = useState('');
  const [qType, setQType] = useState('single');       // 'single' | 'multi'
  const [correctOpt, setCorrectOpt] = useState('A');   // single-select answer
  const [correctOpts, setCorrectOpts] = useState([]);  // multi-select answers
  const [mcqMarks, setMcqMarks] = useState(4);

  // New Coding Problem form state
  const [cTitle, setCTitle] = useState('');
  const [cStatement, setCStatement] = useState('');
  const [cInFormat, setCInFormat] = useState('');
  const [cOutFormat, setCOutFormat] = useState('');
  const [cSampleIn, setCSampleIn] = useState('');
  const [cSampleOut, setCSampleOut] = useState('');
  const [cMarks, setCMarks] = useState(30);
  const [cLanguage, setCLanguage] = useState('python'); // fixed compiler language for the whole problem
  // 2-3 reference solutions array — language always follows cLanguage, not per-solution
  const [refSolutions, setRefSolutions] = useState([
    { title: 'Solution 1: Optimal Approach', code: '', logic_explanation: '' },
    { title: 'Solution 2: Alternative Approach', code: '', logic_explanation: '' }
  ]);

  // Roster (#14) — who joined / submitted / hasn't started, plus UFM locks
  const [roster, setRoster] = useState([]);
  const [rosterCounts, setRosterCounts] = useState(null);
  const [rosterLoading, setRosterLoading] = useState(false);
  const [resultStatus, setResultStatus] = useState(null);
  const [rosterCanManage, setRosterCanManage] = useState(true);
  const [resultPublishing, setResultPublishing] = useState(false);
  const [verifyingStudentId, setVerifyingStudentId] = useState(null);

  const LANGUAGE_LABELS = { python: 'Python 3', javascript: 'JavaScript (Node.js)', cpp: 'C++', java: 'Java' };
  const languageAliases = { python: 'python', 'python 3': 'python', javascript: 'javascript', 'node.js': 'javascript', nodejs: 'javascript', 'c++': 'cpp', cpp: 'cpp', java: 'java' };
  const assignedLanguages = (user?.faculty_subjects || '')
    .split(',').map((item) => languageAliases[item.trim().toLowerCase()]).filter(Boolean);
  // Older faculty profiles may not yet have a programming-subject assignment.
  // Keep those accounts usable, while assigned faculty only see their language.
  const codingLanguages = assignedLanguages.length ? [...new Set(assignedLanguages)] : Object.keys(LANGUAGE_LABELS);

  useEffect(() => {
    if (!codingLanguages.includes(cLanguage)) setCLanguage(codingLanguages[0]);
  }, [user?.faculty_subjects]);

  const [loading, setLoading] = useState(true);

  const fetchManageData = async () => {
    try {
      const res = await api.get(`exams/${examId}/manage/`);
      setExamData(res.data.exam);
      if (res.data.exam) setActiveExam(res.data.exam);
      setMcqs(res.data.mcqs || []);
      setCodingProblems(res.data.coding_problems || []);
      setOtps(res.data.otps || []);
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchManageData();
  }, [examId]);

  useEffect(() => {
    api.get('question-bank/', { params: { kind: 'mcq' } })
      .then(({ data }) => setBankItems((data.items || []).filter((item) => item.payload?.option_a)))
      .catch(() => setBankItems([]));
    api.get('question-bank/', { params: { kind: 'coding' } })
      .then(({ data }) => setCodingBankItems(data.items || []))
      .catch(() => setCodingBankItems([]));
  }, [examId]);

  useEffect(() => {
    setActiveTab(tabFromPath(location.pathname));
  }, [location.pathname]);


  const loadRoster = async () => {
    setRosterLoading(true);
    try {
      const res = await api.get(`exams/${examId}/roster/`);
      setRoster(res.data.roster || []);
      setRosterCounts(res.data.counts || null);
      setResultStatus(res.data.result_status || null);
      setRosterCanManage(res.data.can_manage !== false);
    } catch (err) {
      console.error(err);
    } finally {
      setRosterLoading(false);
    }
  };

  useEffect(() => {
    if (activeTab === 'roster') loadRoster();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [activeTab, examId]);

  const handleVerifyFromRoster = async (studentId) => {
    if (verifyingStudentId) return;
    setVerifyingStudentId(studentId);
    try {
      await api.post(`exams/${examId}/students/${studentId}/verify/`, {});
      toast({ type: 'success', title: 'Student verified', message: 'This attempt is now reviewed for result publishing.' });
      loadRoster();
    } catch (err) {
      toast({ type: 'error', title: 'Could not verify student', message: err.response?.data?.error || 'Open analysis and try again.' });
    } finally {
      setVerifyingStudentId(null);
    }
  };

  const handleAddMCQ = async (e) => {
    e.preventDefault();
    if (examData?.content_locked) {
      toast({ type: 'warning', title: 'Exam paper locked', message: 'This exam has already been published. Questions and solutions cannot be changed.' });
      return;
    }
    if (qType === 'multi' && correctOpts.length < 2) {
      toast({ type: 'warning', title: 'Select more answers', message: 'Choose at least 2 correct options for a multi-select question.' });
      return;
    }
    try {
      await api.post(`exams/${examId}/mcqs/`, {
        question_text: qText,
        option_a: optA,
        option_b: optB,
        option_c: optC,
        option_d: optD,
        question_type: qType,
        correct_option: qType === 'single' ? correctOpt : '',
        correct_options: qType === 'multi' ? correctOpts : [],
        marks: parseFloat(mcqMarks)
      });
      setQText(''); setOptA(''); setOptB(''); setOptC(''); setOptD(''); setCorrectOpts([]); setBankPick('');
      fetchManageData();
    } catch (err) {
      toast({ type: 'error', title: 'Error adding MCQ', message: err.response?.data?.error || 'Please check the question fields.' });
    }
  };

  const toggleCorrectOpt = (k) => setCorrectOpts((p) => (p.includes(k) ? p.filter((o) => o !== k) : [...p, k].sort()));

  const loadFromBank = (itemId) => {
    setBankPick(itemId);
    const item = bankItems.find((b) => String(b.id) === String(itemId));
    if (!item) return;
    const p = item.payload || {};
    setQText(p.question_text || item.title || '');
    setOptA(p.option_a || ''); setOptB(p.option_b || ''); setOptC(p.option_c || ''); setOptD(p.option_d || '');
    setQType('single');
    setCorrectOpt(p.correct_option || 'A');
    setCorrectOpts([]);
    toast({ type: 'info', title: 'Loaded from question bank', message: 'Review the question, adjust marks, then add it to this exam.' });
  };


  const loadCodingFromBank = (itemId) => {
    setCodingBankPick(itemId);
    const item = codingBankItems.find((b) => String(b.id) === String(itemId));
    if (!item) return;
    const p = item.payload || {};
    setCTitle(p.title || item.title || 'Coding problem');
    setCStatement(p.problem_statement || p.statement || item.title || '');
    setCInFormat(p.input_format || '');
    setCOutFormat(p.output_format || '');
    setCSampleIn(p.sample_input || '');
    setCSampleOut(p.sample_output || '');
    toast({ type: 'info', title: 'Loaded coding problem', message: 'Review the problem, set marks/references, then add it to this exam.' });
  };

  const downloadMcqTemplate = () => {
    const csv = 'question_text,option_a,option_b,option_c,option_d,correct_option,marks,negative_marks\n'
      + 'What is 2 + 2?,3,4,5,6,B,4,0\n'
      + 'Which are prime numbers?,2,3,4,9,"A,B",6,0\n';
    const url = URL.createObjectURL(new Blob([csv], { type: 'text/csv' }));
    const link = document.createElement('a');
    link.href = url; link.download = 'mcq-import-template.csv'; link.click();
    URL.revokeObjectURL(url);
  };

  const importMcqsFromCsv = async () => {
    if (!bulkFile) return;
    setBulkImporting(true);
    setBulkResult(null);
    try {
      const form = new FormData();
      form.append('file', bulkFile);
      const res = await api.post(`exams/${examId}/mcqs/bulk-import/`, form);
      setBulkResult(res.data);
      setBulkFile(null);
      if (res.data.created > 0) {
        toast({ type: 'success', title: 'Bulk import complete', message: `${res.data.created} question(s) added.` });
        fetchManageData();
      }
    } catch (err) {
      toast({ type: 'error', title: 'Import failed', message: err.response?.data?.error || 'Could not read that CSV file.' });
    } finally {
      setBulkImporting(false);
    }
  };

  const handleDeleteMCQ = async (mcqId) => {
    if (examData?.content_locked || examData?.is_active) {
      toast({ type: 'warning', title: 'Exam paper locked', message: 'This exam has already been published. Questions and solutions cannot be changed.' });
      return;
    }
    const ok = await confirm({
      title: 'Delete MCQ question?',
      message: 'This permanently removes the question from the exam paper and frees its marks budget.',
      confirmText: 'Delete question',
      danger: true,
    });
    if (!ok) return;
    await api.delete(`exams/${examId}/mcqs/${mcqId}/`);
    toast({ type: 'success', title: 'Question deleted' });
    fetchManageData();
  };

  const handleRefChange = (idx, field, val) => {
    const updated = [...refSolutions];
    updated[idx][field] = val;
    setRefSolutions(updated);
  };

  const handleAddRefSlot = () => {
    if (refSolutions.length < 3) {
      setRefSolutions([
        ...refSolutions,
        { title: `Solution ${refSolutions.length + 1}: Brute Force Approach`, code: '', logic_explanation: '' }
      ]);
    }
  };

  const handleRemoveRefSlot = (idx) => {
    setRefSolutions(refSolutions.filter((_, i) => i !== idx));
  };

  const handleDeleteRefSolution = async (problemId, solutionId) => {
    if (examData?.content_locked) {
      toast({ type: 'warning', title: 'Exam paper locked', message: 'This exam has already been published. Questions and solutions cannot be changed.' });
      return;
    }
    const ok = await confirm({ title: 'Delete reference solution?', message: 'This solution will be removed permanently.', confirmText: 'Delete solution', danger: true });
    if (!ok) return;
    try {
      await api.delete(`coding-problems/${problemId}/solutions/${solutionId}/`);
      fetchManageData();
    } catch (err) {
      toast({ type: 'error', title: 'Error deleting reference solution', message: err.response?.data?.error || 'Please try again.' });
    }
  };

  const handleAddCoding = async (e) => {
    e.preventDefault();
    if (examData?.content_locked) {
      toast({ type: 'warning', title: 'Exam paper locked', message: 'Coding problems and reference solutions cannot be changed after publish.' });
      return;
    }
    try {
      await api.post(`exams/${examId}/coding/`, {
        title: cTitle,
        problem_statement: cStatement,
        input_format: cInFormat,
        output_format: cOutFormat,
        sample_input: cSampleIn,
        sample_output: cSampleOut,
        marks: parseFloat(cMarks),
        language: cLanguage,
        reference_solutions: refSolutions.filter(r => r.title && r.code)
      });
      setCTitle(''); setCStatement(''); setCSampleIn(''); setCSampleOut('');
      setRefSolutions([
        { title: 'Solution 1: Optimal Approach', code: '', logic_explanation: '' },
        { title: 'Solution 2: Alternative Approach', code: '', logic_explanation: '' }
      ]);
      fetchManageData();
    } catch (err) {
      toast({ type: 'error', title: 'Error adding coding problem', message: err.response?.data?.error || 'Please check the problem fields.' });
    }
  };

  const handleDeleteCoding = async (probId) => {
    if (examData?.content_locked) {
      toast({ type: 'warning', title: 'Exam paper locked', message: 'Coding problems and reference solutions cannot be changed after publish.' });
      return;
    }
    const ok = await confirm({
      title: 'Delete coding problem?',
      message: 'This permanently removes the coding problem, reference solutions.',
      confirmText: 'Delete problem',
      danger: true,
    });
    if (!ok) return;
    await api.delete(`exams/${examId}/coding/${probId}/`);
    toast({ type: 'success', title: 'Coding problem deleted' });
    fetchManageData();
  };

  const handleGenerateOTPs = async () => {
    if (otpBusy) return;
    setOtpBusy(true);
    try {
      const res = await api.post(`exams/${examId}/otps/`, {});
      toast({ type: 'success', title: 'OTPs generated', message: res.data.message });
      fetchManageData();
    } catch (err) {
      toast({ type: 'error', title: 'Error generating OTPs', message: err.response?.data?.error || 'Please try again.' });
    } finally {
      setOtpBusy(false);
    }
  };

  const handleClearOTPs = async () => {
    if (otpBusy) return;
    const ok = await confirm({
      title: 'Clear all active OTPs?',
      message: 'Students will not be able to start the exam until OTPs are generated again.',
      confirmText: 'Clear OTPs',
      danger: true,
    });
    if (!ok) return;
    setOtpBusy(true);
    try {
      await api.delete(`exams/${examId}/otps/`);
      toast({ type: 'success', title: 'OTPs cleared' });
      fetchManageData();
    } finally {
      setOtpBusy(false);
    }
  };


  const handlePublishExam = async () => {
    setPublishing(true);
    try {
      const res = await api.post(`exams/${examId}/publish/`, {});
      toast({ type: 'success', title: 'Exam published', message: res.data.message || 'Exam published successfully.' });
      fetchManageData();
    } catch (err) {
      toast({ type: 'error', title: 'Cannot publish exam', message: err.response?.data?.error || 'Allocate exactly the total marks first.' });
    } finally {
      setPublishing(false);
    }
  };

  const handleUnpublishExam = async () => {
    const ok = await confirm({
      title: 'Disable exam start?',
      message: 'Students will not be able to start this exam. The published paper remains locked.',
      confirmText: 'Disable start',
      danger: true,
    });
    if (!ok) return;
    setPublishing(true);
    try {
      const res = await api.delete(`exams/${examId}/publish/`);
      toast({ type: 'info', title: 'Exam disabled', message: res.data.message || 'Exam unpublished.' });
      fetchManageData();
    } catch (err) {
      toast({ type: 'error', title: 'Could not unpublish exam', message: err.response?.data?.error || 'Please try again.' });
    } finally {
      setPublishing(false);
    }
  };

  const handlePublishResults = async () => {
    setResultPublishing(true);
    try {
      const res = await api.post(`exams/${examId}/publish-results/`, {});
      toast({ type: 'success', title: 'Results published', message: res.data.message || 'Students can now view results.' });
      setResultStatus(res.data.result_status || null);
      loadRoster();
      fetchManageData();
    } catch (err) {
      toast({ type: 'error', title: 'Cannot publish results', message: err.response?.data?.error || 'Verify all student attempts first.' });
    } finally {
      setResultPublishing(false);
    }
  };


  if (loading) {
    return (
      <div className="min-h-[70vh] flex items-center justify-center">
        <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-amber-600"></div>
      </div>
    );
  }

  const allocatedMarks = [...mcqs, ...codingProblems].reduce((sum, item) => sum + Number(item.marks || 0), 0);
  const totalMarks = Number(examData?.total_marks || 0);
  const rawRemainingMarks = totalMarks - allocatedMarks;
  const remainingMarks = Math.max(0, rawRemainingMarks);
  const canPublish = allocatedMarks > 0 && Math.abs(rawRemainingMarks) <= 0.001;
  const isPublished = Boolean(examData?.is_active && canPublish);
  const isContentLocked = Boolean(examData?.content_locked || examData?.is_active);

  return (
    <div className="app-page workflow-page manage-exam-page">
      
      {/* Header */}
      <div className="bg-white rounded-3xl p-8 shadow-xl border border-slate-200 flex flex-col md:flex-row items-center justify-between gap-6">
        <div className="flex items-center space-x-4">
          <Link to="/" className="p-2.5 bg-slate-100 rounded-xl hover:bg-slate-200 transition">
            <ArrowLeft className="w-5 h-5 text-slate-700" />
          </Link>
          <div>
            <h1 className="text-2xl font-black text-slate-900">{examData?.title}</h1>
            <p className="text-slate-600 text-sm">Faculty Question Bank & Logic Configuration</p>
            <p className="mt-1 text-xs font-semibold text-slate-500">
              Marks allocated: <span className="font-mono text-slate-800">{allocatedMarks}</span> / {examData?.total_marks} · Remaining: <span className={remainingMarks > 0 ? 'font-mono text-emerald-700' : 'font-mono text-rose-700'}>{remainingMarks}</span>
            </p>
            <p className={`mt-2 inline-flex rounded-full px-3 py-1 text-xs font-black uppercase tracking-wide ${isPublished ? 'bg-emerald-100 text-emerald-800 border border-emerald-200' : 'bg-amber-100 text-amber-800 border border-amber-200'}`}>
              {isPublished ? 'Published / Active' : 'Not Published'}
            </p>
          </div>
        </div>

        {/* Tab selector */}
        <div className="flex items-center space-x-2 bg-slate-100 p-1 rounded-xl">
          <button
            onClick={() => setActiveTab('mcqs')}
            className={`px-4 py-2 rounded-lg text-sm font-bold transition flex items-center gap-1.5 ${
              activeTab === 'mcqs' ? 'bg-white text-blue-600 shadow-sm' : 'text-slate-600 hover:text-slate-900'
            }`}
          >
            <HelpCircle className="w-4 h-4" />
            <span>MCQs ({mcqs.length})</span>
          </button>
          <button
            onClick={() => setActiveTab('coding')}
            className={`px-4 py-2 rounded-lg text-sm font-bold transition flex items-center gap-1.5 ${
              activeTab === 'coding' ? 'bg-white text-purple-600 shadow-sm' : 'text-slate-600 hover:text-slate-900'
            }`}
          >
            <Code className="w-4 h-4" />
            <span>Coding Problems ({codingProblems.length})</span>
          </button>
          <button
            onClick={() => setActiveTab('otps')}
            className={`px-4 py-2 rounded-lg text-sm font-bold transition flex items-center gap-1.5 ${
              activeTab === 'otps' ? 'bg-white text-amber-600 shadow-sm' : 'text-slate-600 hover:text-slate-900'
            }`}
          >
            <Key className="w-4 h-4" />
            <span>Temporary OTPs ({otps.length})</span>
          </button>
          <button
            onClick={() => setActiveTab('roster')}
            className={`px-4 py-2 rounded-lg text-sm font-bold transition flex items-center gap-1.5 ${
              activeTab === 'roster' ? 'bg-white text-emerald-600 shadow-sm' : 'text-slate-600 hover:text-slate-900'
            }`}
          >
            <Radio className="w-4 h-4" />
            <span>Live Status{rosterCounts ? ` (${rosterCounts.in_progress + rosterCounts.submitted + rosterCounts.ufm}/${roster.length})` : ''}</span>
          </button>
        </div>
      </div>

      {isContentLocked && (
        <div className="rounded-2xl border border-amber-200 bg-amber-50 p-4 text-sm text-amber-900">
          <b>Exam paper locked:</b> This exam has been published. Faculty can still view questions, OTPs, live status, analytics and reports, but MCQs, coding problems, reference solutions can no longer be added, edited or deleted.
        </div>
      )}

      {activeTab === 'mcqs' && (
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-8">
          
          {/* Add MCQ Form */}
          <div className="lg:col-span-5 bg-white rounded-3xl shadow-lg border border-slate-200 p-6 space-y-5">
            <h3 className="font-bold text-slate-800 text-lg flex items-center gap-2 border-b border-slate-100 pb-3">
              <PlusCircle className="w-5 h-5 text-blue-600" /> Add New MCQ Question
            </h3>

            {false && bankItems.length > 0 && !examData?.content_locked && (
              <div className="workflow-bank-picker">
                <label htmlFor="bank-picker">Insert from your question bank</label>
                <select id="bank-picker" value={bankPick} onChange={(e) => loadFromBank(e.target.value)}>
                  <option value="">Choose a saved question…</option>
                  {bankItems.map((item) => <option key={item.id} value={item.id}>{item.title || 'Untitled question'}</option>)}
                </select>
              </div>
            )}

            {!examData?.content_locked && (
              <div className="workflow-bulk-import">
                <div className="workflow-bulk-import__head">
                  <span>Bulk import from CSV</span>
                  <button type="button" onClick={downloadMcqTemplate}>Download template</button>
                </div>
                <div className="workflow-bulk-import__controls">
                  <input
                    type="file" accept=".csv,text/csv"
                    onChange={(e) => { setBulkFile(e.target.files?.[0] || null); setBulkResult(null); }}
                  />
                  <button type="button" className="app-button app-button--quiet" disabled={!bulkFile || bulkImporting} onClick={importMcqsFromCsv}>
                    {bulkImporting ? 'Importing…' : 'Import'}
                  </button>
                </div>
                {bulkResult && (
                  <p className="workflow-bulk-import__result">
                    {bulkResult.created} question{bulkResult.created === 1 ? '' : 's'} added.
                    {bulkResult.errors.length > 0 && ` ${bulkResult.errors.length} row(s) skipped: ${bulkResult.errors.slice(0, 3).map((e) => `line ${e.line} (${e.error})`).join('; ')}${bulkResult.errors.length > 3 ? '…' : ''}`}
                  </p>
                )}
              </div>
            )}
            
            <form onSubmit={handleAddMCQ} className="space-y-4 text-sm">
              <div>
                <label className="font-semibold text-slate-700">Question Text</label>
                <textarea
                  rows="3"
                  required
                  value={qText}
                  onChange={(e) => setQText(e.target.value)}
                  placeholder="Enter multiple choice question..."
                  className="w-full mt-1 px-3 py-2 border rounded-xl focus:ring-blue-500"
                />
              </div>

              <div>
                <label className="font-semibold text-slate-700">Question Type</label>
                <div className="mt-1 grid grid-cols-2 gap-2">
                  <button type="button" onClick={() => { setQType('single'); setCorrectOpts([]); }}
                    className={`rounded-xl border py-2 text-xs font-bold transition ${
                      qType === 'single' ? 'border-blue-500 bg-blue-50 text-blue-700' : 'border-slate-300 text-slate-500'
                    }`}>
                    Single Correct
                  </button>
                  <button type="button" onClick={() => setQType('multi')}
                    className={`rounded-xl border py-2 text-xs font-bold transition ${
                      qType === 'multi' ? 'border-indigo-500 bg-indigo-50 text-indigo-700' : 'border-slate-300 text-slate-500'
                    }`}>
                    Multiple Correct
                  </button>
                </div>
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="font-semibold text-slate-700">Option A</label>
                  <input
                    type="text"
                    required
                    value={optA}
                    onChange={(e) => setOptA(e.target.value)}
                    className="w-full mt-1 px-3 py-2 border rounded-xl"
                  />
                </div>
                <div>
                  <label className="font-semibold text-slate-700">Option B</label>
                  <input
                    type="text"
                    required
                    value={optB}
                    onChange={(e) => setOptB(e.target.value)}
                    className="w-full mt-1 px-3 py-2 border rounded-xl"
                  />
                </div>
                <div>
                  <label className="font-semibold text-slate-700">Option C</label>
                  <input
                    type="text"
                    required
                    value={optC}
                    onChange={(e) => setOptC(e.target.value)}
                    className="w-full mt-1 px-3 py-2 border rounded-xl"
                  />
                </div>
                <div>
                  <label className="font-semibold text-slate-700">Option D</label>
                  <input
                    type="text"
                    required
                    value={optD}
                    onChange={(e) => setOptD(e.target.value)}
                    className="w-full mt-1 px-3 py-2 border rounded-xl"
                  />
                </div>
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="font-semibold text-slate-700">
                    {qType === 'multi' ? 'Correct Options (select 2+)' : 'Correct Option'}
                  </label>
                  {qType === 'single' ? (
                    <select
                      value={correctOpt}
                      onChange={(e) => setCorrectOpt(e.target.value)}
                      className="w-full mt-1 px-3 py-2 border rounded-xl font-bold bg-slate-50"
                    >
                      <option value="A">Option A</option>
                      <option value="B">Option B</option>
                      <option value="C">Option C</option>
                      <option value="D">Option D</option>
                    </select>
                  ) : (
                    <div className="mt-1 grid grid-cols-4 gap-1.5">
                      {['A', 'B', 'C', 'D'].map((k) => (
                        <button key={k} type="button" onClick={() => toggleCorrectOpt(k)}
                          className={`rounded-lg border py-2 text-xs font-bold transition ${
                            correctOpts.includes(k)
                              ? 'border-indigo-500 bg-indigo-100 text-indigo-800'
                              : 'border-slate-300 bg-slate-50 text-slate-500'
                          }`}>
                          {k}
                        </button>
                      ))}
                    </div>
                  )}
                </div>
                <div>
                  <label className="font-semibold text-slate-700">Marks</label>
                  <input
                    type="number"
                    step="0.5"
                    min="0.5"
                    max={remainingMarks || 0}
                    required
                    value={mcqMarks}
                    onChange={(e) => setMcqMarks(e.target.value)}
                    className="w-full mt-1 px-3 py-2 border rounded-xl font-mono"
                  />
                  <p className="mt-1 text-[11px] text-slate-500">Remaining budget: {remainingMarks} marks</p>
                </div>
              </div>

              <button
                type="submit"
                disabled={isContentLocked || remainingMarks <= 0 || Number(mcqMarks || 0) > remainingMarks}
                className="w-full py-3 bg-blue-600 hover:bg-blue-700 text-white font-bold rounded-xl shadow transition disabled:cursor-not-allowed disabled:opacity-50"
              >
                {isContentLocked ? 'Published Exam Locked' : remainingMarks <= 0 ? 'No Marks Remaining' : 'Add MCQ to Shuffled Pool'}
              </button>
            </form>
          </div>

          {/* Existing MCQs List */}
          <div className="lg:col-span-7 space-y-4">
            {mcqs.length === 0 ? (
              <div className="bg-white rounded-3xl p-12 text-center border text-slate-500">No MCQs added yet.</div>
            ) : (
              mcqs.map((q, idx) => {
                const isMulti = q.question_type === 'multi';
                const correctSet = isMulti ? (q.correct_options || []) : [q.correct_option];
                return (
                <div key={q.id} className="bg-white rounded-2xl p-5 shadow-sm border border-slate-200 flex justify-between items-start gap-4">
                  <div className="space-y-2 flex-1">
                    <div className="flex items-center justify-between gap-2">
                      <span className="font-bold text-slate-800 text-sm">Q{idx + 1}: {q.question_text}</span>
                      <div className="flex flex-shrink-0 items-center gap-1.5">
                        {isMulti && (
                          <span className="px-2 py-0.5 bg-indigo-50 text-indigo-700 text-[11px] font-bold uppercase rounded">Multi</span>
                        )}
                        <span className="px-2.5 py-0.5 bg-blue-50 text-blue-800 text-xs font-bold rounded">{q.marks} Marks</span>
                      </div>
                    </div>
                    <div className="grid grid-cols-2 gap-2 text-xs text-slate-600">
                      <div className={correctSet.includes('A') ? 'font-bold text-emerald-700 bg-emerald-50 p-1.5 rounded' : 'p-1.5'}>A) {q.option_a}</div>
                      <div className={correctSet.includes('B') ? 'font-bold text-emerald-700 bg-emerald-50 p-1.5 rounded' : 'p-1.5'}>B) {q.option_b}</div>
                      <div className={correctSet.includes('C') ? 'font-bold text-emerald-700 bg-emerald-50 p-1.5 rounded' : 'p-1.5'}>C) {q.option_c}</div>
                      <div className={correctSet.includes('D') ? 'font-bold text-emerald-700 bg-emerald-50 p-1.5 rounded' : 'p-1.5'}>D) {q.option_d}</div>
                    </div>
                  </div>
                  {!isContentLocked && (
                    <button onClick={() => handleDeleteMCQ(q.id)} className="p-2 text-rose-500 hover:bg-rose-50 rounded-lg">
                      <Trash2 className="w-4 h-4" />
                    </button>
                  )}
                </div>
                );
              })
            )}
          </div>

        </div>
      )}

      {activeTab === 'coding' && (
        <div className="space-y-8">
          
          {/* Add Coding Problem Box */}
          <div className="bg-white rounded-3xl shadow-xl border border-slate-200 p-8">
            <h3 className="text-xl font-bold text-slate-800 mb-6 flex items-center gap-2 border-b pb-4">
              <PlusCircle className="w-6 h-6 text-purple-600" /> Add Coding Problem
            </h3>


            {false && codingBankItems.length > 0 && !examData?.content_locked && (
              <div className="workflow-bank-picker mb-6">
                <label htmlFor="coding-bank-picker">Insert coding problem from question bank</label>
                <select id="coding-bank-picker" value={codingBankPick} onChange={(e) => loadCodingFromBank(e.target.value)}>
                  <option value="">Choose a saved coding problem…</option>
                  {codingBankItems.map((item) => <option key={item.id} value={item.id}>{item.title || 'Untitled coding problem'}</option>)}
                </select>
              </div>
            )}

            <form onSubmit={handleAddCoding} className="space-y-6">
              <div className="grid grid-cols-1 md:grid-cols-4 gap-6">
                <div className="md:col-span-3">
                  <label className="font-semibold text-slate-700 text-sm">Problem Title</label>
                  <input
                    type="text"
                    required
                    value={cTitle}
                    onChange={(e) => setCTitle(e.target.value)}
                    placeholder="e.g. Merge Intervals / Two Sum"
                    className="w-full mt-1 px-4 py-2.5 border rounded-xl text-sm"
                  />
                </div>
                <div>
                  <label className="font-semibold text-slate-700 text-sm">Marks</label>
                  <input
                    type="number"
                    min="1"
                    max={remainingMarks || 0}
                    required
                    value={cMarks}
                    onChange={(e) => setCMarks(e.target.value)}
                    className="w-full mt-1 px-4 py-2.5 border rounded-xl text-sm font-mono font-bold"
                  />
                  <p className="mt-1 text-[11px] text-slate-500">Remaining budget: {remainingMarks} marks</p>
                </div>
              </div>

              <div>
                <label className="font-semibold text-slate-700 text-sm">Compiler Language</label>
                <div className="mt-1 grid grid-cols-4 gap-2">
                  {codingLanguages.map((val) => (
                    ([val, LANGUAGE_LABELS[val]])
                  )).map(([val, label]) => (
                    <button key={val} type="button" onClick={() => setCLanguage(val)}
                      className={`rounded-xl border py-2.5 text-xs font-bold transition ${
                        cLanguage === val ? 'border-purple-500 bg-purple-50 text-purple-700' : 'border-slate-300 text-slate-500 hover:border-purple-300'
                      }`}>
                      {label}
                    </button>
                  ))}
                </div>
                <p className="mt-1.5 flex items-center gap-1 text-[12px] text-slate-500">
                  This is permanent — every reference solution and the student's exam editor will be locked to this one language.
                </p>
              </div>

              <div>
                <label className="font-semibold text-slate-700 text-sm">Problem Statement</label>
                <textarea
                  rows="4"
                  required
                  value={cStatement}
                  onChange={(e) => setCStatement(e.target.value)}
                  placeholder="Detailed description of the programming problem..."
                  className="w-full mt-1 px-4 py-2.5 border rounded-xl text-sm"
                />
              </div>

              <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                <div>
                  <label className="font-semibold text-slate-700 text-sm">Sample Input</label>
                  <textarea
                    rows="2"
                    value={cSampleIn}
                    onChange={(e) => setCSampleIn(e.target.value)}
                    className="w-full mt-1 px-3 py-2 border rounded-xl font-mono text-xs bg-slate-50"
                  />
                </div>
                <div>
                  <label className="font-semibold text-slate-700 text-sm">Sample Output</label>
                  <textarea
                    rows="2"
                    value={cSampleOut}
                    onChange={(e) => setCSampleOut(e.target.value)}
                    className="w-full mt-1 px-3 py-2 border rounded-xl font-mono text-xs bg-slate-50"
                  />
                </div>
              </div>

              {/* 2-3 Reference Solutions Section */}
              <div className="hidden bg-purple-50/70 border border-purple-200 rounded-2xl p-6 space-y-6">
                <div className="flex items-center justify-between">
                  <div>
                    <h4 className="font-bold text-purple-950 text-base">Faculty Reference Answers (2-3 Solutions)</h4>
                    <p className="text-xs text-purple-800">Shown to students after evaluation if their logic is incorrect.</p>
                  </div>
                  {refSolutions.length < 3 && (
                    <button
                      type="button"
                      onClick={handleAddRefSlot}
                      className="px-4 py-2 bg-purple-600 hover:bg-purple-700 text-white text-xs font-bold rounded-xl transition"
                    >
                      + Add Solution #{refSolutions.length + 1}
                    </button>
                  )}
                </div>

                <div className="grid grid-cols-1 gap-6">
                  {refSolutions.map((sol, idx) => (
                    <div key={idx} className="bg-white rounded-xl p-5 border border-purple-200 space-y-3 shadow-sm">
                      <div className="flex items-center justify-between">
                        <span className="font-bold text-purple-900 text-sm">Solution #{idx + 1}</span>
                        {!isContentLocked && (
                          <button
                            type="button"
                            onClick={() => handleRemoveRefSlot(idx)}
                            className="flex items-center gap-1 rounded-lg px-2 py-1 text-xs font-bold text-rose-500 hover:bg-rose-50"
                          >
                            <Trash2 className="h-3.5 w-3.5" /> Remove
                          </button>
                        )}
                      </div>
                      <input
                        type="text"
                        placeholder="Solution Title (e.g. Optimal One-Pass Hash Map)"
                        value={sol.title}
                        onChange={(e) => handleRefChange(idx, 'title', e.target.value)}
                        className="w-full px-3 py-2 border rounded-lg text-xs font-semibold"
                      />
                      <textarea
                        rows="2"
                        placeholder="Explain the algorithm logic (time/space complexity)..."
                        value={sol.logic_explanation}
                        onChange={(e) => handleRefChange(idx, 'logic_explanation', e.target.value)}
                        className="w-full px-3 py-2 border rounded-lg text-xs"
                      />
                      <textarea
                        rows="5"
                        placeholder={`Write the complete ${LANGUAGE_LABELS[cLanguage]} reference solution...`}
                        value={sol.code}
                        onChange={(e) => handleRefChange(idx, 'code', e.target.value)}
                        className="w-full px-3 py-2 border rounded-lg font-mono text-xs bg-slate-900 text-emerald-300"
                      />
                    </div>
                  ))}
                  {refSolutions.length === 0 && (
                    <button
                      type="button"
                      onClick={handleAddRefSlot}
                      className="w-full rounded-xl border-2 border-dashed border-purple-300 py-4 text-xs font-bold text-purple-600 hover:bg-purple-50"
                    >
                      + Add Reference Solution
                    </button>
                  )}
                </div>
              </div>

              <button
                type="submit"
                disabled={isContentLocked || remainingMarks <= 0 || Number(cMarks || 0) > remainingMarks}
                className="w-full py-3.5 bg-purple-600 hover:bg-purple-700 text-white font-bold rounded-xl shadow-lg transition disabled:cursor-not-allowed disabled:opacity-50"
              >
                {isContentLocked ? 'Published Exam Locked' : remainingMarks <= 0 ? 'No Marks Remaining' : 'Upload Problem Statement & Reference Answers'}
              </button>
            </form>
          </div>

          {/* Existing Coding Problems */}
          <div className="space-y-6">
            <h3 className="text-xl font-bold text-slate-800">Uploaded Coding Problems ({codingProblems.length})</h3>
            {codingProblems.map((prob, idx) => (
              <div key={prob.id} className="bg-white rounded-3xl p-6 shadow-md border border-slate-200 space-y-4">
                <div className="flex items-start justify-between">
                  <div>
                    <span className="text-xs font-bold uppercase tracking-wider text-purple-600">Problem #{idx + 1}</span>
                    <h4 className="text-xl font-bold text-slate-900 mt-0.5">{prob.title}</h4>
                  </div>
                  <div className="flex items-center gap-3">
                    <span className="flex items-center gap-1 px-3 py-1 bg-slate-100 text-slate-700 text-xs font-bold rounded-full">
                      {LANGUAGE_LABELS[prob.language] || prob.language}
                    </span>
                    <span className="px-3 py-1 bg-purple-100 text-purple-800 text-xs font-bold rounded-full">{prob.marks} Marks</span>
                    {!isContentLocked && (
                      <button onClick={() => handleDeleteCoding(prob.id)} className="p-2 text-rose-500 hover:bg-rose-50 rounded-lg" title="Delete this coding question">
                        <Trash2 className="w-5 h-5" />
                      </button>
                    )}
                  </div>
                </div>

                <p className="text-slate-600 text-sm whitespace-pre-line bg-slate-50 p-4 rounded-xl border">{prob.problem_statement}</p>

                <div className="space-y-3 pt-2">
                  <h5 className="font-bold text-slate-800 text-xs uppercase tracking-wider">Reference Solutions ({prob.reference_solutions?.length || 0})</h5>
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                    {prob.reference_solutions?.map((sol) => (
                      <div key={sol.id} className="bg-purple-50/50 border border-purple-200 rounded-xl p-4 space-y-2">
                        <div className="flex items-center justify-between">
                          <div className="font-bold text-purple-900 text-xs">{sol.title}</div>
                          {!isContentLocked && (
                            <button
                              onClick={() => handleDeleteRefSolution(prob.id, sol.id)}
                              className="p-1 text-rose-500 hover:bg-rose-100 rounded"
                              title="Delete this reference solution"
                            >
                              <Trash2 className="w-3.5 h-3.5" />
                            </button>
                          )}
                        </div>
                        <pre className="p-2 bg-slate-900 text-emerald-300 font-mono text-xs rounded-lg overflow-x-auto max-h-36">{sol.code}</pre>
                      </div>
                    ))}
                    {(!prob.reference_solutions || prob.reference_solutions.length === 0) && (
                      <p className="text-xs text-slate-400 italic">No reference solutions uploaded for this problem.</p>
                    )}
                  </div>
                </div>
              </div>
            ))}
          </div>

        </div>
      )}

      {activeTab === 'roster' && (
        <div className="space-y-6">
          {resultStatus && (
            <div className="rounded-3xl border border-slate-200 bg-white p-6 shadow-xl">
              <div className="flex flex-col gap-4 md:flex-row md:items-center md:justify-between">
                <div>
                  <h3 className="text-lg font-black text-slate-900">Publish Student Results</h3>
                  <p className="mt-1 text-sm text-slate-600">
                    Results stay hidden even after exam time ends. Verify every attempted student session, then publish results for students.
                  </p>
                  <div className="mt-3 flex flex-wrap gap-2 text-xs font-bold">
                    <span className="rounded-full bg-slate-100 px-3 py-1 text-slate-700">Attempts: {resultStatus.total_attempted}</span>
                    <span className="rounded-full bg-emerald-100 px-3 py-1 text-emerald-700">Verified: {resultStatus.verified}</span>
                    <span className="rounded-full bg-amber-100 px-3 py-1 text-amber-700">Unverified: {resultStatus.unverified}</span>
                    {resultStatus.in_progress > 0 && <span className="rounded-full bg-blue-100 px-3 py-1 text-blue-700">In progress: {resultStatus.in_progress}</span>}
                  </div>
                </div>
                <div className="flex flex-col gap-2 md:items-end">
                  {resultStatus.results_published ? (
                    <span className="rounded-xl border border-emerald-200 bg-emerald-100 px-4 py-2 text-sm font-black text-emerald-800">Results Published</span>
                  ) : (
                    <button
                      onClick={handlePublishResults}
                      disabled={resultPublishing || !resultStatus.can_publish_results}
                      className={`rounded-xl px-6 py-3 text-sm font-black shadow transition ${resultStatus.can_publish_results && !resultPublishing ? 'bg-emerald-600 text-white hover:bg-emerald-700' : 'cursor-not-allowed bg-slate-200 text-slate-500'}`}
                    >
                      {resultPublishing ? 'Publishing…' : 'Publish Results'}
                    </button>
                  )}
                  {!resultStatus.can_publish_results && !resultStatus.results_published && (
                    <span className="max-w-sm text-right text-xs font-semibold text-amber-700">
                      Publish unlocks after exam end and all attempted sessions are verified.
                    </span>
                  )}
                </div>
              </div>
            </div>
          )}
          {rosterCounts && (
            <div className="grid grid-cols-2 gap-4 md:grid-cols-4">
              {[
                ['Not Started', rosterCounts.not_started, 'slate'],
                ['In Progress', rosterCounts.in_progress, 'blue'],
                ['Submitted', rosterCounts.submitted, 'emerald'],
                ['Unfair Means', rosterCounts.ufm, 'rose'],
              ].map(([label, count, tone]) => (
                <div key={label} className={`rounded-2xl border p-5 shadow-sm ${
                  tone === 'rose' ? 'border-rose-200 bg-rose-50' : 'border-slate-200 bg-white'
                }`}>
                  <div className="text-xs font-bold uppercase tracking-wide text-slate-500">{label}</div>
                  <div className={`mt-1 text-2xl font-black ${
                    tone === 'blue' ? 'text-blue-600' : tone === 'emerald' ? 'text-emerald-600' : tone === 'rose' ? 'text-rose-600' : 'text-slate-700'
                  }`}>{count}</div>
                </div>
              ))}
            </div>
          )}

          <div className="overflow-hidden rounded-3xl border border-slate-200 bg-white shadow-sm">
            {rosterLoading ? (
              <div className="flex items-center justify-center p-16"><Loader2 className="h-8 w-8 animate-spin text-emerald-600" /></div>
            ) : roster.length === 0 ? (
              <div className="p-12 text-center text-sm text-slate-500">No students have been granted OTP access yet.</div>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full text-left text-sm">
                  <thead className="bg-slate-50 text-xs font-bold uppercase tracking-wide text-slate-500">
                    <tr>
                      <th className="px-5 py-3">Student</th>
                      <th className="px-5 py-3">Status</th>
                      <th className="px-5 py-3">Joined</th>
                      <th className="px-5 py-3">Submitted</th>
                      <th className="px-5 py-3 text-center">Violations</th>
                      <th className="px-5 py-3 text-right">Score</th>
                      <th className="px-5 py-3 text-center">Verified</th>
                      <th className="px-5 py-3 text-center">Analysis</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-100">
                    {roster.map((r) => (
                      <tr key={r.student_id} className={r.status === 'ufm' ? 'bg-rose-50/50' : ''}>
                        <td className="px-5 py-3">
                          <div className="font-semibold text-slate-800">{r.name}</div>
                          <div className="text-xs text-slate-400">{r.enrollment_no}</div>
                        </td>
                        <td className="px-5 py-3">
                          <span className={`inline-flex items-center gap-1 rounded-full px-2.5 py-1 text-xs font-bold ${
                            r.status === 'not_started' ? 'bg-slate-100 text-slate-600'
                              : r.status === 'in_progress' ? 'bg-blue-100 text-blue-700'
                              : r.status === 'ufm' ? 'bg-rose-100 text-rose-700'
                              : 'bg-emerald-100 text-emerald-700'
                          }`}>
                            {r.status === 'ufm' && <Ban className="h-3 w-3" />}
                            {r.status === 'not_started' ? 'Not Started' : r.status === 'in_progress' ? 'In Progress' : r.status === 'ufm' ? 'Unfair Means' : 'Submitted'}
                          </span>
                          {r.is_blocked && (
                            <span className="mt-1.5 flex items-center gap-1 rounded-lg bg-slate-100 px-2 py-1 text-[12px] font-bold text-slate-500">
                              <Lock className="h-3 w-3" /> Locked — admin can restore access
                            </span>
                          )}
                        </td>
                        <td className="px-5 py-3 text-xs text-slate-500">
                          {r.joined_at ? new Date(r.joined_at).toLocaleString() : '—'}
                        </td>
                        <td className="px-5 py-3 text-xs text-slate-500">
                          {r.submitted_at ? new Date(r.submitted_at).toLocaleString() : '—'}
                        </td>
                        <td className="px-5 py-3 text-center font-mono text-xs font-bold text-slate-600">{r.violation_count}</td>
                        <td className="px-5 py-3 text-right font-mono text-sm font-bold text-slate-800">
                          {r.total_score !== null ? `${r.total_score} (${r.percentage}%)` : '—'}
                        </td>
                        <td className="px-5 py-3 text-center">
                          {r.status === 'not_started' ? '—' : r.faculty_verified ? (
                            <span className="rounded-full bg-emerald-100 px-2.5 py-1 text-xs font-bold text-emerald-700">Verified</span>
                          ) : r.status === 'in_progress' ? (
                            <span className="rounded-full bg-blue-100 px-2.5 py-1 text-xs font-bold text-blue-700">In Progress</span>
                          ) : rosterCanManage ? (
                            <div className="flex flex-col items-center gap-1.5">
                              <span className="rounded-full bg-amber-100 px-2.5 py-1 text-xs font-bold text-amber-700">Needs Review</span>
                              <button
                                type="button"
                                onClick={() => handleVerifyFromRoster(r.student_id)}
                                disabled={verifyingStudentId === r.student_id}
                                className="inline-flex items-center gap-1 rounded-lg bg-emerald-600 px-2.5 py-1.5 text-[12px] font-black text-white hover:bg-emerald-700 disabled:opacity-50"
                              >
                                <ShieldCheck className="h-3.5 w-3.5" /> {verifyingStudentId === r.student_id ? 'Verifying…' : 'Mark Verified'}
                              </button>
                            </div>
                          ) : (
                            <span className="rounded-full bg-amber-100 px-2.5 py-1 text-xs font-bold text-amber-700">Needs Review</span>
                          )}
                        </td>
                        <td className="px-5 py-3 text-center">
                          {r.status !== 'not_started' && (
                            <Link
                              to={`/faculty/exam/${examId}/student/${r.student_id}/analysis`}
                              className="inline-flex items-center gap-1 rounded-lg bg-indigo-50 px-2.5 py-1.5 text-xs font-bold text-indigo-700 hover:bg-indigo-100"
                            >
                              <BarChart3 className="h-3.5 w-3.5" /> Analysis
                            </Link>
                          )}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        </div>
      )}

      {activeTab === 'otps' && (
        <div className="bg-white rounded-3xl shadow-xl border border-slate-200 p-8 space-y-6">
          <div className="flex flex-col md:flex-row items-center justify-between gap-4 border-b pb-6">
            <div>
              <h3 className="text-xl font-bold text-slate-800">Temporary Student Exam OTPs</h3>
              <p className="text-xs text-slate-500 mt-1">Generated specifically for the exam window and cleared after exam submission</p>
            </div>
            <div className="flex items-center gap-3">
              <button
                onClick={handleGenerateOTPs}
                disabled={otpBusy}
                className="px-6 py-2.5 bg-blue-600 hover:bg-blue-700 text-white font-bold rounded-xl text-sm transition shadow disabled:opacity-50 disabled:cursor-not-allowed"
              >
                {otpBusy ? 'Working…' : 'Generate OTPs for Registered Students'}
              </button>
              <button
                onClick={handleClearOTPs}
                disabled={otpBusy}
                className="px-6 py-2.5 bg-rose-600 hover:bg-rose-700 text-white font-bold rounded-xl text-sm transition shadow disabled:opacity-50 disabled:cursor-not-allowed"
              >
                Clear All Active OTPs
              </button>
            </div>
          </div>

          <div className="overflow-x-auto">
            <table className="w-full text-left border-collapse text-sm">
              <thead>
                <tr className="bg-slate-100 text-slate-600 text-xs uppercase tracking-wider font-bold">
                  <th className="py-3 px-4">Enrollment No.</th>
                  <th className="py-3 px-4">Student Name</th>
                  <th className="py-3 px-4 text-center">Temporary OTP</th>
                  <th className="py-3 px-4 text-center">Status</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {otps.map((otp) => (
                  <tr key={otp.id} className="hover:bg-slate-50">
                    <td className="py-3 px-4 font-mono font-bold text-slate-800">{otp.student_enrollment}</td>
                    <td className="py-3 px-4 font-medium text-slate-900">{otp.student_name}</td>
                    <td className="py-3 px-4 text-center">
                      {otp.is_active ? (
                        <span className="font-mono font-black text-blue-600 text-base bg-blue-50 px-3 py-1 rounded-md border border-blue-200">
                          {otp.temp_otp}
                        </span>
                      ) : (
                        <span className="font-mono text-slate-400 text-xs bg-slate-100 px-2 py-1 rounded">
                          CLEARED
                        </span>
                      )}
                    </td>
                    <td className="py-3 px-4 text-center">
                      <span className={`px-2.5 py-0.5 rounded-full text-xs font-bold ${
                        otp.is_active ? 'bg-emerald-100 text-emerald-800' : 'bg-slate-200 text-slate-600'
                      }`}>
                        {otp.is_active ? 'Active Window' : 'Cleared / Submitted'}
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* ---------------- Code Similarity ---------------- */}
      {false && activeTab === 'similarity' && (
        <div className="rounded-3xl border border-slate-200 bg-white p-8 shadow-xl">
          <div className="mb-6 flex flex-wrap items-center justify-between gap-4 border-b border-slate-200 pb-5">
            <div>
              <h3 className="flex items-center gap-2 text-xl font-bold text-slate-800">
                <GitCompareArrows className="h-5 w-5 text-rose-600" /> Code Similarity Check
              </h3>
              <p className="mt-1 text-sm text-slate-600">
                Flags pairs of submissions with unusually similar code, as a starting point for review. Full anti-cheat proctoring reports (fullscreen exits, tab switches, blocked shortcuts) are available to admins in the Admin panel.
              </p>
            </div>
          </div>

          {codingProblems.length === 0 ? (
            <p className="tool-empty">Add coding problems to this assessment to run a similarity check.</p>
          ) : (
            <div className="mb-5 flex flex-wrap items-center justify-between gap-4">
              <select
                value={similarityProblemId}
                onChange={(e) => checkSimilarity(e.target.value)}
                className="rounded-xl border border-slate-300 px-4 py-2.5 text-sm font-semibold text-slate-700"
              >
                <option value="">Choose a coding problem…</option>
                {codingProblems.map((prob) => <option key={prob.id} value={prob.id}>{prob.title}</option>)}
              </select>
            </div>
          )}

              {similarityLoading && (
                <div className="py-10 text-center text-slate-500">
                  <Loader2 className="mx-auto mb-3 h-8 w-8 animate-spin" />
                  <p className="text-sm font-semibold">Comparing submissions…</p>
                </div>
              )}

              {!similarityLoading && similarityData && (
                similarityData.flagged_pairs.length === 0 ? (
                  <div className="rounded-2xl border border-emerald-200 bg-emerald-50/50 py-10 text-center text-emerald-800">
                    <ShieldCheck className="mx-auto mb-3 h-10 w-10 text-emerald-400" />
                    <p className="font-semibold">No unusually similar pairs found among {similarityData.compared_submissions} compared submission{similarityData.compared_submissions === 1 ? '' : 's'}.</p>
                  </div>
                ) : (
                  <div className="space-y-3">
                    <p className="text-xs font-bold uppercase tracking-wide text-slate-500">
                      {similarityData.flagged_pairs.length} pair{similarityData.flagged_pairs.length === 1 ? '' : 's'} flagged out of {similarityData.compared_submissions} submissions compared
                    </p>
                    {similarityData.flagged_pairs.map((pair) => (
                      <div key={`${pair.submission_a_id}-${pair.submission_b_id}`} className="flex flex-wrap items-center justify-between gap-3 rounded-2xl border border-rose-200 bg-rose-50/50 p-5">
                        <div className="flex flex-wrap items-center gap-3 text-sm">
                          <div>
                            <div className="font-bold text-slate-900">{pair.student_a.name}</div>
                            <div className="font-mono text-xs text-slate-500">{pair.student_a.enrollment_no}</div>
                          </div>
                          <GitCompareArrows className="h-4 w-4 text-slate-400" />
                          <div>
                            <div className="font-bold text-slate-900">{pair.student_b.name}</div>
                            <div className="font-mono text-xs text-slate-500">{pair.student_b.enrollment_no}</div>
                          </div>
                        </div>
                        <span className="flex items-center gap-1.5 rounded-lg bg-rose-600 px-3 py-1.5 text-xs font-bold text-white">
                          <AlertTriangle className="h-3.5 w-3.5" /> {Math.round(pair.similarity * 100)}% similar
                        </span>
                      </div>
                    ))}
                  </div>
                )
              )}
        </div>
      )}


      {/* Publish exam after complete mark allocation */}
      <div className="rounded-3xl border border-slate-200 bg-white p-6 shadow-xl">
        <div className="flex flex-col gap-4 md:flex-row md:items-center md:justify-between">
          <div>
            <h3 className="text-lg font-black text-slate-900">Final Step: Publish Exam</h3>
            <p className="mt-1 text-sm text-slate-600">
              Students cannot start this exam until faculty publishes it. Publish is enabled only when allocated marks are exactly {totalMarks} / {totalMarks}.
            </p>
            <p className="mt-2 text-xs font-semibold text-slate-500">
              Current allocation: <span className="font-mono text-slate-900">{allocatedMarks}</span> / {totalMarks} · Remaining: <span className={remainingMarks > 0 ? 'text-rose-700' : 'text-emerald-700'}>{remainingMarks}</span>
            </p>
          </div>
          <div className="flex flex-col gap-2 md:items-end">
            {!isPublished ? (
              <button
                type="button"
                onClick={handlePublishExam}
                disabled={!canPublish || publishing}
                className={`inline-flex items-center justify-center gap-2 rounded-xl px-6 py-3 text-sm font-black shadow transition ${canPublish && !publishing ? 'bg-emerald-600 text-white hover:bg-emerald-700' : 'cursor-not-allowed bg-slate-200 text-slate-500'}`}
              >
                {publishing ? <Loader2 className="h-4 w-4 animate-spin" /> : <ShieldCheck className="h-4 w-4" />}
                Publish Exam
              </button>
            ) : (
              <>
                <span className="rounded-xl bg-emerald-100 px-4 py-2 text-sm font-black text-emerald-800 border border-emerald-200">Exam Published</span>
                <button
                  type="button"
                  onClick={handleUnpublishExam}
                  disabled={publishing}
                  className="rounded-xl bg-slate-100 px-4 py-2 text-xs font-bold text-slate-700 transition hover:bg-slate-200 disabled:opacity-60"
                >
                  Unpublish / Disable Start
                </button>
              </>
            )}
            {!canPublish && (
              <span className="max-w-sm text-right text-xs font-semibold text-amber-700">
                Allocate exactly all marks first. Remaining: {remainingMarks}.
              </span>
            )}
          </div>
        </div>
      </div>

    </div>
  );
}

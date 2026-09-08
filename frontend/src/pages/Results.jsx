import React, { useEffect, useMemo, useState } from 'react';
import { Link } from 'react-router-dom';
import api from '../api/axios';
import { useAuth } from '../context/AuthContext';
import { useToast } from '../components/ToastProvider';
import {
  AlertTriangle,
  ArrowUpRight,
  Ban,
  BarChart3,
  CheckCircle2,
  ChevronLeft,
  ChevronRight,
  Clock,
  Download,
  FileSpreadsheet,
  Filter,
  Loader2,
  Search,
  SlidersHorizontal,
  UsersRound,
  XCircle,
} from 'lucide-react';
import './results-page.css';

const PHASES = ['T1', 'T2', 'T3', 'T4'];
const PAGE_SIZES = [10, 20, 50];

function ResultStatus({ row }) {
  if (row.is_ufm) {
    return <span className="results-status results-status--ufm"><Ban size={14} /> UFM</span>;
  }

  if (!row.results_released) {
    const availableAt = row.exam_end_time
      ? `Available after ${new Date(row.exam_end_time).toLocaleString()}`
      : 'Awaiting result release';
    return <span className="results-status results-status--pending" title={availableAt}><Clock size={14} /> Pending</span>;
  }

  return row.is_passed
    ? <span className="results-status results-status--pass"><CheckCircle2 size={14} /> Passed</span>
    : <span className="results-status results-status--fail"><XCircle size={14} /> Not passed</span>;
}

function Score({ value, row, suffix = '' }) {
  if (!row.results_released) return <span className="results-score results-score--hidden">—</span>;
  return <span className="results-score">{value ?? 0}{suffix}</span>;
}

export default function Results() {
  const { user } = useAuth();
  const { toast } = useToast();
  const isFaculty = user?.user_type === 'faculty';

  const [rows, setRows] = useState([]);
  const [subjects, setSubjects] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [exporting, setExporting] = useState(false);

  const [minScore, setMinScore] = useState('');
  const [maxScore, setMaxScore] = useState('');
  const [phase, setPhase] = useState('');
  const [subject, setSubject] = useState('');
  const [search, setSearch] = useState('');

  const [sortBy, setSortBy] = useState('source');
  const [pageSize, setPageSize] = useState(PAGE_SIZES[0]);
  const [currentPage, setCurrentPage] = useState(1);

  const buildParams = (extra = {}, filters = {}) => {
    const selectedMinScore = filters.minScore ?? minScore;
    const selectedMaxScore = filters.maxScore ?? maxScore;
    const selectedPhase = filters.phase ?? phase;
    const selectedSubject = filters.subject ?? subject;
    const selectedSearch = filters.search ?? search;
    const params = {};

    if (selectedMinScore !== '') params.min_score = selectedMinScore;
    if (selectedMaxScore !== '') params.max_score = selectedMaxScore;
    if (selectedPhase) params.phase = selectedPhase;
    if (selectedSubject) params.subject = selectedSubject;
    if (selectedSearch.trim()) params.search = selectedSearch.trim();

    return { ...params, ...extra };
  };

  const load = async (filters) => {
    setLoading(true);
    setError('');
    try {
      const response = await api.get('results/', { params: buildParams({}, filters) });
      setRows(response.data.results || []);
      setSubjects(response.data.available_subjects || []);
      setCurrentPage(1);
    } catch (requestError) {
      setError(requestError.response?.data?.error || 'Could not load results.');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { load(); /* eslint-disable-next-line react-hooks/exhaustive-deps */ }, []);

  const handleFilter = (event) => {
    event.preventDefault();
    load();
  };

  const clearFilters = () => {
    const clearedFilters = {
      minScore: '', maxScore: '', phase: '', subject: '', search: '',
    };
    setMinScore('');
    setMaxScore('');
    setPhase('');
    setSubject('');
    setSearch('');
    load(clearedFilters);
  };

  const handleExportCsv = async () => {
    setExporting(true);
    try {
      const response = await api.get('results/', {
        params: buildParams({ export: 'csv' }),
        responseType: 'blob',
      });
      const url = URL.createObjectURL(new Blob([response.data], { type: 'text/csv' }));
      const anchor = document.createElement('a');
      anchor.href = url;
      anchor.download = isFaculty ? 'results.csv' : 'my_result.csv';
      document.body.appendChild(anchor);
      anchor.click();
      anchor.remove();
      URL.revokeObjectURL(url);
    } catch {
      toast({ type: 'error', title: 'Export failed', message: 'Could not export CSV. Please try again.' });
    } finally {
      setExporting(false);
    }
  };

  const summary = useMemo(() => {
    if (!rows.length) return null;

    const released = rows.filter((row) => row.results_released);
    const passed = released.filter((row) => row.is_passed).length;
    const average = released.length
      ? released.reduce((total, row) => total + (Number(row.percentage) || 0), 0) / released.length
      : 0;

    return {
      total: rows.length,
      passed,
      failed: released.length - passed,
      pending: rows.length - released.length,
      average: Math.round(average * 10) / 10,
    };
  }, [rows]);

  const orderedRows = useMemo(() => {
    if (sortBy === 'source') return rows;

    return [...rows].sort((first, second) => {
      if (sortBy === 'score') return (Number(second.total_score) || 0) - (Number(first.total_score) || 0);
      if (sortBy === 'percentage') return (Number(second.percentage) || 0) - (Number(first.percentage) || 0);
      if (sortBy === 'exam') return (first.exam_title || '').localeCompare(second.exam_title || '');
      if (sortBy === 'student') return (first.student_name || '').localeCompare(second.student_name || '');
      return 0;
    });
  }, [rows, sortBy]);

  const pageCount = Math.max(1, Math.ceil(orderedRows.length / pageSize));
  const safePage = Math.min(currentPage, pageCount);
  const startIndex = (safePage - 1) * pageSize;
  const visibleRows = orderedRows.slice(startIndex, startIndex + pageSize);
  const rangeStart = orderedRows.length ? startIndex + 1 : 0;
  const rangeEnd = Math.min(startIndex + pageSize, orderedRows.length);

  const changeSort = (event) => {
    setSortBy(event.target.value);
    setCurrentPage(1);
  };

  const changePageSize = (event) => {
    setPageSize(Number(event.target.value));
    setCurrentPage(1);
  };

  const resultPath = (row) => (isFaculty
    ? `/faculty/exam/${row.exam_id}/student/${row.student_id}/analysis`
    : `/exam/${row.exam_id}/result`);

  return (
    <div className="results-page">
      <header className="results-hero">
        <div className="results-hero__accent" aria-hidden="true" />
        <div className="results-hero__copy">
          <div className="results-hero__eyebrow"><span /> {isFaculty ? 'Faculty reporting' : 'Academic record'}</div>
          <h1>{isFaculty ? 'Results, made readable.' : 'Your assessment record.'}</h1>
          <p>
            {isFaculty
              ? 'Review outcomes across every assessment, then open a student attempt for its detailed analysis.'
              : 'Keep every submitted assessment in one place and revisit feedback whenever results are released.'}
          </p>
        </div>
        <div className="results-hero__actions">
          <div className="results-hero__count" aria-live="polite">
            <UsersRound size={18} />
            <span><strong>{loading ? '…' : rows.length}</strong> {isFaculty ? 'records' : 'assessments'}</span>
          </div>
          <button
            type="button"
            onClick={handleExportCsv}
            disabled={exporting || rows.length === 0}
            className="results-export"
          >
            {exporting ? <Loader2 size={17} className="results-spin" /> : <Download size={17} />}
            <span>{exporting ? 'Preparing file' : 'Download CSV'}</span>
          </button>
        </div>
      </header>

      {summary && (
        <section className="results-summary" aria-label="Results overview">
          <div className="results-summary__intro">
            <p>Selection overview</p>
            <span>Based on the current result filters</span>
          </div>
          <div className="results-summary__metrics">
            <div><span>Shown</span><strong>{summary.total}</strong></div>
            <div className="is-good"><span>Passed</span><strong>{summary.passed}</strong></div>
            <div className="is-bad"><span>Not passed</span><strong>{summary.failed}</strong></div>
            <div className="is-pending"><span>Pending</span><strong>{summary.pending}</strong></div>
            <div className="is-average"><span>Average</span><strong>{summary.average}%</strong></div>
          </div>
        </section>
      )}

      <form className="results-filter-panel" onSubmit={handleFilter}>
        <div className="results-filter-panel__heading">
          <span className="results-filter-panel__icon"><SlidersHorizontal size={18} /></span>
          <div>
            <h2>Find a result</h2>
            <p>Refine the record without leaving the page.</p>
          </div>
        </div>
        <div className="results-filter-panel__fields">
          <label className="results-field">
            <span>Minimum score</span>
            <input type="number" value={minScore} onChange={(event) => setMinScore(event.target.value)} placeholder="Any score" inputMode="decimal" />
          </label>
          <label className="results-field">
            <span>Maximum score</span>
            <input type="number" value={maxScore} onChange={(event) => setMaxScore(event.target.value)} placeholder="Any score" inputMode="decimal" />
          </label>
          <label className="results-field">
            <span>Phase</span>
            <select value={phase} onChange={(event) => setPhase(event.target.value)}>
              <option value="">All phases</option>
              {PHASES.map((item) => <option key={item} value={item}>{item}</option>)}
            </select>
          </label>
          <label className="results-field">
            <span>Subject</span>
            <select value={subject} onChange={(event) => setSubject(event.target.value)}>
              <option value="">All subjects</option>
              {subjects.map((item) => <option key={item} value={item}>{item}</option>)}
            </select>
          </label>
          <label className="results-field results-field--search">
            <span>Search</span>
            <div className="results-search-box">
              <Search size={16} aria-hidden="true" />
              <input
                type="search"
                value={search}
                onChange={(event) => setSearch(event.target.value)}
                placeholder={isFaculty ? 'Student name or enrollment' : 'Assessment title'}
              />
            </div>
          </label>
        </div>
        <div className="results-filter-panel__actions">
          <button type="button" className="results-clear" onClick={clearFilters}>Clear filters</button>
          <button type="submit" className="results-apply"><Filter size={16} /> Apply filters</button>
        </div>
      </form>

      <section className="results-data-panel" aria-labelledby="results-grid-heading">
        <div className="results-data-panel__toolbar">
          <div>
            <p className="results-data-panel__eyebrow">Assessment ledger</p>
            <h2 id="results-grid-heading">{isFaculty ? 'Student outcomes' : 'Exam outcomes'}</h2>
          </div>
          <div className="results-data-panel__controls">
            <label>
              <span>Order</span>
              <select value={sortBy} onChange={changeSort}>
                <option value="source">Original order</option>
                <option value="score">Highest total score</option>
                <option value="percentage">Highest percentage</option>
                <option value="exam">Assessment A–Z</option>
                {isFaculty && <option value="student">Student A–Z</option>}
              </select>
            </label>
            <label>
              <span>Rows</span>
              <select value={pageSize} onChange={changePageSize}>
                {PAGE_SIZES.map((size) => <option key={size} value={size}>{size} per page</option>)}
              </select>
            </label>
          </div>
        </div>

        {loading ? (
          <div className="results-state results-state--loading" role="status" aria-live="polite">
            <Loader2 size={28} className="results-spin" />
            <strong>Gathering your records</strong>
            <span>This will only take a moment.</span>
          </div>
        ) : error ? (
          <div className="results-state results-state--error" role="alert">
            <AlertTriangle size={28} />
            <strong>We could not load these results</strong>
            <span>{error}</span>
            <button type="button" onClick={() => load()}>Try again</button>
          </div>
        ) : !visibleRows.length ? (
          <div className="results-state">
            <FileSpreadsheet size={30} />
            <strong>No results found</strong>
            <span>Try adjusting the filters to see a different set of records.</span>
            {(minScore || maxScore || phase || subject || search) && <button type="button" onClick={clearFilters}>Clear all filters</button>}
          </div>
        ) : (
          <>
            <div className="results-table-shell">
              <table className="results-table">
                <caption className="sr-only">{isFaculty ? 'Student assessment outcomes' : 'Your assessment outcomes'}</caption>
                <thead>
                  <tr>
                    {isFaculty && <th scope="col">Student</th>}
                    <th scope="col">Assessment</th>
                    <th scope="col">Subject</th>
                    <th scope="col">Phase</th>
                    <th scope="col" className="is-number">MCQ</th>
                    <th scope="col" className="is-number">Coding</th>
                    <th scope="col" className="is-number">Total</th>
                    <th scope="col" className="is-number">Percent</th>
                    <th scope="col">Status</th>
                    {isFaculty && <th scope="col"><span className="sr-only">Open analysis</span></th>}
                  </tr>
                </thead>
                <tbody>
                  {visibleRows.map((row) => (
                    <tr key={row.session_id} className={row.is_ufm ? 'is-flagged' : ''}>
                      {isFaculty && (
                        <td>
                          <div className="results-student">
                            <strong>{row.student_name}</strong>
                            <span>{row.enrollment_no}</span>
                          </div>
                        </td>
                      )}
                      <td>
                        <Link to={resultPath(row)} className="results-assessment-link">
                          <span>{row.exam_title}</span><ArrowUpRight size={15} aria-hidden="true" />
                        </Link>
                      </td>
                      <td><span className="results-muted">{row.subject || '—'}</span></td>
                      <td><span className="results-phase">{row.phase || '—'}</span></td>
                      <td className="is-number"><Score value={row.mcq_score} row={row} /></td>
                      <td className="is-number"><Score value={row.coding_score} row={row} /></td>
                      <td className="is-number"><Score value={row.total_score} row={row} suffix={`/${row.total_marks}`} /></td>
                      <td className="is-number"><Score value={row.percentage} row={row} suffix="%" /></td>
                      <td><ResultStatus row={row} /></td>
                      {isFaculty && (
                        <td className="results-analysis-cell">
                          <Link to={resultPath(row)} className="results-analysis-link" aria-label={`Open analysis for ${row.student_name}`}>
                            <BarChart3 size={16} /><span>Analysis</span>
                          </Link>
                        </td>
                      )}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            <div className="results-mobile-list">
              {visibleRows.map((row) => (
                <article key={row.session_id} className={`results-mobile-card${row.is_ufm ? ' is-flagged' : ''}`}>
                  <div className="results-mobile-card__topline">
                    <span className="results-phase">{row.phase || 'No phase'}</span>
                    <ResultStatus row={row} />
                  </div>
                  {isFaculty && <div className="results-mobile-card__student"><strong>{row.student_name}</strong><span>{row.enrollment_no}</span></div>}
                  <Link to={resultPath(row)} className="results-mobile-card__title">{row.exam_title}<ArrowUpRight size={17} /></Link>
                  <p>{row.subject || 'Subject not set'}</p>
                  <dl className="results-mobile-card__scores">
                    <div><dt>MCQ</dt><dd><Score value={row.mcq_score} row={row} /></dd></div>
                    <div><dt>Coding</dt><dd><Score value={row.coding_score} row={row} /></dd></div>
                    <div><dt>Total</dt><dd><Score value={row.total_score} row={row} suffix={`/${row.total_marks}`} /></dd></div>
                    <div><dt>Percentage</dt><dd><Score value={row.percentage} row={row} suffix="%" /></dd></div>
                  </dl>
                  {isFaculty && <Link to={resultPath(row)} className="results-mobile-card__analysis"><BarChart3 size={16} /> Open detailed analysis</Link>}
                </article>
              ))}
            </div>
          </>
        )}

        {!loading && !error && orderedRows.length > 0 && (
          <footer className="results-pagination" aria-label="Results pagination">
            <p>Showing <strong>{rangeStart}–{rangeEnd}</strong> of <strong>{orderedRows.length}</strong> records</p>
            <div>
              <button type="button" onClick={() => setCurrentPage((page) => Math.max(1, page - 1))} disabled={safePage === 1} aria-label="Previous page"><ChevronLeft size={17} /></button>
              <span>Page {safePage} of {pageCount}</span>
              <button type="button" onClick={() => setCurrentPage((page) => Math.min(pageCount, page + 1))} disabled={safePage === pageCount} aria-label="Next page"><ChevronRight size={17} /></button>
            </div>
          </footer>
        )}
      </section>
    </div>
  );
}



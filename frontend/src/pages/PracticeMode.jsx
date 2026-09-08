import React, { useEffect, useState, useRef } from 'react';
import { RefreshCcw, CheckCircle2, XCircle, Clock, ListChecks, ShieldOff } from 'lucide-react';
import api from '../api/axios';
import './practice-page.css';

const COUNT_OPTIONS = [5, 10, 15, 20];

function formatElapsed(seconds) {
  const m = Math.floor(seconds / 60).toString().padStart(2, '0');
  const s = Math.floor(seconds % 60).toString().padStart(2, '0');
  return `${m}:${s}`;
}

export default function PracticeMode() {
  const [phase, setPhase] = useState('setup'); // setup | active | result
  const [topics, setTopics] = useState([]);
  const [topic, setTopic] = useState('');
  const [count, setCount] = useState(10);
  const [questions, setQuestions] = useState([]);
  const [answers, setAnswers] = useState({});
  const [result, setResult] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [elapsed, setElapsed] = useState(0);
  const timerRef = useRef(null);

  useEffect(() => {
    api.get('/practice/questions/', { params: { count: 1 } })
      .then(({ data }) => setTopics(data.topics || []))
      .catch(() => setTopics([]));
  }, []);

  useEffect(() => {
    if (phase !== 'active') {
      window.clearInterval(timerRef.current);
      return undefined;
    }
    timerRef.current = window.setInterval(() => setElapsed((t) => t + 1), 1000);
    return () => window.clearInterval(timerRef.current);
  }, [phase]);

  const startTest = async () => {
    setLoading(true);
    setError('');
    try {
      const { data } = await api.get('/practice/questions/', { params: { topic, count } });
      if (!data.questions?.length) {
        setError('No practice questions are available for that topic yet. Try "All topics".');
        return;
      }
      setQuestions(data.questions);
      setAnswers({});
      setResult(null);
      setElapsed(0);
      setPhase('active');
    } catch {
      setError('Could not load practice questions. Please try again.');
    } finally {
      setLoading(false);
    }
  };

  const selectAnswer = (questionId, option) => {
    setAnswers((prev) => ({ ...prev, [questionId]: option }));
  };

  const submitTest = async () => {
    setLoading(true);
    setError('');
    try {
      const { data } = await api.post('/practice/submit/', { answers });
      setResult(data);
      setPhase('result');
    } catch {
      setError('Could not submit your answers. Please try again.');
    } finally {
      setLoading(false);
    }
  };

  const restart = () => {
    setPhase('setup');
    setQuestions([]);
    setAnswers({});
    setResult(null);
  };

  const answeredCount = Object.keys(answers).length;
  const resultById = new Map((result?.results || []).map((r) => [r.id, r]));

  return (
    <section className="app-page practice-page">
      <header className="page-heading">
        <div>
          <p className="eyebrow">Practice mode</p>
          <h1>Mock test</h1>
          <p>Low-stakes practice questions to warm up before a real assessment. Nothing here is proctored, timed against you, recorded, or ever visible to faculty — no camera or microphone access is used.</p>
        </div>
      </header>

      <div className="practice-privacy-note">
        <ShieldOff size={16} />
        <span>No camera, no microphone, no session recording. Retake as many times as you like.</span>
      </div>

      {error && <p className="practice-error">{error}</p>}

      {phase === 'setup' && (
        <article className="practice-card practice-setup">
          <h2>Set up your practice run</h2>
          <div className="practice-setup-grid">
            <label>
              <span>Topic</span>
              <select value={topic} onChange={(e) => setTopic(e.target.value)}>
                <option value="">All topics</option>
                {topics.map((t) => <option key={t} value={t}>{t}</option>)}
              </select>
            </label>
            <label>
              <span>Number of questions</span>
              <select value={count} onChange={(e) => setCount(Number(e.target.value))}>
                {COUNT_OPTIONS.map((c) => <option key={c} value={c}>{c} questions</option>)}
              </select>
            </label>
          </div>
          <button type="button" className="button" onClick={startTest} disabled={loading}>
            <ListChecks size={16} /> {loading ? 'Loading…' : 'Start mock test'}
          </button>
        </article>
      )}

      {phase === 'active' && (
        <>
          <div className="practice-progress-bar">
            <span><Clock size={14} /> {formatElapsed(elapsed)}</span>
            <span>{answeredCount} / {questions.length} answered</span>
          </div>
          <div className="practice-question-list">
            {questions.map((q, idx) => (
              <article className="practice-card" key={q.id}>
                <p className="practice-question-meta">Question {idx + 1} · {q.topic} · {q.difficulty}</p>
                <h3>{q.question_text}</h3>
                <div className="practice-options">
                  {Object.entries(q.options).map(([key, text]) => (
                    <label key={key} className={`practice-option${answers[q.id] === key ? ' is-selected' : ''}`}>
                      <input
                        type="radio"
                        name={`q-${q.id}`}
                        checked={answers[q.id] === key}
                        onChange={() => selectAnswer(q.id, key)}
                      />
                      <span className="practice-option-key">{key}</span>
                      <span>{text}</span>
                    </label>
                  ))}
                </div>
              </article>
            ))}
          </div>
          <div className="practice-submit-bar">
            <p>{answeredCount < questions.length ? `${questions.length - answeredCount} question(s) still unanswered — you can still submit.` : 'All questions answered.'}</p>
            <button type="button" className="button" onClick={submitTest} disabled={loading || answeredCount === 0}>
              {loading ? 'Submitting…' : 'Submit and see score'}
            </button>
          </div>
        </>
      )}

      {phase === 'result' && result && (
        <>
          <article className="practice-card practice-score-card">
            <p className="practice-question-meta">Your score</p>
            <h2>{result.score} / {result.total}</h2>
            <p className="practice-score-pct">{result.percentage}% correct</p>
            <button type="button" className="button" onClick={restart}>
              <RefreshCcw size={16} /> Try another set
            </button>
          </article>
          <div className="practice-question-list">
            {questions.map((q, idx) => {
              const r = resultById.get(q.id);
              if (!r) return null;
              return (
                <article className={`practice-card practice-review-card${r.is_correct ? ' is-correct' : ' is-incorrect'}`} key={q.id}>
                  <p className="practice-question-meta">
                    Question {idx + 1} · {q.topic}
                    {r.is_correct
                      ? <span className="practice-review-tag is-correct"><CheckCircle2 size={13} /> Correct</span>
                      : <span className="practice-review-tag is-incorrect"><XCircle size={13} /> Incorrect</span>}
                  </p>
                  <h3>{q.question_text}</h3>
                  <div className="practice-options practice-options--readonly">
                    {Object.entries(q.options).map(([key, text]) => {
                      const isCorrectAnswer = key === r.correct_answer;
                      const isYourAnswer = key === r.your_answer;
                      const tone = isCorrectAnswer ? 'is-correct' : (isYourAnswer ? 'is-incorrect' : '');
                      return (
                        <div key={key} className={`practice-option ${tone}`.trim()}>
                          <span className="practice-option-key">{key}</span>
                          <span>{text}</span>
                          {isYourAnswer && !isCorrectAnswer && <em>Your answer</em>}
                          {isCorrectAnswer && <em>Correct answer</em>}
                        </div>
                      );
                    })}
                  </div>
                  {r.explanation && <p className="practice-explanation">{r.explanation}</p>}
                </article>
              );
            })}
          </div>
        </>
      )}
    </section>
  );
}



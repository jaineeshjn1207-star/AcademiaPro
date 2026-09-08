import React from 'react';
import { Link } from 'react-router-dom';
import {
  ArrowRight,
  BarChart3,
  BookOpenCheck,
  Check,
  ChevronRight,
  Code2,
  FileCheck2,
  GraduationCap,
  Layers3,
  Moon,
  ShieldCheck,
  Sparkles,
  Sun,
  UserRoundCheck,
} from 'lucide-react';
import { useTheme } from '../context/ThemeContext';
import './public-pages.css';

const capabilities = [
  {
    icon: ShieldCheck,
    title: 'Designed for integrity',
    text: 'Secure delivery controls and real-time proctoring give every assessment the attention it deserves.',
    tone: 'blue',
  },
  {
    icon: BookOpenCheck,
    title: 'Materials in context',
    text: 'Organise faculty notes and learning resources around the examinations that need them.',
    tone: 'violet',
  },
  {
    icon: Code2,
    title: 'Thoughtful evaluation',
    text: 'Bring automated logic evaluation and human review into one consistent marking workflow.',
    tone: 'mint',
  },
];

export default function Home() {
  const { theme, toggleTheme } = useTheme();

  return (
    <div className="public-home">
      <div className="public-grid-noise" aria-hidden="true" />
      <header className="public-topbar public-home__topbar">
        <a className="public-brand" href="/" aria-label="Academia Pro home">
          <span className="public-brand__mark"><GraduationCap aria-hidden="true" /></span>
          <span>Academia <em>Pro</em></span>
        </a>

        <nav className="public-home__nav" aria-label="Primary navigation">
          <a href="#capabilities">Capabilities</a>
          <a href="#experience">Experience</a>
          <a href="#start">Get started</a>
        </nav>

        <div className="public-home__actions">
          <button className="public-theme-toggle" type="button" onClick={toggleTheme} aria-label={`Switch to ${theme === 'dark' ? 'light' : 'dark'} mode`}>
            {theme === 'dark' ? <Sun aria-hidden="true" /> : <Moon aria-hidden="true" />}
            <span>{theme === 'dark' ? 'Light' : 'Dark'}</span>
          </button>
          <Link className="public-nav-login" to="/login">Sign in <ArrowRight aria-hidden="true" /></Link>
        </div>
      </header>

      <main>
        <section className="public-hero" aria-labelledby="home-title">
          <div className="public-hero__copy">
            <p className="public-kicker"><span aria-hidden="true" /> A calmer assessment experience</p>
            <h1 id="home-title">Exams that feel <i>clear, fair,</i> and in control.</h1>
            <p className="public-hero__lede">
              Academia Pro brings secure assessments, faculty workflows, and meaningful learning insight into one focused workspace.
            </p>
            <div className="public-hero__actions">
              <Link className="public-primary-link" to="/login">Open your workspace <ArrowRight aria-hidden="true" /></Link>
              <a className="public-text-link" href="#capabilities">Explore the platform <ChevronRight aria-hidden="true" /></a>
            </div>
            <div className="public-hero__proof" aria-label="Platform benefits">
              <span><Check aria-hidden="true" /> Student and faculty portals</span>
              <span><Check aria-hidden="true" /> Secure by design</span>
            </div>
          </div>

          <div className="public-hero__visual" aria-label="Preview of the Academia Pro assessment workspace">
            <div className="public-preview public-preview--back" aria-hidden="true" />
            <div className="public-preview">
              <div className="public-preview__head">
                <div><span className="public-preview__signal" /><span>Today’s assessment</span></div>
                <span className="public-preview__avatar">AP</span>
              </div>
              <div className="public-preview__main">
                <span className="public-preview__eyebrow">Live workspace</span>
                <h2>Data structures<br />midterm</h2>
                <p>Friday, 14:30 — 90 minutes</p>
                <div className="public-preview__progress"><span /></div>
                <div className="public-preview__meta"><span><strong>08</strong> questions</span><span><strong>72</strong> marks</span><span><strong>38:14</strong> remaining</span></div>
              </div>
              <div className="public-preview__foot">
                <span><ShieldCheck aria-hidden="true" /> Secure session active</span>
                <span aria-hidden="true"><ArrowRight /></span>
              </div>
            </div>
            <div className="public-floating-note public-floating-note--one"><FileCheck2 aria-hidden="true" /><span><strong>Everything ready</strong><small>Reviewing your instructions</small></span></div>
            <div className="public-floating-note public-floating-note--two"><Sparkles aria-hidden="true" /><span><strong>Clearer outcomes</strong><small>Live assessment insight</small></span></div>
          </div>
        </section>

        <section className="public-trust-line" aria-label="Core platform areas">
          <span>Built for modern assessment teams</span>
          <div><strong>01</strong> Secure delivery</div>
          <div><strong>02</strong> Faculty control</div>
          <div><strong>03</strong> Actionable insight</div>
        </section>

        <section id="capabilities" className="public-capabilities" aria-labelledby="capabilities-title">
          <div className="public-section-heading">
            <p className="public-kicker"><span aria-hidden="true" /> Built around the work</p>
            <h2 id="capabilities-title">A practical foundation for better assessment.</h2>
            <p>Less administrative friction, more confidence at every step — from preparation through to results.</p>
          </div>
          <div className="public-capability-grid">
            {capabilities.map(({ icon: Icon, title, text, tone }) => (
              <article className={`public-capability public-capability--${tone}`} key={title}>
                <span className="public-capability__icon"><Icon aria-hidden="true" /></span>
                <h3>{title}</h3>
                <p>{text}</p>
                <Link to="/login" aria-label={`Open ${title.toLowerCase()} in the portal`}>Open portal <ArrowRight aria-hidden="true" /></Link>
              </article>
            ))}
          </div>
        </section>

        <section id="experience" className="public-experience" aria-labelledby="experience-title">
          <div className="public-experience__visual">
            <div className="public-experience__chart" aria-hidden="true">
              <div className="public-experience__chart-top"><span>Assessment pulse</span><span>Weekly</span></div>
              <div className="public-bar-set"><i style={{ height: '38%' }} /><i style={{ height: '62%' }} /><i style={{ height: '48%' }} /><i style={{ height: '82%' }} /><i style={{ height: '68%' }} /><i style={{ height: '94%' }} /><i style={{ height: '76%' }} /></div>
              <div className="public-chart-labels"><span>Mon</span><span>Tue</span><span>Wed</span><span>Thu</span><span>Fri</span><span>Sat</span><span>Sun</span></div>
            </div>
            <div className="public-experience__metric"><BarChart3 aria-hidden="true" /><strong>One clear view</strong><span>See assessment progress and signals as they emerge.</span></div>
          </div>
          <div className="public-experience__copy">
            <p className="public-kicker"><span aria-hidden="true" /> A shared point of view</p>
            <h2 id="experience-title">Built to reduce uncertainty, not add another dashboard.</h2>
            <p>Students find what is next quickly. Faculty have the context to guide, review, and improve — without losing sight of the people behind the data.</p>
            <ul>
              <li><span><UserRoundCheck aria-hidden="true" /></span><div><strong>Role-aware from the start</strong><small>Each person enters a workspace shaped around their responsibilities.</small></div></li>
              <li><span><Layers3 aria-hidden="true" /></span><div><strong>One connected workflow</strong><small>Assessment setup, delivery, analysis, and feedback stay in rhythm.</small></div></li>
            </ul>
          </div>
        </section>

        <section id="start" className="public-cta" aria-labelledby="start-title">
          <div><p className="public-kicker"><span aria-hidden="true" /> Ready when you are</p><h2 id="start-title">Your next assessment begins with a better first screen.</h2></div>
          <Link className="public-primary-link public-primary-link--inverse" to="/login">Sign in to Academia Pro <ArrowRight aria-hidden="true" /></Link>
        </section>
      </main>

      <footer className="public-footer">
        <a className="public-brand" href="/" aria-label="Academia Pro home">
          <span className="public-brand__mark"><GraduationCap aria-hidden="true" /></span>
          <span>Academia <em>Pro</em></span>
        </a>
        <p>Secure examination and automated logic evaluation.</p>
        <span>© {new Date().getFullYear()} Academia Pro</span>
      </footer>
    </div>
  );
}



import React, { useState } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import {
  ArrowRight,
  BadgeCheck,
  BookOpen,
  Check,
  GraduationCap,
  LockKeyhole,
  Moon,
  ShieldCheck,
  Sun,
  UserRound,
} from 'lucide-react';
import { useAuth } from '../context/AuthContext';
import { useTheme } from '../context/ThemeContext';
import './public-pages.css';

export default function Login() {
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  const [mustChange, setMustChange] = useState(false);
  const [newPassword, setNewPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [success, setSuccess] = useState('');

  const location = useLocation();
  const navigate = useNavigate();
  const { theme, toggleTheme } = useTheme();
  const { loginUnified, forcePasswordChange } = useAuth();

  const blockedNoticeFromRedirect = new URLSearchParams(location.search).get('blocked') === '1'
    ? 'Your account has been locked following a suspected unfair-means violation. You cannot sign back in until access is restored.'
    : '';
  const [blockedMessage] = useState(location.state?.blockedMessage || blockedNoticeFromRedirect || '');

  const submit = async (event) => {
    event.preventDefault();
    setError('');
    setSuccess('');
    setLoading(true);
    try {
      if (mustChange) {
        if (newPassword !== confirmPassword) {
          setError('New passwords do not match.');
          return;
        }
        await forcePasswordChange(username.trim(), password, newPassword);
        setMustChange(false);
        setPassword('');
        setNewPassword('');
        setConfirmPassword('');
        setSuccess('Password created. Sign in with your new password.');
        return;
      }
      const data = await loginUnified(username.trim(), password);
      const role = data?.user?.user_type;
      navigate(role === 'admin' ? '/admin' : '/', { replace: true });
    } catch (requestError) {
      if (requestError.response?.data?.must_change_password) {
        setMustChange(true);
        setError('Temporary password accepted. Create your permanent password to continue.');
      } else {
        setError(requestError.response?.data?.error || 'Invalid credentials.');
      }
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="public-auth">
      <div className="public-orb public-orb--one" aria-hidden="true" />
      <div className="public-orb public-orb--two" aria-hidden="true" />

      <header className="public-topbar public-auth__topbar">
        <a className="public-brand" href="/" aria-label="Academia Pro home">
          <span className="public-brand__mark"><GraduationCap aria-hidden="true" /></span>
          <span>Academia <em>Pro</em></span>
        </a>
        <button className="public-theme-toggle" type="button" onClick={toggleTheme} aria-label={`Switch to ${theme === 'dark' ? 'light' : 'dark'} mode`}>
          {theme === 'dark' ? <Sun aria-hidden="true" /> : <Moon aria-hidden="true" />}
          <span>{theme === 'dark' ? 'Light' : 'Dark'}</span>
        </button>
      </header>

      <main className="public-auth__layout">
        <section className="public-auth__story" aria-labelledby="secure-access-title">
          <p className="public-kicker"><span aria-hidden="true" /> Unified access</p>
          <h1 id="secure-access-title">Every assessment, <i>in good hands.</i></h1>
          <p className="public-auth__lede">
            One secure sign-in for students, faculty, and admins. Academia Pro opens the right workspace automatically.
          </p>

          <div className="public-assurance-list">
            <div>
              <span className="public-assurance-list__icon"><ShieldCheck aria-hidden="true" /></span>
              <span><strong>Role-aware routing</strong><small>Students, faculty, and admins land in their correct panel.</small></span>
            </div>
            <div>
              <span className="public-assurance-list__icon"><BadgeCheck aria-hidden="true" /></span>
              <span><strong>Protected workflow</strong><small>Secure exams, manual result publish, proctoring, and admin oversight.</small></span>
            </div>
          </div>

          <div className="public-auth__quote">
            <BookOpen aria-hidden="true" />
            <p>“The best assessment experience feels quietly dependable from the very first sign-in.”</p>
          </div>
        </section>

        <section className="public-auth-card" aria-labelledby="sign-in-title">
          <div className="public-auth-card__heading">
            <span className="public-auth-card__step">Secure sign-in</span>
            <h2 id="sign-in-title">{mustChange ? 'Create your password' : 'Welcome back'}</h2>
            <p>{mustChange ? 'Enter a new permanent password for your account.' : 'Use your student, faculty, or admin account.'}</p>
          </div>

          {blockedMessage && (
            <div className="public-alert public-alert--danger" role="alert">
              <LockKeyhole aria-hidden="true" />
              <span>{blockedMessage}</span>
            </div>
          )}
          {error && (
            <div className="public-alert public-alert--danger" role="alert">
              <LockKeyhole aria-hidden="true" />
              <span>{error}</span>
            </div>
          )}
          {success && (
            <div className="public-form-note" role="status">
              <Check aria-hidden="true" />
              <span>{success}</span>
            </div>
          )}

          <form className="public-login-form" onSubmit={submit}>
            <label className="public-field">
              <span>Username / email / enrollment</span>
              <div className="public-field__control">
                <UserRound aria-hidden="true" />
                <input
                  autoComplete="username"
                  value={username}
                  onChange={(event) => setUsername(event.target.value)}
                  placeholder="e.g. en2026001, prof_sharma, admin"
                  required
                />
              </div>
            </label>

            <label className="public-field">
              <span>{mustChange ? 'Temporary password' : 'Password'}</span>
              <div className="public-field__control">
                <LockKeyhole aria-hidden="true" />
                <input
                  type="password"
                  autoComplete="current-password"
                  value={password}
                  onChange={(event) => setPassword(event.target.value)}
                  placeholder={mustChange ? 'Enter temporary password' : 'Enter password'}
                  required
                />
              </div>
            </label>

            {mustChange && (
              <>
                <label className="public-field">
                  <span>New password</span>
                  <div className="public-field__control">
                    <LockKeyhole aria-hidden="true" />
                    <input type="password" value={newPassword} onChange={(event) => setNewPassword(event.target.value)} placeholder="At least 8 characters" required />
                  </div>
                </label>
                <label className="public-field">
                  <span>Confirm new password</span>
                  <div className="public-field__control">
                    <LockKeyhole aria-hidden="true" />
                    <input type="password" value={confirmPassword} onChange={(event) => setConfirmPassword(event.target.value)} placeholder="Repeat new password" required />
                  </div>
                </label>
              </>
            )}

            <button className="public-submit" disabled={loading} type="submit">
              <span>{loading ? (mustChange ? 'Saving…' : 'Signing in…') : (mustChange ? 'Create password' : 'Sign in')}</span>
              <ArrowRight aria-hidden="true" />
            </button>
          </form>

          <p className="public-auth-card__foot" style={{fontSize: '15px'}}>
            Need help? Ask your institution admin to reset your account.
          </p>
        </section>
      </main>
    </div>
  );
}

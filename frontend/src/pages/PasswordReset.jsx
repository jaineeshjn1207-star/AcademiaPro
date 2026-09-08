import React, { useState } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import { KeyRound, Mail, ShieldCheck } from 'lucide-react';
import api from '../api/axios';
import './public-pages.css';

export default function PasswordReset() {
  const [params] = useSearchParams(); const token = params.get('token');
  const [identifier, setIdentifier] = useState(''); const [password, setPassword] = useState(''); const [message, setMessage] = useState(''); const [error, setError] = useState(''); const [loading, setLoading] = useState(false);
  const submit = async (event) => { event.preventDefault(); setLoading(true); setError(''); try { const res = token ? await api.post('auth/password-reset/confirm/', { token, password }) : await api.post('auth/password-reset/', { identifier }); setMessage(res.data.message); } catch (e) { setError(e.response?.data?.error?.[0] || e.response?.data?.error || 'Unable to complete this request.'); } finally { setLoading(false); } };
  return <main className="public-auth"><header className="public-topbar"><Link className="public-brand" to="/"><span className="public-brand__mark"><ShieldCheck /></span><span>Academia <em>Pro</em></span></Link></header><section className="public-auth__layout"><div className="public-auth__story"><p className="public-kicker"><span /> Account recovery</p><h1>{token ? 'Choose a new password.' : 'Get back to your workspace.'}</h1><p className="public-auth__lede">{token ? 'Use a strong password you do not use elsewhere.' : 'Enter your username, enrollment number, or institutional email.'}</p></div><form className="public-auth-card public-login-form" onSubmit={submit}><div className="public-auth-card__heading"><span className="public-auth-card__step">Secure recovery</span><h2>{token ? 'Reset password' : 'Forgot password?'}</h2></div>{message && <div className="public-message public-message--critical" role="status">{message}</div>}{error && <div className="public-message public-message--error" role="alert">{error}</div>}<label className="public-field"><span>{token ? 'New password' : 'Account identifier'}</span><span className="public-field__control">{token ? <KeyRound /> : <Mail />}<input required type={token ? 'password' : 'text'} value={token ? password : identifier} onChange={(e) => token ? setPassword(e.target.value) : setIdentifier(e.target.value)} /></span></label><button className="public-submit" disabled={loading}>{loading ? 'Please wait…' : token ? 'Set new password' : 'Send reset instructions'}</button><Link to="/login" className="public-nav-login">Back to sign in</Link></form></section></main>;
}



import React, { useEffect, useRef, useState } from 'react';
import { Bot, Loader2, Send, ShieldAlert, Sparkles, UserRound } from 'lucide-react';
import api from '../api/axios';
import { useAuth } from '../context/AuthContext';
import './tutor-page.css';

const starters = [
  'Explain recursion with a simple Python example',
  'Help me debug this code',
  'Explain time complexity of binary search',
  'How should I structure a REST API project?',
];

export default function AITutor() {
  const { user } = useAuth();
  const [messages, setMessages] = useState([{ role: 'assistant', content: 'I’m your learning partner. Ask about programming, debugging, algorithms, web development, databases, or exam preparation.' }]);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const bottomRef = useRef(null);

  useEffect(() => { bottomRef.current?.scrollIntoView({ behavior: 'smooth' }); }, [messages, loading]);

  const sendMessage = async (text = input) => {
    const query = String(text || '').trim();
    if (!query || loading) return;
    setInput('');
    setError('');
    const nextMessages = [...messages, { role: 'user', content: query }];
    setMessages(nextMessages);
    setLoading(true);
    try {
      const history = nextMessages.slice(-20).map((message) => ({ role: message.role, content: message.content }));
      const response = await api.post('ai-tutor/chat/', { message: query, history });
      setMessages((current) => [...current, { role: 'assistant', content: response.data.reply || 'No response.' }]);
    } catch (requestError) {
      const message = requestError.response?.data?.error || 'The tutor is unavailable right now. Please try again later.';
      setError(message);
      setMessages((current) => [...current, { role: 'assistant', content: message, isError: true }]);
    } finally { setLoading(false); }
  };

  return (
    <div className="tutor-page">
      <aside className="tutor-rail">
        <div className="tutor-rail-mark"><Sparkles size={19} /></div>
        <p className="app-eyebrow">Learning lab</p>
        <h1>Think it through.<br /><em>Build it better.</em></h1>
        <p className="tutor-rail-copy">A focused space for explanations, debugging, and practical programming guidance.</p>
        <div className="tutor-guardrail"><ShieldAlert size={17} /><p>The tutor will never help bypass proctoring, security, or active-exam rules.</p></div>
        <div className="tutor-identity"><span>{(user?.name || 'U')[0]}</span><div><strong>{user?.name || user?.username}</strong><small>Connected to your workspace</small></div></div>
      </aside>
      <main className="tutor-conversation">
        <header><div><p className="app-eyebrow">Academia assistant</p><h2>What are you working on?</h2></div><span className="tutor-online"><i /> Online</span></header>
        <section className="tutor-thread" aria-live="polite">
          {messages.map((message, index) => {
            const isUser = message.role === 'user';
            return <div key={`${message.role}-${index}`} className={`tutor-message ${isUser ? 'is-user' : ''}${message.isError ? ' is-error' : ''}`}>
              <div className="tutor-message-avatar">{isUser ? <UserRound size={16} /> : <Bot size={17} />}</div>
              <div><span className="tutor-message-label">{isUser ? 'You' : 'Tutor'}</span><div className="tutor-bubble">{message.content}</div></div>
            </div>;
          })}
          {loading && <div className="tutor-thinking"><Loader2 size={15} className="animate-spin" /> Thinking through it…</div>}
          <div ref={bottomRef} />
        </section>
        {messages.length === 1 && <div className="tutor-starters"><span>Try one of these</span><div>{starters.map((prompt) => <button type="button" key={prompt} onClick={() => sendMessage(prompt)}>{prompt}</button>)}</div></div>}
        {error && <p className="tutor-error" role="alert">{error}</p>}
        <form className="tutor-composer" onSubmit={(event) => { event.preventDefault(); sendMessage(); }}>
          <textarea value={input} onChange={(event) => setInput(event.target.value)} onKeyDown={(event) => { if (event.key === 'Enter' && !event.shiftKey) { event.preventDefault(); sendMessage(); } }} rows={1} placeholder="Describe a problem, paste code, or ask a question…" aria-label="Message the tutor" />
          <button type="submit" disabled={loading || !input.trim()} aria-label="Send message">{loading ? <Loader2 size={18} className="animate-spin" /> : <Send size={18} />}</button>
        </form>
      </main>
    </div>
  );
}



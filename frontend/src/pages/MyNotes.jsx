import React, { useState, useEffect, useCallback, useRef } from 'react';
import api from '../api/axios';
import { useToast } from '../components/ToastProvider';
import './notes-page.css';
import {
  NotebookPen, PlusCircle, Search, Trash2, Pencil, Pin, X, Save,
  Tag, Loader2, CheckCircle2, AlertCircle, StickyNote, Lock, Paperclip, Download,
} from 'lucide-react';

const COLORS = [
  { id: 'slate',   dot: 'bg-slate-400',   card: 'bg-white border-slate-200',        head: 'text-slate-900' },
  { id: 'blue',    dot: 'bg-blue-500',    card: 'bg-blue-50/60 border-blue-200',    head: 'text-blue-900' },
  { id: 'emerald', dot: 'bg-emerald-500', card: 'bg-emerald-50/60 border-emerald-200', head: 'text-emerald-900' },
  { id: 'amber',   dot: 'bg-amber-500',   card: 'bg-amber-50/70 border-amber-200',  head: 'text-amber-900' },
  { id: 'rose',    dot: 'bg-rose-500',    card: 'bg-rose-50/60 border-rose-200',    head: 'text-rose-900' },
  { id: 'violet',  dot: 'bg-violet-500',  card: 'bg-violet-50/60 border-violet-200', head: 'text-violet-900' },
];

const EMPTY = { title: '', content: '', subject: '', tags: '', color: 'slate', is_pinned: false };

export default function MyNotes() {
  const { confirm } = useToast();
  const [notes, setNotes] = useState([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState('');

  const [showForm, setShowForm] = useState(false);
  const [editingId, setEditingId] = useState(null);
  const [form, setForm] = useState(EMPTY);
  const [file, setFile] = useState(null);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');
  const [toast, setToast] = useState('');
  const titleRef = useRef(null);

  const flash = (m) => { setToast(m); setTimeout(() => setToast(''), 2500); };

  const load = useCallback(async () => {
    try {
      const params = search.trim() ? { search: search.trim() } : {};
      const res = await api.get('my-notes/', { params });
      setNotes(Array.isArray(res.data) ? res.data : res.data.results || []);
    } catch {
      setError('Could not load your notes.');
    } finally {
      setLoading(false);
    }
  }, [search]);

  useEffect(() => {
    const t = setTimeout(load, search ? 300 : 0);
    return () => clearTimeout(t);
  }, [load, search]);

  useEffect(() => {
    if (showForm) setTimeout(() => titleRef.current?.focus(), 80);
  }, [showForm]);

  const openCreate = () => { setForm(EMPTY); setFile(null); setEditingId(null); setError(''); setShowForm(true); };

  const openEdit = (n) => {
    setForm({
      title: n.title || '', content: n.content || '', subject: n.subject || '',
      tags: n.tags || '', color: n.color || 'slate', is_pinned: n.is_pinned,
    });
    setFile(null);
    setEditingId(n.id);
    setError('');
    setShowForm(true);
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!form.title.trim()) { setError('Please give your note a title.'); return; }
    setSaving(true);
    setError('');
    try {
      let payload = form;
      let headers;
      if (file) {
        payload = new FormData();
        Object.entries(form).forEach(([k, v]) => payload.append(k, typeof v === 'boolean' ? String(v) : v));
        payload.append('attachment', file);
        headers = { 'Content-Type': 'multipart/form-data' };
      }
      if (editingId) {
        await api.patch(`my-notes/${editingId}/`, payload, { headers });
        flash('Note updated.');
      } else {
        await api.post('my-notes/', payload, { headers });
        flash('Note saved.');
      }
      setShowForm(false);
      load();
    } catch (err) {
      const d = err.response?.data;
      setError(typeof d === 'object' ? Object.entries(d || {}).map(([k, v]) => `${k}: ${v}`).join(' | ') : 'Failed to save.');
    } finally {
      setSaving(false);
    }
  };

  const handleDelete = async (id) => {
    const ok = await confirm({
      title: 'Delete this note?',
      message: 'This cannot be undone.',
      confirmText: 'Delete note',
      danger: true,
    });
    if (!ok) return;
    try {
      await api.delete(`my-notes/${id}/`);
      setNotes((n) => n.filter((x) => x.id !== id));
      flash('Note deleted.');
    } catch { flash('Could not delete the note.'); }
  };

  const togglePin = async (n) => {
    try {
      await api.patch(`my-notes/${n.id}/`, { is_pinned: !n.is_pinned });
      load();
    } catch { flash('Could not update the note.'); }
  };

  const colorOf = (id) => COLORS.find((c) => c.id === id) || COLORS[0];

  if (loading) {
    return (
      <div className="flex min-h-[60vh] items-center justify-center">
        <Loader2 className="h-10 w-10 animate-spin text-emerald-600" />
      </div>
    );
  }

  return (
    <div className="app-page notes-page my-notes-page">
      {toast && (
        <div className="fixed right-6 top-6 z-50 flex items-center gap-2 rounded-xl bg-slate-900 px-4 py-3 text-sm font-medium text-white shadow-2xl">
          <CheckCircle2 className="h-4 w-4 text-emerald-400" /> {toast}
        </div>
      )}

      {/* Header */}
      <div className="rounded-2xl border border-slate-200 bg-white p-6 text-slate-900 shadow-sm sm:p-8">
        <div className="flex flex-col justify-between gap-6 md:flex-row md:items-center">
          <div>
            <span className="inline-flex items-center gap-1.5 rounded-full border border-emerald-200 bg-emerald-100 px-3 py-1 text-xs font-semibold uppercase tracking-wider text-emerald-700">
              <Lock className="h-3 w-3" /> Private to you
            </span>
            <h1 className="mt-2 flex items-center gap-3 text-3xl font-extrabold tracking-tight">
              <NotebookPen className="h-8 w-8 text-emerald-400" />
              My Personal Notes
            </h1>
            <p className="mt-1 text-sm text-slate-500">
              Your own revision notebook. Only you can see these — faculty and other students cannot.
            </p>
          </div>
          <button
            onClick={openCreate}
            className="flex items-center justify-center gap-2 rounded-xl bg-emerald-600 px-6 py-3.5 font-bold text-white shadow-lg transition hover:bg-emerald-700"
          >
            <PlusCircle className="h-5 w-5" /> New Note
          </button>
        </div>
      </div>

      {/* Search */}
      <div className="relative">
        <Search className="absolute left-3.5 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400" />
        <input
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          placeholder="Search your notes by title, content or tag..."
          className="w-full rounded-xl border border-slate-300 bg-white py-3 pl-11 pr-4 text-sm outline-none transition focus:border-emerald-500 focus:ring-2 focus:ring-emerald-100"
        />
      </div>

      {/* Notes grid */}
      {notes.length === 0 ? (
        <div className="rounded-3xl border-2 border-dashed border-slate-300 bg-white p-16 text-center">
          <StickyNote className="mx-auto mb-3 h-12 w-12 text-slate-300" />
          <p className="font-semibold text-slate-700">
            {search ? 'No notes match your search.' : 'Your notebook is empty.'}
          </p>
          <p className="mt-1 text-xs text-slate-400">
            {search ? 'Try a different keyword.' : 'Create your first note to start building your revision material.'}
          </p>
          {!search && (
            <button onClick={openCreate}
              className="mt-5 inline-flex items-center gap-2 rounded-xl bg-emerald-600 px-5 py-2.5 text-sm font-bold text-white transition hover:bg-emerald-700">
              <PlusCircle className="h-4 w-4" /> Create a note
            </button>
          )}
        </div>
      ) : (
        <div className="grid grid-cols-1 gap-5 md:grid-cols-2 xl:grid-cols-3">
          {notes.map((n) => {
            const c = colorOf(n.color);
            return (
              <article key={n.id}
                className={`flex flex-col rounded-2xl border p-5 shadow-sm transition hover:shadow-md ${c.card} ${
                  n.is_pinned ? 'ring-2 ring-amber-300' : ''
                }`}>
                <div className="mb-2 flex items-start justify-between gap-2">
                  <div className="flex min-w-0 items-center gap-2">
                    <span className={`h-2.5 w-2.5 flex-shrink-0 rounded-full ${c.dot}`} />
                    <h3 className={`truncate text-base font-bold ${c.head}`}>{n.title}</h3>
                  </div>
                  <div className="flex flex-shrink-0 items-center gap-0.5">
                    <button onClick={() => togglePin(n)} title={n.is_pinned ? 'Unpin' : 'Pin'}
                      className={`rounded-lg p-1.5 transition ${n.is_pinned ? 'text-amber-600' : 'text-slate-400 hover:text-slate-700'}`}>
                      <Pin className="h-3.5 w-3.5" />
                    </button>
                    <button onClick={() => openEdit(n)} title="Edit"
                      className="rounded-lg p-1.5 text-slate-400 transition hover:text-blue-600">
                      <Pencil className="h-3.5 w-3.5" />
                    </button>
                    <button onClick={() => handleDelete(n.id)} title="Delete"
                      className="rounded-lg p-1.5 text-slate-400 transition hover:text-rose-600">
                      <Trash2 className="h-3.5 w-3.5" />
                    </button>
                  </div>
                </div>

                {n.subject && (
                  <span className="mb-2 w-fit rounded-full bg-white/70 px-2 py-0.5 text-[11px] font-bold uppercase tracking-wide text-slate-600">
                    {n.subject}
                  </span>
                )}

                <pre className="mb-3 line-clamp-[10] flex-1 whitespace-pre-wrap break-words font-sans text-xs leading-relaxed text-slate-700">
                  {n.content || <span className="italic text-slate-400">No content</span>}
                </pre>

                {n.tag_list?.length > 0 && (
                  <div className="mb-2 flex flex-wrap gap-1">
                    {n.tag_list.map((t) => (
                      <span key={t} className="inline-flex items-center gap-1 rounded-md bg-white/80 px-1.5 py-0.5 text-[11px] font-medium text-slate-600">
                        <Tag className="h-2.5 w-2.5" />{t}
                      </span>
                    ))}
                  </div>
                )}

                {n.attachment_url && (
                  <a
                    href={n.attachment_url}
                    target="_blank"
                    rel="noreferrer"
                    className="mb-3 inline-flex w-fit items-center gap-1.5 rounded-lg border border-emerald-200 bg-white/80 px-2.5 py-1 text-[12px] font-bold text-emerald-700 hover:bg-emerald-50"
                  >
                    <Download className="h-3 w-3" /> {n.attachment_name || 'Download attachment'}
                  </a>
                )}

                <div className="mt-auto border-t border-slate-900/5 pt-2 text-[11px] text-slate-500">
                  Updated {new Date(n.updated_at).toLocaleString('en-IN', {
                    day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit',
                  })}
                </div>
              </article>
            );
          })}
        </div>
      )}

      {/* Editor modal */}
      {showForm && (
        <div className="fixed inset-0 z-50 flex items-start justify-center overflow-y-auto bg-black/60 p-4 backdrop-blur-sm">
          <form onSubmit={handleSubmit} className="my-8 w-full max-w-2xl rounded-3xl bg-white shadow-2xl">
            <div className="flex items-center justify-between border-b border-slate-200 px-6 py-5">
              <h3 className="flex items-center gap-2 text-lg font-bold text-slate-900">
                <NotebookPen className="h-5 w-5 text-emerald-600" />
                {editingId ? 'Edit Note' : 'New Personal Note'}
              </h3>
              <button type="button" onClick={() => setShowForm(false)}
                className="rounded-lg p-2 text-slate-400 transition hover:bg-slate-100">
                <X className="h-5 w-5" />
              </button>
            </div>

            <div className="space-y-4 p-6">
              {error && (
                <div className="flex items-start gap-2 rounded-xl border border-rose-200 bg-rose-50 p-3 text-sm text-rose-700">
                  <AlertCircle className="mt-0.5 h-4 w-4 flex-shrink-0" /> {error}
                </div>
              )}

              <div>
                <label className="mb-1.5 block text-xs font-bold uppercase tracking-wide text-slate-600">Title *</label>
                <input ref={titleRef} value={form.title} onChange={(e) => setForm({ ...form, title: e.target.value })}
                  placeholder="e.g. Sliding window — key insight"
                  className="w-full rounded-xl border border-slate-300 px-4 py-2.5 text-sm outline-none focus:border-emerald-500 focus:ring-2 focus:ring-emerald-100" />
              </div>

              <div className="grid gap-4 sm:grid-cols-2">
                <div>
                  <label className="mb-1.5 block text-xs font-bold uppercase tracking-wide text-slate-600">Subject</label>
                  <input value={form.subject} onChange={(e) => setForm({ ...form, subject: e.target.value })}
                    placeholder="Algorithms"
                    className="w-full rounded-xl border border-slate-300 px-4 py-2.5 text-sm outline-none focus:border-emerald-500" />
                </div>
                <div>
                  <label className="mb-1.5 block text-xs font-bold uppercase tracking-wide text-slate-600">Tags (comma separated)</label>
                  <input value={form.tags} onChange={(e) => setForm({ ...form, tags: e.target.value })}
                    placeholder="revision, important"
                    className="w-full rounded-xl border border-slate-300 px-4 py-2.5 text-sm outline-none focus:border-emerald-500" />
                </div>
              </div>

              <div>
                <label className="mb-1.5 block text-xs font-bold uppercase tracking-wide text-slate-600">Content</label>
                <textarea value={form.content} onChange={(e) => setForm({ ...form, content: e.target.value })}
                  rows={12} placeholder="Write whatever helps you revise..."
                  className="w-full rounded-xl border border-slate-300 px-4 py-3 font-mono text-sm leading-relaxed outline-none focus:border-emerald-500" />
              </div>

              <div>
                <label className="mb-1.5 block text-xs font-bold uppercase tracking-wide text-slate-600">Optional attachment</label>
                <label className="flex cursor-pointer items-center justify-between gap-3 rounded-xl border border-dashed border-emerald-300 bg-emerald-50/60 px-4 py-3 text-sm text-emerald-900 hover:bg-emerald-50">
                  <span className="flex min-w-0 items-center gap-2">
                    <Paperclip className="h-4 w-4 flex-shrink-0 text-emerald-600" />
                    <span className="truncate">{file ? file.name : 'Attach PDF, notes, image, CSV, ZIP, etc. (max 20 MB)'}</span>
                  </span>
                  <input
                    type="file"
                    className="hidden"
                    onChange={(e) => setFile(e.target.files?.[0] || null)}
                  />
                </label>
                {file && (
                  <button type="button" onClick={() => setFile(null)} className="mt-1 text-xs font-bold text-rose-600 hover:text-rose-700">Remove selected file</button>
                )}
              </div>

              <div>
                <label className="mb-2 block text-xs font-bold uppercase tracking-wide text-slate-600">Colour</label>
                <div className="flex flex-wrap gap-2">
                  {COLORS.map((c) => (
                    <button key={c.id} type="button" onClick={() => setForm({ ...form, color: c.id })}
                      title={c.id}
                      className={`h-9 w-9 rounded-xl transition ${c.dot} ${
                        form.color === c.id ? 'ring-2 ring-slate-900 ring-offset-2' : 'opacity-60 hover:opacity-100'
                      }`} />
                  ))}
                </div>
              </div>

              <label className="flex w-fit cursor-pointer items-center gap-2 rounded-xl bg-slate-50 px-4 py-2.5 text-sm font-medium text-slate-700">
                <input type="checkbox" checked={form.is_pinned}
                  onChange={(e) => setForm({ ...form, is_pinned: e.target.checked })}
                  className="h-4 w-4 rounded accent-amber-500" />
                <Pin className="h-3.5 w-3.5 text-amber-600" /> Pin to top
              </label>
            </div>

            <div className="flex justify-end gap-3 border-t border-slate-200 px-6 py-4">
              <button type="button" onClick={() => setShowForm(false)}
                className="rounded-xl bg-slate-100 px-5 py-2.5 text-sm font-semibold text-slate-700 transition hover:bg-slate-200">
                Cancel
              </button>
              <button type="submit" disabled={saving}
                className="flex items-center gap-2 rounded-xl bg-emerald-600 px-6 py-2.5 text-sm font-bold text-white shadow transition hover:bg-emerald-700 disabled:opacity-60">
                {saving ? <Loader2 className="h-4 w-4 animate-spin" /> : <Save className="h-4 w-4" />}
                {editingId ? 'Save Changes' : 'Save Note'}
              </button>
            </div>
          </form>
        </div>
      )}
    </div>
  );
}



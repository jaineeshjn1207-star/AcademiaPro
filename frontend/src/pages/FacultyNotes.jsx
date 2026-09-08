import React, { useState, useEffect, useCallback } from 'react';
import api from '../api/axios';
import { useAuth } from '../context/AuthContext';
import { useToast } from '../components/ToastProvider';
import './notes-page.css';
import {
  BookOpen, PlusCircle, Search, Paperclip, Link2, Trash2, Pencil, Pin,
  X, Save, Eye, EyeOff, Download, FileText, Users, Building2, ClipboardList,
  AlertCircle, CheckCircle2, Loader2,
} from 'lucide-react';

const EMPTY_FORM = {
  title: '', subject: '', description: '', content: '',
  external_link: '', visibility: 'all', department: '',
  exam: '', is_published: true, is_pinned: false,
};

export default function FacultyNotes() {
  const { user } = useAuth();
  const { confirm } = useToast();
  const isFaculty = user?.user_type === 'faculty';

  const [notes, setNotes] = useState([]);
  const [exams, setExams] = useState([]);
  const [subjects, setSubjects] = useState([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState('');
  const [subjectFilter, setSubjectFilter] = useState('');

  const [showForm, setShowForm] = useState(false);
  const [editingId, setEditingId] = useState(null);
  const [form, setForm] = useState(EMPTY_FORM);
  const [file, setFile] = useState(null);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');
  const [toast, setToast] = useState('');
  const [expanded, setExpanded] = useState(null);

  const flash = (msg) => {
    setToast(msg);
    setTimeout(() => setToast(''), 3000);
  };

  const load = useCallback(async () => {
    try {
      const params = {};
      if (search.trim()) params.search = search.trim();
      if (subjectFilter) params.subject = subjectFilter;
      const res = await api.get('faculty-notes/', { params });
      setNotes(Array.isArray(res.data) ? res.data : res.data.results || []);
    } catch (err) {
      setError('Could not load notes.');
    } finally {
      setLoading(false);
    }
  }, [search, subjectFilter]);

  useEffect(() => {
    const t = setTimeout(load, search ? 350 : 0);
    return () => clearTimeout(t);
  }, [load, search]);

  useEffect(() => {
    api.get('notes/subjects/')
      .then((r) => setSubjects(r.data.faculty_subjects || []))
      .catch(() => {});
    if (isFaculty) {
      api.get('exams/').then((r) => setExams(r.data || [])).catch(() => {});
    }
  }, [isFaculty]);

  const openCreate = () => {
    setForm({ ...EMPTY_FORM, department: user?.department || '' });
    setFile(null);
    setEditingId(null);
    setError('');
    setShowForm(true);
  };

  const openEdit = (note) => {
    setForm({
      title: note.title || '', subject: note.subject || '',
      description: note.description || '', content: note.content || '',
      external_link: note.external_link || '', visibility: note.visibility || 'all',
      department: note.department || '', exam: note.exam || '',
      is_published: note.is_published, is_pinned: note.is_pinned,
    });
    setFile(null);
    setEditingId(note.id);
    setError('');
    setShowForm(true);
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!form.title.trim()) {
      setError('Title is required.');
      return;
    }
    setSaving(true);
    setError('');

    try {
      let payload;
      let headers;
      if (file) {
        payload = new FormData();
        Object.entries(form).forEach(([k, v]) => {
          if (k === 'exam' && !v) return;
          payload.append(k, typeof v === 'boolean' ? String(v) : v);
        });
        payload.append('attachment', file);
        headers = { 'Content-Type': 'multipart/form-data' };
      } else {
        payload = { ...form };
        if (!payload.exam) delete payload.exam;
      }

      if (editingId) {
        await api.patch(`faculty-notes/${editingId}/`, payload, { headers });
        flash('Note updated successfully.');
      } else {
        await api.post('faculty-notes/', payload, { headers });
        flash('Note published successfully.');
      }
      setShowForm(false);
      load();
    } catch (err) {
      const d = err.response?.data;
      setError(
        d?.detail ||
        (typeof d === 'object' ? Object.entries(d || {}).map(([k, v]) => `${k}: ${v}`).join(' | ') : '') ||
        'Failed to save the note.'
      );
    } finally {
      setSaving(false);
    }
  };

  const handleDelete = async (id) => {
    const ok = await confirm({
      title: 'Delete note permanently?',
      message: 'Students will lose access to this note and any attachment.',
      confirmText: 'Delete note',
      danger: true,
    });
    if (!ok) return;
    try {
      await api.delete(`faculty-notes/${id}/`);
      setNotes((n) => n.filter((x) => x.id !== id));
      flash('Note deleted.');
    } catch {
      flash('Could not delete this note.');
    }
  };

  const togglePin = async (note) => {
    try {
      await api.patch(`faculty-notes/${note.id}/`, { is_pinned: !note.is_pinned });
      load();
    } catch {
      flash('Could not update the note.');
    }
  };

  const visibilityBadge = (v) => {
    const map = {
      all: { icon: Users, label: 'All Students', cls: 'bg-emerald-50 text-emerald-700 border-emerald-200' },
      department: { icon: Building2, label: 'Department', cls: 'bg-blue-50 text-blue-700 border-blue-200' },
      exam: { icon: ClipboardList, label: 'Exam Candidates', cls: 'bg-purple-50 text-purple-700 border-purple-200' },
    };
    const { icon: Icon, label, cls } = map[v] || map.all;
    return (
      <span className={`inline-flex items-center gap-1 rounded-full border px-2 py-0.5 text-[11px] font-semibold ${cls}`}>
        <Icon className="h-3 w-3" /> {label}
      </span>
    );
  };

  if (loading) {
    return (
      <div className="flex min-h-[60vh] items-center justify-center">
        <Loader2 className="h-10 w-10 animate-spin text-blue-600" />
      </div>
    );
  }

  return (
    <div className="app-page notes-page faculty-notes-page">
      {toast && (
        <div className="fixed right-6 top-6 z-50 flex items-center gap-2 rounded-xl bg-slate-900 px-4 py-3 text-sm font-medium text-white shadow-2xl">
          <CheckCircle2 className="h-4 w-4 text-emerald-400" /> {toast}
        </div>
      )}

      {/* Header */}
      <div className="rounded-2xl border border-slate-200 bg-white p-6 text-slate-900 shadow-sm sm:p-8">
        <div className="flex flex-col justify-between gap-6 md:flex-row md:items-center">
          <div>
            <span className="rounded-full border border-indigo-200 bg-indigo-100 px-3 py-1 text-xs font-semibold uppercase tracking-wider text-indigo-700">
              {isFaculty ? 'Study Material Management' : 'Study Material'}
            </span>
            <h1 className="mt-2 flex items-center gap-3 text-3xl font-extrabold tracking-tight">
              <BookOpen className="h-8 w-8 text-indigo-400" />
              Faculty Notes
            </h1>
            <p className="mt-1 text-sm text-slate-500">
              {isFaculty
                ? 'Upload lecture notes, guides and reference material for your students.'
                : 'Study material and guides shared by your faculty.'}
            </p>
          </div>
          {isFaculty && (
            <button
              onClick={openCreate}
              className="flex items-center justify-center gap-2 rounded-xl bg-indigo-600 px-6 py-3.5 font-bold text-white shadow-lg transition hover:bg-indigo-700"
            >
              <PlusCircle className="h-5 w-5" /> Upload New Note
            </button>
          )}
        </div>
      </div>

      {/* Filters */}
      <div className="flex flex-col gap-3 sm:flex-row">
        <div className="relative flex-1">
          <Search className="absolute left-3.5 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400" />
          <input
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Search notes by title, subject or content..."
            className="w-full rounded-xl border border-slate-300 bg-white py-3 pl-11 pr-4 text-sm outline-none transition focus:border-indigo-500 focus:ring-2 focus:ring-indigo-100"
          />
        </div>
        <select
          value={subjectFilter}
          onChange={(e) => setSubjectFilter(e.target.value)}
          className="rounded-xl border border-slate-300 bg-white px-4 py-3 text-sm outline-none focus:border-indigo-500 sm:w-56"
        >
          <option value="">All Subjects</option>
          {subjects.map((s) => <option key={s} value={s}>{s}</option>)}
        </select>
      </div>

      {/* Notes list */}
      {notes.length === 0 ? (
        <div className="rounded-3xl border border-slate-200 bg-white p-16 text-center">
          <FileText className="mx-auto mb-3 h-12 w-12 text-slate-300" />
          <p className="font-semibold text-slate-700">No notes found.</p>
          <p className="mt-1 text-xs text-slate-400">
            {isFaculty ? 'Upload your first note to share it with students.' : 'Your faculty has not published any notes yet.'}
          </p>
        </div>
      ) : (
        <div className="space-y-4">
          {notes.map((note) => (
            <article
              key={note.id}
              className={`overflow-hidden rounded-2xl border bg-white shadow-sm transition hover:shadow-md ${
                note.is_pinned ? 'border-amber-300 ring-1 ring-amber-100' : 'border-slate-200'
              }`}
            >
              <div className="p-6">
                <div className="flex flex-wrap items-start justify-between gap-4">
                  <div className="min-w-0 flex-1">
                    <div className="mb-2 flex flex-wrap items-center gap-2">
                      {note.is_pinned && (
                        <span className="inline-flex items-center gap-1 rounded-full bg-amber-100 px-2 py-0.5 text-[11px] font-bold text-amber-800">
                          <Pin className="h-3 w-3" /> PINNED
                        </span>
                      )}
                      {note.subject && (
                        <span className="rounded-full bg-slate-100 px-2.5 py-0.5 text-[12px] font-semibold text-slate-700">
                          {note.subject}
                        </span>
                      )}
                      {isFaculty && visibilityBadge(note.visibility)}
                      {isFaculty && !note.is_published && (
                        <span className="inline-flex items-center gap-1 rounded-full bg-slate-200 px-2 py-0.5 text-[11px] font-bold text-slate-600">
                          <EyeOff className="h-3 w-3" /> DRAFT
                        </span>
                      )}
                    </div>

                    <h3 className="text-lg font-bold leading-snug text-slate-900">{note.title}</h3>
                    {note.description && (
                      <p className="mt-1 text-sm text-slate-600">{note.description}</p>
                    )}

                    <div className="mt-3 flex flex-wrap items-center gap-x-4 gap-y-1 text-[12px] text-slate-500">
                      <span>By <b className="text-slate-700">{note.uploaded_by_name}</b></span>
                      <span>{new Date(note.created_at).toLocaleDateString('en-IN', { day: 'numeric', month: 'short', year: 'numeric' })}</span>
                      {note.exam_title && <span className="text-purple-600">Linked: {note.exam_title}</span>}
                    </div>
                  </div>

                  {isFaculty && (
                    <div className="flex items-center gap-1.5">
                      <button onClick={() => togglePin(note)} title={note.is_pinned ? 'Unpin' : 'Pin'}
                        className={`rounded-lg p-2 transition ${note.is_pinned ? 'bg-amber-100 text-amber-700' : 'text-slate-400 hover:bg-slate-100'}`}>
                        <Pin className="h-4 w-4" />
                      </button>
                      <button onClick={() => openEdit(note)} title="Edit"
                        className="rounded-lg p-2 text-slate-400 transition hover:bg-blue-50 hover:text-blue-600">
                        <Pencil className="h-4 w-4" />
                      </button>
                      <button onClick={() => handleDelete(note.id)} title="Delete"
                        className="rounded-lg p-2 text-slate-400 transition hover:bg-rose-50 hover:text-rose-600">
                        <Trash2 className="h-4 w-4" />
                      </button>
                    </div>
                  )}
                </div>

                {/* Attachments / links */}
                {(note.attachment_url || note.external_link) && (
                  <div className="mt-4 flex flex-wrap gap-2">
                    {note.attachment_url && (
                      <a href={note.attachment_url} target="_blank" rel="noreferrer"
                        className="inline-flex items-center gap-2 rounded-xl border border-slate-200 bg-slate-50 px-3 py-2 text-xs font-semibold text-slate-700 transition hover:bg-slate-100">
                        <Download className="h-3.5 w-3.5 text-blue-600" />
                        {note.attachment_name || 'Download attachment'}
                      </a>
                    )}
                    {note.external_link && (
                      <a href={note.external_link} target="_blank" rel="noreferrer"
                        className="inline-flex items-center gap-2 rounded-xl border border-blue-200 bg-blue-50 px-3 py-2 text-xs font-semibold text-blue-700 transition hover:bg-blue-100">
                        <Link2 className="h-3.5 w-3.5" /> External resource
                      </a>
                    )}
                  </div>
                )}

                {note.content && (
                  <>
                    <button
                      onClick={() => setExpanded(expanded === note.id ? null : note.id)}
                      className="mt-4 inline-flex items-center gap-1.5 text-xs font-bold text-indigo-600 hover:text-indigo-800"
                    >
                      <Eye className="h-3.5 w-3.5" />
                      {expanded === note.id ? 'Hide full note' : 'Read full note'}
                    </button>
                    {expanded === note.id && (
                      <div className="mt-3 rounded-2xl border border-slate-200 bg-slate-50 p-5">
                        <pre className="whitespace-pre-wrap break-words font-sans text-sm leading-relaxed text-slate-800">
                          {note.content}
                        </pre>
                      </div>
                    )}
                  </>
                )}
              </div>
            </article>
          ))}
        </div>
      )}

      {/* Create / Edit modal */}
      {showForm && isFaculty && (
        <div className="fixed inset-0 z-50 flex items-start justify-center overflow-y-auto bg-black/60 p-4 backdrop-blur-sm">
          <form onSubmit={handleSubmit} className="my-8 w-full max-w-2xl rounded-3xl bg-white shadow-2xl">
            <div className="flex items-center justify-between border-b border-slate-200 px-6 py-5">
              <h3 className="text-lg font-bold text-slate-900">
                {editingId ? 'Edit Note' : 'Upload New Note'}
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
                <input value={form.title} onChange={(e) => setForm({ ...form, title: e.target.value })}
                  placeholder="e.g. Unit 3 — Dynamic Programming"
                  className="w-full rounded-xl border border-slate-300 px-4 py-2.5 text-sm outline-none focus:border-indigo-500 focus:ring-2 focus:ring-indigo-100" />
              </div>

              <div className="grid gap-4 sm:grid-cols-2">
                <div>
                  <label className="mb-1.5 block text-xs font-bold uppercase tracking-wide text-slate-600">Subject</label>
                  <input value={form.subject} onChange={(e) => setForm({ ...form, subject: e.target.value })}
                    placeholder="Algorithms" list="subject-suggestions"
                    className="w-full rounded-xl border border-slate-300 px-4 py-2.5 text-sm outline-none focus:border-indigo-500" />
                  <datalist id="subject-suggestions">
                    {subjects.map((s) => <option key={s} value={s} />)}
                  </datalist>
                </div>
                <div>
                  <label className="mb-1.5 block text-xs font-bold uppercase tracking-wide text-slate-600">Visibility</label>
                  <select value={form.visibility} onChange={(e) => setForm({ ...form, visibility: e.target.value })}
                    className="w-full rounded-xl border border-slate-300 px-4 py-2.5 text-sm outline-none focus:border-indigo-500">
                    <option value="all">All Students</option>
                    <option value="department">My Department Only</option>
                    <option value="exam">Specific Exam Candidates</option>
                  </select>
                </div>
              </div>

              {form.visibility === 'department' && (
                <div>
                  <label className="mb-1.5 block text-xs font-bold uppercase tracking-wide text-slate-600">Department</label>
                  <input value={form.department} onChange={(e) => setForm({ ...form, department: e.target.value })}
                    placeholder="Computer Science & Engineering"
                    className="w-full rounded-xl border border-slate-300 px-4 py-2.5 text-sm outline-none focus:border-indigo-500" />
                </div>
              )}

              {form.visibility === 'exam' && (
                <div>
                  <label className="mb-1.5 block text-xs font-bold uppercase tracking-wide text-slate-600">Exam</label>
                  <select value={form.exam} onChange={(e) => setForm({ ...form, exam: e.target.value })}
                    className="w-full rounded-xl border border-slate-300 px-4 py-2.5 text-sm outline-none focus:border-indigo-500">
                    <option value="">Select an exam...</option>
                    {exams.map((ex) => <option key={ex.id} value={ex.id}>{ex.title}</option>)}
                  </select>
                </div>
              )}

              <div>
                <label className="mb-1.5 block text-xs font-bold uppercase tracking-wide text-slate-600">Short Description</label>
                <input value={form.description} onChange={(e) => setForm({ ...form, description: e.target.value })}
                  placeholder="One line summary shown in the list"
                  className="w-full rounded-xl border border-slate-300 px-4 py-2.5 text-sm outline-none focus:border-indigo-500" />
              </div>

              <div>
                <label className="mb-1.5 block text-xs font-bold uppercase tracking-wide text-slate-600">Note Content</label>
                <textarea value={form.content} onChange={(e) => setForm({ ...form, content: e.target.value })}
                  rows={10} placeholder="Write the full study material here..."
                  className="w-full rounded-xl border border-slate-300 px-4 py-3 font-mono text-sm leading-relaxed outline-none focus:border-indigo-500" />
              </div>

              <div className="grid gap-4 sm:grid-cols-2">
                <div>
                  <label className="mb-1.5 block text-xs font-bold uppercase tracking-wide text-slate-600">
                    <Paperclip className="mr-1 inline h-3.5 w-3.5" /> Attachment (PDF / DOC / any)
                  </label>
                  <input type="file" onChange={(e) => setFile(e.target.files?.[0] || null)}
                    className="w-full rounded-xl border border-slate-300 px-3 py-2 text-xs file:mr-3 file:rounded-lg file:border-0 file:bg-indigo-50 file:px-3 file:py-1.5 file:text-xs file:font-semibold file:text-indigo-700" />
                </div>
                <div>
                  <label className="mb-1.5 block text-xs font-bold uppercase tracking-wide text-slate-600">
                    <Link2 className="mr-1 inline h-3.5 w-3.5" /> External Link
                  </label>
                  <input type="url" value={form.external_link} onChange={(e) => setForm({ ...form, external_link: e.target.value })}
                    placeholder="https://..."
                    className="w-full rounded-xl border border-slate-300 px-4 py-2.5 text-sm outline-none focus:border-indigo-500" />
                </div>
              </div>

              <div className="flex flex-wrap gap-6 rounded-xl bg-slate-50 p-4">
                <label className="flex cursor-pointer items-center gap-2 text-sm font-medium text-slate-700">
                  <input type="checkbox" checked={form.is_published}
                    onChange={(e) => setForm({ ...form, is_published: e.target.checked })}
                    className="h-4 w-4 rounded accent-indigo-600" />
                  Publish immediately
                </label>
                <label className="flex cursor-pointer items-center gap-2 text-sm font-medium text-slate-700">
                  <input type="checkbox" checked={form.is_pinned}
                    onChange={(e) => setForm({ ...form, is_pinned: e.target.checked })}
                    className="h-4 w-4 rounded accent-amber-500" />
                  Pin to top
                </label>
              </div>
            </div>

            <div className="flex justify-end gap-3 border-t border-slate-200 px-6 py-4">
              <button type="button" onClick={() => setShowForm(false)}
                className="rounded-xl bg-slate-100 px-5 py-2.5 text-sm font-semibold text-slate-700 transition hover:bg-slate-200">
                Cancel
              </button>
              <button type="submit" disabled={saving}
                className="flex items-center gap-2 rounded-xl bg-indigo-600 px-6 py-2.5 text-sm font-bold text-white shadow transition hover:bg-indigo-700 disabled:opacity-60">
                {saving ? <Loader2 className="h-4 w-4 animate-spin" /> : <Save className="h-4 w-4" />}
                {editingId ? 'Save Changes' : 'Publish Note'}
              </button>
            </div>
          </form>
        </div>
      )}
    </div>
  );
}



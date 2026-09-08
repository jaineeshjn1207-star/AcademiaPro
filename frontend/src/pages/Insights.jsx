import React, { useEffect, useState } from 'react';
import { Navigate } from 'react-router-dom';
import { BarChart3, Loader2 } from 'lucide-react';
import api from '../api/axios';

export default function Insights() {
  const [exams, setExams] = useState([]); const [selected, setSelected] = useState(''); const [loading, setLoading] = useState(true);
  useEffect(() => { (async () => { try { const res = await api.get('results/'); const rows = res.data.results || []; const unique = [...new Map(rows.map((row) => [row.exam_id, row])).values()]; setExams(unique); setSelected(String(unique[0]?.exam_id || '')); } finally { setLoading(false); } })(); }, []);
  if (loading) return <div className="flex min-h-[50vh] items-center justify-center"><Loader2 className="animate-spin text-blue-600" /></div>;
  if (selected) return <Navigate to={`/exam/${selected}/analytics`} replace />;
  return <section className="app-page py-16 text-center"><BarChart3 className="mx-auto h-10 w-10 text-slate-300" /><h1 className="mt-4 text-xl font-bold">No submitted results yet</h1><p className="mt-2 text-sm text-slate-500">Insights open automatically after your most recently submitted result is released.</p></section>;
}

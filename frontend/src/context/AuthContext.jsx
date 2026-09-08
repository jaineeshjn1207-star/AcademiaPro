import React, { createContext, useState, useEffect, useContext, useCallback } from 'react';
import api from '../api/axios';

const AuthContext = createContext(null);

const read = (key) => {
  try {
    const raw = localStorage.getItem(key);
    return raw && raw !== 'undefined' ? JSON.parse(raw) : null;
  } catch {
    localStorage.removeItem(key);
    return null;
  }
};

export const AuthProvider = ({ children }) => {
  const [user, setUser] = useState(() => read('user'));
  const [activeExam, setActiveExamState] = useState(() => read('active_exam'));
  const [loading, setLoading] = useState(true);

  const logout = useCallback(() => {
    ['access_token', 'refresh_token', 'user', 'active_exam'].forEach((k) =>
      localStorage.removeItem(k)
    );
    setUser(null);
    setActiveExamState(null);
  }, []);

  const setActiveExam = useCallback((exam) => {
    if (exam) localStorage.setItem('active_exam', JSON.stringify(exam));
    else localStorage.removeItem('active_exam');
    setActiveExamState(exam);
  }, []);

  // Validate the stored session on boot
  useEffect(() => {
    let cancelled = false;
    (async () => {
      const token = localStorage.getItem('access_token');
      if (!token) {
        if (!cancelled) setLoading(false);
        return;
      }
      try {
        const res = await api.get('auth/me/');
        if (cancelled) return;
        setUser(res.data);
        localStorage.setItem('user', JSON.stringify(res.data));
      } catch {
        if (!cancelled) logout();
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => { cancelled = true; };
  }, [logout]);

  const persistSession = (data) => {
    const { access, refresh, user: userData, exam } = data;
    localStorage.setItem('access_token', access);
    localStorage.setItem('refresh_token', refresh);
    localStorage.setItem('user', JSON.stringify(userData));
    setUser(userData);
    if (exam) setActiveExam(exam);
    return data;
  };

  const loginUnified = async (username, password) =>
    persistSession((await api.post('auth/login/', { username, password })).data);

  const forcePasswordChange = async (username, current_password, new_password) =>
    (await api.post('auth/force-password-change/', { username, current_password, new_password })).data;

  const loginStudentNormal = async (username, password) =>
    persistSession((await api.post('auth/student/login/', { username, password })).data);

  const loginFaculty = async (username, password) =>
    persistSession((await api.post('auth/faculty/login/', { username, password })).data);

  const value = {
    user, activeExam, setActiveExam,
    loginUnified, forcePasswordChange, loginStudentNormal, loginFaculty, logout, loading,
    isFaculty: user?.user_type === 'faculty',
    isStudent: user?.user_type === 'student',
    isAdmin: user?.user_type === 'admin',
  };

  return (
    <AuthContext.Provider value={value}>
      {loading ? (
        <div className="flex min-h-screen items-center justify-center bg-slate-50 dark:bg-slate-950">
          <div className="space-y-3 text-center">
            <div className="mx-auto h-10 w-10 animate-spin rounded-full border-b-2 border-t-2 border-blue-600 dark:border-blue-400" />
            <p className="text-sm font-medium text-slate-500 dark:text-slate-300">Restoring your session…</p>
          </div>
        </div>
      ) : (
        children
      )}
    </AuthContext.Provider>
  );
};

export const useAuth = () => {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error('useAuth must be used inside an AuthProvider');
  return ctx;
};



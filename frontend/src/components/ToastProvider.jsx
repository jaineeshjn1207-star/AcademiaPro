import React, { createContext, useCallback, useContext, useMemo, useRef, useState } from 'react';
import { AlertTriangle, CheckCircle2, Info, X, XCircle } from 'lucide-react';
import './feedback.css';

const ToastContext = createContext(null);

const toneMap = {
  success: {
    icon: CheckCircle2,
    cls: 'border-emerald-200 bg-emerald-50 text-emerald-900',
    iconCls: 'text-emerald-600',
  },
  error: {
    icon: XCircle,
    cls: 'border-rose-200 bg-rose-50 text-rose-900',
    iconCls: 'text-rose-600',
  },
  warning: {
    icon: AlertTriangle,
    cls: 'border-amber-200 bg-amber-50 text-amber-900',
    iconCls: 'text-amber-600',
  },
  info: {
    icon: Info,
    cls: 'border-blue-200 bg-blue-50 text-blue-900',
    iconCls: 'text-blue-600',
  },
};

export function ToastProvider({ children }) {
  const [toasts, setToasts] = useState([]);
  const [dialog, setDialog] = useState(null);
  const nextId = useRef(1);

  const dismiss = useCallback((id) => {
    setToasts((items) => items.filter((item) => item.id !== id));
  }, []);

  const toast = useCallback(({ type = 'info', title, message, duration = 4500 }) => {
    const id = nextId.current++;
    const item = { id, type, title, message };
    setToasts((items) => [item, ...items].slice(0, 5));
    if (duration > 0) window.setTimeout(() => dismiss(id), duration);
    return id;
  }, [dismiss]);

  const confirm = useCallback((options = {}) => new Promise((resolve) => {
    setDialog({
      title: options.title || 'Confirm action',
      message: options.message || 'Are you sure you want to continue?',
      confirmText: options.confirmText || 'Confirm',
      cancelText: options.cancelText || 'Cancel',
      danger: Boolean(options.danger),
      resolve,
    });
  }), []);

  const closeDialog = useCallback((answer) => {
    setDialog((current) => {
      current?.resolve?.(answer);
      return null;
    });
  }, []);

  const value = useMemo(() => ({ toast, confirm, dismiss }), [toast, confirm, dismiss]);

  return (
    <ToastContext.Provider value={value}>
      {children}

      <div className="feedback-toasts" aria-live="polite">
        {toasts.map((item) => {
          const tone = toneMap[item.type] || toneMap.info;
          const Icon = tone.icon;
          return (
            <div
              key={item.id}
              role="status"
              className={`feedback-toast is-${item.type || 'info'}`}
            >
              <div className="feedback-toast-inner">
                <Icon className="feedback-toast-icon" />
                <div className="feedback-toast-copy">
                  {item.title && <div>{item.title}</div>}
                  {item.message && <p>{item.message}</p>}
                </div>
                <button
                  type="button"
                  onClick={() => dismiss(item.id)}
                  aria-label="Dismiss notification"
                  className="feedback-dismiss"
                >
                  <X className="h-4 w-4" />
                </button>
              </div>
            </div>
          );
        })}
      </div>

      {dialog && (
        <div className="feedback-dialog-backdrop" role="dialog" aria-modal="true">
          <div className="feedback-dialog">
            <div className="feedback-dialog-main">
              <div className={`feedback-dialog-icon${dialog.danger ? ' is-danger' : ''}`}>
                {dialog.danger ? <AlertTriangle className="h-5 w-5" /> : <Info className="h-5 w-5" />}
              </div>
              <div className="feedback-dialog-copy">
                <h2>{dialog.title}</h2>
                <p>{dialog.message}</p>
              </div>
            </div>
            <div className="feedback-dialog-actions">
              <button
                type="button"
                onClick={() => closeDialog(false)}
                className="feedback-dialog-cancel"
              >
                {dialog.cancelText}
              </button>
              <button
                type="button"
                onClick={() => closeDialog(true)}
                className={`feedback-dialog-confirm${dialog.danger ? ' is-danger' : ''}`}
              >
                {dialog.confirmText}
              </button>
            </div>
          </div>
        </div>
      )}
    </ToastContext.Provider>
  );
}

export function useToast() {
  const ctx = useContext(ToastContext);
  if (!ctx) throw new Error('useToast must be used within ToastProvider');
  return ctx;
}



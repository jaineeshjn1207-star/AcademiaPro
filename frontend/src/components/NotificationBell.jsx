import React, { useEffect, useRef, useState, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { Bell, CheckCheck } from 'lucide-react';
import api from '../api/axios';

const TYPE_TONE = {
  exam: 'is-exam',
  result: 'is-result',
  proctor: 'is-proctor',
  appeal: 'is-appeal',
  system: 'is-system',
};

function timeAgo(iso) {
  const diffMs = Date.now() - new Date(iso).getTime();
  const mins = Math.round(diffMs / 60000);
  if (mins < 1) return 'just now';
  if (mins < 60) return `${mins}m ago`;
  const hours = Math.round(mins / 60);
  if (hours < 24) return `${hours}h ago`;
  const days = Math.round(hours / 24);
  return `${days}d ago`;
}

/**
 * Polls /notifications/ for the signed-in user and renders a bell with an
 * unread badge + dropdown. Marks everything read when opened.
 */
export default function NotificationBell() {
  const [items, setItems] = useState([]);
  const [unread, setUnread] = useState(0);
  const [open, setOpen] = useState(false);
  const [loading, setLoading] = useState(false);
  const popRef = useRef(null);
  const navigate = useNavigate();

  const fetchNotifications = useCallback(async () => {
    try {
      const { data } = await api.get('/notifications/', { params: { limit: 20 } });
      setItems(data.notifications || []);
      setUnread(data.unread_count || 0);
    } catch {
      // Silent: notifications are a convenience layer, not critical path.
    }
  }, []);

  useEffect(() => {
    fetchNotifications();
    const id = window.setInterval(fetchNotifications, 45000);
    return () => window.clearInterval(id);
  }, [fetchNotifications]);

  useEffect(() => {
    if (!open) return undefined;
    const onClick = (e) => {
      if (popRef.current && !popRef.current.contains(e.target)) setOpen(false);
    };
    document.addEventListener('mousedown', onClick);
    return () => document.removeEventListener('mousedown', onClick);
  }, [open]);

  const openPanel = async () => {
    const next = !open;
    setOpen(next);
    if (next && unread > 0) {
      setLoading(true);
      try {
        await api.patch('/notifications/', {});
        setUnread(0);
        setItems((prev) => prev.map((n) => ({ ...n, is_read: true })));
      } catch {
        // ignore
      } finally {
        setLoading(false);
      }
    }
  };

  const handleItemClick = (n) => {
    setOpen(false);
    if (n.link) navigate(n.link);
  };

  return (
    <div className="workspace-notif" ref={popRef}>
      <button
        type="button"
        className="workspace-icon-button"
        onClick={openPanel}
        aria-label={unread > 0 ? `${unread} unread notifications` : 'Notifications'}
        aria-expanded={open}
        aria-haspopup="menu"
        title="Notifications"
      >
        <Bell size={18} />
        {unread > 0 && <span className="workspace-notif-badge">{unread > 9 ? '9+' : unread}</span>}
      </button>

      {open && (
        <div className="workspace-notif-panel" role="menu">
          <div className="workspace-notif-panel-head">
            <span>Notifications</span>
            {loading && <CheckCheck size={14} className="workspace-notif-syncing" />}
          </div>
          {items.length === 0 ? (
            <p className="workspace-notif-empty">You're all caught up.</p>
          ) : (
            <ul>
              {items.map((n) => (
                <li key={n.id}>
                  <button
                    type="button"
                    className={`workspace-notif-item ${TYPE_TONE[n.type] || 'is-system'}${n.is_read ? '' : ' is-unread'}`}
                    onClick={() => handleItemClick(n)}
                  >
                    <strong>{n.title}</strong>
                    {n.body && <span>{n.body}</span>}
                    <time>{timeAgo(n.created_at)}</time>
                  </button>
                </li>
              ))}
            </ul>
          )}
        </div>
      )}
    </div>
  );
}



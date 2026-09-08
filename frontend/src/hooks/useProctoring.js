import { useEffect, useRef, useCallback, useState } from 'react';

/**
 * useProctoring — enforces exam-room lockdown.
 *
 * Responsibilities:
 *   1. Request and hold fullscreen; re-arm the moment the user escapes.
 *   2. Swallow every keyboard shortcut that could be used to cheat or escape.
 *   3. Block copy / cut / paste / right-click / text selection / drag.
 *   4. Detect tab-switching, window blur and page-hide.
 *   5. Report every violation to the server and auto-submit at the limit.
 *
 * Browsers refuse to enter fullscreen outside a user gesture, so the exam room
 * shows an explicit "Enter secure mode" gate first; `requestFullscreen()`
 * returned from this hook is what that button calls.
 */

const BLOCKED_SINGLE_KEYS = new Set([
  'F1', 'F3', 'F5', 'F6', 'F7', 'F10', 'F11', 'F12',
  'PrintScreen', 'ContextMenu',
]);

export default function useProctoring({
  enabled = true,
  enforceFullscreenActive = true,
  reportToServer = true,
  config = {},
  onViolation,
  onAutoSubmit,
  isSubmitting = false,
}) {
  const {
    enforce_fullscreen: enforceFullscreen = true,
    block_shortcuts: blockShortcuts = true,
    block_copy_paste: blockCopyPaste = true,
  } = config;

  const [isFullscreen, setIsFullscreen] = useState(false);
  const [showWarning, setShowWarning] = useState(false);
  const [warningMessage, setWarningMessage] = useState('');

  // Refs keep the latest values inside long-lived native listeners
  const enabledRef = useRef(enabled);
  const submittingRef = useRef(isSubmitting);
  const onViolationRef = useRef(onViolation);
  const onAutoSubmitRef = useRef(onAutoSubmit);
  const reportToServerRef = useRef(reportToServer);
  const lastEventAt = useRef({});

  useEffect(() => { reportToServerRef.current = reportToServer; }, [reportToServer]);
  useEffect(() => { enabledRef.current = enabled; }, [enabled]);
  useEffect(() => { submittingRef.current = isSubmitting; }, [isSubmitting]);
  useEffect(() => { onViolationRef.current = onViolation; }, [onViolation]);
  useEffect(() => { onAutoSubmitRef.current = onAutoSubmit; }, [onAutoSubmit]);

  // ---------------------------------------------------------------- report
  /** Throttled violation reporter (same event type max once per 1.2s). */
  const report = useCallback((eventType, details = '', warn = true) => {
    if (!enabledRef.current || submittingRef.current) return;

    const now = Date.now();
    if (now - (lastEventAt.current[eventType] || 0) < 1200) return;
    lastEventAt.current[eventType] = now;

    if (warn) {
      setWarningMessage(details || 'Prohibited action detected.');
      setShowWarning(true);
      window.clearTimeout(report._t);
      report._t = window.setTimeout(() => setShowWarning(false), 4000);
    }

    // Before the student formally starts, block the action and warn them, but
    // don't record a violation against their attempt.
    if (reportToServerRef.current) {
      onViolationRef.current?.(eventType, details);
    }
  }, []);

  // ------------------------------------------------------------ fullscreen
  const requestFullscreen = useCallback(async () => {
    const el = document.documentElement;
    try {
      if (el.requestFullscreen) await el.requestFullscreen({ navigationUI: 'hide' });
      else if (el.webkitRequestFullscreen) await el.webkitRequestFullscreen();
      else if (el.mozRequestFullScreen) await el.mozRequestFullScreen();
      else if (el.msRequestFullscreen) await el.msRequestFullscreen();
      return true;
    } catch (err) {
      console.warn('Fullscreen request rejected:', err);
      return false;
    }
  }, []);

  const exitFullscreen = useCallback(async () => {
    try {
      if (document.exitFullscreen && document.fullscreenElement) await document.exitFullscreen();
      else if (document.webkitExitFullscreen) await document.webkitExitFullscreen();
    } catch {
      /* ignore */
    }
  }, []);

  const fsElement = () =>
    document.fullscreenElement ||
    document.webkitFullscreenElement ||
    document.mozFullScreenElement ||
    document.msFullscreenElement;

  // --------------------------------------------------- fullscreen watchdog
  useEffect(() => {
    if (!enabled || !enforceFullscreen || !enforceFullscreenActive) return;

    const handleChange = () => {
      const active = Boolean(fsElement());
      setIsFullscreen(active);

      if (!active && enabledRef.current && !submittingRef.current) {
        report(
          'fullscreen_exit',
          'You exited fullscreen. This is recorded as a proctoring violation.'
        );
        // Re-arm: browsers block programmatic re-entry without a gesture, so the
        // exam room renders a blocking overlay whose button calls requestFullscreen.
        setTimeout(() => {
          if (enabledRef.current && !submittingRef.current && !fsElement()) {
            requestFullscreen();
          }
        }, 300);
      }
    };

    const events = [
      'fullscreenchange', 'webkitfullscreenchange',
      'mozfullscreenchange', 'MSFullscreenChange',
    ];
    events.forEach((e) => document.addEventListener(e, handleChange));
    setIsFullscreen(Boolean(fsElement()));

    return () => events.forEach((e) => document.removeEventListener(e, handleChange));
  }, [enabled, enforceFullscreen, enforceFullscreenActive, report, requestFullscreen]);

  // ------------------------------------------------------- keyboard lockdown
  useEffect(() => {
    if (!enabled || !blockShortcuts) return;

    const onKeyDown = (e) => {
      if (!enabledRef.current || submittingRef.current) return;

      const key = e.key || '';
      const upper = key.length === 1 ? key.toUpperCase() : key;
      const ctrl = e.ctrlKey || e.metaKey;
      const inEditor = e.target?.dataset?.examEditor === 'true';

      const kill = (type, msg) => {
        e.preventDefault();
        e.stopPropagation();
        report(type, msg);
        return false;
      };

      // --- Escape: never allow it to break fullscreen quietly -------------
      if (key === 'Escape' && enforceFullscreenActive) {
        e.preventDefault();
        e.stopPropagation();
        report('blocked_key', 'The Escape key is disabled during the examination.');
        return false;
      }

      // --- Function keys / PrintScreen ------------------------------------
      if (BLOCKED_SINGLE_KEYS.has(key)) {
        return kill('blocked_key', `The ${key} key is disabled during the examination.`);
      }

      // --- DevTools combos --------------------------------------------------
      if (
        (ctrl && e.shiftKey && ['I', 'J', 'C', 'K', 'E', 'M'].includes(upper)) ||
        (ctrl && upper === 'U')
      ) {
        return kill('devtools', 'Developer tools are disabled during the examination.');
      }

      // --- Window / tab management -----------------------------------------
      if (
        (ctrl && ['T', 'N', 'W', 'R', 'P', 'S', 'O', 'H', 'D', 'F', 'G'].includes(upper)) ||
        (ctrl && e.shiftKey && ['T', 'N', 'W'].includes(upper)) ||
        (ctrl && ['Tab', 'PageUp', 'PageDown'].includes(key)) ||
        (ctrl && /^[0-9]$/.test(key)) ||
        e.altKey && ['Tab', 'F4', 'ArrowLeft', 'ArrowRight'].includes(key) ||
        (e.metaKey && ['Tab', '`'].includes(key))
      ) {
        return kill('blocked_key', 'Switching tabs or windows is disabled during the examination.');
      }

      // --- Copy / cut / paste / select-all ----------------------------------
      if (blockCopyPaste && ctrl && ['C', 'X', 'V', 'A'].includes(upper)) {
        // The code editor is allowed internal select-all so students can
        // reformat their own work, but never copy/cut/paste.
        if (inEditor && upper === 'A') return;
        const map = { C: 'copy', X: 'cut', V: 'paste', A: 'blocked_key' };
        return kill(map[upper], `Ctrl+${upper} is disabled during the examination.`);
      }

      // --- Browser-level zoom is allowed; everything else with meta is not ---
      if (e.metaKey && ['Q', 'H', 'M'].includes(upper)) {
        return kill('blocked_key', 'This shortcut is disabled during the examination.');
      }
    };

    // Capture phase so we win before React handlers or the browser default.
    window.addEventListener('keydown', onKeyDown, true);
    return () => window.removeEventListener('keydown', onKeyDown, true);
  }, [enabled, blockShortcuts, blockCopyPaste, enforceFullscreenActive, report]);

  // ------------------------------------------------ clipboard / context menu
  useEffect(() => {
    if (!enabled) return;

    const onContextMenu = (e) => {
      if (!enabledRef.current) return;
      e.preventDefault();
      report('contextmenu', 'Right-click is disabled during the examination.', false);
    };

    const onCopy = (e) => {
      if (!enabledRef.current || !blockCopyPaste) return;
      e.preventDefault();
      report('copy', 'Copying exam content is not permitted.');
    };
    const onCut = (e) => {
      if (!enabledRef.current || !blockCopyPaste) return;
      e.preventDefault();
      report('cut', 'Cutting exam content is not permitted.');
    };
    const onPaste = (e) => {
      if (!enabledRef.current || !blockCopyPaste) return;
      e.preventDefault();
      report('paste', 'Pasting external content is not permitted.');
    };
    const onDragStart = (e) => {
      if (!enabledRef.current) return;
      e.preventDefault();
    };
    // Dropping text into the editor is a paste by another name.
    const onDrop = (e) => {
      if (!enabledRef.current || !blockCopyPaste) return;
      e.preventDefault();
      e.stopPropagation();
      report('paste', 'Dragging content into the exam is not permitted.');
    };
    const onDragOver = (e) => {
      if (!enabledRef.current || !blockCopyPaste) return;
      e.preventDefault();
    };
    // Catches Edit>Paste, middle-click paste and IME paste that bypass keydown.
    const onBeforeInput = (e) => {
      if (!enabledRef.current || !blockCopyPaste) return;
      const t = e.inputType || '';
      if (t === 'insertFromPaste' || t === 'insertFromDrop' || t === 'insertFromPasteAsQuotation') {
        e.preventDefault();
        e.stopPropagation();
        report('paste', 'Pasting external content is not permitted.');
      }
    };
    const onSelectStart = (e) => {
      if (!enabledRef.current || !blockCopyPaste) return;
      // Allow selection only inside the student's own answer editor.
      if (e.target?.dataset?.examEditor === 'true') return;
      if (['INPUT', 'TEXTAREA'].includes(e.target?.tagName)) return;
      e.preventDefault();
    };

    document.addEventListener('contextmenu', onContextMenu, true);
    document.addEventListener('copy', onCopy, true);
    document.addEventListener('cut', onCut, true);
    document.addEventListener('paste', onPaste, true);
    document.addEventListener('dragstart', onDragStart, true);
    document.addEventListener('drop', onDrop, true);
    document.addEventListener('dragover', onDragOver, true);
    document.addEventListener('beforeinput', onBeforeInput, true);
    document.addEventListener('selectstart', onSelectStart, true);

    return () => {
      document.removeEventListener('contextmenu', onContextMenu, true);
      document.removeEventListener('copy', onCopy, true);
      document.removeEventListener('cut', onCut, true);
      document.removeEventListener('paste', onPaste, true);
      document.removeEventListener('dragstart', onDragStart, true);
      document.removeEventListener('drop', onDrop, true);
      document.removeEventListener('dragover', onDragOver, true);
      document.removeEventListener('beforeinput', onBeforeInput, true);
      document.removeEventListener('selectstart', onSelectStart, true);
    };
  }, [enabled, blockCopyPaste, report]);

  // ------------------------------------------- tab switch / focus detection
  useEffect(() => {
    if (!enabled || !enforceFullscreenActive) return;

    const onVisibility = () => {
      if (document.hidden && enabledRef.current && !submittingRef.current) {
        report('tab_switch', 'You switched away from the exam tab. This is recorded.');
      }
    };
    const onBlur = () => {
      if (enabledRef.current && !submittingRef.current) {
        report('blur', 'The exam window lost focus. This is recorded.');
      }
    };
    const onBeforeUnload = (e) => {
      if (!enabledRef.current || submittingRef.current) return;
      e.preventDefault();
      e.returnValue = 'Leaving now will end your examination. Are you sure?';
      return e.returnValue;
    };

    document.addEventListener('visibilitychange', onVisibility);
    window.addEventListener('blur', onBlur);
    window.addEventListener('beforeunload', onBeforeUnload);

    return () => {
      document.removeEventListener('visibilitychange', onVisibility);
      window.removeEventListener('blur', onBlur);
      window.removeEventListener('beforeunload', onBeforeUnload);
    };
  }, [enabled, enforceFullscreenActive, report]);

  // ------------------------------------------------ block browser back nav
  useEffect(() => {
    if (!enabled || !enforceFullscreenActive) return;
    window.history.pushState(null, '', window.location.href);
    const onPopState = () => {
      if (!enabledRef.current || submittingRef.current) return;
      window.history.pushState(null, '', window.location.href);
      report('blocked_key', 'Navigating away from the exam is disabled.');
    };
    window.addEventListener('popstate', onPopState);
    return () => window.removeEventListener('popstate', onPopState);
  }, [enabled, enforceFullscreenActive, report]);

  return {
    isFullscreen,
    requestFullscreen,
    exitFullscreen,
    showWarning,
    warningMessage,
    dismissWarning: () => setShowWarning(false),
    reportViolation: report,
  };
}



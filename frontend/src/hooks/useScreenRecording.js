import { useCallback, useEffect, useRef, useState } from 'react';
import api from '../api/axios';

const FOCUS_LOSS_EVENT_TYPE = 'blur';
const TAB_SWITCH_EVENT_TYPE = 'tab_switch';

const getRecorderMimeType = () => {
  if (typeof MediaRecorder === 'undefined') return '';
  if (MediaRecorder.isTypeSupported('video/webm;codecs=vp8')) return 'video/webm;codecs=vp8';
  if (MediaRecorder.isTypeSupported('video/webm')) return 'video/webm';
  return '';
};

/**
 * Screen sharing + incident recording for proctoring evidence.
 *
 * We DO NOT upload clips for every violation anymore. Faculty asked for clips
 * only when the student loses focus or switches tabs/windows.
 *
 * To avoid empty/unplayable WebM files, each blur/tab-switch incident gets
 * its own MediaRecorder instance. Starting a fresh recorder on the already
 * approved screen-share stream creates a valid WebM file with its own header.
 * The recorder starts when the student leaves and stops/uploads when the student
 * returns, so the full middle period is captured in one playable clip.
 */
export default function useScreenRecording({ examId, enabled = true }) {
  const streamRef = useRef(null);
  const incidentRecorderRef = useRef(null);
  const activeIncidentRef = useRef(null);
  const incidentSeqRef = useRef(0);
  const [isRecording, setIsRecording] = useState(false);
  const [error, setError] = useState('');

  const uploadBlob = useCallback(async (blob, eventType, details, filenamePrefix = eventType) => {
    // Avoid saving empty/near-empty files. A real blur WebM should be
    // much larger than this; tiny files usually render as 0:00 clips.
    if (!blob || blob.size < 25 * 1024) return false;

    const now = Date.now();
    const form = new FormData();
    form.append('event_type', eventType);
    form.append('details', details || 'Screen recording evidence.');
    form.append('clip', blob, `${filenamePrefix}-${now}.webm`);

    try {
      await api.post(`exams/${examId}/proctor-recording/`, form);
      return true;
    } catch (err) {
      console.warn('Could not upload screen recording clip:', err);
      return false;
    }
  }, [examId]);

  const discardActiveIncident = useCallback(() => {
    const incident = activeIncidentRef.current;
    activeIncidentRef.current = null;
    const recorder = incident?.recorder || incidentRecorderRef.current;
    incidentRecorderRef.current = null;
    if (incident) incident.discard = true;
    try {
      if (recorder && recorder.state !== 'inactive') recorder.stop();
    } catch { /* ignore */ }
  }, []);

  const stopRecording = useCallback(() => {
    discardActiveIncident();
    if (streamRef.current) {
      streamRef.current.getTracks().forEach((t) => t.stop());
      streamRef.current = null;
    }
    setIsRecording(false);
  }, [discardActiveIncident]);

  const startRecording = useCallback(async (requiredOverride) => {
    const required = requiredOverride !== undefined ? requiredOverride : enabled;
    if (!required) return true;
    if (streamRef.current) return true;

    setError('');

    if (!navigator.mediaDevices?.getDisplayMedia) {
      setError('This browser does not support screen recording. Use a recent Chrome/Edge/Firefox browser and allow screen sharing.');
      return false;
    }
    if (typeof MediaRecorder === 'undefined' || !getRecorderMimeType()) {
      setError('This browser does not support exam screen recording. Use a recent Chrome or Edge browser.');
      return false;
    }

    try {
      const stream = await navigator.mediaDevices.getDisplayMedia({
        video: {
          displaySurface: 'monitor',
          frameRate: { ideal: 10, max: 15 },
          width: { max: 1920 },
          height: { max: 1080 },
        },
        audio: false,
        monitorTypeSurfaces: 'include',
        selfBrowserSurface: 'exclude',
        surfaceSwitching: 'exclude',
      });

      const track = stream.getVideoTracks()[0];
      const surface = track?.getSettings?.().displaySurface;
      if (surface !== 'monitor') {
        stream.getTracks().forEach((t) => t.stop());
        setError('Only Entire Screen sharing is allowed. You selected a browser tab or application window. Please click start again and choose Entire Screen.');
        return false;
      }

      streamRef.current = stream;
      track?.addEventListener('ended', () => {
        discardActiveIncident();
        streamRef.current = null;
        setIsRecording(false);
        setError('Screen sharing was stopped. Restart it to continue the exam securely.');
      });

      // "isRecording" means screen-share evidence capture is armed. Actual file
      // recording starts only for blur/tab-switch incidents.
      setIsRecording(true);
      return true;
    } catch (err) {
      setError('Screen recording permission is required. Click start again, choose Entire Screen, and press Share.');
      console.warn('Screen recording permission rejected:', err);
      return false;
    }
  }, [discardActiveIncident, enabled]);

  const beginFocusLossClip = useCallback((details = 'The exam window lost focus.', eventType = FOCUS_LOSS_EVENT_TYPE) => {
    if (!enabled) return;
    if (eventType !== FOCUS_LOSS_EVENT_TYPE && eventType !== TAB_SWITCH_EVENT_TYPE) return;
    if (activeIncidentRef.current || incidentRecorderRef.current) return;

    const stream = streamRef.current;
    if (!stream || stream.getVideoTracks().every((t) => t.readyState !== 'live')) return;

    try {
      const mimeType = getRecorderMimeType();
      const recorder = new MediaRecorder(stream, mimeType ? { mimeType } : undefined);
      const id = ++incidentSeqRef.current;
      const incident = {
        id,
        eventType,
        startedAt: Date.now(),
        details,
        returnDetails: '',
        chunks: [],
        recorder,
        discard: false,
        uploaded: false,
      };

      recorder.ondataavailable = (e) => {
        if (e.data && e.data.size > 0) incident.chunks.push(e.data);
      };

      recorder.onerror = (e) => {
        console.warn('Blur recording error:', e);
      };

      recorder.onstop = async () => {
        if (incident.uploaded || incident.discard) return;
        incident.uploaded = true;
        if (activeIncidentRef.current?.id === incident.id) activeIncidentRef.current = null;
        if (incidentRecorderRef.current === recorder) incidentRecorderRef.current = null;

        const chunks = incident.chunks.slice();
        if (!chunks.length) return;

        const durationMs = (incident.stoppedAt || Date.now()) - incident.startedAt;
        // Ignore accidental instant focus bounces; they produce 0:00 clips in
        // many browsers and are not useful proctoring evidence.
        if (durationMs < 2000) return;
        const secondsAway = Math.max(2, Math.round(durationMs / 1000));
        const blob = new Blob(chunks, { type: 'video/webm' });
        const detailsText = `${incident.details} ${incident.returnDetails || 'The student returned to the exam window.'} Full ${incident.eventType === TAB_SWITCH_EVENT_TYPE ? 'tab-switch' : 'blur'} interval recorded (${secondsAway}s).`;
        const prefix = incident.eventType === TAB_SWITCH_EVENT_TYPE ? 'tab-switch' : 'blur';
        await uploadBlob(blob, incident.eventType, detailsText, `${prefix}-${incident.id}`);
      };

      activeIncidentRef.current = incident;
      incidentRecorderRef.current = recorder;
      recorder.start(1000);
    } catch (err) {
      console.warn('Could not start blur incident recorder:', err);
    }
  }, [enabled, uploadBlob]);

  const finishFocusLossClip = useCallback((returnDetails = 'The student returned to the exam window.') => {
    const incident = activeIncidentRef.current;
    const recorder = incident?.recorder || incidentRecorderRef.current;
    if (!incident || !recorder) return;

    incident.returnDetails = returnDetails;
    incident.stoppedAt = Date.now();

    try {
      if (recorder.state === 'recording') {
        // requestData first helps very short away periods include the latest frame.
        try { recorder.requestData(); } catch { /* ignore */ }
        recorder.stop();
      }
    } catch (err) {
      console.warn('Could not finish blur recording:', err);
      activeIncidentRef.current = null;
      incidentRecorderRef.current = null;
    }
  }, []);

  // Intentionally no-op: clips are now saved only by begin/finishFocusLossClip.
  // Proctor events are still logged, but fullscreen/devtools/etc. do not create
  // recording files, preventing empty/unwanted clips in the faculty report.
  const uploadViolationClip = useCallback(async () => {}, []);

  useEffect(() => stopRecording, [stopRecording]);

  return {
    isRecording,
    recordingError: error,
    startRecording,
    stopRecording,
    uploadViolationClip,
    beginFocusLossClip,
    finishFocusLossClip,
  };
}



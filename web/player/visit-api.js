import { api } from '/web/api.js';

// The server owns visit IDs. Both player entry points use the same cookie-bound
// capability for REST, WebSocket and LiveKit; a restart creates a new visit.
export async function createVisitApi(demoId) {
  const base = `/api/demos/${encodeURIComponent(demoId)}`;
  let sessionId;
  const newVisit = async () => {
    const visit = await api.post(`${base}/run/visit`, {});
    if (typeof visit.session_id !== 'string' || !visit.session_id) throw new Error('The visit could not start. Please retry.');
    sessionId = visit.session_id;
    return sessionId;
  };
  await newVisit();
  return {
    sessionId, newVisit,
    qa: (body, options) => api.post(`${base}/run/qa`, body, options),
    tts: text => api.post(`${base}/run/tts`, { text, session_id:sessionId }).then(r => r.url),
    tts_lang: (text, language) => api.post(`${base}/run/tts`, { text, language, session_id:sessionId }).then(r => r.url),
    pitch: body => api.post(`${base}/run/pitch`, body),
    lead: body => api.post(`${base}/run/lead`, body),
    stt: (blob, language) => {
      const body = new FormData(); body.append('file', blob, 'speech.wav');
      body.append('language', language || 'en-IN'); body.append('session_id', sessionId);
      return api.form(`${base}/run/stt`, body).then(r => r.transcript || '');
    },
    saveSession: body => api.post(`${base}/run/session`, body),
    beacon: body => navigator.sendBeacon(`${base}/run/session`, new Blob([JSON.stringify(body)], { type:'application/json' })),
  };
}

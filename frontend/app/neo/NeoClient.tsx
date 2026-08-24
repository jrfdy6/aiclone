'use client';

import { FormEvent, useEffect, useRef, useState } from 'react';
import { ownerSafeErrorMessage } from '@/lib/control-api';
import { possessivePublicName, publicOwnerDisplayName } from '@/lib/public-profile';
import styles from './neo.module.css';
import responsiveStyles from './neo-responsive.module.css';

type ChatMessage = { role: 'user' | 'assistant'; content: string };
type Job = { status: string; response?: string; partial_response?: string; error_message?: string };
type ActiveResponse = { clientRequestId: string; userMessage: string; jobId?: string; partialResponse: string };
type GuestSessionSnapshot = {
  messages?: ChatMessage[];
  active_job?: {
    job_id?: string;
    client_request_id?: string;
    user_message?: string;
    partial_response?: string;
  } | null;
};
type RecognitionEvent = { results: { 0: { transcript: string } }[] };
type Recognition = { lang: string; interimResults: boolean; onresult: (event: RecognitionEvent) => void; onerror: () => void; onend: () => void; start: () => void; stop: () => void };
type RecognitionConstructor = new () => Recognition;

const welcome = `I'm Neo, ${possessivePublicName()} AI assistant. I can answer questions about their professional experience, projects, and the way they work. I can also help you request a 15-minute coffee chat—${publicOwnerDisplayName} reviews every request before anything is booked.`;
const ACTIVE_JOB_STORAGE_KEY = 'neo.active-response.v1';
const RESPONSE_POLL_WINDOW_MS = 5 * 60 * 1000;
const MAX_CONSECUTIVE_TRANSIENT_FAILURES = 6;
const REQUEST_TIMEOUT_MS = 20_000;

class JsonRequestError extends Error {
  status: number;

  constructor(message: string, status: number) {
    super(message);
    this.name = 'JsonRequestError';
    this.status = status;
  }
}

function responsePollDelay(attempt: number, transientFailures = 0) {
  if (transientFailures > 0) return Math.min(5000, 750 * (2 ** Math.min(transientFailures, 3)));
  if (attempt < 10) return 750;
  if (attempt < 40) return 1250;
  if (attempt < 100) return 1875;
  return 3000;
}

function wait(milliseconds: number) {
  return new Promise((resolve) => setTimeout(resolve, milliseconds));
}

function isInvalidGuestSession(issue: unknown) {
  return issue instanceof JsonRequestError && (issue.status === 401 || issue.status === 403);
}

function isTransientRequestError(issue: unknown) {
  if (issue instanceof TypeError) return true;
  if (!(issue instanceof JsonRequestError)) return false;
  return issue.status === 408 || issue.status === 425 || issue.status === 429 || issue.status >= 500;
}

function createClientRequestId() {
  if (typeof window.crypto.randomUUID === 'function') return window.crypto.randomUUID();
  const bytes = window.crypto.getRandomValues(new Uint8Array(16));
  bytes[6] = (bytes[6] & 0x0f) | 0x40;
  bytes[8] = (bytes[8] & 0x3f) | 0x80;
  const value = Array.from(bytes, (byte) => byte.toString(16).padStart(2, '0')).join('');
  return `${value.slice(0, 8)}-${value.slice(8, 12)}-${value.slice(12, 16)}-${value.slice(16, 20)}-${value.slice(20)}`;
}

function readStoredActiveResponse(): ActiveResponse | null {
  try {
    const value = window.sessionStorage.getItem(ACTIVE_JOB_STORAGE_KEY);
    if (!value) return null;
    const candidate = JSON.parse(value) as Partial<ActiveResponse>;
    if (
      typeof candidate.clientRequestId !== 'string'
      || !/^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i.test(candidate.clientRequestId)
      || typeof candidate.userMessage !== 'string'
      || !candidate.userMessage.trim()
      || candidate.userMessage.length > 4000
      || (candidate.jobId !== undefined && (typeof candidate.jobId !== 'string' || !candidate.jobId.trim() || candidate.jobId.length > 128))
      || (candidate.partialResponse !== undefined && typeof candidate.partialResponse !== 'string')
      || String(candidate.partialResponse || '').length > 8000
    ) {
      window.sessionStorage.removeItem(ACTIVE_JOB_STORAGE_KEY);
      return null;
    }
    return {
      clientRequestId: candidate.clientRequestId,
      userMessage: candidate.userMessage,
      ...(candidate.jobId ? { jobId: candidate.jobId } : {}),
      partialResponse: candidate.partialResponse || '',
    };
  } catch {
    try {
      window.sessionStorage.removeItem(ACTIVE_JOB_STORAGE_KEY);
    } catch {
      // Storage may be unavailable; there is nothing else to recover safely.
    }
    return null;
  }
}

function storeActiveResponse(job: ActiveResponse) {
  try {
    window.sessionStorage.setItem(ACTIVE_JOB_STORAGE_KEY, JSON.stringify(job));
  } catch {
    // A privacy-restricted browser may disable storage; the active tab still recovers in memory.
  }
}

function clearStoredActiveResponse() {
  try {
    window.sessionStorage.removeItem(ACTIVE_JOB_STORAGE_KEY);
  } catch {
    // Clearing storage is best-effort when the browser denies storage access.
  }
}

async function jsonRequest<T>(url: string, options?: RequestInit): Promise<T> {
  const controller = new AbortController();
  const forwardAbort = () => controller.abort(options?.signal?.reason);
  if (options?.signal?.aborted) forwardAbort();
  else options?.signal?.addEventListener('abort', forwardAbort, { once: true });
  const timeoutId = window.setTimeout(() => controller.abort(), REQUEST_TIMEOUT_MS);
  try {
    const response = await fetch(url, {
      ...options,
      headers: { 'Content-Type': 'application/json', ...(options?.headers || {}) },
      signal: controller.signal,
    });
    const payload = await response.json().catch(() => ({})) as { detail?: unknown };
    if (!response.ok) {
      const detail = ownerSafeErrorMessage(payload.detail, 'Something went wrong. Please try again.');
      throw new JsonRequestError(detail, response.status);
    }
    return payload as T;
  } catch (issue) {
    if (controller.signal.aborted && !options?.signal?.aborted) {
      throw new JsonRequestError('The connection timed out. Please try again.', 408);
    }
    throw issue;
  } finally {
    window.clearTimeout(timeoutId);
    options?.signal?.removeEventListener('abort', forwardAbort);
  }
}

export default function NeoClient() {
  const [ready, setReady] = useState(false);
  const [checkingSession, setCheckingSession] = useState(true);
  const [passcode, setPasscode] = useState('');
  const [messages, setMessages] = useState<ChatMessage[]>([{ role: 'assistant', content: welcome }]);
  const [draft, setDraft] = useState('');
  const [busy, setBusy] = useState(false);
  const [responding, setResponding] = useState(false);
  const [partialResponse, setPartialResponse] = useState('');
  const [activeResponse, setActiveResponse] = useState<ActiveResponse | null>(null);
  const [responsePaused, setResponsePaused] = useState(false);
  const [error, setError] = useState('');
  const [listening, setListening] = useState(false);
  const [meetingOpen, setMeetingOpen] = useState(false);
  const [meetingSent, setMeetingSent] = useState(false);
  const recognitionRef = useRef<Recognition | null>(null);
  const bottomRef = useRef<HTMLDivElement | null>(null);
  const activeResponseRef = useRef<ActiveResponse | null>(null);
  const pollRunRef = useRef(0);
  const messagePostInFlightRef = useRef(false);
  const meetingSubmissionRef = useRef<{ clientRequestId: string; payloadKey: string } | null>(null);
  const meetingConfirmationRef = useRef<HTMLDivElement | null>(null);
  const componentMountedRef = useRef(false);
  const sessionBootstrapRef = useRef(0);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, busy, partialResponse, responsePaused]);

  useEffect(() => {
    componentMountedRef.current = true;
    const runId = sessionBootstrapRef.current + 1;
    sessionBootstrapRef.current = runId;
    void bootstrapSession(runId);
    return () => {
      componentMountedRef.current = false;
      if (sessionBootstrapRef.current === runId) sessionBootstrapRef.current += 1;
      pollRunRef.current += 1;
    };
    // Mount-only by design: polling reads stable refs/setters and must not restart on re-render.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    if (meetingSent) meetingConfirmationRef.current?.focus();
  }, [meetingSent]);

  async function bootstrapSession(runId: number) {
    const saved = readStoredActiveResponse();
    setCheckingSession(true);
    try {
      const snapshot = await jsonRequest<GuestSessionSnapshot>('/api/neo/session');
      if (!componentMountedRef.current || sessionBootstrapRef.current !== runId) return;

      const restoredMessages = Array.isArray(snapshot.messages)
        ? snapshot.messages.filter((message): message is ChatMessage => (
          (message?.role === 'user' || message?.role === 'assistant')
          && typeof message.content === 'string'
          && Boolean(message.content.trim())
        )).map((message) => ({ role: message.role, content: message.content.trim() }))
        : [];
      const baseMessages: ChatMessage[] = [{ role: 'assistant', content: welcome }, ...restoredMessages];
      const serverJob = snapshot.active_job;
      const serverJobId = typeof serverJob?.job_id === 'string' ? serverJob.job_id.trim() : '';
      const serverUserMessage = typeof serverJob?.user_message === 'string' ? serverJob.user_message.trim() : '';
      const serverClientRequestId = typeof serverJob?.client_request_id === 'string'
        ? serverJob.client_request_id.trim()
        : '';
      const serverPartial = typeof serverJob?.partial_response === 'string'
        ? serverJob.partial_response.trim()
        : '';
      let recovery = saved;
      if (serverJobId && serverUserMessage) {
        recovery = {
          clientRequestId: serverClientRequestId || saved?.clientRequestId || createClientRequestId(),
          userMessage: serverUserMessage,
          jobId: serverJobId,
          partialResponse: serverPartial,
        };
      }

      if (recovery && !restoredMessages.some(
        (message) => message.role === 'user' && message.content === recovery.userMessage,
      )) {
        baseMessages.push({ role: 'user', content: recovery.userMessage });
      }
      setMessages(baseMessages);
      setReady(true);
      setError('');
      if (recovery) {
        rememberActiveResponse(recovery);
        setPartialResponse(recovery.partialResponse);
        void continueActiveResponse(recovery);
      }
    } catch (issue) {
      if (!componentMountedRef.current || sessionBootstrapRef.current !== runId) return;
      if (isInvalidGuestSession(issue)) {
        clearStoredActiveResponse();
        activeResponseRef.current = null;
        setActiveResponse(null);
      } else {
        setError('Neo could not restore an existing invite. Check your connection and refresh to try again.');
      }
    } finally {
      if (componentMountedRef.current && sessionBootstrapRef.current === runId) {
        setCheckingSession(false);
      }
    }
  }

  function rememberActiveResponse(job: ActiveResponse) {
    activeResponseRef.current = job;
    setActiveResponse(job);
    storeActiveResponse(job);
  }

  function forgetActiveResponse() {
    activeResponseRef.current = null;
    setActiveResponse(null);
    clearStoredActiveResponse();
  }

  function pauseResponse(job: ActiveResponse, message: string) {
    rememberActiveResponse(job);
    setResponding(false);
    setResponsePaused(true);
    setBusy(false);
    setError(message);
  }

  function endInvalidSession(message: string) {
    forgetActiveResponse();
    setResponding(false);
    setResponsePaused(false);
    setPartialResponse('');
    setBusy(false);
    setMessages([{ role: 'assistant', content: welcome }]);
    setCheckingSession(false);
    setReady(false);
    setError(message);
  }

  async function pollExistingJob(initialJob: ActiveResponse) {
    const durableJobId = initialJob.jobId;
    if (!durableJobId) {
      pauseResponse(initialJob, 'Neo has not confirmed this response yet. Resume to reconnect without duplicating your question.');
      return;
    }
    const runId = pollRunRef.current + 1;
    pollRunRef.current = runId;
    const startedAt = Date.now();
    let attempt = 0;
    let transientFailures = 0;
    let currentJob = initialJob;
    setResponding(true);
    setResponsePaused(false);
    setBusy(true);

    while (Date.now() - startedAt < RESPONSE_POLL_WINDOW_MS) {
      try {
        const job = await jsonRequest<Job>(`/api/neo/jobs/${encodeURIComponent(durableJobId)}`);
        if (pollRunRef.current !== runId) return;
        transientFailures = 0;
        const nextPartial = typeof job.partial_response === 'string' ? job.partial_response.trim() : '';
        if (nextPartial !== currentJob.partialResponse) {
          currentJob = { ...currentJob, partialResponse: nextPartial };
          rememberActiveResponse(currentJob);
          setPartialResponse(nextPartial);
        }
        if (job.status === 'completed') {
          const finalResponse = typeof job.response === 'string' ? job.response.trim() : '';
          if (!finalResponse) {
            forgetActiveResponse();
            setPartialResponse('');
            setResponding(false);
            setBusy(false);
            setError('Neo finished without a response. Please ask a new question.');
            return;
          }
          forgetActiveResponse();
          setPartialResponse('');
          setResponding(false);
          setBusy(false);
          setMessages((current) => current.some(
            (message) => message.role === 'assistant' && message.content === finalResponse,
          ) ? current : [...current, { role: 'assistant', content: finalResponse }]);
          return;
        }
        if (job.status === 'failed') {
          const jobError = ownerSafeErrorMessage(job.error_message, '');
          forgetActiveResponse();
          setPartialResponse('');
          setResponding(false);
          setBusy(false);
          setError(jobError || 'Neo could not complete this response. Please ask a new question.');
          return;
        }
      } catch (issue) {
        if (pollRunRef.current !== runId) return;
        const message = ownerSafeErrorMessage(issue, 'Neo could not check this response.');
        if (isInvalidGuestSession(issue)) {
          endInvalidSession(message);
          return;
        }
        if (!isTransientRequestError(issue)) {
          forgetActiveResponse();
          setPartialResponse('');
          setResponding(false);
          setBusy(false);
          setError(message);
          return;
        }
        transientFailures += 1;
        if (transientFailures >= MAX_CONSECUTIVE_TRANSIENT_FAILURES) {
          pauseResponse(currentJob, 'The connection paused while Neo was responding. Resume when your connection is stable—your question will not be sent twice.');
          return;
        }
      }

      const elapsed = Date.now() - startedAt;
      const remaining = RESPONSE_POLL_WINDOW_MS - elapsed;
      if (remaining <= 0) break;
      await wait(Math.min(responsePollDelay(attempt, transientFailures), remaining));
      if (pollRunRef.current !== runId) return;
      attempt += 1;
    }

    if (pollRunRef.current === runId) {
      pauseResponse(currentJob, 'Neo is still working on this response. Resume to keep checking without sending your question again.');
    }
  }

  async function recoverUnconfirmedJob(initialResponse: ActiveResponse): Promise<ActiveResponse | null> {
    try {
      const snapshot = await jsonRequest<GuestSessionSnapshot>('/api/neo/session');
      const active = snapshot.active_job;
      const jobId = typeof active?.job_id === 'string' ? active.job_id.trim() : '';
      const serverRequestId = typeof active?.client_request_id === 'string' ? active.client_request_id.trim() : '';
      const serverMessage = typeof active?.user_message === 'string' ? active.user_message.trim() : '';
      if (!jobId || serverRequestId !== initialResponse.clientRequestId || serverMessage !== initialResponse.userMessage) {
        return null;
      }
      const recovered = {
        ...initialResponse,
        jobId,
        partialResponse: typeof active?.partial_response === 'string' ? active.partial_response.trim() : initialResponse.partialResponse,
      };
      rememberActiveResponse(recovered);
      return recovered;
    } catch {
      return null;
    }
  }

  async function createOrRecoverJob(initialResponse: ActiveResponse) {
    if (initialResponse.jobId) {
      await pollExistingJob(initialResponse);
      return;
    }
    if (messagePostInFlightRef.current) return;
    messagePostInFlightRef.current = true;
    let attempt = 0;
    let transientFailures = 0;
    setResponding(true);
    setResponsePaused(false);
    setBusy(true);
    setError('');

    try {
      while (transientFailures < MAX_CONSECUTIVE_TRANSIENT_FAILURES) {
        if (!componentMountedRef.current) return;
        try {
          const created = await jsonRequest<{ job_id: string }>('/api/neo/messages', {
            method: 'POST',
            body: JSON.stringify({
              content: initialResponse.userMessage,
              client_request_id: initialResponse.clientRequestId,
            }),
          });
          if (!componentMountedRef.current) return;
          const jobId = String(created.job_id || '').trim();
          if (!jobId) throw new JsonRequestError('Neo did not confirm the response job.', 502);
          const confirmedResponse = { ...initialResponse, jobId };
          rememberActiveResponse(confirmedResponse);
          messagePostInFlightRef.current = false;
          await pollExistingJob(confirmedResponse);
          return;
        } catch (issue) {
          if (!componentMountedRef.current) return;
          const message = ownerSafeErrorMessage(issue, 'Neo could not confirm this response.');
          if (isInvalidGuestSession(issue)) {
            endInvalidSession(message);
            return;
          }
          if (!isTransientRequestError(issue)) {
            forgetActiveResponse();
            setPartialResponse('');
            setResponding(false);
            setBusy(false);
            setError(message);
            return;
          }
          transientFailures += 1;
          if (transientFailures >= MAX_CONSECUTIVE_TRANSIENT_FAILURES) {
            const recovered = await recoverUnconfirmedJob(initialResponse);
            if (recovered) {
              messagePostInFlightRef.current = false;
              await pollExistingJob(recovered);
              return;
            }
            pauseResponse(initialResponse, 'The connection paused before Neo confirmed the response. Resume to retry safely—the same question and request ID will be reused.');
            return;
          }
          await wait(responsePollDelay(attempt, transientFailures));
          attempt += 1;
        }
      }
    } finally {
      messagePostInFlightRef.current = false;
    }
  }

  async function continueActiveResponse(job: ActiveResponse) {
    if (job.jobId) {
      await pollExistingJob(job);
      return;
    }
    await createOrRecoverJob(job);
  }

  function resumeResponse() {
    const job = activeResponseRef.current;
    if (!job || responding) return;
    setError('');
    void continueActiveResponse(job);
  }

  async function enter(event: FormEvent) {
    event.preventDefault(); setError(''); setBusy(true);
    try {
      await jsonRequest('/api/neo/access', { method: 'POST', body: JSON.stringify({ passcode }) });
      setReady(true); setCheckingSession(false); setPasscode('');
    } catch (issue) { setError(ownerSafeErrorMessage(issue, 'Invite could not be verified.')); }
    finally { setBusy(false); }
  }

  async function send(event: FormEvent) {
    event.preventDefault();
    const content = draft.trim();
    if (!content || busy || activeResponseRef.current || messagePostInFlightRef.current) return;
    const pendingResponse = {
      clientRequestId: createClientRequestId(),
      userMessage: content,
      partialResponse: '',
    };
    rememberActiveResponse(pendingResponse);
    setDraft(''); setError(''); setBusy(true); setResponding(true); setPartialResponse('');
    setMessages((current) => [...current, { role: 'user', content }]);
    await continueActiveResponse(pendingResponse);
  }

  function toggleVoice() {
    if (listening) { recognitionRef.current?.stop(); return; }
    const browserWindow = window as typeof window & { SpeechRecognition?: RecognitionConstructor; webkitSpeechRecognition?: RecognitionConstructor };
    const SpeechRecognition = browserWindow.SpeechRecognition || browserWindow.webkitSpeechRecognition;
    if (!SpeechRecognition) { setError('Voice input is not supported in this browser. Text chat still works.'); return; }
    const recognition = new SpeechRecognition();
    recognition.lang = 'en-US'; recognition.interimResults = false;
    recognition.onresult = (event) => setDraft(event.results[0][0].transcript);
    recognition.onerror = () => setError('I could not hear that clearly. You can try again or type your question.');
    recognition.onend = () => setListening(false);
    recognitionRef.current = recognition; setListening(true); recognition.start();
  }

  function speak(text: string) {
    window.speechSynthesis.cancel();
    const utterance = new SpeechSynthesisUtterance(text); utterance.rate = 0.96; utterance.pitch = 0.96;
    window.speechSynthesis.speak(utterance);
  }

  async function requestMeeting(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); setError(''); setBusy(true);
    const form = new FormData(event.currentTarget);
    const meetingPayload = {
      visitor_name: String(form.get('name') || '').trim(),
      visitor_email: String(form.get('email') || '').trim(),
      visitor_phone: String(form.get('phone') || '').trim(),
      purpose: String(form.get('purpose') || '').trim(),
      preferred_times: [String(form.get('times') || '').trim()],
      timezone: String(form.get('timezone') || '').trim(),
    };
    const payloadKey = JSON.stringify(meetingPayload);
    const clientRequestId = meetingSubmissionRef.current?.payloadKey === payloadKey
      ? meetingSubmissionRef.current.clientRequestId
      : createClientRequestId();
    meetingSubmissionRef.current = { clientRequestId, payloadKey };
    try {
      await jsonRequest('/api/neo/meeting-requests', {
        method: 'POST',
        body: JSON.stringify({ ...meetingPayload, client_request_id: clientRequestId }),
      });
      meetingSubmissionRef.current = null;
      setMeetingSent(true);
    } catch (issue) {
      const message = ownerSafeErrorMessage(issue, 'Meeting request could not be sent.');
      if (isInvalidGuestSession(issue)) endInvalidSession(message);
      else setError(message);
    }
    finally { setBusy(false); }
  }

  if (checkingSession) return (
    <main className={styles.shell}><section className={`${styles.accessCard} ${responsiveStyles.accessCard}`} role="status" aria-live="polite">
      <div className={styles.mark}>N</div><p className={styles.eyebrow}>A private introduction</p>
      <h1>Meet Neo</h1><p>Checking for your existing invite and conversation…</p>
    </section></main>
  );

  if (!ready) return (
    <main className={styles.shell}><section className={`${styles.accessCard} ${responsiveStyles.accessCard}`}>
      <div className={styles.mark}>N</div><p className={styles.eyebrow}>A private introduction</p>
      <h1>Meet Neo</h1><p>{possessivePublicName()} AI assistant for professional conversations.</p>
      <form onSubmit={enter}><label htmlFor="passcode">Your invite passcode</label><input id="passcode" value={passcode} onChange={(event) => setPasscode(event.target.value)} type="password" autoComplete="one-time-code" required />
        <button disabled={busy}>{busy ? 'Checking…' : 'Start conversation'}</button></form>
      {error && <p className={styles.error} role="alert">{error}</p>}
      <small>Invite access is separate from {possessivePublicName()} private AI Clone dashboards.</small>
    </section></main>
  );

  return <main className={styles.shell}><section className={`${styles.chatCard} ${responsiveStyles.chatCard}`}>
    <header><div><p className={styles.eyebrow}>{publicOwnerDisplayName}</p><h1>Neo</h1></div><span className={styles.status}><i /> Local AI assistant</span></header>
    <div className={styles.messages} aria-live={activeResponse ? 'off' : 'polite'} aria-busy={responding}>
      {messages.map((message, index) => <div key={`${message.role}-${index}`} className={`${styles.message} ${styles[message.role]}`}><span>{message.role === 'assistant' ? 'Neo' : 'You'}</span><p>{message.content}</p>{message.role === 'assistant' && <button className={styles.speak} onClick={() => speak(message.content)} aria-label="Speak Neo's response">Listen</button>}</div>)}
      {(responding || activeResponse) && <div className={`${styles.message} ${styles.assistant}`} role="status" aria-live="polite" aria-atomic="false" aria-label={responsePaused ? 'Neo response paused. Resume to continue the preserved response.' : partialResponse ? 'Neo is drafting a response. The visible draft may still change.' : 'Neo is preparing a response.'}><span>{responsePaused ? 'Neo · Response paused' : partialResponse ? 'Neo · Draft in progress' : 'Neo · Preparing'}</span><p className={partialResponse ? undefined : styles.thinking}>{partialResponse || (responsePaused ? 'The response is preserved and ready to resume.' : 'Preparing a response…')}</p>{responsePaused && <button type="button" className={styles.speak} onClick={resumeResponse}>Resume response</button>}</div>}
      <div ref={bottomRef} />
    </div>
    {error && <p className={styles.error} role="alert">{error}</p>}
    <form className={styles.composer} onSubmit={send}><textarea aria-label="Ask Neo a question" value={draft} onChange={(event) => setDraft(event.target.value)} placeholder={`Ask about ${possessivePublicName()} experience, projects, or approach…`} rows={2} /><button type="button" className={styles.mic} onClick={toggleVoice} aria-pressed={listening}>{listening ? 'Stop' : 'Talk'}</button><button disabled={busy || Boolean(activeResponse) || !draft.trim()}>Send</button></form>
    <button className={styles.coffee} onClick={() => setMeetingOpen((value) => !value)} aria-expanded={meetingOpen} aria-controls="neo-meeting-panel">☕ Request a 15-minute coffee chat</button>
    {meetingOpen && (meetingSent ? <div id="neo-meeting-panel" ref={meetingConfirmationRef} className={styles.confirmation} role="status" aria-live="polite" aria-atomic="true" tabIndex={-1}><strong>Request sent.</strong><p>{publicOwnerDisplayName} will review it before anything is booked.</p></div> : <form id="neo-meeting-panel" className={styles.meeting} onSubmit={requestMeeting}><h2>Let {publicOwnerDisplayName} buy you a coffee</h2><p>Share a few options. This sends an approval request; it does not book the meeting.</p><div className={styles.grid}><label>Name<input name="name" required /></label><label>Email<input name="email" type="email" required /></label><label>Phone<input name="phone" type="tel" required /></label><label>Timezone<input name="timezone" placeholder="America/New_York" required /></label></div><label>Preferred dates and times<textarea name="times" placeholder="Tuesday 2–4 PM; Thursday after 11 AM" required /></label><label>What would you like to discuss?<textarea name="purpose" required /></label><button disabled={busy}>Send for owner approval</button></form>)}
  </section></main>;
}

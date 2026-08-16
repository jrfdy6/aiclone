const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const test = require('node:test');

const neoClientSource = fs.readFileSync(
  path.join(__dirname, '..', 'app', 'neo', 'NeoClient.tsx'),
  'utf8',
);
const neoResponsiveSource = fs.readFileSync(
  path.join(__dirname, '..', 'app', 'neo', 'neo-responsive.module.css'),
  'utf8',
);
const neoInboxSource = fs.readFileSync(
  path.join(__dirname, '..', 'app', 'inbox', 'neo', 'page.tsx'),
  'utf8',
);
const neoErrorSource = fs.readFileSync(
  path.join(__dirname, '..', 'app', 'neo', 'error.tsx'),
  'utf8',
);
const globalErrorSource = fs.readFileSync(
  path.join(__dirname, '..', 'app', 'global-error.tsx'),
  'utf8',
);
const routeStateSource = fs.readFileSync(
  path.join(__dirname, '..', 'components', 'runtime', 'RouteStateShell.tsx'),
  'utf8',
);
const middlewareSource = fs.readFileSync(
  path.join(__dirname, '..', 'middleware.ts'),
  'utf8',
);
const neoGuestServerSource = fs.readFileSync(
  path.join(__dirname, '..', 'lib', 'neo-guest-server.ts'),
  'utf8',
);
const neoSessionRouteSource = fs.readFileSync(
  path.join(__dirname, '..', 'app', 'api', 'neo', 'session', 'route.ts'),
  'utf8',
);
const neoMessagesRouteSource = fs.readFileSync(
  path.join(__dirname, '..', 'app', 'api', 'neo', 'messages', 'route.ts'),
  'utf8',
);
const neoMeetingRouteSource = fs.readFileSync(
  path.join(__dirname, '..', 'app', 'api', 'neo', 'meeting-requests', 'route.ts'),
  'utf8',
);

function sourceFunction(source, name) {
  const start = source.indexOf(`function ${name}(`);
  assert.notEqual(start, -1, `${name} must exist`);
  const openingBrace = source.indexOf('{', start);
  let depth = 0;
  for (let index = openingBrace; index < source.length; index += 1) {
    if (source[index] === '{') depth += 1;
    if (source[index] === '}') depth -= 1;
    if (depth === 0) return source.slice(start, index + 1);
  }
  assert.fail(`${name} must have a complete body`);
}

test('Neo auto-scroll effect never returns the browser method result as cleanup', () => {
  assert.match(
    neoClientSource,
    /useEffect\(\(\) => \{\s*bottomRef\.current\?\.scrollIntoView\(\{ behavior: 'smooth' \}\);\s*\}, \[messages, busy, partialResponse, responsePaused\]\);/,
  );
  assert.doesNotMatch(
    neoClientSource,
    /useEffect\(\(\) => bottomRef\.current\?\.scrollIntoView/,
  );
});

test('Neo invite creation retains the form element across the async request', () => {
  assert.match(neoInboxSource, /const formElement = event\.currentTarget;/);
  assert.match(neoInboxSource, /const form = new FormData\(formElement\);/);
  assert.match(neoInboxSource, /formElement\.reset\(\); await load\(\);/);
  assert.doesNotMatch(neoInboxSource, /event\.currentTarget\.reset\(\)/);
});

test('Neo shows one accessible temporary bubble while a response is progressing', () => {
  assert.match(neoClientSource, /partial_response\?: string/);
  assert.match(neoClientSource, /const \[responding, setResponding\] = useState\(false\);/);
  assert.match(neoClientSource, /const \[partialResponse, setPartialResponse\] = useState\(''\);/);
  assert.match(neoClientSource, /if \(nextPartial !== currentJob\.partialResponse\) \{/);
  assert.doesNotMatch(neoClientSource, /if \(nextPartial && nextPartial !== currentJob\.partialResponse\) \{/);
  assert.match(neoClientSource, /setPartialResponse\(nextPartial\);/);
  assert.match(neoClientSource, /aria-busy=\{responding\}/);
  assert.match(neoClientSource, /aria-live=\{activeResponse \? 'off' : 'polite'\}/);
  assert.match(neoClientSource, /role="status"[^>]+aria-live="polite"[^>]+aria-atomic="false"/);
  assert.match(neoClientSource, /Neo · Draft in progress/);
  assert.match(neoClientSource, /\{\(responding \|\| activeResponse\) && <div/);
});

test('Neo bounds browser and proxy requests without leaving timeout handles behind', () => {
  assert.match(neoClientSource, /const REQUEST_TIMEOUT_MS = 20_000;/);
  assert.match(neoClientSource, /const controller = new AbortController\(\);/);
  assert.match(neoClientSource, /window\.setTimeout\(\(\) => controller\.abort\(\), REQUEST_TIMEOUT_MS\)/);
  assert.match(neoClientSource, /throw new JsonRequestError\('The connection timed out\. Please try again\.', 408\);/);
  assert.match(neoClientSource, /window\.clearTimeout\(timeoutId\);/);
  assert.match(neoClientSource, /options\?\.signal\?\.removeEventListener\('abort', forwardAbort\);/);

  assert.match(neoGuestServerSource, /const NEO_BACKEND_TIMEOUT_MS = 15_000;/);
  assert.match(neoGuestServerSource, /const controller = new AbortController\(\);/);
  assert.match(neoGuestServerSource, /setTimeout\(\(\) => controller\.abort\(\), NEO_BACKEND_TIMEOUT_MS\)/);
  assert.match(neoGuestServerSource, /clearTimeout\(timeoutId\);/);
  assert.match(neoGuestServerSource, /options\.signal\?\.removeEventListener\('abort', forwardAbort\);/);
});

test('Neo replaces progressive text with the completed response', () => {
  assert.match(neoClientSource, /if \(job\.status === 'completed'\) \{/);
  assert.match(neoClientSource, /forgetActiveResponse\(\);\s*setPartialResponse\(''\);[\s\S]+setMessages\(\(current\) => current\.some\(/);
  assert.match(neoClientSource, /\? current : \[\.\.\.current, \{ role: 'assistant', content: finalResponse \}\]\);/);
  assert.doesNotMatch(
    neoClientSource,
    /setMessages\([^;]+partialResponse/,
  );
});

test('Neo polls beyond the worker ceiling with bounded normal and recovery backoff', () => {
  const windowExpression = neoClientSource.match(/const RESPONSE_POLL_WINDOW_MS = ([^;]+);/)?.[1];
  assert.ok(windowExpression);
  const responseWindow = Function(`return ${windowExpression}`)();
  assert.equal(responseWindow, 300000);
  assert.ok(responseWindow > 180000);
  assert.match(neoClientSource, /while \(Date\.now\(\) - startedAt < RESPONSE_POLL_WINDOW_MS\) \{/);
  assert.doesNotMatch(neoClientSource, /for \(let attempt = 0; attempt < 80/);

  const delaySource = sourceFunction(neoClientSource, 'responsePollDelay')
    .replace('attempt: number', 'attempt');
  const delay = Function(`return (${delaySource})`)();
  assert.equal(delay(0, 0), 750);
  assert.equal(delay(1000, 0), 3000);
  assert.equal(delay(0, 1), 1500);
  assert.equal(delay(0, 6), 5000);
  assert.ok([0, 10, 40, 100, 1000].every((attempt) => delay(attempt, 0) <= 5000));
  assert.ok([1, 2, 3, 4, 10].every((failures) => delay(0, failures) <= 5000));
});

test('one transient GET failure is recovered instead of abandoning the job', () => {
  const pollSource = sourceFunction(neoClientSource, 'pollExistingJob');
  assert.match(neoClientSource, /const MAX_CONSECUTIVE_TRANSIENT_FAILURES = 6;/);
  assert.match(pollSource, /const durableJobId = initialJob\.jobId;/);
  assert.match(pollSource, /const job = await jsonRequest<Job>\(`\/api\/neo\/jobs\/\$\{encodeURIComponent\(durableJobId\)\}`\);/);
  assert.match(pollSource, /transientFailures = 0;/);
  assert.match(pollSource, /transientFailures \+= 1;/);
  assert.match(pollSource, /if \(transientFailures >= MAX_CONSECUTIVE_TRANSIENT_FAILURES\) \{/);
  assert.doesNotMatch(pollSource, /if \(transientFailures === 1\)/);
});

test('pending and durable responses persist enough state to survive reload', () => {
  assert.match(neoClientSource, /const ACTIVE_JOB_STORAGE_KEY = 'neo\.active-response\.v1';/);
  assert.match(neoClientSource, /window\.sessionStorage\.getItem\(ACTIVE_JOB_STORAGE_KEY\)/);
  assert.match(neoClientSource, /window\.sessionStorage\.setItem\(ACTIVE_JOB_STORAGE_KEY, JSON\.stringify\(job\)\)/);
  assert.match(neoClientSource, /window\.sessionStorage\.removeItem\(ACTIVE_JOB_STORAGE_KEY\)/);
  assert.match(neoClientSource, /type ActiveResponse = \{ clientRequestId: string; userMessage: string; jobId\?: string; partialResponse: string \}/);
  assert.match(neoClientSource, /const snapshot = await jsonRequest<GuestSessionSnapshot>\('\/api\/neo\/session'\);/);
  assert.match(neoClientSource, /const restoredMessages = Array\.isArray\(snapshot\.messages\)/);
  assert.match(neoClientSource, /const baseMessages: ChatMessage\[\] = \[\{ role: 'assistant', content: welcome \}, \.\.\.restoredMessages\];/);
  assert.match(neoClientSource, /const serverJob = snapshot\.active_job;/);
  assert.match(neoClientSource, /rememberActiveResponse\(recovery\);\s*setPartialResponse\(recovery\.partialResponse\);\s*void continueActiveResponse\(recovery\);/);
  assert.match(neoClientSource, /const \[checkingSession, setCheckingSession\] = useState\(true\);/);
  assert.match(neoClientSource, /Checking for your existing invite and conversation…/);
});

test('a valid guest cookie restores history without consuming another passcode attempt', () => {
  const bootstrapSource = sourceFunction(neoClientSource, 'bootstrapSession');
  assert.match(bootstrapSource, /jsonRequest<GuestSessionSnapshot>\('\/api\/neo\/session'\)/);
  assert.match(bootstrapSource, /setMessages\(baseMessages\);\s*setReady\(true\);/);
  assert.doesNotMatch(bootstrapSource, /\/api\/neo\/access/);
  assert.match(neoSessionRouteSource, /export async function GET\(request: NextRequest\)/);
  assert.match(neoSessionRouteSource, /neoBackendFetch\(request, '\/api\/neo\/guest\/session'\)/);
  assert.match(neoSessionRouteSource, /return passThrough\(upstream\);/);
});

test('new guest writes use versioned backend contracts while the public browser paths stay stable', () => {
  assert.match(neoMessagesRouteSource, /neoBackendFetch\(request, '\/api\/neo\/guest\/v2\/messages'/);
  assert.match(neoMeetingRouteSource, /neoBackendFetch\(request, '\/api\/neo\/guest\/v2\/meeting-requests'/);
  assert.match(neoClientSource, /jsonRequest<\{ job_id: string \}>\('\/api\/neo\/messages'/);
  assert.match(neoClientSource, /jsonRequest\('\/api\/neo\/meeting-requests'/);
});

test('ambiguous POST recovery reuses one persisted idempotency key and exact content', () => {
  const sendSource = sourceFunction(neoClientSource, 'send');
  const createSource = sourceFunction(neoClientSource, 'createOrRecoverJob');
  assert.match(sendSource, /clientRequestId: createClientRequestId\(\),\s*userMessage: content,\s*partialResponse: ''/);
  assert.match(sendSource, /rememberActiveResponse\(pendingResponse\);[\s\S]+await continueActiveResponse\(pendingResponse\);/);
  assert.match(createSource, /while \(transientFailures < MAX_CONSECUTIVE_TRANSIENT_FAILURES\) \{/);
  assert.match(createSource, /content: initialResponse\.userMessage,\s*client_request_id: initialResponse\.clientRequestId,/);
  assert.doesNotMatch(createSource, /createClientRequestId\(\)/);
  assert.match(createSource, /const confirmedResponse = \{ \.\.\.initialResponse, jobId \};\s*rememberActiveResponse\(confirmedResponse\);/);
  assert.match(createSource, /pauseResponse\(initialResponse, 'The connection paused before Neo confirmed the response\./);
  assert.equal((neoClientSource.match(/'\/api\/neo\/messages'/g) || []).length, 1);
  assert.match(neoClientSource, /const messagePostInFlightRef = useRef\(false\);/);
  assert.match(neoClientSource, /if \(!content \|\| busy \|\| activeResponseRef\.current \|\| messagePostInFlightRef\.current\) return;/);
});

test('once the durable job id is known every resume operation is GET only', () => {
  const resumeSource = sourceFunction(neoClientSource, 'resumeResponse');
  const continueSource = sourceFunction(neoClientSource, 'continueActiveResponse');
  const pollSource = sourceFunction(neoClientSource, 'pollExistingJob');
  assert.match(resumeSource, /void continueActiveResponse\(job\);/);
  assert.doesNotMatch(resumeSource, /\/api\/neo\/messages/);
  assert.match(continueSource, /if \(job\.jobId\) \{\s*await pollExistingJob\(job\);\s*return;\s*\}/);
  assert.doesNotMatch(pollSource, /\/api\/neo\/messages/);
  assert.match(pollSource, /jsonRequest<Job>\(`\/api\/neo\/jobs\//);
});

test('a paused response retains its latest partial and has one explicit resume action', () => {
  const pauseSource = sourceFunction(neoClientSource, 'pauseResponse');
  assert.match(pauseSource, /rememberActiveResponse\(job\);/);
  assert.match(pauseSource, /setResponsePaused\(true\);/);
  assert.doesNotMatch(pauseSource, /setPartialResponse\(''\)/);
  assert.match(neoClientSource, /currentJob = \{ \.\.\.currentJob, partialResponse: nextPartial \};\s*rememberActiveResponse\(currentJob\);\s*setPartialResponse\(nextPartial\);/);
  assert.match(neoClientSource, /Neo is still working on this response\. Resume to keep checking without sending your question again\./);
  assert.match(neoClientSource, /<button type="button" className=\{styles\.speak\} onClick=\{resumeResponse\}>Resume response<\/button>/);
  assert.equal((neoClientSource.match(/>Resume response<\/button>/g) || []).length, 1);
});

test('invalid guest sessions are terminal and clear the saved response', () => {
  const invalidSessionSource = sourceFunction(neoClientSource, 'isInvalidGuestSession');
  const terminalSource = sourceFunction(neoClientSource, 'endInvalidSession');
  assert.match(invalidSessionSource, /issue\.status === 401 \|\| issue\.status === 403/);
  assert.match(terminalSource, /forgetActiveResponse\(\);/);
  assert.match(terminalSource, /setPartialResponse\(''\);/);
  assert.match(terminalSource, /setReady\(false\);/);
  assert.match(neoClientSource, /if \(isInvalidGuestSession\(issue\)\) \{\s*endInvalidSession\(message\);\s*return;/);
});

test('meeting retries reuse one idempotency key for the same normalized request', () => {
  const meetingSource = sourceFunction(neoClientSource, 'requestMeeting');
  assert.match(neoClientSource, /const meetingSubmissionRef = useRef<\{ clientRequestId: string; payloadKey: string \} \| null>\(null\);/);
  assert.match(meetingSource, /const meetingPayload = \{/);
  assert.match(meetingSource, /const payloadKey = JSON\.stringify\(meetingPayload\);/);
  assert.match(meetingSource, /meetingSubmissionRef\.current\?\.payloadKey === payloadKey/);
  assert.match(meetingSource, /meetingSubmissionRef\.current = \{ clientRequestId, payloadKey \};/);
  assert.match(meetingSource, /body: JSON\.stringify\(\{ \.\.\.meetingPayload, client_request_id: clientRequestId \}\)/);
  assert.match(meetingSource, /meetingSubmissionRef\.current = null;/);
  assert.match(meetingSource, /if \(isInvalidGuestSession\(issue\)\) endInvalidSession\(message\);/);
});

test('the primary text composer has an accessible name', () => {
  assert.match(neoClientSource, /<textarea aria-label="Ask Neo a question"/);
});

test('Neo guest cards stay inside a phone viewport', () => {
  assert.match(neoClientSource, /responsiveStyles\.accessCard/);
  assert.match(neoClientSource, /responsiveStyles\.chatCard/);
  assert.match(neoResponsiveSource, /@media \(max-width: 600px\)/);
  assert.match(neoResponsiveSource, /width: calc\(100% - 32px\)/);
  assert.match(neoResponsiveSource, /box-sizing: border-box/);
});

test('meeting disclosure and success are announced and focused accessibly', () => {
  assert.match(neoClientSource, /const meetingConfirmationRef = useRef<HTMLDivElement \| null>\(null\);/);
  assert.match(neoClientSource, /if \(meetingSent\) meetingConfirmationRef\.current\?\.focus\(\);/);
  assert.match(neoClientSource, /aria-expanded=\{meetingOpen\} aria-controls="neo-meeting-panel"/);
  assert.match(neoClientSource, /id="neo-meeting-panel" ref=\{meetingConfirmationRef\}[^>]+role="status"[^>]+aria-live="polite"[^>]+aria-atomic="true"[^>]+tabIndex=\{-1\}/);
});

test('Neo failures recover inside the guest module without dashboard navigation', () => {
  assert.match(neoErrorSource, /primaryLabel="Retry Neo"/);
  assert.match(neoErrorSource, /secondaryHref=\{null\}/);
  assert.doesNotMatch(neoErrorSource, /\/(?:ops|brain|inbox|lab|workspace|login)/);
});

test('the global boundary fails closed before exposing private Ops recovery', () => {
  assert.match(globalErrorSource, /useState<ErrorSurface>\('unknown'\)/);
  assert.match(globalErrorSource, /const exposeOpsRecovery = surface === 'private';/);
  assert.match(globalErrorSource, /secondaryHref=\{exposeOpsRecovery \? '\/ops' : null\}/);
  assert.match(routeStateSource, /\{secondaryHref \? \(/);
});

test('nested Neo-shaped URLs return to the guest root instead of private login', () => {
  assert.match(middlewareSource, /if \(path\.startsWith\('\/neo\/'\)\) \{/);
  assert.match(middlewareSource, /neo\.pathname = '\/neo';/);
  assert.match(middlewareSource, /return NextResponse\.redirect\(neo\);/);
});

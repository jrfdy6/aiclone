const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const test = require('node:test');
const ts = require('typescript');

const sourcePath = path.join(__dirname, '..', 'lib', 'integrated-content-job.ts');
const source = fs.readFileSync(sourcePath, 'utf8');
const compiled = ts.transpileModule(source, { compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022 } }).outputText;
const moduleValue = { exports: {} };
new Function('module', 'exports', compiled)(moduleValue, moduleValue.exports);
const {
  forgetPendingIntegratedVariantJob,
  IntegratedContentJobError,
  listPendingIntegratedVariantJobs,
  rememberPendingIntegratedVariantJob,
  waitForIntegratedContentJob,
} = moduleValue.exports;

test('waits for the exact signed local content job and returns completion', async () => {
  const states = ['queued', 'running', 'completed'];
  const result = await waitForIntegratedContentJob({
    receipt: { job_id: 'job-1', card_id: 'job-1' },
    readStatus: async () => ({ job_id: 'job-1', card_id: 'job-1', status: states.shift() }),
    sleep: async () => {},
    pollIntervalMs: 1,
    timeoutMs: 3,
  });
  assert.equal(result.status, 'completed');
});

test('fails closed on mismatched identity and bounded runner failure', async () => {
  await assert.rejects(
    waitForIntegratedContentJob({
      receipt: { job_id: 'job-1' },
      readStatus: async () => ({ job_id: 'other', card_id: 'other', status: 'completed' }),
      sleep: async () => {},
      pollIntervalMs: 1,
      timeoutMs: 1,
    }),
    /did not match/,
  );
  await assert.rejects(
    waitForIntegratedContentJob({
      receipt: { job_id: 'job-1' },
      readStatus: async () => ({ job_id: 'job-1', card_id: 'job-1', status: 'failed', error: 'Evidence gate failed.' }),
      sleep: async () => {},
      pollIntervalMs: 1,
      timeoutMs: 1,
    }),
    /Evidence gate failed/,
  );
});

test('owner-action polling surfaces the canonical local runner error without treating it as completion', async () => {
  const statuses = [
    { job_id: 'owner-action-1', card_id: 'owner-action-1', status: 'queued' },
    { job_id: 'owner-action-1', card_id: 'owner-action-1', status: 'running' },
    {
      job_id: 'owner-action-1',
      card_id: 'owner-action-1',
      status: 'failed',
      error: 'The exact revision changed before owner approval.',
    },
  ];
  await assert.rejects(
    waitForIntegratedContentJob({
      receipt: { job_id: 'owner-action-1', card_id: 'owner-action-1' },
      readStatus: async () => statuses.shift(),
      sleep: async () => {},
      pollIntervalMs: 1,
      timeoutMs: 3,
    }),
    /exact revision changed/,
  );
  assert.equal(statuses.length, 0);
});

test('transient status reads recover without retrying the generation action', async () => {
  let reads = 0;
  const observed = [];
  const result = await waitForIntegratedContentJob({
    receipt: { job_id: 'job-transient', card_id: 'job-transient' },
    readStatus: async () => {
      reads += 1;
      if (reads === 1) throw new Error('temporary network loss');
      return { job_id: 'job-transient', card_id: 'job-transient', status: 'completed' };
    },
    onStatus: (status) => observed.push(status.status),
    sleep: async () => {},
    pollIntervalMs: 1,
    timeoutMs: 2,
  });
  assert.equal(result.status, 'completed');
  assert.equal(reads, 2);
  assert.deepEqual(observed, ['completed']);
});

test('bounded consecutive status failures remain resumable and hide diagnostics', async () => {
  await assert.rejects(
    waitForIntegratedContentJob({
      receipt: { job_id: 'job-offline', card_id: 'job-offline' },
      readStatus: async () => {
        const privatePath = ['', 'Users', 'test-owner', 'private-worker'].join('/');
        throw new Error(`${privatePath} exception`);
      },
      sleep: async () => {},
      pollIntervalMs: 1,
      timeoutMs: 3,
      maxConsecutiveReadFailures: 3,
    }),
    (error) => {
      assert.ok(error instanceof IntegratedContentJobError);
      assert.equal(error.kind, 'status_unavailable');
      assert.equal(error.retryable, true);
      assert.doesNotMatch(error.message, /Users|exception/);
      return true;
    },
  );
});

test('terminal job diagnostics are bounded before rendering', async () => {
  await assert.rejects(
    waitForIntegratedContentJob({
      receipt: { job_id: 'job-failed', card_id: 'job-failed' },
      readStatus: async () => ({
        job_id: 'job-failed', card_id: 'job-failed', status: 'failed',
        error: 'Traceback at /private/tmp/secret.py',
      }),
      sleep: async () => {},
      pollIntervalMs: 1,
      timeoutMs: 1,
    }),
    (error) => {
      assert.equal(error.kind, 'terminal_failure');
      assert.equal(
        error.message,
        'The local job did not finish all of its delivery steps. Refresh before retrying because canonical local state may already contain the action.',
      );
      assert.doesNotMatch(error.message, /private|Traceback/);
      assert.doesNotMatch(error.message, /not changed/i);
      return true;
    },
  );
});

test('generic terminal transport errors use the honest partial-delivery fallback', async () => {
  await assert.rejects(
    waitForIntegratedContentJob({
      receipt: { job_id: 'job-version-skew', card_id: 'job-version-skew' },
      readStatus: async () => ({
        job_id: 'job-version-skew', card_id: 'job-version-skew', status: 'failed',
        message: 'HTTP Error 422: Unprocessable Content',
      }),
      sleep: async () => {},
      pollIntervalMs: 1,
      timeoutMs: 1,
    }),
    (error) => {
      assert.ok(error instanceof IntegratedContentJobError);
      assert.equal(error.kind, 'terminal_failure');
      assert.equal(
        error.message,
        'The local job did not finish all of its delivery steps. Refresh before retrying because canonical local state may already contain the action.',
      );
      assert.doesNotMatch(error.message, /HTTP|422|unprocessable|not changed/i);
      return true;
    },
  );
});

test('exact pending variant receipt survives reload and is cleared only by identity', () => {
  const values = new Map();
  const storage = {
    getItem: (key) => values.get(key) ?? null,
    setItem: (key, value) => values.set(key, value),
    removeItem: (key) => values.delete(key),
  };
  const pending = {
    schema_version: 'integrated_content_pending_variant/v1',
    job_id: 'job-resume-1',
    card_id: 'job-resume-1',
    post_id: 'post-1',
    parent_revision_id: 'revision-1',
    platform: 'linkedin',
    created_at: new Date().toISOString(),
  };
  rememberPendingIntegratedVariantJob(pending, storage);
  assert.deepEqual(listPendingIntegratedVariantJobs(storage), [pending]);
  forgetPendingIntegratedVariantJob('different-job', storage);
  assert.deepEqual(listPendingIntegratedVariantJobs(storage), [pending]);
  forgetPendingIntegratedVariantJob(pending.job_id, storage);
  assert.deepEqual(listPendingIntegratedVariantJobs(storage), []);
});

const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const test = require('node:test');

const source = fs.readFileSync(path.join(__dirname, '..', 'app', 'inbox', 'page.tsx'), 'utf8');

test('Inbox reports provider readiness without exposing account or local setup details', () => {
  assert.match(source, /Gmail is connected\. Sync can pull the owner-authorized inbox/);
  assert.match(source, /No account identifier or local setup path is shown remotely/);
  assert.doesNotMatch(source, /providerStatus\.account_email/);
  assert.doesNotMatch(source, /providerStatus\.client_file/);
  assert.doesNotMatch(source, /providerStatus\.sync_query/);
  assert.doesNotMatch(source, /scripts\/connect_gmail_inbox\.py/);
  assert.doesNotMatch(source, /GOOGLE_GMAIL_ENABLE_DRAFTS/);
  assert.doesNotMatch(source, /GOOGLE_GMAIL_OAUTH_CLIENT_JSON/);
});

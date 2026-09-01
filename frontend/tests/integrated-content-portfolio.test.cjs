const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const test = require('node:test');

const root = path.resolve(__dirname, '..');
const component = fs.readFileSync(path.join(root, 'app/workspace/IntegratedContentPortfolio.tsx'), 'utf8');
const workspace = fs.readFileSync(path.join(root, 'app/workspace/WorkspaceClient.tsx'), 'utf8');

test('workspace renders the canonical integrated content portfolio', () => {
  assert.match(workspace, /<IntegratedContentPortfolio\s*\/>/);
  assert.match(component, /\/api\/workspace\/integrated-content/);
  assert.match(component, /Sources → Opportunities → Posts/);
});

test('portfolio exposes real states, lineage toggles, attribution, and exact copy', () => {
  assert.match(component, /'ready' \| 'empty' \| 'degraded' \| 'error'/);
  assert.match(component, /selectedByPost/);
  assert.match(component, /parent_revision_id/);
  assert.match(component, /content_sha256/);
  assert.match(component, /public_source_url/);
  assert.match(component, /revision\.body/);
  assert.match(component, /LinkedIn variant/);
  assert.match(component, /Instagram variant/);
  assert.match(component, /integrated-content\/variants/);
  assert.match(component, /Create post from this/);
  assert.match(component, /integrated-content\/owner-posts/);
  assert.match(component, /Discovery routes/);
  assert.match(component, /Merged source identities/);
  assert.match(component, /merged_source_aliases/);
  assert.match(component, /Evidence and named interpretations/);
  assert.match(component, /provenance_kind/);
  assert.match(component, /Complete source-to-decision lineage/);
  assert.match(component, /Draft job/);
  assert.match(component, /Canonical draft ready for owner review\. Nothing was published\./);
  assert.match(component, /Selected for scheduled canonical drafting/);
  assert.match(component, /Production receipt bound/);
  assert.match(component, /Remaining governed controller boundaries/);
  assert.match(component, /post\.variant_control_options\.map/);
  assert.match(component, /control\.label/);
  assert.match(component, /integrated-content\/manual-edits/);
  assert.match(component, /integrated-content\/learning-actions/);
  assert.match(component, /integrated-content\/owner-actions/);
  assert.match(component, /Save immutable edit/);
  assert.match(component, /Select exact variant/);
  assert.match(component, /Reject exact variant/);
  assert.match(component, /Approve exact revision/);
  assert.match(component, /Confirm exact published revision/);
  assert.match(component, /integrityConfirmation/);
  assert.match(component, /publicationForm\.eventAt/);
  assert.match(component, /eventAt: currentLocalDateTimeInputValue\(\)/);
  assert.match(component, /getTimezoneOffset\(\)/);
  assert.match(component, /integrated-content\/persona-reversals/);
  assert.match(component, /integrated-content\/persona-actions/);
  assert.match(component, /Reverse exact persona promotion/);
  assert.match(component, /promotion\.canon_version/);
  assert.match(component, /resolveOwnerPostThesis/);
  assert.match(component, /Canonical content learning receipts/);
  assert.match(component, /gated content-lifecycle count, not a measure of all AI Clone learning/);
  assert.doesNotMatch(component, />Learning events</);
  assert.doesNotMatch(component, /raw_path|transcript_body|evidence_binding_json/);
});

test('variant controls fail closed on runtime or exact-parent readiness and lock double taps', () => {
  assert.match(component, /variant_generation\?: \{/);
  assert.match(component, /controller_capabilities\.variant_generation === true/);
  assert.match(component, /revision\?\.variant_generation\?\.eligible === true/);
  assert.match(component, /disabled=\{generationBusy \|\| !variantGenerationReady\}/);
  assert.match(component, /variantActionLocks\.current\.has\(post\.post_id\)/);
  assert.match(component, /variantActionLocks\.current\.add\(post\.post_id\)/);
  assert.match(component, /variantActionLocks\.current\.delete\(post\.post_id\)/);
  assert.match(component, /Owner edit ·/);
  assert.match(component, /approved remote-safe input binding/);
  assert.match(component, /rememberPendingIntegratedVariantJob/);
  assert.match(component, /listPendingIntegratedVariantJobs/);
});

test('published posts cannot queue unusable variants and explain the lifecycle boundary', () => {
  assert.match(component, /const PUBLISHED_VARIANT_MESSAGE = 'This post is already published\./);
  assert.match(component, /if \(post\.status === 'published'\)/);
  assert.match(component, /const postPublished = post\.status === 'published'/);
  assert.match(component, /!postPublished\s*&& projection\.controller_capabilities\.variant_generation === true/);
  assert.match(component, /disabled=\{generationBusy \|\| !variantGenerationReady\}/);
  assert.match(component, /cannot select or reject new post-publication revisions/);
});

test('content lineage stays inside a phone viewport even when canonical identifiers are long', () => {
  assert.match(component, /const panelStyle = \{[^\n]+minWidth: 0[^\n]+width: '100%'[^\n]+boxSizing: 'border-box'[^\n]+overflowWrap: 'anywhere'/);
  assert.match(component, /const cardStyle = \{[^\n]+minWidth: 0/);
  assert.match(component, /const nestedCardStyle = \{[^\n]+minWidth: 0[^\n]+overflowWrap: 'anywhere'/);
  assert.match(component, /const compactListStyle = \{[^\n]+minWidth: 0[^\n]+overflowWrap: 'anywhere'/);
  assert.match(component, /const selectStyle = \{[^\n]+width: 'min\(100%, 240px\)'[^\n]+maxWidth: '100%'[^\n]+minWidth: 0[^\n]+boxSizing: 'border-box'/);
});

# Truth Lane Cleanup Decision

## Decision

Cleanup mode: `forward_only_with_audit`

The system will **not** rebuild or rewrite historical runtime memory by default right now.

Instead it will:

1. keep the hardened forward path in place,
2. audit historical runtime memory for suspicious conversation-derived residue,
3. surface that audit through Brain,
4. only quarantine or rebuild selected files if the residue starts contaminating primary coordination surfaces again.

## Why

The current contamination problem is real, but the cost of rewriting historical memory is also real.

Right now the higher-value move is:

- stop new contamination,
- expose the historical residue honestly,
- keep operators aware of where trust is weaker,
- and only pay the rebuild cost when it becomes operationally necessary.

This is the smallest decision that improves truth quality without reopening the whole memory substrate immediately.

## What counts as suspicious residue

Examples include:

- raw user request language appearing in durable memory lanes
- assistant interpretive phrasing presented as durable truth
- Codex Chronicle memory-promotion sections that still carry conversational language instead of stable operating facts

## Trigger to escalate from audit to rebuild

Escalate to targeted quarantine or rebuild if one of these happens:

1. suspect runtime-memory residue is promoted back into standups, PM recommendations, or content-safe/public drafting context,
2. operators cannot reliably distinguish verified operating truth from conversation-derived residue,
3. the audit shows growth instead of containment over repeated review windows.

## Current operator rule

Treat runtime memory as:

- useful continuity context,
- but not automatically equivalent to verified truth.

When there is tension between runtime memory and verified artifacts, prefer:

1. PM state
2. execution-result write-back
3. mounted/live automation truth
4. explicit durable docs
5. runtime memory residue last

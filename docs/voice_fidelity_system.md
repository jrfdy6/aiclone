# Owner voice fidelity system

The content generator now treats owner voice as a provenance-controlled local dataset, not a list of catchphrases.

## Safety boundary

- Positive examples must be `human_published` or `human_edited`.
- Every positive example must be explicitly `approved` or `verified`.
- The Codex bridge is a cloud-inference path. It can use only `public` or `cloud_ok_excerpt` examples.
- `local_only` examples are eligible only for a future on-device inference path.
- `sensitive`, generated, outside-author, and unapproved text never enters a positive prompt.
- Full reference text stays inside the local worker process. Remote diagnostics contain IDs, modes, counts, scores, and a digest—not the corpus text.
- Approved outside creators live in a separate influence library. They contribute abstract techniques, never owner-authorship evidence.

The default corpus is:

`~/.codex/ai-clone/state/persona/voice_corpus.jsonl`

It can be overridden with `AI_CLONE_VOICE_CORPUS_PATH`, or moved with the rest of local state using `AI_CLONE_STATE_ROOT`.

The optional influence library is:

`~/.codex/ai-clone/state/persona/voice_influences.jsonl`

The initial approved cards abstract EYL transcript techniques such as accessible concept ladders, balanced contrast, question-led operator thinking, community-before-transaction framing, and brick-by-brick candor. They explicitly prohibit copying EYL slogans, co-host banter, or speaker-specific verbal tics.

## Generation path

1. The server plans the topic, proof, and optional story.
2. The local bridge retrieves up to four complete, relevant owner examples with deterministic BM25 ranking and diversity.
3. It may add up to two approved outside-influence technique cards as a secondary layer.
4. The prompt tells the writer to learn owner rhythm and range while forbidding facts or exact phrasing from the examples, and makes owner references override outside influence.
5. Codex writes the drafts.
6. Only public-release safety cleanup runs. The old deterministic house-style rewrite is skipped for Codex drafts.
7. The existing grounding/taste gate evaluates the actual writer output.
8. A separate voice-fidelity scorer runs in shadow mode and records structure, rhythm, copy-overlap, and catchphrase diagnostics.

Ollama semantic retrieval is an opt-in experiment, not a production dependency. Repeated live checks showed that the local Ollama service could time out in normal use, so the default remains the fast, deterministic lexical path. When explicitly enabled, it has a short timeout, falls back to BM25, and opens a five-minute circuit breaker after a failure so it cannot repeatedly delay generation. The embedding endpoint is restricted to loopback hosts, so owner text cannot be sent to a remote embedding server by configuration mistake. Controls:

- `AI_CLONE_VOICE_SEMANTIC_RETRIEVAL=true` enables the optional experiment.
- `AI_CLONE_VOICE_EMBEDDING_MODEL=embeddinggemma` selects the local model.
- `AI_CLONE_VOICE_EMBEDDING_URL=http://127.0.0.1:11434/api/embed` selects the loopback endpoint.
- `AI_CLONE_VOICE_EMBEDDING_TIMEOUT_SECONDS=1.5` controls the fail-fast timeout.
- `AI_CLONE_VOICE_EMBEDDING_BACKOFF_SECONDS=300` controls the failure circuit breaker.

This is also the system-wide reliability rule. Direct content generation defaults
to configured OpenAI or Gemini providers and will not silently attempt Ollama.
Ollama content generation requires both
`CONTENT_GENERATION_ENABLE_OLLAMA=true` and an explicit `ollama` entry in
`CONTENT_GENERATION_PROVIDER_ORDER`. The NEO guest worker normally renders its
approved public knowledge packet without any model call; its loopback fallback
requires `NEO_ENABLE_OLLAMA=true`. If Ollama is disabled and a legacy NEO packet
is missing its approved response, the worker fails closed instead of hanging or
inventing an ungrounded answer.

Shadow scoring deliberately does not reject or reorder posts yet. It needs enough owner decisions to establish a trustworthy threshold.

## Feedback path

The system can store an exact generated→owner-edited pair locally and, only with explicit promotion, add the final edit as `human_edited`. It also records rejected alternatives so later ranking can learn what the owner chose and what they declined.

Generated Codex options already enter the existing FEEZIE owner-review lane. For those cards, the same review surface now includes a **Private voice-learning edit** field. The browser keeps that field out of the Railway decision request. After a successful Approve, Revise, or Park decision, it creates a local JSON download instead:

- Approve captures the generated draft and the current private edit as an acceptance decision.
- Revise captures the exact generated→edited pair and the owner notes.
- Park discards any edit and records the exact generated draft as rejected.
- Every packet is `local_only` and hard-codes `promote_edited: false`.

Unselected sibling options are not silently labeled rejected. A preference becomes negative only when the owner explicitly Parks that generated review item (or supplies a rejected file through the lower-level command).

Import one downloaded packet on the Mac:

```bash
python3 scripts/voice_fidelity.py import-review \
  --packet-file ~/Downloads/ai-clone-voice-review-FEEZIE-CODEX-123.json
```

The importer accepts only the `ai_clone_voice_review/v1` schema from `feezie_owner_review`, refuses symlinks and oversized files, rejects any non-`local_only` privacy value or promotion request, and writes only to the local `voice_preferences.jsonl` file with owner-only permissions. It does not delete the downloaded packet and does not write a positive corpus example.

This is an explicit browser-to-local handoff because the current FEEZIE UI is served by Railway while the preference store intentionally exists only on the owner’s computer. Sending the private edit through the existing review API would violate that boundary. The operational limitation is that this private edit teaches the local preference log but does not replace the cloud-backed review draft; use the normal review notes or copy the local edit when an operational revision is also needed.

The lower-level file command remains available when a generated draft, edit, and rejected options already exist as local files:

```bash
python3 scripts/voice_fidelity.py preference \
  --generated-file /path/to/generated.txt \
  --edited-file /path/to/final.txt \
  --rejected-file /path/to/rejected.txt \
  --privacy cloud_ok_excerpt \
  --promote-edited
```

Use `local_only` when the text may guide on-device evaluation but must not be sent to a cloud model. Use `sensitive` for archival capture that should not enter any generation prompt.

## Audit

```bash
python3 scripts/voice_fidelity.py audit
```

The audit reports:

- provenance, approval, and privacy counts;
- the examples retrieved for a representative query;
- a structural writing fingerprint;
- leave-one-published-post-out calibration;
- progress toward the initial 15-example minimum and stronger 30–50 example range.

The held-out score is a calibration baseline, not a guarantee of authorship quality. Human blind preference remains the deciding evaluation.

## Why this approach

Primary research and platform guidance consistently support:

- complete few-shot examples and explicit instructions before fine-tuning;
- retrieval that combines current intent with a stable global author representation;
- held-out evaluation and human preference data;
- preference optimization only after enough trustworthy pairs exist.

References:

- OpenAI prompt engineering: https://developers.openai.com/api/docs/guides/prompt-engineering
- OpenAI model optimization: https://developers.openai.com/api/docs/guides/model-optimization
- LaMP personalization benchmark: https://arxiv.org/abs/2304.11406
- Persona-Plug global plus retrieved user context: https://arxiv.org/abs/2409.11901
- Direct Preference Optimization: https://arxiv.org/abs/2305.18290
- Ollama embedding guidance: https://docs.ollama.com/capabilities/embeddings

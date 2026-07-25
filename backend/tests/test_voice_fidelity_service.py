from __future__ import annotations

import json
import stat
from pathlib import Path

import pytest

from app.services import voice_fidelity_service as service


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    path.write_text("\n".join(json.dumps(row) for row in rows) + "\n", encoding="utf-8")


def _entry(
    entry_id: str,
    text: str,
    *,
    provenance: str = "human_published",
    approval_status: str = "approved",
    privacy: str = "public",
    post_type: str = "commentary",
) -> dict:
    return {
        "id": entry_id,
        "text": text,
        "kind": "positive",
        "provenance": provenance,
        "approval_status": approval_status,
        "privacy": privacy,
        "channel": "linkedin",
        "post_type": post_type,
        "topic_tags": ["ai", "education"],
    }


def test_load_voice_corpus_enforces_provenance_approval_and_cloud_privacy(tmp_path: Path) -> None:
    corpus = tmp_path / "voice.jsonl"
    _write_jsonl(
        corpus,
        [
            _entry("public", "I learned this by doing the work. The handoff made the difference.", privacy="public"),
            _entry("cloud", "A clear system made the next decision easier. That is the lesson.", privacy="cloud_ok_excerpt"),
            _entry("local", "This personal story stays on my machine unless I explicitly change that.", privacy="local_only"),
            _entry("generated", "A model generated this text, so it must never become a positive voice example.", provenance="generated"),
            _entry("external", "Someone else wrote this, so it is evidence or inspiration, not my voice.", provenance="external"),
            _entry("pending", "I wrote this, but I have not approved it as a voice reference yet.", approval_status="pending"),
        ],
    )

    assert [entry["id"] for entry in service.load_voice_corpus(corpus, execution_mode="cloud")] == ["public", "cloud"]
    assert [entry["id"] for entry in service.load_voice_corpus(corpus, execution_mode="strict_local")] == [
        "public",
        "cloud",
        "local",
    ]


def test_select_voice_exemplars_uses_relevance_and_mode_diversity() -> None:
    entries = [
        _entry("education-1", "Students deserve clarity, not pressure. The right next step should fit the student.", post_type="event"),
        _entry("education-2", "Families need clarity about the next step. Students deserve a path that fits.", post_type="event"),
        _entry("ai", "The AI workflow turns market signal into a concrete decision and a useful next action.", post_type="commentary"),
        _entry("life", "A couple weeks ago, my role changed. I am grateful for the reset and ready to grow.", post_type="life_update"),
    ]

    selected = service.select_voice_exemplars(
        entries,
        query="AI market signal and workflow",
        limit=3,
        use_semantic=False,
    )

    assert selected[0]["id"] == "ai"
    assert len({entry["post_type"] for entry in selected}) >= 2


def test_render_prompt_keeps_complete_examples_and_blocks_fact_copying() -> None:
    entry = _entry(
        "published-1",
        "There is no single right path.\n\nStudents deserve clarity, not pressure.",
        post_type="event",
    )

    prompt = service.render_voice_reference_prompt([entry])

    assert "There is no single right path.\n\nStudents deserve clarity, not pressure." in prompt
    assert "every fact, name, event, organization" in prompt
    assert "Do not force a catchphrase" in prompt
    assert "Do not copy an eight-word sequence" in prompt


def test_voice_score_penalizes_stock_phrase_repetition_and_copying() -> None:
    exemplars = [
        "A couple weeks ago, my role changed. I am grateful for the reset.\n\nToday, I am ready to grow.",
        "Students deserve clarity, not pressure.\n\nThe next step should truly fit.",
    ]
    natural = "I spent the week looking at where the handoff slowed down.\n\nThe answer was simple: the next step was not clear."
    copied = (
        "Students deserve clarity, not pressure. The next step should truly fit.\n\n"
        "That is the operating model. That is the operating model."
    )

    natural_score = service.score_voice_fidelity(natural, exemplars=exemplars)
    copied_score = service.score_voice_fidelity(copied, exemplars=exemplars)

    assert natural_score["score"] is not None
    assert copied_score["score"] < natural_score["score"]
    assert any(warning.startswith("possible_exemplar_copy:") for warning in copied_score["warnings"])
    assert any(warning.startswith("stock_phrase:") for warning in copied_score["warnings"])


def test_public_diagnostics_never_expose_example_text(tmp_path: Path) -> None:
    corpus = tmp_path / "voice.jsonl"
    secret_text = "This is an approved public writing sample with enough detail to be a complete example."
    _write_jsonl(corpus, [_entry("one", secret_text)])

    context = service.build_voice_context(query="writing sample", path=corpus, use_semantic=False)
    diagnostics = service.public_voice_diagnostics(context)

    assert context["_local_exemplars"][0]["text"] == secret_text
    assert secret_text not in json.dumps(diagnostics)
    assert diagnostics["reference_ids"] == ["one"]


def test_audit_reports_target_gap_without_promoting_unsafe_records(tmp_path: Path) -> None:
    corpus = tmp_path / "voice.jsonl"
    _write_jsonl(
        corpus,
        [
            _entry("one", "I learned something useful from this project, and I want to make the lesson concrete."),
            _entry("unsafe", "This generated draft cannot count toward the verified corpus target.", provenance="generated"),
        ],
    )

    audit = service.audit_voice_corpus(corpus)

    assert audit["counts"]["valid_json"] == 2
    assert audit["counts"]["cloud_eligible"] == 1
    assert audit["minimum_recommended_met"] is False


def test_record_voice_preference_promotes_only_material_human_edit(tmp_path: Path) -> None:
    preference_path = tmp_path / "preferences.jsonl"
    corpus_path = tmp_path / "corpus.jsonl"
    result = service.record_voice_preference(
        generated_text="This generated draft is long enough, but it still sounds like generic system copy.",
        edited_text="I kept coming back to one thing: the handoff was making the decision harder than it needed to be.",
        rejected_texts=["That is the operating model. Operator clarity wins."],
        context={"channel": "linkedin", "post_type": "direct_commentary", "topic_tags": ["systems"]},
        privacy="cloud_ok_excerpt",
        promote_edited=True,
        corpus_path=corpus_path,
        preference_path=preference_path,
    )

    assert result["created"] is True
    promoted = service.load_voice_corpus(corpus_path, execution_mode="cloud")
    assert len(promoted) == 1
    assert promoted[0]["provenance"] == "human_edited"
    assert "I kept coming back" in promoted[0]["text"]


def test_local_review_packet_records_exact_edit_and_rejection_without_promotion(tmp_path: Path) -> None:
    packet_path = tmp_path / "ai-clone-voice-review-FEEZIE-CODEX-1.json"
    preference_path = tmp_path / "private" / "voice_preferences.jsonl"
    generated = "Most AI advice stops at the prompt. The real work starts when the handoff has to hold up."
    edited = "I keep coming back to the handoff. If it falls apart there, the prompt was never the whole system."
    packet_path.write_text(
        json.dumps(
            {
                "schema_version": service.VOICE_REVIEW_PACKET_SCHEMA_VERSION,
                "source": service.VOICE_REVIEW_PACKET_SOURCE,
                "privacy": "local_only",
                "promote_edited": False,
                "decision": "revise",
                "queue_id": "FEEZIE-CODEX-1",
                "generation_job_id": "job-1",
                "generation_option_index": 2,
                "generated_text": generated,
                "edited_text": edited,
                "rejected_texts": ["Operator clarity wins. That is the operating model."],
                "context": {
                    "channel": "linkedin",
                    "post_type": "owner_review",
                    "topic": "AI workflow handoffs",
                    "topic_tags": ["AI", "systems"],
                    "owner_notes": "Keep the opening more conversational.",
                },
            }
        ),
        encoding="utf-8",
    )

    result = service.import_local_voice_review_packet(packet_path, preference_path=preference_path)

    assert result["created"] is True
    assert result["promoted"] is False
    assert result["has_material_edit"] is True
    assert result["packet_retained"] is True
    stored = json.loads(preference_path.read_text(encoding="utf-8"))
    assert stored["generated_text"] == generated
    assert stored["edited_text"] == edited
    assert stored["rejected_texts"] == ["Operator clarity wins. That is the operating model."]
    assert stored["privacy"] == "local_only"
    assert stored["context"]["decision"] == "revise"
    assert stat.S_IMODE(preference_path.stat().st_mode) == 0o600
    assert not (preference_path.parent / "voice_corpus.jsonl").exists()


def test_local_review_packet_turns_explicit_park_into_rejected_text(tmp_path: Path) -> None:
    packet_path = tmp_path / "ai-clone-voice-review-park.json"
    preference_path = tmp_path / "voice_preferences.jsonl"
    generated = "This draft sounds polished, but it does not sound like the owner."
    packet_path.write_text(
        json.dumps(
            {
                "schema_version": service.VOICE_REVIEW_PACKET_SCHEMA_VERSION,
                "source": service.VOICE_REVIEW_PACKET_SOURCE,
                "privacy": "local_only",
                "promote_edited": False,
                "decision": "park",
                "generated_text": generated,
                "edited_text": "A browser edit must not override an explicit rejection.",
                "rejected_texts": [],
            }
        ),
        encoding="utf-8",
    )

    result = service.import_local_voice_review_packet(packet_path, preference_path=preference_path)

    stored = json.loads(preference_path.read_text(encoding="utf-8"))
    assert result["rejected_count"] == 1
    assert result["has_material_edit"] is False
    assert stored["edited_text"] is None
    assert stored["rejected_texts"] == [generated]


def test_local_review_packet_rejects_cloud_privacy_and_promotion_request(tmp_path: Path) -> None:
    base_packet = {
        "schema_version": service.VOICE_REVIEW_PACKET_SCHEMA_VERSION,
        "source": service.VOICE_REVIEW_PACKET_SOURCE,
        "privacy": "local_only",
        "promote_edited": False,
        "decision": "approve",
        "generated_text": "This generated draft is long enough to be reviewed without becoming owner-authored canon.",
    }
    preference_path = tmp_path / "voice_preferences.jsonl"

    for name, overrides, expected in (
        ("cloud.json", {"privacy": "cloud_ok_excerpt"}, "local_only"),
        ("promote.json", {"promote_edited": True}, "cannot promote"),
        ("source.json", {"source": "remote_review_api"}, "source is not trusted"),
    ):
        packet_path = tmp_path / name
        packet_path.write_text(json.dumps({**base_packet, **overrides}), encoding="utf-8")
        try:
            service.import_local_voice_review_packet(packet_path, preference_path=preference_path)
        except ValueError as exc:
            assert expected in str(exc)
        else:
            raise AssertionError(f"unsafe review packet {name} was accepted")

    assert not preference_path.exists()


def test_local_review_packet_refuses_symlink(tmp_path: Path) -> None:
    target = tmp_path / "target.json"
    target.write_text("{}", encoding="utf-8")
    packet_path = tmp_path / "ai-clone-voice-review-link.json"
    packet_path.symlink_to(target)

    try:
        service.import_local_voice_review_packet(packet_path, preference_path=tmp_path / "preferences.jsonl")
    except ValueError as exc:
        assert "safely" in str(exc)
    else:
        raise AssertionError("symlinked review packet was accepted")


def test_append_voice_example_rejects_generated_positive(tmp_path: Path) -> None:
    try:
        service.append_voice_example(
            text="This model-generated sentence must not silently teach the system how the owner writes.",
            provenance="generated",
            approval_status="approved",
            privacy="public",
            path=tmp_path / "corpus.jsonl",
        )
    except ValueError as exc:
        assert "human_published or human_edited" in str(exc)
    else:
        raise AssertionError("generated text was incorrectly accepted as owner voice")


def test_fingerprint_counts_curly_apostrophe_contractions() -> None:
    fingerprint = service.build_writing_fingerprint(["I’m grateful for what we’ve learned. We’re ready to grow."])

    assert fingerprint["contraction_rate"] > 0


def test_external_influence_stays_secondary_and_out_of_authorship_score(tmp_path: Path) -> None:
    corpus_path = tmp_path / "voice.jsonl"
    influence_path = tmp_path / "influences.jsonl"
    owner_text = "I learned this by building the system myself. The useful part was seeing where the handoff broke."
    _write_jsonl(corpus_path, [_entry("owner", owner_text)])
    _write_jsonl(
        influence_path,
        [
            {
                "id": "eyl-problem-solving",
                "provenance": "external_influence",
                "approval_status": "approved",
                "privacy": "public",
                "source_name": "EYL transcript",
                "techniques": ["Move from the big idea to a plain-language first step."],
                "avoid": ["Do not borrow slogans."],
                "topic_tags": ["education", "systems"],
            }
        ],
    )

    context = service.build_voice_context(
        query="systems and education",
        path=corpus_path,
        influence_path=influence_path,
        use_semantic=False,
    )

    assert context["corpus_count"] == 1
    assert context["influence_count"] == 1
    assert context["influence_ids"] == ["eyl-problem-solving"]
    assert "not evidence of the owner's vocabulary" in context["prompt_block"]
    assert "Do not imitate a named speaker" in context["prompt_block"]
    diagnostics = service.public_voice_diagnostics(context)
    assert owner_text not in json.dumps(diagnostics)


def test_external_influence_is_not_used_without_owner_examples(tmp_path: Path) -> None:
    corpus_path = tmp_path / "missing-owner-corpus.jsonl"
    influence_path = tmp_path / "influences.jsonl"
    _write_jsonl(
        influence_path,
        [
            {
                "id": "eyl-technique",
                "provenance": "external_influence",
                "approval_status": "approved",
                "privacy": "public",
                "source_name": "EYL transcript",
                "techniques": ["Explain the big idea with a concrete first step."],
            }
        ],
    )

    context = service.build_voice_context(
        query="make this practical",
        path=corpus_path,
        influence_path=influence_path,
        use_semantic=False,
    )

    assert context["corpus_count"] == 0
    assert context["influence_count"] == 0
    assert context["prompt_block"] == ""


def test_private_voice_append_uses_owner_only_file_permissions(tmp_path: Path) -> None:
    corpus_path = tmp_path / "private" / "voice.jsonl"

    service.append_voice_example(
        text="I learned this by doing the work, and the next decision became much clearer.",
        provenance="human_published",
        approval_status="verified",
        privacy="public",
        path=corpus_path,
    )

    assert stat.S_IMODE(corpus_path.stat().st_mode) == 0o600


def test_external_embedding_endpoint_is_refused(monkeypatch) -> None:
    monkeypatch.setenv("AI_CLONE_VOICE_EMBEDDING_URL", "https://example.com/api/embed")

    assert service._ollama_embedding_endpoint() is None


def test_semantic_retrieval_is_opt_in(monkeypatch) -> None:
    monkeypatch.delenv("AI_CLONE_VOICE_SEMANTIC_RETRIEVAL", raising=False)

    assert service._semantic_retrieval_enabled() is False


@pytest.mark.parametrize("value", ["", "tru", "enabled-ish", "false", "0"])
def test_semantic_retrieval_fails_closed_for_blank_or_unrecognized_values(
    monkeypatch,
    value: str,
) -> None:
    monkeypatch.setenv("AI_CLONE_VOICE_SEMANTIC_RETRIEVAL", value)

    assert service._semantic_retrieval_enabled() is False


@pytest.mark.parametrize("value", ["1", "true", "yes", "on", "enabled"])
def test_semantic_retrieval_accepts_only_explicit_true_values(monkeypatch, value: str) -> None:
    monkeypatch.setenv("AI_CLONE_VOICE_SEMANTIC_RETRIEVAL", value)

    assert service._semantic_retrieval_enabled() is True


def test_semantic_failure_falls_back_to_lexical(monkeypatch) -> None:
    entries = [
        _entry("systems", "The workflow turns scattered signal into a useful next decision."),
        _entry("students", "Students deserve clarity about the path in front of them."),
    ]
    monkeypatch.setattr(service, "_ollama_embeddings", lambda _texts: None)

    selected, diagnostics = service._select_voice_exemplars(
        entries,
        query="workflow signal",
        limit=1,
        use_semantic=True,
    )

    assert selected[0]["id"] == "systems"
    assert diagnostics["mode"] == "lexical_bm25"

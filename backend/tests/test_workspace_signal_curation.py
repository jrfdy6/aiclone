from __future__ import annotations

import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock


ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_ROOT = ROOT / "scripts"
RUNNERS_ROOT = SCRIPTS_ROOT / "runners"
BACKEND_ROOT = ROOT / "backend"


def _load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Unable to load module from {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class WorkspaceSignalCurationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        if str(SCRIPTS_ROOT) not in sys.path:
            sys.path.insert(0, str(SCRIPTS_ROOT))
        if str(RUNNERS_ROOT) not in sys.path:
            sys.path.insert(0, str(RUNNERS_ROOT))
        if str(BACKEND_ROOT) not in sys.path:
            sys.path.insert(0, str(BACKEND_ROOT))
        cls.build_standup = _load_module("build_standup_prep", SCRIPTS_ROOT / "build_standup_prep.py")
        cls.promote = _load_module("promote_standup_packet", SCRIPTS_ROOT / "promote_standup_packet.py")
        cls.instagram_feedback = _load_module(
            "instagram_public_feedback_service",
            BACKEND_ROOT / "app" / "services" / "instagram_public_feedback_service.py",
        )
        cls.jean = _load_module(
            "run_jean_claude_execution",
            SCRIPTS_ROOT / "runners" / "run_jean_claude_execution.py",
        )
        cls.workspace_agent = _load_module(
            "run_workspace_agent",
            SCRIPTS_ROOT / "runners" / "run_workspace_agent.py",
        )
        cls.signal_quality = _load_module("chronicle_signal_quality", SCRIPTS_ROOT / "chronicle_signal_quality.py")
        cls.chronicle = _load_module("chronicle_memory_contract", SCRIPTS_ROOT / "chronicle_memory_contract.py")
        cls.progress_gate = _load_module("progress_pulse_gate", SCRIPTS_ROOT / "progress_pulse_gate.py")
        cls.digest_quality = _load_module("cron_digest_quality", SCRIPTS_ROOT / "cron_digest_quality.py")
        cls.morning_brief = _load_module("build_morning_daily_brief", SCRIPTS_ROOT / "build_morning_daily_brief.py")
        cls.sync_chronicle = _load_module("sync_codex_chronicle", SCRIPTS_ROOT / "sync_codex_chronicle.py")
        cls.fallback_watchdog = _load_module("fallback_watchdog", SCRIPTS_ROOT / "fallback_watchdog.py")
        cls.durable = _load_module("durable_memory_context", SCRIPTS_ROOT / "durable_memory_context.py")

    def test_load_strategy_context_reads_workspace_pack_signals(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            workspace_root = Path(temp_dir)
            (workspace_root / "CHARTER.md").write_text("# Charter\nProtect the lane.\n", encoding="utf-8")
            (workspace_root / "IDENTITY.md").write_text(
                "\n".join(
                    [
                        "# IDENTITY.md - Fusion Systems Operator",
                        "",
                        "- Is not: executive leadership or a cross-workspace planner",
                        "- Operating boundary: execute inside `fusion-os` only",
                    ]
                )
                + "\n",
                encoding="utf-8",
            )
            (workspace_root / "SOUL.md").write_text(
                "\n".join(
                    [
                        "# SOUL.md - Fusion Systems Operator",
                        "",
                        "- Protect trust with families and partners",
                        "- Clean handoffs and artifact-backed status",
                    ]
                )
                + "\n",
                encoding="utf-8",
            )
            (workspace_root / "USER.md").write_text(
                "\n".join(
                    [
                        "# USER.md - Fusion Preferences",
                        "",
                        "- Keep all Fusion work inside `fusion-os`.",
                        "- Accept Jean-Claude SOPs, execute locally, and report back clearly.",
                    ]
                )
                + "\n",
                encoding="utf-8",
            )
            registry = {"fusion-os": {"filesystem_path": str(workspace_root), "display_name": "Fusion OS"}}
            missing_inferred = workspace_root / "missing.md"
            with mock.patch.object(self.build_standup, "INFERRED_BRIEF_PATH", missing_inferred):
                context = self.build_standup._load_strategy_context("fusion-os", registry)

        self.assertEqual(context["identity_path"], str(workspace_root / "IDENTITY.md"))
        self.assertEqual(context["soul_path"], str(workspace_root / "SOUL.md"))
        self.assertEqual(context["user_path"], str(workspace_root / "USER.md"))
        self.assertEqual(context["lane_boundary"], "Keep all Fusion work inside `fusion-os`")
        self.assertEqual(context["trust_constraint"], "Protect trust with families and partners")
        self.assertIn("report back clearly", context["execution_posture"])

    def test_workspace_prep_filters_shared_ops_chronicle_noise(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            chronicle_path = Path(temp_dir) / "chronicle.jsonl"
            entries = [
                {"workspace_key": "fusion-os", "summary": "Fusion-local signal"},
                {"workspace_key": "shared_ops", "summary": "Executive residue"},
                {"workspace_key": "agc", "summary": "Another workspace"},
            ]
            chronicle_path.write_text(
                "".join(json.dumps(entry) + "\n" for entry in entries),
                encoding="utf-8",
            )
            with mock.patch.object(self.build_standup, "CODEX_CHRONICLE_PATH", chronicle_path):
                filtered = self.build_standup._filter_chronicle_entries("fusion-os", 8)

        self.assertEqual([entry["workspace_key"] for entry in filtered], ["fusion-os"])

    def test_chronicle_contract_requires_explicit_opt_in_for_shared_ops(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            chronicle_path = Path(temp_dir) / "chronicle.jsonl"
            entries = [
                {"workspace_key": "fusion-os", "summary": "Fusion-local signal"},
                {"workspace_key": "shared_ops", "summary": "Executive residue"},
            ]
            chronicle_path.write_text(
                "".join(json.dumps(entry) + "\n" for entry in entries),
                encoding="utf-8",
            )

            local_only = self.chronicle.filter_recent_chronicle_entries(
                "fusion-os",
                path=chronicle_path,
            )
            with_shared = self.chronicle.filter_recent_chronicle_entries(
                "fusion-os",
                path=chronicle_path,
                include_shared_ops=True,
            )

        self.assertEqual([entry["workspace_key"] for entry in local_only], ["fusion-os"])
        self.assertEqual([entry["workspace_key"] for entry in with_shared], ["fusion-os", "shared_ops"])

    def test_chronicle_contract_canonicalizes_raw_workspace_routing_text(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            chronicle_path = Path(temp_dir) / "chronicle.jsonl"
            entry = {
                "workspace_key": "fusion-os",
                "summary": "love it . review my entire system and create thorough plan to execute on this",
                "decisions": [
                    "so he will need to have all of th ai clone inform what he brings to a particulr workspace( in this case fusion os) but only give the relevent information in the stand ups."
                ],
            }
            chronicle_path.write_text(json.dumps(entry) + "\n", encoding="utf-8")

            filtered = self.chronicle.filter_recent_chronicle_entries("fusion-os", path=chronicle_path)

        self.assertEqual(len(filtered), 1)
        self.assertEqual(
            filtered[0]["decisions"][0],
            "Jean-Claude should use whole-system AI Clone context to inform each workspace while only routing workspace-relevant signal into standups.",
        )

    def test_build_bundle_keeps_executive_context_separate_from_workspace_context(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            workspace_root = Path(temp_dir)
            registry = {
                "fusion-os": {
                    "filesystem_path": str(workspace_root),
                    "display_name": "Fusion OS",
                    "target_agent": "Fusion Systems Operator",
                    "workspace_agent": "Fusion Systems Operator",
                }
            }

            def fake_memory_contract(workspace_key: str, **_: object) -> dict[str, object]:
                if workspace_key == "shared_ops":
                    return {
                        "chronicle_entries": [{"workspace_key": "shared_ops", "summary": "Executive signal"}],
                        "durable_memory_context": {"results": []},
                        "memory_context": {"persistent_state_tail": ""},
                        "source_paths": ["/tmp/shared_ops.md"],
                    }
                return {
                    "chronicle_entries": [{"workspace_key": "fusion-os", "summary": "Fusion signal"}],
                    "durable_memory_context": {"results": []},
                    "memory_context": {"persistent_state_tail": ""},
                    "source_paths": ["/tmp/fusion.md"],
                }

            with mock.patch.object(self.jean, "build_workspace_memory_contract", side_effect=fake_memory_contract):
                bundle = self.jean._build_bundle(
                    SimpleNamespace(goal="Test", time_budget_minutes=25, model="test-model", dry_run=True),
                    "run-1",
                    {"workspace_key": "fusion-os", "title": "Scoped work", "reason": "Need a bounded handoff."},
                    {"title": "Scoped work", "payload": {}},
                    registry,
                )

        self.assertEqual(bundle["recent_chronicle_entries"][0]["workspace_key"], "fusion-os")
        self.assertEqual(bundle["executive_context"]["recent_chronicle_entries"][0]["workspace_key"], "shared_ops")
        self.assertEqual(bundle["source_paths"], ["/tmp/fusion.md"])

    def test_build_sop_keeps_direct_reroutes_on_jean_claude(self) -> None:
        bundle = {
            "queue_entry": {
                "execution_mode": "direct",
                "target_agent": "Fusion Systems Operator",
                "workspace_agent": "Fusion Systems Operator",
                "card_id": "card-1",
                "title": "Return delegated lane to direct execution",
                "reason": "Manager should handle the closure directly.",
            },
            "pm_card": {"payload": {}, "source": "test-source", "link_id": "standup-1"},
            "primary_workspace_key": "fusion-os",
            "registry_item": {
                "display_name": "Fusion OS",
                "target_agent": "Fusion Systems Operator",
                "workspace_agent": "Fusion Systems Operator",
            },
            "agent_pack": {},
            "workspace_pack": {},
        }

        sop = self.jean._build_sop(bundle)

        self.assertEqual(sop["execution_mode"], "direct")
        self.assertEqual(sop["target_agent"], "Jean-Claude")
        self.assertEqual(sop["workspace_agent"], "Fusion Systems Operator")
        self.assertIn("whole-system AI Clone context", sop["context_policy"]["manager_scope"])
        self.assertIn("Only route broader system context", sop["context_policy"]["relevance_rule"])

    def test_workspace_execution_contract_requires_local_citations(self) -> None:
        contract = self.workspace_agent._build_workspace_execution_contract(
            workspace_key="fusion-os",
            manager_briefing_path="/tmp/manager.md",
            latest_workspace_briefing_path="/tmp/workspace.md",
            execution_log_path="/tmp/execution_log.md",
            task_instructions=["Review the latest delegated proof."],
            acceptance_criteria=["Return a bounded status."],
            completion_contract={},
        )

        instructions = contract["instructions"]
        self.assertTrue(any("current Jean-Claude briefing" in item for item in instructions))
        self.assertTrue(any("latest workspace execution log" in item for item in instructions))
        requirements = contract["completion_contract"]["result_requirements"]
        self.assertTrue(requirements["require_briefing_citation"])
        self.assertTrue(requirements["require_execution_log_citation"])
        self.assertTrue(requirements["require_lane_constraint"])
        self.assertTrue(requirements["require_relevance_explanation_for_global_context"])
        self.assertTrue(requirements["require_exact_next_artifact_or_blocker"])
        self.assertEqual(
            contract["local_artifact_context"]["execution_log_path"],
            "/tmp/execution_log.md",
        )

    def test_workspace_agent_note_uses_pack_signals_and_artifacts(self) -> None:
        prep = {
            "workspace_key": "fusion-os",
            "workspace_context": {
                "latest_briefing_path": "/tmp/latest_briefing.md",
                "execution_log_path": "/tmp/execution_log.md",
                "audience_feedback_path": "/tmp/instagram_public_feedback_summary.json",
            },
            "strategy_context": {
                "lane_boundary": "Keep all Fusion work inside `fusion-os`",
                "trust_constraint": "Protect trust with families, students, and partners",
                "execution_posture": "Accept Jean-Claude SOPs, execute locally, and report back clearly",
            },
        }

        note = self.promote._workspace_agent_note(
            prep,
            ["Review `Fusion lane proof` and either close it or return it to execution."],
        )

        self.assertIn("execute inside `fusion-os` only", note)
        self.assertIn("/tmp/latest_briefing.md", note)
        self.assertIn("/tmp/execution_log.md", note)
        self.assertIn("/tmp/instagram_public_feedback_summary.json", note)
        self.assertIn("Protect trust with families, students, and partners", note)
        self.assertIn("exact next artifact or blocker", note)

    def test_instagram_public_feedback_snapshot_summarizes_visible_response(self) -> None:
        payload = {
            "data": {
                "user": {
                    "username": "fusionacademydc",
                    "full_name": "Fusion Academy Washington DC",
                    "biography": "Institutional voice here.",
                    "external_url": "https://linktr.ee/fusionwashingtondc",
                    "category_name": "Education",
                    "is_business_account": True,
                    "is_professional_account": True,
                    "edge_followed_by": {"count": 552},
                    "edge_follow": {"count": 209},
                    "edge_owner_to_timeline_media": {
                        "count": 401,
                        "edges": [
                            {
                                "node": {
                                    "id": "1",
                                    "__typename": "GraphImage",
                                    "shortcode": "ABC123",
                                    "taken_at_timestamp": 1774045563,
                                    "edge_liked_by": {"count": 12},
                                    "edge_media_to_comment": {"count": 3},
                                    "edge_media_to_caption": {"edges": [{"node": {"text": "Family clarity post"}}]},
                                }
                            },
                            {
                                "node": {
                                    "id": "2",
                                    "__typename": "GraphVideo",
                                    "shortcode": "XYZ789",
                                    "taken_at_timestamp": 1773442539,
                                    "edge_liked_by": {"count": 6},
                                    "edge_media_to_comment": {"count": 1},
                                    "edge_media_to_caption": {"edges": [{"node": {"text": "Partner credibility post"}}]},
                                }
                            },
                        ],
                    },
                }
            }
        }

        snapshot = self.instagram_feedback.build_snapshot_from_profile_payload(payload, "fusionacademydc", sample_size=12)

        self.assertEqual(snapshot["profile"]["followers"], 552)
        self.assertEqual(snapshot["recent_summary"]["sample_size"], 2)
        self.assertEqual(snapshot["recent_summary"]["average_visible_engagement"], 11)
        self.assertEqual(snapshot["recent_summary"]["top_post"]["shortcode"], "ABC123")
        self.assertEqual(snapshot["recent_posts"][0]["content_pillar"], "Family Clarity")
        self.assertEqual(snapshot["recent_posts"][1]["content_pillar"], "Partner Credibility")
        self.assertTrue(any(item["label"] == "Family Clarity" for item in snapshot["pillar_breakdown"]))
        self.assertTrue(any("4-post" in item for item in snapshot["recommended_next_focus"]))
        self.assertTrue(any("Public-only Instagram signal" in item for item in snapshot["limitations"]))

    def test_workspace_context_loads_public_audience_feedback_snapshot(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            workspace_root = Path(temp_dir)
            analytics_root = workspace_root / "analytics" / "instagram_public"
            analytics_root.mkdir(parents=True, exist_ok=True)
            summary_path = analytics_root / "instagram_public_feedback_summary.json"
            markdown_path = analytics_root / "instagram_public_feedback_summary.md"
            summary_path.write_text(
                json.dumps(
                    {
                        "generated_at": "2026-04-16T23:59:00Z",
                        "source": "instagram_public_web",
                        "profile": {"followers": 552},
                        "recent_summary": {"sample_size": 4, "average_visible_engagement": 6.5},
                    }
                ),
                encoding="utf-8",
            )
            markdown_path.write_text("# Snapshot\n", encoding="utf-8")
            registry = {"fusion-os": {"filesystem_path": str(workspace_root), "display_name": "Fusion OS"}}

            context = self.build_standup._workspace_context("fusion-os", registry)

        self.assertTrue(context["audience_feedback_available"])
        self.assertEqual(context["audience_feedback_path"], str(summary_path))
        self.assertEqual(context["audience_feedback_markdown_path"], str(markdown_path))

    def test_workspace_context_resolves_feezie_legacy_alias_without_registry(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            repo_root = Path(temp_dir)
            workspace_root = repo_root / "workspaces" / "linkedin-content-os"
            workspace_root.mkdir(parents=True)
            (workspace_root / "memory").mkdir()
            (workspace_root / "memory" / "execution_log.md").write_text("# Log\n\nFEEZIE proof exists.\n", encoding="utf-8")

            with mock.patch.object(self.build_standup, "WORKSPACE_ROOT", repo_root):
                context = self.build_standup._workspace_context("linkedin-os", {})

        self.assertTrue(context["available"])
        self.assertEqual(context["workspace_root"], str(workspace_root))
        self.assertEqual(context["execution_log_path"], str(workspace_root / "memory" / "execution_log.md"))

    def test_build_audience_response_uses_public_feedback_snapshot(self) -> None:
        workspace_context = {
            "audience_feedback_path": "/tmp/instagram_public_feedback_summary.json",
            "audience_feedback": {
                "profile": {"followers": 552},
                "recent_summary": {
                    "sample_size": 4,
                    "average_visible_likes": 5.5,
                    "average_visible_comments": 0.5,
                    "average_visible_engagement": 6.0,
                    "top_post": {
                        "shortcode": "ABC123",
                        "url": "https://www.instagram.com/p/ABC123/",
                        "visible_engagement": 9,
                    },
                },
                "limitations": ["Public-only Instagram signal."],
            },
        }

        lines = self.build_standup._build_audience_response(workspace_context)

        self.assertTrue(any("instagram_public_feedback_summary.json" in item for item in lines))
        self.assertTrue(any("avg_visible_engagement=6.0" in item for item in lines))
        self.assertTrue(any("ABC123" in item for item in lines))

    def test_build_standup_sections_for_fusion_uses_public_feedback_and_next_focus(self) -> None:
        sections = self.build_standup._build_standup_sections(
            "fusion-os",
            [{"workspace_key": "fusion-os", "summary": "Fusion local learning"}],
            {
                "audience_feedback": {
                    "recent_posts": [
                        {
                            "shortcode": "ABC123",
                            "taken_at": "2026-04-16T12:00:00Z",
                            "content_pillar": "Family Clarity",
                            "audience": "families",
                            "visible_engagement": 9,
                            "caption_excerpt": "Family clarity post",
                        }
                    ],
                    "signal_lines": ["Visible response is currently led by `Family Clarity`."],
                    "opportunity_signals": ["`Partner Credibility` has no recent visible post in the public sample."],
                    "recommended_next_focus": ["Ship a `Partner Credibility` post in the next cycle so the weekly mix stays balanced."],
                }
            },
            {"cards": [{"title": "Review Fusion lane", "status": "review"}]},
            ["Instagram public response: followers=552, recent_sample=4, avg_visible_engagement=6.0."],
            ["Review the live validation card."],
        )

        self.assertIn("signals_captured", sections)
        self.assertIn("content_produced", sections)
        self.assertIn("audience_response", sections)
        self.assertIn("opportunities_created", sections)
        self.assertIn("next_focus", sections)
        self.assertTrue(any("Family Clarity" in item for item in sections["content_produced"]))
        self.assertTrue(any("Partner Credibility" in item for item in sections["opportunities_created"]))
        self.assertTrue(any("Review Fusion lane" in item for item in sections["next_focus"]))

    def test_standup_cleanup_normalizes_raw_codex_history_language(self) -> None:
        entry = {
            "workspace_key": "fusion-os",
            "source": "codex-history",
            "summary": "Synced 2 new Codex history entries across 1 sessions, touching fusion-os. Latest signal: love it . review my entire system and create thorough plan to execute on this",
            "decisions": [
                "so he will need to have all of th ai clone inform what he brings to a particulr workspace( in this case fusion os) but only give the relevent information in the stand ups."
            ],
            "follow_ups": [
                "so he will need to have all of th ai clone inform what he brings to a particulr workspace( in this case fusion os) but only give the relevent information in the stand ups."
            ],
            "project_updates": [
                "I think a great place to start is with jean claude he will be executing in multiple wrkspaces and that is only going to increase in the future."
            ],
        }

        summary = self.build_standup._standup_chronicle_summary(entry)
        delta_lines = self.build_standup._build_artifact_deltas([entry], {}, {}, {})

        self.assertEqual(
            summary,
            "Recent Codex discussion for `fusion-os`: Jean-Claude should use whole-system AI Clone context to inform each workspace while only routing workspace-relevant signal into standups.",
        )
        self.assertTrue(
            any("Jean-Claude should use whole-system AI Clone context" in item for item in delta_lines),
        )
        self.assertFalse(any("so he will need" in item.lower() for item in delta_lines))

    def test_standup_cleanup_canonicalizes_fusion_prompt_dump_and_voice_rules(self) -> None:
        entry = {
            "workspace_key": "fusion-os",
            "source": "codex-history",
            "summary": "Synced 7 new Codex history entries across 3 sessions, touching fusion-os. Latest signal: excellent please let me know what you need to implement.",
            "decisions": [
                'Voice System All content must: - use institutional voice ("we") - represent Fusion Academy DC - NOT use first-person singular - be safe, clear, non-controversial - follow structure: Observation → Clarification → Guidance --- ### 6.'
            ],
            "blockers": [
                "--- ## CONTEXT (READ CAREFULLY) The current fusion-os workspace is internally inconsistent: - CHARTER.md defines Fusion OS as an operations system..."
            ],
            "follow_ups": [
                "excellent please let me know what you need to implement."
            ],
        }

        summary = self.build_standup._standup_chronicle_summary(entry)
        normalized_blocker = self.build_standup._normalize_standup_signal_text(entry["blockers"][0])
        normalized_follow_up = self.build_standup._normalize_standup_signal_text(entry["follow_ups"][0])

        self.assertEqual(
            summary,
            "Recent Codex discussion for `fusion-os`: Fusion content should use institutional voice, represent Fusion Academy DC, avoid first-person singular, and follow Observation -> Clarification -> Guidance.",
        )
        self.assertEqual(
            normalized_blocker,
            "Fusion OS needed a coherent content-and-signal operating model before weekly automation could be trusted.",
        )
        self.assertEqual(
            normalized_follow_up,
            "Implement the approved Fusion operating model and audience-feedback loop.",
        )

    def test_sync_chronicle_canonicalizes_cross_workspace_routing_signal(self) -> None:
        text = (
            "I think a great place to start is with jean claude he will be executing in multiple wrkspaces and that is only going to increase in the future."
        )

        normalized = self.sync_chronicle._canonicalize_discussion_signal(text)

        self.assertEqual(
            normalized,
            "Jean-Claude needs a routing contract for using whole-system context across multiple workspaces.",
        )

    def test_sync_chronicle_canonicalizes_fusion_prompt_dump(self) -> None:
        self.assertEqual(
            self.sync_chronicle._canonicalize_discussion_signal(
                "--- ## CONTEXT (READ CAREFULLY) The current fusion-os workspace is internally inconsistent: - CHARTER.md defines Fusion OS as an operations system..."
            ),
            "Fusion OS needed a coherent content-and-signal operating model before weekly automation could be trusted.",
        )
        self.assertEqual(
            self.sync_chronicle._canonicalize_discussion_signal(
                'Voice System All content must: - use institutional voice ("we") - represent Fusion Academy DC - NOT use first-person singular - follow structure: Observation -> Clarification -> Guidance.'
            ),
            "Fusion content should use institutional voice, represent Fusion Academy DC, avoid first-person singular, and follow Observation -> Clarification -> Guidance.",
        )

    def test_signal_quality_marks_acknowledgements_as_low_signal(self) -> None:
        self.assertTrue(self.signal_quality.is_low_signal_ack("ok please continue"))
        self.assertTrue(self.signal_quality.is_low_signal_ack("yes please do it"))
        self.assertFalse(self.signal_quality.is_low_signal_ack("could you give me a fresh deploy"))

    def test_progress_pulse_gate_ignores_low_signal_chronicle_entries(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_root = Path(temp_dir)
            run_log = temp_root / "runs.jsonl"
            handoff_log = temp_root / "handoff.jsonl"
            persistent_state = temp_root / "persistent_state.md"
            low_signal_entry = {
                "created_at": "2026-04-17T02:00:45Z",
                "summary": "Synced 2 new Codex history entries across 2 sessions, touching codex, chronicle. Latest signal: ok please continue",
                "signal_types": [],
                "decisions": [],
                "blockers": [],
                "project_updates": [],
                "follow_ups": [],
                "pm_candidates": [],
            }
            handoff_log.write_text(json.dumps(low_signal_entry) + "\n", encoding="utf-8")

            with mock.patch.object(self.progress_gate, "RUN_LOG", run_log), mock.patch.object(
                self.progress_gate, "HANDOFF_LOG", handoff_log
            ), mock.patch.object(self.progress_gate, "PERSISTENT_STATE", persistent_state):
                report = self.progress_gate.build_report()

        self.assertFalse(report["should_deliver"])
        self.assertEqual(report["material_handoff_count"], 0)

    def test_progress_pulse_gate_keeps_material_chronicle_entries(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_root = Path(temp_dir)
            run_log = temp_root / "runs.jsonl"
            handoff_log = temp_root / "handoff.jsonl"
            persistent_state = temp_root / "persistent_state.md"
            material_entry = {
                "created_at": "2026-04-17T03:30:47Z",
                "summary": "Synced 1 new Codex history entries across 1 sessions, touching shared_ops. Latest signal: still broken now",
                "signal_types": ["blocker"],
                "decisions": [],
                "blockers": ["still broken now"],
                "project_updates": [],
                "follow_ups": ["still broken now"],
                "pm_candidates": ["still broken now"],
            }
            handoff_log.write_text(json.dumps(material_entry) + "\n", encoding="utf-8")

            with mock.patch.object(self.progress_gate, "RUN_LOG", run_log), mock.patch.object(
                self.progress_gate, "HANDOFF_LOG", handoff_log
            ), mock.patch.object(self.progress_gate, "PERSISTENT_STATE", persistent_state):
                report = self.progress_gate.build_report()

        self.assertTrue(report["should_deliver"])
        self.assertEqual(report["material_handoff_count"], 1)
        self.assertEqual(report["latest_material_signal"], "still broken now")

    def test_progress_pulse_gate_rejects_stale_persistent_state_only(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_root = Path(temp_dir)
            run_log = temp_root / "runs.jsonl"
            handoff_log = temp_root / "handoff.jsonl"
            persistent_state = temp_root / "persistent_state.md"
            run_log.write_text(
                json.dumps(
                    {
                        "action": "finished",
                        "delivered": True,
                        "runAtMs": 1000,
                    }
                )
                + "\n",
                encoding="utf-8",
            )
            persistent_state.write_text(
                "\n".join(
                    [
                        "# Snapshot for April 9, 2026",
                        "",
                        "- Daily log input processing completed without errors.",
                        "- Latest heartbeats are syncing, ensuring ongoing stability.",
                    ]
                ),
                encoding="utf-8",
            )

            with mock.patch.object(self.progress_gate, "RUN_LOG", run_log), mock.patch.object(
                self.progress_gate, "HANDOFF_LOG", handoff_log
            ), mock.patch.object(self.progress_gate, "PERSISTENT_STATE", persistent_state):
                report = self.progress_gate.build_report()

        self.assertTrue(report["persistent_state_newer"])
        self.assertFalse(report["persistent_state_material"])
        self.assertFalse(report["should_deliver"])
        self.assertTrue(report["persistent_state_diagnostics"]["snapshot_heading_stale"])

    def test_digest_validator_accepts_structured_action_bearing_digest(self) -> None:
        digest = "\n".join(
            [
                "Progress Pulse — 2026-04-18 02:14 UTC",
                "Status: yellow",
                "What Changed:",
                "- `shared_ops`: Jean-Claude opened a direct execution lane for stale PM review.",
                "Why It Matters:",
                "- The review lane is now active on the PM board instead of living only in Chronicle.",
                "Action Now:",
                "- Owner: Jean-Claude",
                "- Next: write the execution result back into PM and Chronicle.",
                "Routing:",
                "- Workspace: shared_ops",
                "- Route: PM card `abc-123` (in_progress) -> executive standup `actions`.",
                "Source:",
                "- Chronicle: 2026-04-18T02:07:47Z jean-claude-dispatch `shared_ops`",
                "- Artifact: `/Users/neo/.openclaw/workspace/workspaces/shared-ops/dispatch/example.json`",
                "Alerts:",
                "- `persistent_state.md` is stale, so Chronicle stays primary for this digest.",
            ]
        )

        report = self.digest_quality.validate_digest("progress_pulse", digest)

        self.assertTrue(report.ok, report.issues)

    def test_digest_validator_rejects_boilerplate_and_missing_routing(self) -> None:
        digest = "\n".join(
            [
                "Morning Daily Brief — 2026-04-17",
                "What Changed:",
                "- Daily log input processing completed without errors.",
                "Why It Matters:",
                "- Latest heartbeats are syncing, ensuring ongoing stability.",
                "Action Now:",
                "- Owner: shared_ops",
                "- Next: no further action needed.",
                "Source:",
                "- Chronicle: latest signal.",
                "Alerts:",
                "- No additional actions required at this moment.",
            ]
        )

        report = self.digest_quality.validate_digest("morning_daily_brief", digest)

        self.assertFalse(report.ok)
        self.assertTrue(any("Missing required section `Routing`." == item for item in report.issues))
        self.assertTrue(any("banned boilerplate" in item for item in report.issues))

    def test_chronicle_memory_contract_flags_stale_persistent_state_boilerplate(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "persistent_state.md"
            path.write_text(
                "\n".join(
                    [
                        "# Snapshot for April 9, 2026",
                        "",
                        "- Daily log input processing completed without errors.",
                        "- Latest heartbeats are syncing, ensuring ongoing stability.",
                    ]
                )
                + "\n",
                encoding="utf-8",
            )

            diagnostics = self.chronicle.inspect_memory_path(
                path,
                relative_path="memory/persistent_state.md",
                now=self.chronicle.datetime(2026, 4, 17, tzinfo=self.chronicle.timezone.utc),
            )

        self.assertTrue(diagnostics["snapshot_heading_stale"])
        self.assertIn("Daily log input processing completed without errors.", diagnostics["boilerplate_flags"])
        self.assertIn("Latest heartbeats are syncing, ensuring ongoing stability.", diagnostics["boilerplate_flags"])

    def test_load_pm_context_prefers_api_as_primary_source(self) -> None:
        api_payload = [
            {
                "id": "card-1",
                "title": "Review fallback coverage",
                "owner": "Jean-Claude",
                "status": "review",
                "payload": {"workspace_key": "shared_ops"},
                "updated_at": "2026-04-17T02:00:00Z",
            }
        ]

        with mock.patch.object(self.build_standup, "_fetch_api_json", return_value=api_payload):
            context = self.build_standup._load_pm_context(
                {"pm_error": "db unavailable"},
                "shared_ops",
                "https://example.invalid",
            )

        self.assertTrue(context["available"])
        self.assertFalse(context["fallback_active"])
        self.assertEqual(context["source"], "pm_api")
        self.assertEqual(context["primary_source"], "pm_api")
        self.assertIn("/api/pm/cards?limit=100", context["source_ref"])

    def test_load_pm_context_marks_local_service_as_fallback_when_api_fails(self) -> None:
        class _Row:
            def model_dump(self, mode: str = "json") -> dict[str, object]:
                return {
                    "id": "card-2",
                    "title": "Review local fallback",
                    "owner": "Jean-Claude",
                    "status": "review",
                    "payload": {"workspace_key": "shared_ops"},
                    "updated_at": "2026-04-17T02:10:00Z",
                }

        with mock.patch.object(self.build_standup, "_fetch_api_json", side_effect=RuntimeError("api offline")):
            context = self.build_standup._load_pm_context(
                {"list_cards": lambda limit=100: [_Row()]},
                "shared_ops",
                "https://example.invalid",
            )

        self.assertTrue(context["available"])
        self.assertTrue(context["fallback_active"])
        self.assertEqual(context["source"], "pm_backend_service")
        self.assertEqual(context["fallback_reason"], "pm_api_error")
        self.assertEqual(context["primary_source"], "pm_api")
        self.assertEqual(context["primary_error"], "api offline")

    def test_load_automation_context_marks_delivery_hygiene_as_fallback(self) -> None:
        with mock.patch.object(
            self.build_standup,
            "_parse_delivery_hygiene_metrics",
            return_value={"source": "/tmp/openclaw_cron_delivery_hygiene.md", "mismatch_count": 2},
        ):
            context = self.build_standup._load_automation_context({"automation_error": "backend import failed"})

        self.assertFalse(context["available"])
        self.assertTrue(context["fallback_active"])
        self.assertEqual(context["source"], "delivery_hygiene_metrics")
        self.assertEqual(context["fallback_reason"], "automation_mismatch_service_unavailable")
        self.assertEqual(context["primary_source"], "automation_mismatch_service")
        self.assertEqual(context["source_ref"], "/tmp/openclaw_cron_delivery_hygiene.md")

    def test_durable_memory_context_resolves_qmd_binary_outside_shell_path(self) -> None:
        fake_completed = SimpleNamespace(returncode=0, stdout="", stderr="")
        with mock.patch.object(self.durable.shutil, "which", return_value=None), mock.patch.object(
            self.durable.Path, "exists", autospec=True, side_effect=lambda path_self: str(path_self) == "/usr/local/bin/qmd"
        ), mock.patch.object(self.durable.subprocess, "run", return_value=fake_completed) as run_mock:
            self.durable._run_qmd_search("fusion", "memory-dir-main", 2)

        command = run_mock.call_args.args[0]
        self.assertEqual(command[0], "/usr/local/bin/qmd")
        self.assertEqual(command[1:4], ["search", "fusion", "-c"])

    def test_progress_pulse_marks_persistent_state_only_delivery_as_fallback(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            run_log = Path(temp_dir) / "progress_pulse.jsonl"
            handoff_log = Path(temp_dir) / "handoff.jsonl"
            persistent_state = Path(temp_dir) / "persistent_state.md"
            run_log.write_text(
                json.dumps(
                    {
                        "action": "finished",
                        "delivered": True,
                        "runAtMs": 1,
                    }
                )
                + "\n",
                encoding="utf-8",
            )
            handoff_log.write_text("", encoding="utf-8")
            persistent_state.write_text("fresh state\n", encoding="utf-8")

            with mock.patch.object(self.progress_gate, "RUN_LOG", run_log), mock.patch.object(
                self.progress_gate, "HANDOFF_LOG", handoff_log
            ), mock.patch.object(self.progress_gate, "PERSISTENT_STATE", persistent_state):
                report = self.progress_gate.build_report()

        self.assertTrue(report["should_deliver"])
        self.assertTrue(report["persistent_state_newer"])
        self.assertTrue(report["delivery_fallback_active"])
        self.assertEqual(report["material_handoff_count"], 0)
        self.assertFalse(report["latest_handoff_is_material"])

    def test_standup_prep_routes_fallback_watchdog_into_blockers_and_sources(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            output_root = Path(temp_dir) / "standup-prep"
            memory_root = Path(temp_dir) / "memory"
            memory_root.mkdir(parents=True, exist_ok=True)

            def fake_resolve(_: Path, relative_path: str) -> Path:
                target = memory_root / relative_path
                target.parent.mkdir(parents=True, exist_ok=True)
                if not target.exists():
                    target.write_text("placeholder\n", encoding="utf-8")
                return target

            fallback_report = {
                "available": True,
                "active": True,
                "active_count": 2,
                "headline": "Fallback watchdog found 2 active fallback condition(s) across memory, retrieval, or delivery lanes.",
                "report_path": "/tmp/fallback_watchdog_latest.json",
                "source_paths": ["/tmp/fallback_watchdog_latest.json", "/tmp/runtime/persistent_state.md"],
                "followup_card": {
                    "title": "Executive resolve fallback usage in memory and retrieval lanes",
                    "status": "todo",
                },
            }

            with mock.patch.object(self.build_standup, "_optional_backend_imports", return_value={}), mock.patch.object(
                self.build_standup, "_read_registry", return_value={}
            ), mock.patch.object(
                self.build_standup,
                "_load_strategy_context",
                return_value={
                    "display_name": "Executive Interpretation Rule",
                    "default_routing": "Strong signal should usually go to canonical memory plus standup before PM.",
                    "charter_path": None,
                    "identity_path": None,
                    "soul_path": None,
                    "user_path": None,
                    "lane_boundary": "",
                    "trust_constraint": "",
                    "execution_posture": "",
                    "inferred_brief_path": None,
                },
            ), mock.patch.object(
                self.build_standup, "_filter_chronicle_entries", return_value=[]
            ), mock.patch.object(
                self.build_standup, "_load_pm_context", return_value={"available": False, "cards": [], "card_count": 0}
            ), mock.patch.object(
                self.build_standup,
                "_load_automation_context",
                return_value={"available": True, "mismatch_count": 0, "action_required_count": 0},
            ), mock.patch.object(
                self.build_standup, "_workspace_context", return_value={"available": False, "source_paths": []}
            ), mock.patch.object(
                self.build_standup,
                "build_durable_memory_context",
                return_value={"available": False, "result_count": 0, "source_paths": [], "queries": []},
            ), mock.patch.object(
                self.build_standup, "_load_fallback_watchdog_report", return_value=fallback_report
            ), mock.patch.object(
                self.build_standup, "resolve_snapshot_fallback_path", side_effect=fake_resolve
            ), mock.patch.object(
                self.build_standup, "maybe_reexec_with_workspace_venv", return_value=None
            ), mock.patch.object(
                sys,
                "argv",
                [
                    "build_standup_prep.py",
                    "--workspace-key",
                    "shared_ops",
                    "--output-root",
                    str(output_root),
                ],
            ):
                self.assertEqual(self.build_standup.main(), 0)

            json_outputs = sorted(output_root.rglob("*.json"))
            self.assertEqual(len(json_outputs), 1)
            prep = json.loads(json_outputs[0].read_text(encoding="utf-8"))

        self.assertTrue(prep["fallback_watchdog"]["active"])
        self.assertTrue(any("Fallback watchdog found 2 active fallback condition" in item for item in prep["blockers"]))
        self.assertTrue(
            any("Executive resolve fallback usage in memory and retrieval lanes" in item for item in prep["needs"])
        )
        self.assertIn("/tmp/fallback_watchdog_latest.json", prep["source_paths"])
        self.assertTrue(any("Fallback watchdog:" in item for item in prep["artifact_deltas"]))


if __name__ == "__main__":
    unittest.main()

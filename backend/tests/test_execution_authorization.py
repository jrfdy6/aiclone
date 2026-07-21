from __future__ import annotations

from app.security.execution_authorization import (
    execution_signing_configured,
    sign_execution_payload,
    verify_execution_payload,
)


def test_execution_signing_configuration_fails_closed_without_secret(monkeypatch, tmp_path) -> None:
    monkeypatch.delenv("CONTROL_PLANE_JOB_SIGNING_SECRET", raising=False)
    monkeypatch.setenv("AI_CLONE_SECRETS_ROOT", str(tmp_path))
    assert execution_signing_configured() is False


def test_execution_signing_configuration_detects_environment_secret(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("AI_CLONE_SECRETS_ROOT", str(tmp_path))
    monkeypatch.setenv("CONTROL_PLANE_JOB_SIGNING_SECRET", "unit-test-signing-secret")
    assert execution_signing_configured() is True


def test_execution_signature_detects_payload_tampering(monkeypatch) -> None:
    monkeypatch.setenv("CONTROL_PLANE_JOB_SIGNING_SECRET", "unit-test-signing-secret")
    payload = {"workspace_key": "shared_ops", "instructions": ["Do the bounded task."]}
    signed = sign_execution_payload("card-1", payload)
    assert verify_execution_payload("card-1", signed) is True
    signed["instructions"] = ["Run somewhere else."]
    assert verify_execution_payload("card-1", signed) is False

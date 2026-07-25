from __future__ import annotations

from app.services import pm_card_service, standup_service
from app.services.workspace_registry_service import canonicalize_workspace_key, workspace_storage_aliases


class _Cursor:
    def __init__(self) -> None:
        self.query = ""
        self.params: list[object] = []

    def __enter__(self) -> "_Cursor":
        return self

    def __exit__(self, *_args: object) -> None:
        return None

    def execute(self, query: str, params: list[object]) -> None:
        self.query = query
        self.params = params

    def fetchall(self) -> list[object]:
        return []


class _Connection:
    def __init__(self, cursor: _Cursor) -> None:
        self._cursor = cursor

    def __enter__(self) -> "_Connection":
        return self

    def __exit__(self, *_args: object) -> None:
        return None

    def cursor(self, **_kwargs: object) -> _Cursor:
        return self._cursor


class _Pool:
    def __init__(self, cursor: _Cursor) -> None:
        self._cursor = cursor

    def connection(self) -> _Connection:
        return _Connection(self._cursor)


def test_feezie_storage_aliases_preserve_legacy_history() -> None:
    aliases = workspace_storage_aliases("feezie-os")

    assert canonicalize_workspace_key("linkedin-os") == "feezie-os"
    assert "feezie-os" in aliases
    assert "linkedin-os" in aliases
    assert "linkedin-content-os" in aliases


def test_pm_workspace_filter_reads_canonical_and_legacy_aliases(monkeypatch) -> None:
    cursor = _Cursor()
    monkeypatch.setattr(pm_card_service, "get_pool", lambda: _Pool(cursor))

    assert pm_card_service.list_cards(workspace_key="feezie-os") == []

    assert "= ANY(%s)" in cursor.query
    aliases = cursor.params[0]
    assert isinstance(aliases, list)
    assert {"feezie-os", "linkedin-os", "linkedin-content-os"}.issubset(set(aliases))


def test_standup_workspace_filter_reads_canonical_and_legacy_aliases(monkeypatch) -> None:
    cursor = _Cursor()
    monkeypatch.setattr(standup_service, "get_pool", lambda: _Pool(cursor))

    assert standup_service.list_standups(workspace_key="feezie-os") == []

    assert "= ANY(%s)" in cursor.query
    aliases = cursor.params[0]
    assert isinstance(aliases, list)
    assert {"feezie-os", "linkedin-os", "linkedin-content-os"}.issubset(set(aliases))

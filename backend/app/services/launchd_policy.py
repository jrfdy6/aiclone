from __future__ import annotations


# The integrated coordinator invokes these behaviors in dependency order.
# Their standalone definitions remain rollback evidence, never desired writers.
RETIRED_INTEGRATED_COMPATIBILITY_IDS = frozenset(
    {"dream_cycle", "morning_daily_brief", "portfolio_standup_prep"}
)

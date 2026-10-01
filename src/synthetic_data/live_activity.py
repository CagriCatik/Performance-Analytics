from __future__ import annotations

import random
from datetime import datetime, timezone

ACTIVITY_STATUSES = ["Active Session", "Idle", "Processing", "Syncing", "Error State", "Logged Out"]
FEATURES_IN_USE = [
    "Dashboard", "Reports", "Analytics", "Integrations", "Settings",
    "User Management", "Billing", "API Console", "Notifications",
]


class _AccountState:
    def __init__(self, subscription: dict, rng: random.Random, speed_range: tuple[float, float]) -> None:
        self.subscription = subscription
        self.status = rng.choice(ACTIVITY_STATUSES[:4])
        self.active_users = max(1, round(int(subscription["max_users"]) * rng.uniform(0.1, 0.8)))
        self.current_feature = rng.choice(FEATURES_IN_USE)
        self.session_duration_min = round(rng.uniform(1.0, 240.0), 1)
        self.api_requests_last_hour = rng.randint(0, 800)

    def tick(self, rng: random.Random, elapsed_seconds: float) -> None:
        if rng.random() < 0.15:
            self.status = rng.choice(ACTIVITY_STATUSES)
        if rng.random() < 0.20:
            self.current_feature = rng.choice(FEATURES_IN_USE)
        delta_users = rng.randint(-2, 2)
        self.active_users = max(0, min(int(self.subscription["max_users"]), self.active_users + delta_users))
        self.session_duration_min = round(self.session_duration_min + elapsed_seconds / 60, 1)
        self.api_requests_last_hour = max(0, self.api_requests_last_hour + rng.randint(-30, 50))


class LiveActivityTracker:
    def __init__(
        self,
        subscriptions: list[dict],
        live_cfg: dict | None = None,
        seed: int = 42,
    ) -> None:
        self._rng = random.Random(seed + 99999)
        cfg = live_cfg or {}
        self._states = [_AccountState(s, self._rng, (0.0, 1.0)) for s in subscriptions]

    def get_activity(self) -> list[dict]:
        now = datetime.now(tz=timezone.utc)
        rows = []
        for state in self._states:
            sub = state.subscription
            rows.append({
                "subscription_id": sub["subscription_id"],
                "account_id": sub["account_id"],
                "plan_name": sub["plan_name"],
                "status": state.status,
                "active_users": state.active_users,
                "max_users": sub["max_users"],
                "current_feature": state.current_feature,
                "session_duration_min": state.session_duration_min,
                "api_requests_last_hour": state.api_requests_last_hour,
                "last_updated": now.isoformat(timespec="seconds"),
            })
        return rows

    def tick(self, elapsed_seconds: float) -> list[dict]:
        for state in self._states:
            state.tick(self._rng, elapsed_seconds)
        return self.get_activity()

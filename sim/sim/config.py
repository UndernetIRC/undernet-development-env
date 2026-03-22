from __future__ import annotations

import json
from dataclasses import dataclass, field, asdict


@dataclass
class SimUser:
    username: str
    password: str
    password_hash: str
    authenticated: bool
    role: str  # "owner", "member", or "roamer"
    channels: list[str] = field(default_factory=list)
    db_user_id: int | None = None


@dataclass
class SimChannel:
    name: str
    registered: bool
    owner: str | None = None
    db_channel_id: int | None = None


@dataclass
class SimConfig:
    authenticated_users: int
    unauthenticated_users: int
    registered_channels: int
    unregistered_channels: int
    password: str
    server: str
    port: int
    users: list[SimUser] = field(default_factory=list)
    channels: list[SimChannel] = field(default_factory=list)


def save_config(config: SimConfig, path: str) -> None:
    with open(path, "w") as f:
        json.dump(asdict(config), f, indent=2)


def load_config(path: str) -> SimConfig:
    with open(path) as f:
        data = json.load(f)
    data["users"] = [SimUser(**u) for u in data["users"]]
    data["channels"] = [SimChannel(**c) for c in data["channels"]]
    return SimConfig(**data)

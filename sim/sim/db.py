from __future__ import annotations

import hashlib
import random
import string
from typing import TYPE_CHECKING

import psycopg2

if TYPE_CHECKING:
    from sim.config import SimConfig


def generate_password_hash(plaintext: str) -> str:
    """Generate a gnuworld-compatible password hash.

    Format: <8-char-salt><32-char-md5-hex>
    Algorithm: MD5(salt + plaintext)
    """
    salt_chars = string.ascii_letters + string.digits
    salt = "".join(random.choice(salt_chars) for _ in range(8))
    md5_hash = hashlib.md5((salt + plaintext).encode()).hexdigest()
    return salt + md5_hash


def verify_password(plaintext: str, stored_hash: str) -> bool:
    """Verify a plaintext password against a stored gnuworld hash."""
    salt = stored_hash[:8]
    expected = hashlib.md5((salt + plaintext).encode()).hexdigest()
    return stored_hash[8:] == expected


def provision_users(conn, config: SimConfig) -> SimConfig:
    cur = conn.cursor()
    for user in config.users:
        if not user.authenticated:
            continue
        cur.execute(
            "SELECT id FROM users WHERE lower(user_name) = lower(%s)",
            (user.username,),
        )
        row = cur.fetchone()
        if row:
            user.db_user_id = row[0]
            print(f"  Reusing existing user {user.username} (id={row[0]})")
        else:
            cur.execute(
                """INSERT INTO users
                   (user_name, password, language_id, flags, last_updated,
                    signup_ts, signup_ip, maxlogins)
                   VALUES (%s, %s, 1, 0,
                           extract(epoch from now())::int,
                           extract(epoch from now())::int,
                           '127.0.0.1', 3)
                   RETURNING id""",
                (user.username, user.password_hash),
            )
            user.db_user_id = cur.fetchone()[0]
            print(f"  Created user {user.username} (id={user.db_user_id})")
    return config


def provision_channels(conn, config: SimConfig) -> SimConfig:
    cur = conn.cursor()
    for channel in config.channels:
        if not channel.registered:
            continue
        cur.execute(
            "SELECT id FROM channels WHERE lower(name) = lower(%s)",
            (channel.name,),
        )
        row = cur.fetchone()
        if row:
            channel.db_channel_id = row[0]
            print(f"  Reusing existing channel {channel.name} (id={row[0]})")
        else:
            cur.execute(
                """INSERT INTO channels
                   (name, flags, registered_ts, channel_ts, channel_mode, last_updated)
                   VALUES (%s, 0,
                           extract(epoch from now())::int,
                           extract(epoch from now())::int,
                           '+nt',
                           extract(epoch from now())::int)
                   RETURNING id""",
                (channel.name,),
            )
            channel.db_channel_id = cur.fetchone()[0]
            print(f"  Created channel {channel.name} (id={channel.db_channel_id})")
    return config


def _ensure_level(cur, channel_id: int, user_id: int, access: int,
                  channel_name: str, username: str) -> None:
    cur.execute(
        "SELECT access FROM levels WHERE channel_id = %s AND user_id = %s AND deleted = 0",
        (channel_id, user_id),
    )
    row = cur.fetchone()
    if row:
        if row[0] == access:
            print(f"  Level {access} already set for {username} on {channel_name}")
        else:
            cur.execute(
                """UPDATE levels SET access = %s,
                   last_updated = extract(epoch from now())::int
                   WHERE channel_id = %s AND user_id = %s""",
                (access, channel_id, user_id),
            )
            print(f"  Updated level for {username} on {channel_name} to {access}")
    else:
        cur.execute(
            """INSERT INTO levels
               (channel_id, user_id, access, flags, added, added_by,
                last_modif, last_modif_by, last_updated)
               VALUES (%s, %s, %s, 0,
                       extract(epoch from now())::int, 'sim-setup',
                       extract(epoch from now())::int, 'sim-setup',
                       extract(epoch from now())::int)""",
            (channel_id, user_id, access),
        )
        print(f"  Set level {access} for {username} on {channel_name}")


def provision_levels(conn, config: SimConfig) -> None:
    cur = conn.cursor()
    # Build lookup maps
    users_by_name = {u.username: u for u in config.users}
    channels_by_name = {c.name: c for c in config.channels}

    # Owner levels (500)
    for channel in config.channels:
        if not channel.registered or not channel.owner:
            continue
        owner = users_by_name.get(channel.owner)
        if not owner or not owner.db_user_id or not channel.db_channel_id:
            continue
        _ensure_level(cur, channel.db_channel_id, owner.db_user_id, 500,
                      channel.name, owner.username)

    # Member levels (100)
    for user in config.users:
        if user.role != "member" or not user.db_user_id:
            continue
        for ch_name in user.channels:
            ch = channels_by_name.get(ch_name)
            if not ch or not ch.registered or not ch.db_channel_id:
                continue
            _ensure_level(cur, ch.db_channel_id, user.db_user_id, 100,
                          ch.name, user.username)


def provision_all(db_url: str, config: SimConfig) -> SimConfig:
    print("Connecting to database...")
    conn = psycopg2.connect(db_url)
    try:
        print("Provisioning users...")
        config = provision_users(conn, config)
        print("Provisioning channels...")
        config = provision_channels(conn, config)
        print("Provisioning access levels...")
        provision_levels(conn, config)
        conn.commit()
        print("Database provisioning complete.")
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
    return config

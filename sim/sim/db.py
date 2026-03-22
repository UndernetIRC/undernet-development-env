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


# gnuworld channel flag that tells X to join the channel
F_AUTOJOIN = 0x00200000


def provision_channels(conn, config: SimConfig) -> SimConfig:
    cur = conn.cursor()
    for channel in config.channels:
        if not channel.registered:
            continue
        cur.execute(
            "SELECT id, flags FROM channels WHERE lower(name) = lower(%s)",
            (channel.name,),
        )
        row = cur.fetchone()
        if row:
            channel.db_channel_id = row[0]
            existing_flags = row[1]
            print(f"  Reusing existing channel {channel.name} (id={row[0]})")
            # Ensure AUTOJOIN flag is set so X joins the channel
            if not (existing_flags & F_AUTOJOIN):
                cur.execute(
                    "UPDATE channels SET flags = flags | %s, last_updated = extract(epoch from now())::int WHERE id = %s",
                    (F_AUTOJOIN, row[0]),
                )
                print(f"  Set AUTOJOIN flag on {channel.name}")
        else:
            cur.execute(
                """INSERT INTO channels
                   (name, flags, registered_ts, channel_ts, channel_mode, last_updated)
                   VALUES (%s, %s,
                           extract(epoch from now())::int,
                           extract(epoch from now())::int,
                           '+nt',
                           extract(epoch from now())::int)
                   RETURNING id""",
                (channel.name, F_AUTOJOIN),
            )
            channel.db_channel_id = cur.fetchone()[0]
            print(f"  Created channel {channel.name} (id={channel.db_channel_id})")
    return config


# gnuworld level flag for auto-op on join
F_LEVEL_AUTOOP = 0x01


def _ensure_level(cur, channel_id: int, user_id: int, access: int,
                  channel_name: str, username: str, autoop: bool = False) -> None:
    level_flags = F_LEVEL_AUTOOP if autoop else 0
    cur.execute(
        "SELECT access, flags FROM levels WHERE channel_id = %s AND user_id = %s AND deleted = 0",
        (channel_id, user_id),
    )
    row = cur.fetchone()
    if row:
        existing_access, existing_flags = row
        need_update = existing_access != access or (autoop and not (existing_flags & F_LEVEL_AUTOOP))
        if need_update:
            new_flags = existing_flags | F_LEVEL_AUTOOP if autoop else existing_flags
            cur.execute(
                """UPDATE levels SET access = %s, flags = %s,
                   last_updated = extract(epoch from now())::int
                   WHERE channel_id = %s AND user_id = %s""",
                (access, new_flags, channel_id, user_id),
            )
            print(f"  Updated level for {username} on {channel_name} to {access} (autoop={'on' if autoop else 'off'})")
        else:
            print(f"  Level {access} already set for {username} on {channel_name}")
    else:
        cur.execute(
            """INSERT INTO levels
               (channel_id, user_id, access, flags, added, added_by,
                last_modif, last_modif_by, last_updated)
               VALUES (%s, %s, %s, %s,
                       extract(epoch from now())::int, 'sim-setup',
                       extract(epoch from now())::int, 'sim-setup',
                       extract(epoch from now())::int)""",
            (channel_id, user_id, access, level_flags),
        )
        print(f"  Set level {access} for {username} on {channel_name} (autoop={'on' if autoop else 'off'})")


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
                      channel.name, owner.username, autoop=True)

    # Member levels (100) - with autoop so X ops them on join
    for user in config.users:
        if user.role != "member" or not user.db_user_id:
            continue
        for ch_name in user.channels:
            ch = channels_by_name.get(ch_name)
            if not ch or not ch.registered or not ch.db_channel_id:
                continue
            _ensure_level(cur, ch.db_channel_id, user.db_user_id, 100,
                          ch.name, user.username, autoop=True)


MIN_CONN_LIMIT = 500


def ensure_ccontrol_limits(db_url: str) -> None:
    """Ensure ccontrol connection limits are high enough for simulation.

    Updates the iplisps table in the ccontrol database and clears any
    existing G-lines that may block simulator connections.
    """
    # Derive ccontrol DB URL by replacing the database name (last path segment)
    ccontrol_url = db_url.rsplit("/", 1)[0] + "/ccontrol"

    print("Checking ccontrol connection limits...")
    conn = psycopg2.connect(ccontrol_url)
    try:
        cur = conn.cursor()

        # Check and update iplisps limits
        cur.execute("SELECT name, maxlimit FROM iplisps WHERE maxlimit < %s", (MIN_CONN_LIMIT,))
        low_limits = cur.fetchall()
        if low_limits:
            for name, limit in low_limits:
                print(f"  Raising {name} maxlimit from {limit} to {MIN_CONN_LIMIT}")
            cur.execute(
                "UPDATE iplisps SET maxlimit = %s WHERE maxlimit < %s",
                (MIN_CONN_LIMIT, MIN_CONN_LIMIT),
            )
        else:
            print("  All iplisps limits OK")

        # Clear any existing G-lines that could block us
        cur.execute("SELECT count(*) FROM glines")
        gline_count = cur.fetchone()[0]
        if gline_count > 0:
            cur.execute("DELETE FROM glines")
            print(f"  Cleared {gline_count} G-line(s)")

        conn.commit()
        print("  ccontrol limits verified.")
    except Exception as e:
        conn.rollback()
        print(f"  Warning: could not update ccontrol limits: {e}")
    finally:
        conn.close()


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

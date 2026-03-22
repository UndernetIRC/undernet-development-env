from __future__ import annotations

import asyncio
import logging
import math
import os
import random
import sys

import click

from sim.config import SimChannel, SimConfig, SimUser, load_config, save_config
from sim.db import ensure_ccontrol_limits, generate_password_hash, provision_all
from sim.simulation import Simulation


def parse_interval(value: str) -> tuple[int, int]:
    parts = value.split("-")
    if len(parts) != 2:
        raise click.BadParameter(f"Invalid interval format '{value}'. Expected 'MIN-MAX' (e.g., '10-60').")
    try:
        lo, hi = int(parts[0]), int(parts[1])
    except ValueError:
        raise click.BadParameter(f"Invalid interval format '{value}'. Expected 'MIN-MAX' (e.g., '10-60').")
    if lo >= hi:
        raise click.BadParameter(f"Invalid interval '{value}'. MIN must be less than MAX.")
    return (lo, hi)


def build_config(
    authenticated_users: int,
    unauthenticated_users: int,
    registered_channels: int,
    unregistered_channels: int,
    password: str,
    server: str,
    port: int,
) -> SimConfig:
    users: list[SimUser] = []
    channels: list[SimChannel] = []

    # Create registered channels
    for i in range(1, registered_channels + 1):
        ch_name = f"#sim-{i:03d}"
        channels.append(SimChannel(name=ch_name, registered=True, owner=None))

    # Create unregistered channels
    for i in range(1, unregistered_channels + 1):
        ch_name = f"#usim-{i:03d}"
        channels.append(SimChannel(name=ch_name, registered=False))

    registered_ch_names = [c.name for c in channels if c.registered]
    unregistered_ch_names = [c.name for c in channels if not c.registered]

    # Assign authenticated users
    owner_count = registered_channels
    remaining_auth = authenticated_users - owner_count
    member_count = max(1, math.ceil(remaining_auth * 0.3)) if remaining_auth > 0 else 0
    roamer_count = remaining_auth - member_count

    user_idx = 0

    # Owners
    for i in range(owner_count):
        user_idx += 1
        username = f"sim-{user_idx:03d}"
        ch_name = registered_ch_names[i]
        user = SimUser(
            username=username,
            password=password,
            password_hash=generate_password_hash(password),
            authenticated=True,
            role="owner",
            channels=[ch_name],
        )
        users.append(user)
        # Set owner on channel
        for c in channels:
            if c.name == ch_name:
                c.owner = username

    # Members
    for _ in range(member_count):
        user_idx += 1
        username = f"sim-{user_idx:03d}"
        # Assign 1-3 random registered channels
        n_channels = min(random.randint(1, 3), len(registered_ch_names))
        assigned = random.sample(registered_ch_names, n_channels)
        user = SimUser(
            username=username,
            password=password,
            password_hash=generate_password_hash(password),
            authenticated=True,
            role="member",
            channels=assigned,
        )
        users.append(user)

    # Roamers (authenticated but no DB level)
    for _ in range(roamer_count):
        user_idx += 1
        username = f"sim-{user_idx:03d}"
        assigned = []
        # Join 1-2 random registered channels
        if registered_ch_names:
            n_reg = min(random.randint(1, 2), len(registered_ch_names))
            assigned.extend(random.sample(registered_ch_names, n_reg))
        # Also join 1-2 unregistered channels (they'll get opped as first joiners)
        if unregistered_ch_names:
            n_unreg = min(random.randint(1, 2), len(unregistered_ch_names))
            assigned.extend(random.sample(unregistered_ch_names, n_unreg))
        user = SimUser(
            username=username,
            password=password,
            password_hash=generate_password_hash(password),
            authenticated=True,
            role="roamer",
            channels=assigned,
        )
        users.append(user)

    # Unauthenticated users
    for i in range(1, unauthenticated_users + 1):
        username = f"usim-{i:03d}"
        # Assign 1-2 unregistered channels
        n_unreg = min(random.randint(1, 2), len(unregistered_ch_names)) if unregistered_ch_names else 0
        assigned = random.sample(unregistered_ch_names, n_unreg) if n_unreg else []
        # Optionally add 1 registered channel
        if registered_ch_names and random.random() < 0.5:
            assigned.append(random.choice(registered_ch_names))
        user = SimUser(
            username=username,
            password=password,
            password_hash="",
            authenticated=False,
            role="roamer",
            channels=assigned,
        )
        users.append(user)

    return SimConfig(
        authenticated_users=authenticated_users,
        unauthenticated_users=unauthenticated_users,
        registered_channels=registered_channels,
        unregistered_channels=unregistered_channels,
        password=password,
        server=server,
        port=port,
        users=users,
        channels=channels,
    )


@click.command()
@click.option("--authenticated-users", default=10, type=int, show_default=True,
              help="Number of authenticated users")
@click.option("--unauthenticated-users", default=5, type=int, show_default=True,
              help="Number of unauthenticated users")
@click.option("--registered-channels", default=2, type=int, show_default=True,
              help="Number of registered channels")
@click.option("--unregistered-channels", default=3, type=int, show_default=True,
              help="Number of unregistered channels")
@click.option("--chat-interval", default="10-60", type=str, show_default=True,
              help="Chat interval range in seconds (MIN-MAX)")
@click.option("--action-interval", default="60-300", type=str, show_default=True,
              help="Channel action interval range in seconds (MIN-MAX)")
@click.option("--config", "config_path", default="./sim-config.json", type=click.Path(),
              show_default=True, help="Path to simulation config file")
@click.option("--db-url", default="postgres://cservice:cservice@localhost:5432/cservice",
              type=str, show_default=True, help="PostgreSQL connection URL")
@click.option("--force-recreate", is_flag=True, default=False,
              help="Force recreation of config even if it exists")
@click.option("--password", default="simPass123", type=str, show_default=True,
              help="Shared password for all sim users")
@click.option("--server", default="localhost", type=str, show_default=True,
              help="IRC server hostname")
@click.option("--port", default=6667, type=int, show_default=True,
              help="IRC server port")
@click.option("--skip-db-limits", is_flag=True, default=False,
              help="Skip checking/fixing ccontrol connection limits")
def main(
    authenticated_users: int,
    unauthenticated_users: int,
    registered_channels: int,
    unregistered_channels: int,
    chat_interval: str,
    action_interval: str,
    config_path: str,
    db_url: str,
    force_recreate: bool,
    password: str,
    server: str,
    port: int,
    skip_db_limits: bool,
) -> None:
    """UnderNET IRC Client Simulator.

    Simulates multiple IRC clients connecting to the development environment
    with varying authentication states, channel memberships, and activity.
    """
    # Set up logging
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)-5s %(message)s",
        datefmt="%H:%M:%S",
        stream=sys.stdout,
    )

    # Validate constraints
    if registered_channels > authenticated_users:
        raise click.UsageError(
            f"Cannot have more registered channels ({registered_channels}) than "
            f"authenticated users ({authenticated_users}). Each registered channel "
            f"needs a unique owner."
        )
    if registered_channels > 0 and authenticated_users < 1:
        raise click.UsageError(
            "Need at least 1 authenticated user to own registered channels."
        )

    # Parse intervals
    chat_iv = parse_interval(chat_interval)
    action_iv = parse_interval(action_interval)

    # Ensure ccontrol connection limits are adequate
    if not skip_db_limits:
        ensure_ccontrol_limits(db_url)

    # Load or create config
    if os.path.exists(config_path) and not force_recreate:
        config = load_config(config_path)
        click.echo(
            f"Loaded existing config from {config_path} "
            f"({len(config.users)} users, {len(config.channels)} channels)"
        )
        click.echo("Use --force-recreate to regenerate")
        # Override server/port from CLI
        config.server = server
        config.port = port
    else:
        click.echo("Building simulation config...")
        config = build_config(
            authenticated_users=authenticated_users,
            unauthenticated_users=unauthenticated_users,
            registered_channels=registered_channels,
            unregistered_channels=unregistered_channels,
            password=password,
            server=server,
            port=port,
        )

        # Provision database
        click.echo("Provisioning database...")
        config = provision_all(db_url, config)

        # Save config
        save_config(config, config_path)
        click.echo(f"Config created at {config_path}")

    # Run simulation
    click.echo(f"Starting simulation with {len(config.users)} clients...")
    sim = Simulation(config=config, chat_interval=chat_iv, action_interval=action_iv)
    asyncio.run(sim.run())

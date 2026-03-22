# UnderNET IRC Client Simulator

A Python-based IRC client simulator for the UnderNET development environment. Spins up multiple concurrent IRC clients with varying authentication states, channel memberships, and activity patterns.

## Prerequisites

- Python 3.11+
- [uv](https://docs.astral.sh/uv/) package manager
- Running UnderNET Docker development environment (`docker compose up -d`)

## Installation

```bash
cd sim
uv sync
```

## Usage

```bash
# Run with defaults (10 auth users, 5 unauth, 2 registered channels, 3 unregistered)
uv run undernet-sim

# Custom configuration
uv run undernet-sim \
  --authenticated-users 20 \
  --unauthenticated-users 10 \
  --registered-channels 4 \
  --unregistered-channels 5

# Faster chat for testing
uv run undernet-sim --chat-interval 3-10 --action-interval 10-30

# Use a custom config file
uv run undernet-sim --config my-sim.json

# Force recreate config (re-provisions DB)
uv run undernet-sim --force-recreate
```

### CLI Options

| Option | Default | Description |
|--------|---------|-------------|
| `--authenticated-users` | 10 | Number of users with X accounts |
| `--unauthenticated-users` | 5 | Number of users without X accounts |
| `--registered-channels` | 2 | Number of channels registered with X |
| `--unregistered-channels` | 3 | Number of unregistered channels |
| `--chat-interval` | 10-60 | Random chat interval range (seconds) |
| `--action-interval` | 60-300 | Random channel action interval (seconds) |
| `--config` | ./sim-config.json | Path to simulation config file |
| `--db-url` | postgres://cservice:cservice@localhost:5432/cservice | PostgreSQL connection URL |
| `--force-recreate` | false | Force recreation of config |
| `--password` | simPass123 | Shared password for all sim users |
| `--server` | localhost | IRC server hostname |
| `--port` | 6667 | IRC server port |

## How It Works

1. **Setup phase**: Creates user accounts in the cservice database, registers channels, and assigns access levels. Saves the full state to a JSON config file.
2. **Run phase**: Connects all simulated clients to the IRC server, authenticates with X where applicable, joins channels, and runs a continuous simulation with random chat and channel operations.

### User Roles

- **Owners** (~20% of auth users): Each owns one registered channel (level 500)
- **Members** (~30% of remaining auth users): Have level 100 access on 1-3 channels
- **Roamers** (remaining auth users): Join channels but have no DB-level access
- **Unauthenticated**: Join unregistered channels, some also join registered ones

### Simulation Activity

- **Chat**: Each client sends a random gibberish message every 10-60 seconds
- **Channel ops**: Opped users randomly op/deop/voice/unvoice/kick other users every 60-300 seconds
- **Kick recovery**: Kicked users automatically rejoin after 5-15 seconds

## Config File Format

The `sim-config.json` file contains the full simulation state. On subsequent runs, the simulator loads this file instead of re-provisioning the database. Use `--force-recreate` to regenerate.

## Troubleshooting

**Connection refused**: Ensure the leaf server is running (`docker compose ps`). Clients connect to `localhost:6667`.

**Login failures**: gnuworld has a `login_delay` (default 5 seconds) after connecting to IRC before it accepts login commands. The simulator waits up to 30 seconds for authentication.

**Too many connections refused / G-lined for excessive connections**: ccontrol (UWorld) enforces per-IP connection limits via the `iplisps` table in the ccontrol database. The default limit is 5 connections per IP. Increase it for simulation:

```bash
docker compose exec db psql -U cservice -d ccontrol \
  -c "UPDATE iplisps SET maxlimit = 500 WHERE name = 'default32';"
docker compose exec db psql -U cservice -d ccontrol \
  -c "DELETE FROM glines;"
docker compose restart hub leaf && sleep 3 && docker compose restart gnuworld
```

Also ensure `etc/leaf.conf` has `"IPCHECK"="FALSE"` in the features block and the `Simulation` connection class with `maxlinks = 500`.

**Nick already in use**: If a previous simulation didn't shut down cleanly, nicks may still be registered on the server. Wait a minute for the server to time them out, or restart the leaf server.

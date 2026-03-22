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

# Skip automatic ccontrol limit checks
uv run undernet-sim --skip-db-limits
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
| `--skip-db-limits` | false | Skip checking/fixing ccontrol connection limits |
| `--password` | simPass123 | Shared password for all sim users |
| `--server` | localhost | IRC server hostname |
| `--port` | 6667 | IRC server port |

## How It Works

1. **Setup phase**: Creates user accounts in the cservice database, registers channels (with `AUTOJOIN` flag so X joins them), assigns access levels (with `AUTOOP` so X ops users on join), and saves the full state to a JSON config file.
2. **Limit check**: Verifies ccontrol's `iplisps` connection limits are high enough and clears any existing G-lines. Use `--skip-db-limits` to disable.
3. **Run phase**: Connects all simulated clients to the IRC server, authenticates with X where applicable, joins channels, and runs a continuous simulation with random chat and channel operations.

### User Roles

- **Owners** (~20% of auth users): Each owns one registered `#sim-XXX` channel (level 500, AUTOOP). Owners ask X to join their channel on connect.
- **Members** (~30% of remaining auth users): Have level 100 access with AUTOOP on 1-3 registered channels
- **Roamers** (remaining auth users): Join registered and unregistered channels. First to join `#usim-XXX` channels, getting ops from the server.
- **Unauthenticated** (`usim-XXX`): Join unregistered channels, some also join registered ones

### Simulation Activity

- **Chat**: Each client sends a random gibberish message at the configured interval (default 10-60 seconds)
- **Channel ops**: Opped users randomly op/deop/voice/unvoice/kick other users at the configured interval (default 60-300 seconds). Channel owners are protected from kick/deop on their own channels.
- **Kick recovery**: Kicked users automatically rejoin after 5-15 seconds
- **Keepalive**: Each client sends a PING every 60 seconds to prevent server timeout

## Config File Format

The `sim-config.json` file contains the full simulation state. On subsequent runs, the simulator loads this file instead of re-provisioning the database. Use `--force-recreate` to regenerate.

## Troubleshooting

**Connection refused**: Ensure the leaf server is running (`docker compose ps`). Clients connect to `localhost:6667`.

**Login failures**: gnuworld has a `login_delay` (default 5 seconds) after connecting to IRC before it accepts login commands. The simulator waits up to 30 seconds for authentication.

**Connection class full**: The leaf server's Client catchall block must use the `Simulation` class (maxlinks=500). Check `etc/leaf.conf` — the catchall `Client { class = "Simulation"; ip = "*@*"; }` must be present. ircu2 Client blocks require CIDR notation for IP matching; glob patterns like `*@10.5.0.*` are silently ignored.

**G-lined for excessive connections**: The simulator automatically checks and fixes ccontrol's `iplisps` limits on startup (unless `--skip-db-limits` is used). If you still get G-lined, manually clear them:

```bash
docker compose exec db psql -U cservice -d ccontrol -c "DELETE FROM glines;"
docker compose restart hub leaf && sleep 3 && docker compose restart gnuworld
```

**ircu2 IPCHECK throttling**: The leaf config should have these features to allow many connections from the same IP:

```
"IPCHECK_CLONE_LIMIT"="500";
"IPCHECK_CLONE_PERIOD"="1";
"IPCHECK_CLONE_DELAY"="0";
```

Note: `"IPCHECK"="FALSE"` does NOT work — that feature doesn't exist in ircu2.

**X not joining registered channels**: Channels need the `F_AUTOJOIN` flag (`0x00200000`) set. The simulator sets this automatically. If X still isn't in a channel, restart gnuworld after the first run: `docker compose restart gnuworld`.

**Nick already in use**: If a previous simulation didn't shut down cleanly, nicks may still be registered on the server. Wait a minute for the server to time them out, or restart the leaf server.

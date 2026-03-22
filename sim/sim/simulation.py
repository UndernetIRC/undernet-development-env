from __future__ import annotations

import asyncio
import logging
import random
import signal

from sim.client import SimIRCClient
from sim.config import SimConfig
from sim.words import generate_message

logger = logging.getLogger("sim")

ACTION_WEIGHTS = {
    "op": 20,
    "deop": 15,
    "voice": 25,
    "unvoice": 15,
    "kick": 25,
}
ACTIONS = list(ACTION_WEIGHTS.keys())
WEIGHTS = list(ACTION_WEIGHTS.values())


class Simulation:
    def __init__(
        self,
        config: SimConfig,
        chat_interval: tuple[int, int],
        action_interval: tuple[int, int],
    ):
        self.config = config
        self.chat_interval = chat_interval
        self.action_interval = action_interval
        self.clients: list[SimIRCClient] = []
        self.clients_by_nick: dict[str, SimIRCClient] = {}
        self.running = False
        self._tasks: list[asyncio.Task] = []

    async def start(self) -> None:
        self.running = True

        # Create clients
        for user in self.config.users:
            client = SimIRCClient(
                user=user,
                server=self.config.server,
                port=self.config.port,
                channels=user.channels,
            )
            self.clients.append(client)
            self.clients_by_nick[user.username.lower()] = client

        # Stagger connections
        logger.info("Connecting %d clients...", len(self.clients))
        for client in self.clients:
            try:
                await client.connect()
            except Exception as e:
                logger.error("[%s] Connection failed: %s", client.user.username, e)
            await asyncio.sleep(1.0)

        # Wait for all clients to be ready
        logger.info("Waiting for clients to be ready...")
        ready_tasks = [client.wait_ready(timeout=30.0) for client in self.clients]
        results = await asyncio.gather(*ready_tasks, return_exceptions=True)
        connected = sum(1 for r in results if r is True)
        logger.info("%d/%d clients ready", connected, len(self.clients))

        # Start activity tasks for connected clients
        for client in self.clients:
            if client.connected:
                self._tasks.append(asyncio.create_task(self._chat_loop(client)))
                self._tasks.append(asyncio.create_task(self._action_loop(client)))

    async def _chat_loop(self, client: SimIRCClient) -> None:
        nick = client.user.username
        while self.running:
            delay = random.uniform(*self.chat_interval)
            await asyncio.sleep(delay)

            if not self.running or not client.connected:
                break

            if client.joined_channels:
                channel = random.choice(list(client.joined_channels))
                msg = generate_message()
                client.send_chat(channel, msg)
                logger.info("[%s -> %s] %s", nick, channel, msg)

    async def _action_loop(self, client: SimIRCClient) -> None:
        nick = client.user.username
        while self.running:
            delay = random.uniform(*self.action_interval)
            await asyncio.sleep(delay)

            if not self.running or not client.connected:
                break

            # Only perform actions if we have ops somewhere
            opped_channels = [ch for ch, opped in client.is_opped.items() if opped]
            if not opped_channels:
                continue

            channel = random.choice(opped_channels)

            # Find other clients in this channel
            others = [
                c for c in self.clients
                if c is not client
                and c.connected
                and channel in c.joined_channels
            ]
            if not others:
                continue

            target_client = random.choice(others)
            target_nick = target_client.user.username
            action = random.choices(ACTIONS, weights=WEIGHTS, k=1)[0]

            # Don't kick or deop channel owners
            if action in ("kick", "deop") and target_client.user.role == "owner":
                # Find a registered channel matching
                owner_channels = {
                    ch.name for ch in self.config.channels
                    if ch.registered and ch.owner == target_nick
                }
                if channel in owner_channels:
                    continue

            if action == "kick":
                client.send_kick(channel, target_nick)
                logger.info("[%s -> %s] kicked %s", nick, channel, target_nick)
            elif action in ("op", "deop"):
                mode = f"+o" if action == "op" else "-o"
                client.send_mode(channel, mode, target_nick)
                logger.info("[%s -> %s] %s %s", nick, channel, action, target_nick)
            elif action in ("voice", "unvoice"):
                mode = "+v" if action == "voice" else "-v"
                client.send_mode(channel, mode, target_nick)
                logger.info("[%s -> %s] %s %s", nick, channel, action, target_nick)

    async def stop(self) -> None:
        self.running = False

        # Cancel activity tasks
        for task in self._tasks:
            task.cancel()
        if self._tasks:
            await asyncio.gather(*self._tasks, return_exceptions=True)
        self._tasks.clear()

        # Disconnect all clients
        count = 0
        for client in self.clients:
            if client.connected:
                client.disconnect()
                count += 1

        logger.info("Simulation stopped. %d clients disconnected.", count)

    async def run(self) -> None:
        loop = asyncio.get_running_loop()
        stop_event = asyncio.Event()

        def _signal_handler():
            logger.info("Received shutdown signal...")
            stop_event.set()

        for sig in (signal.SIGINT, signal.SIGTERM):
            loop.add_signal_handler(sig, _signal_handler)

        await self.start()
        logger.info("Simulation running. Press Ctrl+C to stop.")

        await stop_event.wait()
        await self.stop()

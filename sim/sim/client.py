from __future__ import annotations

import asyncio
import logging
import random

import irc.client_aio
import irc.client

from sim.config import SimUser

logger = logging.getLogger("sim")

# Shared reactor for all clients — avoids creating 100+ separate reactors
_shared_reactor: irc.client_aio.AioReactor | None = None


def get_shared_reactor() -> irc.client_aio.AioReactor:
    global _shared_reactor
    if _shared_reactor is None:
        loop = asyncio.get_running_loop()
        _shared_reactor = irc.client_aio.AioReactor(loop=loop)
    return _shared_reactor


class SimIRCClient:
    def __init__(self, user: SimUser, server: str, port: int, channels: list[str]):
        self.user = user
        self.server = server
        self.port = port
        self.channels = channels
        self.connected = False
        self.authenticated = False
        self.joined_channels: set[str] = set()
        self.is_opped: dict[str, bool] = {}
        self.connection: irc.client_aio.AioConnection | None = None
        self._login_event = asyncio.Event()
        self._keepalive_task: asyncio.Task | None = None

    async def connect(self) -> None:
        reactor = get_shared_reactor()
        self.connection = reactor.server()

        # Register per-connection event handlers on the shared reactor.
        # We filter by connection in each handler to avoid cross-talk.
        reactor.add_global_handler("welcome", self._on_welcome)
        reactor.add_global_handler("privnotice", self._on_notice)
        reactor.add_global_handler("kick", self._on_kick)
        reactor.add_global_handler("mode", self._on_mode)
        reactor.add_global_handler("join", self._on_join)
        reactor.add_global_handler("disconnect", self._on_disconnect)
        reactor.add_global_handler("nicknameinuse", self._on_nick_in_use)

        nick = self.user.username
        ident = self.user.username.replace("-", "")

        try:
            await self.connection.connect(
                self.server, self.port, nick,
                username=ident, ircname="UnderNET Simulator",
            )
            logger.info("[%s] Connected to %s:%d", nick, self.server, self.port)
        except Exception as e:
            logger.error("[%s] Failed to connect: %s", nick, e)
            raise

    def _is_mine(self, connection) -> bool:
        return connection is self.connection

    def _on_welcome(self, connection, event):
        if not self._is_mine(connection):
            return
        nick = self.user.username
        self.connected = True
        logger.info("[%s] Received welcome from server", nick)

        # Start client-side keepalive
        self._keepalive_task = asyncio.ensure_future(self._keepalive_loop())

        if self.user.authenticated:
            login_msg = f"login {self.user.username} {self.user.password}"
            connection.privmsg("X@channels.undernet.org", login_msg)
            logger.info("[%s] Sent login request to X", nick)
        else:
            self._join_channels()
            self._login_event.set()

    async def _keepalive_loop(self):
        """Send periodic PINGs to keep the connection alive."""
        while self.connected and self.connection:
            try:
                await asyncio.sleep(60)
                if self.connected and self.connection:
                    self.connection.ping("keepalive")
            except asyncio.CancelledError:
                break
            except Exception:
                break

    def _on_notice(self, connection, event):
        if not self._is_mine(connection):
            return
        nick = self.user.username
        source = event.source or ""
        text = event.arguments[0] if event.arguments else ""

        # Check for X login response
        if "X!" in str(source) or "X@" in str(source):
            lower_text = text.lower()
            if "authentication successful" in lower_text:
                self.authenticated = True
                logger.info("[%s] Authentication successful", nick)
                self._join_channels()
                self._login_event.set()
            elif "authentication failed" in lower_text or "login failed" in lower_text:
                logger.warning("[%s] Authentication failed: %s", nick, text)
                # Still join channels even if auth failed
                self._join_channels()
                self._login_event.set()

    def _on_kick(self, connection, event):
        if not self._is_mine(connection):
            return
        nick = self.user.username
        channel = event.target
        kicked_nick = event.arguments[0] if event.arguments else ""

        if kicked_nick.lower() == nick.lower():
            self.joined_channels.discard(channel)
            self.is_opped.pop(channel, None)
            reason = event.arguments[1] if len(event.arguments) > 1 else "no reason"
            logger.info("[%s] Kicked from %s (%s), will rejoin", nick, channel, reason)

            delay = random.uniform(5, 15)
            loop = asyncio.get_running_loop()
            loop.call_later(delay, lambda: connection.join(channel))

    def _on_mode(self, connection, event):
        if not self._is_mine(connection):
            return
        nick = self.user.username
        channel = event.target

        if not channel.startswith("#"):
            return

        modes = event.arguments[0] if event.arguments else ""
        targets = event.arguments[1:] if len(event.arguments) > 1 else []

        adding = True
        target_idx = 0
        for char in modes:
            if char == "+":
                adding = True
            elif char == "-":
                adding = False
            elif char in "ovbklI":
                if target_idx < len(targets):
                    target = targets[target_idx]
                    target_idx += 1
                    if target.lower() == nick.lower():
                        if char == "o":
                            self.is_opped[channel] = adding
                            status = "opped" if adding else "deopped"
                            logger.info("[%s] %s in %s", nick, status, channel)
                else:
                    target_idx += 1

    def _on_join(self, connection, event):
        if not self._is_mine(connection):
            return
        nick = self.user.username
        joiner = irc.client.NickMask(event.source).nick if event.source else ""
        channel = event.target

        if joiner.lower() == nick.lower():
            self.joined_channels.add(channel)
            logger.info("[%s] Joined %s", nick, channel)

    def _on_disconnect(self, connection, event):
        if not self._is_mine(connection):
            return
        nick = self.user.username
        self.connected = False
        self.authenticated = False
        self.joined_channels.clear()
        self.is_opped.clear()
        if self._keepalive_task:
            self._keepalive_task.cancel()
            self._keepalive_task = None
        logger.info("[%s] Disconnected", nick)

    def _on_nick_in_use(self, connection, event):
        if not self._is_mine(connection):
            return
        nick = self.user.username
        new_nick = nick + "_"
        logger.warning("[%s] Nick in use, trying %s", nick, new_nick)
        connection.nick(new_nick)

    def _join_channels(self):
        if not self.connection:
            return
        for channel in self.channels:
            self.connection.join(channel)

    async def wait_ready(self, timeout: float = 30.0) -> bool:
        try:
            await asyncio.wait_for(self._login_event.wait(), timeout=timeout)
            return self.connected
        except asyncio.TimeoutError:
            logger.warning("[%s] Timed out waiting for ready state", self.user.username)
            return False

    def send_chat(self, channel: str, message: str) -> None:
        if self.connection and self.connected:
            self.connection.privmsg(channel, message)

    def send_mode(self, channel: str, mode: str, target: str) -> None:
        if self.connection and self.connected:
            self.connection.mode(channel, f"{mode} {target}")

    def send_kick(self, channel: str, target: str, reason: str = "simulated kick") -> None:
        if self.connection and self.connected:
            self.connection.kick(channel, target, reason)

    def disconnect(self) -> None:
        if self._keepalive_task:
            self._keepalive_task.cancel()
            self._keepalive_task = None
        if self.connection:
            try:
                self.connection.disconnect("Simulator shutting down")
            except Exception:
                pass

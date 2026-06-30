"""Connection manager: one per machine, dial-on-demand, reconnect/backoff.

`ConnectionManager` is the **single** QObject the QML UI talks to. It
owns:
- the list of registered machines
- per-machine dial/reconnect state (with exponential backoff)
- the in-flight `HttpAgentClient` (or `LocalConnection` for the local
  machine)
"""

from __future__ import annotations

import asyncio
import contextlib
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import Any

from PySide6.QtCore import (
    Property,
    QAbstractListModel,
    QByteArray,
    QModelIndex,
    QObject,
    QPersistentModelIndex,
    Qt,
    QThread,
    Signal,
    Slot,
)

from armar_manager.secrets import Machine, MachineStore, SecretTokenStore
from armar_server.contracts import PROTOCOL_VERSION, ConnectionState

from .client import AgentClient
from .connection import Tunnel, TunnelFactory, dial_remote, rotate_remote_token
from .hostkeys import HostKeyPinner
from .http import LocalConnection
from .tunnel import TunnelError


class MachineListModel(QAbstractListModel):
    NameRole = Qt.ItemDataRole.UserRole + 1
    HostRole = Qt.ItemDataRole.UserRole + 2
    StateRole = Qt.ItemDataRole.UserRole + 3

    countChanged = Signal()

    def __init__(self) -> None:
        super().__init__()
        self._machines: list[tuple[Machine, ConnectionState]] = []

    def roleNames(self) -> dict[int, QByteArray]:
        return {
            self.NameRole: QByteArray(b"name"),
            self.HostRole: QByteArray(b"host"),
            self.StateRole: QByteArray(b"state"),
        }

    def rowCount(self, parent: QModelIndex | QPersistentModelIndex = QModelIndex()) -> int:  # type: ignore[override]  # noqa: B008
        if parent.isValid():
            return 0
        return len(self._machines)

    def data(
        self,
        index: QModelIndex | QPersistentModelIndex,
        role: int = Qt.ItemDataRole.DisplayRole,
    ) -> Any:
        if not index.isValid() or index.row() >= len(self._machines):
            return None
        machine, state = self._machines[index.row()]
        if role in (self.NameRole, Qt.ItemDataRole.DisplayRole):
            return machine.name
        if role == self.HostRole:
            return f"{machine.ssh_user}@{machine.ssh_host}"
        if role == self.StateRole:
            return int(state)
        return None

    def replace(self, machines: list[tuple[Machine, ConnectionState]]) -> None:
        self.beginResetModel()
        self._machines = machines
        self.endResetModel()
        self.countChanged.emit()

    def update_state(self, name: str, state: ConnectionState) -> None:
        for row, (machine, _) in enumerate(self._machines):
            if machine.name == name:
                self._machines[row] = (machine, state)
                idx = self.index(row, 0)
                self.dataChanged.emit(idx, idx, [self.StateRole])
                return

    def add(self, machine: Machine) -> None:
        for existing, _ in self._machines:
            if existing.name == machine.name:
                return
        row = len(self._machines)
        self.beginInsertRows(QModelIndex(), row, row)
        self._machines.append((machine, ConnectionState.DISCONNECTED))
        self.endInsertRows()
        self.countChanged.emit()


@dataclass
class _Conn:
    machine: Machine
    tunnel: Tunnel | None = None
    client: AgentClient | None = None
    state: ConnectionState = ConnectionState.DISCONNECTED
    last_error: str | None = None
    backoff_s: float = 1.0
    reconnect_task: asyncio.Task[None] | None = None

    def cancel(self) -> None:
        if self.reconnect_task is not None:
            self.reconnect_task.cancel()


class ConnectionManager(QObject):
    machinesChanged = Signal()
    stateChanged = Signal(str, int, arguments=["name", "state"])  # name, ConnectionState

    def __init__(
        self,
        *,
        machine_store: MachineStore,
        host_key_pinner: HostKeyPinner,
        token_store: SecretTokenStore | None = None,
        tunnel_factory: TunnelFactory | None = None,
        max_backoff_s: float = 30.0,
    ) -> None:
        super().__init__()
        self._store = machine_store
        self._pinner = host_key_pinner
        self._token_store = token_store if token_store is not None else SecretTokenStore()
        self._tunnel_factory = tunnel_factory
        self._max_backoff_s = max_backoff_s
        self._conns: dict[str, _Conn] = {}
        self._pending_tasks: set[asyncio.Task[None]] = set()
        self._list_model = MachineListModel()
        for m in self._store.load():
            self._conns[m.name] = _Conn(machine=m)
            self._list_model.add(m)

    @Property(QObject, constant=True)
    def machines(self) -> QObject:  # type: ignore[type-var]
        return self._list_model

    @Slot(str, str, str)
    def addMachine(self, name: str, ssh_user: str, ssh_host: str) -> None:
        machine = Machine(name=name, ssh_user=ssh_user, ssh_host=ssh_host)
        self._conns[name] = _Conn(machine=machine)
        self._list_model.add(machine)
        # Persist.
        self._store.save([c.machine for c in self._conns.values()])
        self.machinesChanged.emit()

    @Slot(str)
    def removeMachine(self, name: str) -> None:
        conn = self._conns.pop(name, None)
        if conn is not None:
            conn.cancel()
            self._list_model.replace([(c.machine, c.state) for c in self._conns.values()])
            self._store.save([c.machine for c in self._conns.values()])
            self.machinesChanged.emit()

    @Slot(str)
    def connectMachine(self, name: str) -> None:
        """Connect to a machine by name (background task)."""

        # Schedule the dial in a background task; keep the UI responsive.
        async def _run() -> None:
            conn = self._conns.get(name)
            if conn is None:
                return
            await self._dial(conn)

        task = asyncio.create_task(_run())
        self._pending_tasks.add(task)
        task.add_done_callback(self._pending_tasks.discard)

    @Slot(str)
    def rotateToken(self, name: str) -> None:
        """Rotate a machine's agent token, then reconnect with the new one."""

        async def _run() -> None:
            conn = self._conns.get(name)
            if conn is None or conn.tunnel is None:
                return
            try:
                await rotate_remote_token(
                    conn.machine, token_store=self._token_store, tunnel=conn.tunnel
                )
            except Exception as exc:
                conn.last_error = str(exc)
                return
            # The running agent now expects the new token; re-dial so the
            # client picks it up from the store.
            await self._teardown(conn)
            await self._dial(conn)

        task = asyncio.create_task(_run())
        self._pending_tasks.add(task)
        task.add_done_callback(self._pending_tasks.discard)

    async def add_remote(self, name: str, ssh_user: str, ssh_host: str) -> None:
        """Add a machine and immediately dial it (background task)."""
        self.addMachine(name, ssh_user, ssh_host)
        await self._dial(self._conns[name])

    async def _dial(self, conn: _Conn) -> None:
        try:
            self._set_state(conn, ConnectionState.CONNECTING)
            if conn.machine.uds_path:
                # Local machine: no SSH, UDS with the token disabled.
                conn.client = LocalConnection(uds_path=conn.machine.uds_path)
                info = await conn.client.info()
                if info.protocol_version != PROTOCOL_VERSION:
                    raise TunnelError(
                        f"protocol version mismatch: agentd={info.protocol_version} "
                        f"manager={PROTOCOL_VERSION}"
                    )
            else:
                # Remote: SSH local-forward; the token is fetched once over
                # SSH-exec and persisted to the Secret Service (see
                # transport/connection.py).
                if self._tunnel_factory is not None:
                    result = await dial_remote(
                        conn.machine,
                        token_store=self._token_store,
                        tunnel_factory=self._tunnel_factory,
                    )
                else:
                    result = await dial_remote(conn.machine, token_store=self._token_store)
                conn.client = result.client
                conn.tunnel = result.tunnel
            conn.backoff_s = 1.0
            self._set_state(conn, ConnectionState.CONNECTED)
        except Exception as exc:
            await self._teardown(conn)
            conn.last_error = str(exc)
            self._set_state(conn, ConnectionState.FAILED)
            await self._schedule_reconnect(conn)

    async def _teardown(self, conn: _Conn) -> None:
        with contextlib.suppress(Exception):
            if conn.client is not None:
                await conn.client.close()
        with contextlib.suppress(Exception):
            if conn.tunnel is not None:
                await conn.tunnel.close()
        conn.client = None
        conn.tunnel = None

    async def _schedule_reconnect(self, conn: _Conn) -> None:
        """Reconnect with exponential backoff."""
        delay = min(conn.backoff_s, self._max_backoff_s)
        conn.backoff_s = min(delay * 2, self._max_backoff_s)
        self._set_state(conn, ConnectionState.RECONNECTING)

        async def _reconnect() -> None:
            await asyncio.sleep(delay)
            await self._dial(conn)

        if conn.reconnect_task is not None and not conn.reconnect_task.done():
            conn.reconnect_task.cancel()
        conn.reconnect_task = asyncio.create_task(_reconnect())

    def _set_state(self, conn: _Conn, state: ConnectionState) -> None:
        conn.state = state
        self._list_model.update_state(conn.machine.name, state)
        self.stateChanged.emit(conn.machine.name, int(state))


__all__ = ["ConnectionManager", "MachineListModel"]


# Re-export for callers
_ = (QThread, Awaitable, Callable, field)

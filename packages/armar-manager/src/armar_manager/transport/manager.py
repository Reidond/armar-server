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

from armar_manager.secrets import Machine, MachineStore
from armar_server.contracts import PROTOCOL_VERSION, ConnectionState

from .client import AgentClient
from .hostkeys import HostKeyPinner
from .http import HttpAgentClient, LocalConnection
from .tunnel import AsyncSshTunnel, TunnelError


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
    tunnel: AsyncSshTunnel | None = None
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
        max_backoff_s: float = 30.0,
    ) -> None:
        super().__init__()
        self._store = machine_store
        self._pinner = host_key_pinner
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

    async def add_remote(self, name: str, ssh_user: str, ssh_host: str) -> None:
        """Add a machine and immediately dial it (background task)."""
        self.addMachine(name, ssh_user, ssh_host)
        await self._dial(self._conns[name])

    async def _dial(self, conn: _Conn) -> None:
        try:
            self._set_state(conn, ConnectionState.CONNECTING)
            if conn.machine.uds_path:
                # Local machine: no SSH.
                conn.client = LocalConnection(uds_path=conn.machine.uds_path)
            else:
                # Remote: SSH local-forward + token.
                tunnel = AsyncSshTunnel(
                    ssh_user=conn.machine.ssh_user,
                    ssh_host=conn.machine.ssh_host,
                    ssh_port=conn.machine.ssh_port,
                )
                spec = await tunnel.open()
                # TODO: load token from Secret Service.
                # For P1, allow unauthenticated local connect; the
                # token requirement is enforced by the agentd on /info.
                conn.client = HttpAgentClient(
                    base_url=f"http://127.0.0.1:{spec.local_port}",
                    token=None,
                )
                conn.tunnel = tunnel
            info = await conn.client.info()
            if info.protocol_version != PROTOCOL_VERSION:
                raise TunnelError(
                    f"protocol version mismatch: agentd={info.protocol_version} "
                    f"manager={PROTOCOL_VERSION}"
                )
            conn.backoff_s = 1.0
            self._set_state(conn, ConnectionState.CONNECTED)
        except Exception as exc:
            conn.last_error = str(exc)
            with contextlib.suppress(Exception):
                if conn.client is not None:
                    await conn.client.close()
                if conn.tunnel is not None:
                    await conn.tunnel.close()
            conn.client = None
            conn.tunnel = None
            self._set_state(conn, ConnectionState.FAILED)
            await self._schedule_reconnect(conn)

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

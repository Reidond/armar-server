"""`armar-manager` entry point.

Boots a single shared qasync event loop, creates a QQmlApplicationEngine
that loads the QML in ``qml/Main.qml``, and exposes the connection
manager + view-models to QML.
"""

from __future__ import annotations

import asyncio
import signal
import sys

from PySide6.QtCore import QCoreApplication, QObject, QUrl, Signal, Slot
from PySide6.QtGui import QGuiApplication
from PySide6.QtQml import QQmlApplicationEngine

from .secrets import MachineStore
from .transport import HostKeyPinner
from .transport.manager import ConnectionManager


def main(argv: list[str] | None = None) -> int:
    """`armar-manager` entry point: a Kirigami app that talks to N agentd's."""
    import qasync

    app = QGuiApplication(sys.argv)
    QCoreApplication.setOrganizationName("Armar")
    QCoreApplication.setApplicationName("ArmarManager")

    loop = qasync.QEventLoop(app)
    asyncio.set_event_loop(loop)

    machine_store = MachineStore()
    host_key_pinner = HostKeyPinner()
    manager = ConnectionManager(
        machine_store=machine_store,
        host_key_pinner=host_key_pinner,
    )

    engine = QQmlApplicationEngine()
    engine.rootContext().setContextProperty("connectionManager", manager)
    engine.rootContext().setContextProperty("machineStore", machine_store)
    # Install an i18n shim as the QML context object. KDE's
    # KLocalizedContext has no PySide6 binding, so we expose the same
    # `i18n`/`i18nc` slots via a small QObject. Our QML uses `qsTr()`
    # (the Qt Linguist path); the shim is here for kirigami-addons and
    # any future `i18n()` call sites. See armar_manager.i18n.
    from .i18n import I18nShim

    engine.rootContext().setContextObject(I18nShim())

    qml = Path(__file__).parent / "qml" / "Main.qml"
    engine.load(QUrl.fromLocalFile(str(qml)))
    if not engine.rootObjects():
        return 1

    # Wire SIGINT/SIGTERM to the Qt loop so Ctrl-C quits cleanly.
    signal.signal(signal.SIGINT, signal.SIG_DFL)

    with loop:
        loop.run_forever()
    return 0


# QObject-friendly wrappers --------------------------------------------------


from pathlib import Path  # noqa: E402


class _Bridge(QObject):
    """Re-export a few async helpers as Qt slots for QML."""

    requestAddMachine = Signal(str, str, str, arguments=["name", "user", "host"])

    def __init__(self, manager: ConnectionManager, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._manager = manager

    @Slot(str, str, str)
    def addMachine(self, name: str, user: str, host: str) -> None:
        """Add a machine: SSH-exec the protocol handshake, then register."""
        import asyncio

        async def _run() -> None:
            await self._manager.add_remote(name, user, host)

        self._pending_tasks: set[asyncio.Task[None]] = set()
        task = asyncio.create_task(_run())
        self._pending_tasks.add(task)
        task.add_done_callback(self._pending_tasks.discard)


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))


__all__ = ["main"]

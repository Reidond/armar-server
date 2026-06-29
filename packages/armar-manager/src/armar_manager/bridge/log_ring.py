"""Bounded ring buffer + QAbstractListModel for the live-log view.

QML reads from `LogRingModel`; the manager writes into it as SSE
events arrive.
"""

from __future__ import annotations

from collections import deque
from typing import Any

from PySide6.QtCore import (
    QAbstractListModel,
    QByteArray,
    QModelIndex,
    QObject,
    QPersistentModelIndex,
    Qt,
    Signal,
    Slot,
)


class LogRingModel(QAbstractListModel):
    SeqRole = Qt.ItemDataRole.UserRole + 1
    TsRole = Qt.ItemDataRole.UserRole + 2
    StreamRole = Qt.ItemDataRole.UserRole + 3
    LineRole = Qt.ItemDataRole.UserRole + 4

    countChanged = Signal()

    def __init__(self, capacity: int = 1000) -> None:
        super().__init__()
        self._capacity = capacity
        self._ring: deque[tuple[int, float, str, str]] = deque(maxlen=capacity)

    def roleNames(self) -> dict[int, QByteArray]:
        return {
            self.SeqRole: QByteArray(b"seq"),
            self.TsRole: QByteArray(b"ts"),
            self.StreamRole: QByteArray(b"stream"),
            self.LineRole: QByteArray(b"line"),
        }

    def rowCount(  # type: ignore[override]
        self, parent: QModelIndex | QPersistentModelIndex = QModelIndex()  # noqa: B008
    ) -> int:
        if parent.isValid():
            return 0
        return len(self._ring)

    def data(  # type: ignore[override]
        self,
        index: QModelIndex | QPersistentModelIndex,
        role: int = Qt.ItemDataRole.DisplayRole,
    ) -> Any:
        if not index.isValid() or index.row() >= len(self._ring):
            return None
        seq, ts, stream, line = self._ring[index.row()]
        if role == self.SeqRole:
            return seq
        if role == self.TsRole:
            return ts
        if role == self.StreamRole:
            return stream
        if role == self.LineRole:
            return line
        if role == Qt.ItemDataRole.DisplayRole:
            return line
        return None

    @Slot(int, str, str, float)
    def append(self, seq: int, stream: str, line: str, ts: float = 0.0) -> None:
        # Bounded ring — items drop off the head automatically.
        row = len(self._ring)
        if row >= self._capacity:
            self.beginRemoveRows(QModelIndex(), 0, 0)
            self._ring.popleft()
            self.endRemoveRows()
            row -= 1
            # After popleft, refresh all roles for the new first row.
            top = self.index(0, 0)
            self.dataChanged.emit(top, top)
        self.beginInsertRows(QModelIndex(), row, row)
        self._ring.append((seq, ts, stream, line))
        self.endInsertRows()
        self.countChanged.emit()

    @Slot()
    def clear(self) -> None:
        if not self._ring:
            return
        self.beginResetModel()
        self._ring.clear()
        self.endResetModel()
        self.countChanged.emit()


__all__ = ["LogRingModel"]


# Touch QObject so ruff does not strip the import.
_ = QObject

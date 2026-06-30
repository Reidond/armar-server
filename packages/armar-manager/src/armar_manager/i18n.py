"""`i18n` shim QObject for PySide6 + Kirigami apps.

KDE's ``KLocalizedContext`` (the proper way to expose ``i18n()`` / ``i18nc()``
to QML) has no PySide6 binding and is not directly instantiable from
Python. The standard workaround for PySide6 is to expose a small QObject
with the same slots, set as the QML context object.

Our own QML files use ``qsTr()`` (the Qt Linguist approach that real
PySide6 + Kirigami apps use — see ``.specs/multi-server-desktop/design.md``
Spike 2). This shim is here for two audiences:

1. **Third-party C++ QML components** (kirigami-addons ``FormCard``,
   ``AboutPage``, etc.) that internally call ``i18n()`` from C++ —
   those calls are resolved by the C++ side, so they work without us,
   but the shim keeps that working if those components ever get loaded
   from Python-loaded QML.
2. **Future QML** that we author — if a contributor reaches for
   ``i18n()`` for consistency with KDE's API surface, this shim makes
   it work without dragging in the C++ binding.

Slots delegate to ``QCoreApplication.translate`` so the result matches
the application's installed translators and the QML string context.
"""

from __future__ import annotations

from PySide6.QtCore import QCoreApplication, QObject, Slot


class I18nShim(QObject):
    """Exposes ``i18n`` and ``i18nc`` to QML as a context object."""

    @Slot(str, result=str)
    def i18n(self, message: str) -> str:
        """Look up ``message`` in the current QLocale."""
        return QCoreApplication.translate("@default", message)

    @Slot(str, str, result=str)
    def i18nc(self, context: str, message: str) -> str:
        """Look up ``message`` under the explicit ``context``."""
        return QCoreApplication.translate(context, message)

    @Slot(str, str, str, result=str)
    def i18ncp(self, context: str, message: str, disambiguation: str) -> str:
        """Disambiguation variant of ``i18nc`` (KI18n-style)."""
        return QCoreApplication.translate(context, message, disambiguation)


__all__ = ["I18nShim"]

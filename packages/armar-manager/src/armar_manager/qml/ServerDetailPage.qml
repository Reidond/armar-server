// Server detail page: tabs for Overview / Mods / Config / Logs.
//
// Kirigami HIG: NavigationTabBar; FormLayout for config; uses
// ConnectionManager-exposed QObject methods via property bindings.

import QtQuick
import QtQuick.Controls as Controls
import QtQuick.Layouts
import org.kde.kirigami as Kirigami

Kirigami.Page {
    id: root
    title: i18n("Server")

    property string slug: ""

    actions: [
        Kirigami.Action {
            text: i18n("Refresh")
            icon.name: "view-refresh-symbolic"
            onTriggered: refresh()
        }
    ]

    function refresh() {
        // P2: trigger status refresh
    }

    ColumnLayout {
        anchors.fill: parent
        spacing: Kirigami.Units.smallSpacing

        Kirigami.NavigationTabBar {
            id: tabs
            Layout.fillWidth: true
            actions: [
                Kirigami.Action { text: i18n("Overview"); checked: true },
                Kirigami.Action { text: i18n("Mods") },
                Kirigami.Action { text: i18n("Config") },
                Kirigami.Action { text: i18n("Logs") }
            ]
        }

        StackLayout {
            Layout.fillWidth: true
            Layout.fillHeight: true
            currentIndex: tabs.currentIndex

            // Overview
            Kirigami.PlaceholderMessage {
                text: i18n("No status yet")
                explanation: i18nc("@info", "Status will appear here when the agent is reachable.")
                visible: true
            }

            // Mods
            Kirigami.PlaceholderMessage {
                text: i18n("Mods management")
                explanation: i18nc("@info", "Coming in Phase P3.")
            }

            // Config
            Kirigami.PlaceholderMessage {
                text: i18n("Config editor")
                explanation: i18nc("@info", "Coming in Phase P3.")
            }

            // Logs
            Kirigami.PlaceholderMessage {
                text: i18n("Live logs")
                explanation: i18nc("@info", "Coming in Phase P2.")
            }
        }
    }
}

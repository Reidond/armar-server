// Server detail page: tabs for Overview / Mods / Config / Logs.
//
// Kirigami HIG: NavigationTabBar; FormLayout for config; uses
// ConnectionManager-exposed QObject methods via property bindings.

import QtQuick
import QtQuick.Layouts
import org.kde.kirigami as Kirigami

Kirigami.Page {
    id: root
    title: qsTr("Server")

    property string slug: ""

    actions: [
        Kirigami.Action {
            text: qsTr("Refresh")
            icon.name: "view-refresh-symbolic"
            onTriggered: root.refresh()
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
                Kirigami.Action { text: qsTr("Overview"); checked: true },
                Kirigami.Action { text: qsTr("Mods") },
                Kirigami.Action { text: qsTr("Config") },
                Kirigami.Action { text: qsTr("Logs") }
            ]
        }

        StackLayout {
            Layout.fillWidth: true
            Layout.fillHeight: true
            currentIndex: tabs.currentIndex

            // Overview
            Kirigami.PlaceholderMessage {
                text: qsTr("No status yet")
                explanation: qsTr("Status will appear here when the agent is reachable.")
                visible: true
            }

            // Mods
            Kirigami.PlaceholderMessage {
                text: qsTr("Mods management")
                explanation: qsTr("Coming in Phase P3.")
            }

            // Config
            Kirigami.PlaceholderMessage {
                text: qsTr("Config editor")
                explanation: qsTr("Coming in Phase P3.")
            }

            // Logs
            Kirigami.PlaceholderMessage {
                text: qsTr("Live logs")
                explanation: qsTr("Coming in Phase P2.")
            }
        }
    }
}

// Config pane (P3): edit server.toml fields with secrets masked.
//
// Password fields show only whether a value is set; the agent enforces
// fastValidation = true for public servers.

import QtQuick
import QtQuick.Controls as Controls
import QtQuick.Layouts
import org.kde.kirigami as Kirigami

Kirigami.ScrollablePage {
    id: root
    title: i18n("Config")

    property string slug: ""
    property var client: null

    ColumnLayout {
        anchors.fill: parent
        spacing: Kirigami.Units.smallSpacing

        Controls.TextField {
            id: nameField
            placeholderText: i18n("Server name")
            Layout.fillWidth: true
        }
        Controls.TextField {
            id: scenarioField
            placeholderText: i18n("Scenario id")
            Layout.fillWidth: true
        }
        Controls.TextField {
            id: passwordField
            placeholderText: i18n("Password (write-only)")
            echoMode: Controls.TextInput.Password
            Layout.fillWidth: true
        }
        Controls.CheckBox {
            id: fastValCheck
            text: i18n("fastValidation (forced true for public servers)")
            checked: true
            enabled: false
        }
        Controls.Button {
            text: i18n("Save")
            onClicked: {
                // P3: PUT /api/v1/instances/{slug}/config
            }
        }
    }
}

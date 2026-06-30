// Main QML for armar-manager.
//
// Kirigami-based shell with a global drawer (machines), a server list
// page, and a server detail page (placeholder for P3). Uses Kirigami
// HIG: Kirigami.Units / Kirigami.Theme — no hardcoded px or colors.

import QtQuick
import QtQuick.Controls as Controls
import QtQuick.Layouts
import org.kde.kirigami as Kirigami

Kirigami.ApplicationWindow {
    id: root
    width: 1100
    height: 720
    visible: true
    title: qsTr("Armar Manager")

    globalDrawer: Kirigami.GlobalDrawer {
        id: drawer
        title: qsTr("Machines")
        actions: [
            Kirigami.Action {
                text: qsTr("Add machine…")
                icon.name: "list-add-symbolic"
                onTriggered: addMachineDialog.open()
            }
        ]
        // P3: per-machine entries are appended to `actions` from
        // connectionManager.machines once a machine is connected.
    }

    pageStack.initialPage: Kirigami.Page {
        title: qsTr("Servers")
        ColumnLayout {
            anchors.fill: parent
            Kirigami.PlaceholderMessage {
                text: qsTr("No machine connected")
                visible: connectionManager.machines.rowCount === 0 // qmllint disable unqualified
                explanation: qsTr("Add a managed machine from the drawer.")
            }
        }
    }

    // --- Add-Machine dialog ----------------------------------------------
    Controls.Dialog {
        id: addMachineDialog
        title: qsTr("Add machine")
        standardButtons: Controls.Dialog.Ok | Controls.Dialog.Cancel
        modal: true
        anchors.centerIn: parent
        width: Kirigami.Units.gridUnit * 18

        ColumnLayout {
            spacing: Kirigami.Units.smallSpacing
            Controls.TextField {
                id: nameField
                placeholderText: qsTr("Name (e.g. home-server)")
                Layout.fillWidth: true
            }
            Controls.TextField {
                id: userField
                placeholderText: qsTr("SSH user")
                text: "armar"
                Layout.fillWidth: true
            }
            Controls.TextField {
                id: hostField
                placeholderText: qsTr("SSH host")
                Layout.fillWidth: true
            }
        }

        onAccepted: {
            connectionManager.addMachine( // qmllint disable unqualified
                nameField.text.trim(),
                userField.text.trim(),
                hostField.text.trim()
            );
        }
    }
}

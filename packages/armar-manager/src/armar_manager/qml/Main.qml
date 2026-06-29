// Main QML for armar-manager.
//
// Kirigami-based shell with a global drawer (machines), a server list
// page, and a server detail page (placeholder for P3). Uses Kirigami
// HIG: Kirigami.Units / Kirigami.Theme — no hardcoded px or colors.

import QtQuick
import QtQuick.Controls as Controls
import org.kde.kirigami as Kirigami

Kirigami.ApplicationWindow {
    id: root
    width: 1100
    height: 720
    visible: true
    title: i18nc("@title:window", "Armar Manager")

    globalDrawer: Kirigami.GlobalDrawer {
        id: drawer
        title: i18n("Machines")
        actions: [
            Kirigami.Action {
                text: i18n("Add machine…")
                icon.name: "list-add-symbolic"
                onTriggered: addMachineDialog.open()
            }
        ]
        model: connectionManager.machines
    }

    pageStack.initialPage: Kirigami.Page {
        title: i18n("Servers")
        ColumnLayout {
            anchors.fill: parent
            Kirigami.PlaceholderMessage {
                text: i18n("No machine connected")
                visible: connectionManager.machines.rowCount === 0
                explanation: i18n("Add a managed machine from the drawer.")
            }
        }
    }

    // --- Add-Machine dialog ----------------------------------------------
    Dialog {
        id: addMachineDialog
        title: i18n("Add machine")
        standardButtons: Dialog.Ok | Dialog.Cancel
        modal: true
        anchors.centerIn: parent
        width: Kirigami.Units.gridUnit * 18

        ColumnLayout {
            spacing: Kirigami.Units.smallSpacing
            Controls.TextField {
                id: nameField
                placeholderText: i18n("Name (e.g. home-server)")
                Layout.fillWidth: true
            }
            Controls.TextField {
                id: userField
                placeholderText: i18n("SSH user")
                text: "armar"
                Layout.fillWidth: true
            }
            Controls.TextField {
                id: hostField
                placeholderText: i18n("SSH host")
                Layout.fillWidth: true
            }
        }

        onAccepted: {
            connectionManager.addMachine(
                nameField.text.trim(),
                userField.text.trim(),
                hostField.text.trim()
            );
        }
    }
}

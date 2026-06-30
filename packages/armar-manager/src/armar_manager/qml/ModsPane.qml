// Mods pane (P3): list mods + add Workshop URL + resolve dependencies.
//
// Talks to ConnectionManager's AgentClient (via a bridge QObject) to
// call POST /api/v1/instances/{slug}/mods and POST .../resolve.

import QtQuick
import QtQuick.Controls as Controls
import QtQuick.Layouts
import org.kde.kirigami as Kirigami

Kirigami.PlaceholderMessage {
    id: root
    text: qsTr("Mods management")
    explanation: qsTr("Add Workshop URLs and resolve the dependency closure.")

    property string slug: ""
    property var client: null
    property var model: null

    // PlaceholderMessage is itself a ColumnLayout, so this nested layout
    // is layout-managed — use Layout.* sizing, not anchors.
    ColumnLayout {
        Layout.fillWidth: true
        spacing: Kirigami.Units.smallSpacing

        Controls.TextField {
            id: urlField
            placeholderText: qsTr("Workshop URL or hex id")
            Layout.fillWidth: true
        }
        Controls.Button {
            text: qsTr("Add")
            enabled: urlField.text.length > 0 && root.client !== null
            onClicked: {
                // P3: call into the bridge QObject
            }
        }
        Controls.Button {
            text: qsTr("Resolve dependencies")
            enabled: root.client !== null
            onClicked: {
                // P3: POST /api/v1/instances/{slug}/resolve
            }
        }
    }
}

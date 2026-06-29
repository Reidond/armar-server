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
    text: i18n("Mods management")
    explanation: i18nc("@info", "Add Workshop URLs and resolve the dependency closure.")

    property string slug: ""
    property var client: null
    property var model: null

    ColumnLayout {
        anchors.fill: parent
        spacing: Kirigami.Units.smallSpacing

        Controls.TextField {
            id: urlField
            placeholderText: i18n("Workshop URL or hex id")
            Layout.fillWidth: true
        }
        Controls.Button {
            text: i18n("Add")
            enabled: urlField.text.length > 0 && root.client !== null
            onClicked: {
                // P3: call into the bridge QObject
            }
        }
        Controls.Button {
            text: i18n("Resolve dependencies")
            enabled: root.client !== null
            onClicked: {
                // P3: POST /api/v1/instances/{slug}/resolve
            }
        }
    }
}

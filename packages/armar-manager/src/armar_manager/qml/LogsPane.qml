// Logs pane (P2): show a scrollable list of live log lines.
//
// The LogRingModel is exposed by the manager; the model.append() slot
// is called by the SSE consumer task (transport level).

import QtQuick
import QtQuick.Controls as Controls
import QtQuick.Layouts
import org.kde.kirigami as Kirigami

Kirigami.ScrollablePage {
    id: root
    title: i18n("Logs")

    property string slug: ""
    property var model: null
    property int lastSeq: 0

    ColumnLayout {
        anchors.fill: parent
        spacing: 0

        RowLayout {
            Layout.fillWidth: true
            Kirigami.Heading {
                text: i18n("Live logs")
                level: 3
            }
            Item { Layout.fillWidth: true }
            Controls.Button {
                text: i18n("Clear")
                onClicked: if (root.model) root.model.clear()
            }
        }

        ListView {
            id: list
            Layout.fillWidth: true
            Layout.fillHeight: true
            model: root.model
            clip: true
            spacing: 0

            delegate: Controls.Label {
                width: list.width
                text: (model.stream === "stderr" ? "[err] " : "") + model.line
                font.family: "monospace"
                wrapMode: Controls.Text.Wrap
                color: model.stream === "stderr" ? Kirigami.Theme.negativeTextColor : Kirigami.Theme.textColor
            }

            onCountChanged: {
                if (count > 0) {
                    positionViewAtEnd();
                }
            }
        }
    }
}

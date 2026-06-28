# Kirigami Component Catalog — Snippets

Companion to SKILL.md §1–§4 and §6. Load when you need the exact shape of a
specific Kirigami / kirigamiaddons component. Every name is verbatim from the KDE
develop-kde-org getting-started docs. HIG rules are noted inline; the full HIG is
in [hig-guidelines.md](hig-guidelines.md).

Imports (Qt6, unversioned, namespaced):

```qml
import QtQuick
import QtQuick.Layouts
import QtQuick.Controls as Controls
import org.kde.kirigami as Kirigami
import org.kde.kirigami.delegates as KD          // only when using subtitle delegates
import org.kde.kirigamiaddons.formcard as FormCard  // only for FormCard.*
```

## App Skeleton — Entrypoints

The QML `Main.qml` (SKILL.md §1) is identical across languages; only the glue
differs.

**C++ `main.cpp`** — `QApplication` (not `QGuiApplication`) forces Breeze:

```cpp
#include <QApplication>
#include <QQmlApplicationEngine>
#include <QQuickStyle>
#include <KLocalizedContext>
#include <KLocalizedString>
#include <KIconTheme>

int main(int argc, char *argv[]) {
    KIconTheme::initTheme();                       // BEFORE QApplication
    QApplication app(argc, argv);
    KLocalizedString::setApplicationDomain("tutorial");
    QApplication::setDesktopFileName(QStringLiteral("org.kde.tutorial"));
    QApplication::setStyle(QStringLiteral("breeze"));
    if (qEnvironmentVariableIsEmpty("QT_QUICK_CONTROLS_STYLE"))
        QQuickStyle::setStyle(QStringLiteral("org.kde.desktop"));

    QQmlApplicationEngine engine;
    engine.rootContext()->setContextObject(new KLocalizedContext(&engine));
    engine.loadFromModule("org.kde.tutorial", "Main");  // URI = ecm_add_qml_module URI
    if (engine.rootObjects().isEmpty()) return -1;
    return app.exec();
}
```

**Python (PySide6) `app.py`** — `QGuiApplication`, style via env var:

```python
import os, sys, signal
from importlib.resources import files
from PySide6.QtGui import QGuiApplication
from PySide6.QtCore import QUrl
from PySide6.QtQml import QQmlApplicationEngine

def main():
    app = QGuiApplication(sys.argv)
    engine = QQmlApplicationEngine()
    signal.signal(signal.SIGINT, signal.SIG_DFL)            # Ctrl+C closes the app
    if not os.environ.get("QT_QUICK_CONTROLS_STYLE"):
        os.environ["QT_QUICK_CONTROLS_STYLE"] = "org.kde.desktop"
    base_path = files('kirigami_python').joinpath('qml', 'Main.qml')
    engine.load(QUrl(f"{base_path}"))                       # MANIFEST.in must bundle *.qml
    app.exec()
```

**CMake/ECM** — C++ build deps via `find_package`, QML runtime deps via
`ecm_find_qmlmodule`; the executable *is* the QML module:

```cmake
find_package(ECM 6.0.0 REQUIRED NO_MODULE)
set(CMAKE_MODULE_PATH ${ECM_MODULE_PATH})
include(KDEInstallDirs); include(ECMQmlModule); include(ECMFindQmlModule)
find_package(Qt6 REQUIRED COMPONENTS Quick Gui QuickControls2 Widgets)
find_package(KF6 REQUIRED COMPONENTS Kirigami I18n CoreAddons QQC2DesktopStyle IconThemes)
ecm_find_qmlmodule(org.kde.kirigami REQUIRED)
# src/: add_executable -> ecm_add_qml_module(<tgt> URI org.kde.tutorial)
#       -> ecm_target_qml_sources(<tgt> SOURCES Main.qml) -> target_link_libraries -> install
```

Every app installs a reverse-DNS `.desktop` file (e.g. `org.kde.tutorial.desktop`)
to `${KDE_INSTALL_APPDIR}`; on Wayland the icon only works if `setDesktopFileName`
matches its basename. Run any app in convergent/mobile mode with
`QT_QUICK_CONTROLS_MOBILE=1`.

## Pages & Drawers

```qml
Kirigami.ScrollablePage {                 // scrollable; do NOT nest a Controls.ScrollView
    title: i18nc("@title", "Kountdown")
    supportsRefreshing: true              // pull-to-refresh
    onRefreshingChanged: if (refreshing) myModel.refresh()
    titleDelegate: Kirigami.SearchField { // search in the toolbar title area
        Layout.fillWidth: true
        onTextChanged: proxyModel.filterText = text
    }
    ListView { id: listView; model: myModel; delegate: myDelegate }
}
```

```qml
// OverlayDrawer — modal or inline edge drawer
Kirigami.OverlayDrawer {
    id: bottomDrawer
    edge: Qt.BottomEdge                    // Top/Right/Bottom/LeftEdge
    modal: true                            // false => inline (no darken, not dismissed)
    contentItem: RowLayout {
        Controls.Label { Layout.fillWidth: true; text: "Say hello to my little drawer!" }
        Controls.Button { text: "Close"; onClicked: bottomDrawer.close() }
    }
}
```

GlobalDrawer / ContextDrawer: see SKILL.md §2.

## Actions & ActionToolBar

```qml
Kirigami.ActionToolBar {
    alignment: Qt.AlignCenter              // default left
    actions: [
        Kirigami.Action { text: "Beep"; icon.name: "notifications"
                          onTriggered: showPassiveNotification("BEEP!") },
        Kirigami.Action {                  // nested => overflow submenu
            text: "Action Menu"; icon.name: "overflow-menu"
            Kirigami.Action { text: "Deet"; icon.name: "notifications" }
        },
        Kirigami.Action {                  // custom render
            icon.name: "search"
            displayComponent: Kirigami.SearchField {}
            displayHint: Kirigami.DisplayHints.KeepVisible
        }
    ]
}

// Contextual actions inside a text field use rightActions, NOT actions:
Kirigami.ActionTextField {
    id: searchField
    rightActions: [
        Kirigami.Action { icon.name: "edit-clear"; visible: searchField.text !== ""
                          onTriggered: searchField.text = "" }
    ]
}
```

## Cards

```qml
Kirigami.AbstractCard {
    header: Kirigami.Heading { text: qsTr("AbstractCard"); level: 2 }
    contentItem: Controls.Label { wrapMode: Text.WordWrap; text: "..." }
}

Kirigami.Card {
    banner { source: "../banner.jpg"; title: "Title"; titleAlignment: Qt.AlignLeft | Qt.AlignBottom }
    actions: [
        Kirigami.Action { text: qsTr("Action1"); icon.name: "add-placemark" }
    ]
    contentItem: Controls.Label { wrapMode: Text.WordWrap; text: "My Text" }
}

ColumnLayout {                              // CardsLayout MUST sit in a ColumnLayout
    Kirigami.CardsLayout {                  // 2-column responsive grid (maximumColumns)
        Kirigami.Card { headerOrientation: Qt.Horizontal; contentItem: Controls.Label { text: "..." } }
    }
}

Kirigami.CardsListView {                    // ListView for cards
    model: 100
    delegate: Kirigami.AbstractCard {
        // NEVER put a Layout as contentItem — binding loops. Wrap in a plain Item:
        contentItem: Item {
            implicitWidth: grid.implicitWidth
            implicitHeight: grid.implicitHeight
            GridLayout {
                id: grid
                anchors { left: parent.left; top: parent.top; right: parent.right }  // NO bottom
                columns: width > Kirigami.Units.gridUnit * 20 ? 4 : 2
                Kirigami.Heading { level: 2; text: qsTr("Product ") + modelData }
            }
        }
    }
}
```

## Chips

```qml
ListModel { id: chips; ListElement { text: "Chip 1" } }
ColumnLayout {                              // wrap Repeater to prevent binding loops
    Repeater {
        model: chips
        Kirigami.Chip {                     // inherits AbstractButton
            text: modelData
            onClicked: { /* edit */ }
            onRemoved: chips.remove(index)  // optional delete button
        }
    }
}
```

## FormLayout (settings)

HIG: the standard way to build a settings/config page; labels in **sentence case**.

```qml
Kirigami.FormLayout {
    anchors.fill: parent
    wideMode: true                          // force desktop double-column (false = mobile)
    Controls.TextField { Kirigami.FormData.label: "Name:" }
    Kirigami.Separator {
        Kirigami.FormData.isSection: true   // section header (best on a Separator or Item)
        Kirigami.FormData.label: "New section"
    }
    ColumnLayout {                          // group multi-component field under one label
        Kirigami.FormData.label: "Radio buttons"
        Kirigami.FormData.labelAlignment: Qt.AlignTop   // for multi-line fields
        Controls.RadioButton { text: "Radio 1"; checked: true }
    }
}
```

## InlineMessage

HIG: use for invalid input (and disable confirm/send). `visible` defaults to false.

```qml
Kirigami.InlineMessage {
    Layout.fillWidth: true
    visible: true
    text: "Hey! Let me tell you something positive!"
    type: Kirigami.MessageType.Positive     // Information(default)/Positive/Warning/Error
    showCloseButton: true
    position: Kirigami.InlineMessage.Position.Header   // page/app-wide scope
    onLinkActivated: Qt.openUrlExternally(link)
    actions: [ Kirigami.Action { text: qsTr("Add text"); icon.name: "list-add" } ]
}
```

## Dialogs & OverlaySheet

HIG: dialogs interrupt — use only for a decision that blocks the app; never two at
once; never open one from another.

```qml
Kirigami.Dialog {                            // general, incl. input
    id: addDialog
    title: i18nc("@title:window", "Add kountdown")
    standardButtons: Kirigami.Dialog.Ok | Kirigami.Dialog.Cancel  // .NoButton + customFooterActions for fully custom
    padding: Kirigami.Units.largeSpacing
    preferredWidth: Kirigami.Units.gridUnit * 20
    Kirigami.FormLayout {
        Controls.TextField { id: nameField; Kirigami.FormData.label: i18nc("@label:textbox", "Name*:") }
    }
    Component.onCompleted: {                  // enable Ok conditionally
        const button = standardButton(Kirigami.Dialog.Ok);
        button.enabled = Qt.binding(() => nameField.text.length > 0);
    }
    onAccepted: { /* append + clear */ }
}

Kirigami.PromptDialog {
    title: i18n("Delete file")
    subtitle: i18n("Are you sure?")          // adding any child component REPLACES the subtitle
    standardButtons: Kirigami.Dialog.Ok | Kirigami.Dialog.Cancel
    onAccepted: console.info("File deleted")
}

Kirigami.MenuDialog {                        // choose among actions
    title: i18n("Track options")
    actions: [
        Kirigami.Action { icon.name: "media-playback-start"; text: i18n("Play") },
        Kirigami.Action { enabled: false; icon.name: "document-open-folder"; text: i18n("Show in folder") }
    ]
}

Kirigami.OverlaySheet {                      // read-only narrow scrollable; NOT for input
    id: sheet
    header: Kirigami.Heading { text: "Edit Chip" }
    footer: DialogButtonBox {
        standardButtons: DialogButtonBox.Ok | DialogButtonBox.Cancel
        onAccepted: sheet.close(); onRejected: sheet.close()
    }
    TextField { id: editTextField }
}
// open/close via .open() / .close()
```

## List Delegates

Set `width: ListView.view.width` — never `anchors.fill: parent`, no bottom anchor.
Prefer Qt delegates; use Kirigami delegates for subtitle + icon.

```qml
ListView {
    model: productsModel
    delegate: Controls.ItemDelegate {
        width: ListView.view.width
        required property string product
        required property int index
        text: `${product}  ·  index ${index}`
    }
}

// Kirigami subtitle delegate (import org.kde.kirigami.delegates as KD):
KD.CheckSubtitleDelegate {
    width: ListView.view.width
    text: model.product
    subtitle: `index ${model.index}`
    icon.name: "kde"
}
// TitleSubtitle / IconTitleSubtitle are meant to OVERRIDE a Qt delegate's contentItem.
```

A `ListView` inside a `ScrollablePage` needs no `anchors.fill`; inside a plain
`Kirigami.Page` it needs explicit dimensions.

## PlaceholderMessage & Progress

```qml
Kirigami.PlaceholderMessage {
    anchors.centerIn: parent
    width: parent.width - (Kirigami.Units.largeSpacing * 4)
    visible: listView.count === 0
    icon.name: "folder-open"
    text: i18n("No data found")
    helpfulAction: Kirigami.Action { text: i18n("Load data"); icon.name: "document-open" }
}

// QtQuick.Controls (NOT Kirigami):
Controls.ProgressBar { Layout.fillWidth: true; from: 0; to: 100; value: 50; indeterminate: false }
Controls.BusyIndicator { anchors.centerIn: parent; running: true }
// Kirigami.LoadingPlaceholder for determinate-or-varying progress.
```

## FormCard (kirigamiaddons settings)

Two imports required (core Kirigami + addons). Inside a `FormCard` do NOT use
Layout attached props / anchors / positioners — it auto-layouts by child order.

```qml
import org.kde.kirigami as Kirigami
import org.kde.kirigamiaddons.formcard as FormCard

FormCard.FormCardPage {                       // inherits ScrollablePage; internal layout
    FormCard.FormHeader { title: i18n("General") }
    FormCard.FormCard {
        FormCard.FormSectionText { text: i18n("Online Account Settings") }
        FormCard.FormTextDelegate {
            leading: Kirigami.Icon { source: "user" }
            text: "John Doe"; description: i18n("The Maintainer")
        }
        FormCard.FormButtonDelegate {         // leading only; right side = nav arrow
            icon.name: "settings-configure"
            text: i18n("Single Settings Page")
            onClicked: root.pageStack.layers.push(settingspage)
        }
        FormCard.FormSwitchDelegate { id: autosave; text: i18n("Enabled") }
        FormCard.FormDelegateSeparator { above: autosave; below: radio1 }
        FormCard.FormRadioDelegate { id: radio1; text: i18n("After every change")
                                     visible: autosave.checked }
        FormCard.FormCheckDelegate {
            text: i18n("Show Tray Icon")
            onToggled: console.info(checkState ? "shown" : "hidden")
        }
        FormCard.FormComboBoxDelegate {
            text: i18n("Default Profile")
            description: i18n("The profile to be loaded by default.")
            displayMode: FormCard.FormComboBoxDelegate.ComboBox   // .ComboBox/.Dialog/.Page
            currentIndex: 0
            editable: false
            model: ["Work", "Personal"]
        }
    }
}
```

In a plain `Kirigami.ScrollablePage`, wrap each `FormCard.FormCard` in a
`ColumnLayout` (FormCard must be its direct child).

## AboutPage — two non-interchangeable types

```qml
// Addon (auto-reads KAboutData::setApplicationData; zero config):
Component { id: aboutpage; FormCard.AboutPage {} }
Component { id: aboutkde;  FormCard.AboutKDE {} }
// push from a FormButtonDelegate.onClicked: root.pageStack.layers.push(aboutpage)

// Core Kirigami (needs the aboutData property — the KAboutData singleton):
Component { id: corePage; Kirigami.AboutPage { aboutData: About } }
```

C++ glue exposes `KAboutData` to QML via
`qmlRegisterSingletonType("org.kde.example", 1, 0, "About", factory)` returning
`engine->toScriptValue(KAboutData::applicationData())`. The addon `AboutPage` can
alternatively take a JSON object (keys: `displayName`, `version`, `description`,
`homepage`, `copyrightStatement`, `authors`, `licenses` …); with JSON you must
still set the window icon in C++.

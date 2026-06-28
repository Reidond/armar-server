# QtQuick.Controls + QtQuick.Layouts + Anchors

Companion to SKILL.md §6. Load when placing widgets, building forms/toolbars, or
deciding between anchors and Layouts.

## 1. The canonical import header

```qml
import QtQuick                            // Item, Text, anchors, Qt.* / Text.* enums
import QtQuick.Layouts                    // ColumnLayout/RowLayout/GridLayout + Layout.*
import QtQuick.Controls as Controls       // every control used as Controls.X
import org.kde.kirigami as Kirigami       // Kirigami.X
```

QtQuick Controls is ALWAYS aliased `as Controls`; Kirigami `as Kirigami`. QtQuick
and QtQuick.Layouts are imported WITHOUT an alias.

## 2. QtQuick.Controls widget catalog

| Type | Key properties / signals |
|---|---|
| `Controls.Button` | `text`, `onClicked`, `checkable`, `checked`, `icon.name` |
| `Controls.ToolButton` | flat by default (`flat`); `icon.name`, `text`, `onClicked` |
| `Controls.ToolBar` | set as `ApplicationWindow.header`; hosts a RowLayout |
| `Controls.Label` | `text`, `horizontalAlignment`, `verticalAlignment`, `wrapMode`, `elide`, `font.bold`, `textFormat` |
| `Controls.CheckBox` | `text`, `checked` (non-exclusive) |
| `Controls.RadioButton` | `text`, `checked` (exclusive **only within the same parent**) |
| `Controls.Switch` | `text`, `checked` |
| `Controls.Slider` | `value`, `to`, `orientation` (`Qt.Vertical`/`Qt.Horizontal`), `stepSize`, `snapMode` |
| `Controls.RangeSlider` | `to`, `first.value`, `second.value`, `stepSize`, `snapMode` |
| `Controls.TextField` | single-line input; `onAccepted` (Enter); label via `Kirigami.FormData.label` |
| `Controls.Page` | base that `Kirigami.Page` inherits; provides `title` |
| `Controls.ProgressBar` | `from`, `to`, `value`, `indeterminate` |
| `Controls.BusyIndicator` | `running` (bool) |
| `Controls.ItemDelegate` | list delegate; `text`, `width: ListView.view.width`, overridable `contentItem` |

`Controls.Slider.SnapAlways` is the `snapMode` value for a tickmarked slider (also
used by `RangeSlider`), paired with `stepSize`.

Styling is delegated to the active QtQuick Controls style (Breeze / `org.kde.desktop`)
and `Kirigami.Theme` — set semantic properties (`text`, `checked`, `value`,
`icon.name`), not pixels. (Note: with the default Breeze theme a toggled Button is
hard to distinguish because pressed buttons turn blue — a different control may be
clearer.)

## 3. Anchors vs Layouts — the positioning split

Two distinct mechanisms; **never mix on the same child**:

- **anchors** glue a single item or a whole Layout to its parent:
  `anchors.fill: parent`, `anchors.centerIn: parent`,
  `anchors.left: parent.left`/`top`/`right`. The brace-block form sets several at
  once: `anchors { left: parent.left; top: parent.top; right: parent.right }`.
- **`Layout.*` attached props** size/align the CHILDREN of a Layout:
  `Layout.fillWidth`, `Layout.fillHeight`, `Layout.alignment`, `Layout.columnSpan`.
  They have no effect on items that aren't direct children of a
  `ColumnLayout`/`RowLayout`/`GridLayout` or `Kirigami.FormLayout`.

```qml
pageStack.initialPage: Kirigami.Page {
    ColumnLayout {
        anchors.fill: parent                  // the Layout is anchored
        Controls.Button {
            Layout.alignment: Qt.AlignCenter  // the child uses Layout.*, never its own anchors
            text: "Beep!"
            onClicked: showPassiveNotification("Boop!")
        }
    }
}
```

Enum families don't mix: `Layout.alignment` takes `Qt.*` (`Qt.AlignCenter`,
`Qt.AlignHCenter`, `Qt.AlignVCenter`); text-internal `horizontalAlignment`/
`verticalAlignment` take `Text.*` (`Text.AlignHCenter`, `Text.AlignRight`,
`Text.AlignTop`, `Text.AlignBottom`). `wrapMode` uses `Text.Wrap`/`Text.WordWrap`;
`elide` uses `Text.elideLeft`.

> The setup/controls/layouts/typography/pages tutorials use only
> `ColumnLayout`/`RowLayout`, `Item`, anchors, and Controls — `GridLayout`,
> `Rectangle`, and `MouseArea` do **not** appear there (GridLayout does appear in the
> model/delegate tutorials — see models-and-views.md). Don't attribute those to the
> layout pages.

## 4. Layouts in practice

### Custom toolbar as the window header (RowLayout)

```qml
header: Controls.ToolBar {
    RowLayout {
        anchors.fill: parent
        Controls.ToolButton {
            icon.name: "application-menu-symbolic"
            onClicked: showPassiveNotification("...")
        }
        Controls.Label {
            text: "Global ToolBar"
            horizontalAlignment: Qt.AlignHCenter     // Qt.* on a Controls.Label here
            verticalAlignment: Qt.AlignVCenter
            Layout.fillWidth: true                   // pushes the ToolButtons to the edges
        }
        Controls.ToolButton { text: "Beep!"; onClicked: showPassiveNotification("...") }
    }
}
```

### Slider that grows + a Label reading it

```qml
ColumnLayout {
    anchors.fill: parent
    Controls.Slider {
        id: normalSlider
        Layout.alignment: Qt.AlignHCenter
        Layout.fillHeight: true                      // a vertical slider grows
        orientation: Qt.Vertical
        value: 60
        to: 100
        // tickmarked variant: snapMode: Controls.Slider.SnapAlways; stepSize: 2.0
    }
    Controls.Label {
        Layout.alignment: Qt.AlignHCenter
        text: Math.round(normalSlider.value)         // binds to the slider by id
    }
}
```

### Toggle button driving another item

```qml
Controls.Button {
    Layout.alignment: Qt.AlignCenter
    text: "Hide inline drawer"
    checkable: true                                  // makes the Button a toggle
    checked: true
    onCheckedChanged: myDrawer.visible = checked     // auto-generated change handler
}
```

### Progress / busy feedback

```qml
Controls.ProgressBar { Layout.fillWidth: true; from: 0; to: 100; value: 42 }   // measurable
Controls.BusyIndicator { id: indicator; anchors.centerIn: parent }             // unmeasurable
// toggle: onTriggered: indicator.running ? indicator.running = false : indicator.running = true
```

## 5. Forms (Kirigami.FormLayout — used like a Layout)

`Kirigami.FormLayout` is a HIG form container (a Kirigami type; full API in the
`kirigami` skill) used exactly like a Layout (`anchors.fill: parent`). Each child
gets the attached `Kirigami.FormData.label`:

```qml
Kirigami.FormLayout {
    anchors.fill: parent
    Controls.TextField { Kirigami.FormData.label: "TextField 1:" }
    Kirigami.Separator {                                   // a line section divider
        Kirigami.FormData.isSection: true
        Kirigami.FormData.label: "New Section!"
    }
    ColumnLayout {                                         // group controls under one label
        Kirigami.FormData.label: "Radio buttons"
        Controls.RadioButton { text: "Radio 1"; checked: true }
        Controls.RadioButton { text: "Radio 2" }
    }
    Item { Kirigami.FormData.isSection: true; Kirigami.FormData.label: "Lineless section" }
}
```

- `Kirigami.FormData.isSection` starts a section whose label becomes the header —
  recommended on `Kirigami.Separator` (line) or `Item` (no line), NOT arbitrary
  controls.
- `Kirigami.FormData.labelAlignment` (`Qt.AlignTop` vs `Qt.AlignVCenter`) positions a
  label against a tall/multi-line child; a ternary on `text.lineCount` top-aligns
  only when wrapped.
- `wideMode`: `true` forces desktop two-column, `false` mobile single-column; omit to
  auto-adapt.

## 6. Loading a page from a separate file

```qml
pageStack.initialPage: Qt.resolvedUrl("StartPage.qml")   // relative → absolute
```

(The new QML file must also be registered in the slice's `src/CMakeLists.txt`.)

## 7. Gotchas

- Import aliases are load-bearing: `Controls.Button`/`Controls.Label`, never bare.
- Don't mix anchors and `Layout.*` on one child; a Layout child must not set its own
  anchors.
- `Layout.*` is inert outside a Layouts container / `Kirigami.FormLayout`.
- `Qt.*` vs `Text.*` alignment enum families are not interchangeable.
- Prefer `Controls.Label` for text and `Kirigami.Heading` (`level: 1`–`5`) for
  titles over a bare QtQuick `Text`.
- RadioButtons are exclusive only within the same parent; CheckBoxes are not
  exclusive.
- `Kirigami.Page` inherits `Controls.Page`, so inherited props like `title` apply —
  always check inherited properties when reading QML API docs.

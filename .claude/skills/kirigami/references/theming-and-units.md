# Kirigami Theming, Units, Typography & Icons

Companion to SKILL.md §5 (and §3/§4). Load when you need exact color roles, spacing
tokens, typography types, or icon-name/size rules. The single overriding rule:
**never hardcode a pixel value (use `Kirigami.Units`) and never hardcode a color
(use `Kirigami.Theme`)** — so the app follows the user's color scheme (Breeze light/
dark) and font/scale settings. This is both a consistency and an accessibility
requirement.

## 1. Kirigami.Theme — Color Roles

`Kirigami.Theme` is an **attached property** available on any QML Item. Primitive
items (`Rectangle`, custom shapes) must take their color from it; standard
Kirigami/QtQuick controls already follow the palette, so you rarely color them.

```qml
import QtQuick
import org.kde.kirigami as Kirigami

Rectangle {
    anchors.centerIn: parent
    implicitWidth: 200; implicitHeight: 100
    color: Kirigami.Theme.highlightColor          // follows the system scheme
}
```

Color roles:

- `Kirigami.Theme.textColor` — foreground/text.
- `Kirigami.Theme.backgroundColor` — background.
- `Kirigami.Theme.highlightColor` / `highlightedTextColor` — selection / highlighted
  items / checked controls (blue by default; also benign/ignorable).
- **Semantic (status) roles** — pair text + background:
  - `positiveTextColor` / `positiveBackgroundColor` — success / confirmation (green);
    this is what `Kirigami.InlineMessage` renders for `type: Kirigami.MessageType.Positive`.
  - `negativeTextColor` / `negativeBackgroundColor` — errors, dangerous actions (red).
  - `neutralTextColor` / `neutralBackgroundColor` — warnings, non-default states (orange).
  - The `highlight*` roles above cover the benign/informational **blue** case — distinct
    from the green `positive*` success roles (the KDE HIG status palette leans on
    Highlight-blue for benign info, but the green positive roles do exist and are correct
    for success states).

HIG: use these semantic roles for status; **never rely on color alone** — also vary
icon, shape, or text (see [hig-guidelines.md](hig-guidelines.md) §4/§6).

## 2. Kirigami.Theme — Color Sets

`Kirigami.Theme.colorSet` selects which palette an item and its descendants use. The
same role (e.g. `backgroundColor`) resolves to a different actual color per set.

Sets: `View`, `Window` (default), `Button`, `Selection`, `Tooltip`,
`Complementary` (dark even in light themes — for emphasis in small areas).

Children inherit the parent's set **recursively** unless you break it with
`Kirigami.Theme.inherit: false`.

```qml
Rectangle {
    color: Kirigami.Theme.backgroundColor               // Window set => gray
    Rectangle {
        Kirigami.Theme.colorSet: Kirigami.Theme.View
        Kirigami.Theme.inherit: false                   // stop inheriting Window
        color: Kirigami.Theme.backgroundColor           // View => near-white (light theme)
        Rectangle {
            color: Kirigami.Theme.backgroundColor       // inherits View => near-white
        }
    }
}
```

**Custom palette (last resort):** if custom colors are genuinely required, reassign
ALL the roles on ONE ancestor with `inherit: false`, so the whole subtree draws from
a single source — replace every role (not just one) to avoid bad contrast:

```qml
Rectangle {
    anchors.fill: parent
    Kirigami.Theme.inherit: false
    Kirigami.Theme.colorSet: Kirigami.Theme.Window
    Kirigami.Theme.backgroundColor: "#b9d795"
    Kirigami.Theme.textColor: "#465c2b"
    Kirigami.Theme.highlightColor: "#89e51c"
    color: Kirigami.Theme.backgroundColor
}
```

## 3. Kirigami.Units — Spacing, Sizing, Durations

Use these everywhere a size/spacing/duration is needed.

**Spacing** (HIG grouping rules in [hig-guidelines.md](hig-guidelines.md) §2):

- `Kirigami.Units.smallSpacing` — directly related items / shared group; group→content.
- `Kirigami.Units.mediumSpacing` — items in a toolbar.
- `Kirigami.Units.largeSpacing` — between groups of controls; window edge→other UI.
- title↔subtitle = 0; window edge→"frameless" view = 0.

**Sizing:**

- `Kirigami.Units.gridUnit` — base unit (18px); fixed sizes and min/default window
  size are `gridUnit * N` (e.g. `preferredWidth: Kirigami.Units.gridUnit * 20`).
- `Kirigami.Units.cornerRadius` — corner radius.
- `Kirigami.Units.iconSizes.*` — `small` (menu items, raised buttons), `smallMedium`
  (flat/toolbar buttons, subtitle-less lists), `medium` (lists with subtitles),
  `huge` (`Layout.maximumHeight: Kirigami.Units.iconSizes.huge`).

**Durations** (animations):

- `veryShortDuration`, `shortDuration`, `longDuration`, `veryLongDuration`.

```qml
Rectangle {
    Layout.margins: Kirigami.Units.largeSpacing
    implicitWidth: Kirigami.Units.iconSizes.medium
    radius: Kirigami.Units.cornerRadius
    Behavior on opacity {
        NumberAnimation { duration: Kirigami.Units.shortDuration }
    }
}
```

The only literal px in KDE guidance is `gridUnit == 18px`, and even that is always
expressed as `gridUnit * N`.

## 4. Typography

- **`Kirigami.Heading`** — titles/section headers. `level` 1 (largest) to 5
  (smallest). Subclass of `Text`, so it shares `horizontalAlignment` /
  `verticalAlignment` / `wrapMode`.
- **`Controls.Label`** (QtQuick.Controls, imported `as Controls`) — normal body
  text; supports `text`, `wrapMode`, `textFormat` (renders rich/HTML markup),
  `font.bold`.
- **Never use `QtQuick.Text` directly** — it ignores the system font settings.
- The only theme font-size API is `Kirigami.Theme.defaultFont.pointSize`.

```qml
Kirigami.Heading {
    Layout.fillWidth: true
    horizontalAlignment: Text.AlignHCenter
    wrapMode: Text.Wrap
    level: 1
    text: i18n("Welcome to my application")
}
Controls.Label {
    text: "<p><strong>List</strong></p><ul><li>Apple</li><li><del>Banana</del></li></ul>"
    // textFormat governs how the HTML-like markup renders
}
```

HIG wording/capitalization rules for the text itself are in
[hig-guidelines.md](hig-guidelines.md) §5.

## 5. Icons

Set themed icons by **name** (FreeDesktop/Breeze) via the grouped `icon.name`
property — never bundle pixmaps or set a file path.

```qml
Controls.Button {
    text: i18n("Delete")            // keep text even for icons-only (screen readers)
    icon.name: "edit-delete"         // red trash from the system theme
}

Controls.ToolButton {
    text: i18n("Add")
    icon.name: "list-add"
    display: Controls.AbstractButton.IconOnly   // hide visible text
    // add a manual Controls.ToolTip for mouse/touch users
}

// Request a monochrome variant at small sizes:
icon.name: "edit-delete-symbolic"
```

Rules (full detail in [hig-guidelines.md](hig-guidelines.md) §7):

- **Style follows render size:** 16px symbolic; 22px almost always symbolic; 32px+
  full-color. `-symbolic` suffix requests monochrome.
- Deletion: `edit-delete` (red trash) destructive; `edit-delete-remove` (red X)
  restorable removal; `trash-empty` (black) non-destructive move-to-trash.
- Use `Kirigami.Units.iconSizes.*` wherever the size isn't chosen automatically.
- C++: `KIconThemes` build dep, `KIconTheme::initTheme()` before `QApplication`,
  `KStandardActions` for standard-action icons. `Kirigami.Icon { source: "user" }`
  renders a standalone themed icon.
- Browse names with Icon Explorer (plasma-sdk). FreeDesktop names also used in
  `GlobalDrawer.titleIcon` and `Kirigami.Action.icon.name`.

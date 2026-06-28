---
name: kirigami
description: >
  Building convergent KDE applications with the Kirigami framework (QtQuick
  Controls 2 + org.kde.kirigami), governed by the KDE Human Interface Guidelines
  (HIG). Covers the app skeleton (Kirigami.ApplicationWindow + pageStack), pages
  and navigation (Page/ScrollablePage/PageRow, GlobalDrawer/ContextDrawer),
  Actions (Kirigami.Action + ActionToolBar), the component catalog (Card, Chip,
  FormLayout, InlineMessage, Dialog/OverlaySheet, list delegates,
  PlaceholderMessage, Heading), theming and units (Kirigami.Units,
  Kirigami.Theme — never hardcode px/colors), and kirigamiaddons FormCard/AboutPage.
  HIG design principles are first-class throughout. Auto-loads when writing or
  reviewing .qml files, Kirigami/KDE UI code, or KDE app architecture.
  Keywords: Kirigami, KDE, QML, QtQuick, HIG, ApplicationWindow, pageStack, Page,
  ScrollablePage, GlobalDrawer, ContextDrawer, Kirigami.Action, ActionToolBar,
  FormLayout, FormCard, InlineMessage, Dialog, OverlaySheet, Kirigami.Units,
  Kirigami.Theme, Breeze, convergent, kirigamiaddons, AboutPage, Plasma.
user-invocable: false
metadata:
  type: reference
---

# Kirigami + KDE Human Interface Guidelines

## Role

Background knowledge for building and reviewing **convergent** KDE applications —
one QML codebase that adapts from desktop (mouse/keyboard) to mobile (touch), TV,
and embedded. Kirigami is KDE's set of QtQuick Controls 2 components
(`org.kde.kirigami`); the **KDE Human Interface Guidelines (HIG)** are the design
law that governs *how* those components are used. This skill weaves the HIG into
every component recommendation — they are inseparable.

Scope: Kirigami components, kirigamiaddons, and KDE HIG only. **QML/QtQuick
language fundamentals — property bindings, signal handlers, `id`, anchors,
Layouts, `Component`, models/delegates, JavaScript expressions — live in the
sibling `qtquick2` skill. Assume that knowledge; this skill does not re-teach the
language.** Anything about how a binding evaluates or how a `ListView` model works
belongs to `qtquick2`; anything about *which* KDE component to pick and how the
HIG constrains it belongs here.

## When This Skill Activates

- Writing or modifying `.qml` files that import `org.kde.kirigami` or `org.kde.kirigamiaddons.*`
- Reviewing KDE/Plasma application UI code
- Choosing a navigation pattern, component, dialog type, or settings layout for a KDE app
- Wiring the C++/Python/Rust entrypoint of a Kirigami app
- Any question about KDE HIG rules: labels, capitalization, icons, accessibility, status feedback

---

## Design Principles (KDE HIG)

The HIG is first-class. Apply these before reaching for any component. Full
deep-dive: [references/hig-guidelines.md](references/hig-guidelines.md).

**Central principle — memorize verbatim: "Simple by default, powerful when
needed."** Target users span basic-knowledge users to experts. Make the 80%
common case simple and obvious; expose power features without overwhelming
novices.

- **Simple by default.** Welcoming empty states (`Kirigami.PlaceholderMessage`
  with `helpfulAction`), sensible defaults, no first-run wizard for simple/medium
  apps. Use **progressive disclosure** (push a sub-page / collapsed view) instead
  of a page literally named "Advanced".
- **Powerful when needed.** Customization exists to support diverse *workflows*,
  not aesthetics; settings that merely enable/disable a feature are "warning signs
  of sloppy design" — prefer settings that switch between multiple valid
  behaviors. Accelerators (shortcuts, gestures, hover controls) must NEVER be the
  only way to reach functionality.
- **Layout & navigation.** Minimize navigation. Pick the pattern by structure:
  linear workflow → `pageStack` + breadcrumbs; ≤5 non-linear destinations →
  `Kirigami.NavigationTabBar`; >5 → `Kirigami.GlobalDrawer`. The launch view is
  always the first navigation item. Reading order conveys importance
  (top-leading = first); the one mobile exception is a bottom toolbar for thumb reach.
- **Input.** Map the situation to the right control: instant-apply →
  `Controls.Switch`; explicit-apply (OK/Apply) → `Controls.CheckBox`; ≤3 obvious
  options → `Controls.RadioButton`; ≤10 → `Controls.ComboBox`; build settings with
  `Kirigami.FormLayout`. Dialogs interrupt — use only for a decision that blocks
  the app.
- **Status feedback.** Foregrounded app → `showPassiveNotification` (ignorable) or
  `Kirigami.InlineMessage` (needs attention, doesn't interrupt); backgrounded →
  `KNotification` with an urgency. Every error message must be **actionable**.
  Never rely on color alone.
- **Text & labels.** Imperative-mood, action-verb labels ("Show Info", not
  "Info"). **Sentence case** for labels in front of controls / checkbox / radio /
  combobox items / subtitles / tooltips / placeholders; **Title Case** otherwise.
  Real "…" (U+2026) only when the action always needs more input. Wrap user-facing
  strings in `i18n()`/`i18nc()`.
- **Accessibility.** Keyboard-only nav with visible focus, screen-reader labels via
  `Accessible.name`, adapt to color scheme + large fonts, never convey meaning by
  color or audio alone. Test RTL with `LANGUAGE=ar_AR`.
- **Icons.** Always themed by `icon.name` (FreeDesktop/Breeze names, e.g.
  `"list-add-symbolic"`) — never bundle pixmaps. Style follows render size: 16/22px
  symbolic, 32px+ full-color. `edit-delete` (red trash) for destructive deletes;
  `trash-empty` (black) for non-destructive move-to-trash.

---

## 1. App Skeleton: ApplicationWindow + pageStack

Every Kirigami app's QML root is `Kirigami.ApplicationWindow`, which owns a
`pageStack`. Seed the first page declaratively with `pageStack.initialPage`.
Imports are **unversioned** (Qt6) and namespaced with `as`.

```qml
import QtQuick
import QtQuick.Layouts
import QtQuick.Controls as Controls
import org.kde.kirigami as Kirigami

Kirigami.ApplicationWindow {
    id: root
    width: 400
    height: 300
    title: i18nc("@title:window", "Hello World")

    // First page loaded when the app opens; can also be an id of a Kirigami.Page
    pageStack.initialPage: Kirigami.Page {
        Controls.Label {
            anchors.centerIn: parent
            text: i18n("Hello World!")
        }
    }
}
```

Rules:
- Root is **always** `Kirigami.ApplicationWindow` — never a plain `Window`. It
  provides `pageStack`, `globalDrawer`, `contextDrawer`, and `header`.
- Import `QtQuick.Controls as Controls` and `org.kde.kirigami as Kirigami` (KDE
  convention — never bare). `Main.qml` must start with an uppercase letter.
- The frontend QML is identical across C++/Python/Rust; only entrypoint glue
  differs. Modern QML load is `engine.loadFromModule("org.kde.tutorial", "Main")`
  (the URI matches `ecm_add_qml_module`). Force the KDE style with
  `org.kde.desktop`, guarded by the `QT_QUICK_CONTROLS_STYLE` env var.
- C++ uses `QApplication` (not `QGuiApplication`) to force the Breeze QStyle, calls
  `KIconTheme::initTheme()` **before** constructing it, and installs
  `KLocalizedContext` for `i18n` in QML.

Entrypoint glue (C++/Python/Rust), CMake/ECM, and the `.desktop` file are in
[references/components-catalog.md](references/components-catalog.md) §App Skeleton.

## 2. Pages & Navigation

Content lives in pages arranged in a **column-based page row**. On a phone only
the top page shows; on desktop multiple columns show side-by-side.

- **`Kirigami.Page`** — a screen with a fixed vertical size (inherits
  `Controls.Page`, so `title` etc. are inherited).
- **`Kirigami.ScrollablePage`** — use when content extends vertically or holds a
  `ListView`; it has a built-in scrollbar. **Never** nest a `Controls.ScrollView`
  inside it (children are already in one).
- **`Kirigami.PageRow`** — `ApplicationWindow.pageStack` *is* a global PageRow;
  prefer it over a hand-rolled one.

Pages are added only two ways: `initialPage` (a page, an id, `Qt.resolvedUrl(...)`,
a component, or an **array** of pages to seed columns) and `push()`. Remove with
`pop()`; move with `goBack()`/`goForward()`.

```qml
Kirigami.ApplicationWindow {
    pageStack.initialPage: Kirigami.Page {
        Controls.Button { text: "Push!"; onClicked: pageStack.push(secondPage) }
    }
    Component {
        id: secondPage
        Kirigami.Page { Controls.Button { text: "Pop!"; onClicked: pageStack.pop() } }
    }
}
```

From a component in another QML file, reach the single global stack with
`applicationWindow().pageStack.push(...)` — never create a second stack.

**Drawers** (window-level, set on the `ApplicationWindow`):

- **`Kirigami.GlobalDrawer`** (`globalDrawer:`) — app-wide main menu; opens from
  the left edge (LTR). `actions` is an array of `Kirigami.Action`. `isMenu: true`
  makes it a compact desktop menu (headers/banners hidden in menu mode). `header`
  places a sticky component (e.g. `Kirigami.SearchField`).
- **`Kirigami.ContextDrawer`** (`contextDrawer:`) — per-page actions; pulls them
  from the current page's `actions`. On desktop with space they appear in the
  toolbar; in narrow windows behind a right-side hamburger.
- **`Kirigami.OverlayDrawer`** — the component behind both modal/inline edge
  drawers: `edge` (`Qt.TopEdge`/`RightEdge`/`BottomEdge`/`LeftEdge`), `modal`
  (true = darken + dismiss; false = inline), `contentItem`; open/close via
  `.open()`/`.close()`.

```qml
Kirigami.ApplicationWindow {
    globalDrawer: Kirigami.GlobalDrawer {
        title: "Global Drawer"
        titleIcon: "applications-graphics"
        actions: [
            Kirigami.Action {
                text: i18n("Quit")
                icon.name: "application-exit-symbolic"
                shortcut: StandardKey.Quit
                onTriggered: Qt.quit()
            }
        ]
    }
    contextDrawer: Kirigami.ContextDrawer {}
}
```

**HIG navigation choice (repeat):** linear → `pageStack` + breadcrumbs; ≤5 →
`Kirigami.NavigationTabBar`; >5 → `GlobalDrawer`. Pin the GlobalDrawer open on
desktop with `modal: false`. Full pattern/responsive rules:
[references/hig-guidelines.md](references/hig-guidelines.md) §Layout & Navigation.

Pull-to-refresh: `ScrollablePage { supportsRefreshing: true }`; reset `refreshing`
to `false` yourself when the async refresh completes. Filter a list by overriding
`titleDelegate` with a `Kirigami.SearchField`.

## 3. Actions: Kirigami.Action and Where They Attach

`Kirigami.Action` inherits `QtQuick.Controls.Action`, so `text`, `icon`,
`shortcut`, and `triggered` come for free; Kirigami **adds** nested child actions
and the `displayHint`/`displayComponent` hint system. Actions are **contextual** —
the same array renders differently per host.

```qml
Kirigami.Action {
    id: addAction
    icon.name: "list-add-symbolic"
    text: i18nc("@action:button", "Add kountdown")
    shortcut: StandardKey.New
    onTriggered: kountdownModel.append({ name: "...", date: 1000 })
}
```

Attachment points (all take an `actions:` array of `Kirigami.Action`):

| Host | Rendering |
|---|---|
| `Kirigami.Page` / `ScrollablePage` | right of header (desktop) / footer (mobile) |
| `Kirigami.GlobalDrawer` | sidebar or menu (`isMenu`) |
| `Kirigami.ContextDrawer` | three-dots overflow |
| `Kirigami.ActionToolBar` | `ToolButton`s, overflow into a menu on resize |
| `Kirigami.Card` | buttons + hamburger at card bottom |
| `Kirigami.ActionTextField` | `rightActions` (note: not `actions`) |

**Nested actions** — declare children inline for submenus / nested navigation:

```qml
Kirigami.Action {
    text: "View"; icon.name: "view-list-icons"
    Kirigami.Action { text: "action 1" }
    Kirigami.Action { text: "action 2" }
}
```

**`Kirigami.ActionToolBar`** lays out an `actions` array, overflowing what doesn't
fit into a menu; set `alignment` (`Qt.AlignLeft`/`Center`/`Right`). An action can
render as a custom control via `displayComponent`, and ask to stay visible with
`displayHint: Kirigami.DisplayHints.KeepVisible` (property singular `displayHint`,
enum plural `DisplayHints`).

**HIG:** `icon.name` is a themed Breeze/FreeDesktop name; label text is
imperative + sentence/title case per the rules above. Don't put Quit/Minimize in a
hamburger menu. Full menu strategy by app size: [references/hig-guidelines.md](references/hig-guidelines.md).

## 4. Component Catalog (quick reference)

Pick the component, then apply the HIG rule. Full snippets for every one:
[references/components-catalog.md](references/components-catalog.md).

- **Cards** — `Kirigami.AbstractCard` (`header`/`contentItem`/`footer`),
  `Kirigami.Card` (adds `banner` group + `actions`). Layout sets with
  `Kirigami.CardsLayout` (inside a `ColumnLayout`) or `Kirigami.CardsListView`. In
  a `CardsListView` delegate **never** put a Layout as `contentItem` (binding
  loops) — wrap in a plain `Item`.
- **`Kirigami.Chip`** — small `AbstractButton`; `text`, `onClicked`, `onRemoved`.
- **`Kirigami.FormLayout`** — two-column label/field form for **settings**
  (HIG-mandated for config pages). Per-field label via attached
  `Kirigami.FormData.label`; section header via `FormData.isSection: true` on a
  `Kirigami.Separator`; `FormData.labelAlignment` for multi-line fields.
- **`Kirigami.InlineMessage`** — non-interrupting banner. `visible` defaults to
  **false**; `type` is `Kirigami.MessageType.Information`/`Positive`/`Warning`/`Error`;
  `actions`, `showCloseButton`. Use for invalid input (and disable confirm).
- **Dialogs** — `Kirigami.Dialog` (general, incl. input; `standardButtons`,
  `customFooterActions`, `standardButton(...)`), `Kirigami.PromptDialog`
  (`subtitle` for yes/no; a child component replaces the subtitle for input),
  `Kirigami.MenuDialog` (choose among `actions`), `Kirigami.OverlaySheet`
  (read-only narrow scrollable; `header`/`footer` slots). Never show two dialogs at
  once or open a dialog from a dialog.
- **List delegates** — prefer Qt `Controls.ItemDelegate`/`CheckDelegate`/
  `RadioDelegate`/`SwitchDelegate`; Kirigami `org.kde.kirigami.delegates`
  (`SubtitleDelegate`, `CheckSubtitleDelegate`, `TitleSubtitle`,
  `IconTitleSubtitle`) add subtitle + icon. Delegates set
  `width: ListView.view.width` — never `anchors.fill: parent`, no bottom anchor.
- **`Kirigami.PlaceholderMessage`** — empty-state UX; `text`, `visible`
  (bind to `count === 0`), `helpfulAction`. HIG: be welcoming on first launch.
- **`Kirigami.Heading`** — titles; `level` 1 (largest) to 5. Body text is
  `Controls.Label` — never `QtQuick.Text` (ignores system font).
- **Progress** — `Controls.ProgressBar` (`from`/`to`/`value`/`indeterminate`) and
  `Controls.BusyIndicator` (`running`) are **QtQuick.Controls**, not Kirigami.
  `Kirigami.LoadingPlaceholder` for determinate-or-varying progress. Show a
  progress indicator for any task longer than a second.

## 5. Theming & Units — Never Hardcode px or Colors

Pull every color from `Kirigami.Theme` and every size/spacing/duration from
`Kirigami.Units`. This is both an HIG consistency rule and an accessibility
requirement (apps must follow the user's color scheme + dark mode). Full reference:
[references/theming-and-units.md](references/theming-and-units.md).

```qml
Rectangle {
    color: Kirigami.Theme.backgroundColor            // follows the active scheme
    Layout.margins: Kirigami.Units.largeSpacing       // not a magic number
    implicitWidth: Kirigami.Units.gridUnit * 20
    Behavior on opacity { NumberAnimation { duration: Kirigami.Units.shortDuration } }
}
```

- **`Kirigami.Theme`** is an attached property on any Item. Color roles:
  `textColor`, `backgroundColor`, `highlightColor`, plus semantic
  `positiveTextColor`/`neutralTextColor`/`negativeTextColor` (+ matching
  `*BackgroundColor`). Color sets via `Kirigami.Theme.colorSet`
  (`View`/`Window`/`Button`/`Selection`/`Tooltip`/`Complementary`, default
  `Window`); children inherit a set unless `Kirigami.Theme.inherit: false`.
- **`Kirigami.Units`** — `smallSpacing`/`mediumSpacing`/`largeSpacing`,
  `gridUnit` (18px) for fixed sizes, `iconSizes.*`, `cornerRadius`, and
  `veryShortDuration`/`shortDuration`/`longDuration`/`veryLongDuration`.
- **Never** hardcode a hex color (`#32b2fa`) or a pixel value. If a custom palette
  is truly required, reassign all `Kirigami.Theme.*` roles on one ancestor with
  `inherit: false`.

## 6. Settings Pages — kirigamiaddons FormCard

Kirigami Addons (`org.kde.kirigamiaddons.formcard`) is a **separate** module; you
import both it and core Kirigami. FormCard is the HIG-blessed way to build settings.
Full catalog: [references/components-catalog.md](references/components-catalog.md) §FormCard.

```qml
import org.kde.kirigami as Kirigami
import org.kde.kirigamiaddons.formcard as FormCard

FormCard.FormCardPage {                 // inherits ScrollablePage; has its own layout
    FormCard.FormHeader { title: i18n("General") }
    FormCard.FormCard {                 // no Layout props/anchors inside — auto-layout by order
        FormCard.FormSwitchDelegate { id: autosave; text: i18n("Enabled") }
        FormCard.FormRadioDelegate {
            text: i18n("After every change")
            visible: autosave.checked   // declarative gating, not imperative
        }
    }
}
```

- **`FormCard.FormCardPage`** has an internal layout — add headers/cards directly.
  A plain `Kirigami.ScrollablePage` needs a `ColumnLayout` wrapping each `FormCard`.
- Delegates: `FormButtonDelegate` (push pages via
  `pageStack.layers.push(component)`; has `leading` only), `FormTextDelegate`
  (`leading`+`trailing`, `description`), `FormSwitchDelegate`/`FormRadioDelegate`/
  `FormCheckDelegate` (inherit `AbstractButton`), `FormComboBoxDelegate`
  (`displayMode` = `.ComboBox`/`.Dialog`/`.Page`), `FormSectionText`,
  `FormDelegateSeparator` (`above`/`below` auto-hide).
- **AboutPages — two non-interchangeable types:** addon `FormCard.AboutPage {}`
  (auto-reads `KAboutData::setApplicationData`) and `FormCard.AboutKDE {}`
  (zero-config) vs **core** `Kirigami.AboutPage { aboutData: About }` (needs the
  property). Pick the right one.

## Anti-Pattern Review Checklist

Scan Kirigami/QML for these (all detailed above):

hardcoded px instead of `Kirigami.Units` · hardcoded hex/named colors instead of
`Kirigami.Theme` · plain `Window`/`Controls.ApplicationWindow` root instead of
`Kirigami.ApplicationWindow` · bare imports (not `as Kirigami`/`as Controls`) ·
versioned Qt6 imports · `Controls.ScrollView` nested in a `ScrollablePage` ·
`Kirigami.Page` where content scrolls (use `ScrollablePage`) · hand-rolled second
`PageRow` instead of `applicationWindow().pageStack` · `QtQuick.Text` instead of
`Controls.Label` · Layout as `contentItem` in a `CardsListView` delegate
(binding loop) · `anchors.fill: parent` / bottom anchor on a list delegate
(use `width: ListView.view.width`) · `ActionTextField` `actions` instead of
`rightActions` · page literally named "Advanced" (use progressive disclosure) ·
settings that only enable/disable a feature · functionality reachable only via an
accelerator · two dialogs at once / dialog opened from a dialog · custom file UI
instead of `FileDialog` · `Kirigami.OverlaySheet` used for input · color as the
sole carrier of meaning · red icon for non-destructive move-to-trash (use
`trash-empty`) · bundled pixmaps instead of themed `icon.name` · Title Case on a
control-label / checkbox / combobox item (use sentence case) · non-imperative
button labels ("Info" not "Show Info") · unwrapped user-facing strings (no
`i18n`/`i18nc`) · icons-only button with no `text` for screen readers · important
text hidden in a hover tooltip · using addon `FormCard.AboutPage` and core
`Kirigami.AboutPage` interchangeably · Layout props/anchors inside a `FormCard`.

## Additional Resources

- [references/components-catalog.md](references/components-catalog.md) — every
  component (app skeleton + entrypoints, pages/drawers, actions/toolbar, cards,
  chips, FormLayout, InlineMessage, dialogs/OverlaySheet, list delegates,
  PlaceholderMessage, progress, FormCard/AboutPage) with a copy-paste snippet.
- [references/hig-guidelines.md](references/hig-guidelines.md) — the KDE HIG
  organized: design philosophy, layout/navigation/content, input controls, status
  feedback, text/label wording + capitalization, accessibility, and the Breeze
  icon system.
- [references/theming-and-units.md](references/theming-and-units.md) —
  `Kirigami.Theme` color roles + color sets, `Kirigami.Units` spacing/sizing/
  durations, typography (`Heading`/`Label`), and the icon-name/size rules.

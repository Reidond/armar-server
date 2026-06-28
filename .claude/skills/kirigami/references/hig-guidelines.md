# KDE Human Interface Guidelines — Deep Dive

Companion to SKILL.md "Design Principles (KDE HIG)" and §2/§3/§4. Load when making
a design decision: choosing a navigation/content pattern, an input control, a
feedback mechanism, wording, or applying accessibility/icon rules. Source:
develop.kde.org/hig. The HIG is "not an ironclad law code" — learn the rules to
know when breaking one yields a better result.

## 1. Design Philosophy — "Simple by Default, Powerful When Needed"

Central principle, verbatim: **"Simple by default, powerful when needed."** Target
users span people with basic technical knowledge up to experts and professionals.

- **Don't be afraid to pick your users.** The best apps know which users/use cases
  they target and which they leave to others. Make the 80% common case simple and
  obvious; under-promise and over-deliver.
- **Be welcoming, not demanding or baffling.** Empty views show something
  actionable on first launch: `Kirigami.PlaceholderMessage` with an icon,
  explanation text, and ideally a `helpfulAction` button.
- **Show the most important UI elements.** Condense related buttons into menus,
  group features onto pages, use `Page.actions` + Context Drawers (Kirigami) or
  `KHamburgerMenu` (QtWidgets) to cut visual complexity without cutting function.
- **Customization increases reach — for workflows, not looks.** Aesthetic
  customization is secondary and must not impair the default UX; defer to the
  platform's theming. Settings that merely enable/disable a feature are "warning
  signs of sloppy design" — prefer settings that switch between multiple valid
  behaviors. Apply newly-saved settings immediately (no relaunch). Don't override
  platform settings (one exception: a setting Plasma has that the current
  non-Plasma platform lacks).
- **Progressive disclosure beats "Advanced".** A page named "Advanced"
  communicates nothing about its contents and the basic/advanced line depends on
  the user. Show simplified data first; push details to a sub-page / separate
  window / collapsed view.
- **Maximize safety.** Offer undo for anything that removes not-trivially-re-addable
  content; defer the real delete until undo is dismissed; move files to trash, not
  immediate delete. Non-catastrophic undo → `showPassiveNotification` (auto-
  disappears); destructive (deleting files) → `Kirigami.InlineMessage` (persists).
- **Be fast.** "Make your app lightning fast or new users will lose interest."
  Show a progress indicator for any task longer than a second
  (`Kirigami.LoadingPlaceholder` determinate; `Controls.BusyIndicator`
  indeterminate). Remember window size/position and view state for project/file
  apps; for one-off utilities show a `KRecentDocument` list instead.
- **Be consistent.** Avoid custom styling, minimize custom components; pull colors
  from `Kirigami.Theme`, sizes/spacing/durations from `Kirigami.Units`. Never
  hardcode px.

First-run wizards only in a *complex* app, and only for mandatory setup or as a
skippable teaching tool — never to ask preferences, never in a simple/medium app.
Don't keep running as a System Tray icon when closed.

KDE recommends **QtQuick + Kirigami** for new apps; QtWidgets is for traditional
complex desktop apps (e.g. KDevelop). Every KDE app = Qt + KDE Frameworks + exactly
one GUI toolkit.

## 2. Layout, Navigation & Displaying Content

**Navigation decision ladder** (minimize navigation first — "the best navigational
flow is nonexistent"):

- Linear / step-by-step workflow → `pageStack` (PageStack) + breadcrumbs + toolbar
  back/forward.
- Non-linear, ≤5 destinations → `Kirigami.NavigationTabBar`.
- Non-linear, >5 destinations → `Kirigami.GlobalDrawer`.
- **Always** make the launch view the FIRST navigation item.

Convergent sidebar: `Kirigami.GlobalDrawer { modal: false }` pins it open on
desktop and collapses to pull-on-demand when narrow. `Kirigami.ContextDrawer`
mirrors this for per-page actions.

**Responsive placement (desktop → mobile/narrow):**

| Element | Desktop | Mobile |
|---|---|---|
| Toolbar | above content | below content |
| Sidebar | leading | on-demand / first page in stack |
| Contextual toolview | trailing | on-demand trailing |
| Menubar | above toolbar | hamburger button on toolbar |
| Navigation tab bar | above content | below content |
| Status bar | below content | omitted |

Detect with `Kirigami.Settings.isMobile` / `Kirigami.Settings.tabletMode`; phones
need a purpose-built UI, not a scaled-down desktop. Test with
`QT_QUICK_CONTROLS_MOBILE=1`.

**Spacing (never hardcode px — `Kirigami.Units`):** title↔subtitle = 0; group→
content below = `smallSpacing`; between groups = `largeSpacing`; toolbar items =
`mediumSpacing`; window edge→"frameless" view = 0; window edge→other UI =
`largeSpacing`; fixed/min sizes = `gridUnit` (18px) × N. Icon sizes:
`IconSizes.small` (menu items, raised buttons), `smallMedium` (flat/toolbar,
subtitle-less lists), `medium` (lists with subtitles).

**Content containers:**

- `ListView` — mostly-textual, long text, fast scanning; alternating background via
  `Kirigami.Theme` when items have subtitles/right-side extras.
- `GridView` — mostly-visual, wide views, large items, scrolling undesirable.
- `TableView` — items with 3+ comparable data pieces (one column each); a 2-column
  or sort-meaningless table should be a list.
- `TreeView` — minimize; only for technical apps over inherently tree-shaped data.
  Prefer a list with collapsible sections.

Add-content controls → `Kirigami.Actions` on a `Kirigami.InlineViewHeader`;
remove controls → inline on the item, always visible (not hover-only); selected
item → bold text. Build items from standard Qt delegates (inherit KDE styling),
then Kirigami delegates, last resort override `ItemDelegate.contentItem`.

**On-demand content:** fills the view → push a `Page`; read-only narrow scrollable
→ `Kirigami.OverlaySheet` (NOT for input, NOT if never tall enough to scroll);
everything else incl. input → `Kirigami.Dialog`. Add a **contrasting outline**
around any overlay or it blends into dark schemes.

**Tabs:** mutable (documents) → `Controls.TabBar` (above content, reorderable,
visible close buttons); immutable (settings groups) → `Kirigami.NavigationTabBar`
(above or below). Both: hide the bar when one tab; add `KStandardShortcut`
switching. Tabs don't scale past 4–5 desktop / ~2 mobile — use a sidebar.

**Menus by size:** small/focused → often none; small-medium → hamburger
(`application-menu` icon, ~15 items max, irrelevant items disabled not hidden);
>15 / large → a real menubar showing all actions. Never put Quit/Minimize in a
hamburger.

**Inline help escalation:** brief+important → inline below the control; ≤2
sentences for a page → inline at top; no room → tooltip (never put important text
here — broken on touch); >1 sentence / must read → `Kirigami.ContextualHelpButton`.

**RTL:** `RowLayout`/`ColumnLayout`/anchors mirror automatically, but verify text
alignment, manually reverse custom directional widgets, use `-rtl`-suffixed icon
variants for directional icons, don't mirror images. Test: `LANGUAGE=ar_AR <app>`.

## 3. Input Controls

Map the situation to the control:

| Situation | Control |
|---|---|
| Two-state, both obvious, **instant apply** | `Controls.Switch` |
| Two-state, both obvious, **explicit apply** (OK/Apply) | `Controls.CheckBox` |
| Mutually-exclusive, opposite not obvious, ≤3 short, room | `Controls.RadioButton` |
| Mutually-exclusive labeled, ≤10 or tight space | `Controls.ComboBox` |
| >10 options | scrollable list view |
| Bounded, speed over precision | `Controls.Slider` |
| Bounded, precision over speed | `Controls.SpinBox` (trail a Slider when both matter) |
| Initiate an action | `Controls.Button` / `ToolButton` (toolbar) / `RoundButton` (floating) |

- Never change a Switch/CheckBox label or icon when state changes. **Avoid
  `checkable: true` buttons** — checkability isn't obvious.
- Free `TextField` only when no validating control fits — then YOU validate: show
  `Kirigami.InlineMessage` AND disable confirm/send. Prefer pre-made
  `Kirigami.ActionTextField` / `SearchField` / `PasswordField`.
- Dialogs interrupt — use only when the user must decide before the app continues,
  or to show blocking progress. `Kirigami.PromptDialog` for do-it/don't-it (embed a
  `TextField` for input); `Kirigami.MenuDialog` to pick an action. Files →
  `QtQuick.Dialogs.FileDialog` with `fileMode`, never a custom file UI. Never two
  dialogs at once; never a dialog from a dialog.

## 4. Status-Change Feedback

- **Foregrounded app:** ignorable → `showPassiveNotification`; needs attention,
  don't interrupt → `Kirigami.InlineMessage` (set
  `position: Kirigami.InlineMessage.Position.Header` for page/app-wide scope).
  Avoid system notifications while the window is foregrounded.
- **Backgrounded app:** `KNotification` with `setUrgency` (Low/Normal/Critical;
  Critical stays until dismissed) and `setFlags(Persistent)` for must-not-miss.
  Never use notifications to advertise/self-promote.
- **Error messages** preference order (best→worst): no message (auto-recover) >
  description + "Fix it" action > description + how to proceed > description only
  (avoid) > technical gibberish (never) > silent failure (never). Every error must
  be actionable, plain-language, and attribute third-party/web failures as such.
- Signal success by changing something on screen, not a "Task completed" message
  (exception: long tasks the user may have forgotten).
- **Color** via `Kirigami.Theme` semantic roles: `negative*` (red, errors/danger),
  `neutral*` (orange, warnings/non-default state), `highlight*` (blue,
  benign/selected). **Never rely on color alone** — also vary icon/shape/text.
  Task Manager badges (`QGuiApplication::setBadgeNumber()`) only for user-initiated
  jobs with actionable counts. OSDs are Plasma-only — never from a windowed app.

## 5. Text & Labels

- **Imperative mood, action verb:** "Apply" not "Yes"; "Show Info" not "Info";
  "Raise Maximum Volume" not "Maximum Volume Raising". Front-load important words.
  Anything longer than "Configure Keyboard Shortcuts" is too long for an
  interactive control.
- **Positive phrasing:** describe what enabling does ("Allow the system to go to
  sleep"), not what disabling prevents.
- **Capitalization — SENTENCE case** when the text ends with a period/colon, is a
  sentence, is a subtitle/tooltip/transient status/placeholder, or labels a radio /
  checkbox / combobox item or sits in front of a control
  (`Kirigami.FormData.label`). **Title Case** otherwise (and for proper nouns like
  "the Internet", "Plasma Widgets").
- **Impersonal** for longer text — avoid "you" ("Missing authorization to access
  the file." not "You are not authorized…").
- **Plain language**, minimize jargon ("folder" over "directory"); reserve
  "Delete" for actions that remove files on disk. Avoid acronyms (PC→System,
  OS→Operating system, URL→Link, RAM→Memory) except acronym-only terms (USB).
- **Ellipsis** "…" (real U+2026, not "...") only when the action ALWAYS needs more
  input (opens a dialog); use a down-arrow for buttons that open a pop-up menu.
  Placeholder text must not end with an ellipsis.
- Real Unicode symbols: … → ÷ × − , × for dimensions (1920 × 1080), " " ' quotes,
  – date ranges, — interjections.
- **Window titles:** distinctive, short, no vendor/version
  ("Inbox — konqi@kde.org"); avoid file paths.
- Use `Controls.Label` for body text, `Kirigami.Heading` (with `level`) for
  headers — never `QtQuick.Text` (ignores system font). Use `i18nc()` for context
  and `i18ncp()` for any text referring to a number (plurals); leave ~50% extra
  room for translations; use KUIT semantic markup, not HTML.
- **Accelerators:** manually assign for buttons / radio / checkbox / switch only
  (auto-generated elsewhere); use `KStandardActions`/`KStandardShortcut` for
  standard actions. Don't use the Meta key for app shortcuts.

## 6. Accessibility & Inclusiveness

**Test matrix:** keyboard-only (unplug mouse — sensible default focus; active focus
visibly different from selection; no important text only in a tooltip);
pointer-only; touchscreen (tooltips also on press-and-hold); change color scheme;
raise system font to 14 (nothing cut off); mute audio; Orca screen reader; disable
animations globally (animated elements transition instantly / show a static image;
avoid blinking).

- Expose tooltip/label text to Orca via `Accessible` attached properties; no label
  used more than once in the same window. Order item text distinctive-part-first
  for keyboard type-ahead. Orca must announce a label AND a type ("Create New
  Folder, Button").
- Icons-only buttons keep `text` set (read by screen readers), hide it with
  `display: Controls.AbstractButton.IconOnly`, add a manual `Tooltip`. When
  shortening an interactive label, set `Accessible.name` to the full text (not for
  static labels).
- **Never convey information by color or audio alone.**
- **Inclusive language:** Kill→Close, Execute→Run, Abort→Exit, Fatal→Critical,
  Force→Require, Illegal→Unauthorized, Slave→Worker/job; "system" not
  "computer/phone"; avoid assumptions about ability/age/gender/ethnicity.

## 7. Breeze Icon System

Reference icons by **theme name** (FreeDesktop/Breeze) via `icon.name` (QML) or
`QIcon::fromTheme` (C++) — never bundle pixmaps. The chosen style is a preference;
the active theme resolves it.

- **Style by render size:** 16px symbolic; 22px almost always symbolic (full-color
  only in very-short list views); 32px+ full-color. Append `-symbolic` to request a
  monochrome variant.
- **Monochrome palette is semantic:** Shade Black = non-destructive/navigation/
  acceptance; Icon Red = destructive/delete/error; Beware Orange = warning;
  Plasma Blue = selection/focus/insertion; Noble Fir green = success/connection.
- **Deletion icons:** `edit-delete` (red trash) for deleting files / destroying
  user content; `edit-delete-remove` (red X) for restorable removal of abstract
  items; `trash-empty` (BLACK trash) for non-destructive move-to-trash (label it
  "move to trash"). Never a red icon for move-to-trash.
- Prefer **universal** icons (broad meaning) when there's a label/context; use
  **specific** icons only to disambiguate items sharing a universal icon. Set an
  icon on every button/menu item; never reuse one icon for multiple visible items.
- Overlay icons on content/other icons only with names beginning `emblem-`.
- C++: make `KIconThemes` a build dependency; call `KIconTheme::initTheme()` before
  `QApplication`; use `KStandardActions` so standard actions get standard icons.
  Browse names with Icon Explorer (plasma-sdk); request missing icons from the
  Breeze product on bugs.kde.org rather than inventing your own. Group icons-only
  buttons via `Kirigami.NavigationTabBar` / `Kirigami.ActionToolBar` to avoid
  overload.

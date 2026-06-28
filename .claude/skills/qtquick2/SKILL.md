---
name: qtquick2
description: >
  Idiomatic QtQuick 2 + QML as used in KDE applications. Covers QML document
  structure and Qt6 versionless imports, the single root object / id / property
  vs JS-expression binding model, signal handlers (on<Signal>), grouped and
  attached properties, splitting UI into uppercase component files that become
  types, QtQuick.Controls (imported `as Controls`) + QtQuick.Layouts + anchors,
  models/views/delegates (ListView/Repeater/ListModel + C++/Python
  QAbstractListModel), and the C++/Python<->QML bridge (Q_PROPERTY/NOTIFY,
  Q_INVOKABLE/Slot, QML_ELEMENT/QML_SINGLETON, context properties, Connections).
  Scope is the QML language + QtQuick stack only; Kirigami components and the KDE
  HIG live in the sibling `kirigami` skill.
  Keywords: QML, QtQuick, Qt Quick, Qt6, Qt Quick Controls, QtQuick.Layouts,
  anchors, ListView, ListModel, Repeater, delegate, model roles,
  QAbstractListModel, Q_PROPERTY, NOTIFY, Q_INVOKABLE, QML_ELEMENT,
  QML_SINGLETON, QQmlApplicationEngine, loadFromModule, Qt.binding,
  Component.onCompleted, Connections, PySide6, KDE, Kirigami, .qml.
user-invocable: false
metadata:
  type: reference
---

# QtQuick 2 / QML Best Practices (KDE-flavored)

## Role

Background knowledge for writing and reviewing **QtQuick 2 + QML** code in the KDE
idiom (the style taught by the KDE "first Kirigami app" tutorials for C++, Python,
and Rust). It covers the QML *language* and the QtQuick *stack*: document
structure, the object/property/binding model, signals and handlers, splitting into
component files, QtQuick.Controls + QtQuick.Layouts + anchors, the
model/view/delegate triad, and the C++/Python<->QML bridge.

Scope: the **QML language and QtQuick framework** only. Kirigami-specific
components (`Kirigami.ApplicationWindow`, `Kirigami.ScrollablePage`,
`Kirigami.Action`, `Kirigami.FormLayout`, `Kirigami.Units`, `Kirigami.Theme`,
`Kirigami.Dialog`, delegate addons) and the KDE Human Interface Guidelines live in
the **sibling `kirigami` skill** — consult it for HIG, page-stack navigation,
theming units, and Kirigami widget APIs. This skill uses Kirigami types in
examples (because the canonical tutorials do) but its *teaching subject* is the
underlying QtQuick/QML mechanics that apply to any QtQuick app.

## When This Skill Activates

- Writing or modifying `.qml` files
- Reviewing QtQuick / Kirigami QML code
- Exposing C++ or Python (PySide6) objects to QML, or wiring `Q_PROPERTY`/signals/slots
- Building models, views, and delegates (ListView/Repeater/ListModel/QAbstractListModel)
- Designing layouts with QtQuick.Controls, QtQuick.Layouts, or anchors

---

## 1. Document Structure & Imports (Qt6 = versionless)

Every QML file is: imports, then **exactly one root object**, which has an `id` and
nested child objects/properties. The canonical KDE four-import header:

```qml
// Includes relevant modules used by the QML
import QtQuick                            // standard library: Item, Text, anchors, Qt.* enums
import QtQuick.Layouts                    // ColumnLayout/RowLayout/GridLayout + Layout.* attached props
import QtQuick.Controls as Controls       // Button, Label, TextField, ... — ALWAYS aliased
import org.kde.kirigami as Kirigami       // Kirigami types — ALWAYS aliased

Kirigami.ApplicationWindow {              // the ONE root object
    id: root                              // bare identifier, never quoted

    width: 400
    height: 300
    title: i18nc("@title:window", "Hello World")

    pageStack.initialPage: Kirigami.Page {        // dotted (sub-)property
        Controls.Label {
            anchors.centerIn: parent              // grouped property; parent = the Page
            text: i18n("Hello World!")
        }
    }
}
```

Hard rules:
- **Qt6 imports are versionless**: `import QtQuick`, never `import QtQuick 2.x`.
- **Alias Controls and Kirigami with `as`** so same-named components can't conflict —
  it is an explicit best practice. Use `Controls.Label`/`Controls.Button`, never bare
  `Label`. QtQuick and QtQuick.Layouts are imported *without* an alias.
- **One root object per file.** Many `id`s, one root.
- `id` values are bare identifiers referenced from anywhere in the file
  (`root.wideScreen`, `kountdownModel.append(...)`), never strings.

## 2. Properties: Assignment vs JS-Expression Binding

Any property accepts either a literal value or a JavaScript expression. When the
expression references other properties, QML keeps it **live** and re-evaluates
automatically when a dependency changes:

```qml
width: 400                                       // literal assignment (one value)
columns: root.wideScreen ? 4 : 2                 // binding: re-runs when root.wideScreen changes
visible: description.length > 0                  // binding on a model role
text: i18n("%1 days", Math.round((date - Date.now()) / 86400000))   // JS in a binding
```

- **Grouped properties** address sub-properties of a value type: `anchors.centerIn`,
  `icon.name`, or the brace-block form
  `anchors { left: parent.left; top: parent.top; right: parent.right }`.
- **Imperative binding** — a plain JS assignment is a *one-time* value, NOT a live
  binding. To stay reactive when assigning from JavaScript, wrap the expression in
  `Qt.binding(() => ...)`:

```qml
Component.onCompleted: {
    const button = standardButton(Kirigami.Dialog.Ok);
    button.enabled = Qt.binding(() => requiredFieldsFilled());   // live binding, not a snapshot
}
function requiredFieldsFilled() {
    return (nameField.text !== "" && dateField.acceptableInput);
}
```

`Component.onCompleted` is the attached signal that runs once the object exists
(needed here because `standardButton()` only returns the button afterward).

> These intro tutorials declare **no** custom `property`/`readonly`/`required`
> (except `required property` in delegates — §7) and **no** custom `signal`; they
> extend objects with the `function` keyword (custom methods like
> `requiredFieldsFilled()`) plus built-in signals. Do not assume keywords absent here.

## 3. Signals & Handlers

Signal handlers are property-style `on<SignalName>:`. Emit a signal by **calling it
like a function**:

```qml
Kirigami.Action {
    text: i18n("Quit")
    icon.name: "application-exit-symbolic"
    shortcut: StandardKey.Quit
    onTriggered: Qt.quit()
}

Controls.TextField {
    id: nameField
    onAccepted: descriptionField.forceActiveFocus()   // chain focus on Enter
}

// Re-emit a Dialog's inherited `accepted` signal:
onAccepted: addDialog.accepted()
```

- Handlers actually used in these tutorials: `onTriggered`, `onAccepted`,
  `onClicked`, `onCheckedChanged`, and the attached `Component.onCompleted`.
- For **any** property `foo` (of any type — not just booleans), QML auto-generates
  an `on<Foo>Changed` handler (e.g. `onCheckedChanged` from `checked`,
  `onTextChanged` from `text`).
- Calling `addDialog.accepted()` **emits** the signal; the conventional form is the
  signal-emit `...accepted()` (one tutorial inconsistently calls the *handler*
  `...onAccepted()` — prefer emitting the signal).

## 4. Attached vs Grouped Properties

Both use dotted syntax but are different mechanisms:

- **Grouped**: sub-properties of one value (`anchors.centerIn`, `icon.name`).
- **Attached**: properties an enclosing/owning type *contributes* to a child,
  addressed `Type.property`:

```qml
Kirigami.FormLayout {
    Controls.TextField {
        Kirigami.FormData.label: i18nc("@label:textbox", "Name*:")   // attached by FormLayout
    }
}
Controls.Button {
    Layout.alignment: Qt.AlignRight     // attached by QtQuick.Layouts
    Layout.columnSpan: 2
}
ListView.view.width                     // ListView attaches `view` to each delegate (§7)
Component.onCompleted: { ... }          // attached signal handler
```

## 5. Splitting Into Component Files (a file becomes a type)

Each `.qml` file's root object becomes an **instantiable type named after the
file** — so the file MUST start with an uppercase letter. Instantiate with
`Name { }`:

```qml
// components/AddDialog.qml          → root object Kirigami.Dialog { id: addDialog ... }
// components/KountdownDelegate.qml  → root object Kirigami.AbstractCard { ... }

// Main.qml after the split:
import org.kde.tutorial.components     // ONLY when components are a SEPARATE QML module

AddDialog { id: addDialog }

Kirigami.CardsListView {
    model: kountdownModel
    delegate: KountdownDelegate {}     // file → type
}
```

- A delegate previously wrapped in `Component { }` can be moved verbatim to its own
  file — a file behaves like a `Component`.
- The extra `import org.kde.tutorial.components` is needed **only** when the files
  live in a different QML module; files sharing the executable's module need no
  import. `Main.qml` never imports its own module.
- `Main.qml`'s uppercase `M` is also why `loadFromModule(..., "Main")` works (§8).

## 6. Controls, Layouts & Anchors (overview)

Interactive widgets come from QtQuick.Controls (`Controls.Button`,
`Controls.Label`, `Controls.TextField`, `Controls.CheckBox`, `Controls.Slider`,
`Controls.ToolBar`, ...); structure comes from QtQuick.Layouts
(`ColumnLayout`/`RowLayout`/`GridLayout` + `Layout.*`) and from anchors.

**The positioning split is load-bearing — never mix on one child:**
- Glue a *single item or a whole Layout* to its parent with **anchors**
  (`anchors.fill: parent`, `anchors.centerIn: parent`, `anchors.left/top/right`).
- Size/align the *children of a Layout* with **`Layout.*` attached props**
  (`Layout.fillWidth`, `Layout.fillHeight`, `Layout.alignment`) — never their own
  anchors.

```qml
Kirigami.Page {
    ColumnLayout {
        anchors.fill: parent                  // the Layout is anchored to the Page
        Controls.Button {
            Layout.alignment: Qt.AlignCenter  // the CHILD uses Layout.*, not anchors
            text: "Beep!"
            onClicked: showPassiveNotification("Boop!")
        }
    }
}
```

- `Layout.alignment` takes `Qt.*` flags (`Qt.AlignCenter`, `Qt.AlignHCenter`,
  `Qt.AlignVCenter`); text-internal `horizontalAlignment`/`verticalAlignment` take
  `Text.*` flags (`Text.AlignHCenter`, `Text.AlignRight`). Don't confuse the two
  enum families.
- `Layout.*` only affects *direct children* of a `ColumnLayout`/`RowLayout`/
  `GridLayout` (or `Kirigami.FormLayout`).

Full Controls/Layouts/anchors catalog → `references/controls-and-layouts.md`.

## 7. Models, Views & Delegates (overview)

The triad: a **view** (`ListView`, `GridView`, `Repeater`, ...) binds a `model` to
a `delegate` blueprint. The delegate reads data via `model.<role>` / `model.index`
(shortenable to bare names; **prefer promoting to `required property`**).

```qml
ListView {
    anchors.fill: parent                  // required in a plain Page; a view is visual & instantiated
    model: ListModel {
        id: plasmaProductsModel
        ListElement { product: "Plasma Desktop"; target: "desktop" }
        ListElement { product: "Plasma Mobile";  target: "mobile" }
    }
    delegate: Controls.ItemDelegate {
        width: ListView.view.width        // size from the view, NEVER parent anchors
        required property string product  // preferred over implicit model.product
        required property string target
        required property int index
        text: `${product} for ${target} at index ${index}`
    }
}
```

- Delegate **width**: `width: ListView.view.width`. Delegates must NOT use bottom
  anchors and essentially never `anchors.fill: parent` (height is independent of
  the view).
- `modelData` is for models with **one role or no role** (JS array, integer,
  single-role model): `model: ["Dolphin", "Ark"]` or `model: 30`.
- `Repeater` shares the same model/delegate contract but is **non-scrolling** and
  instantiates every delegate eagerly into its parent (use inside a `ColumnLayout`);
  use `ListView`/`CardsListView` when you need scrolling/recycling.
- C++/Python models subclass **`QAbstractListModel`** overriding
  `rowCount()`/`roleNames()`/`data()` (+ `setData()`, `begin/endInsertRows`).

Inline `ListModel`, C++ `QAbstractListModel`, role consumption, and editing →
`references/models-and-views.md`.

## 8. The C++/Python <-> QML Bridge

Modern KDE uses **declarative registration**, not `setContextProperty`. Expose a
QObject with `QML_ELEMENT` (+ `QML_SINGLETON` for app-wide singletons); state flows
C++→QML through a `Q_PROPERTY` `READ`/`WRITE`/`NOTIFY` trio whose NOTIFY signal
drives QML bindings.

```cpp
// backend.h
#include <qqmlintegration.h>
class Backend : public QObject {
    Q_OBJECT
    QML_ELEMENT
    QML_SINGLETON
    Q_PROPERTY(QString introductionText READ introductionText
               WRITE setIntroductionText NOTIFY introductionTextChanged)
public:
    QString introductionText() const;
    void setIntroductionText(const QString &introductionText);
    Q_SIGNAL void introductionTextChanged();
private:
    QString m_introductionText = QStringLiteral("Hello World!");
};
```

`Q_INVOKABLE` methods live on whichever QObject owns the operation — a value-holding
singleton like `Backend` stays a pure property bag, while a mutation like
`Q_INVOKABLE void deleteSpecies(const QString &speciesName, const int &rowIndex)`
belongs on the `QAbstractListModel` subclass it acts on (see §10 / models-and-views.md).

```cpp
// backend.cpp — the setter MUST emit NOTIFY or QML won't update
void Backend::setIntroductionText(const QString &t) {
    m_introductionText = t;
    Q_EMIT introductionTextChanged();
}
```

```qml
// QML side: import the module URI (UNALIASED) → singleton type is visible
import org.kde.tutorial.components
Kirigami.Heading { text: Backend.introductionText }   // live binding via NOTIFY
```

Loading the UI from the host language:

```cpp
// C++ (preferred): load by module URI + type name
QQmlApplicationEngine engine;
engine.rootContext()->setContextObject(new KLocalizedContext(&engine));  // for i18n; NOT the backend
engine.loadFromModule("org.kde.tutorial", "Main");   // URI from CMake, "Main" from Main.qml (uppercase!)
if (engine.rootObjects().isEmpty()) return -1;
```

```python
# Python (PySide6): the older engine.load(QUrl(...)) form
engine = QQmlApplicationEngine()
base_path = files("kirigami_python").joinpath("qml", "Main.qml")
engine.load(QUrl(f"{base_path}"))
```

Key rules:
- A `Q_PROPERTY` alone is NOT reactive — you must declare the NOTIFY signal AND
  `Q_EMIT` it from the setter; the names must exactly match getter/setter/signal.
- The C++ class name becomes the QML type name verbatim; a `QML_SINGLETON` is used
  as a namespaced value (`Backend.introductionText`), never instantiated in QML.
- Exposing C++ is TWO steps: the header macros **and** adding the `.cpp/.h` to a QML
  module (`ecm_add_qml_module`/`qt_add_qml_module`). The CMake `URI` string MUST
  equal the QML import string. No manual `qmlRegisterType`.
- `Q_INVOKABLE` (C++) / `@Slot` (PySide6) methods are callable from QML on the
  object that exposes them — e.g. the model: `customModel.deleteSpecies(model.species, index)`.
- Keep logic in the backend; the docs explicitly discourage writing logic in QML.

Deep dive (singletons, Connections, dynamic `Qt.createComponent`, PySide6 mapping)
→ `references/qml-language.md`.

## 9. `Connections` and Reacting to Signals

When you cannot attach an `on<Signal>` handler directly on the emitter (e.g. a
singleton or an externally-provided object), use the `Connections` element to bind
a handler to a target's signal:

```qml
Connections {
    target: Backend
    function onIntroductionTextChanged() { console.log("changed") }
}
```

> The KDE intro tutorials do not themselves demonstrate `Connections`,
> `QtQuick states/transitions/animations`, or `Behavior`; their bridge is
> `Q_PROPERTY`/NOTIFY + singleton access + `Kirigami.Action.onTriggered` +
> `Qt.createComponent`. Use those proven patterns; treat the rest as standard
> QtQuick available when needed.

## 10. Localization & Theming Conventions

- Wrap user-visible strings in `i18n(...)` / `i18nc(...)`; **`i18nc` takes the
  translator context FIRST** (`i18nc("@title:window", "Hello World")`,
  `"@label:textbox"`, `"@action:button"`). `i18n` works in QML only because C++
  sets a `KLocalizedContext` on the engine's root context — Python/Rust tutorial
  QML use plain string literals instead.
- Never hardcode pixel spacing — use `Kirigami.Units`
  (`Kirigami.Units.largeSpacing`, `Kirigami.Units.gridUnit * 20`) and read fonts/
  colors from `Kirigami.Theme`. (These are Kirigami APIs — see the `kirigami` skill.)
- Use `icon.name` with freedesktop icon names (`"list-add-symbolic"`), not image paths.

## Anti-Pattern / Review Checklist

Scan QML/bridge code for these (all detailed above):

versioned imports (`import QtQuick 2.x`) · bare `Label`/`Button` (un-aliased
Controls) · quoted `id` (`id: "root"`) · more than one root object per file ·
lowercase component filename · plain JS assignment where a live binding is needed
(missing `Qt.binding`) · a child inside a Layout using its own anchors · `Layout.*`
on a non-Layout child · delegate sized via `anchors.fill: parent`/parent anchors
instead of `ListView.view.width` · delegate using bottom anchors · `modelData` on a
multi-role model · hardcoded pixel spacing instead of `Kirigami.Units` · `i18nc`
context passed as the second arg · `Q_PROPERTY` with no NOTIFY, or a setter that
forgets `Q_EMIT` · `setData()` that forgets to `Q_EMIT dataChanged()` · exposing a
backend via `setContextProperty` instead of `QML_ELEMENT` · CMake `URI` not matching
the QML import string · calling a handler (`addDialog.onAccepted()`) instead of
emitting the signal (`addDialog.accepted()`) · writing app logic in QML instead of
the C++/Python backend.

## Additional Resources

- [references/qml-language.md](references/qml-language.md) — QML language deep dive:
  objects/ids/bindings, signals & custom `function`s, splitting files & QML modules,
  loading from C++/Python/Rust, and the full C++/Python<->QML bridge
  (Q_PROPERTY/NOTIFY, QML_ELEMENT/QML_SINGLETON, Q_INVOKABLE, Connections,
  Qt.createComponent).
- [references/controls-and-layouts.md](references/controls-and-layouts.md) —
  QtQuick.Controls widget catalog, QtQuick.Layouts containers + `Layout.*` attached
  properties, anchors, and the anchors-vs-Layouts positioning split.
- [references/models-and-views.md](references/models-and-views.md) —
  model/view/delegate patterns: ListView/Repeater, ListModel/ListElement, role
  consumption (`model.<role>` / `modelData` / `required property`), and the C++/
  Python `QAbstractListModel` (`rowCount`/`roleNames`/`data`/`setData`, row
  mutations, editing from QML).

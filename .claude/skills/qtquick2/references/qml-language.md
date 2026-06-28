# QML Language & the C++/Python <-> QML Bridge

Companion to SKILL.md §1–§5, §8–§9. Load when writing QML document structure,
custom methods/signals, splitting files into QML modules, or wiring a C++/Python
(PySide6) backend to QML.

## 1. Document anatomy

A QML file = imports, then exactly ONE root object, recursively containing child
objects and property assignments. Identifiers (`id`) are bare, file-wide references.

```qml
import QtQuick
import QtQuick.Layouts
import QtQuick.Controls as Controls
import org.kde.kirigami as Kirigami

Kirigami.ApplicationWindow {
    id: root                         // referenced anywhere: root.wideScreen
    width: 400
    height: 300
    title: i18nc("@title:window", "Hello World")

    pageStack.initialPage: Kirigami.Page {
        Controls.Label {
            anchors.centerIn: parent // `parent` = the enclosing Kirigami.Page
            text: i18n("Hello World!")
        }
    }
}
```

The Python/Rust variants are byte-identical except they use plain string literals
(`title: "Hello World"`, `text: "Hello World!"`) instead of `i18n`/`i18nc`.

## 2. Bindings: declarative vs imperative

A property assignment with a JS expression that references other properties is a
**live binding** — re-evaluated whenever a dependency changes. A plain JS assignment
in a handler is a **one-shot** value.

```qml
columns: root.wideScreen ? 4 : 2                 // live: tracks root.wideScreen
text: i18n("%1 days", Math.round((date - Date.now()) / 86400000))
```

To assign imperatively yet stay reactive, wrap the expression in `Qt.binding`:

```qml
Component.onCompleted: {
    const button = standardButton(Kirigami.Dialog.Ok);
    // () => is a JavaScript arrow function
    button.enabled = Qt.binding(() => requiredFieldsFilled());
}
```

`Component.onCompleted` is an attached signal handler that runs once the object is
fully constructed (the only point at which `standardButton()` returns the button).

## 3. Custom methods with `function`; built-in signals

The intro tutorials extend objects with the `function` keyword, not custom
`property`/`signal` declarations:

```qml
function requiredFieldsFilled() {
    return (nameField.text !== "" && dateField.acceptableInput);
}
function appendDataToModel() { /* ... */ }
function clearFieldsAndClose() { /* ... */ }

onAccepted: {
    if (!addDialog.requiredFieldsFilled()) return;
    appendDataToModel();
    clearFieldsAndClose();
}
```

Emit a signal by calling it like a function. Built-in signals used: `accepted`
(`onAccepted`), `triggered` (`onTriggered`), `clicked` (`onClicked`),
auto-generated `onCheckedChanged` from the boolean `checked` property.

```qml
onAccepted: addDialog.accepted()     // EMITS the inherited Dialog `accepted` signal (conventional)
// (one tutorial inconsistently writes addDialog.onAccepted() — calling the handler; avoid)
```

`Kirigami.Dialog` enum flags are bitwise-OR'd:
`standardButtons: Kirigami.Dialog.Ok | Kirigami.Dialog.Cancel`;
`standardButton(Kirigami.Dialog.Ok)` returns the live button object.

## 4. Splitting into component files & QML modules

A `.qml` file's root object becomes an instantiable type named after the file
(filename MUST be uppercase). Instantiate as `Name { }`.

```qml
// components/AddDialog.qml          root = Kirigami.Dialog { id: addDialog ... }
// components/KountdownDelegate.qml  root = Kirigami.AbstractCard { ... }

// Main.qml:
import org.kde.tutorial.components   // ONLY when components are a SEPARATE module
AddDialog { id: addDialog }
Kirigami.CardsListView { model: kountdownModel; delegate: KountdownDelegate {} }
```

- A `Component { }`-wrapped delegate can be moved verbatim to its own file — a file
  behaves like a `Component`, so the wrapper is dropped.
- The extra import is required only when the new files form a *different* QML module
  (`org.kde.tutorial.components`); files in the executable's own module need none.
  `Main.qml` never imports its own module.

CMake registers modules (extra-cmake-modules). The `URI` is exactly what
`loadFromModule`'s first argument and the QML `import` string must match:

```cmake
# main module
add_executable(kirigami-hello)
ecm_add_qml_module(kirigami-hello URI org.kde.tutorial)
target_sources(kirigami-hello PRIVATE main.cpp)          # C++ (incl. QML_ELEMENT types)
ecm_target_qml_sources(kirigami-hello SOURCES Main.qml)  # QML files

# separate module
add_library(kirigami-hello-components)
ecm_add_qml_module(kirigami-hello-components URI "org.kde.tutorial.components" GENERATE_PLUGIN_SOURCE)
ecm_target_qml_sources(kirigami-hello-components SOURCES AddDialog.qml KountdownDelegate.qml ExposePage.qml)
target_sources(kirigami-hello-components PRIVATE backend.cpp backend.h model.cpp model.h)
ecm_finalize_qml_module(kirigami-hello-components)
```

```rust
// Rust build.rs equivalent
CxxQtBuilder::new_qml_module(
    QmlModule::new("org.kde.tutorial").qml_files(&["src/qml/Main.qml"])
).build();
```

`.qml` files go in `ecm_target_qml_sources`; C++ types (`QML_ELEMENT`) go in
`target_sources(... PRIVATE ...)`. A separate module also needs
`GENERATE_PLUGIN_SOURCE` + `ecm_finalize_qml_module()` and must be linked into the
executable.

## 5. Loading the UI from the host language

```cpp
// C++ (preferred): QApplication so the Widgets-based Breeze QStyle is usable
KIconTheme::initTheme();                       // BEFORE QApplication, so icon.name resolves
QApplication app(argc, argv);
QApplication::setStyle("breeze");
QQuickStyle::setStyle("org.kde.desktop");
QQmlApplicationEngine engine;
engine.rootContext()->setContextObject(new KLocalizedContext(&engine));  // i18n only
engine.loadFromModule("org.kde.tutorial", "Main");   // URI (CMake) + type "Main" (uppercase!)
if (engine.rootObjects().isEmpty()) return -1;
return app.exec();
```

```python
# Python (PySide6): older engine.load(QUrl(...)); set the style via env instead
# QT_QUICK_CONTROLS_STYLE=org.kde.desktop
engine = QQmlApplicationEngine()
base_path = files("kirigami_python").joinpath("qml", "Main.qml")
engine.load(QUrl(f"{base_path}"))
```

```rust
engine.load(&"qrc:/qt/qml/org/kde/tutorial/src/qml/Main.qml".into());
```

The legacy C++ form `engine.load(QUrl(QStringLiteral("qrc:/qt/qml/org/kde/tutorial/qml/Main.qml")))`
is "excessively verbose after Qt6"; prefer `loadFromModule`. The qrc URL =
`qrc:/qt/qml/` + URI-with-slashes + optional qml dir + file.

## 6. Exposing C++ to QML: declarative registration

Modern KDE uses `QML_ELEMENT` (+ `QML_SINGLETON`), NOT `setContextProperty`. The
only `setContext*` call shown is `setContextObject(new KLocalizedContext(...))` for
i18n — not the backend.

```cpp
// backend.h
#pragma once
#include <QObject>
#include <qqmlintegration.h>          // (prose links QML_ELEMENT to <QtQml/qqmlregistration.h>)

class Backend : public QObject {
    Q_OBJECT
    QML_ELEMENT
    QML_SINGLETON
    Q_PROPERTY(QString introductionText READ introductionText
               WRITE setIntroductionText NOTIFY introductionTextChanged)
public:
    explicit Backend(QObject *parent = nullptr);
    QString introductionText() const;
    void setIntroductionText(const QString &introductionText);
    Q_SIGNAL void introductionTextChanged();
private:
    QString m_introductionText = QStringLiteral("Hello World!");
};
```

```cpp
// backend.cpp
QString Backend::introductionText() const { return m_introductionText; }

void Backend::setIntroductionText(const QString &introductionText) {
    m_introductionText = introductionText;
    Q_EMIT introductionTextChanged();      // REQUIRED — without it QML never updates
}
```

```qml
import org.kde.kirigami as Kirigami
import org.kde.tutorial.components          // UNALIASED → exposes singleton type `Backend`

Kirigami.Page {
    Kirigami.Heading {
        anchors.centerIn: parent
        text: Backend.introductionText       // live binding driven by NOTIFY
    }
}
```

Rules:
- READ/WRITE/NOTIFY names must exactly match getter/setter/signal. The NOTIFY signal
  needs no `.cpp` body — emitting it is the work.
- The class name becomes the QML type name verbatim; a `QML_SINGLETON` is accessed as
  `Backend.<prop>`, never instantiated in QML.
- Two steps: header macros AND the `.cpp/.h` in a QML module (CMake `URI` == import
  string). No manual `qmlRegisterType`.
- PySide6 equivalent: decorate the class with `@QmlElement` (and `@QmlSingleton`),
  expose state with `Property(str, notify=...)`, and mark callable methods with
  `@Slot` (the analogue of `Q_INVOKABLE`).

## 7. Calling into the backend; dynamic components; Connections

```qml
// Q_INVOKABLE / @Slot method called from QML:
Controls.Button { text: "Delete"; onClicked: customModel.deleteSpecies(model.species, index) }

// dynamic page creation from a module URI + type name:
onTriggered: pageStack.push(Qt.createComponent("org.kde.tutorial.components", "ExposePage"))

// Kirigami.Action is the QML-side event sink:
Kirigami.Action {
    id: addAction
    icon.name: "list-add-symbolic"
    text: i18nc("@action:button", "Add kountdown")
    onTriggered: kountdownModel.append({ name: "New", description: "...", date: 1000 })
}
```

When you cannot place an `on<Signal>` handler on the emitter itself (a singleton, an
injected object), bind with `Connections`:

```qml
Connections {
    target: Backend
    function onIntroductionTextChanged() { /* react */ }
}
```

> The KDE intro tutorials do not themselves exercise `Connections`,
> `Q_INVOKABLE`-called-from-QML beyond the model methods above, or
> states/transitions/animations/`Behavior`. The demonstrated, proven bridge is
> `Q_PROPERTY`/NOTIFY + singleton access + `Kirigami.Action.onTriggered` +
> `Qt.createComponent`. Keep app logic in the backend (QObject subclasses), not QML.

## 8. Gotchas

- A `Q_PROPERTY` without a NOTIFY signal (or a setter that forgets `Q_EMIT`) yields
  a dead, non-reactive binding.
- Backends are exposed via `QML_ELEMENT`/`QML_SINGLETON` + a QML module, never via
  `setContextProperty`.
- Filenames that become types MUST be uppercase; that is also why
  `loadFromModule(URI, "Main")` works.
- The extra `import org.kde.tutorial.components` is needed only for a *separate*
  module, never for the entrypoint's own module.
- `qqmlintegration.h` vs `qqmlregistration.h`: the actual `backend.h` includes
  `<qqmlintegration.h>` while prose links the macro to `<QtQml/qqmlregistration.h>`
  — keep both in mind; do not "correct" the source.
- Use `QStringLiteral()` in production (the tutorial disables
  `QT_NO_CAST_FROM_ASCII` only for didactic raw strings — do not copy that flag).

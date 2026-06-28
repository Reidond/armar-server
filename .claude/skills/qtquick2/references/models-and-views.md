# Models, Views & Delegates

Companion to SKILL.md §7. Load when building ListView/Repeater UIs, defining
delegates, or backing a view with a C++/Python `QAbstractListModel`.

## 1. The triad

A **view** (`ListView`, `GridView`, `TableView`, `TreeView`, `Repeater`, or
Kirigami's `CardsListView`) binds a `model` to a `delegate` blueprint. The two
essential view properties are `model` and `delegate`.

`model` accepts: a `ListModel` (id or inline), a JS array (`["Dolphin", "Ark"]`), an
integer (`30`), or a C++/Python `QAbstractListModel` instance.

## 2. ListView + inline ListModel + Component delegate (multi-role)

```qml
Kirigami.ScrollablePage {
    ListView {
        anchors.fill: parent                 // needed in a plain Kirigami.Page; optional in ScrollablePage
        model: plasmaProductsModel
        delegate: listDelegate
    }
    ListModel {
        id: plasmaProductsModel
        ListElement { product: "Plasma Desktop"; target: "desktop" }
        ListElement { product: "Plasma Mobile";  target: "mobile" }
    }
    Component {
        id: listDelegate
        Controls.ItemDelegate {
            width: ListView.view.width        // size from the view, NOT parent anchors
            text: `${model.product} is KDE software for ${model.target} at index ${model.index}`
        }
    }
}
```

`ListElement` properties (`product`, `target`) become **roles**; `model.index` is
always available. `ListModel` methods: `append(jsobject)`, `get(index)`,
`remove(index, count)`, `set(index, jsobject)`.

`Component { }` wraps a delegate as a blueprint that is only instantiated when the
view creates items. Inline `model`/`delegate` is equivalent shorthand (an inline
delegate is wrapped implicitly) — use an explicit `Component` only for a reusable
named blueprint.

## 3. Consuming roles — prefer `required property`

`model.<role>` / `model.index` can be shortened to bare names, but the docs RECOMMEND
promoting each to a typed `required property`:

```qml
Component {
    id: listDelegate
    Controls.ItemDelegate {
        width: ListView.view.width
        required property string product
        required property string target
        required property int index
        text: `${product} is KDE software for ${target} at index ${index}`
    }
}
```

`modelData` is for models with **one role or no role** (JS array, integer,
single-role Qt model):

```qml
model: ["Dolphin", "Ark"]        // or  model: 30  (modelData is the index)
delegate: Controls.ItemDelegate {
    width: ListView.view.width
    required property string modelData
    text: modelData
}
```

## 4. Card delegate sizing (Kirigami.CardsListView)

`Kirigami.AbstractCard`'s `contentItem` is a raw `Item` whose
`implicitWidth`/`implicitHeight` default to **0x0** — you MUST bind them to the inner
layout's implicit size or the card collapses. (Kirigami types here are documented in
the `kirigami` skill; this shows the QtQuick sizing mechanic.)

```qml
Kirigami.CardsListView {
    model: kountdownModel
    delegate: kountdownDelegate
}
Component {
    id: kountdownDelegate
    Kirigami.AbstractCard {
        contentItem: Item {
            implicitWidth: delegateLayout.implicitWidth     // raw Item is 0x0 by default!
            implicitHeight: delegateLayout.implicitHeight
            GridLayout {
                id: delegateLayout
                anchors { left: parent.left; top: parent.top; right: parent.right }  // NOT bottom
                rowSpacing: Kirigami.Units.largeSpacing
                columnSpacing: Kirigami.Units.largeSpacing
                columns: root.wideScreen ? 4 : 2            // responsive
                Kirigami.Heading { level: 1; text: date }
                ColumnLayout {
                    Kirigami.Heading { Layout.fillWidth: true; level: 2; text: name }
                    Kirigami.Separator { Layout.fillWidth: true; visible: description.length > 0 }
                    Controls.Label {
                        Layout.fillWidth: true; wrapMode: Text.WordWrap
                        text: description; visible: description.length > 0
                    }
                }
                Controls.Button { Layout.alignment: Qt.AlignRight; Layout.columnSpan: 2; text: i18n("Edit") }
            }
        }
    }
}
```

Roles (`date`/`name`/`description`) are used as bare names here. Rows are added
imperatively: `kountdownModel.append({ name, description, date: new Date(...) })`.

## 5. Repeater (non-scrolling)

`Repeater` shares the model/delegate contract but instantiates ALL delegates eagerly
as children of its parent (no scrolling/recycling). Use it inside a `ColumnLayout`;
use `ListView`/`CardsListView` when you need scrolling.

```qml
Kirigami.ScrollablePage {
    Model { id: customModel }                 // C++ QML_ELEMENT type, instantiated like any QML type
    ColumnLayout {
        anchors.left: parent.left
        anchors.right: parent.right
        Repeater {
            model: customModel
            delegate: Kirigami.AbstractCard {
                header: Kirigami.Heading { text: model.species; level: 2 }
                contentItem: Controls.Label { text: model.characters }
            }
        }
    }
}
```

## 6. C++/Python QAbstractListModel

Subclass `QAbstractListModel` and override the three mandatory methods; expose with
`Q_OBJECT` + `QML_ELEMENT` (registered through `ecm_add_qml_module` — no manual
`qmlRegisterType`).

```cpp
// model.h
class Model : public QAbstractListModel {
    Q_OBJECT
    QML_ELEMENT
public:
    enum Roles { SpeciesRole = Qt::UserRole, CharactersRole };       // custom roles from Qt::UserRole
    int rowCount(const QModelIndex &) const override;               // how many items
    QHash<int, QByteArray> roleNames() const override;              // role enum -> QByteArray name
    QVariant data(const QModelIndex &index, int role) const override;
    bool setData(const QModelIndex &index, const QVariant &value, int role) override;
    Q_INVOKABLE void addSpecies(const QString &species);
    Q_INVOKABLE void deleteSpecies(const QString &speciesName, const int &rowIndex);
private:
    QMap<QString, QStringList> m_list = { /* ... */ };
};
```

```cpp
// model.cpp
int Model::rowCount(const QModelIndex &) const { return m_list.count(); }

QHash<int, QByteArray> Model::roleNames() const {
    return { {SpeciesRole, "species"}, {CharactersRole, "characters"} };  // names become model.species etc.
}

QVariant Model::data(const QModelIndex &index, int role) const {
    const auto it = std::next(m_list.begin(), index.row());
    switch (role) {
        case SpeciesRole:    return it.key();
        case CharactersRole: return formatList(it.value());   // convert QStringList -> QString
        default:             return {};
    }
}
```

- The `QByteArray` names returned by `roleNames()` are exactly what QML reads as
  `model.species` / `model.characters`. They are usable ONLY while the model is being
  delegated (inside a view/Repeater delegate).
- `data()` may convert types — binding incompatible types fails, so e.g. a
  `QStringList` is formatted to a `QString`.
- PySide6 equivalent: subclass `QAbstractListModel`, override the same methods,
  return role names from `roleNames()`, and decorate callable methods with `@Slot`.

## 7. Editing / adding / removing rows from QML

Writing `model.<role> = ...` in QML routes to C++ `setData()` (role `Qt::EditRole`).
**`setData()` does NOT auto-emit `dataChanged()`** — you must `Q_EMIT` it or the UI
won't refresh. Structural changes are wrapped in `begin/endInsertRows` /
`begin/endRemoveRows` with `QModelIndex()` as parent.

```qml
// invoke a Q_INVOKABLE method:
Controls.Button { text: "Delete"; onClicked: customModel.deleteSpecies(model.species, index) }

// edit via a dialog writing back to a writable role (triggers setData):
Kirigami.PromptDialog {
    id: editPrompt
    property var model
    standardButtons: Kirigami.Dialog.Ok | Kirigami.Dialog.Cancel
    onAccepted: editPrompt.model.characters = editPromptText.text
    Controls.TextField { id: editPromptText; onAccepted: editPrompt.accept() }
}
// add via Q_INVOKABLE:
onAccepted: customModel.addSpecies(addPromptText.text)
```

```cpp
void Model::addSpecies(const QString &s) {
    beginInsertRows(QModelIndex(), m_list.size() - 1, m_list.size() - 1);
    m_list.insert(s, {});
    endInsertRows();
    Q_EMIT dataChanged(index(0), index(m_list.size() - 1));   // build indices via index(int)
}
```

## 8. Empty-state, search & pull-to-refresh

```qml
Kirigami.ScrollablePage {
    supportsRefreshing: true
    onRefreshingChanged: if (refreshing) myModel.refresh()
    titleDelegate: Kirigami.SearchField {
        Layout.fillWidth: true
        onTextChanged: mySortFilterModel.filterText = text   // drives a proxy model
        KeyNavigation.tab: listView
    }
    ListView {
        id: listView
        model: myModel
        delegate: BasicListItem {}
        Kirigami.PlaceholderMessage {                        // put centered/non-visual items INSIDE the view
            anchors.centerIn: parent
            width: parent.width - (Kirigami.Units.largeSpacing * 4)
            visible: listView.count === 0
            text: i18n("No data found")
            helpfulAction: Kirigami.Action { text: i18n("Load data") }
        }
    }
}
```

`KSortFilterProxyModel` (from `org.kde.kitemmodels`) does filtering/sorting in pure
QML — wrap the source model and expose `filterText` from the SearchField.

## 9. Kirigami delegate addons (brief)

Kirigami / Kirigami-Addons layer subtitle+icon delegates over the Qt ones (full API
in the `kirigami` skill):

- `import org.kde.kirigami.delegates as KD` — types ENDING in `Delegate`
  (`KD.SubtitleDelegate`, `KD.CheckSubtitleDelegate`,
  `KD.RadioSubtitleDelegate`, `KD.SwitchSubtitleDelegate`) are used **directly as the
  view's delegate** (set `width`, `text`, `subtitle`, `icon.name`).
- `KD.TitleSubtitle` / `KD.IconTitleSubtitle` instead **override a Qt delegate's
  `contentItem`** (`title`, `subtitle`, `icon.name`):

```qml
Controls.ItemDelegate {
    width: ListView.view.width
    text: `${model.product} for ${model.target}.`
    contentItem: KD.IconTitleSubtitle { title: parent.text; subtitle: `index ${model.index}`; icon.name: "kde" }
}
```

- `import org.kde.kirigamiaddons.formcard as FormCard` — form-card delegates for
  settings pages (`FormCard.FormCardPage` inherits `Kirigami.ScrollablePage` and has
  its own internal layout, so its `FormCard.FormButtonDelegate`/`FormTextDelegate`/
  `FormSwitchDelegate`/`FormComboBoxDelegate` need no wrapping `ColumnLayout`).
- Prefer declarative bindings (`visible: autosave.checked`) over imperative JS
  assignments in handlers.

## 10. Gotchas

- Delegate width: `width: ListView.view.width`, never parent anchors; a delegate's
  parent is not guaranteed to be the view.
- Delegates must NOT use bottom anchors and essentially never `anchors.fill: parent`
  — height is independent of the view; set only width, let height be implicit.
- The view is visual and instantiated immediately: in a `Kirigami.ScrollablePage` a
  `ListView` becomes main content and `anchors.fill: parent` is NOT required; in a
  plain `Kirigami.Page` it IS required or the list won't show.
- Do NOT put a `Controls.ScrollView` inside a `Kirigami.ScrollablePage` — its
  children are already inside a ScrollView.
- A raw `Item` as `AbstractCard.contentItem` is 0x0 until you bind
  `implicitWidth`/`implicitHeight` to the inner layout.
- `modelData` is only for single-role/no-role models; multi-role data is
  `model.<rolename>`; `model.index` is always available.
- `setData()` must manually `Q_EMIT dataChanged()`; after insert/remove also emit
  across affected rows (a `QMap` may reorder). Wrap structural changes in
  `begin/endInsertRows` / `begin/endRemoveRows`.
- Import aliases are load-bearing: `as Controls`, `as Kirigami`, `as KD`,
  `as FormCard`. Use `Kirigami.Units` for spacing, not hardcoded pixels.

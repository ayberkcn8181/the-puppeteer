import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import QtQuick.Dialogs

ApplicationWindow {
    id: win
    objectName: "mainWindow"
    width: 1100
    height: 760
    minimumWidth: 800
    minimumHeight: 600
    visible: true
    title: "The Puppeteer"
    property int page: 0
    property bool dark: backend.theme === "dark" || (backend.theme === "system" && backend.systemDark)
    property color base: dark ? "#181120" : "#F6F1FC"
    property color surface: dark ? "#251D32" : "#FFFFFF"
    property color sidebar: dark ? "#20172B" : "#EEE5F8"
    property color ink: dark ? "#F2EBFF" : "#241935"
    property color secondary: dark ? "#B9ABC9" : "#675876"
    property color line: dark ? "#443651" : "#DED3EE"
    property color accent: dark ? "#C5A3FF" : "#7C3AED"
    property color onAccent: dark ? "#241239" : "#FFFFFF"
    property color soft: dark ? "#3A2752" : "#EEE3FF"
    property color danger: dark ? "#FF9BAB" : "#B33B4B"
    property bool hasSelection: (backend.selected.name || "") !== ""
    property bool canOperate: hasSelection && backend.host.ready && !backend.busy && !backend.refreshing
    color: base
    onClosing: function(close) {
        if (backend.busy) {
            close.accepted = false
            closeBusyDialog.open()
        }
    }
    font.family: "Noto Sans"
    font.pixelSize: 14
    palette.window: base
    palette.windowText: ink
    palette.base: surface
    palette.text: ink
    palette.button: surface
    palette.buttonText: ink
    palette.highlight: accent
    palette.highlightedText: onAccent
    palette.mid: line
    palette.placeholderText: secondary

    function tr(turkish, english) { return backend.language === "en" ? english : turkish }
    function openCreate(index) {
        createError.text = ""
        distroChoice.currentIndex = index || 0
        versionChoice.currentIndex = 0
        imageField.text = backend.catalog[distroChoice.currentIndex].image
        nameField.text = backend.catalog[distroChoice.currentIndex].id + "-work"
        ownHome.checked = true
        templateChoice.currentIndex = 0
        extraPackages.text = ""
        nvidia.checked = false
        createDialog.open()
    }

    component ActionButton: Button {
        property bool primary: false
        property bool destructive: false
        implicitHeight: 38
        leftPadding: 13
        rightPadding: 13
        Accessible.name: text
        contentItem: Text {
            text: parent.text
            font: parent.font
            color: parent.primary ? win.onAccent : parent.destructive ? win.danger : win.ink
            horizontalAlignment: Text.AlignHCenter
            verticalAlignment: Text.AlignVCenter
            opacity: parent.enabled ? 1 : 0.45
        }
        background: Rectangle {
            radius: 7
            color: parent.primary ? win.accent : parent.hovered ? win.soft : win.surface
            border.width: parent.activeFocus ? 2 : 1
            border.color: parent.activeFocus ? win.accent : parent.primary ? win.accent : win.line
            opacity: parent.enabled ? 1 : 0.5
        }
    }
    component Heading: Label {
        color: ink
        font.pixelSize: 25
        font.weight: Font.Medium
        wrapMode: Text.Wrap
    }
    component Hint: Label {
        color: secondary
        font.pixelSize: 13
        wrapMode: Text.Wrap
        Layout.fillWidth: true
    }
    component Field: TextField {
        implicitHeight: 38
        color: ink
        selectByMouse: true
        background: Rectangle {
            radius: 7
            color: surface
            border.color: parent.activeFocus ? accent : line
            border.width: parent.activeFocus ? 2 : 1
        }
    }
    component Choice: ComboBox {
        implicitHeight: 38
        background: Rectangle {
            radius: 7
            color: surface
            border.color: parent.activeFocus ? accent : line
        }
    }
    component Panel: Rectangle {
        radius: 12
        color: surface
        border.color: line
    }
    component Pair: RowLayout {
        property string label
        property string value
        Layout.fillWidth: true
        spacing: 12
        Label { text: parent.label; color: secondary; Layout.preferredWidth: 98; font.pixelSize: 12 }
        Label { text: parent.value; color: ink; Layout.fillWidth: true; wrapMode: Text.Wrap; font.pixelSize: 12; textFormat: Text.PlainText }
    }

    header: ToolBar {
        background: Rectangle { color: surface; border.color: line }
        RowLayout {
            anchors.fill: parent
            anchors.leftMargin: 18
            anchors.rightMargin: 18
            spacing: 12
            Image { source: "logo.svg"; Layout.preferredWidth: 34; Layout.preferredHeight: 34; Accessible.ignored: true }
            Label { text: "The Puppeteer"; color: ink; font.pixelSize: 18; font.weight: Font.Medium }
            Label { text: tr("Distrobox yöneticisi", "Distrobox manager"); color: secondary; visible: win.width > 950; font.pixelSize: 12 }
            Item { Layout.fillWidth: true }
            Label { text: backend.demo ? "DEMO" : "v0.2.0"; color: accent; font.pixelSize: 12 }
            Choice {
                objectName: "themeChoice"
                model: [tr("Sistem teması", "System theme"), tr("Koyu mor", "Dark purple"), tr("Açık lavanta", "Light lavender")]
                currentIndex: ["system", "dark", "light"].indexOf(backend.theme)
                Accessible.name: tr("Tema", "Theme")
                onActivated: backend.setPreference("theme", ["system", "dark", "light"][currentIndex])
                Layout.preferredWidth: 145
            }
            Choice {
                model: ["Türkçe", "English"]
                currentIndex: backend.language === "en" ? 1 : 0
                Accessible.name: tr("Dil", "Language")
                onActivated: backend.setPreference("language", currentIndex === 1 ? "en" : "tr")
                Layout.preferredWidth: 100
            }
        }
        implicitHeight: 62
    }

    RowLayout {
        anchors.fill: parent
        spacing: 0
        Rectangle {
            Layout.preferredWidth: 170
            Layout.fillHeight: true
            color: sidebar
            ColumnLayout {
                anchors.fill: parent
                anchors.margins: 12
                spacing: 7
                Repeater {
                    model: [tr("Ortamlar", "Environments"), tr("Dağıtımlar", "Distributions"), tr("Uygulamalar", "Applications"), tr("İşlemler", "Activity"), tr("Kurulum", "Setup"), tr("Ortam tarifleri", "Definitions"), tr("Tanılama", "Diagnostics")]
                    delegate: Button {
                        required property int index
                        required property string modelData
                        objectName: "nav" + index
                        text: modelData
                        Layout.fillWidth: true
                        implicitHeight: 44
                        Accessible.name: text
                        Accessible.selected: win.page === index
                        contentItem: Text { text: parent.text; color: win.page === index ? accent : secondary; font: parent.font; verticalAlignment: Text.AlignVCenter; leftPadding: 9 }
                        background: Rectangle { color: win.page === index || parent.hovered ? surface : "transparent"; radius: 8; border.width: parent.activeFocus ? 2 : 0; border.color: accent }
                        onClicked: win.page = index
                    }
                }
                Item { Layout.fillHeight: true }
                Label { text: tr("Ana sistem", "Host system"); color: secondary; font.pixelSize: 12 }
                Label { text: backend.host.name || "Linux"; color: ink; Layout.fillWidth: true; wrapMode: Text.Wrap; textFormat: Text.PlainText; font.pixelSize: 12 }
                Label { text: backend.runtime + (backend.host.rootless ? " · rootless" : ""); color: accent; font.pixelSize: 12 }
                Label { text: backend.host.ready ? tr("Hazır", "Ready") : tr("Kurulum gerekli", "Setup required"); color: secondary; font.pixelSize: 12 }
            }
        }

        StackLayout {
            id: pages
            Layout.fillWidth: true
            Layout.fillHeight: true
            currentIndex: win.page

            Item {
                ColumnLayout {
                    anchors.fill: parent
                    anchors.margins: 24
                    spacing: 18
                    RowLayout {
                        Layout.fillWidth: true
                        ColumnLayout {
                            Layout.fillWidth: true
                            Heading { text: tr("Ortamlar", "Environments") }
                            Hint { text: tr("Farklı dağıtımlar, aynı masaüstü.", "Different distributions, one desktop.") }
                        }
                        ActionButton { text: tr("Yenile", "Refresh"); enabled: !backend.busy && !backend.refreshing; onClicked: backend.refresh() }
                        ActionButton { objectName: "newEnvironment"; text: tr("+ Yeni ortam", "+ New environment"); primary: true; enabled: backend.host.ready && !backend.busy && !backend.refreshing; onClicked: win.openCreate(0) }
                    }
                    Hint {
                        visible: !backend.host.ready
                        text: tr("Başlamak için Kurulum ekranında Distrobox ve motor erişimini hazırla.", "Prepare Distrobox and engine access on the Setup page.")
                    }
                    RowLayout {
                        Layout.fillWidth: true
                        Layout.fillHeight: true
                        spacing: 18
                        ListView {
                            id: environments
                            objectName: "environmentList"
                            Layout.preferredWidth: win.width > 1000 ? 270 : 210
                            Layout.fillHeight: true
                            model: backend.containers
                            spacing: 9
                            clip: true
                            ScrollBar.vertical: ScrollBar {}
                            delegate: ItemDelegate {
                                required property var modelData
                                width: ListView.view.width
                                height: 83
                                Accessible.name: modelData.name
                                Accessible.selected: backend.selected.name === modelData.name
                                background: Rectangle { radius: 10; color: backend.selected.name === modelData.name ? soft : surface; border.color: backend.selected.name === modelData.name ? accent : line }
                                contentItem: Column {
                                    spacing: 5
                                    Label { width: parent.width; text: modelData.name; color: ink; elide: Text.ElideRight; font.weight: Font.Medium; textFormat: Text.PlainText }
                                    Label { width: parent.width; text: modelData.distro; color: secondary; elide: Text.ElideRight; font.pixelSize: 12; textFormat: Text.PlainText }
                                    Label { text: modelData.running ? tr("● Çalışıyor", "● Running") : tr("○ Durduruldu", "○ Stopped"); color: modelData.running ? accent : secondary; font.pixelSize: 12 }
                                }
                                onClicked: backend.selectContainer(modelData.name)
                            }
                            Label { anchors.centerIn: parent; visible: backend.containers.length === 0; text: backend.refreshing ? tr("Denetleniyor…", "Checking…") : tr("Henüz ortam yok", "No environments yet"); color: secondary; width: parent.width; horizontalAlignment: Text.AlignHCenter; wrapMode: Text.Wrap }
                        }
                        Panel {
                            Layout.fillWidth: true
                            Layout.fillHeight: true
                            visible: win.hasSelection
                            ScrollView {
                                anchors.fill: parent
                                anchors.margins: 19
                                contentWidth: availableWidth
                                ColumnLayout {
                                    width: parent.width
                                    spacing: 15
                                    Label { text: backend.selected.name || ""; font.pixelSize: 20; font.weight: Font.Medium; color: ink; Layout.fillWidth: true; wrapMode: Text.Wrap; textFormat: Text.PlainText }
                                    Hint { text: backend.selected.running ? tr("Çalışıyor", "Running") : tr("Durduruldu", "Stopped"); color: accent }
                                    Flow {
                                        Layout.fillWidth: true
                                        Layout.preferredHeight: childrenRect.height
                                        spacing: 8
                                        ActionButton { objectName: "openTerminal"; text: tr("Terminal aç", "Open terminal"); primary: true; enabled: win.canOperate; onClicked: backend.openTerminal() }
                                        ActionButton { text: tr("Güncelle", "Update"); enabled: win.canOperate; onClicked: backend.containerAction("upgrade", "") }
                                        ActionButton { text: backend.selected.running ? tr("Durdur", "Stop") : tr("Başlat", "Start"); enabled: win.canOperate; onClicked: backend.containerAction(backend.selected.running ? "stop" : "start", "") }
                                        ActionButton { objectName: "exportDefinition"; text: tr("Tarifi dışa aktar", "Export definition"); enabled: win.hasSelection && !backend.busy && !backend.refreshing; onClicked: { if (backend.exportDefinition()) win.page = 5 } }
                                    }
                                    Rectangle { Layout.fillWidth: true; height: 1; color: line }
                                    Pair { label: tr("İmaj", "Image"); value: backend.selected.image || "" }
                                    Pair { label: tr("Ev dizini", "Home"); value: backend.selected.home || tr("Bu ortam için kayıt yok", "Not recorded for this environment") }
                                    Pair { label: tr("Motor", "Engine"); value: backend.runtime + (backend.host.rootless ? " · rootless" : "") }
                                    Hint { text: tr("Ayrı ev dizini ayarlarını düzenli tutar. Ana sistem dosyalarına erişimi engellemez.", "A separate home keeps configuration organized. Host files remain accessible.") }
                                    Rectangle { Layout.fillWidth: true; height: 1; color: line }
                                    Label { text: tr("Grafik uygulamalar", "Graphical applications"); color: ink; font.weight: Font.Medium }
                                    Hint { text: tr("Kurulu uygulamaları keşfet ve masaüstü menüne ekle.", "Discover installed applications and add them to your desktop menu.") }
                                    ActionButton { text: tr("Uygulamaları göster", "Show applications"); enabled: win.canOperate; onClicked: { win.page = 2; backend.discoverApps() } }
                                    Item { Layout.preferredHeight: 8 }
                                    RowLayout {
                                        Layout.fillWidth: true
                                        ActionButton { text: tr("Klonla", "Clone"); enabled: win.canOperate && !backend.selected.running; onClicked: { cloneError.text = ""; cloneName.text = backend.selected.name + "-copy"; cloneDialog.open() } }
                                        Item { Layout.fillWidth: true }
                                        ActionButton { objectName: "deleteEnvironment"; text: tr("Ortamı sil", "Delete"); destructive: true; enabled: win.canOperate; onClicked: { removeDialog.targetName = backend.selected.name; removeName.text = ""; removeError.text = ""; removeDialog.open() } }
                                    }
                                    Hint { visible: !!backend.selected.running; text: tr("Klonlamak için önce ortamı durdur.", "Stop the environment before cloning.") }
                                }
                            }
                        }
                        Item {
                            Layout.fillWidth: true
                            Layout.fillHeight: true
                            visible: !win.hasSelection
                            ColumnLayout {
                                anchors.centerIn: parent
                                width: parent.width
                                Heading { text: tr("İlk ortamını oluştur", "Create your first environment"); Layout.fillWidth: true; horizontalAlignment: Text.AlignHCenter }
                                Hint { text: tr("Dağıtım seç, ad ver ve kullanmaya başla.", "Choose a distribution, name it, and start."); horizontalAlignment: Text.AlignHCenter }
                            }
                        }
                    }
                }
            }

            Item {
                ColumnLayout {
                    anchors.fill: parent
                    anchors.margins: 24
                    spacing: 18
                    Heading { text: tr("Dağıtımlar", "Distributions") }
                    Hint { text: tr("Dağıtımı seç; sürümü ve geliştirme şablonunu oluşturma penceresinde belirle.", "Choose a distribution, then select a version and development template.") }
                    Hint { text: tr("Yerel mimari: ", "Native platform: ") + (backend.nativePlatform || tr("Otomatik", "Automatic")) + tr(" · Etiketler registry'de canlı doğrulanmaz.", " · Tags are not verified live in the registry.") }
                    ScrollView {
                        Layout.fillWidth: true
                        Layout.fillHeight: true
                        contentWidth: availableWidth
                        GridLayout {
                            width: parent.width
                            columns: 2
                            columnSpacing: 14
                            rowSpacing: 14
                            Repeater {
                                model: backend.catalog
                                delegate: Panel {
                                    required property var modelData
                                    required property int index
                                    Layout.fillWidth: true
                                    Layout.preferredHeight: 190
                                    ColumnLayout {
                                        anchors.fill: parent
                                        anchors.margins: 18
                                        spacing: 8
                                        Label { text: modelData.name; color: ink; font.pixelSize: 18; font.weight: Font.Medium }
                                        Hint { text: modelData.version + " · " + modelData.manager }
                                        Hint { text: modelData.image; Layout.fillHeight: true; font.pixelSize: 12; textFormat: Text.PlainText }
                                        ActionButton { text: tr("+ Ortam oluştur", "+ Create environment"); Layout.fillWidth: true; enabled: backend.host.ready && !backend.busy && !backend.refreshing; onClicked: win.openCreate(index) }
                                    }
                                }
                            }
                        }
                    }
                    Hint { text: tr("Özel imaj adresleri desteklenir. Farklı mimari emülasyonu bu sürümde yapılandırılmaz.", "Custom image addresses are supported. Cross-architecture emulation is not configured.") }
                }
            }

            Item {
                ColumnLayout {
                    anchors.fill: parent
                    anchors.margins: 24
                    spacing: 16
                    Heading { text: tr("Uygulamalar", "Applications") }
                    Hint { text: tr("Kısayollar kendi konteynerinde çalışır; ortam adı menüde korunur.", "Launchers run inside their container; the environment name stays in the menu.") }
                    RowLayout {
                        Layout.fillWidth: true
                        Choice {
                            model: backend.containers.map(function(c) { return c.name })
                            currentIndex: Math.max(0, backend.containers.findIndex(function(c) { return c.name === backend.selected.name }))
                            Layout.fillWidth: true
                            enabled: !backend.busy && !backend.refreshing
                            Accessible.name: tr("Uygulama ortamı", "Application environment")
                            onActivated: backend.selectContainer(backend.containers[currentIndex].name)
                        }
                        ActionButton { objectName: "scanApps"; text: tr("Uygulamaları tara", "Scan applications"); primary: true; enabled: win.canOperate; onClicked: backend.discoverApps() }
                    }
                    Hint { text: tr("Tarama, durdurulmuş ortamı başlatabilir. İlk açılış sorununda ortamı terminalden aç.", "Scanning may start a stopped environment. Complete first-run setup in its terminal if needed.") }
                    ListView {
                        Layout.fillWidth: true
                        Layout.fillHeight: true
                        model: backend.applications
                        spacing: 9
                        clip: true
                        ScrollBar.vertical: ScrollBar {}
                        delegate: Panel {
                            required property var modelData
                            width: ListView.view.width
                            height: 84
                            RowLayout {
                                anchors.fill: parent
                                anchors.margins: 14
                                ColumnLayout {
                                    Layout.fillWidth: true
                                    Label { text: modelData.name; color: ink; font.weight: Font.Medium; textFormat: Text.PlainText }
                                    Hint { text: modelData.path; elide: Text.ElideMiddle; wrapMode: Text.NoWrap; font.pixelSize: 12; textFormat: Text.PlainText }
                                }
                                ActionButton { text: modelData.exported ? tr("Menüden kaldır", "Remove launcher") : tr("Menüye ekle", "Add launcher"); enabled: win.canOperate; onClicked: backend.exportApp(modelData.path) }
                            }
                        }
                        Label { visible: backend.applications.length === 0; anchors.centerIn: parent; width: parent.width; color: secondary; horizontalAlignment: Text.AlignHCenter; wrapMode: Text.Wrap; text: tr("Bir ortam seç ve uygulamaları tara.", "Choose an environment and scan its applications.") }
                    }
                }
            }

            Item {
                ColumnLayout {
                    anchors.fill: parent
                    anchors.margins: 24
                    spacing: 16
                    Heading { text: tr("İşlemler", "Activity") }
                    Hint { text: tr("Terminal işleri için canlı çıktı terminalde görünür. Aşama ve sonuç burada izlenir.", "Live output for terminal jobs appears in the terminal. Track stages and results here.") }
                    ListView {
                        Layout.fillWidth: true
                        Layout.fillHeight: true
                        model: backend.jobs
                        spacing: 12
                        clip: true
                        ScrollBar.vertical: ScrollBar {}
                        delegate: Panel {
                            id: jobPanel
                            required property var modelData
                            property bool expanded: false
                            width: ListView.view.width
                            height: expanded ? 280 : 110
                            ColumnLayout {
                                anchors.fill: parent
                                anchors.margins: 15
                                spacing: 8
                                RowLayout {
                                    Layout.fillWidth: true
                                    Label { text: jobPanel.modelData.title; color: ink; Layout.fillWidth: true; elide: Text.ElideRight; textFormat: Text.PlainText }
                                    Label { text: jobPanel.modelData.state === "done" ? tr("Tamamlandı", "Done") : jobPanel.modelData.state === "running" ? tr("Sürüyor", "Running") : tr("Başarısız", "Failed"); color: jobPanel.modelData.state === "failed" ? danger : accent; font.pixelSize: 12 }
                                }
                                Hint { text: jobPanel.modelData.stage; textFormat: Text.PlainText }
                                CheckBox { text: tr("Ayrıntıları göster", "Show details"); checked: jobPanel.expanded; onToggled: jobPanel.expanded = checked }
                                ScrollView {
                                    Layout.fillWidth: true
                                    Layout.fillHeight: true
                                    visible: jobPanel.expanded
                                    TextArea { readOnly: true; text: jobPanel.modelData.log; color: ink; wrapMode: TextEdit.Wrap; font.family: "monospace"; font.pixelSize: 12; selectByMouse: true; textFormat: TextEdit.PlainText; background: Rectangle { color: base; radius: 6 } }
                                }
                            }
                        }
                        Label { visible: backend.jobs.length === 0; anchors.centerIn: parent; text: tr("Henüz işlem yok", "No activity yet"); color: secondary }
                    }
                }
            }

            Item {
                ScrollView {
                    anchors.fill: parent
                    anchors.margins: 24
                    contentWidth: availableWidth
                    ColumnLayout {
                        width: parent.width
                        spacing: 16
                        Heading { text: tr("Kurulum ve tercihler", "Setup and preferences") }
                        Hint { text: tr("Ana sistemi denetle, eksik bileşenleri kur ve motorunu seç.", "Check the host, install missing components, and choose your engine.") }
                        GridLayout {
                            columns: 2
                            Layout.fillWidth: true
                            columnSpacing: 16
                            Label { text: tr("Konteyner motoru", "Container engine"); color: secondary }
                            Choice { objectName: "runtimeChoice"; Layout.fillWidth: true; model: ["Podman", "Docker"]; currentIndex: backend.runtime === "podman" ? 0 : 1; enabled: !backend.busy; Accessible.name: tr("Konteyner motoru", "Container engine"); onActivated: backend.setPreference("runtime", currentIndex === 0 ? "podman" : "docker") }
                            Label { text: tr("Terminal", "Terminal"); color: secondary }
                            Choice {
                                Layout.fillWidth: true
                                property var terminals: ["auto", "konsole", "gnome-terminal", "kgx", "kitty", "alacritty", "foot", "xterm", "x-terminal-emulator"]
                                model: [tr("Otomatik", "Automatic"), "Konsole", "GNOME Terminal", "GNOME Console", "Kitty", "Alacritty", "Foot", "xterm", "x-terminal-emulator"]
                                currentIndex: terminals.indexOf(backend.terminal)
                                Accessible.name: tr("Tercih edilen terminal", "Preferred terminal")
                                onActivated: backend.setPreference("terminal", terminals[currentIndex])
                            }
                        }
                        Panel {
                            Layout.fillWidth: true
                            Layout.preferredHeight: 155
                            ColumnLayout {
                                anchors.fill: parent
                                anchors.margins: 17
                                spacing: 12
                                Pair { label: tr("Ana sistem", "Host"); value: backend.host.name || "Linux" }
                                Pair { label: "Distrobox"; value: backend.host.distrobox ? tr("Kurulu", "Installed") : tr("Eksik", "Missing") }
                                Pair { label: backend.runtime; value: backend.host.ready ? tr("Erişim hazır", "Access ready") : backend.host.motor ? tr("Erişim doğrulanamadı", "Access not verified") : tr("Eksik", "Missing") }
                                Pair { label: "Rootless"; value: backend.host.rootless ? tr("Doğrulandı", "Verified") : tr("Doğrulanmadı", "Not verified") }
                            }
                        }
                        Hint { text: backend.host.engineError || ""; color: danger; visible: text !== ""; textFormat: Text.PlainText }
                        Hint { text: backend.host.immutable ? tr("Bu sistemde dağıtımın özel kurulum yönergesi kullanılmalı.", "Use distribution-specific installation instructions on this system.") : tr("Kurulum, sistem paket yöneticisiyle terminalde yapılır. Paket listesi aşağıda görünür.", "Installation runs in your terminal using the system package manager. Review its plan below.") }
                        Label { text: tr("Kurulum planı", "Installation plan"); color: ink; font.weight: Font.Medium }
                        TextArea {
                            Layout.fillWidth: true
                            Layout.preferredHeight: 85
                            text: { backend.host; backend.runtime; return backend.installPreview() }
                            readOnly: true
                            selectByMouse: true
                            wrapMode: TextEdit.Wrap
                            font.family: "monospace"
                            font.pixelSize: 12
                            color: ink
                            textFormat: TextEdit.PlainText
                            background: Rectangle { color: surface; radius: 7; border.color: line }
                        }
                        RowLayout {
                            ActionButton { objectName: "installButton"; text: tr("Terminalde kur", "Install in terminal"); primary: true; enabled: !backend.busy && !backend.refreshing && !backend.host.immutable && backend.host.family !== "unknown" && (!backend.host.distrobox || (!backend.host.motor && backend.runtime === "podman")); onClicked: installDialog.open() }
                            ActionButton { text: tr("Yeniden denetle", "Check again"); enabled: !backend.busy && !backend.refreshing; onClicked: backend.refresh() }
                            ActionButton { text: tr("Resmi yönerge", "Official guide"); onClicked: backend.openDocumentation() }
                            ActionButton { text: tr("Tanılama", "Diagnostics"); onClicked: win.page = 6 }
                        }
                        Hint { text: tr("Yeni kurulum için Podman rootless önerilir. Docker seçeneği mevcut servis erişimini kullanır; grupları veya servisleri otomatik değiştirmez.", "Podman rootless is recommended. Docker uses existing daemon access; groups and services are not changed automatically.") }
                        Hint { text: tr("Distrobox ana sistemle entegredir; güvenlik sandbox'ı değildir.", "Distrobox integrates with the host; it is not a security sandbox.") }
                    }
                }
            }
            Item {
                ScrollView {
                    id: definitionsScroll
                    anchors.fill: parent
                    anchors.margins: 24
                    contentWidth: availableWidth
                    ColumnLayout {
                        width: definitionsScroll.availableWidth
                        spacing: 14
                        Heading { text: tr("Ortam tarifleri", "Environment definitions") }
                        Hint { text: tr("INI dosyasını aç veya metni yapıştır; incele, sonra seçili ortamı oluştur. Dosyadaki diğer ortamlar çalıştırılmaz.", "Open an INI file or paste its text, review it, then create the selected environment. Other entries are not executed.") }
                        Flow {
                            Layout.fillWidth: true
                            Layout.preferredHeight: childrenRect.height
                            spacing: 8
                            ActionButton { objectName: "openManifestFile"; text: tr("Dosya aç", "Open file"); onClicked: openManifestDialog.open() }
                            ActionButton { text: tr("Seçili ortamın tarifi", "Selected environment definition"); enabled: win.hasSelection && !backend.busy; onClicked: backend.exportDefinition() }
                            ActionButton { objectName: "copyManifest"; text: tr("Kopyala", "Copy"); enabled: manifestEditor.text.length > 0; onClicked: backend.copyText(manifestEditor.text) }
                            ActionButton { objectName: "saveManifest"; text: tr("Farklı kaydet", "Save as"); enabled: !backend.demo && backend.manifestEntries.length > 0; onClicked: saveManifestDialog.open() }
                        }
                        ScrollView {
                            Layout.fillWidth: true
                            Layout.preferredHeight: 205
                            TextArea {
                                id: manifestEditor
                                objectName: "manifestEditor"
                                property bool syncing: false
                                text: ""
                                placeholderText: "[python-work]\nimage=\"docker.io/library/ubuntu:24.04\"\nadditional_packages=\"git python3 python3-venv\"\nstart_now=true"
                                color: ink
                                font.family: "monospace"
                                font.pixelSize: 12
                                selectByMouse: true
                                wrapMode: TextEdit.Wrap
                                textFormat: TextEdit.PlainText
                                background: Rectangle { color: surface; radius: 7; border.color: line }
                                onTextChanged: if (!syncing) backend.editManifest(text)
                            }
                        }
                        Connections {
                            target: backend
                            function onManifestChanged() {
                                if (manifestEditor.text !== backend.manifestText) {
                                    manifestEditor.syncing = true
                                    manifestEditor.text = backend.manifestText
                                    manifestEditor.syncing = false
                                }
                            }
                        }
                        ActionButton { objectName: "reviewManifest"; text: tr("Tanımı incele", "Review definition"); primary: true; onClicked: backend.reviewManifest(manifestEditor.text) }
                        Hint { text: backend.manifestError; visible: text !== ""; color: danger; textFormat: Text.PlainText }
                        Choice {
                            id: manifestChoice
                            objectName: "manifestChoice"
                            Layout.fillWidth: true
                            visible: backend.manifestEntries.length > 0
                            model: backend.manifestEntries.map(function(e) { return e.name + " · " + e.image })
                            Accessible.name: tr("İçe aktarılacak ortam", "Environment to import")
                        }
                        TextArea {
                            objectName: "manifestPreview"
                            visible: backend.manifestEntries.length > 0
                            Layout.fillWidth: true
                            text: { backend.manifestEntries; backend.containers; backend.runtime; return backend.manifestPreview(manifestChoice.currentIndex) }
                            readOnly: true
                            selectByMouse: true
                            wrapMode: TextEdit.Wrap
                            textFormat: TextEdit.PlainText
                            font.family: "monospace"
                            font.pixelSize: 12
                            color: secondary
                            background: Rectangle { color: surface; radius: 7 }
                        }
                        ActionButton {
                            objectName: "importEnvironment"
                            visible: backend.manifestEntries.length > 0
                            text: tr("Seçili ortamı oluştur", "Create selected environment")
                            primary: true
                            enabled: { backend.manifestEntries; backend.containers; return backend.host.ready && !backend.busy && !backend.refreshing && backend.canImport(manifestChoice.currentIndex) }
                            onClicked: { if (backend.importEnvironment(manifestChoice.currentIndex)) win.page = 3 }
                        }
                        Hint { text: tr("Seçili motor kullanılır. Tarif; kişisel dosyaları ve sonradan yapılan değişiklikleri yedeklemez. Hook, root=true, replace=true ve gelişmiş seçenekler desteklenmez.", "Uses the selected engine. Definitions do not back up personal files or later changes. Hooks, root=true, replace=true and advanced options are unsupported.") }
                    }
                }
            }

            Item {
                ColumnLayout {
                    anchors.fill: parent
                    anchors.margins: 24
                    spacing: 14
                    Heading { text: tr("Tanılama", "Diagnostics") }
                    Hint { text: tr("Distrobox, motor ve terminal erişimini kontrol et. Sistem ayarları otomatik değiştirilmez.", "Check Distrobox, engine and terminal access. System settings are not changed automatically.") }
                    RowLayout {
                        ActionButton { text: tr("Yeniden denetle", "Check again"); primary: true; enabled: !backend.busy && !backend.refreshing; onClicked: backend.refresh() }
                        ActionButton { objectName: "copyDiagnostics"; text: tr("Raporu kopyala", "Copy report"); onClicked: backend.copyText(backend.diagnosticReport()) }
                        ActionButton { text: tr("Kuruluma git", "Go to Setup"); onClicked: win.page = 4 }
                    }
                    Hint { text: tr("Denetleniyor…", "Checking…"); visible: backend.refreshing }
                    ListView {
                        objectName: "diagnosticList"
                        Layout.fillWidth: true
                        Layout.fillHeight: true
                        model: backend.diagnostics
                        clip: true
                        spacing: 10
                        ScrollBar.vertical: ScrollBar {}
                        delegate: Panel {
                            required property var modelData
                            width: ListView.view.width
                            height: checkContent.implicitHeight + 30
                            ColumnLayout {
                                id: checkContent
                                anchors.left: parent.left
                                anchors.right: parent.right
                                anchors.top: parent.top
                                anchors.margins: 15
                                spacing: 8
                                Label { text: (modelData.status === "ok" ? "✓ " : modelData.status === "error" ? "! " : "• ") + modelData.title; color: modelData.status === "error" ? danger : accent; font.weight: Font.Medium; textFormat: Text.PlainText }
                                Hint { text: modelData.detail; textFormat: Text.PlainText }
                            }
                        }
                    }
                    Hint { text: tr("Raporu paylaşmadan önce hata çıktısındaki kişisel yolları incele.", "Review personal paths in error output before sharing the report.") }
                }
            }
        }
    }

    FileDialog {
        id: openManifestDialog
        title: win.tr("Ortam tanımını aç", "Open environment definition")
        nameFilters: ["Distrobox definitions (*.ini)", "All files (*)"]
        onAccepted: backend.loadManifestFile(selectedFile.toString())
    }
    FileDialog {
        id: saveManifestDialog
        title: win.tr("Ortam tanımını kaydet", "Save environment definition")
        fileMode: FileDialog.SaveFile
        defaultSuffix: "ini"
        nameFilters: ["Distrobox definitions (*.ini)"]
        onAccepted: backend.saveManifestFile(selectedFile.toString(), manifestEditor.text)
    }

    footer: Rectangle {
        color: surface
        border.color: line
        implicitHeight: backend.message !== "" ? 76 : 43
        ColumnLayout {
            anchors.fill: parent
            anchors.margins: 10
            spacing: 5
            RowLayout {
                Layout.fillWidth: true
                BusyIndicator { running: backend.busy || backend.refreshing; visible: running; implicitWidth: 22; implicitHeight: 22 }
                Label { text: backend.busy ? (backend.jobs[0] ? backend.jobs[0].stage : tr("İşlem sürüyor…", "Working…")) : backend.refreshing ? tr("Denetleniyor…", "Checking…") : backend.demo ? tr("Demo · sistem komutları çalıştırılmaz", "Demo · system commands are disabled") : backend.runtime; color: secondary; Layout.fillWidth: true; elide: Text.ElideRight; font.pixelSize: 12; textFormat: Text.PlainText }
                ActionButton { visible: backend.busy; text: tr("İşlemi göster", "View activity"); implicitHeight: 29; onClicked: win.page = 3 }
                ActionButton { visible: backend.busy; text: tr("İptal", "Cancel job"); destructive: true; implicitHeight: 29; onClicked: backend.cancelJob() }
                Label { text: "The Puppeteer · 0.2.0"; color: secondary; font.pixelSize: 11 }
            }
            Label { objectName: "statusMessage"; text: backend.message; visible: text !== ""; color: backend.messageError ? danger : accent; Layout.fillWidth: true; maximumLineCount: 2; wrapMode: Text.Wrap; elide: Text.ElideRight; textFormat: Text.PlainText; font.pixelSize: 12; Accessible.name: text }
        }
    }

    Dialog {
        id: createDialog
        objectName: "createDialog"
        parent: Overlay.overlay
        anchors.centerIn: parent
        width: 545
        height: Math.min(implicitHeight, win.height - 24)
        modal: true
        title: tr("Yeni ortam", "New environment")
        background: Rectangle { color: surface; radius: 12; border.color: line }
        contentItem: ScrollView {
            id: createScroll
            implicitHeight: createForm.implicitHeight
            contentWidth: availableWidth
            ColumnLayout {
            id: createForm
            width: createScroll.availableWidth
            spacing: 11
            RowLayout {
                Layout.fillWidth: true
                ColumnLayout {
                    Layout.fillWidth: true
                    Label { text: tr("Dağıtım", "Distribution"); color: secondary }
                    Choice {
                        id: distroChoice
                        objectName: "distroChoice"
                        Layout.fillWidth: true
                        model: backend.catalog.map(function(d) { return d.name })
                        onActivated: { versionChoice.currentIndex = 0; imageField.text = backend.catalog[currentIndex].versions[0].image }
                        Accessible.name: tr("Dağıtım", "Distribution")
                    }
                }
                ColumnLayout {
                    Layout.fillWidth: true
                    Label { text: tr("Ortam adı", "Environment name"); color: secondary }
                    Field { id: nameField; objectName: "createName"; Layout.fillWidth: true; maximumLength: 63; Accessible.name: tr("Ortam adı", "Environment name") }
                }
            }
            RowLayout {
                Layout.fillWidth: true
                ColumnLayout {
                    Layout.fillWidth: true
                    Label { text: tr("Sürüm", "Version"); color: secondary }
                    Choice { id: versionChoice; objectName: "versionChoice"; Layout.fillWidth: true; model: backend.catalog[distroChoice.currentIndex].versions.map(function(v) { return v.label }); onActivated: imageField.text = backend.catalog[distroChoice.currentIndex].versions[currentIndex].image; Accessible.name: tr("İmaj sürümü", "Image version") }
                }
                ColumnLayout {
                    Layout.fillWidth: true
                    Label { text: tr("Geliştirme şablonu", "Development template"); color: secondary }
                    Choice { id: templateChoice; objectName: "templateChoice"; Layout.fillWidth: true; model: backend.templates.map(function(t) { return backend.language === "en" ? t.en : t.tr }); Accessible.name: tr("Geliştirme şablonu", "Development template") }
                }
            }
            Label { text: tr("İmaj ve sürüm", "Image and version"); color: secondary }
            Field { id: imageField; objectName: "imageField"; Layout.fillWidth: true; Accessible.name: tr("İmaj adresi", "Image address") }
            Hint { text: tr("Mimari: ", "Platform: ") + (backend.nativePlatform || tr("Otomatik", "Automatic")); font.pixelSize: 12 }
            CheckBox { id: ownHome; text: tr("Ortama özel ev dizini", "Separate home directory"); checked: true }
            Hint { text: ownHome.checked ? backend.homePreview(nameField.text) : tr("Ana sistem ev dizini kullanılacak.", "The host home directory will be used."); font.pixelSize: 12; textFormat: Text.PlainText }
            Hint { text: tr("Ayrı ev dizini ana sistem dosyalarına erişimi engellemez.", "A separate home does not restrict access to host files."); font.pixelSize: 12 }
            Label { text: tr("Ek paketler (boşlukla ayır)", "Additional packages (space separated)"); color: secondary }
            Field { id: extraPackages; objectName: "extraPackages"; Layout.fillWidth: true; placeholderText: "git cmake"; Accessible.name: tr("Ek paketler", "Additional packages") }
            Hint { text: tr("Kurulacak paketler: ", "Packages to install: ") + backend.packagePreview(backend.templates[templateChoice.currentIndex].id, imageField.text, extraPackages.text); textFormat: Text.PlainText; font.pixelSize: 12 }
            CheckBox { id: nvidia; text: tr("NVIDIA sürücü entegrasyonu (uyumlu ana sistemde)", "NVIDIA driver integration (compatible hosts)") }
            ScrollView {
                Layout.fillWidth: true
                Layout.preferredHeight: 93
                TextArea {
                    objectName: "profilePreview"
                    text: { backend.containers; return backend.profilePreview(nameField.text, imageField.text, ownHome.checked, backend.templates[templateChoice.currentIndex].id, extraPackages.text, nvidia.checked) }
                    readOnly: true
                    wrapMode: TextEdit.Wrap
                    font.family: "monospace"
                    font.pixelSize: 12
                    color: secondary
                    textFormat: TextEdit.PlainText
                    background: Rectangle { color: base; radius: 6 }
                }
            }
            Label { id: createError; color: danger; visible: text !== ""; Layout.fillWidth: true; wrapMode: Text.Wrap; textFormat: Text.PlainText }
            }
        }
        footer: Item {
            implicitHeight: 56
            RowLayout {
                anchors.fill: parent
                anchors.margins: 12
                Item { Layout.fillWidth: true }
                ActionButton { text: tr("Vazgeç", "Cancel"); onClicked: createDialog.close() }
                ActionButton { objectName: "confirmCreate"; text: tr("Oluştur ve hazırla", "Create and prepare"); primary: true; enabled: !backend.busy && !backend.refreshing; onClicked: { if (backend.createProfile(nameField.text, imageField.text, ownHome.checked, backend.templates[templateChoice.currentIndex].id, extraPackages.text, nvidia.checked)) createDialog.close(); else createError.text = backend.message } }
            }
        }
    }

    Dialog {
        id: cloneDialog
        parent: Overlay.overlay
        anchors.centerIn: parent
        width: 460
        modal: true
        title: tr("Ortamı klonla", "Clone environment")
        background: Rectangle { color: surface; radius: 12; border.color: line }
        contentItem: ColumnLayout {
            spacing: 14
            Hint { text: tr("Kaynak: ", "Source: ") + (backend.selected.name || ""); textFormat: Text.PlainText }
            Field { id: cloneName; Layout.fillWidth: true; maximumLength: 63; Accessible.name: tr("Klon adı", "Clone name") }
            CheckBox { id: cloneHome; text: tr("Klon için ayrı ev dizini", "Separate home for the clone"); checked: true }
            Hint { text: tr("Klonlama, ev dizininin tam yedeğini oluşturmaz.", "Cloning does not back up the complete home directory.") }
            Label { id: cloneError; color: danger; visible: text !== ""; Layout.fillWidth: true; wrapMode: Text.Wrap; textFormat: Text.PlainText }
            RowLayout {
                Layout.fillWidth: true
                Item { Layout.fillWidth: true }
                ActionButton { text: tr("Vazgeç", "Cancel"); onClicked: cloneDialog.close() }
                ActionButton { text: tr("Klonla", "Clone"); primary: true; enabled: !backend.busy && !backend.refreshing; onClicked: { if (backend.cloneContainer(cloneName.text, cloneHome.checked)) cloneDialog.close(); else cloneError.text = backend.message } }
            }
        }
    }

    Dialog {
        id: removeDialog
        objectName: "removeDialog"
        property string targetName: ""
        parent: Overlay.overlay
        anchors.centerIn: parent
        width: 470
        modal: true
        title: tr("Ortamı sil", "Delete environment")
        background: Rectangle { color: surface; radius: 12; border.color: line }
        contentItem: ColumnLayout {
            spacing: 14
            Hint { text: tr("Konteynerdeki kurulu paketler silinir. Ev dizini ve imaj korunur. Yalnızca bu oturumda keşfedilmiş menü kısayolları temizlenir.", "Installed container packages are removed. Home and image are preserved. Only launchers discovered in this session are cleaned.") }
            Label { text: tr("Onay için ortam adını yaz: ", "Type the name to confirm: ") + removeDialog.targetName; color: ink; Layout.fillWidth: true; wrapMode: Text.Wrap; textFormat: Text.PlainText }
            Field { id: removeName; objectName: "deleteConfirmation"; Layout.fillWidth: true; Accessible.name: tr("Silme onayı", "Deletion confirmation") }
            Label { id: removeError; color: danger; visible: text !== ""; Layout.fillWidth: true; wrapMode: Text.Wrap; textFormat: Text.PlainText }
            RowLayout {
                Layout.fillWidth: true
                Item { Layout.fillWidth: true }
                ActionButton { text: tr("Vazgeç", "Cancel"); onClicked: removeDialog.close() }
                ActionButton { objectName: "confirmDelete"; text: tr("Ortamı sil", "Delete environment"); destructive: true; enabled: removeName.text === removeDialog.targetName && !backend.busy && !backend.refreshing; onClicked: { if (backend.containerAction("remove", removeName.text)) removeDialog.close(); else removeError.text = backend.message } }
            }
        }
    }

    Dialog {
        id: installDialog
        parent: Overlay.overlay
        anchors.centerIn: parent
        width: 520
        modal: true
        title: tr("Kurulum planını uygula", "Apply installation plan")
        background: Rectangle { color: surface; radius: 12; border.color: line }
        contentItem: ColumnLayout {
            spacing: 14
            Hint { text: tr("Aşağıdaki işlem terminalde açılacak. Paket yöneticisi onayını ve sudo parolasını orada girebilirsin.", "This operation opens in a terminal. Review the package manager prompt and enter your sudo password there.") }
            TextArea { text: backend.installPreview(); readOnly: true; Layout.fillWidth: true; wrapMode: TextEdit.Wrap; color: ink; font.family: "monospace"; font.pixelSize: 12; textFormat: TextEdit.PlainText }
            RowLayout {
                Layout.fillWidth: true
                Item { Layout.fillWidth: true }
                ActionButton { text: tr("Vazgeç", "Cancel"); onClicked: installDialog.close() }
                ActionButton { text: tr("Terminalde başlat", "Start in terminal"); primary: true; onClicked: { if (backend.installDependencies()) installDialog.close() } }
            }
        }
    }

    Shortcut { sequence: "Ctrl+N"; enabled: backend.host.ready && !backend.busy; onActivated: win.openCreate(0) }
    Shortcut { sequence: "Ctrl+R"; enabled: !backend.busy; onActivated: backend.refresh() }

    Dialog {
        id: closeBusyDialog
        parent: Overlay.overlay
        anchors.centerIn: parent
        width: 450
        modal: true
        title: tr("İşlem sürüyor", "An operation is running")
        background: Rectangle { color: surface; radius: 12; border.color: line }
        contentItem: ColumnLayout {
            spacing: 14
            Hint { text: tr("Kapatmadan önce işlemi tamamla veya iptal et. İptal, tamamlanan değişiklikleri geri almaz.", "Finish or cancel the operation before closing. Cancellation does not undo completed changes.") }
            RowLayout {
                ActionButton { text: tr("İşlemi izle", "View activity"); onClicked: { win.page = 3; closeBusyDialog.close() } }
                ActionButton { text: tr("İptal iste", "Request cancellation"); destructive: true; onClicked: { backend.cancelJob(); closeBusyDialog.close() } }
            }
        }
    }
}

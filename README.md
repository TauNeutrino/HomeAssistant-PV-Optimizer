# PV Optimizer - Home Assistant Custom Integration

[![Version](https://img.shields.io/badge/version-0.2.0-blue.svg)](CHANGELOG.md)
[![Home Assistant](https://img.shields.io/badge/Home%20Assistant-2023.1+-blue.svg)](https://www.home-assistant.io/)

Eine intelligente Home Assistant Custom Integration zur Optimierung des PV-Eigenverbrauchs durch automatische Steuerung von Haushaltsgeräten basierend auf PV-Überschuss.

## 🎯 Funktionsweise

Der PV Optimizer maximiert den Eigenverbrauch von selbst erzeugtem Solarstrom, indem er Geräte automatisch aktiviert, wenn ein Leistungsüberschuss vorhanden ist. Die Integration verwendet einen prioritätsbasierten Knapsack-Algorithmus, um die optimale Kombination von Geräten zu finden, die den verfügbaren PV-Überschuss am besten nutzt.

### Kernkonzepte

- **PV-Überschuss**: Differenz zwischen erzeugter und verbrauchter Leistung
- **Prioritätsbasiert**: Geräte mit höherer Priorität (niedrigere Zahl) werden zuerst aktiviert
- **Power Budget**: Verfügbare Leistung für die Optimierung
- **Device Locking**: Verhindert zu häufiges Schalten durch Min-Ein/Aus-Zeiten
- **Gleitendes Fenster**: Mittelwertbildung über konfigurierbare Zeitspanne

## ✨ Features

### Version 0.2.0 - Vollständige UI-Verwaltung

- ✅ **Grafische Geräteverwaltung**: Hinzufügen, Bearbeiten und Löschen von Geräten direkt über die UI
- ✅ **Zwei Gerätetypen**: Switch (Ein/Aus) und Numeric (Wertebereich)
- ✅ **Prioritätssteuerung**: Definiere welche Geräte bei begrenztem Überschuss Vorrang haben
- ✅ **Min Ein/Aus-Zeiten**: Verhindere zu häufiges Schalten
- ✅ **Manuelle Intervention**: Automatische Erkennung und Respektierung manueller Änderungen
- ✅ **Echtzeitüberwachung**: Live-Status, Leistungsmessung und Lock-Status
- ✅ **Responsive Design**: Funktioniert auf Desktop und Mobile

## 📦 Installation

### HACS (Empfohlen)

1. Öffne HACS in Home Assistant
2. Gehe zu "Integrationen"
3. Klicke auf die drei Punkte (oben rechts) → "Benutzerdefinierte Repositories"
4. Füge die Repository-URL hinzu: `https://github.com/yourusername/ha-pv-optimizer`
5. Wähle Kategorie "Integration"
6. Suche nach "PV Optimizer" und installiere

### Manuelle Installation

1. Kopiere den `custom_components/pv_optimizer` Ordner in dein `config/custom_components` Verzeichnis
2. Starte Home Assistant neu

## ⚙️ Einrichtung

### Schritt 1: Integration hinzufügen

1. Gehe zu **Einstellungen** → **Geräte & Dienste** → **Integration hinzufügen**
2. Suche nach "PV Optimizer"
3. Konfiguriere die globalen Parameter:
   - **PV Surplus Sensor**: Der Sensor, der deinen Netz-Einspeisewert liefert (negativ = Überschuss)
   - **Sliding Window Size**: Zeitfenster für Leistungsmittelwertbildung (Standard: 5 Minuten)
   - **Optimization Cycle Time**: Wie oft der Optimizer läuft (Standard: 60 Sekunden)

### Schritt 2: Sidebar-Panel nutzen

Nach der Installation findest du einen neuen **"PV Optimizer"** Eintrag in der linken Sidebar.

### Schritt 3: Geräte hinzufügen

#### Switch-Type Gerät (z.B. Heizstab, Waschmaschine)

1. Öffne das PV Optimizer Panel
2. Klicke auf **"➕ Add Device"**
3. Fülle das Formular aus:

```
Name: Heizstab Warmwasser
Type: Switch
Priority: 1 (höchste Priorität)
Power: 2000 W
Switch Entity: switch.heater_rod
Optimization Enabled: ✓
Min On Time: 30 minutes
Min Off Time: 20 minutes
```

#### Numeric-Type Gerät (z.B. Wärmepumpe)

1. Öffne das PV Optimizer Panel
2. Klicke auf **"➕ Add Device"**
3. Wähle Type: **Numeric**
4. Füge Numeric Targets hinzu:

```
Name: Wärmepumpe Warmwasser
Type: Numeric
Priority: 1
Power: 2300 W

Numeric Targets:
  Target 1:
    Entity: number.heat_pump_dhw_target_temp
    Activated Value: 55
    Deactivated Value: 45
  
  Target 2:
    Entity: number.heat_pump_dhw_hysteresis
    Activated Value: 5
    Deactivated Value: 10
```

## 📊 Monitoring

Die Integration erstellt automatisch Entities für jedes Gerät:

### Sensors (pro Gerät)
- `sensor.pvo_{device_name}_locked` - Lock-Status
- `sensor.pvo_{device_name}_measured_power_avg` - Gemittelte Leistung
- `sensor.pvo_{device_name}_last_target_state` - Letzter Zielzustand vom Optimizer
- `sensor.pvo_{device_name}_contribution_to_budget` - Beitrag zum Power Budget

### Configuration Entities (pro Gerät)
- `number.pvo_{device_name}_priority` - Priorität dynamisch ändern
- `number.pvo_{device_name}_min_on_time` - Min-Ein-Zeit anpassen
- `number.pvo_{device_name}_min_off_time` - Min-Aus-Zeit anpassen
- `switch.pvo_{device_name}_optimization_enabled` - Optimierung ein/ausschalten

### Controller Sensors (global)
- `sensor.pv_optimizer_power_budget` - Aktuelles Power Budget
- `sensor.pv_optimizer_averaged_surplus` - Gemittelter PV-Überschuss

## 🔧 Erweiterte Konfiguration

### Power Threshold

Der Power Threshold wird verwendet, um zu bestimmen, ob ein Gerät als "EIN" gilt, wenn ein `measured_power_entity_id` konfiguriert ist:

```
Power Threshold: 100 W
```

Wenn die gemessene Leistung > 100W ist, gilt das Gerät als eingeschaltet.

### Invert Switch Logic

Manche Geräte haben invertierte Logik (Ein = Aus, Aus = Ein):

```
☑ Invert Switch Logic
```

### Gemessene Leistung

Für präzisere Optimierung kannst du einen Power Sensor angeben:

```
Measured Power Entity: sensor.washing_machine_power
```

Der Optimizer verwendet dann die tatsächlich gemessene Leistung statt des nominalen Werts.

## 🎨 UI-Features

### Device Management
- **Add**: Vollständiges Formular mit Validierung
- **Edit**: Alle Parameter änderbar (außer Name)
- **Delete**: Mit Bestätigungsdialog

### Visual Feedback
- 🟢 Grünes Icon: Optimierung aktiviert
- 🔴 Rotes Icon: Optimierung deaktiviert
- Status-Indikator: Verbindungsstatus zur Websocket-API
- Live-Updates: Automatische Aktualisierung der Gerätezustände

### Form Validation
- Pflichtfelder werden markiert
- Duplicate Name Detection
- Type-spezifische Validierung
- Hilfetext für jeden Parameter

## 🔍 Beispiel-Szenarien

### Scenario 1: Einfacher Heizstab

**Situation**: Du hast einen 2kW Heizstab, der Warmwasser aufheizen soll, wenn Überschuss vorhanden ist.

**Konfiguration**:
```
Name: Warmwasser Heizstab
Type: Switch
Priority: 1
Power: 2000
Switch Entity: switch.water_heater
Min On Time: 60  # Mindestens 1h laufen lassen
Min Off Time: 30  # Mindestens 30min Pause
```

### Scenario 2: Mehrere Geräte mit Prioritäten

**Situation**: Verschiedene Geräte sollen nacheinander aktiviert werden.

```
Gerät 1 - Wärmepumpe (höchste Priorität):
  Priority: 1
  Power: 2300 W

Gerät 2 - Waschmaschine:
  Priority: 2
  Power: 800 W

Gerät 3 - Trockenschrank:
  Priority: 3
  Power: 350 W
```

**Verhalten**:
- Bei 2500W Überschuss: Wärmepumpe wird aktiviert
- Bei 3500W Überschuss: Wärmepumpe + Waschmaschine
- Bei 4000W Überschuss: Alle drei Geräte

### Scenario 3: Wärmepumpe mit mehreren Parametern

**Situation**: Eine Wärmepumpe soll bei Überschuss aggressivere Zieltemperaturen verwenden.

```
Name: Wärmepumpe Optimiert
Type: Numeric
Priority: 1
Power: 2300

Target 1 - Warmwasser Zieltemperatur:
  Entity: number.luxtronik_dhw_target_temp
  Activated: 55°C
  Deactivated: 45°C

Target 2 - Warmwasser Hysterese:
  Entity: number.luxtronik_dhw_hysteresis
  Activated: 5°C  (engeres Band = häufigeres Heizen)
  Deactivated: 10°C

Target 3 - Heizung Korrektur:
  Entity: number.luxtronik_heating_correction
  Activated: 1°C
  Deactivated: 0°C
```

## 🐛 Troubleshooting

### Device wird nicht geschaltet

1. **Prüfe Lock-Status**: `sensor.pvo_{device}_locked`
2. **Prüfe Optimization Enabled**: `switch.pvo_{device}_optimization_enabled`
3. **Prüfe Power Budget**: `sensor.pv_optimizer_power_budget`
4. **Prüfe Priorität**: Höhere Priorität = niedrigere Nummer

### Gerät schaltet zu häufig

- Erhöhe `Min On Time` und `Min Off Time`
- Erhöhe `Sliding Window Size` für stabilere Durchschnittswerte

### WebSocket Fehler im Panel

1. Hard-Refresh der Seite (Ctrl+F5)
2. Browser-Cache leeren
3. Home Assistant neu starten

### Geräte bleiben gesperrt

- Manuelle Änderungen werden als Intervention erkannt
- Stelle sicher, dass `pvo_last_target_state` mit aktuellem Status übereinstimmt
- Deaktiviere und aktiviere die Optimierung neu

## 📈 Performance

- **Optimierungszyklen**: Konfigurierbar (Standard: 60 Sekunden)
- **Overhead**: Minimal, nur während Optimierungszyklen
- **Recorder Impact**: Verwendet History für Glättung, aber effizient

## 🔮 Geplante Features

### Phase 2 (Core Improvements)
- [ ] Präzises Timestamp Tracking für Min-Zeiten
- [ ] Power Threshold Verwendung in is_on() Detection
- [ ] Globale Config Live-Bearbeitung

### Phase 3 (UX Enhancements)
- [ ] Visualisierung des Power Flows
- [ ] Historische Optimierungsdaten
- [ ] Device-Templates für häufige Geräte
- [ ] Import/Export von Device Configs
- [ ] Bulk Operations (mehrere Geräte gleichzeitig aktivieren)

## 🤝 Contributing

Contributions sind willkommen! Bitte:

1. Fork das Repository
2. Erstelle einen Feature Branch
3. Committe deine Änderungen
4. Push zum Branch
5. Erstelle einen Pull Request

## 📄 Lizenz

Dieses Projekt ist unter der MIT-Lizenz lizenziert.

## 🙏 Credits

Entwickelt für die intelligente Steuerung von Haushaltsgeräten basierend auf PV-Überschuss.

## 📞 Support

- **Issues**: [GitHub Issues](https://github.com/yourusername/ha-pv-optimizer/issues)
- **Discussions**: [GitHub Discussions](https://github.com/yourusername/ha-pv-optimizer/discussions)

---

**Version 0.2.0** - Vollständige UI-basierte Device-Verwaltung implementiert
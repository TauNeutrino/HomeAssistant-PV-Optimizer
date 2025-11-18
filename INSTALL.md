# PV Optimizer - Installation & Quick Start

## 🚀 Schnellstart-Anleitung

### Voraussetzungen

- Home Assistant 2023.1 oder neuer
- Ein PV-Überschuss-Sensor (z.B. von deinem Wechselrichter oder Smart Meter)
- Mindestens ein steuerbares Gerät (Switch oder Number Entity)

### Installation

1. **Integration installieren**
   - Kopiere den `pv_optimizer` Ordner nach `config/custom_components/`
   - Oder installiere über HACS (empfohlen)

2. **Home Assistant neu starten**

3. **Integration einrichten**
   - Gehe zu **Einstellungen** → **Geräte & Dienste**
   - Klicke auf **"+ Integration hinzufügen"**
   - Suche nach **"PV Optimizer"**
   - Konfiguriere die globalen Parameter:
     ```
     PV Surplus Sensor: sensor.my_grid_power
     Sliding Window: 5 Minuten
     Cycle Time: 60 Sekunden
     ```

4. **Panel öffnen**
   - In der linken Sidebar findest du nun **"PV Optimizer"**
   - Klicke darauf, um das Verwaltungspanel zu öffnen

### Erstes Gerät hinzufügen

#### Beispiel: Heizstab aktivieren bei Überschuss

1. Öffne das PV Optimizer Panel
2. Klicke auf **"➕ Add Device"**
3. Konfiguriere:
   ```
   Name: Heizstab Warmwasser
   Type: Switch
   Priority: 1
   Power: 2000
   Switch Entity: switch.water_heater
   ✓ Optimization Enabled
   Min On Time: 30
   Min Off Time: 20
   ```
4. Klicke **"Add Device"**

Das war's! Der Optimizer wird nun automatisch deinen Heizstab aktivieren, wenn mindestens 2000W PV-Überschuss vorhanden sind.

### Monitoring

Nach dem Hinzufügen eines Geräts werden automatisch folgende Entities erstellt:

**Sensoren**:
- `sensor.pvo_heizstab_warmwasser_locked` - Zeigt ob das Gerät gesperrt ist
- `sensor.pvo_heizstab_warmwasser_measured_power_avg` - Durchschnittliche Leistung
- `sensor.pvo_heizstab_warmwasser_last_target_state` - Letzter Optimizer-Status

**Steuerung**:
- `number.pvo_heizstab_warmwasser_priority` - Priorität anpassen (1-10)
- `number.pvo_heizstab_warmwasser_min_on_time` - Min-Ein-Zeit
- `number.pvo_heizstab_warmwasser_min_off_time` - Min-Aus-Zeit  
- `switch.pvo_heizstab_warmwasser_optimization_enabled` - Optimierung ein/aus

### Tipps für den Start

**Prioritäten richtig setzen**:
```
Priorität 1: Kritische Geräte (z.B. Warmwasser)
Priorität 2-3: Wichtige Geräte (z.B. Puffer laden)
Priorität 4-10: Nice-to-have (z.B. Trockner)
```

**Min-Zeiten anpassen**:
- Start mit konservativen Werten (30-60min)
- Bei zu häufigem Schalten erhöhen
- Bei zu wenig Optimierung reduzieren

**Sliding Window**:
- 5 Minuten = schnelle Reaktion, ggf. instabil
- 10 Minuten = guter Kompromiss
- 15+ Minuten = sehr stabil, langsame Reaktion

### Fehlerbehebung

**"WebSocket connection not available"**
- Aktualisiere die Seite (F5)
- Prüfe ob Home Assistant läuft
- Leere den Browser-Cache

**"Device not found"**
- Prüfe ob die Entity ID korrekt ist
- Prüfe ob das Gerät in Home Assistant verfügbar ist
- Verwende Developer Tools → States zur Verifikation

**Gerät wird nicht geschaltet**
- Prüfe `sensor.pvo_{device}_locked`
- Prüfe `switch.pvo_{device}_optimization_enabled`
- Prüfe `sensor.pv_optimizer_power_budget`
- Prüfe ob genug Überschuss vorhanden ist

### Nächste Schritte

1. **Weitere Geräte hinzufügen**: Optimiere mehr Verbraucher
2. **Prioritäten anpassen**: Feintuning der Reihenfolge
3. **Monitoring einrichten**: Erstelle Dashboards mit den Sensor-Daten
4. **Automationen ergänzen**: Zusätzliche Logik für spezielle Fälle

### Support

- Dokumentation: [README.md](README.md)
- Changelog: [CHANGELOG.md](CHANGELOG.md)
- GitHub Issues: Für Bug-Reports und Feature-Requests

---

**Viel Erfolg beim Maximieren deines PV-Eigenverbrauchs! ☀️**
[![hacs_badge](https://img.shields.io/badge/HACS-Custom-orange.svg)](https://github.com/custom-components/hacs)

# PV Optimizer - Simulation Feature

## 🧪 Simulation Mode (v1.1.0+)

### Was ist Simulation Mode?

Der Simulation Mode ermöglicht es, die Optimierungslogik für bestimmte Geräte **ohne physische Steuerung** zu testen. Die Integration führt parallel zur echten Optimierung eine Simulation durch und zeigt die Ergebnisse im Frontend an.

### Warum Simulation?

**Hauptgründe:**
1. **Neue Geräte testen** - Bevor ein echtes Gerät gekauft/installiert wird
2. **Konfiguration optimieren** - Prioritäten und Parameter ohne Risiko ausprobieren
3. **Vergleiche anstellen** - Real vs. "Was-wäre-wenn"-Szenarien
4. **Schulung/Demonstration** - Zeigen wie die Optimierung funktioniert

### Funktionsweise

#### Zwei parallele Optimierungen

```
┌─────────────────────────────────────────┐
│         PV Optimizer Coordinator         │
├─────────────────────────────────────────┤
│                                          │
│  1. Real Optimization                    │
│     - Geräte mit optimization_enabled    │
│     - Budget: Surplus + Real Running     │
│     - Knapsack Algorithmus               │
│     → Physische Gerätesteuerung ✅       │
│                                          │
│  2. Simulation                           │
│     - Geräte mit simulation_active       │
│     - Budget: Surplus + Sim Running      │
│     - Knapsack Algorithmus               │
│     → Nur Anzeige, KEINE Steuerung ❌    │
│                                          │
└─────────────────────────────────────────┘
```

#### Budget-Berechnung

**Real Optimization:**
```
Budget = PV-Überschuss + Leistung(laufende Real-Geräte)
```

**Simulation:**
```
Budget = PV-Überschuss + Leistung(laufende Sim-Geräte)
```

> **Wichtig:** Getrennte Budgets! Simulation und Real beeinflussen sich nicht gegenseitig.

### Schritt-für-Schritt Anleitung

#### 1. Simulation aktivieren für bestehendes Gerät

**Via Config Flow:**
```
Einstellungen → Geräte & Dienste → PV Optimizer → Konfigurieren
→ Geräte verwalten → Geräteliste anzeigen
→ Gerät auswählen → Bearbeiten
→ ✓ Simulation aktiviert (ankreuzen)
→ Speichern
```

**Via Entity:**
```
switch.pvo_[gerätename]_simulation_active einschalten
```

#### 2. Neues Simulations-Gerät hinzufügen

```
Einstellungen → Geräte & Dienste → PV Optimizer → Konfigurieren
→ Geräte verwalten → Schalter-Gerät hinzufügen

Konfiguration:
- Name: Test Waschmaschine
- Typ: Switch
- Priorität: 3
- Leistung: 800W
- Switch Entity: switch.dummy_washing_machine (oder beliebig)
- ☐ Optimierung aktiviert (aus)
- ✓ Simulation aktiviert (an)
```

> **Tipp:** Für reine Simulation kann eine Dummy-Switch-Entity verwendet werden!

#### 3. Ergebnisse ansehen

**Panel öffnen:**
```
Sidebar → PV Optimizer
```

**Zwei Ansichten verfügbar:**

**A) Separate Karten (Standard)**
```
┌─────────────────────────────────────┐
│ ⚡ Real Optimization                 │
│ ───────────────────────────────────  │
│ Aktive Geräte: 2                     │
│ Gesamtleistung: 4300W                │
│ Budget verfügbar: 5000W              │
│ Budget genutzt: 86%                  │
│                                      │
│ ✅ Heizstab Warmwasser (2000W)      │
│ ✅ Wärmepumpe (2300W)                │
└─────────────────────────────────────┘

┌─────────────────────────────────────┐
│ 🧪 Simulation                        │
│ ───────────────────────────────────  │
│ Aktive Geräte: 1                     │
│ Gesamtleistung: 800W                 │
│ Budget verfügbar: 5000W              │
│ Budget genutzt: 16%                  │
│                                      │
│ ✅ Test Waschmaschine (800W)        │
└─────────────────────────────────────┘
```

**B) Vergleichstabelle**

Klicke auf "Show Comparison Table" Button:

```
┌────────────────────────────────────────────────────┐
│ Real vs Simulation Comparison                      │
├────────────────────────────────────────────────────┤
│ Device              │ Power │ Real │ Simulation    │
├─────────────────────┼───────┼──────┼──────────────┤
│ Heizstab Warmwasser │ 2000W │ ✅   │ ❌           │
│ Wärmepumpe          │ 2300W │ ✅   │ ❌           │
│ Test Waschmaschine  │ 800W  │ ❌   │ ✅           │
└────────────────────────────────────────────────────┘
```

### Anwendungsbeispiele

#### Beispiel 1: Waschmaschine hinzufügen?

**Szenario:** Überlegen ob eine Waschmaschine sinnvoll steuerbar wäre.

**Vorgehen:**
```
1. Simulation-Gerät "Test Waschmaschine" erstellen
   - Priorität: 4 (nach wichtigen Geräten)
   - Leistung: 800W
   - simulation_active: ON

2. Über mehrere Tage beobachten:
   - Wie oft würde Waschmaschine aktiviert?
   - Passt in verfügbares Budget?
   - Stört andere Geräte?

3. Entscheidung:
   ✅ Ja → Echtes Gerät kaufen, optimization_enabled
   ❌ Nein → Simulation-Gerät löschen
```

#### Beispiel 2: Prioritäten optimieren

**Szenario:** Ist Priorität 2 oder 3 besser für die Wärmepumpe?

**Vorgehen:**
```
1. Echte Wärmepumpe:
   - Name: Wärmepumpe Real
   - Priorität: 2
   - optimization_enabled: ON
   - simulation_active: OFF

2. Simulations-Wärmepumpe:
   - Name: Wärmepumpe Test
   - Priorität: 3
   - optimization_enabled: OFF
   - simulation_active: ON

3. Vergleichstabelle anzeigen:
   → Welche Konfiguration aktiviert häufiger?
   → Welche nutzt Budget besser?

4. Beste Priorität auf Real übernehmen
```

#### Beispiel 3: Budget-Analyse

**Szenario:** Wie viele Geräte passen in typischen PV-Überschuss?

**Vorgehen:**
```
1. Alle geplanten Geräte als Simulation hinzufügen:
   - Pool-Pumpe (1500W) - Prio 5
   - E-Auto Laden (3000W) - Prio 6
   - Geschirrspüler (1200W) - Prio 4

2. Simulation über 1 Woche laufen lassen

3. Auswertung:
   - Welche Geräte aktiviert Simulation häufig?
   - Welche fast nie?
   - Gibt es Leistungsspitzen wo nichts passt?

4. Realistische Gerätekombination finden
```

### Entities für Monitoring

#### Pro Gerät (neu)

```
switch.pvo_[gerät]_simulation_active
  - Simulation für dieses Gerät aktivieren
  - Default: False
  - Icon: mdi:test-tube
```

#### Global (neu)

```
sensor.pv_optimizer_simulation_power_budget
  - Verfügbares Budget für Simulation
  - Unit: W
  - Attribute: surplus, running_power

sensor.pv_optimizer_simulation_ideal_devices
  - Anzahl Geräte in Simulation ideal state
  - Attribute:
    - devices: ["Gerät1", "Gerät2"]
    - device_details: [{name, power, priority}, ...]
    - total_power: Summe in W

sensor.pv_optimizer_real_ideal_devices
  - Anzahl Geräte in Real ideal state
  - Gleiche Attribute wie Simulation
```

### Automatisierungs-Beispiele

#### Benachrichtigung bei Simulation-Potenzial

```yaml
automation:
  - alias: "PV Optimizer: Simulation zeigt Potenzial"
    trigger:
      - platform: numeric_state
        entity_id: sensor.pv_optimizer_simulation_ideal_devices
        above: 2
        for:
          hours: 1
    condition:
      - condition: numeric_state
        entity_id: sensor.pv_optimizer_real_ideal_devices
        below: 1
    action:
      - service: notify.mobile_app
        data:
          message: >
            Simulation würde {{ states('sensor.pv_optimizer_simulation_ideal_devices') }} 
            Geräte aktivieren, aber Real nur {{ states('sensor.pv_optimizer_real_ideal_devices') }}.
            Überprüfe Konfiguration!
```

#### Automatischer Vergleichs-Report

```yaml
automation:
  - alias: "PV Optimizer: Täglicher Simulation Report"
    trigger:
      - platform: time
        at: "20:00:00"
    action:
      - service: notify.telegram
        data:
          message: >
            📊 PV Optimizer Report:
            
            Real: {{ state_attr('sensor.pv_optimizer_real_ideal_devices', 'total_power') }}W
            Sim: {{ state_attr('sensor.pv_optimizer_simulation_ideal_devices', 'total_power') }}W
            
            Real Geräte: {{ state_attr('sensor.pv_optimizer_real_ideal_devices', 'devices') | join(', ') }}
            Sim Geräte: {{ state_attr('sensor.pv_optimizer_simulation_ideal_devices', 'devices') | join(', ') }}
```

### Tipps & Best Practices

#### ✅ Do's

- **Realistische Leistungswerte** verwenden
- **Mehrere Tage testen** für aussagekräftige Ergebnisse
- **Vergleichstabelle nutzen** für direkte Analyse
- **Simulation nach Test deaktivieren** (Performance)

#### ❌ Don'ts

- **Nicht zu viele Sim-Geräte** gleichzeitig (max. 5-10)
- **Nicht auf Simulation verlassen** - Real-Test ist Gold-Standard
- **Nicht vergessen auszuschalten** nach Testphase
- **Lock-States ignorieren** - auch Simulation beachtet Locks

### Troubleshooting

#### Simulation zeigt keine Geräte

**Prüfen:**
1. `switch.pvo_[gerät]_simulation_active` ist ON?
2. Budget ausreichend? (`sensor.pv_optimizer_simulation_power_budget`)
3. Geräte gesperrt? (`sensor.pvo_[gerät]_locked`)
4. Priorität zu niedrig?

#### Simulation und Real zeigen gleiches

**Wahrscheinlich:**
- Beide Sets haben gleiche Geräte mit gleichen Prioritäten
- Budget für beide ausreichend
- **Lösung:** Unterschiedliche Geräte oder Prioritäten testen

#### Performance-Probleme

**Bei vielen Geräten:**
- Max. 10-15 Gesamt-Geräte (Real + Sim)
- Simulation zeitweise deaktivieren
- Cycle Time erhöhen (90-120s statt 60s)

### Einschränkungen

**Simulation berücksichtigt NICHT:**
- Tatsächliche Geräteverfügbarkeit
- Anlaufzeiten von Geräten
- Externe Faktoren (Wetter, Temperatur)
- Benutzerverhalten

**Simulation zeigt nur:**
- Optimierungs-Algorithmus-Ergebnis
- Budget-Berechnung
- Prioritäts-Logik

> **Wichtig:** Simulation ist ein Planungstool, kein Ersatz für Real-Tests!

### Weitere Ressourcen

- **Changelog:** [CHANGELOG.md](CHANGELOG.md) - Version 1.1.0
- **Beispiel-Konfigurationen:** [examples/simulation/](examples/simulation/)
- **Diskussionen:** GitHub Discussions
- **Feedback:** GitHub Issues mit Label "simulation"

---

**Version:** 1.1.0+
**Status:** ✅ Production Ready
**Backward Compatibility:** ✅ Vollständig kompatibel

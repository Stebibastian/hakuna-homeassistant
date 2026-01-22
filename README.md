# Hakuna Time Tracking Integration für Home Assistant

[![hacs_badge](https://img.shields.io/badge/HACS-Custom-41BDF5.svg)](https://github.com/hacs/integration)
[![GitHub Release](https://img.shields.io/github/v/release/Stebibastian/hakuna-homeassistant)](https://github.com/Stebibastian/hakuna-homeassistant/releases)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

[![Open your Home Assistant instance and open a repository inside the Home Assistant Community Store.](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=Stebibastian&repository=hakuna-homeassistant&category=integration)

Eine vollständige Home Assistant Integration für [Hakuna](https://www.hakuna.ch/) - die Schweizer Zeiterfassungs-Software.

## Features

### Sensoren
- **Überstunden** - Aktueller Überstunden-Stand (Format: `HH:MM`)
- **Resturlaub** - Verbleibende Urlaubstage
- **Genommener Urlaub** - Bereits genommene Urlaubstage
- **Timer Dauer** - Aktuelle Timer-Laufzeit
- **Timer Startzeit** - Wann der Timer gestartet wurde
- **Timer Projekt** - Zugewiesenes Projekt (optional)
- **Timer Aufgabe** - Zugewiesene Aufgabe (optional)

### Binary Sensoren
- **Eingestempelt** - `on` wenn ein Timer läuft, `off` wenn nicht

### Buttons
- **Timer starten** - Startet einen neuen Timer (mit Default-Task)
- **Timer stoppen** - Stoppt den Timer und erstellt einen Zeiteintrag
- **Timer abbrechen** - Bricht den Timer ab ohne Zeiteintrag
- **Daten aktualisieren** - Manuelles Refresh der Daten

## Installation

### HACS (empfohlen)

1. Öffne HACS in Home Assistant
2. Gehe zu "Integrationen"
3. Klicke auf die drei Punkte oben rechts → "Benutzerdefinierte Repositories"
4. Füge die Repository-URL hinzu und wähle "Integration"
5. Suche nach "Hakuna" und installiere es
6. Starte Home Assistant neu

### Manuelle Installation

1. Kopiere den Ordner `custom_components/hakuna` in dein Home Assistant `config/custom_components/` Verzeichnis
2. Starte Home Assistant neu

## Konfiguration

1. Gehe zu **Einstellungen → Geräte & Dienste → Integration hinzufügen**
2. Suche nach "Hakuna"
3. Gib deinen API-Token ein (findest du unter https://app.hakuna.ch/my_settings)

### Optionen

Nach der Einrichtung kannst du folgende Optionen anpassen:
- **Aktualisierungsintervall** - Wie oft die Daten abgefragt werden (Standard: 5 Minuten)

## API Token erstellen

1. Melde dich bei [Hakuna](https://app.hakuna.ch) an
2. Klicke auf deinen Namen unten links
3. Wähle "Meine Einstellungen" oder gehe direkt zu https://app.hakuna.ch/my_settings
4. Erstelle einen neuen Token

**Wichtig:** Behandle deinen Token wie ein Passwort!

## Beispiel-Automationen

### Erinnerung bei Feierabend (noch eingestempelt)

```yaml
automation:
  - alias: "Hakuna - Ausstempel-Erinnerung"
    trigger:
      - platform: time
        at: "18:30:00"
    condition:
      - condition: state
        entity_id: binary_sensor.hakuna_eingestempelt
        state: "on"
      - condition: time
        weekday:
          - mon
          - tue
          - wed
          - thu
          - fri
    action:
      - service: notify.mobile_app
        data:
          title: "⏰ Hakuna"
          message: "Du bist noch eingestempelt!"
```

### Timer automatisch starten bei Ankunft

```yaml
automation:
  - alias: "Hakuna - Auto-Einstempeln"
    trigger:
      - platform: zone
        entity_id: person.sebastian
        zone: zone.buero
        event: enter
    condition:
      - condition: state
        entity_id: binary_sensor.hakuna_eingestempelt
        state: "off"
      - condition: time
        after: "07:00:00"
        before: "10:00:00"
        weekday:
          - mon
          - tue
          - wed
          - thu
          - fri
    action:
      - service: button.press
        target:
          entity_id: button.hakuna_timer_starten
      - service: notify.mobile_app
        data:
          title: "✅ Hakuna"
          message: "Timer automatisch gestartet"
```

### Überstunden-Dashboard-Karte

```yaml
type: entities
title: Hakuna Zeiterfassung
entities:
  - entity: binary_sensor.hakuna_eingestempelt
    name: Status
  - entity: sensor.hakuna_timer_dauer
    name: Heutige Arbeitszeit
  - entity: sensor.hakuna_uberstunden
    name: Überstunden
  - entity: sensor.hakuna_resturlaub
    name: Resturlaub
  - type: divider
  - entity: button.hakuna_timer_starten
  - entity: button.hakuna_timer_stoppen
```

## Node-RED Integration

Für komplexere Automatisierungen kannst du den mitgelieferten Node-RED Flow verwenden. 

### Umgebungsvariablen

Setze in Node-RED folgende Umgebungsvariablen:
- `HAKUNA_API_TOKEN` - Dein Hakuna API Token
- `TELEGRAM_CHAT_ID` - Deine Telegram Chat-ID (optional, für Benachrichtigungen)

### Funktionen des Flows

1. **Timer-Status-Check** (alle 30 Min während Arbeitszeit)
   - Prüft ob Timer läuft
   - Warnt bei Timer > 10 Stunden

2. **Täglicher Overview** (8:00 Uhr)
   - Holt Überstunden und Urlaub
   - Setzt Home Assistant Input-Number

3. **Feierabend-Check** (18:30 Uhr)
   - Warnt wenn noch eingestempelt

## Verfügbare Hakuna API Endpunkte

| Endpunkt | Beschreibung |
|----------|--------------|
| `GET /api/v1/timer` | Aktueller Timer-Status |
| `POST /api/v1/timer` | Timer starten |
| `PUT /api/v1/timer` | Timer stoppen (erstellt Eintrag) |
| `DELETE /api/v1/timer` | Timer abbrechen |
| `GET /api/v1/overview` | Überstunden + Urlaub |
| `GET /api/v1/time_entries` | Zeiteinträge |
| `GET /api/v1/presence` | Team-Anwesenheit |
| `GET /api/v1/users` | Benutzer (für Supervisoren) |
| `GET /api/v1/absences` | Abwesenheiten |
| `GET /api/v1/projects` | Projekte |
| `GET /api/v1/tasks` | Aufgaben |

## Fehlerbehebung

### "Invalid API Token"
- Überprüfe ob der Token korrekt kopiert wurde
- Stelle sicher, dass der Token nicht abgelaufen ist
- Erstelle ggf. einen neuen Token

### "Rate Limit Exceeded"
- Die Hakuna API hat ein Limit von 100 Anfragen pro Minute
- Erhöhe das Aktualisierungsintervall in den Optionen

## Changelog

### 1.0.0
- Erste Version
- Timer-Status und -Steuerung
- Überstunden und Urlaub
- Node-RED Beispiel-Flow

## Lizenz

MIT License

## Mitwirken

Pull Requests sind willkommen! Bitte erstelle zuerst ein Issue um die geplanten Änderungen zu besprechen.

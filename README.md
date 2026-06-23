# US-Projekat — SmartHome Assistant

Završni projekat iz predmeta *Ugradbeni sistemi* — agentski IoT sistem za upravljanje
pametnom kućom putem prirodnog jezika, zasnovan na **Hermes Agentu**, **MQTT** protokolu
i krajnjim IoT uređajima (Tasmota ESP32 + picoETF).

**Tim:** Sendin Pašović, Halima Pezo, Mubarak Appa Bugis, Samra Salkica — ak. god. 2025./2026.

## Šta sistem radi

Korisnik priča sa agentom prirodnim jezikom (*"Idem van"*, *"Vraćam se za 30 minuta"*,
*"Postavi večernji ambijent"*), a agent sam bira MCP alat i izvršava radnju na uređajima:

- **Kuhinja (Tasmota ESP32):** bojler (relej 1), pametna utičnica — trenutno **klima**
  (relej 2), DHT11 senzor temperature i vlažnosti.
- **Spavaća soba (picoETF — Raspberry Pi Pico W):** ambijentalne boje (RGB + 8 LED) i
  alarm, ostvareni kroz scene (`arrival`, `departure`, `evening`, `alarm`).

## Struktura repozitorija

```
.
├── picoETF.py                          # MicroPython app za picoETF (Spavaća soba)
├── workspace/
│   ├── mcp_server.py                   # MCP server: Hermes Agent ↔ MQTT (5 alata)
│   └── AGENTS.md                       # Uputstvo ponašanja za SmartHome Assistanta
├── docs/
│   ├── SpecifikacijaUS.md              # Specifikacija projekta
│   ├── hermes_architektura.md          # Arhitektura sistema
│   └── US2026_pro_zadatak.md           # Zadatak i bodovanje
└── Config_smarthometim_4140_15.4.0.dmp # Tasmota konfiguracija (dump)
```

## MQTT

Broker: `195.130.59.221:1883`. Korišteni topici:

- `cmnd/smarthometim/Power1`, `Power2` → komande bojleru / utičnici (`ON`/`OFF`)
- `tele/smarthometim/SENSOR` ← DHT11 telemetrija (svakih ~60 s)
- `stat/smarthometim/POWER1`, `POWER2` ← status releja
- `smarthome/pico/ambience/set` → scena ambijenta: `{"scene":"..."}`
- `smarthome/pico/status` ← status picoETF (RGB, LED, uptime)
- `smarthome/pico/buttons/state` ← tasteri T1–T4 (ignoriraju se u dijalogu)

## MCP alati (`mcp_smarthome_*`)

| Alat | Opis |
|---|---|
| `get_device_status()` | Stanje svih uređaja (temp, vlažnost, releji, ambijent) |
| `toggle_relay(device, state)` | `device` = `boiler` / `socket`; `state` = bool |
| `set_ambience(scene)` | `scene` = `arrival` / `departure` / `evening` / `alarm` |
| `set_mode_leaving()` | Mod odlaska: gasi releje + plava scena |
| `set_mode_arriving(minutes)` | Mod dolaska: pali releje + narandžasta scena |

## Pokretanje

1. **picoETF** — flash-uj MicroPython firmware na Pico W, prenesi `picoETF.py`
   (npr. Thonny / `mpremote`). Po potrebi izmijeni `WIFI_SSID` i `WIFI_PASSWORD`
   u fajlu. Uređaj se spoji na WiFi i MQTT broker te objavljuje status.
2. **Tasmota** — flash-uj Tasmota na ESP32, konfiguriši DHT11 i 2 releja u web sučelju,
   postavi MQTT broker `195.130.59.221` i topic prefiks `smarthometim`.
   (Referenca: `Config_smarthometim_4140_15.4.0.dmp`.)
3. **MCP server** — `pip install paho-mqtt`, zatim `python3 workspace/mcp_server.py`
   (Hermes ga pokreće kao stdio MCP proces).
4. **Hermes Agent** — konfiguriši MCP server u Hermesu, pokreni `hermes --tui` i
   razgovaraj sa agentom.

## Dokumentacija

Detalji u `docs/SpecifikacijaUS.md` (specifikacija), `docs/hermes_architektura.md`
(arhitektura) i `workspace/AGENTS.md` (uputstvo za agenta).

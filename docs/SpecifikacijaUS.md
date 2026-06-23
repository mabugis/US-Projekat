# SmartHome Assistant

**Sistem za pametno upravljanje kućom putem prirodnog jezika**

*Hermes Agent · MQTT · IoT*

---

## Članovi tima

- Sendin Pašović
- Halima Pezo
- Mubarak Appa Bugis
- Samra Salkica

**Ugradbeni sistemi — Samostalni projekat**  
Akademska godina 2025./2026.

---

## 1. Opis projekta i scenarija

Svakome se barem jednom desilo: izađete iz kuće i odmah vas obuzme ona nelagodna misao — jesam li ugasio peglu? Je li bojler ostao upaljen? Ili suprotno — vraćate se kući na kraju dugog dana i kuća je hladna, bojler nije upaljen, sve treba čekati.

SmartHome Assistant rješava upravo taj problem. Umjesto da pamtite i ručno upravljate svakim uređajem, jednostavno kažete Hermes Agentu šta trebate — a on se pobrine za ostalo. Sistem koristi Hermes Agent kao centralni mozak koji prima zahtjeve na prirodnom jeziku, komunicira sa IoT uređajima putem MQTT protokola i donosi odluke na osnovu konteksta i zadanih pravila.

### Modovi rada

Sistem podržava tri osnovna moda koja korisnik aktivira razgovorom sa agentom:

- **Mod odlaska** — korisnik kaže "Idem van", agent provjerava sve uređaje, javlja šta je uključeno i nudi gašenje
- **Mod dolaska** — korisnik kaže "Vraćam se za 30 minuta", agent kalkulira i zakazuje paljenje bojlera i grijanja
- **Ručno upravljanje** — direktne naredbe poput "Upali bojler" ili "Postavi večernji ambijent"

Pored lokalnog chat interfejsa, sistem podržava i Telegram gateway, što omogućava upravljanje sistemom na daljinu putem mobitela.

---

## 2. Korišteni krajnji uređaji

### 2.1 Tasmota uređaj — ESP32

ESP32 mikrokontroler sa Tasmota firmware-om predstavlja jezgro fizičke simulacije kućnih uređaja. Na njega su priključeni:

- **DHT11 senzor** temperature i vlažnosti, koji simulira termostat sobe i na osnovu čijih očitavanja agent odlučuje o grijanju
- **Relej 1** — simulira bojler (uključen/isključen)
- **Relej 2** — simulira pametnu utičnicu za uređaje koji se moraju isključiti pri odlasku (pegla, šporet); u trenutnoj konfiguraciji na njoj je priključena **klima**, pa se pod "klima" podrazumijeva ova utičnica

Uređaj je konfigurisan na WiFi mrežu laboratorije i MQTT broker (`195.130.59.221`). Telemetrija se objavljuje svakih 60 sekundi, a relejima se upravlja putem MQTT komandi.

### 2.2 Custom uređaj — picoETF (Raspberry Pi Pico W)

picoETF platforma pokriva vizualni i interaktivni dio sistema. MicroPython aplikacija realizira:

- **RGB LED** za vizualizaciju ambijenta (toplo/hladno, mod odlaska, mod dolaska, alarm)
- **Osam LED dioda** kao indikatore stanja uređaja
- **Četiri tastera (T1–T4)** koji služe kao fizički komandni panel za brze akcije

Komunikacija sa sistemom odvija se putem JSON poruka preko MQTT protokola.

---

## 3. MQTT topici i format poruka

### 3.1 Tasmota uređaj

Tasmota uređaj koristi standardni Tasmota MQTT format. Topic prefiks dogovara se sa asistentom (npr. `smarthome/tasmota01`).

| Topic | Smjer | Opis |
|-------|-------|------|
| `cmnd/smarthometim/Power1` | → uređaj | Upravljanje relejom 1 (bojler): `ON` / `OFF` |
| `cmnd/smarthometim/Power2` | → uređaj | Upravljanje relejom 2 (utičnica): `ON` / `OFF` |
| `tele/smarthometim/SENSOR` | ← uređaj | Telemetrija: temperatura i vlažnost (DHT11) |
| `stat/smarthometim/POWER1` | ← uređaj | Status releja 1 nakon promjene |
| `stat/smarthometim/POWER2` | ← uređaj | Status releja 2 nakon promjene |

### 3.2 picoETF uređaj

picoETF uređaj koristi vlastiti JSON format poruka definisan u ovom projektu.

| Topic | Smjer | Format poruke |
|-------|-------|---------------|
| `smarthome/pico/leds/set` | → uređaj | `{"mask": 255}` — postavi LED masku |
| `smarthome/pico/rgb/set` | → uređaj | `{"r": 255, "g": 100, "b": 0}` — postavi RGB boju |
| `smarthome/pico/ambience/set` | → uređaj | `{"scene": "departure"}` — aktiviraj scenu |
| `smarthome/pico/buttons/state` | ← uređaj | `{"T1": 0, "T2": 1, "T3": 0, "T4": 0}` |
| `smarthome/pico/status` | ← uređaj | `{"leds": 255, "rgb": {...}, "uptime": 1234}` |

### 3.3 Primjeri JSON poruka

```json
// Scena pri povratku kući:
{"scene": "arrival"}   → RGB toplo narandžasta, LED mask = 0b00000011
{"scene": "departure"} → RGB plava, sve LED diode se gase
```

---

## 4. MCP funkcije

Hermes Agent pristupa uređajima isključivo putem MCP servera, koji je proširenje kostura priloženog u radnom okruženju (`mcp_server.py`). Implementirane su sljedeće funkcije (Hermes ih poziva s prefiksom `mcp_smarthome_`, npr. `mcp_smarthome_get_device_status`):

| MCP alat | Parametri | Opis |
|---|---|---|
| `get_device_status()` | — | Čita stanje svih uređaja: temperaturu i vlažnost (DHT11), status bojlera i utičnice, ambijent (LED maska + RGB) i tastera |
| `toggle_relay(device, state)` | `device: 'boiler'\|'socket'`, `state: bool` | Uključuje/isključuje relej na Tasmota uređaju — `boiler` (relej 1) ili `socket` (relej 2, pametna utičnica) |
| `set_ambience(scene)` | `scene: 'arrival'\|'departure'\|'evening'\|'alarm'` | Postavlja scenu na picoETF — određuje RGB boju i LED masku |
| `set_mode_leaving()` | — | Mod odlaska: gasi bojler i utičnicu, postavlja plavu scenu odlaska |
| `set_mode_arriving(minutes)` | `minutes: int` | Mod dolaska: pali bojler i utičnicu, postavlja toplu narandžastu scenu; `minutes` = minuta do dolaska |

---

## 5. Komunikacija korisnika sa agentom

Ključni princip projekta jeste da korisnik komunicira isključivo prirodnim jezikom — bez ručnog slanja MQTT poruka ili direktnog upravljanja uređajima. Agent interpretira zahtjev, bira odgovarajuće MCP funkcije i izvršava radnje autonomno. Pored lokalnog chat interfejsa (`hermes` ili `hermes --tui`), sistem podržava i Telegram gateway za upravljanje na daljinu.

### Primjeri dijaloških scenarija

- `"Idem van, je li sve okej?"` — agent poziva `get_device_status()`, javlja šta je uključeno i nudi gašenje
- `"Ugasi sve i postavi da sam otišao"` — agent poziva `set_mode_leaving()`, gasi releje i postavlja plavu RGB scenu
- `"Vraćam se za 45 minuta"` — agent poziva `set_mode_arriving(45)` i pali bojler s procjenom vremena grijanja vode
- `"Kolika je temperatura u sobi?"` — agent poziva `get_device_status()` i odgovara: *"Trenutno je 21.5°C, vlažnost 58%."*
- `"Postavi večernji ambijent"` — agent poziva `set_ambience('evening')`, topla narandžasta RGB, prigušeni LED-ovi
- `"Upali klimu"` — agent poziva `toggle_relay('socket', true)` (klima je na pametnoj utičnici)

---

## 6. Plan demonstracije projekta

Demonstracija se izvodi uživo kroz razgovor sa Hermes Agentom, uz vidljive fizičke reakcije uređaja. Video demonstracija biće snimljena i priložena uz finalnu predaju projekta.

### Redoslijed demonstracije

1. **Pokretanje sistema** — `hermes --tui`; agent prikazuje dostupne alate i MCP funkcije
2. **Provjera stanja** — *"Provjeri sve uređaje"*; agent čita DHT11 i stanje releja, javlja rezultat na prirodnom jeziku
3. **Mod odlaska** — *"Idem van"*; relej se isključuje, RGB prelazi na plavu, LED diode se gase
4. **Mod dolaska** — *"Vraćam se za 20 minuta"*; agent pali bojler i utičnicu, postavlja narandžastu scenu i javlja procjenu
5. **Ambijent i alarm** — *"Postavi večernji ambijent"* / *"Uključi alarm"*; RGB i LED diode reaguju na scenu
6. **Telegram upravljanje** — ista komanda putem Telegrama sa mobitela, isti rezultat na uređajima
7. **Klima preko utičnice** — *"Upali klimu"* / *"Ugasi klimu"*; agent upravlja pametnom utičnicom (relej 2)

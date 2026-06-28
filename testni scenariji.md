# SmartHome Assistant — Skripta dijaloških scenarija

**Projekat:** SmartHome Assistant  
**SmartHome Assistant:** Sendin Pašović, Halima Pezo, Mubarak Appa Bugis, Samra Salkica  
**Akademska godina:** 2025./2026.

Ovaj dokument koristi se za testiranje sistema po fazama i kao dio projektne dokumentacije.
Za svaki scenarij bilježi se: ulaz korisnika, očekivano ponašanje agenta, očekivana reakcija
uređaja i da li se stvarno desila reakcija koja je očekivana ili nije (status).

Status testiranja: Prošlo | Nije prošlo | Djelimično | Nije testirano

---

## Faza 1 — Osnovna komunikacija sa agentom (bez uređaja)
Ovi testovi zahtjevaju osnovnu funkcionalnost Hermes agenta.
---

### S-01 — Predstavljanje agenta

| | |
|---|---|
| **Korisnik kaže** | "Zdravo, predstavi se i reci mi čime možeš upravljati u ovoj kući." |
| **Agent treba** | Predstaviti se, nabrojati dostupne uređaje (bojler, utičnica, temperatura, RGB LED, LED diode, tasteri) i opisati modove rada. |
| **Reakcija uređaja** | Nema. |
| **Status** | Prošlo |


---

### S-02 — Nerazumljiv zahtjev

| | |
|---|---|
| **Korisnik kaže** | "Bzvk frmp." |
| **Agent treba** | Ljubazno reći da nije razumio i zamoliti korisnika da preformuluje zahtjev. Ne smije pozivati nikakve MCP funkcije. |
| **Reakcija uređaja** | Nema. |
| **Status** | Prošlo |


---

### S-03 — Zahtjev van domene

| | |
|---|---|
| **Korisnik kaže** | "Koji je danas datum?" |
| **Agent treba** | Odgovoriti normalno (ovo nije IoT zahtjev, agent može odgovoriti iz opšteg znanja). Ne smije pozivati MCP funkcije. |
| **Reakcija uređaja** | Nema. |
| **Status** | Prošlo |


---

## Faza 2 — Provjera stanja sistema

Ovi testovi zahtijevaju funkcionalan Tasmota uređaj.

---

### S-04 — Provjera stanja svih uređaja

| | |
|---|---|
| **Korisnik kaže** | "Provjeri sve uređaje." |
| **Agent treba** | Pozvati `mcp_smarthome_get_device_status()`, pa odgovoriti sa stanjem bojlera, utičnice i trenutnom temperaturom i vlažnošću. |
| **MCP funkcija** | `mcp_smarthome_get_device_status()` |
| **Reakcija uređaja** | Nema fizičke reakcije — samo čitanje stanja. |
| **Status** | Prošlo |


---

### S-05 — Provjera temperature

| | |
|---|---|
| **Korisnik kaže** | "Kolika je temperatura u sobi?" |
| **Agent treba** | Pozvati `get_device_status()` i odgovoriti prirodnim jezikom, npr. "Trenutno je 21.5°C uz vlažnost 58%." |
| **MCP funkcija** | `get_device_status()` |
| **Reakcija uređaja** | Nema fizičke reakcije. |
| **Status** | Prošlo |


---

### S-06 — Provjera temperature alternativna formulacija

| | |
|---|---|
| **Korisnik kaže** | "Je li toplo u kući?" |
| **Agent treba** | Pozvati `get_device_status()` i dati odgovor s interpretacijom, npr. "Temperatura je 17°C — malo je svježije nego obično." |
| **MCP funkcija** | `get_device_status()` |
| **Reakcija uređaja** | Nema fizičke reakcije. |
| **Status** | Nije testirano |


---

## Faza 3 — Direktno upravljanje relejima

Ovi testovi zahtijevaju funkcionalan Tasmota uređaj.

---

### S-07 — Paljenje bojlera

| | |
|---|---|
| **Korisnik kaže** | "Upali bojler." |
| **Agent treba** | Pozvati ` toggle_relay("boiler", true)` i potvrditi: "Bojler je upaljen." |
| **MCP funkcija** | ` toggle_relay("boiler", true)` |
| **Reakcija uređaja** | Relej 1 na Tasmota uređaju se uključuje. |
| **Status** | Prošlo |


---

### S-08 — Gašenje bojlera

| | |
|---|---|
| **Korisnik kaže** | "Ugasi bojler." |
| **Agent treba** | Pozvati ` toggle_relay("boiler", false)` i potvrditi: "Bojler je ugašen." |
| **MCP funkcija** | ` toggle_relay("boiler", false)` |
| **Reakcija uređaja** | Relej 1 na Tasmota uređaju se isključuje. |
| **Status** | Prošlo |

---

### S-09 — Gašenje utičnice (indirektna formulacija)

| | |
|---|---|
| **Korisnik kaže** | "Ugasi peglu." |
| **Agent treba** | Prepoznati da se "pegla" odnosi na pametnu utičnicu i pozvati `toggle_relay("socket", false)`. |
| **MCP funkcija** | `toggle_relay("socket", false)` |
| **Reakcija uređaja** | Relej 2 na Tasmota uređaju se isključuje. |
| **Status** | Prošlo |

---

## Faza 4 — Mod odlaska i dolaska

Ovi testovi zahtijevaju funkcionalne Tasmota i picoETF uređaje.

---

### S-10 — Mod odlaska s potvrdom

| | |
|---|---|
| **Korisnik kaže** | "Idem van, je li sve okej?" |
| **Agent treba** | 1. Pozvati `get_device_status() `. 2. Javiti šta je uključeno. 3. Ponuditi gašenje: "Bojler je upaljen. Želiš li da ugasim sve?" |
| **MCP funkcija** | `get_device_status()`, zatim čeka potvrdu korisnika |
| **Reakcija uređaja** | Nema u ovom koraku — čeka potvrdu. |
| **Status** | Prošlo |


---

### S-11 — Mod odlaska direktan

| | |
|---|---|
| **Korisnik kaže** | "Ugasi sve i postavi da sam otišao." |
| **Agent treba** | Direktno pozvati ` mcp_smarthome_set_mode_leaving()` bez traženja potvrde. |
| **MCP funkcija** | ` mcp_smarthome_set_mode_leaving()` |
| **Reakcija uređaja** |  RGB LED prelazi na plavu. Sve LED diode se gase. |
| **Status** | Prošlo |


---

### S-12 — Mod dolaska s brojem minuta

| | |
|---|---|
| **Korisnik kaže** | "Vraćam se za 45 minuta." |
| **Agent treba** | Pozvati `set_mode_arriving(45)` i potvrditi plan: "Zakazao sam paljenje bojlera — bit će spreman kad stigneš za 45 minuta." |
| **MCP funkcija** | `set_mode_arriving(45)` |
| **Reakcija uređaja** | RGB LED prelazi na toplu narandžastu. Bojler se pali s odgodom od ~30 minuta . |
| **Status** | Prošlo |
---

### S-13 — Mod dolaska bez broja minuta

| | |
|---|---|
| **Korisnik kaže** | "Idem kući." |
| **Agent treba** | Prepoznati namjeru dolaska ali pitati za broj minuta: "Za koliko minuta se vraćaš?" |
| **MCP funkcija** | Nema, čeka odgovor korisnika. |
| **Reakcija uređaja** | Nema. |
| **Status** | Nije testirano |
| **Napomena** | Testira da li agent traži informacije koje mu nedostaju umjesto da pretpostavlja. |

---

## Faza 5 — Ambijenalna scena i LED kontrola

Ovi testovi zahtijevaju funkcionalan picoETF uređaj.

---

### S-14 — Večernji ambijent

| | |
|---|---|
| **Korisnik kaže** | "Postavi večernji ambijent." |
| **Agent treba** | Pozvati `set_ambience('evening')` i potvrditi: "Aktiviran je večernji ambijent." |
| **MCP funkcija** | `set_ambience('evening')` |
| **Reakcija uređaja** | RGB LED prelazi na toplu narandžastu. LED diode se prigušuju po definisanoj maski. |
| **Status** | Prošlo |

---

### S-15 — Alarm scena

| | |
|---|---|
| **Korisnik kaže** | "Aktiviraj alarm." |
| **Agent treba** | Pozvati `set_ambience('alarm')` i potvrditi. |
| **MCP funkcija** | `set_ambience('alarm')` |
| **Reakcija uređaja** | RGB LED prelazi na crvenu. LED diode su sve upaljene po definisanoj maski. |
| **Status** | Prošlo |

---

## Faza 7 — Greške i rubni slučajevi


---

### S-19 — Uređaj nije dostupan

| | |
|---|---|
| **Korisnik kaže** | "Upali bojler." |
| **Simulacija greške** | Tasmota uređaj isključen s mreže ili MQTT broker nedostupan. |
| **Agent treba** | Javiti grešku i stati: "Nisam mogao komunicirati s bojlerom. Provjeri da li je uređaj uključen i pokušaj ponovo." Ne smije tvrditi da je bojler upaljen. |
| **MCP funkcija** | `set_relay('boiler', true)` — vraća grešku |
| **Reakcija uređaja** | Nema (uređaj nedostupan). |
| **Status** | Nije testirano |

---

### S-20 — Nejasan zahtjev za relay

| | |
|---|---|
| **Korisnik kaže** | "Upali onu stvar u kuhinji." |
| **Agent treba** | Zatražiti pojašnjenje: "Na koji uređaj misliš — bojler ili pametnu utičnicu?" Ne smije nagađati. |
| **MCP funkcija** | Nema, čeka pojašnjenje. |
| **Reakcija uređaja** | Nema. |
| **Status** | Prošlo |

---

### S-21 — Višestruki zahtjevi u jednoj poruci

| | |
|---|---|
| **Korisnik kaže** | "Upali bojler i postavi večernji ambijent." |
| **Agent treba** | Pozvati obje funkcije redom: `set_relay('boiler', true)` pa `set_ambience('evening')`, i potvrditi obje radnje u jednoj poruci. |
| **MCP funkcija** | `set_relay('boiler', true)`, `set_ambience('evening')` |
| **Reakcija uređaja** | Relej 1 se uključuje. RGB LED prelazi na toplu narandžastu. |
| **Status** | Prošlo |

---

## Faza 8 — Telegram gateway

Ovi testovi provjeravaju da li sve gore navedene funkcionalnosti rade identično i putem Telegrama.

---

### S-22 — Osnovna komunikacija putem Telegrama

| | |
|---|---|
| **Korisnik kaže** | Telegram poruka: "Zdravo, je li sistem aktivan?" |
| **Agent treba** | Odgovoriti putem Telegram bota, isti kvalitet odgovora kao u lokalnom CLI-u. |
| **Reakcija uređaja** | Nema. |
| **Status** | Prošlo |


---

### S-23 — Upravljanje uređajima putem Telegrama

| | |
|---|---|
| **Korisnik kaže** | Telegram poruka: "Upali bojler." |
| **Agent treba** | Pozvati `set_relay('boiler', true)` i odgovoriti putem Telegram bota. |
| **MCP funkcija** | `set_relay('boiler', true)` |
| **Reakcija uređaja** | Relej 1 se uključuje — isti rezultat kao da je komanda data lokalno. |
| **Status** | Prošlo |

---

### S-24 — Kompletan scenario putem Telegrama

| | |
|---|---|
| **Korisnik kaže** | Telegram poruka: "Idem van, ugasi sve." |
| **Agent treba** | Pozvati `mcp_smarthome_set_mode_leaving()` i odgovoriti putem Telegram bota s potvrdom. |
| **MCP funkcija** | `mcp_smarthome_set_mode_leaving()` |
| **Reakcija uređaja** | Relej 1 i 2 se gase. RGB LED prelazi na plavu. LED diode se gase. |
| **Status** | Prošlo |


---

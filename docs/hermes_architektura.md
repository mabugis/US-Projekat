# Hermes Agent — Arhitektura sistema

## Komponente

### PC (radno mjesto)
- Pristup sistemu putem SSH protokola
- Koristi SSH klijent/terminal za povezivanje na Raspberry Pi

### Raspberry Pi 5
- Pokreće Docker kontejner
- Unutar kontejnera se izvršava Hermes Agent sa MCP serverom
- Agent koristi MQTT za komunikaciju sa krajnjim uređajima
- Agent koristi HTTPS za pristup ML serveru i Internetu

### ML server (195.130.59.211)
- Pokreće Ollama servis sa LLM modelom qwen3.5:9b-64k
- Raspberry Pi pristupa putem HTTPS-a korištenjem tokena za autentifikaciju

### MQTT broker (195.130.59.221)
- Mosquitto broker na portu 1883
- Posrednik između Hermes Agenta i krajnjih uređaja
- Sva MQTT komunikacija ide preko ovog brokera

### Krajnji uređaji (lokalna WiFi mreža)
- **Tasmota (ESP32) + DHT11** — senzor temperature/vlažnosti i releji
- **picoETF (Pico W)** — RGB LED, 8 LED dioda, 4 tastera
- Komuniciraju sa sistemom putem MQTT protokola

## Protokoli komunikacije

| Veza | Protokol | Opis |
|------|----------|------|
| PC → Raspberry Pi | SSH | Pristup kontejneru i izvršavanje komandi |
| Raspberry Pi → ML server | HTTPS | Pozivi LLM modelu (token autentifikacija) |
| Raspberry Pi → MQTT broker | MQTT | Komanda i status krajnjih uređaja |
| MQTT broker → Krajnji uređaji | MQTT | Distribucija poruka |
| Raspberry Pi → Internet | HTTPS | Web pretraga, vanjski servisi |

## Tok podataka

1. Korisnik šalje zahtjev prirodnim jezikom (preko SSH ili Telegrama)
2. Hermes Agent interpretira zahtjev i poziva MCP funkcije
3. MCP funkcije šalju MQTT poruke preko brokera na krajnje uređaje
4. Krajnji uređaji izvršavaju akcije i šalju status nazad
5. Agent prima podatke, kombinuje sa kontekstom i odgovara korisniku
6. Po potrebi agent poziva LLM model na ML serveru za obradu jezika

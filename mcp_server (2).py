#!/usr/bin/env python3
"""
SmartHome MCP Server - Hermes Agent integracija sa MQTT IoT uredjajima.
Komunikacija: JSON-RPC preko stdin/stdout (MCP stdio protokol).

MCP funkcije:
- set_mode_leaving()   -> aktivira mod odlaska
- set_mode_arriving(minutes) -> aktivira mod dolaska
- get_device_status()   -> citanje stanja svih uredjaja
- set_ambience(scene)   -> postavljanje scene na picoETF
- toggle_relay(device, state) -> upravljanje relejima

MQTT topici (Tasmota + picoETF):
- cmnd/smarthometim/Power1, Power2  -> komanda relejima
- tele/smarthometim/SENSOR          -> DHT11 telemetrija
- stat/smarthometim/POWER1, POWER2  -> status releja
- smarthome/pico/ambience/set       -> scena ambijenta
- smarthome/pico/buttons/state      -> stanje tastera
- smarthome/pico/status             -> status picoETF uredjaja
"""

import json
import sys
import time
import threading
import logging

import paho.mqtt.client as mqtt

# ---------- KONFIGURACIJA (izmijeni prema svom timu) ----------

MQTT_BROKER = "195.130.59.221"
MQTT_PORT = 1883
TASMOTA_PREFIX = "smarthometim"
PICO_PREFIX = "smarthome/pico"
MQTT_KEEPALIVE = 60

# ---------- LOGGING (na stderr da ne ometa MCP komunikaciju) ----------

logging.basicConfig(
    level=logging.INFO,
    stream=sys.stderr,
    format="[MCP] %(asctime)s %(levelname)s %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("smarthome-mcp")

# ---------- STANJE UREÐAJA ----------


class DeviceState:
    def __init__(self):
        self.relay1 = "nepoznato"
        self.relay2 = "nepoznato"
        self.relay3 = "nepoznato"
        self.temperature = None
        self.humidity = None
        self.leds_mask = None
        self.rgb = None
        self.buttons = {"T1": 0, "T2": 0, "T3": 0, "T4": 0}
        self._lock = threading.Lock()
        # Pravilo za grijanje: (min_temp, max_temp) ili None ako nije postavljeno
        self.heating_rule = None

    def set_relay(self, num, val):
        with self._lock:
            if num == 1:
                self.relay1 = val
            elif num == 2:
                self.relay2 = val
            elif num == 3:
                self.relay3 = val

    def set_sensor(self, temp, hum):
        with self._lock:
            self.temperature = temp
            self.humidity = hum

    def set_buttons(self, data):
        with self._lock:
            self.buttons = dict(data)

    def set_leds(self, mask, rgb=None):
        with self._lock:
            self.leds_mask = mask
            if rgb is not None:
                self.rgb = rgb

    def snapshot(self):
        with self._lock:
            return {
                "relay_boiler": self.relay1,
                "relay_socket": self.relay2,
                "relay_heating": self.relay3,
                "temperature": self.temperature,
                "humidity": self.humidity,
                "leds_mask": self.leds_mask,
                "rgb": self.rgb,
                "buttons": dict(self.buttons),
                "heating_rule": self.heating_rule,
            }


state = DeviceState()

# ---------- MQTT ----------


def on_connect(client, userdata, flags, rc):
    if rc == 0:
        log.info("MQTT povezan na %s:%d", MQTT_BROKER, MQTT_PORT)
        client.subscribe(f"tele/{TASMOTA_PREFIX}/SENSOR")
        client.subscribe(f"stat/{TASMOTA_PREFIX}/POWER1")
        client.subscribe(f"stat/{TASMOTA_PREFIX}/POWER2")
        client.subscribe(f"stat/{TASMOTA_PREFIX}/POWER3")
        client.subscribe(f"{PICO_PREFIX}/buttons/state")
        client.subscribe(f"{PICO_PREFIX}/status")
    else:
        log.error("MQTT greska pri povezivanju, rc=%d", rc)


def on_message(client, userdata, msg):
    topic = msg.topic
    payload = msg.payload.decode()
    log.debug("MQTT <- %s: %s", topic, payload)

    if topic == f"tele/{TASMOTA_PREFIX}/SENSOR":
        try:
            data = json.loads(payload)
            dht = data.get("DHT11", {})
            temp = dht.get("Temperature")
            hum = dht.get("Humidity")
            if temp is not None:
                state.set_sensor(temp, hum)
                log.info("DHT11: %.1fC, %.0f%%", temp, hum or 0)
                # Provjeri pravilo grijanja sa novom temperaturom
                _check_heating_rule()
        except (json.JSONDecodeError, KeyError):
            pass

    elif topic == f"stat/{TASMOTA_PREFIX}/POWER1":
        try:
            data = json.loads(payload)
            val = data.get("POWER", payload)
        except json.JSONDecodeError:
            val = payload
        state.set_relay(1, val)
        log.info("Relej 1 (bojler): %s", val)

    elif topic == f"stat/{TASMOTA_PREFIX}/POWER2":
        try:
            data = json.loads(payload)
            val = data.get("POWER", payload)
        except json.JSONDecodeError:
            val = payload
        state.set_relay(2, val)
        log.info("Relej 2 (uticnica): %s", val)

    elif topic == f"stat/{TASMOTA_PREFIX}/POWER3":
        try:
            data = json.loads(payload)
            val = data.get("POWER", payload)
        except json.JSONDecodeError:
            val = payload
        state.set_relay(3, val)
        log.info("Relej 3 (grijanje): %s", val)
        # Provjeri pravilo grijanja nakon promjene stanja
        _check_heating_rule()

    elif topic == f"{PICO_PREFIX}/buttons/state":
        try:
            data = json.loads(payload)
            state.set_buttons(data)
            log.info("Tasteri: %s", data)
        except json.JSONDecodeError:
            pass

    elif topic == f"{PICO_PREFIX}/status":
        try:
            data = json.loads(payload)
            state.set_leds(data.get("leds"), data.get("rgb"))
            log.info("picoETF status: leds=%s, rgb=%s", data.get("leds"), data.get("rgb"))
        except json.JSONDecodeError:
            pass


def mqtt_start():
    client = mqtt.Client(
        mqtt.CallbackAPIVersion.VERSION1,
        client_id=f"hermes-mcp-{TASMOTA_PREFIX}",
    )
    client.on_connect = on_connect
    client.on_message = on_message
    client.connect(MQTT_BROKER, MQTT_PORT, MQTT_KEEPALIVE)
    client.loop_start()
    return client


def mqtt_publish(client, topic, payload):
    log.info("MQTT -> %s: %s", topic, payload)
    client.publish(topic, payload)


# ---------- MCP PROTOKOL ----------


def mcp_send(data):
    sys.stdout.write(json.dumps(data) + "\n")
    sys.stdout.flush()


def mcp_response(id, result):
    mcp_send({"jsonrpc": "2.0", "id": id, "result": result})


def mcp_error(id, code, message):
    mcp_send({"jsonrpc": "2.0", "id": id, "error": {"code": code, "message": message}})


# ---------- MCP HANDLERI ----------


def handle_initialize(req_id, params):
    mcp_response(req_id, {
        "protocolVersion": "2024-11-05",
        "capabilities": {"tools": {}},
        "serverInfo": {
            "name": "smarthome-mcp",
            "version": "1.0.0",
        },
    })
    log.info("MCP inicijalizovan")


def handle_tools_list(req_id, params):
    tools = [
        {
            "name": "set_mode_leaving",
            "description": (
                "Aktivira mod odlaska. Provjerava sve uredjaje, gasi oba releja "
                "(bojler i uticnica) i postavlja scenu odlaska na picoETF "
                "(plava RGB dioda, sve LED se gase). Koristi kada korisnik "
                "kaze da ide van ili napusta kucu."
            ),
            "inputSchema": {"type": "object", "properties": {}, "required": []},
        },
        {
            "name": "set_mode_arriving",
            "description": (
                "Aktivira mod dolaska. Ukljucuje bojler i uticnicu i postavlja "
                "scenu dolaska na picoETF (topla narandzasta RGB, LED 1 i 2 se "
                "pale). Prima broj minuta do dolaska korisnika."
            ),
            "inputSchema": {
                "type": "object",
                "properties": {
                    "minutes": {
                        "type": "integer",
                        "description": "Broj minuta do dolaska korisnika",
                        "minimum": 0,
                    }
                },
                "required": ["minutes"],
            },
        },
        {
            "name": "get_device_status",
            "description": (
                "Cita trenutno stanje svih uredjaja: temperatura i vlaznost sa "
                "DHT11 senzora, status oba releja (bojler i uticnica), stanje "
                "LED dioda i RGB diode na picoETF, i stanje cetiri tastera T1-T4."
            ),
            "inputSchema": {"type": "object", "properties": {}, "required": []},
        },
        {
            "name": "set_ambience",
            "description": (
                "Postavlja scenu ambijenta na picoETF uredjaju. Podrzane scene: "
                "'arrival' (dolazak - narandzasta), 'departure' (odlazak - plava), "
                "'evening' (vece - prigusena topla), 'alarm' (crvena, trepce)."
            ),
            "inputSchema": {
                "type": "object",
                "properties": {
                    "scene": {
                        "type": "string",
                        "enum": ["arrival", "departure", "evening", "alarm"],
                        "description": "Scena ambijenta",
                    }
                },
                "required": ["scene"],
            },
        },
        {
            "name": "toggle_relay",
            "description": (
                "Ukljucuje ili iskljucuje zadani relej na Tasmota uredjaju. "
                "Koristi 'boiler' za bojler (relej 1), 'socket' za klimu "
                "(relej 2) ili 'heating' za grijanje (relej 3). "
                "state=true ukljucuje, state=false iskljucuje."
            ),
            "inputSchema": {
                "type": "object",
                "properties": {
                    "device": {
                        "type": "string",
                        "enum": ["boiler", "socket", "heating"],
                        "description": "Uredjaj: 'boiler', 'socket' ili 'heating'",
                    },
                    "state": {
                        "type": "boolean",
                        "description": "true za ON, false za OFF",
                    },
                },
                "required": ["device", "state"],
            },
        },
        {
            "name": "set_heating_rule",
            "description": (
                "Postavlja pravilo za automatsko ukljucivanje i iskljucivanje grijanja. "
                "Kad temperatura padne ispod min_temp, grijanje se ukljucuje. "
                "Kad temperatura poraste iznad max_temp, grijanje se iskljucuje. "
                "Koristi kada korisnik zadaje pravilo poput: 'ako temperatura padne "
                "ispod 19 stepeni upali grijanje'."
            ),
            "inputSchema": {
                "type": "object",
                "properties": {
                    "min_temp": {
                        "type": "number",
                        "description": "Minimalna temperatura (ispod koje se pali grijanje)",
                    },
                    "max_temp": {
                        "type": "number",
                        "description": "Maksimalna temperatura (iznad koje se gasi grijanje)",
                    },
                },
                "required": ["min_temp", "max_temp"],
            },
        },
        {
            "name": "get_heating_rule",
            "description": (
                "Vraca trenutno postavljeno pravilo za automatsko grijanje, "
                "ili poruku da pravilo nije postavljeno."
            ),
            "inputSchema": {"type": "object", "properties": {}, "required": []},
        },
        {
            "name": "clear_heating_rule",
            "description": (
                "Brise postavljeno pravilo za automatsko grijanje. "
                "Koristi kada korisnik kaze 'ugasi automatsko grijanje' ili "
                "'obrisi pravilo za grijanje'."
            ),
            "inputSchema": {"type": "object", "properties": {}, "required": []},
        },
    ]
    mcp_response(req_id, {"tools": tools})


def handle_tools_call(req_id, params):
    tool_name = params.get("name")
    arguments = params.get("arguments", {})

    try:
        if tool_name == "set_mode_leaving":
            text = tool_set_mode_leaving()
        elif tool_name == "set_mode_arriving":
            text = tool_set_mode_arriving(arguments)
        elif tool_name == "get_device_status":
            text = tool_get_device_status()
        elif tool_name == "set_ambience":
            text = tool_set_ambience(arguments)
        elif tool_name == "toggle_relay":
            text = tool_toggle_relay(arguments)
        elif tool_name == "set_heating_rule":
            text = tool_set_heating_rule(arguments)
        elif tool_name == "get_heating_rule":
            text = tool_get_heating_rule()
        elif tool_name == "clear_heating_rule":
            text = tool_clear_heating_rule()
        else:
            mcp_error(req_id, -32601, f"Nepoznat alat: {tool_name}")
            return

        mcp_response(req_id, {"content": [{"type": "text", "text": text}]})

    except Exception as exc:
        log.exception("Greska u alatu %s", tool_name)
        mcp_response(req_id, {
            "content": [{"type": "text", "text": f"GRESKA: {exc}"}],
            "isError": True,
        })


# ---------- IMPLEMENTACIJA MCP FUNKCIJA ----------


def tool_set_mode_leaving():
    # Gasi sve releje
    mqtt_publish(mqtt, f"cmnd/{TASMOTA_PREFIX}/Power1", "OFF")
    mqtt_publish(mqtt, f"cmnd/{TASMOTA_PREFIX}/Power2", "OFF")
    mqtt_publish(mqtt, f"cmnd/{TASMOTA_PREFIX}/Power3", "OFF")

    # Postavi scenu odlaska na picoETF
    mqtt_publish(mqtt, f"{PICO_PREFIX}/ambience/set", json.dumps({"scene": "departure"}))

    return (
        "Mod odlaska aktiviran.\n"
        "  - Bojler (relej 1): ISKLJUCEN\n"
        "  - Klima (relej 2): ISKLJUCENA\n"
        "  - Grijanje (relej 3): ISKLJUCENO\n"
        "  - picoETF: scena 'departure' (plava RGB, LED gase se)\n"
        "\n"
        "Svi uredjaji su iskljuceni. Kuca je u modu odsutnosti."
    )


def tool_set_mode_arriving(arguments):
    minutes = int(arguments.get("minutes", 0))

    # Uvijek ukljuci bojler
    mqtt_publish(mqtt, f"cmnd/{TASMOTA_PREFIX}/Power1", "ON")

    # Procitaj trenutnu temperaturu i odluci o grijanju/klimi
    snap = state.snapshot()
    temp = snap["temperature"]
    climate_action = ""

    if temp is not None:
        if temp < 19:
            # Hladno -> upali grijanje, ugasi klimu
            mqtt_publish(mqtt, f"cmnd/{TASMOTA_PREFIX}/Power3", "ON")
            mqtt_publish(mqtt, f"cmnd/{TASMOTA_PREFIX}/Power2", "OFF")
            climate_action = f"  - Grijanje (relej 3): UKLJUCENO (temperatura {temp}C, ispod 19C)\n  - Klima (relej 2): ISKLJUCENA\n"
        elif temp > 24:
            # Toplo -> upali klimu, ugasi grijanje
            mqtt_publish(mqtt, f"cmnd/{TASMOTA_PREFIX}/Power2", "ON")
            mqtt_publish(mqtt, f"cmnd/{TASMOTA_PREFIX}/Power3", "OFF")
            climate_action = f"  - Klima (relej 2): UKLJUCENA (temperatura {temp}C, iznad 24C)\n  - Grijanje (relej 3): ISKLJUCENO\n"
        else:
            # Ugodna temperatura -> nista ne pali
            mqtt_publish(mqtt, f"cmnd/{TASMOTA_PREFIX}/Power2", "OFF")
            mqtt_publish(mqtt, f"cmnd/{TASMOTA_PREFIX}/Power3", "OFF")
            climate_action = f"  - Klima i grijanje: ISKLJUCENI (temperatura {temp}C, ugodna)\n"
    else:
        climate_action = "  - Klima/grijanje: nema podataka o temperaturi, ostavljeno iskljuceno\n"

    # Postavi scenu dolaska na picoETF
    mqtt_publish(mqtt, f"{PICO_PREFIX}/ambience/set", json.dumps({"scene": "arrival"}))

    return (
        f"Mod dolaska aktiviran (dolazak za {minutes} minuta).\n"
        f"  - Bojler (relej 1): UKLJUCEN (voda ce biti topla za ~{min(30, minutes)} min)\n"
        f"{climate_action}"
        f"  - picoETF: scena 'arrival' (topla narandzasta RGB, LED 1 i 2 pale se)\n"
        f"\n"
        f"Sistem je spreman za Vas dolazak."
    )


def tool_get_device_status():
    # Zatrazi trenutno stanje od uredjaja
    mqtt_publish(mqtt, f"cmnd/{TASMOTA_PREFIX}/Power1", "")
    mqtt_publish(mqtt, f"cmnd/{TASMOTA_PREFIX}/Power2", "")
    mqtt_publish(mqtt, f"cmnd/{TASMOTA_PREFIX}/Power3", "")
    time.sleep(0.3)

    snap = state.snapshot()

    lines = ["Stanje sistema:"]
    lines.append(f"  Bojler (relej 1): {snap['relay_boiler']}")
    lines.append(f"  Klima (relej 2): {snap['relay_socket']}")
    lines.append(f"  Grijanje (relej 3): {snap['relay_heating']}")

    if snap["temperature"] is not None:
        lines.append(f"  Temperatura: {snap['temperature']}C")
        lines.append(f"  Vlaznost: {snap['humidity']}%")
    else:
        lines.append("  Temperatura: nema podataka (sacekajte telemetriju)")

    if snap["heating_rule"]:
        lines.append(f"  Pravilo grijanja: pali ispod {snap['heating_rule'][0]}C, gasi iznad {snap['heating_rule'][1]}C")
    else:
        lines.append("  Pravilo grijanja: nije postavljeno")

    if snap["leds_mask"] is not None:
        lines.append(f"  LED maska: {snap['leds_mask']} (binarno: {snap['leds_mask']:08b})")
    if snap["rgb"] is not None:
        lines.append(f"  RGB: R={snap['rgb'].get('r',0)}, G={snap['rgb'].get('g',0)}, B={snap['rgb'].get('b',0)}")
    lines.append(f"  Tasteri: {snap['buttons']}")

    return "\n".join(lines)


def tool_set_ambience(arguments):
    scene = arguments.get("scene", "evening")
    mqtt_publish(mqtt, f"{PICO_PREFIX}/ambience/set", json.dumps({"scene": scene}))

    descriptions = {
        "arrival": "scena dolaska (topla narandzasta RGB, LED 1 i 2 pale se)",
        "departure": "scena odlaska (plava RGB, sve LED gase se)",
        "evening": "vecernji ambijent (prigusena topla RGB, prigusene LED)",
        "alarm": "alarm (crvena RGB, sve LED trepcu)",
    }
    desc = descriptions.get(scene, f"nepoznata scena: {scene}")
    return f"Ambient postavljen: {desc}"


def tool_toggle_relay(arguments):
    device = arguments.get("device")
    desired_state = arguments.get("state", False)
    state_str = "ON" if desired_state else "OFF"

    if device == "boiler":
        topic = f"cmnd/{TASMOTA_PREFIX}/Power1"
        label = "Bojler (relej 1)"
    elif device == "socket":
        topic = f"cmnd/{TASMOTA_PREFIX}/Power2"
        label = "Klima (relej 2)"
    elif device == "heating":
        topic = f"cmnd/{TASMOTA_PREFIX}/Power3"
        label = "Grijanje (relej 3)"
    else:
        return f"GRESKA: nepoznat uredjaj '{device}'. Koristi 'boiler', 'socket' ili 'heating'."

    mqtt_publish(mqtt, topic, state_str)
    return f"{label} -> {state_str}"


def _check_heating_rule():
    """Interna funkcija: provjerava pravilo grijanja i reaguje na temperaturu."""
    snap = state.snapshot()
    rule = snap["heating_rule"]
    temp = snap["temperature"]

    if rule is None or temp is None:
        return

    min_t, max_t = rule

    if temp < min_t:
        log.info("Pravilo grijanja: %.1fC < %.1fC -> UKLJUCUJEM grijanje", temp, min_t)
        mqtt_publish(mqtt, f"cmnd/{TASMOTA_PREFIX}/Power3", "ON")
        # Ugasi klimu ako je upaljena
        mqtt_publish(mqtt, f"cmnd/{TASMOTA_PREFIX}/Power2", "OFF")
    elif temp > max_t:
        log.info("Pravilo grijanja: %.1fC > %.1fC -> ISKLJUCUJEM grijanje", temp, max_t)
        mqtt_publish(mqtt, f"cmnd/{TASMOTA_PREFIX}/Power3", "OFF")


def tool_set_heating_rule(arguments):
    min_t = float(arguments.get("min_temp", 19))
    max_t = float(arguments.get("max_temp", 23))

    if min_t >= max_t:
        return f"GRESKA: min_temp ({min_t}) mora biti manji od max_temp ({max_t})."

    with state._lock:
        state.heating_rule = (min_t, max_t)

    # Odmah provjeri trenutnu temperaturu
    _check_heating_rule()

    snap = state.snapshot()
    temp_info = f" (trenutna temperatura: {snap['temperature']}C)" if snap["temperature"] else ""

    return (
        f"Pravilo grijanja postavljeno{temp_info}:\n"
        f"  - Pali grijanje kad temperatura padne ispod {min_t}C\n"
        f"  - Gasi grijanje kad temperatura poraste iznad {max_t}C\n"
        f"Pravilo ce se automatski primjenjivati pri svakom ocitavanju DHT11 senzora."
    )


def tool_get_heating_rule():
    snap = state.snapshot()
    rule = snap["heating_rule"]
    temp = snap["temperature"]

    if rule is None:
        return "Pravilo grijanja nije postavljeno."

    min_t, max_t = rule
    temp_info = f"\nTrenutna temperatura: {temp}C" if temp else ""
    return (
        f"Aktivno pravilo grijanja:\n"
        f"  - Pali grijanje ispod: {min_t}C\n"
        f"  - Gasi grijanje iznad: {max_t}C"
        f"{temp_info}"
    )


def tool_clear_heating_rule():
    with state._lock:
        state.heating_rule = None
    log.info("Pravilo grijanja obrisano")
    return "Pravilo grijanja je obrisano. Grijanje nece biti automatski kontrolisano."


# ---------- MAIN LOOP ----------


def main():
    global mqtt
    mqtt = mqtt_start()
    log.info("SmartHome MCP server pokrenut. Ceka se Hermes Agent...")

    while True:
        line = sys.stdin.readline()
        if not line:
            log.info("stdin zatvoren, gasenje...")
            break

        try:
            request = json.loads(line.strip())
        except json.JSONDecodeError as exc:
            log.error("Neispravan JSON: %s", exc)
            continue

        method = request.get("method")
        req_id = request.get("id")
        params = request.get("params", {})

        # JSON-RPC notifikacije nemaju id - ne salji odgovor
        if req_id is None:
            log.debug("Notifikacija: %s", method)
            continue

        log.debug("MCP <- %s (id=%s)", method, req_id)

        try:
            if method == "initialize":
                handle_initialize(req_id, params)
            elif method == "tools/list":
                handle_tools_list(req_id, params)
            elif method == "tools/call":
                handle_tools_call(req_id, params)
            else:
                mcp_error(req_id, -32601, f"Nepoznat metod: {method}")
        except Exception as exc:
            log.exception("Greska pri obradi %s", method)
            mcp_error(req_id, -32603, f"Interna greska: {exc}")


if __name__ == "__main__":
    main()

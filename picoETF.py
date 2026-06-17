import network
import time
import json
from machine import Pin, PWM
from umqtt.simple import MQTTClient


WIFI_SSID     = "Lab220"           # naziv WiFi mreže laboratorije
WIFI_PASSWORD = "lab220lozinka"              # lozinka 

MQTT_BROKER   = "195.130.59.221"
MQTT_PORT     = 1883
MQTT_CLIENT_ID = "smarthome-pico-tim06" 

# MQTT topici
TOPIC_LEDS_SET     = b"smarthome/pico/leds/set"
TOPIC_RGB_SET      = b"smarthome/pico/rgb/set"
TOPIC_AMBIENCE_SET = b"smarthome/pico/ambience/set"
TOPIC_BUTTONS      = b"smarthome/pico/buttons/state"
TOPIC_STATUS       = b"smarthome/pico/status"


# LED diode: LED0=GP4 ... LED7=GP11
LED_PINS = [4, 5, 6, 7, 8, 9, 10, 11]
leds = [Pin(p, Pin.OUT) for p in LED_PINS]

# RGB LED: R=GP14, G=GP12, B=GP13
# Koristimo PWM za miješanje boja
rgb_r = PWM(Pin(14))
rgb_g = PWM(Pin(12))
rgb_b = PWM(Pin(13))
rgb_r.freq(1000)
rgb_g.freq(1000)
rgb_b.freq(1000)

# Tasteri: T1=GP0, T2=GP1, T3=GP2, T4=GP3
# pull_up jer su tasteri aktivni LOW (pritisak = GND)
BUTTON_PINS = [0, 1, 2, 3]
buttons = [Pin(p, Pin.IN, Pin.PULL_UP) for p in BUTTON_PINS]

# ─────────────────────────────────────────
#  STANJE SISTEMA
# ─────────────────────────────────────────
current_led_mask = 0
current_rgb = {"r": 0, "g": 0, "b": 0}
prev_button_states = [1, 1, 1, 1]  # 1 = nije pritisnut (pull_up)

# ─────────────────────────────────────────
#  SCENE AMBIJENTA
# ─────────────────────────────────────────
SCENES = {
    "arrival": {
        "rgb": {"r": 255, "g": 80, "b": 10},   # toplo narandžasta
        "mask": 0b00000011                       # LED0 i LED1 upaljene
    },
    "departure": {
        "rgb": {"r": 0, "g": 30, "b": 255},     # hladna plava
        "mask": 0b00000000                       # sve ugašeno
    },
    "evening": {
        "rgb": {"r": 200, "g": 60, "b": 0},     # toplo žuta/narandžasta
        "mask": 0b00001111                       # prva 4 LED-a
    },
    "alarm": {
        "rgb": {"r": 255, "g": 0, "b": 0},      # crvena
        "mask": 0b11111111                       # sve upaljene
    },
    "off": {
        "rgb": {"r": 0, "g": 0, "b": 0},
        "mask": 0b00000000
    }
}

# ─────────────────────────────────────────
#  HARDWARE FUNKCIJE
# ─────────────────────────────────────────

def set_led_mask(mask):
    """Postavi stanje LED dioda prema bitmask vrijednosti (0-255)."""
    global current_led_mask
    current_led_mask = mask & 0xFF
    for i, led in enumerate(leds):
        led.value(1 if (mask >> i) & 1 else 0)

def set_rgb(r, g, b):
    """Postavi boju RGB LED diode. r, g, b su vrijednosti 0-255."""
    global current_rgb
    current_rgb = {"r": r, "g": g, "b": b}
    # PWM duty cycle: 0-65535. Pretvaramo iz 0-255.
    rgb_r.duty_u16(int(r / 255 * 65535))
    rgb_g.duty_u16(int(g / 255 * 65535))
    rgb_b.duty_u16(int(b / 255 * 65535))

def set_ambience(scene_name):
    """Aktiviraj predefinisanu scenu ambijenta."""
    scene = SCENES.get(scene_name)
    if scene is None:
        print(f"[WARN] Nepoznata scena: {scene_name}")
        return False
    set_rgb(scene["rgb"]["r"], scene["rgb"]["g"], scene["rgb"]["b"])
    set_led_mask(scene["mask"])
    print(f"[OK] Scena '{scene_name}' aktivirana")
    return True

def read_buttons():
    """Čita stanje sva četiri tastera. Vraća dict {T1: 0/1, ...}"""
    # Inverzija jer su pull_up (0 = pritisnut, 1 = slobodan)
    return {
        "T1": 0 if buttons[0].value() == 0 else 1,
        "T2": 0 if buttons[1].value() == 0 else 1,
        "T3": 0 if buttons[2].value() == 0 else 1,
        "T4": 0 if buttons[3].value() == 0 else 1,
    }

def blink_alarm(times=3):
    """Trepni svim LED diodama - za alarm/potvrdu."""
    original_mask = current_led_mask
    original_rgb = current_rgb.copy()
    for _ in range(times):
        set_led_mask(0xFF)
        set_rgb(255, 0, 0)
        time.sleep(0.2)
        set_led_mask(0x00)
        set_rgb(0, 0, 0)
        time.sleep(0.2)
    set_led_mask(original_mask)
    set_rgb(original_rgb["r"], original_rgb["g"], original_rgb["b"])

# ─────────────────────────────────────────
#  MQTT CALLBACK - prima komande od agenta
# ─────────────────────────────────────────

def on_message(topic, msg):
    """Obrađuje primljene MQTT poruke."""
    print(f"[MQTT] Primljeno na {topic}: {msg}")
    try:
        data = json.loads(msg)
    except Exception as e:
        print(f"[ERROR] JSON parsiranje: {e}")
        return

    if topic == TOPIC_LEDS_SET:
        # {"mask": 255}
        mask = data.get("mask", 0)
        set_led_mask(mask)
        publish_status(client)

    elif topic == TOPIC_RGB_SET:
        # {"r": 255, "g": 100, "b": 0}
        r = data.get("r", 0)
        g = data.get("g", 0)
        b = data.get("b", 0)
        set_rgb(r, g, b)
        publish_status(client)

    elif topic == TOPIC_AMBIENCE_SET:
        # {"scene": "arrival"}
        scene = data.get("scene", "off")
        set_ambience(scene)
        publish_status(client)

# ─────────────────────────────────────────
#  MQTT PUBLISH FUNKCIJE
# ─────────────────────────────────────────

def publish_status(c):
    """Objavi trenutno stanje uređaja."""
    payload = json.dumps({
        "leds": current_led_mask,
        "rgb": current_rgb,
        "uptime": time.ticks_ms() // 1000
    })
    c.publish(TOPIC_STATUS, payload)

def publish_buttons(c, states):
    """Objavi stanje tastera."""
    payload = json.dumps(states)
    c.publish(TOPIC_BUTTONS, payload)
    print(f"[MQTT] Taster event: {payload}")

# ─────────────────────────────────────────
#  WIFI KONEKCIJA
# ─────────────────────────────────────────

def connect_wifi():
    wlan = network.WLAN(network.STA_IF)
    wlan.active(True)
    if not wlan.isconnected():
        print(f"[WiFi] Spajanje na {WIFI_SSID}...")
        wlan.connect(WIFI_SSID, WIFI_PASSWORD)
        timeout = 15
        while not wlan.isconnected() and timeout > 0:
            time.sleep(1)
            timeout -= 1
            print(".", end="")
        print()
    if wlan.isconnected():
        print(f"[WiFi] Spojeno! IP: {wlan.ifconfig()[0]}")
        return True
    else:
        print("[WiFi] GREŠKA: Nije moguće spojiti se!")
        return False

# ─────────────────────────────────────────
#  MQTT KONEKCIJA
# ─────────────────────────────────────────

def connect_mqtt():
    c = MQTTClient(
        client_id=MQTT_CLIENT_ID,
        server=MQTT_BROKER,
        port=MQTT_PORT,
        keepalive=60
    )
    c.set_callback(on_message)
    c.connect()
    # Pretplati se na sve komandne topice
    c.subscribe(TOPIC_LEDS_SET)
    c.subscribe(TOPIC_RGB_SET)
    c.subscribe(TOPIC_AMBIENCE_SET)
    print(f"[MQTT] Spojen na broker {MQTT_BROKER}")
    print(f"[MQTT] Slušam na: leds/set, rgb/set, ambience/set")
    return c

# ─────────────────────────────────────────
#  INICIJALIZACIJA
# ─────────────────────────────────────────

def startup_sequence():
    """Vizualna potvrda da je uređaj aktivan."""
    print("[INFO] picoETF SmartHome pokrenut")
    # Sweep LED dioda
    for i in range(8):
        set_led_mask(1 << i)
        time.sleep(0.08)
    set_led_mask(0xFF)
    time.sleep(0.3)
    set_led_mask(0x00)
    # RGB rainbow kratki test
    for r, g, b in [(255,0,0), (0,255,0), (0,0,255), (0,0,0)]:
        set_rgb(r, g, b)
        time.sleep(0.2)
    print("[INFO] Startup sekvenca završena")

# ─────────────────────────────────────────
#  GLAVNA PETLJA
# ─────────────────────────────────────────

# Inicijalizacija
startup_sequence()

if not connect_wifi():
    # Ako WiFi nije dostupan, trepni alarm i zaustavi
    blink_alarm(5)
    raise SystemExit("WiFi konekcija nije uspjela")

client = connect_mqtt()

# Objavi inicijalni status
publish_status(client)

# Postavi početnu scenu
set_ambience("off")

print("[INFO] Ulazim u glavnu petlju...")
STATUS_INTERVAL = 30  # šalji status svakih 30 sekundi
last_status = time.ticks_ms()

while True:
    try:
        # Provjeri nove MQTT poruke (non-blocking)
        client.check_msg()

        # Provjera tastera - objavi samo ako se promijenilo stanje
        current_btn = read_buttons()
        current_vals = [current_btn["T1"], current_btn["T2"],
                        current_btn["T3"], current_btn["T4"]]

        if current_vals != prev_button_states:
            publish_buttons(client, current_btn)
            prev_button_states = current_vals

        # Periodični status
        if time.ticks_diff(time.ticks_ms(), last_status) > STATUS_INTERVAL * 1000:
            publish_status(client)
            last_status = time.ticks_ms()

        time.sleep(0.05)  # 50ms polling interval

    except OSError as e:
        print(f"[ERROR] MQTT greška: {e}. Pokušavam reconnect...")
        time.sleep(3)
        try:
            client = connect_mqtt()
        except Exception as e2:
            print(f"[ERROR] Reconnect nije uspio: {e2}")
            time.sleep(5)

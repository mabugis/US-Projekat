"""
SmartHome Dashboard - Tim 06
Pokreni: pip install paho-mqtt
         python dashboard.py
Otvori:  http://localhost:8080
"""

import paho.mqtt.client as mqtt
import json
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
from datetime import datetime

MQTT_BROKER    = "195.130.59.221"
MQTT_PORT      = 1883
TASMOTA_TOPIC  = "smarthometim"  # prefiks vašeg Tasmota uređaja - prilagodi!

state = {
    "temperature": "--", "humidity": "--",
    "relay1": "OFF", "relay2": "OFF",
    "rgb": {"r": 0, "g": 0, "b": 0},
    "leds": 0,
    "buttons": {"T1": 1, "T2": 1, "T3": 1, "T4": 1},
    "uptime": "--", "scene": "--",
    "last_temp": "--", "last_pico": "--", "last_relay": "--",
    "log": [], "connected": False
}

def ts():
    return datetime.now().strftime("%H:%M:%S")

def add_log(topic, msg):
    state["log"].insert(0, {"ts": ts(), "topic": topic, "msg": str(msg)[:100]})
    if len(state["log"]) > 40:
        state["log"].pop()
    print(f"[{ts()}] {topic}: {str(msg)[:80]}")

def on_connect(client, userdata, flags, rc):
    if rc == 0:
        state["connected"] = True
        # Samo naši topici
        client.subscribe(f"tele/{TASMOTA_TOPIC}/SENSOR")
        client.subscribe(f"stat/{TASMOTA_TOPIC}/POWER1")
        client.subscribe(f"stat/{TASMOTA_TOPIC}/POWER2")
        client.subscribe(f"stat/{TASMOTA_TOPIC}/RESULT")
        client.subscribe("smarthome/pico/#")
        add_log("SYSTEM", f"Spojeno! Slušam: {TASMOTA_TOPIC} + smarthome/pico/#")
    else:
        print(f"[MQTT] Greška: {rc}")

def on_disconnect(client, userdata, rc):
    state["connected"] = False
    add_log("SYSTEM", "Odspojeno")

def on_message(client, userdata, msg):
    topic = msg.topic
    try:
        payload = msg.payload.decode("utf-8")
    except:
        return

    add_log(topic, payload)
    now = ts()

    try:
        if "/SENSOR" in topic:
            d = json.loads(payload)
            if "DHT11" in d:
                state["temperature"] = d["DHT11"].get("Temperature", "--")
                state["humidity"]    = d["DHT11"].get("Humidity", "--")
                state["last_temp"]   = now

        elif "/POWER1" in topic and "stat/" in topic:
            state["relay1"] = payload.strip()
            state["last_relay"] = now

        elif "/POWER2" in topic and "stat/" in topic:
            state["relay2"] = payload.strip()
            state["last_relay"] = now

        elif "/RESULT" in topic:
            d = json.loads(payload)
            if "POWER1" in d: state["relay1"] = d["POWER1"]
            if "POWER2" in d: state["relay2"] = d["POWER2"]
            state["last_relay"] = now

        elif topic == "smarthome/pico/status":
            d = json.loads(payload)
            if "rgb"    in d: state["rgb"]  = d["rgb"]
            if "leds"   in d: state["leds"] = d["leds"]
            if "uptime" in d:
                u = d["uptime"]
                state["uptime"] = f"{u//3600}h {(u%3600)//60}m {u%60}s"
            state["last_pico"] = now

        elif topic == "smarthome/pico/buttons/state":
            state["buttons"] = json.loads(payload)
            state["last_pico"] = now

        elif topic == "smarthome/pico/ambience/set":
            state["scene"] = json.loads(payload).get("scene", "--")

        elif topic == "smarthome/pico/rgb/set":
            d = json.loads(payload)
            state["rgb"] = {"r": d.get("r",0), "g": d.get("g",0), "b": d.get("b",0)}

        elif topic == "smarthome/pico/leds/set":
            state["leds"] = json.loads(payload).get("mask", 0)

    except Exception as e:
        pass

# ── HTML template (CSS zagrade su escapane kao {{ i }}) ────
HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="bs">
<head>
<meta charset="UTF-8">
<meta http-equiv="refresh" content="2">
<title>SmartHome Tim 06</title>
<style>
*{{box-sizing:border-box;margin:0;padding:0}}
body{{font-family:'Segoe UI',sans-serif;background:#0f1117;color:#e2e8f0;padding:20px}}
header{{display:flex;justify-content:space-between;align-items:center;margin-bottom:24px;padding-bottom:14px;border-bottom:1px solid #1e2433}}
h1{{font-size:1.3rem;font-weight:600}}
h1 span{{color:#475569;font-weight:400;font-size:.9rem;margin-left:8px}}
.dot{{width:10px;height:10px;border-radius:50%;display:inline-block;margin-right:6px;background:{DOT_COLOR};{DOT_GLOW}}}
.stxt{{font-size:.85rem;color:#64748b}}
.grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(260px,1fr));gap:14px;margin-bottom:14px}}
.card{{background:#161b27;border:1px solid #1e2433;border-radius:10px;padding:18px}}
.ctitle{{font-size:.7rem;text-transform:uppercase;letter-spacing:1px;color:#475569;margin-bottom:14px;display:flex;align-items:center;gap:8px}}
.ctitle::before{{content:'';width:3px;height:13px;border-radius:2px;background:var(--a,#3b82f6)}}
.big{{font-size:3rem;font-weight:700;letter-spacing:-2px;line-height:1}}
.big span{{font-size:1.3rem;color:#64748b;font-weight:400}}
.sub{{color:#64748b;font-size:.85rem;margin-top:6px}}
.sub strong{{color:#94a3b8}}
.lts{{font-size:.7rem;color:#334155;margin-top:10px}}
.rrow{{display:flex;justify-content:space-between;align-items:center;padding:9px 0;border-bottom:1px solid #1e2433}}
.rrow:last-of-type{{border:none}}
.badge{{font-size:.72rem;font-weight:700;padding:3px 10px;border-radius:20px}}
.boff{{background:#1e2433;color:#475569}}
.bon{{background:#14532d;color:#4ade80;box-shadow:0 0 6px #4ade8044}}
.rgb-box{{width:100%;height:70px;border-radius:8px;margin-bottom:10px;display:flex;align-items:center;justify-content:center;font-size:.75rem;color:rgba(255,255,255,.4)}}
.rgb-row{{display:flex;gap:10px}}
.rgb-val{{flex:1;text-align:center}}
.rgb-val .l{{font-size:.65rem;color:#475569;margin-bottom:3px}}
.rgb-val .n{{font-size:1rem;font-weight:600}}
.ll{{display:grid;grid-template-columns:repeat(8,1fr);gap:6px;margin-bottom:5px}}
.ll div{{text-align:center;font-size:.58rem;color:#334155}}
.lg{{display:grid;grid-template-columns:repeat(8,1fr);gap:6px}}
.led{{aspect-ratio:1;border-radius:50%;background:#1e2433;border:1px solid #2d3748;display:flex;align-items:center;justify-content:center;font-size:.5rem;color:#334155}}
.led.on{{background:#fbbf24;border-color:#f59e0b;box-shadow:0 0 8px #fbbf2455;color:#78350f}}
.bg{{display:grid;grid-template-columns:repeat(4,1fr);gap:8px}}
.taster{{background:#1e2433;border:1px solid #2d3748;border-radius:7px;padding:10px 0;text-align:center;font-size:.85rem;font-weight:600;color:#475569}}
.taster.on{{background:#1e3a5f;border-color:#3b82f6;color:#60a5fa;box-shadow:0 0 8px #3b82f644}}
.taster small{{display:block;font-size:.6rem;font-weight:400;margin-top:2px;color:#334155}}
.taster.on small{{color:#3b82f6}}
.logbox{{background:#0a0d14;border:1px solid #1e2433;border-radius:8px;padding:10px;height:160px;overflow-y:auto;font-family:monospace;font-size:.73rem}}
.logline{{color:#475569;margin-bottom:3px}}
.logline .lt{{color:#3b82f6}}
.logline .lts2{{color:#334155}}
.scene{{display:inline-block;margin-top:8px;padding:3px 10px;border-radius:20px;background:#1e2433;color:#64748b;font-size:.78rem}}
.irow{{font-size:.83rem;color:#475569;line-height:1.9}}
.irow strong{{color:#94a3b8}}
</style>
</head>
<body>
<header>
  <h1>SmartHome Dashboard <span>Tim 06</span></h1>
  <div><span class="dot"></span><span class="stxt">{STATUS_TEXT}</span></div>
</header>
<div class="grid">
  <div class="card" style="--a:#f97316">
    <div class="ctitle">Temperatura i vlažnost (DHT11)</div>
    <div class="big">{TEMP}<span>°C</span></div>
    <div class="sub">Vlažnost: <strong>{HUM}%</strong></div>
    <div class="lts">Zadnje: {LAST_TEMP}</div>
  </div>
  <div class="card" style="--a:#22c55e">
    <div class="ctitle">Releji u kuhinji</div>
    <div class="rrow"><span>Bojler</span><span class="badge {R1C}">{RELAY1}</span></div>
    <div class="rrow"><span>Klima</span><span class="badge {R2C}">{RELAY2}</span></div>
    <div class="lts">Zadnje: {LAST_RELAY}</div>
  </div>
  <div class="card" style="--a:#a855f7">
    <div class="ctitle">Boja ambientalnih svjetala</div>
    <div class="rgb-box" style="background:rgb({RR},{RG},{RB})">{RGB_EMPTY}</div>
    <div class="rgb-row">
      <div class="rgb-val"><div class="l">R</div><div class="n">{RR}</div></div>
      <div class="rgb-val"><div class="l">G</div><div class="n">{RG}</div></div>
      <div class="rgb-val"><div class="l">B</div><div class="n">{RB}</div></div>
    </div>
    <div class="scene">scena: {SCENE}</div>
  </div>
  <div class="card" style="--a:#fbbf24">
    <div class="ctitle">Status ambijentalnih svjetala</div>
    <div class="ll"><div>L0</div><div>L1</div><div>L2</div><div>L3</div><div>L4</div><div>L5</div><div>L6</div><div>L7</div></div>
    <div class="lg">{LEDS_HTML}</div>
    <div class="lts">Maska: {LED_MASK} &nbsp;|&nbsp; Zadnje: {LAST_PICO}</div>
  </div>
  <div class="card" style="--a:#3b82f6">
    <div class="ctitle">Tasteri (picoETF)</div>
    <div class="bg">{BTNS_HTML}</div>
    <div class="lts">Zadnje: {LAST_PICO}</div>
  </div>
  <div class="card" style="--a:#64748b">
    <div class="ctitle">Smarthome Assistant Status</div>
    <div class="irow">
      Uptime: <strong>{UPTIME}</strong><br>
      LED maska: <strong>0b{LED_BIN}</strong><br>
      RGB: <strong>({RR}, {RG}, {RB})</strong>
    </div>
    <div class="lts">Zadnje: {LAST_PICO}</div>
  </div>
</div>
<div class="card" style="--a:#334155">
  <div class="ctitle">MQTT log (osvježava se svake 2s)</div>
  <div class="logbox">{LOG_HTML}</div>
</div>
</body>
</html>"""

class Handler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        pass

    def do_GET(self):
        s = state
        r = s["rgb"]

        leds_html = "".join(
            f'<div class="led {"on" if (s["leds"] >> i) & 1 else ""}">{i}</div>'
            for i in range(8)
        )

        btns_html = ""
        for t in ["T1","T2","T3","T4"]:
            pressed = s["buttons"].get(t, 1) == 0
            cls = "taster on" if pressed else "taster"
            lbl = "pritisnut" if pressed else "slobodan"
            btns_html += f'<div class="{cls}">{t}<small>{lbl}</small></div>'

        log_html = "".join(
            f'<div class="logline"><span class="lts2">{e["ts"]}</span> '
            f'<span class="lt">{e["topic"]}</span> {e["msg"]}</div>'
            for e in s["log"]
        )

        dot_color = "#22c55e" if s["connected"] else "#ef4444"
        dot_glow  = "box-shadow:0 0 8px #22c55e88;" if s["connected"] else ""
        rgb_empty = "" if (r["r"] or r["g"] or r["b"]) else "nema signala"

        html = HTML_TEMPLATE.format(
            DOT_COLOR=dot_color, DOT_GLOW=dot_glow,
            STATUS_TEXT="Spojeno na MQTT broker" if s["connected"] else "Nije spojeno",
            TEMP=s["temperature"], HUM=s["humidity"], LAST_TEMP=s["last_temp"],
            RELAY1=s["relay1"], RELAY2=s["relay2"],
            R1C="bon" if s["relay1"]=="ON" else "boff",
            R2C="bon" if s["relay2"]=="ON" else "boff",
            LAST_RELAY=s["last_relay"],
            RR=r["r"], RG=r["g"], RB=r["b"], RGB_EMPTY=rgb_empty,
            SCENE=s["scene"],
            LEDS_HTML=leds_html, LED_MASK=s["leds"],
            LED_BIN=bin(s["leds"])[2:].zfill(8),
            BTNS_HTML=btns_html,
            UPTIME=s["uptime"], LAST_PICO=s["last_pico"],
            LOG_HTML=log_html,
        )

        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.end_headers()
        self.wfile.write(html.encode("utf-8"))

def run_server():
    HTTPServer(("0.0.0.0", 8080), Handler).serve_forever()

if __name__ == "__main__":
    threading.Thread(target=run_server, daemon=True).start()
    print(f"[HTTP] Dashboard: http://localhost:8080")

    client = mqtt.Client(client_id="dashboard-tim06")
    client.on_connect    = on_connect
    client.on_disconnect = on_disconnect
    client.on_message    = on_message

    print(f"[MQTT] Spajanje na {MQTT_BROKER}:{MQTT_PORT}...")
    client.connect(MQTT_BROKER, MQTT_PORT, keepalive=60)
    print("[INFO] Ctrl+C za izlaz")
    client.loop_forever()

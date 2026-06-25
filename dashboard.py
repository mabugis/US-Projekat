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
            for key in d:
                if isinstance(d[key], dict) and "Temperature" in d[key]:
                    state["temperature"] = d[key]["Temperature"]
                    state["humidity"]    = d[key].get("Humidity", "--")
                    state["last_temp"]   = now
                    break

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
<title>SmartHome Tim 06</title>
<style>
*{{box-sizing:border-box;margin:0;padding:0}}
body{{font-family:-apple-system,'Segoe UI',sans-serif;background:#f5f6f8;color:#1a1a1a;padding:20px 28px}}
header{{display:flex;justify-content:space-between;align-items:center;margin-bottom:28px;padding:20px 28px;background:#fff;border-radius:18px;box-shadow:0 2px 16px rgba(0,0,0,.05)}}
h1{{font-size:1.45rem;font-weight:700;letter-spacing:-.5px;color:#111}}
h1 span{{color:#cbd5e1;font-weight:300;font-size:.95rem;margin-left:10px;font-weight:400}}
.dot{{width:9px;height:9px;border-radius:50%;display:inline-block;margin-right:7px;background:{DOT_COLOR};{DOT_GLOW}}}
.stxt{{font-size:.85rem;color:#64748b;font-weight:500}}
.grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(280px,1fr));gap:20px;margin-bottom:20px}}
.card{{background:#fff;border:1px solid #eef1f5;border-radius:18px;padding:26px;box-shadow:0 2px 14px rgba(0,0,0,.04);transition:box-shadow .2s}}
.card:hover{{box-shadow:0 8px 28px rgba(0,0,0,.07)}}
.ctitle{{font-size:.72rem;text-transform:uppercase;letter-spacing:1.5px;color:#94a3b8;margin-bottom:20px;display:flex;align-items:center;gap:10px;font-weight:600}}
.ctitle::before{{content:'';width:4px;height:15px;border-radius:3px;background:var(--a,#3b82f6)}}
.big{{font-size:3.4rem;font-weight:800;letter-spacing:-3px;line-height:1;color:#0f172a}}
.big span{{font-size:1.4rem;color:#cbd5e1;font-weight:300;margin-left:2px}}
.sub{{color:#64748b;font-size:.9rem;margin-top:10px;font-weight:500}}
.sub strong{{color:#0f172a;font-weight:700}}
.lts{{font-size:.72rem;color:#cbd5e1;margin-top:14px;font-weight:500}}
.rrow{{display:flex;justify-content:space-between;align-items:center;padding:12px 0;border-bottom:1px solid #f1f5f9;font-weight:500;font-size:.92rem}}
.rrow:last-of-type{{border:none}}
.badge{{font-size:.72rem;font-weight:700;padding:4px 14px;border-radius:20px;letter-spacing:.5px}}
.boff{{background:#f1f5f9;color:#94a3b8}}
.bon{{background:#dcfce7;color:#16a34a;box-shadow:0 0 0 1px #bbf7d0}}
.rgb-box{{width:100%;height:80px;border-radius:14px;margin-bottom:14px;display:flex;align-items:center;justify-content:center;font-size:.78rem;color:rgba(255,255,255,.5);font-weight:500;box-shadow:inset 0 1px 2px rgba(0,0,0,.08)}}
.rgb-row{{display:flex;gap:10px}}
.rgb-val{{flex:1;text-align:center;padding:8px 0;background:#f8fafc;border-radius:10px}}
.rgb-val .l{{font-size:.68rem;color:#94a3b8;margin-bottom:5px;font-weight:600}}
.rgb-val .n{{font-size:1.05rem;font-weight:700;color:#0f172a}}
.ll{{display:grid;grid-template-columns:repeat(8,1fr);gap:7px;margin-bottom:7px}}
.ll div{{text-align:center;font-size:.6rem;color:#94a3b8;font-weight:600}}
.lg{{display:grid;grid-template-columns:repeat(8,1fr);gap:7px}}
.led{{aspect-ratio:1;border-radius:10px;background:#f1f5f9;border:1px solid #e2e8f0;display:flex;align-items:center;justify-content:center;font-size:.52rem;color:#cbd5e1;font-weight:600}}
.led.on{{background:#2563eb;border-color:#3b82f6;box-shadow:0 0 12px rgba(37,99,235,.35);color:#fff}}
.logbox{{background:#fafbfc;border:1px solid #eef1f5;border-radius:12px;padding:14px;height:170px;overflow-y:auto;font-family:'SF Mono',Consolas,monospace;font-size:.78rem}}
.logline{{color:#64748b;margin-bottom:4px;line-height:1.5}}
.logline .lt{{color:#2563eb;font-weight:500}}
.logline .lts2{{color:#cbd5e1}}
.scene{{display:inline-block;margin-top:12px;padding:5px 16px;border-radius:20px;background:#eff6ff;color:#2563eb;font-size:.8rem;font-weight:600}}
.irow{{font-size:.88rem;color:#64748b;line-height:2.1;font-weight:500}}
.irow strong{{color:#0f172a;font-weight:700}}
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
    <div class="big" id="tv">{TEMP}<span>°C</span></div>
    <div class="sub" id="hv">Vlažnost: <strong>{HUM}%</strong></div>
    <div class="lts" id="lt">Zadnje: {LAST_TEMP}</div>
  </div>
  <div class="card" style="--a:#22c55e">
    <div class="ctitle">Releji u kuhinji</div>
    <div class="rrow"><span>Bojler</span><span class="badge {R1C}" id="r1">{RELAY1}</span></div>
    <div class="rrow"><span>Klima</span><span class="badge {R2C}" id="r2">{RELAY2}</span></div>
    <div class="lts" id="lr">Zadnje: {LAST_RELAY}</div>
  </div>
  <div class="card" style="--a:#a855f7">
    <div class="ctitle">Boja ambientalnih svjetala</div>
    <div class="rgb-box" style="background:rgb({RR},{RG},{RB})">{RGB_EMPTY}</div>
    <div class="rgb-row">
      <div class="rgb-val"><div class="l">R</div><div class="n" id="rr">{RR}</div></div>
      <div class="rgb-val"><div class="l">G</div><div class="n" id="rg">{RG}</div></div>
      <div class="rgb-val"><div class="l">B</div><div class="n" id="rb">{RB}</div></div>
    </div>
    <div class="scene" id="sc">scena: {SCENE}</div>
  </div>
  <div class="card" style="--a:#fbbf24">
    <div class="ctitle">Status ambijentalnih svjetala</div>
    <div class="ll"><div>L0</div><div>L1</div><div>L2</div><div>L3</div><div>L4</div><div>L5</div><div>L6</div><div>L7</div></div>
    <div class="lg" id="lh">{LEDS_HTML}</div>
    <div class="lts" id="lm">Maska: {LED_MASK} &nbsp;|&nbsp; Zadnje: {LAST_PICO}</div>
  </div>
  <div class="card" style="--a:#64748b">
    <div class="ctitle">Smarthome Assistant Status</div>
    <div class="irow">
      <span id="up">Uptime: <strong>{UPTIME}</strong></span><br>
      <span id="lb">LED maska: <strong>0b{LED_BIN}</strong></span><br>
      <span id="rg2">RGB: <strong>({RR}, {RG}, {RB})</strong></span>
    </div>
    <div class="lts" id="lp2">Zadnje: {LAST_PICO}</div>
  </div>
</div>
<div class="card" style="--a:#334155">
  <div class="ctitle">MQTT log</div>
  <div class="logbox" id="lg">{LOG_HTML}</div>
</div>
<script>
async function poll(){try{let r=await fetch('/api/state'),d=await r.json()
document.querySelector('.dot').style.background=d.connected?'#22c55e':'#ef4444'
document.querySelector('.dot').style.boxShadow=d.connected?'0 0 8px #22c55e88':'none'
document.querySelector('.stxt').textContent=d.connected?'Spojeno na MQTT broker':'Nije spojeno'
document.getElementById('tv').innerHTML=d.temp+'<span>°C</span>'
document.getElementById('hv').innerHTML='Vlažnost: <strong>'+d.hum+'%</strong>'
document.getElementById('lt').textContent='Zadnje: '+d.last_temp
let r1=document.getElementById('r1'),r2=document.getElementById('r2')
r1.textContent=d.relay1;r1.className='badge '+d.r1c
r2.textContent=d.relay2;r2.className='badge '+d.r2c
document.getElementById('lr').textContent='Zadnje: '+d.last_relay
let bg=document.querySelector('.rgb-box')
bg.style.background='rgb('+d.rr+','+d.rg+','+d.rb+')'
bg.textContent=(d.rr||d.rg||d.rb)?'':'nema signala'
document.getElementById('rr').textContent=d.rr
document.getElementById('rg').textContent=d.rg
document.getElementById('rb').textContent=d.rb
document.getElementById('sc').textContent='scena: '+d.scene
document.getElementById('lh').innerHTML=d.leds_html
document.getElementById('lm').innerHTML='Maska: '+d.leds+' | Zadnje: '+d.last_pico
document.getElementById('lp2').textContent='Zadnje: '+d.last_pico
document.getElementById('up').innerHTML='Uptime: <strong>'+d.uptime+'</strong>'
document.getElementById('lb').innerHTML='LED maska: <strong>0b'+d.led_bin+'</strong>'
document.getElementById('rg2').innerHTML='RGB: <strong>('+d.rr+', '+d.rg+', '+d.rb+')</strong>'
document.getElementById('lg').innerHTML=d.log_html}catch(e){}}
setInterval(poll,1000);poll()
</script>
</body>
</html>"""

class Handler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        pass

    def _state_json(self):
        s = state
        r = s["rgb"]
        leds_html = "".join(
            f'<div class="led {"on" if (s["leds"] >> i) & 1 else ""}">{i}</div>'
            for i in range(8)
        )
        log_html = "".join(
            f'<div class="logline"><span class="lts2" style="color:#cbd5e1">{e["ts"]}</span> '
            f'<span class="lt" style="color:#2563eb">{e["topic"]}</span> {e["msg"]}</div>'
            for e in s["log"]
        )
        return {
            "temp": str(s["temperature"]), "hum": str(s["humidity"]),
            "last_temp": str(s["last_temp"]),
            "relay1": s["relay1"], "r1c": "bon" if s["relay1"]=="ON" else "boff",
            "relay2": s["relay2"], "r2c": "bon" if s["relay2"]=="ON" else "boff",
            "last_relay": str(s["last_relay"]),
            "rr": r["r"], "rg": r["g"], "rb": r["b"],
            "scene": str(s["scene"]),
            "leds_html": leds_html, "leds": s["leds"],
            "last_pico": str(s["last_pico"]),
            "uptime": str(s["uptime"]),
            "led_bin": bin(s["leds"])[2:].zfill(8),
            "log_html": log_html,
            "connected": s["connected"],
        }

    def do_GET(self):
        if self.path == "/api/state":
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Cache-Control", "no-cache")
            self.end_headers()
            self.wfile.write(json.dumps(self._state_json(), ensure_ascii=False).encode("utf-8"))
            return

        d = self._state_json()
        html = HTML_TEMPLATE.format(
            DOT_COLOR="#22c55e" if d["connected"] else "#ef4444",
            DOT_GLOW="box-shadow:0 0 8px #22c55e88;" if d["connected"] else "",
            STATUS_TEXT="Spojeno na MQTT broker" if d["connected"] else "Nije spojeno",
            TEMP=d["temp"], HUM=d["hum"], LAST_TEMP=d["last_temp"],
            RELAY1=d["relay1"], RELAY2=d["relay2"],
            R1C=d["r1c"], R2C=d["r2c"], LAST_RELAY=d["last_relay"],
            RR=d["rr"], RG=d["rg"], RB=d["rb"],
            RGB_EMPTY="" if (d["rr"] or d["rg"] or d["rb"]) else "nema signala",
            SCENE=d["scene"],
            LEDS_HTML=d["leds_html"], LED_MASK=d["leds"],
            LED_BIN=d["led_bin"],
            UPTIME=d["uptime"], LAST_PICO=d["last_pico"],
            LOG_HTML=d["log_html"],
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

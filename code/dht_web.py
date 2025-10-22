import time
import threading
import adafruit_dht
import board
from digitalio import DigitalInOut, Direction
from RPLCD.i2c import CharLCD
from flask import Flask, jsonify, render_template_string

# ======================================
# Shared Data
# ======================================
shared_data = {
    "temperature": None,
    "humidity": None,
    "mosfet_on": False,
    "displ": "",
    "mosfet_on_time": 0,  # seconds
    "summary": "Normal",
    "max_temp": None,
    "min_temp": None,
    "avg_temp": None
}

# Track readings for average calculation
temp_history = []

# ======================================
# Hardware Setup
# ======================================
dht_device = adafruit_dht.DHT22(board.D4)
mosfet_pin = DigitalInOut(board.D11)
mosfet_pin.direction = Direction.OUTPUT
lcd = CharLCD('PCF8574', 0x27)

# ======================================
# DHT22 + MOSFET Thread
# ======================================
def dht_thread():
    mosfet_start_time = None
    while True:
        try:
            # Simulated values for testing
            temperature = dht_device.temperature
            humidity = dht_device.humidity

            # Add temperature to history for avg/min/max
            if temperature is not None:
                temp_history.append(temperature)
                if len(temp_history) > 100:
                    temp_history.pop(0)
                shared_data["max_temp"] = max(temp_history)
                shared_data["min_temp"] = min(temp_history)
                shared_data["avg_temp"] = round(sum(temp_history) / len(temp_history), 1)

            # Update shared data
            shared_data["temperature"] = temperature
            shared_data["humidity"] = humidity

            # Control MOSFET
            if temperature is not None and temperature > 20:
                if not shared_data["mosfet_on"]:
                    mosfet_start_time = time.time()  # start timer
                mosfet_pin.value = True
                shared_data["mosfet_on"] = True
                shared_data["mosfet_on_time"] = int(time.time() - mosfet_start_time)
                shared_data["summary"] = "Cooling"
            else:
                mosfet_pin.value = False
                shared_data["mosfet_on"] = False
                shared_data["mosfet_on_time"] = 0
                mosfet_start_time = None
                shared_data["summary"] = "Normal"

            # Update LCD
            if temperature is not None and humidity is not None:
                lcd.cursor_pos = (0, 0)
                lcd.write_string(f"Temp:{temperature:.1f}C".ljust(16))
                lcd.cursor_pos = (1, 0)
                lcd.write_string(f"Hum:{humidity:.1f}% {shared_data['summary']}".ljust(16))
                shared_data["displ"] = f"Temp: {temperature:.1f}°C | Hum: {humidity:.1f}%"

        except KeyboardInterrupt:
            lcd.clear()
            lcd.write_string("Shutting Down...")
            mosfet_pin.value = False
            time.sleep(2)
            lcd.backlight_enabled = False
        except RuntimeError as e:
            print(f"DHT22 Error: {e.args[0]}")  # recoverable error
        time.sleep(2)

# ======================================
# Flask Web Server
# ======================================
app = Flask(__name__)

@app.route('/')
def index():
    return render_template_string(html_template)

@app.route('/data')
def data():
    return jsonify(shared_data)

# ======================================
# HTML Dashboard
# ======================================
html_template = """
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Raspberry Pi Sensor Dashboard</title>
  <style>
    body {
      font-family: "Segoe UI", sans-serif;
      background: #0f172a;
      color: #f1f5f9;
      display: flex;
      flex-direction: column;
      align-items: center;
      justify-content: center;
      min-height: 100vh;
      margin: 0;
    }
    h1 {
      color: #38bdf8;
      margin-bottom: 20px;
    }
    .container {
      display: flex;
      flex-wrap: wrap;
      justify-content: center;
      gap: 20px;
      max-width: 800px;
    }
    .card {
      background: #1e293b;
      border-radius: 12px;
      padding: 20px;
      text-align: center;
      width: 250px;
      box-shadow: 0 0 10px rgba(56, 189, 248, 0.3);
      transition: transform 0.2s;
    }
    .card:hover {
      transform: scale(1.05);
    }
    h2 {
      color: #7dd3fc;
      margin-bottom: 10px;
    }
    p {
      font-size: 1.1em;
    }
  </style>
</head>
<body>
  <h1>🌡️ Raspberry Pi Sensor Dashboard 🚚</h1>
  <div class="container">
    <div class="card">
      <h2>Temperature</h2>
      <p id="temperature">-- °C</p>
    </div>
    <div class="card">
      <h2>Humidity</h2>
      <p id="humidity">-- %</p>
    </div>
    <div class="card">
      <h2>MOSFET</h2>
      <p id="mosfet">OFF</p>
      <p id="mosfet_time">ON Time: 0 s</p>
      <p id="summary">Status: Normal</p>
    </div>
    <div class="card">
      <h2>Summary</h2>
      <p>Max Temp: <span id="max_temp">--</span> °C</p>
      <p>Min Temp: <span id="min_temp">--</span> °C</p>
      <p>Avg Temp: <span id="avg_temp">--</span> °C</p>
    </div>
    <div class="card" style="width: 520px;">
      <h2>LCD Display</h2>
      <p id="displ">Loading...</p>
    </div>
  </div>

  <script>
    async function updateData() {
      try {
        const res = await fetch('/data');
        const data = await res.json();

        document.getElementById('temperature').textContent = data.temperature ? data.temperature + " °C" : "N/A";
        document.getElementById('humidity').textContent = data.humidity ? data.humidity + " %" : "N/A";
        document.getElementById('mosfet').textContent = data.mosfet_on ? "ON" : "OFF";
        document.getElementById('mosfet_time').textContent = "ON Time: " + data.mosfet_on_time + " s";
        document.getElementById('summary').textContent = "Status: " + data.summary;
        document.getElementById('displ').textContent = data.displ || "No data";

        document.getElementById('max_temp').textContent = data.max_temp ?? "--";
        document.getElementById('min_temp').textContent = data.min_temp ?? "--";
        document.getElementById('avg_temp').textContent = data.avg_temp ?? "--";
      } catch (err) {
        console.error("Failed to fetch data:", err);
      }
    }

    setInterval(updateData, 1000);
    updateData();
  </script>
</body>
</html>
"""

# ======================================
# Main
# ======================================
if __name__ == '__main__':
    threading.Thread(target=dht_thread, daemon=True).start()
    app.run(host='0.0.0.0', port=5000, debug=False)

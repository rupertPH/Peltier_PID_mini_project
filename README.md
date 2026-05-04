# 🌡️ PID Temperature Control System (Arduino + Python + PyQt6)

![Python](https://img.shields.io/badge/Python-3.10+-blue.svg)
![Arduino](https://img.shields.io/badge/Arduino-UNO-green.svg)
![PyQt6](https://img.shields.io/badge/GUI-PyQt6-orange.svg)
![License](https://img.shields.io/badge/License-MIT-lightgrey.svg)

A real-time **closed-loop temperature control system** using Arduino, a Peltier module, and a Python-based PID controller with a graphical interface.

---

## 📌 Overview

This project implements an automated temperature regulation system:

- **DS18B20 sensor** measures temperature
- **Arduino** reads and transmits data via Serial
- **Python PID controller** computes control signal
- **Power supply** drives the Peltier module
- **PyQt6 GUI** provides live control and visualization

---

## 🔁 System Architecture


DS18B20 → Arduino → Serial → Python PID → Power Supply → Peltier → System → DS18B20


---

## 🧠 Features

✔ PID temperature regulation  
✔ Real-time plotting (Matplotlib)  
✔ PyQt6 graphical interface  
✔ CSV data logging  
✔ Peltier power control (0–100%)  
✔ Fan ON/OFF control  
✔ Serial communication handling  

---

## 🧩 Project Structure


project/
│
├── Arduino/
│ └── Basic.ino # DS18B20 + fan control
│
├── python/
│ ├── main_gui.py # PyQt6 GUI application
│ ├── functions_PID.py # PID logic + serial + logger
│
└── README.md


---

## ⚙️ Requirements

### Hardware
- Arduino UNO (or compatible board)
- DS18B20 temperature sensor + 4.7kΩ resistor
- Peltier module
- Laboratory power supply (serial-controlled)
- Cooling fan (digital output)

### Software

pip install pyserial numpy matplotlib simple-pid pyqt6

🔌 Arduino Firmware
Functionality
Reads temperature from DS18B20
Sends temperature via Serial
Controls fan via serial commands
Serial Commands
Command	Function
F1	Fan ON
F0	Fan OFF
Example output
23.56
23.61
23.70
🧮 PID Controller

PID implemented in Python using simple-pid:

pid = PID(-Kp, -Ki, -Kd, setpoint=T_set)
pid.output_limits = (0, 1)
Output range: 0 → 1
Mapped to power supply voltage/current control
⚡ Power Supply Control

Commands sent via Serial:

ISET1:4.80
VSET1:6.50
OUT1
ISET1 → current limit
VSET1 → voltage setpoint
OUT1 → enable output
🖥️ GUI (PyQt6)
Features
Set target temperature (T_set)
Start / Stop control loop
Fan toggle
Live temperature plot
Export data to CSV
Real-time log console
📊 Data Logging

Recorded values:

time [s]
temperature [°C]
PID output [0–1]

Example CSV:

time_s,temperature_C,power_0_1
0.0,24.30,0.45
1.0,24.55,0.48
2.0,24.70,0.52
▶️ How to Run
1. Upload Arduino firmware
Arduino IDE → Basic.ino → Upload
2. Start Python GUI
python main_gui.py
⚠️ Configuration

Set correct serial ports:

ARDUINO_PORT = "COM11"
PSU_PORT = "COM15"
🚀 Future Improvements
Auto-tuning PID (Ziegler–Nichols method)
Kalman filtering for sensor noise reduction
SQLite database logging
Web dashboard (Flask / FastAPI)
Multi-sensor DS18B20 support
Thermal safety cutoff system

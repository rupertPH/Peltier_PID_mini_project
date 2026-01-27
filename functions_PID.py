
import serial
from serial.tools import list_ports
import time
import numpy as np
import matplotlib.pyplot as plt
from simple_pid import PID
import threading

### GLOBAL PARAMETERS ###
BAUD = 9600
U_MAX = 12.0
I_MAX = 4.8


# setup
def check_serial_port(port: str) -> bool:
    """
    Checks if given serial port exists in the system.

    :param port: Port to be checked
    :type port: str
    :return: List of available ports
    :rtype: bool
    """
    available_ports = [p.device for p in list_ports.comports()]
    print("[INFO] Available ports:", available_ports)
    return port in available_ports


def setup_arduino(port: str, baud=BAUD, timeout=1):
    """
    Sets up Arduino serial connection with port validation.

    :param port: Port with arudino
    :type port: str
    :param baud: Rate in symbols per second
    :param timeout: Reading data timeout
    """
    if not check_serial_port(port):
        raise RuntimeError(f"[ERROR] Arduino port '{port}' not found")

    try:
        ser = serial.Serial(port=port, baudrate=baud, timeout=timeout)
        print(f"[INFO] Arduino connected on {port}")
        return ser
    except serial.SerialException as e:
        raise RuntimeError(f"[ERROR] Failed to open Arduino port {port}: {e}")


def setup_power_supp(port: str, baud=BAUD, timeout=1):
    """
    Sets up power supply serial connection with port validation.

    :param port: Opis
    :type port: str
    :param baud: Opis
    :param timeout: Opis
    """
    if not check_serial_port(port):
        raise RuntimeError(f"[ERROR] Power supply port '{port}' not found")

    try:
        ser = serial.Serial(port=port, baudrate=baud, timeout=timeout)
        print(f"[INFO] Power supply connected on {port}")
        return ser
    except serial.SerialException as e:
        raise RuntimeError(f"[ERROR] Failed to open power supply port {port}: {e}")


def close_port_connection(ser):
    """
    Closes serial connections saftely

    :param ser: Port to be closed
    """
    if ser and ser.is_open:
        ser.close()
        print("[INFO] Port closed.")

def read_temp(ser):
    """
    Reads temperature from Arduino via serial.
    Returns None if no valid data.

    :param ser: Port with Arduino
    :return: Temp. value from termometer connected to Arduino / None if data is invalid
    :rtype: float | None
    """
    if ser.in_waiting == 0:
        return None

    try:
        line = ser.readline().decode(errors="ignore").strip()
        return float(line)
    except ValueError:
        print(f"[ERROR] Invalid temperature data: {line}")
        return None


def set_power(ser, power: float):
    """
    Sets power (voltage and current) of programmable power supply connected to Peltier element

    :param ser: Sereial for power supply
    :param power: value from 0 - 1; 1 -> u_max / i_max , 0 -> u=0 / i=0 [V] / [A]
    :type power: float
    """
    power = max(0.0, min(1.0, power))
    current = I_MAX
    current = round(current, 2)
    voltage = round(power * U_MAX, 2)
    cmd = f"ISET1:{current}"
    ser.write((cmd + "\n").encode())
    time.sleep(0.05)
    cmd = f"VSET1:{voltage}"
    ser.write((cmd + "\n").encode())
    time.sleep(0.05)
    ser.write(("OUT1" + "\n").encode())
    time.sleep(0.05)

def read_power(ser):
    """
    Reads power parameter value. Function used for debuging

    :param ser: serial for power supply
    :return: volts on power supply
    :rtype: float | None
    """
    ser.write(b"READ?\n")
    try:
        line = ser.readline().decode().strip()
        return float(line)
    except ValueError:
        print(f"[ERROR] Invalid power data: {line}")
        return None

def pid_loop(ser_arduino, ser_psu, Kp, Ki, Kd, T_set, logger, running: threading.Event):
    '''
    Conducts PID loop while the program is running and "Start" has been selected
    
    :param ser_arduino: Port with Arduino (termometer)
    :param ser_psu: Port with power supply connected to Pelrier element
    :param Kp: PID proportional term
    :param Ki: PID integral term
    :param Kd: PID derivative term
    :param T_set: temp. value set by user
    :param logger: data storage and handling
    :param running: flag for starting PID loop
    :type running: threading.Event
    '''
    pid = PID(-Kp, -Ki, -Kd, setpoint=T_set)
    pid.sample_time = 1
    pid.output_limits = (0, 1)
    t0 = time.time()

    while running.is_set():
        try:
            temp = read_temp(ser_arduino)
            if temp is None:
                time.sleep(0.05)
                continue

            power = pid(temp)
            set_power(ser_psu, power)

            print(f"T={temp:.2f} °C | P={power:.2f}")

            t = time.time() - t0
            logger.add(t, temp, power)

        except Exception as e:
            print(f"[ERROR] PID loop failed: {e}")
            running.clear()



def init_hardware():
    """
    Hardware (Arduino, power supply) set up. Connecting ports.
    Note: before use make sure both arduono nad power supply are connected via right ports.
    """
    ARDUINO_PORT = "COM11"
    check_serial_port(ARDUINO_PORT)
    PSU_PORT = "COM15"
    check_serial_port(PSU_PORT)

    ser_arduino = setup_arduino(ARDUINO_PORT)
    ser_psu = setup_power_supp(PSU_PORT)
    return ser_arduino, ser_psu

def shut_down_hardware(ser_arduino, ser_psu):
    """
    Hardware safe shut down. Setting power to 0, turning fan off, disconnecting ports.
    
    :param ser_arduino: Port with Arduino
    :param ser_psu: Port with power supply (Peltier)
    """
    try:
        set_power(ser_psu, 0)
    except Exception:
        pass
    ser_arduino.write("F0".encode())
    close_port_connection(ser_arduino)
    close_port_connection(ser_psu)


### COLLECTING DATA ###

class DataLogger:
    '''
    Class for data storage (temp. and power level) and handling (saving to a file).
    '''

    def __init__(self):
        self.time_log = []
        self.temp_log = []
        self.power_log = []

    def add(self, time, temp, power):
        self.time_log.append(time)
        self.temp_log.append(temp)
        self.power_log.append(power)
    
    def clear(self):
        self.time_log.clear()
        self.temp_log.clear()
        self.power_log.clear()

    def save_csv(self, filename):
        import csv
        with open(filename, "w", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(["time_s", "temperature_C", "power_0_1"])
            for row in zip(self.time_log, self.temp_log, self.power_log):
                writer.writerow(row)












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


###

### LOGIC ###

# setup
def check_serial_port(port: str) -> bool:
    """
    Docstring for check_serial_port
    Checks if given serial port exists in the system.

    :param port: Opis
    :type port: str
    :return: Opis
    :rtype: bool
    """
    available_ports = [p.device for p in list_ports.comports()]
    print("[INFO] Available ports:", available_ports)
    return port in available_ports


def setup_arduino(port: str, baud=BAUD, timeout=1):
    """
    Docstring for setup_arduino
    Sets up Arduino serial connection with port validation.

    :param port: Opis
    :type port: str
    :param baud: Opis
    :param timeout: Opis
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
    Docstring for setup_power_supp
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
    Docstring for close_port_connection

    :param ser: Opis
    """
    if ser and ser.is_open:
        ser.close()
        print("[INFO] Port closed.")


#


def set_temp_level(T_min, T_max, value) -> float:
    """
    Docstring for set_temp_level
    Reads temperature setpoint from console with validation.

    :param T_min: Opis
    :param T_max: Opis
    :return: Opis
    :rtype: float
    """
    while True:
        try:
            if T_min <= value <= T_max:
                return value
            print(f"[ERROR] Temperature must be in range {T_min}-{T_max} °C")
        except ValueError:
            print("[ERROR] Invalid number")


def read_temp(ser):
    """
    Docstring for read_temp
    Reads temperature from Arduino via serial.
    Returns None if no valid data.

    :param ser: Opis
    :return: Opis
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
    Docstring for set_power

    :param ser: sereial for power supply
    :param power: value from 0 - 1; 1 -> u_max, 0 -> u=0 [V]
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
    Docstring for read_power

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


def autotune_pid_step_response(
        ser_arduino,
        ser_psu,
        power_step: float = 0.3,
        sample_time: float = 1.0,
        duration: float = 600.0,
        T_max: float = 80.0,
):
    set_power(ser_psu, 0.0)
    time.sleep(30)

    set_power(ser_psu, power_step)
    t0 = time.time()
    data = []

    while time.time() - t0 < duration:
        temp = read_temp(ser_arduino)
        if temp is None:
            time.sleep(0.05)
            continue

        if temp > T_max:
            set_power(ser_psu, 0.0)
            raise RuntimeError("[SAFETY] Temperature exceeded T_max")

        data.append((time.time() - t0, temp))
        time.sleep(sample_time)

    set_power(ser_psu, 0.0)

    data = np.array(data)
    t = data[:, 0]
    T = data[:, 1]

    T0 = T[0]
    Tend = T[-1]
    dT = Tend - T0

    if abs(dT) <= 0:
        raise RuntimeError("[ERROR] Invalid step response (no temperature change)")

    K = abs(dT) / power_step
    T63 = T0 + 0.63 * dT

    # wybór L i T63_time zależnie od kierunku zmiany temperatury
    if dT > 0:  # temperatura rośnie
        L = t[np.where(T > T0 + 0.05 * dT)][0]
        T63_time = t[np.where(T > T63)][0]
    else:       # temperatura spada (odwrócony układ)
        L = t[np.where(T < T0 + 0.05 * dT)][0]
        T63_time = t[np.where(T < T63)][0]

    Tau = T63_time - L

    # Cohen-Coon
    Kp = Tau / (K * L)
    Ti = 2.0 * L
    Td = 0.5 * L

    Ki = Kp / Ti
    Kd = Kp * Td

    return Kp, Ki, Kd



def pid_loop(ser_arduino, ser_psu, Kp, Ki, Kd, T_set, logger, running: threading.Event):
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






### COLLECTING DATA ###

class DataLogger:
    """
    Docstring for DataLogger
    """

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


def init_hardware():
    ARDUINO_PORT = "COM11"
    check_serial_port(ARDUINO_PORT)
    PSU_PORT = "COM15"
    check_serial_port(PSU_PORT)

    ser_arduino = setup_arduino(ARDUINO_PORT)
    ser_psu = setup_power_supp(PSU_PORT)
    return ser_arduino, ser_psu

def shut_down_hardware(ser_arduino, ser_psu):
    try:
        set_power(ser_psu, 0)
    except Exception:
        pass
    ser_arduino.write("F0".encode())
    close_port_connection(ser_arduino)
    close_port_connection(ser_psu)








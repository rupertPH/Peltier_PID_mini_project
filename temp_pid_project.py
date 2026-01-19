import serial
from serial.tools import list_ports
import time
import numpy as np
import matplotlib.pyplot as plt
from simple_pid import PID

### GLOBAL PARAMETERS ###
BAUD = 9600
U_MAX = 12.00
I_MAX = 2.8 #A


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


def set_temp_level(T_min=0.0, T_max=100.0) -> float:
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
            value = float(input("[INPUT] Set temperature [°C]: "))
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
    voltage = power * U_max
    current = round(current, 2)
    cmd = f"ISET1:{current}"
    ser.write((cmd + "\n").encode())
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
    """
    Docstring for autotune_pid_step_response

    :param ser_arduino: Opis
    :param ser_psu: Opis
    :param power_step: Opis
    :type power_step: float
    :param sample_time: Opis
    :type sample_time: float
    :param duration: Opis
    :type duration: float
    :param T_max: Opis
    :type T_max: float
    """

    # --- 1. Initial conditions ---
    set_power(ser_psu, 0.0)
    time.sleep(30)

    # --- 2. Apply step ---
    set_power(ser_psu, power_step)
    t0 = time.time()
    data = []

    while time.time() - t0 < duration:
        temp = read_temp(ser_arduino)
        if temp is None:
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

    # --- 3. FOPDT estimation ---
    T0 = T[0]
    Tend = T[-1]
    dT = Tend - T0

    if dT <= 0:
        raise RuntimeError("[ERROR] Invalid step response (no temperature rise)")

    K = dT / power_step
    T63 = T0 + 0.63 * dT

    L = t[np.where(T > T0 + 0.05 * dT)][0]
    T63_time = t[np.where(T > T63)][0]
    Tau = T63_time - L

    # --- 4. Cohen-Coon tuning ---
    Kp = Tau / (K * L)
    Ti = 2.0 * L
    Td = 0.5 * L

    Ki = Kp / Ti
    Kd = Kp * Td

    # --- 5. Plot ---
    plt.figure()
    plt.plot(t, T, label="Temperature")
    plt.axhline(T63, linestyle="--", label="63%")
    plt.xlabel("Time [s]")
    plt.ylabel("Temperature [°C]")
    plt.legend()
    plt.grid()
    plt.show()

    return Kp, Ki, Kd


def pid_loop(ser_arduino, ser_psu, Kp, Ki, Kd, T_set, logger):
    """
    Docstring for pid_function

    :param ser_arduino: Opis
    :param ser_psu: Opis
    :param Kp: Opis
    :param Ki: Opis
    :param Kd: Opis
    :param T_set: Opis
    """
    pid = PID(Kp, Ki, Kd, setpoint=T_set)
    pid.sample_time = 1
    pid.output_limits = (0, 1)
    plotter = Plotter(T_set)
    t0 = time.time()
    try:
        while True:
            temp = read_temp(ser_arduino)
            if temp is None:
                continue
            power = pid(temp)
            set_power(ser_psu, power)
            print(f"T={temp:.2f} °C | P={power:.2f}")
            t = time.time() - t0
            logger.add(t, temp, power)
            plotter.update(t, temp, power)
    except KeyboardInterrupt:
        print("[INFO] PID stopped by user")
    finally:
        plotter.close()


###

### PLOTTING ###

class Plotter:
    """
    Docstring for Plotter
    """

    def __init__(self, T_set=None):
        self.T_set = T_set
        plt.ion()

        self.temp = []
        self.power = []
        self.time = []

        self.fig, self.ax_temp = plt.subplots()
        self.ax_power = self.ax_temp.twinx()

        self.line_temp, = self.ax_temp.plot([], [], label="Temperture [° C]")
        self.line_power, = self.ax_power.plot([], [], label="Power (0-1)")

        if T_set is not None:
            self.ax_temp.axhline(T_set, linestyle="--", label="T_set")

        self.ax_temp.set_xlabel("Time [s]")
        self.ax_temp.set_ylabel("Temperature [°C]")
        self.ax_power.set_ylabel("Power (0-1)")

        self.ax_temp.legend(loc="upper left")
        self.ax_power.legend(loc="upper right")

        self.ax_temp.grid()

    def update(self, t, temp, power):
        self.time.append(t)
        self.temp.append(temp)
        self.power.append(power)

        self.line_temp.set_data(self.time, self.temp)
        self.line_power.set_data(self.time, self.power)

        self.ax_temp.relim()
        self.ax_power.autoscale_view()

        plt.pause(0.05)

    def close(self):
        plt.ioff()
        plt.show()


###

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


def main():
    ARDUINO_PORT = "COM12"
    check_serial_port(ARDUINO_PORT)
    PSU_PORT = "COM15"
    check_serial_port(PSU_PORT)

    try:
        ser_arduino = setup_arduino(ARDUINO_PORT)
        ser_psu = setup_power_supp(PSU_PORT)

        T_set = set_temp_level()

        # autotuning
        use_atuotune = input("Run PID autotuning? [y/n]:").lower() == "y"
        if use_atuotune:
            print("[INFO] Running PID autotunning...")
            Kp, Ki, Kd = autotune_pid_step_response(ser_arduino, ser_psu, power_step=0.3, duration=600,
                                                    T_max=T_set + 10)
            print(f"[INFO] Autotune results: Kp={Kp:.3f}, Ki={Ki:.3f}, Kd={Kd:.3f}")
        else:
            # default values
            Kp = -0.5
            Ki = -0.05
            Kd = -0.0

        print("[INFO] PID loop starting...")
        print("[INFO] Initializing Data logger...")
        logger = DataLogger()
        pid_loop(ser_arduino, ser_psu, Kp, Ki, Kd, T_set, logger)


    except KeyboardInterrupt:
        print("[INFO] Program interupted by user")

    except Exception as e:
        print(f"[ERROR] {e}")

    finally:
        try:
            set_power(ser_psu, 0)
            ser_psu.write(("OUT0" + "\n").encode())
        except Exception:
            pass

        close_port_connection(ser_arduino)
        close_port_connection(ser_psu)
        print("[INFO] Power off. Ports closed.")
        logger.clear()
        print("[INFO] Data logger cleared.")


if __name__ == "__main__":
    main()


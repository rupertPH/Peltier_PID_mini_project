import sys
import numpy as np
import time
import threading

from functions_PID import (
    DataLogger,
    init_hardware,
    shut_down_hardware,
    pid_loop, set_temp_level
)

from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget,
    QPushButton, QVBoxLayout, QHBoxLayout,
    QTextEdit, QFileDialog, QDoubleSpinBox, QLabel
)
from PyQt6.QtCore import QTimer
from PyQt6.QtGui import QTextCursor

from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure


# ------------------------------------------------------------
# Przechwytywanie print() do okna logów
# ------------------------------------------------------------
class EmittingStream:
    def __init__(self, text_edit):
        self.text_edit = text_edit

    def write(self, text):
        self.text_edit.moveCursor(QTextCursor.MoveOperation.End)
        self.text_edit.insertPlainText(text)

    def flush(self):
        pass


# ------------------------------------------------------------
# Widget z wykresem matplotlib
# ------------------------------------------------------------
class PlotWidget(QWidget):
    def __init__(self, logger, T_set=None):
        super().__init__()

        self.logger = logger
        self.T_set = T_set

        self.figure = Figure()
        self.canvas = FigureCanvas(self.figure)
        self.ax_temp = self.figure.add_subplot(111)
        #self.ax_power = self.ax_temp.twinx()

        layout = QVBoxLayout()
        layout.addWidget(self.canvas)
        self.setLayout(layout)

        self.line_temp, = self.ax_temp.plot([], [], label="Temperature [°C]")
        #self.line_power, = self.ax_power.plot([], [], label="Power (0-1)")

        if T_set is not None:
            self.ax_temp.axhline(T_set, linestyle="--", label="T_set")

        self.ax_temp.set_title("Live plot")
        self.ax_temp.set_xlabel("Time [s]")
        self.ax_temp.set_ylabel("Temperature [°C]")
        #self.ax_power.set_ylabel("Power (0-1)")

        self.ax_temp.legend(loc="upper left")
        #self.ax_power.legend(loc="upper right")
        self.ax_temp.grid()

    def update_plot(self):
        if not self.logger or not self.logger.time_log:
            return

        t = self.logger.time_log
        temp = self.logger.temp_log
        #power = self.logger.power_log

        self.line_temp.set_data(t, temp)
        #self.line_power.set_data(t, power)

        self.ax_temp.relim()
        #self.ax_power.relim()

        self.ax_temp.autoscale_view()
        #self.ax_power.autoscale_view()

        self.canvas.draw_idle()



# ------------------------------------------------------------
# Główne okno
# ------------------------------------------------------------
class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()

        self.setWindowTitle("PyQt6 GUI – live plot")

        self.logger = DataLogger()   # <- poprawka: logger jest od razu

        # --- Centralny widget
        central = QWidget()
        self.setCentralWidget(central)

        # --- Wykres
        self.plot_widget = PlotWidget(self.logger, self.T_set)

        # --- Logi
        self.log_box = QTextEdit()
        self.log_box.setReadOnly(True)
        self.log_box.setMaximumHeight(150)
        sys.stdout = EmittingStream(self.log_box)
        # Temp set
        self.temp_label = QLabel("Set temperature [C]")
        self.temp_input = QDoubleSpinBox()
        self.temp_input.setRange(18.0, 28.0)
        self.temp_input.setDecimals(2)
        self.temp_input.setSingleStep(.5)
        self.temp_input.setValue(25.00)
        self.T_set = self.temp_input
        # --- Przyciski

        self.start_btn = QPushButton("Start")
        self.stop_btn = QPushButton("Stop")
        self.fan_btn = QPushButton("Fan ON")
        self.save_btn = QPushButton("Save to a file")
        #self.autotune_btn = QPushButton("Autotune PID")


        self.start_btn.clicked.connect(self.start)
        self.stop_btn.clicked.connect(self.stop)
        self.fan_btn.clicked.connect(self.toggle_fan)
        self.save_btn.clicked.connect(self.save_to_file)
        #self.autotune_btn.clicked.connect(self.autotune)

        btn_layout = QHBoxLayout()
        btn_layout.addWidget(self.start_btn)
        btn_layout.addWidget(self.stop_btn)
        btn_layout.addWidget(self.fan_btn)
        btn_layout.addWidget(self.save_btn)
        #btn_layout.addWidget(self.autotune_btn)
        temp_layout = QHBoxLayout()
        temp_layout.addWidget(self.temp_label)
        temp_layout.addWidget(self.temp_input)


        main_layout = QVBoxLayout()
        main_layout.addLayout(temp_layout)
        main_layout.addWidget(self.plot_widget)
        main_layout.addLayout(btn_layout)
        main_layout.addWidget(self.log_box)

        central.setLayout(main_layout)

        # --- Timer do live plot
        self.timer = QTimer()
        self.timer.timeout.connect(self.plot_widget.update_plot)

        self.fan_on = False

        self.running = threading.Event()
        self.thread = None

        #self.autotune_thread = None
        #self.autotuning = threading.Event()

        self.Kp = -0.5
        self.Ki = -0.05
        self.Kd = -0.0

        self.T_set = 30   


    def start(self):
        print("Start pressed")
        self.T_set = self.temp_input.value()
        print(f"[INFO] T_set = {self.T_set:2f}")
        self.temp_input.setEnabled(False)
        if self.thread is not None and self.thread.is_alive():
            return

        #if self.autotuning.is_set():
            #print("[WARN] Autotuning in progress")
            #return

        # 1) inicjalizacja sprzętu
        self.ser_arduino, self.ser_psu = init_hardware()

        # 2) ustawienia PID
        T_set = self.T_set
        Kp, Ki, Kd = self.Kp, self.Ki, self.Kd

        # 3) uruchom logger
        self.logger = DataLogger()
        self.plot_widget.logger = self.logger  # ważne!

        # 4) ustaw flagę running
        self.running.set()

     # 5) uruchom wątek PID
        self.thread = threading.Thread(
            target=pid_loop,
            args=(self.ser_arduino, self.ser_psu, Kp, Ki, Kd, T_set, self.logger, self.running),
            daemon=True
        )
        self.thread.start()

        # 6) uruchom timer wykresu
        self.timer.start(100)



    def stop(self):
        print("[INFO] Stop pressed")

        if self.running.is_set():
            self.running.clear()

        if self.thread is not None:
            self.thread.join(timeout=5)
            self.thread = None

        if self.timer.isActive():
            self.timer.stop()

        # zamknij sprzęt
        try:
            if self.ser_arduino or self.ser_psu:
                shut_down_hardware(self.ser_arduino, self.ser_psu)
        except Exception as e:
            print(f"[WARN] Hardware shutdown failed: {e}")

        # wyczyść logger
        if self.logger is not None:
            self.logger.clear()

        self.temp_input.setEnabled(True)

    def toggle_fan(self):
        self.fan_on = not self.fan_on
        state = "ON" if self.fan_on else "OFF"
        self.fan_btn.setText(f"Fan {state}")
        print(f"Fan turned {state}")
        if state == "ON":
            self.ser_arduino.write("F1".encode())
        else:
            self.ser_arduino.write("F0".encode())

    def save_to_file(self):
        if not self.logger.time_log:
            print("[WARN] Logger is empty")
            return

        filename, _ = QFileDialog.getSaveFileName(
            self,
            "Save data to CSV",
            "",
            "CSV files (*.csv);;All files (*)"
        )
        if not filename:
            return

        self.logger.save_csv(filename)
        print(f"[INFO] Data saved to {filename}")


    # def autotune(self):
    #     if self.autotune_thread and self.autotune_thread.is_alive():
    #         return
    #
    #     if self.running.is_set():
    #         print("[WARN] Stop PID before autotune")
    #         return
    #
    #     print("[INFO] Starting PID autotuning...")
    #     self.autotuning.set()
    #
    #     self.autotune_thread = threading.Thread(
    #         target=self._autotune_worker,
    #         daemon=True
    #     )
    #     self.autotune_thread.start()


    # def _autotune_worker(self):
    #     time.sleep(1)  # dummy
    #     print("[INFO] Autotune done")
    #     self.autotuning.clear()


    def closeEvent(self, event):
        self.stop()
        event.accept()


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWindow()
    window.resize(900, 600)
    window.show()
    sys.exit(app.exec())

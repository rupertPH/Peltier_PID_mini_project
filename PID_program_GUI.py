import sys
import numpy as np
import time

from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget,
    QPushButton, QVBoxLayout, QHBoxLayout,
    QTextEdit, QFileDialog
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
    def __init__(self):
        super().__init__()

        self.figure = Figure()
        self.canvas = FigureCanvas(self.figure)
        self.ax = self.figure.add_subplot(111)

        layout = QVBoxLayout()
        layout.addWidget(self.canvas)
        self.setLayout(layout)

        self.x = []
        self.y = []
        self.t0 = time.time()

        self.ax.set_title("Live plot")
        self.ax.set_xlabel("Time [s]")
        self.ax.set_ylabel("Value")
        self.line, = self.ax.plot([], [], lw=2)

    def update_plot(self):
        t = time.time() - self.t0
        value = np.sin(t)

        self.x.append(t)
        self.y.append(value)

        self.line.set_data(self.x, self.y)
        self.ax.relim()
        self.ax.autoscale_view()

        self.canvas.draw_idle()


# ------------------------------------------------------------
# Główne okno
# ------------------------------------------------------------
class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()

        self.setWindowTitle("PyQt6 GUI – live plot")

        # --- Centralny widget
        central = QWidget()
        self.setCentralWidget(central)

        # --- Wykres
        self.plot_widget = PlotWidget()

        # --- Logi
        self.log_box = QTextEdit()
        self.log_box.setReadOnly(True)
        self.log_box.setMaximumHeight(150)

        sys.stdout = EmittingStream(self.log_box)

        # --- Przyciski
        self.start_btn = QPushButton("Start")
        self.stop_btn = QPushButton("Stop")
        self.fan_btn = QPushButton("Fan OFF")
        self.save_btn = QPushButton("Save to a file")

        self.start_btn.clicked.connect(self.start)
        self.stop_btn.clicked.connect(self.stop)
        self.fan_btn.clicked.connect(self.toggle_fan)
        self.save_btn.clicked.connect(self.save_to_file)

        # --- Layout przycisków
        btn_layout = QHBoxLayout()
        btn_layout.addWidget(self.start_btn)
        btn_layout.addWidget(self.stop_btn)
        btn_layout.addWidget(self.fan_btn)
        btn_layout.addWidget(self.save_btn)

        # --- Layout główny
        main_layout = QVBoxLayout()
        main_layout.addWidget(self.plot_widget)
        main_layout.addLayout(btn_layout)
        main_layout.addWidget(self.log_box)

        central.setLayout(main_layout)

        # --- Timer do live plot
        self.timer = QTimer()
        self.timer.timeout.connect(self.plot_widget.update_plot)

        self.fan_on = False

    # --------------------------------------------------------
    def start(self):
        print("Start pressed")
        self.timer.start(100)  # ms

    def stop(self):
        print("Stop pressed")
        self.timer.stop()

    def toggle_fan(self):
        self.fan_on = not self.fan_on
        state = "ON" if self.fan_on else "OFF"
        self.fan_btn.setText(f"Fan {state}")
        print(f"Fan turned {state}")

    def save_to_file(self):
        filename, _ = QFileDialog.getSaveFileName(
            self,
            "Save data",
            "",
            "Text files (*.txt);;All files (*)"
        )

        if filename:
            with open(filename, "w") as f:
                for x, y in zip(self.plot_widget.x, self.plot_widget.y):
                    f.write(f"{x:.3f}\t{y:.3f}\n")

            print(f"Data saved to {filename}")


# ------------------------------------------------------------
# Start aplikacji
# ------------------------------------------------------------
if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWindow()
    window.resize(900, 600)
    window.show()
    sys.exit(app.exec())

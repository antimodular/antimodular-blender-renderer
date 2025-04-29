import sys
import os
import json
import platform
import subprocess

from PySide6.QtWidgets import (
    QApplication,
    QMainWindow,
    QLabel,
    QFileDialog,
    QMessageBox,
    QMenuBar,
    QMenu,
    QWidget,
    QVBoxLayout,
)
from PySide6.QtGui import QAction
from PySide6.QtCore import Qt

CONFIG_FILE = "config.json"


def load_config():
    if not os.path.exists(CONFIG_FILE):
        default_config = {"blender_path": ""}
        save_config(default_config)
        return default_config
    else:
        with open(CONFIG_FILE, "r") as f:
            return json.load(f)


def save_config(data):
    with open(CONFIG_FILE, "w") as f:
        json.dump(data, f, indent=4)


class DragDropWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Blender Drag & Drop Launcher")
        self.resize(500, 300)

        # Central widget and layout
        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        layout = QVBoxLayout()
        central_widget.setLayout(layout)

        # Label
        self.label = QLabel("")
        self.label.setAlignment(Qt.AlignCenter)
        self.label.setStyleSheet(
            "border: 2px dashed gray; font-size: 16px; padding: 40px;"
        )
        layout.addWidget(self.label)

        # Drag and drop
        self.setAcceptDrops(True)

        # Config
        self.config = load_config()

        # Menu
        self.setup_menu()

        # Check Blender
        self.check_blender_installation()

    def setup_menu(self):
        menu_bar = self.menuBar()
        setup_menu = menu_bar.addMenu("Setup")

        choose_blender_action = QAction("Choose Blender Path", self)
        choose_blender_action.triggered.connect(self.choose_blender_path)

        setup_menu.addAction(choose_blender_action)

    def choose_blender_path(self):
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Select Blender Executable",
            "",
            "Blender App (*.app *.exe);;All Files (*)",
        )
        if path:
            system = platform.system()
            if system == "Darwin" and path.endswith(".app"):
                # macOS app bundle, adjust to internal Blender binary
                path = os.path.join(path, "Contents", "MacOS", "Blender")

            self.config["blender_path"] = path
            save_config(self.config)
            QMessageBox.information(
                self, "Blender Path Saved", f"Blender path:\n{path}"
            )
            self.check_blender_installation()

    def check_blender_installation(self):
        blender_path = self.config.get("blender_path", "")

        if not blender_path:
            self.label.setText("Setup Blender path first!")
            self.setAcceptDrops(False)
        elif not os.path.exists(blender_path):
            self.label.setText(
                "There seems to be no Blender installed on this computer!"
            )
            self.setAcceptDrops(False)
        else:
            self.label.setText("Drag a Blender file here")
            self.setAcceptDrops(True)

    def run_blender_with_args(self, additional_args=None):
        blender_path = self.config.get("blender_path", "")
        if not blender_path or not os.path.exists(blender_path):
            QMessageBox.warning(self, "Error", "Blender path not set correctly.")
            return

        args = [blender_path]
        if additional_args:
            args += additional_args

        try:
            subprocess.run(args, check=True)
        except subprocess.CalledProcessError as e:
            QMessageBox.critical(
                self, "Execution Failed", f"Error running Blender:\n{e}"
            )

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls() and self.acceptDrops():
            event.accept()
        else:
            event.ignore()

    def dropEvent(self, event):
        if not self.acceptDrops():
            QMessageBox.warning(
                self, "Setup Required", "Please setup a valid Blender path first!"
            )
            return

        if event.mimeData().hasUrls():
            file_path = event.mimeData().urls()[0].toLocalFile()
            if file_path.endswith(".blend"):
                self.run_blender_with_args([file_path])
            else:
                QMessageBox.warning(
                    self, "Invalid File", "Please drop a valid .blend file."
                )
        else:
            event.ignore()


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = DragDropWindow()
    window.show()
    sys.exit(app.exec())

import sys
import os
import json
import platform
import subprocess
import tempfile
import re
from pathlib import Path
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
    QProgressBar,
    QPushButton,
)
from PySide6.QtGui import QAction
from PySide6.QtCore import Qt, QTimer

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
        self.setWindowTitle("Blender Drag & Drop Renderer")
        self.resize(500, 450)

        self.menu_bar = self.menuBar()
        self.setup_menu()

        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        layout = QVBoxLayout()
        central_widget.setLayout(layout)

        self.label = QLabel("Drag a Blender file here")
        self.label.setAlignment(Qt.AlignCenter)
        self.label.setStyleSheet(
            "border: 2px dashed gray; font-size: 16px; padding: 40px;"
        )
        layout.addWidget(self.label)

        self.progress = QProgressBar()
        self.progress.setValue(0)
        layout.addWidget(self.progress)

        self.frame_counter = QLabel("No rendering yet.")
        self.frame_counter.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.frame_counter)

        self.cancel_button = QPushButton("Cancel Rendering")
        self.cancel_button.setEnabled(False)
        self.cancel_button.setStyleSheet(
            "background-color: lightgray; border-radius: 4px; padding: 5px;"
        )
        self.cancel_button.clicked.connect(self.cancel_render)
        layout.addWidget(self.cancel_button)

        self.process = None
        self.start_frame = 1
        self.end_frame = 250
        self.total_frames = 250
        self.current_frame = 0
        self.output_dir = ""
        self.image_format = "png"
        self.current_blend_file = ""
        self.crash_count = 0

        self.config = load_config()
        self.check_blender_installation()

        self.timer = QTimer()
        self.timer.timeout.connect(self.check_process_output)

        self.is_windows = platform.system() == "Windows"
        self.is_macos = platform.system() == "Darwin"

    def setup_menu(self):
        setup_menu = QMenu("Setup", self)
        choose_blender_action = QAction("Choose Blender Path", self)
        choose_blender_action.triggered.connect(self.choose_blender_path)
        setup_menu.addAction(choose_blender_action)
        self.menu_bar.addMenu(setup_menu)

    def choose_blender_path(self):
        filter_text = (
            "Blender Executable (*.exe)" if self.is_windows else "Blender App (*.app)"
        )
        path, _ = QFileDialog.getOpenFileName(
            self, "Select Blender Executable", "", filter_text
        )

        if path:
            if self.is_macos and path.endswith(".app"):
                path = os.path.join(path, "Contents", "MacOS", "Blender")

            self.config["blender_path"] = path
            save_config(self.config)
            QMessageBox.information(
                self, "Blender Path Saved", f"Blender path:\n{path}"
            )
            self.check_blender_installation()

    def check_blender_installation(self):
        blender_path = self.config.get("blender_path", "")
        if not blender_path or not os.path.exists(blender_path):
            self.label.setText("Setup Blender path first!")
            self.setAcceptDrops(False)
        else:
            self.label.setText("Drag a Blender file here")
            self.setAcceptDrops(True)

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
                self.probe_scene(file_path)
                self.adjust_start_frame_based_on_existing_output()

                if self.start_frame > self.end_frame:
                    QMessageBox.information(
                        self,
                        "Already Rendered",
                        "All frames of this scene are already rendered.",
                    )
                    return

                self.label.setText(
                    f"Processing {os.path.basename(file_path)} currently"
                )
                self.current_blend_file = file_path
                self.crash_count = 0
                self.start_render(file_path)
            else:
                QMessageBox.warning(
                    self, "Invalid File", "Please drop a valid .blend file."
                )
        else:
            event.ignore()

    def probe_scene(self, blend_file):
        script_text = """
import bpy
print("[PROBE] START_FRAME", bpy.context.scene.frame_start)
print("[PROBE] END_FRAME", bpy.context.scene.frame_end)
print("[PROBE] OUTPUT_DIR", bpy.path.abspath(bpy.context.scene.render.filepath))
print("[PROBE] OUTPUT_FORMAT", bpy.context.scene.render.image_settings.file_format)
exit()
"""
        with tempfile.NamedTemporaryFile(
            delete=False, suffix=".py", mode="w", encoding="utf8"
        ) as probe_script:
            probe_script.write(script_text)

        blender_path = self.config.get("blender_path", "")
        args = [blender_path, "-b", blend_file, "-P", probe_script.name]
        encoding = "utf8" if self.is_macos else "cp1252"

        result = subprocess.run(
            args,
            capture_output=True,
            text=True,
            shell=False,
            encoding=encoding,
            errors="replace",
        )
        os.remove(probe_script.name)

        scene_basename = Path(blend_file).stem
        fallback_output = str(Path(blend_file).with_name(f"{scene_basename}_output"))

        self.output_dir = ""
        self.image_format = "png"

        for line in result.stdout.splitlines():
            if "[PROBE] START_FRAME" in line:
                self.start_frame = int(line.split()[-1])
            elif "[PROBE] END_FRAME" in line:
                self.end_frame = int(line.split()[-1])
            elif "[PROBE] OUTPUT_DIR" in line:
                output = line.split(" ", 2)[-1].strip()
                if output and output != "//":
                    self.output_dir = output
            elif "[PROBE] OUTPUT_FORMAT" in line:
                fmt = line.split(" ", 2)[-1].strip()
                if fmt:
                    self.image_format = fmt.lower()

        if not self.output_dir:
            self.output_dir = fallback_output

        self.output_dir = os.path.abspath(self.output_dir)
        os.makedirs(self.output_dir, exist_ok=True)
        self.total_frames = self.end_frame - self.start_frame + 1

    def adjust_start_frame_based_on_existing_output(self):
        if not self.output_dir:
            return

        existing_frames = [
            f
            for f in os.listdir(self.output_dir)
            if f.endswith(f".{self.image_format}") and f.startswith("frame_")
        ]

        frame_pattern = re.compile(rf"frame_(\\d+)\\.{re.escape(self.image_format)}")
        max_frame = 0

        for filename in existing_frames:
            match = frame_pattern.match(filename)
            if match:
                frame_num = int(match.group(1))
                max_frame = max(max_frame, frame_num)

        if max_frame >= self.start_frame:
            self.start_frame = max_frame + 1
            self.total_frames = self.end_frame - self.start_frame + 1

    def start_render(self, blend_file):
        if self.process:
            QMessageBox.warning(self, "Render In Progress", "Already rendering!")
            return

        blender_path = self.config.get("blender_path", "")
        render_script = os.path.join(os.getcwd(), "render_script.py")

        args = [
            blender_path,
            "-b",
            blend_file,
            "-P",
            render_script,
            "--",
            "--output_dir",
            self.output_dir,
            "--prefix",
            "frame_",
            "--resume",
            "true",
        ]

        self.process = subprocess.Popen(
            args,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            bufsize=1,
            universal_newlines=True,
        )

        self.progress.setMinimum(0)
        self.progress.setMaximum(self.total_frames)
        self.progress.setValue(0)
        self.frame_counter.setText(
            f"Rendering frames {self.start_frame}-{self.end_frame}"
        )
        self.current_frame = self.start_frame
        self.cancel_button.setEnabled(True)
        self.cancel_button.setStyleSheet(
            "background-color: salmon; font-weight: bold; border-radius: 4px; padding: 5px;"
        )
        self.timer.start(100)

    def cancel_render(self):
        if self.process:
            self.process.terminate()
            self.process = None
            self.timer.stop()
            self.cancel_button.setEnabled(False)
            self.cancel_button.setStyleSheet(
                "background-color: lightgray; border-radius: 4px; padding: 5px;"
            )
            self.label.setText("Rendering cancelled. Drag a Blender file here")
            self.frame_counter.setText("Rendering cancelled.")

    def check_process_output(self):
        if self.process and self.process.stdout:
            line = self.process.stdout.readline()
            if line:
                print(line.strip())
                if "Fra:" in line:
                    try:
                        fra_index = line.find("Fra:")
                        rest = line[fra_index + 4 :]
                        frame_num_str = rest.split()[0]
                        frame_num = int(frame_num_str)
                        self.current_frame = frame_num
                        progress = self.current_frame - self.start_frame
                        self.progress.setValue(progress)
                        self.frame_counter.setText(
                            f"Rendering frame {self.current_frame}/{self.end_frame} | Crashes: {self.crash_count}"
                        )
                    except Exception as e:
                        print(f"[ERROR parsing Fra:]: {e}")
                if "[DONE]" in line:
                    self.finish_render()

        if self.process and self.process.poll() is not None:
            self.timer.stop()
            if self.current_frame >= self.end_frame:
                self.finish_render()
            else:
                self.crash_count += 1
                print(
                    f"[CRASH DETECTED] Restarting render (crash #{self.crash_count})..."
                )
                self.process = None
                self.start_render(self.current_blend_file)

    def finish_render(self):
        self.progress.setValue(self.progress.maximum())
        self.frame_counter.setText(
            f"Rendering finished!\n\n{self.end_frame - self.start_frame + 1} frames rendered to:\n{self.output_dir}\nCrashes: {self.crash_count}"
        )
        self.label.setText("Drag a Blender file here")
        self.cancel_button.setEnabled(False)
        self.cancel_button.setStyleSheet(
            "background-color: lightgray; border-radius: 4px; padding: 5px;"
        )
        self.process = None


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = DragDropWindow()
    window.show()
    sys.exit(app.exec())

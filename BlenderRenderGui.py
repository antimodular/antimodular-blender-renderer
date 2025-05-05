import sys
import os
import json
import platform
import tempfile
import re
import time
import datetime
import traceback
import logging
from pathlib import Path
from PySide6.QtWidgets import (
    QApplication,
    QMainWindow,
    QLabel,
    QFileDialog,
    QMessageBox,
    QMenu,
    QWidget,
    QVBoxLayout,
    QProgressBar,
    QPushButton,
    QListWidget,
    QListWidgetItem,
    QHBoxLayout,
    QFrame,
    QToolButton,
    QSplitter,
)
from PySide6.QtGui import QAction, QIcon
from PySide6.QtCore import Qt, QProcess, QSize

# Get the application's base directory - important for PyInstaller compatibility
if getattr(sys, 'frozen', False):
    # If the application is run as a bundle (PyInstaller)
    APPLICATION_PATH = sys._MEIPASS
else:
    # If running from script
    APPLICATION_PATH = os.path.dirname(os.path.abspath(__file__))

CONFIG_FILE = os.path.join(APPLICATION_PATH, "config.json") if getattr(sys, 'frozen', False) else "config.json"


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


class QueueItemWidget(QWidget):
    def __init__(self, file_path, parent=None):
        super().__init__(parent)
        self.file_path = file_path
        layout = QHBoxLayout()
        layout.setContentsMargins(5, 2, 5, 2)
        self.setLayout(layout)

        # File path label
        file_name = os.path.basename(file_path)
        self.label = QLabel(f"{file_name}")
        self.label.setToolTip(file_path)
        layout.addWidget(self.label, 1)  # 1 = stretch factor

        # Remove button
        self.remove_btn = QToolButton()
        self.remove_btn.setText("✕")
        self.remove_btn.setToolTip("Remove from queue")
        self.remove_btn.setStyleSheet(
            "QToolButton { border: none; color: red; font-weight: bold; }"
            "QToolButton:hover { background-color: #ffeeee; }"
        )
        layout.addWidget(self.remove_btn)


class DragDropWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Blender Drag & Drop Renderer")
        self.resize(600, 650)  # Increased window size to accommodate queue list

        self.menu_bar = self.menuBar()
        self.setup_menu()

        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        layout = QVBoxLayout()
        central_widget.setLayout(layout)

        self.label = QLabel("Drag one or more Blender files here")
        self.label.setAlignment(Qt.AlignCenter)
        self.label.setStyleSheet(
            "border: 2px dashed gray; font-size: 16px; padding: 40px;"
        )
        layout.addWidget(self.label)

        # File queue section
        queue_section = QFrame()
        queue_section.setFrameShape(QFrame.StyledPanel)
        queue_layout = QVBoxLayout()
        queue_section.setLayout(queue_layout)

        queue_header = QLabel("File Queue")
        queue_header.setStyleSheet("font-weight: bold; font-size: 14px;")
        queue_layout.addWidget(queue_header)

        self.queue_list = QListWidget()
        self.queue_list.setMinimumHeight(150)
        self.queue_list.setAlternatingRowColors(True)
        queue_layout.addWidget(self.queue_list)

        layout.addWidget(queue_section)

        self.progress = QProgressBar()
        self.progress.setValue(0)
        layout.addWidget(self.progress)

        self.stats_label = QLabel("Render statistics will appear here")
        self.stats_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.stats_label)

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

        self.probe_process = None
        self._probe_script_path = ""

        # File queue management
        self.file_queue = []
        self.queue_items = {}  # Dictionary to track all queue items by file path
        self.currently_rendering = False

        # Rendering time tracking
        self.render_start_time = 0
        self.frame_start_time = 0
        self.frame_times = []

        self.config = load_config()
        self.check_blender_installation()

        self.is_windows = platform.system() == "Windows"
        self.is_macos = platform.system() == "Darwin"

        # Add counters for overall statistics
        self.total_scenes_rendered = 0
        self.total_frames_rendered = 0
        self.total_render_time = 0
        self.session_start_time = time.time()

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
            dropped_files = [url.toLocalFile() for url in event.mimeData().urls()]
            blend_files = [f for f in dropped_files if f.endswith(".blend")]

            if not blend_files:
                QMessageBox.warning(
                    self, "Invalid Files", "Please drop valid .blend files."
                )
                return

            # Add files to queue
            for blend_file in blend_files:
                self.add_file_to_queue(blend_file)

            # If this is a new batch after previous completion, reset overall statistics
            if (
                not self.currently_rendering
                and self.total_scenes_rendered > 0
                and not self.file_queue
            ):
                self.reset_overall_statistics()

            # Start processing if not already rendering
            if not self.currently_rendering:
                self.process_next_file()
        else:
            event.ignore()

    def reset_overall_statistics(self):
        """Reset the overall statistics when starting a new batch"""
        self.total_scenes_rendered = 0
        self.total_frames_rendered = 0
        self.total_render_time = 0
        self.session_start_time = time.time()

    def add_file_to_queue(self, blend_file):
        # Check if file is already in queue
        existing_item = None
        already_queued = False

        # Check if this file has already been queued
        for i in range(self.queue_list.count()):
            item = self.queue_list.item(i)
            widget = self.queue_list.itemWidget(item)
            if widget and widget.file_path == blend_file:
                # Found existing item for this file
                already_queued = True
                existing_item = item

        if already_queued:
            # File already queued, update status if not currently rendering
            widget = self.queue_list.itemWidget(existing_item)
            if self.current_blend_file != blend_file:
                if blend_file not in self.file_queue:
                    # Add to queue if not already there
                    self.file_queue.append(blend_file)
                    status_text = (
                        "Ready to render" if not self.currently_rendering else "Queued"
                    )
                    widget.label.setText(
                        f"{os.path.basename(blend_file)} ({status_text})"
                    )
                    # Reset styling
                    widget.label.setStyleSheet("")
            return

        # Add to internal queue
        self.file_queue.append(blend_file)

        # Create and add queue item widget
        item_widget = QueueItemWidget(blend_file)
        item = QListWidgetItem(self.queue_list)
        item.setSizeHint(item_widget.sizeHint())
        self.queue_list.addItem(item)
        self.queue_list.setItemWidget(item, item_widget)

        # Store reference to item in our tracking dictionary
        self.queue_items[blend_file] = item

        # Connect remove button to remove function
        item_widget.remove_btn.clicked.connect(
            lambda: self.remove_file_from_queue(item, blend_file)
        )

        # Update UI
        status_text = "Ready to render" if not self.currently_rendering else "Queued"
        item_widget.label.setText(f"{os.path.basename(blend_file)} ({status_text})")

    def remove_file_from_queue(self, item, blend_file):
        if blend_file == self.current_blend_file and self.currently_rendering:
            QMessageBox.warning(
                self,
                "File In Use",
                f"Cannot remove {os.path.basename(blend_file)} while it's being rendered.",
            )
            return

        # Remove from list widget and internal queue
        row = self.queue_list.row(item)
        self.queue_list.takeItem(row)

        if blend_file in self.file_queue:
            self.file_queue.remove(blend_file)

        # Remove from tracking dictionary if present
        if blend_file in self.queue_items:
            del self.queue_items[blend_file]

    def process_next_file(self):
        if not self.file_queue:
            self.currently_rendering = False
            self.label.setText("Drag one or more Blender files here")

            # If we've rendered at least one scene, display overall statistics
            if self.total_scenes_rendered > 0:
                self.display_overall_statistics()
            return

        self.currently_rendering = True
        next_file = self.file_queue[0]
        self.file_queue.pop(0)

        # Update UI to show which file is now rendering
        for i in range(self.queue_list.count()):
            item = self.queue_list.item(i)
            widget = self.queue_list.itemWidget(item)
            if widget and widget.file_path == next_file:
                widget.label.setText(f"{os.path.basename(next_file)} (Rendering...)")
                widget.label.setStyleSheet("font-weight: bold; color: green;")
                break

        self.probe_scene(next_file)

    def probe_scene(self, blend_file):
        self._probe_script_path = tempfile.NamedTemporaryFile(
            delete=False, suffix=".py", mode="w", encoding="utf8"
        ).name
        with open(self._probe_script_path, "w", encoding="utf8") as f:
            f.write(
                """
import bpy
print("[PROBE] START_FRAME", bpy.context.scene.frame_start)
print("[PROBE] END_FRAME", bpy.context.scene.frame_end)
print("[PROBE] OUTPUT_DIR", bpy.path.abspath(bpy.context.scene.render.filepath))
print("[PROBE] OUTPUT_FORMAT", bpy.context.scene.render.image_settings.file_format)
exit()
"""
            )

        self.probe_output_lines = []
        blender_path = self.config.get("blender_path", "")
        self.probe_process = QProcess(self)
        self.probe_process.readyReadStandardOutput.connect(self.read_probe_output)
        self.probe_process.finished.connect(lambda: self.parse_probe_output(blend_file))

        args = ["-b", blend_file, "-P", self._probe_script_path]
        self.probe_process.setProgram(blender_path)
        self.probe_process.setArguments(args)
        self.probe_process.start()

    def read_probe_output(self):
        if not self.probe_process:
            return
        while self.probe_process.canReadLine():
            line = bytes(self.probe_process.readLine()).decode(errors="replace").strip()
            print("[PROBE]", line)
            self.probe_output_lines.append(line)

    def parse_probe_output(self, blend_file):
        if self._probe_script_path and os.path.exists(self._probe_script_path):
            os.remove(self._probe_script_path)
            self._probe_script_path = ""

        # Get the directory and basename of the blend file for creating the default output folder
        scene_dir = os.path.dirname(blend_file)
        scene_basename = Path(blend_file).stem
        fallback_output = os.path.join(scene_dir, f"{scene_basename}_output")

        self.start_frame = 1
        self.end_frame = 250
        self.output_dir = ""
        self.image_format = "png"

        for line in self.probe_output_lines:
            if "[PROBE] START_FRAME" in line:
                self.start_frame = int(line.split()[-1])
            elif "[PROBE] END_FRAME" in line:
                self.end_frame = int(line.split()[-1])
            elif "[PROBE] OUTPUT_DIR" in line:
                output = line.split(" ", 2)[-1].strip()
                # Only use the output if it's not empty and not just "//"
                if output and output != "//" and not output.endswith("OUTPUT_DIR"):
                    self.output_dir = output
            elif "[PROBE] OUTPUT_FORMAT" in line:
                fmt = line.split(" ", 2)[-1].strip()
                if fmt:
                    self.image_format = fmt.lower()

        # Use the fallback (scene name + _output) if output dir is unset or just "//"
        if (
            not self.output_dir
            or self.output_dir == "//"
            or self.output_dir.endswith("OUTPUT_DIR")
        ):
            self.output_dir = fallback_output
        else:
            # If the path starts with //, it's relative to the blend file directory
            if self.output_dir.startswith("//"):
                self.output_dir = os.path.normpath(
                    os.path.join(scene_dir, self.output_dir[2:])
                )
            # Ensure we have an absolute path
            elif not os.path.isabs(self.output_dir):
                self.output_dir = os.path.normpath(
                    os.path.join(scene_dir, self.output_dir)
                )
            # Convert the path to an absolute path
            self.output_dir = os.path.abspath(self.output_dir)

        try:
            os.makedirs(self.output_dir, exist_ok=True)

            # Continue with normal processing
            self.total_frames = self.end_frame - self.start_frame + 1
            self.adjust_start_frame_based_on_existing_output()

            if self.start_frame > self.end_frame:
                # Update UI to show this file was already rendered
                for i in range(self.queue_list.count()):
                    item = self.queue_list.item(i)
                    widget = self.queue_list.itemWidget(item)
                    if widget and widget.file_path == blend_file:
                        widget.label.setText(
                            f"{os.path.basename(blend_file)} (Already rendered)"
                        )
                        widget.label.setStyleSheet("color: gray; font-style: italic;")
                        break

                # Move to next file in queue
                self.currently_rendering = False
                self.process_next_file()
                return

            self.label.setText(f"Processing {os.path.basename(blend_file)} currently")
            self.current_blend_file = blend_file
            self.crash_count = 0
            self.start_render(blend_file)

        except (OSError, PermissionError) as e:
            # Handle errors creating output directory
            error_message = f"Error accessing output directory: {str(e)}"
            self.log_error(blend_file, error_message)

            # Update queue status for this file
            for i in range(self.queue_list.count()):
                item = self.queue_list.item(i)
                widget = self.queue_list.itemWidget(item)
                if widget and widget.file_path == blend_file:
                    widget.label.setText(
                        f"{os.path.basename(blend_file)} (Failed with Error)"
                    )
                    widget.label.setStyleSheet("color: red; font-weight: bold;")
                    break

            # Display error in UI
            self.frame_counter.setText(f"Error: {error_message}")

            # Move to the next file
            self.currently_rendering = False
            self.process_next_file()

    def adjust_start_frame_based_on_existing_output(self):
        if not self.output_dir or not os.path.exists(self.output_dir):
            return

        # Get all image files in the output directory
        existing_files = [
            f
            for f in os.listdir(self.output_dir)
            if f.lower().endswith(f".{self.image_format.lower()}")
        ]

        if not existing_files:
            return

        # More robust pattern matching to handle different naming conventions
        # This will handle both standard frames and stereoscopic images
        frame_patterns = [
            # Standard frame pattern (frame_001.png)
            re.compile(rf".*?(\d+)\.{re.escape(self.image_format)}$", re.IGNORECASE),
            # Left eye pattern (frame_001_L.png)
            re.compile(rf".*?(\d+)_L\.{re.escape(self.image_format)}$", re.IGNORECASE),
            # Right eye pattern (frame_001_R.png)
            re.compile(rf".*?(\d+)_R\.{re.escape(self.image_format)}$", re.IGNORECASE),
        ]

        # Find all existing frame numbers
        rendered_frames = set()
        for filename in existing_files:
            for pattern in frame_patterns:
                match = pattern.match(filename)
                if match:
                    try:
                        frame_num = int(match.group(1))
                        rendered_frames.add(frame_num)
                    except (ValueError, IndexError):
                        continue

        # Quick check if we have any rendered frames
        if not rendered_frames:
            return

        # Rather than just taking the max frame, we need to find missing frames
        missing_frames = []
        for frame in range(self.start_frame, self.end_frame + 1):
            if frame not in rendered_frames:
                missing_frames.append(frame)
                
        # Now we can determine what to do based on missing frames
        if not missing_frames:
            # If there are no missing frames, all frames are rendered
            self.start_frame = self.end_frame + 1
            print("All frames already rendered")
        else:
            # Set start frame to the first missing frame
            self.start_frame = missing_frames[0]
            print(f"Found {len(missing_frames)} missing frames. Start rendering from frame {self.start_frame}")
            
            # If there are multiple non-consecutive missing frames, we'll need to pass this info to render_script
            if len(missing_frames) > 1 and missing_frames[-1] - missing_frames[0] + 1 != len(missing_frames):
                # Store missing frames for use in start_render
                self.missing_frames = missing_frames
                print(f"Missing frames are non-consecutive: {missing_frames[:10]}...")
            else:
                self.missing_frames = None
            
        # Update total frames to render
        self.total_frames = max(0, self.end_frame - self.start_frame + 1)
        print(f"Adjusted start frame to {self.start_frame}, approximately {self.total_frames} frames to render")

    def start_render(self, blend_file):
        if self.process:
            QMessageBox.warning(self, "Render In Progress", "Already rendering!")
            return

        # Initialize time tracking for this render
        self.render_start_time = time.time()
        self.frame_start_time = time.time()
        self.frame_times = []

        blender_path = self.config.get("blender_path", "")
        
        # PyInstaller compatibility: Get the correct path to the render script
        if getattr(sys, 'frozen', False):
            # If running as PyInstaller bundle, extract render_script.py to a temporary location
            render_script = os.path.join(APPLICATION_PATH, "render_script.py")
            if not os.path.exists(render_script):
                # If the script isn't found in the bundle, create a temporary copy
                temp_render_script = tempfile.NamedTemporaryFile(
                    delete=False, suffix=".py", mode="w", encoding="utf8"
                ).name
                
                # Extract render_script content from the bundle or embed it directly
                try:
                    with open(render_script, 'r', encoding='utf-8') as src_file:
                        script_content = src_file.read()
                    with open(temp_render_script, 'w', encoding='utf-8') as dest_file:
                        dest_file.write(script_content)
                    render_script = temp_render_script
                    print(f"[INFO] Created temporary render script at: {render_script}")
                except Exception as e:
                    error_msg = f"Error extracting render script: {str(e)}"
                    print(f"[ERROR] {error_msg}")
                    QMessageBox.critical(self, "Render Script Error", error_msg)
                    return
        else:
            # If running as Python script, use the script in the current directory
            render_script = os.path.join(os.path.dirname(os.path.abspath(__file__)), "render_script.py")
        
        # Verify the render script exists
        if not os.path.exists(render_script):
            error_msg = f"Render script not found at: {render_script}"
            print(f"[ERROR] {error_msg}")
            QMessageBox.critical(self, "Render Script Error", error_msg)
            return
        
        print(f"[INFO] Using render script at: {render_script}")
        print(f"[INFO] Using Blender at: {blender_path}")
        
        args = [
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

        # If we detected non-consecutive missing frames, pass them to the render script
        if hasattr(self, 'missing_frames') and self.missing_frames and len(self.missing_frames) > 1:
            # Convert frame list to comma-separated string for passing as argument
            missing_frames_str = ",".join(str(f) for f in self.missing_frames)
            args.extend(["--missing_frames", missing_frames_str])
            print(f"Passing list of {len(self.missing_frames)} missing frames to render script")

        try:
            self.process = QProcess(self)
            self.process.setProcessChannelMode(QProcess.MergedChannels)  # Merge stdout and stderr
            self.process.setProgram(blender_path)
            self.process.setArguments(args)
            self.process.readyReadStandardOutput.connect(self.handle_stdout)
            self.process.finished.connect(self.render_finished)
            self.process.errorOccurred.connect(self.handle_process_error)
            self.process.start()
            
            # Check if process started successfully
            if not self.process.waitForStarted(3000):  # Wait up to 3 seconds
                error_msg = f"Failed to start Blender process. Check if Blender path is correct: {blender_path}"
                print(f"[ERROR] {error_msg}")
                QMessageBox.critical(self, "Process Error", error_msg)
                self.process = None
                return
                
            print(f"[INFO] Blender process started with PID: {self.process.processId()}")
            
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
        except Exception as e:
            error_msg = f"Error starting render process: {str(e)}"
            print(f"[ERROR] {error_msg}")
            print(traceback.format_exc())
            QMessageBox.critical(self, "Process Error", error_msg)
            self.process = None

    def handle_process_error(self, error):
        """Handle QProcess errors"""
        error_messages = {
            QProcess.FailedToStart: "Failed to start Blender. Check if the Blender path is correct and accessible.",
            QProcess.Crashed: f"Blender process crashed at frame {self.current_frame}.",
            QProcess.Timedout: "Blender process timed out.",
            QProcess.WriteError: "Error writing to Blender process.",
            QProcess.ReadError: "Error reading from Blender process.",
            QProcess.UnknownError: "Unknown error occurred with Blender process."
        }
        
        error_msg = error_messages.get(error, "An error occurred with the Blender process.")
        print(f"[ERROR] Process error: {error_msg}")
        
        # For crashed processes, try to restart rendering
        if error == QProcess.Crashed:
            self.crash_count += 1
            print(f"[INFO] Blender crashed {self.crash_count} times. Attempting to restart from frame {self.current_frame}.")
            # Logic to restart rendering could be added here

    def handle_stdout(self):
        # Check if process exists and is still running before trying to read from it
        if self.process is None or self.process.state() != QProcess.Running:
            return
            
        try:
            # Only read lines while the process is still running and has data
            while self.process is not None and self.process.state() == QProcess.Running and self.process.canReadLine():
                line = bytes(self.process.readLine()).decode(errors="replace").strip()
                print(line)
                if "Fra:" in line:
                    try:
                        fra_index = line.find("Fra:")
                        rest = line[fra_index + 4 :]
                        frame_num_str = rest.split()[0]
                        frame_num = int(frame_num_str)

                        # If frame number changed, record frame time
                        if self.current_frame != frame_num:
                            if self.current_frame > 0:  # Not first frame
                                # Record the time for previous frame
                                frame_time = time.time() - self.frame_start_time
                                self.frame_times.append(frame_time)

                            # Start timing for new frame
                            self.frame_start_time = time.time()
                            self.current_frame = frame_num

                        progress = self.current_frame - self.start_frame
                        self.progress.setValue(progress)
                        self.frame_counter.setText(
                            f"Rendering frame {self.current_frame}/{self.end_frame} | Crashes: {self.crash_count}"
                        )

                        # Update time statistics
                        self.update_time_statistics()
                    except Exception as e:
                        print(f"[ERROR parsing Fra:]: {e}")
                if "[DONE]" in line:
                    # Call render_finished only if process still exists
                    if self.process is not None:
                        self.render_finished()
        except Exception as e:
            # More descriptive error message with less alarmist language
            print(f"Error while reading process output: {e}")
            # Continue execution - don't let this error stop the application

    def update_time_statistics(self):
        # Need at least one completed frame for calculations
        if not self.frame_times:
            self.stats_label.setText("Calculating render statistics...")
            return

        # Calculate averages and estimates
        avg_frame_time = sum(self.frame_times) / len(self.frame_times)
        elapsed_time = time.time() - self.render_start_time

        # Estimate remaining time
        frames_done = len(self.frame_times)
        frames_remaining = self.total_frames - frames_done
        estimated_remaining_seconds = frames_remaining * avg_frame_time

        # Format times for display
        def format_time(seconds):
            if seconds < 60:
                return f"{seconds:.1f} seconds"
            elif seconds < 3600:
                minutes = seconds / 60
                return f"{minutes:.1f} minutes"
            else:
                hours = seconds / 3600
                return f"{hours:.1f} hours"

        elapsed_str = format_time(elapsed_time)
        remaining_str = format_time(estimated_remaining_seconds)
        avg_frame_str = format_time(avg_frame_time)

        # Estimate completion time
        completion_time = time.time() + estimated_remaining_seconds
        completion_time_str = datetime.datetime.fromtimestamp(completion_time).strftime(
            "%H:%M:%S"
        )

        # Update statistics label
        stats = (
            f"Render Statistics:\n"
            f"Average: {avg_frame_str} per frame | "
            f"Elapsed: {elapsed_str} | "
            f"Remaining: {remaining_str}\n"
            f"Estimated completion at: {completion_time_str}"
        )

        self.stats_label.setText(stats)

    def render_finished(self):
        if not self.process:
            return

        self.progress.setValue(self.progress.maximum())

        # Calculate total render time for this scene
        total_render_time = time.time() - self.render_start_time
        formatted_time = self.format_time_short(total_render_time)
        frames_rendered = self.end_frame - self.start_frame + 1

        # Update overall statistics
        self.total_scenes_rendered += 1
        self.total_frames_rendered += frames_rendered
        self.total_render_time += total_render_time

        # Update status for the completed file in the queue list with detailed stats
        for i in range(self.queue_list.count()):
            item = self.queue_list.item(i)
            widget = self.queue_list.itemWidget(item)
            if widget and widget.file_path == self.current_blend_file:
                widget.label.setText(
                    f"{os.path.basename(self.current_blend_file)} (Completed - {frames_rendered} frames, {formatted_time}, {self.crash_count} crashes)"
                )
                widget.label.setStyleSheet("color: blue;")
                break

        # Display scene-specific completion info
        self.frame_counter.setText(
            f"Rendering finished!\n\n{frames_rendered} frames rendered to:\n{self.output_dir}\nCrashes: {self.crash_count}"
        )

        self.cancel_button.setEnabled(False)
        self.cancel_button.setStyleSheet(
            "background-color: lightgray; border-radius: 4px; padding: 5px;"
        )

        self.process = None
        self.currently_rendering = False

        # Process next file in queue if any
        self.process_next_file()

        # If no more files to render, display overall statistics
        if not self.currently_rendering:
            self.label.setText("Drag one or more Blender files here")
            self.display_overall_statistics()

    def cancel_render(self):
        if self.process:
            self.process.kill()
            self.process = None
            self.cancel_button.setEnabled(False)
            self.cancel_button.setStyleSheet(
                "background-color: lightgray; border-radius: 4px; padding: 5px;"
            )
            self.label.setText("Drag one or more Blender files here")
            self.frame_counter.setText("Rendering cancelled.")

            # Update queue item status
            for i in range(self.queue_list.count()):
                item = self.queue_list.item(i)
                widget = self.queue_list.itemWidget(item)
                if widget and widget.file_path == self.current_blend_file:
                    widget.label.setText(
                        f"{os.path.basename(self.current_blend_file)} (Cancelled)"
                    )
                    widget.label.setStyleSheet("color: red;")
                    break

            # Process next file in queue after a short delay
            self.currently_rendering = False
            self.current_blend_file = ""
            self.process_next_file()

    def format_time_short(self, seconds):
        """Format time in a compact way for the queue list display"""
        if seconds < 60:
            return f"{int(seconds)}s"
        elif seconds < 3600:
            minutes = int(seconds / 60)
            secs = int(seconds % 60)
            return f"{minutes}m {secs}s"
        else:
            hours = int(seconds / 3600)
            minutes = int((seconds % 3600) / 60)
            return f"{hours}h {minutes}m"

    def format_time_long(self, seconds):
        """Format time in a more detailed way for final statistics"""
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = int(seconds % 60)

        if hours > 0:
            return f"{hours} hours, {minutes} minutes, {secs} seconds"
        elif minutes > 0:
            return f"{minutes} minutes, {secs} seconds"
        else:
            return f"{secs} seconds"

    def log_error(self, blend_file, error_message):
        """Create a log file next to the scene file with error details"""
        try:
            # Generate log filename based on scene filename
            scene_dir = os.path.dirname(blend_file)
            scene_basename = Path(blend_file).stem
            log_file = os.path.join(scene_dir, f"{scene_basename}.log")

            # Get timestamp for the log
            timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

            # Create log content with error details
            log_content = [
                f"Error Log for {os.path.basename(blend_file)}",
                f"Date: {timestamp}",
                f"Error: {error_message}",
                "Stack Trace:",
                traceback.format_exc(),
            ]

            # Write to log file
            with open(log_file, "w") as f:
                f.write("\n".join(log_content))

            print(f"Error log written to: {log_file}")
        except Exception as e:
            # If logging fails, just print to console - don't want to cascade errors
            print(f"Failed to write error log: {str(e)}")
            print(f"Original error was: {error_message}")
            print(traceback.format_exc())

    def display_overall_statistics(self):
        """Display overall rendering statistics when all scenes are rendered"""
        # Calculate session duration
        session_duration = time.time() - self.session_start_time
        session_time_formatted = self.format_time_long(session_duration)
        render_time_formatted = self.format_time_long(self.total_render_time)

        # Create detailed statistics message
        stats_message = (
            f"All Rendering Complete!\n\n"
            f"Total scenes rendered: {self.total_scenes_rendered}\n"
            f"Total frames rendered: {self.total_frames_rendered}\n"
            f"Total rendering time: {render_time_formatted}\n"
            f"Session duration: {session_time_formatted}"
        )

        # Update the UI
        self.frame_counter.setText(stats_message)
        self.stats_label.setText("Rendering session completed")


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = DragDropWindow()
    window.show()
    sys.exit(app.exec())

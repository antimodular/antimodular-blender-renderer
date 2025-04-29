# 🧰 Blender Drag & Drop Renderer – Full Setup Guide

This guide shows you how to install, configure, and package the **Blender Drag & Drop Renderer** GUI as a standalone application for **Windows** and **macOS**.

---

## ❓ Why This Tool Exists

Long render sessions in Blender can sometimes crash due to memory limitations, hardware instability, or software issues. This tool solves that problem by automatically recovering from crashes and resuming the rendering process from the last successfully rendered frame. 

Instead of starting over, it picks up exactly where it left off — ensuring that even the longest and most complex render jobs can be completed reliably without manual intervention.

You simply drag and drop your `.blend` file, and the tool takes care of the rest.

---

## 1. 🐍 Install Python

### Windows:
- Download Python 3.11+ from [python.org/downloads/windows](https://www.python.org/downloads/windows/)
- During installation:
  - ✅ Check "Add Python to PATH"
  - Proceed with default settings.

### macOS:
- Open Terminal and install Homebrew if you haven't:
  ```bash
  /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
  ```
- Then install Python:
  ```bash
  brew install python
  ```

**Verify installation:**
```bash
python3 --version
```

---

## 2. 🧪 Create a Virtual Environment (recommended)

Inside your project folder:
```bash
python3 -m venv venv
```

Activate the environment:

- **Windows:**
  ```bash
  venv\Scripts\activate
  ```
- **macOS/Linux:**
  ```bash
  source venv/bin/activate
  ```

---

## 3. 📦 Install Required Python Packages

Inside your virtual environment:
```bash
pip install -r requirements.txt
```

---

## 4. 🗂️ Project Structure

Ensure your folder is structured like this:
```
application/
├── BlenderRenderGui.py   # Main GUI script
├── render_script.py      # Blender-side render script
├── config.json           # (auto-created after first run)
```
✅ Make sure `render_script.py` exists and is functional.

---

## 5. 🛠️ Create an Executable with PyInstaller

### macOS:
```bash
pyinstaller --noconfirm --onefile --windowed --name "BlenderRenderGui" BlenderRenderGui.py
```

### Windows:
```bash
pyinstaller --noconfirm --onefile --windowed --name "BlenderRenderGui" BlenderRenderGui.py
```

The built app will appear in:
```
dist/BlenderRenderGui
```

- `.app` (macOS)
- `.exe` (Windows)

✅ You can now double-click to run!

---

## 6. ✨ Optional Improvements

- Add a custom icon:
  ```bash
  --icon=path/to/icon.ico   # Windows
  --icon=path/to/icon.icns  # macOS
  ```
- Embed everything into a polished `.app` or installer (see below).

---

# ✅ That's it! 🎉

You now have a cross-platform, standalone **drag-and-drop renderer for Blender**.

---

## 💡 Bonus: Build a Polished Installer

### macOS:
- Use [`create-dmg`](https://github.com/create-dmg/create-dmg) to generate a `.dmg` drag-and-drop installer.
- For system-wide installations, create a `.pkg` using `pkgbuild` or `Packages` app.

### Windows:
- Use [Inno Setup](https://jrsoftware.org/isinfo.php) to create a wizard-style `.exe` installer.
- Alternatively, use [WiX Toolset](https://wixtoolset.org/) to generate a `.msi` installer.

Let us know if you want help generating those configurations!

---

## 🧯 Troubleshooting

- If you encounter permission issues on macOS:
  ```bash
  chmod +x dist/BlenderRenderGui
  ```
- If the app doesn’t open:
  - Make sure Blender’s path is correctly set via the app's **Setup** menu.
  - Use a terminal to launch the executable and view logs.
- To include additional assets, use:
  ```bash
  pyinstaller --add-data "relative/path/to/file:destination" ...
  ```

# Blender Drag & Drop Renderer - Setup Guide

This guide shows you how to install everything needed to run and package the Blender Drag & Drop Renderer GUI as a standalone app for **Windows** and **macOS**.

---

## 1. Install Python

### Windows:
- Download Python 3.11+ from https://www.python.org/downloads/windows/
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

Check Python is installed:
```bash
python3 --version
```

---

## 2. Create a Virtual Environment (recommended)

Inside your project folder:

```bash
python3 -m venv venv
```

Activate it:

- **Windows:**
  ```bash
  venv\Scripts\activate
  ```
- **macOS/Linux:**
  ```bash
  source venv/bin/activate
  ```

---

## 3. Install Required Python Packages

Inside your virtual environment:

```bash
pip install PySide6 pyinstaller
```

---

## 4. Project Structure

Ensure your project folder looks like this:

```
application/
├── BlenderRenderGui.py   # Main GUI script
├── render_script.py      # Blender-side render script
├── config.json           # (auto-created after first run)
```

✅ Make sure `render_script.py` exists!

---

## 5. Create Executable with PyInstaller

### macOS:
```bash
pyinstaller --noconfirm --onefile --windowed --name "BlenderRenderGui" BlenderRenderGui.py
```

### Windows:
```bash
pyinstaller --noconfirm --onefile --windowed --name "BlenderRenderGui" BlenderRenderGui.py
```

After building, your app will appear in:
```
dist/BlenderRenderGui
```

- `.app` (Mac)
- `.exe` (Windows)

✅ Double-click to run!

---

## 6. Optional Improvements

- Add a custom icon:
  ```bash
  --icon=path/to/icon.ico  # Windows
  --icon=path/to/icon.icns # macOS
  ```
- Embed everything into a cleaner `.app` structure (ask if you need it!)

---

# That's it! 🎉

You now have a cross-platform drag-and-drop Blender background renderer!

---

## Troubleshooting

- If you get permission issues, try:
  ```bash
  chmod +x dist/BlenderRenderGui
  ```
- If your app doesn't open, ensure Blender's path is properly configured via the app's menu.
- If you need to bundle additional files, use PyInstaller's `--add-data` option.

---

Need help building a polished installer or custom `.app` bundle? Just ask!


# PyMasterLauncher
A lightweight desktop launcher for keeping track and running your Python projects efficiently.
[![Python](https://img.shields.io/badge/python-3.8+-blue)](https://www.python.org/)  
[![License: MIT](https://img.shields.io/badge/License-MIT-green)](LICENSE)

PyMasterLauncher is a **master Python app launcher** that allows you to organize, run, and manage multiple Python scripts from a single GUI. Launch your apps safely in separate processes, add new Python apps easily, delete unwanted apps, and search through your collection quickly.

---

## Features

- Add multiple Python apps at once
- Run apps in **separate processes** (so closing them doesn’t affect the master launcher)
- Delete apps directly from the GUI
- **Auto-refresh** app list every 2 seconds
- **Search/filter bar** to quickly find apps
- Scrollable interface for managing many apps
- Status bar to display messages and actions
---

## Usage

Run the master launcher:
python3 master_gui.py
Use the “Add Python App(s)” button to add new .py files.
Click Run to launch an app in a separate process.
Click Delete to remove apps from the launcher.
Use the Search bar to filter apps quickly.
All apps are safely run in separate processes, so closing a child app does not close the launcher.

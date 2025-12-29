import tkinter as tk
from tkinter import messagebox, filedialog, simpledialog
import os
import shutil
import subprocess
import sys
import platform

APPS_DIR = "apps"

# Ensure apps folder exists
os.makedirs(APPS_DIR, exist_ok=True)

# ------------------- Functions -------------------

def get_apps():
    return [f[:-3] for f in os.listdir(APPS_DIR) if f.endswith(".py")]

def run_app(app_name):
    """Run the selected app in a separate process without opening a terminal for GUI apps"""
    app_path = os.path.join(APPS_DIR, f"{app_name}.py")
    if not os.path.exists(app_path):
        messagebox.showerror("Error", f"{app_name} not found!")
        return

    try:
        system = platform.system()
        if system == "Windows":
            # Detached process, no terminal window
            subprocess.Popen([sys.executable, app_path], creationflags=subprocess.DETACHED_PROCESS)
        else:
            # macOS/Linux: run in a separate process
            subprocess.Popen([sys.executable, app_path])
    except Exception as e:
        messagebox.showerror("Error", f"Failed to run {app_name}:\n{e}")

def add_apps():
    """Add one or multiple .py files to the apps folder"""
    files = filedialog.askopenfilenames(
        title="Select Python files",
        filetypes=[("Python files", "*.py")]
    )
    for file_path in files:
        if file_path:
            filename = os.path.basename(file_path)
            dest_path = os.path.join(APPS_DIR, filename)

            if os.path.exists(dest_path):
                action = messagebox.askquestion(
                    "File exists",
                    f"{filename} already exists. Overwrite?",
                    icon='warning'
                )
                if action == 'no':
                    new_name = simpledialog.askstring(
                        "Rename",
                        f"Enter new name for {filename} (without .py):"
                    )
                    if new_name:
                        dest_path = os.path.join(APPS_DIR, f"{new_name}.py")
                    else:
                        continue  # skip this file

            try:
                shutil.copy(file_path, dest_path)
            except Exception as e:
                messagebox.showerror("Error", f"Failed to add {filename}:\n{e}")
    refresh_buttons()

def delete_app(app_name):
    """Delete an app from the apps folder"""
    if messagebox.askyesno("Delete", f"Are you sure you want to delete {app_name}?"):
        try:
            os.remove(os.path.join(APPS_DIR, f"{app_name}.py"))
            refresh_buttons()
        except Exception as e:
            messagebox.showerror("Error", f"Failed to delete {app_name}:\n{e}")

def refresh_buttons():
    """Refresh the app buttons"""
    for widget in button_frame.winfo_children():
        widget.destroy()

    apps = get_apps()
    if not apps:
        tk.Label(button_frame, text="No apps found in the apps folder.").pack(pady=10)

    for app in apps:
        frame = tk.Frame(button_frame)
        frame.pack(pady=2, fill="x")

        run_btn = tk.Button(frame, text=app, width=25, command=lambda a=app: run_app(a))
        run_btn.pack(side="left", padx=5)

        del_btn = tk.Button(frame, text="Delete", fg="red", command=lambda a=app: delete_app(a))
        del_btn.pack(side="left", padx=5)

def auto_refresh():
    """Automatically refresh buttons every 2 seconds"""
    refresh_buttons()
    root.after(2000, auto_refresh)

# ------------------- GUI Setup -------------------

root = tk.Tk()
root.title("Master Python App Launcher")

button_frame = tk.Frame(root)
button_frame.pack(padx=10, pady=10)

add_button = tk.Button(root, text="Add Python App(s)", width=30, command=add_apps)
add_button.pack(pady=5)

refresh_buttons()
auto_refresh()  # start auto-refresh

root.mainloop()

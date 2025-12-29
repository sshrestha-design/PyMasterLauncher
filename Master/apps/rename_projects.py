import os
import re
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from datetime import datetime

PROJECT_TYPES = ['app', 'ios', 'mac', 'android', 'web', 'unity', 'film', 'video', 'tool', 'test']
PROJECT_STATUS = ['active', 'wip', 'inactive', 'archived', 'done']

def clean_name(name):
    name = name.lower()
    name = re.sub(r'[\s\-]+', '_', name)
    name = re.sub(r'[^a-z0-9_]', '', name)
    name = re.sub(r'_+', '_', name)
    return name

def generate_new_name(edited_name, type_value, status_value, year_value, version_value, client_value):
    # Use the user-edited name
    name = clean_name(edited_name)
    parts = [type_value, name]
    if client_value:
        parts.append(clean_name(client_value))
    if year_value:
        parts.append(str(year_value))
    if version_value:
        parts.append(f"v{version_value}")
    parts.append(status_value)
    return "_".join(parts)

def browse_folder():
    path = filedialog.askdirectory()
    if path:
        folder_path_var.set(path)
        folder_name_var.set(os.path.basename(path))
        preview_name()

def preview_name(*args):
    edited_name = folder_name_var.get()
    new_name = generate_new_name(
        edited_name,
        type_var.get(),
        status_var.get(),
        year_var.get(),
        version_var.get(),
        client_var.get()
    )
    preview_var.set(new_name)

def apply_rename():
    folder = folder_path_var.get()
    new_name = preview_var.get()
    if not folder or not os.path.exists(folder):
        messagebox.showerror("Error", "Please select a valid folder")
        return

    # Confirmation popup
    confirm = messagebox.askyesno(
        "Confirm Rename",
        f"Are you sure you want to rename:\n\n{os.path.basename(folder)}\n\nto:\n\n{new_name}?"
    )
    if confirm:
        parent_dir = os.path.dirname(folder)
        new_path = os.path.join(parent_dir, new_name)
        if folder != new_path:
            os.rename(folder, new_path)
            messagebox.showinfo("Success", f"Folder renamed to:\n{new_name}")
            folder_path_var.set(new_path)  # Update path
            folder_name_var.set(os.path.basename(new_path))
        else:
            messagebox.showinfo("Info", "Folder name unchanged.")

# GUI
root = tk.Tk()
root.title("Single Project Folder Renamer (Editable Name)")
root.geometry("650x500")

folder_path_var = tk.StringVar()
folder_name_var = tk.StringVar()
preview_var = tk.StringVar()
type_var = tk.StringVar(value=PROJECT_TYPES[0])
status_var = tk.StringVar(value=PROJECT_STATUS[0])
year_var = tk.IntVar(value=datetime.now().year)
version_var = tk.StringVar(value="01")
client_var = tk.StringVar()

# Widgets
tk.Label(root, text="Select Project Folder:").pack(anchor="w", padx=10, pady=5)
tk.Entry(root, textvariable=folder_path_var, width=60, state="readonly").pack(anchor="w", padx=10)
tk.Button(root, text="Browse", command=browse_folder).pack(anchor="w", padx=10, pady=5)

tk.Label(root, text="Edit Folder Name:").pack(anchor="w", padx=10, pady=5)
tk.Entry(root, textvariable=folder_name_var, width=50).pack(anchor="w", padx=10)

tk.Label(root, text="Project Type:").pack(anchor="w", padx=10, pady=5)
ttk.Combobox(root, textvariable=type_var, values=PROJECT_TYPES, state="readonly").pack(anchor="w", padx=10)

tk.Label(root, text="Status:").pack(anchor="w", padx=10, pady=5)
ttk.Combobox(root, textvariable=status_var, values=PROJECT_STATUS, state="readonly").pack(anchor="w", padx=10)

tk.Label(root, text="Year:").pack(anchor="w", padx=10, pady=5)
tk.Entry(root, textvariable=year_var, width=10).pack(anchor="w", padx=10)

tk.Label(root, text="Version:").pack(anchor="w", padx=10, pady=5)
tk.Entry(root, textvariable=version_var, width=10).pack(anchor="w", padx=10)

tk.Label(root, text="Client / Optional Tag:").pack(anchor="w", padx=10, pady=5)
tk.Entry(root, textvariable=client_var, width=40).pack(anchor="w", padx=10)

tk.Label(root, text="Preview New Folder Name:").pack(anchor="w", padx=10, pady=5)
tk.Entry(root, textvariable=preview_var, width=55, state="readonly").pack(anchor="w", padx=10)

# Rename button – bold and colored
rename_btn = tk.Button(root, text="Rename Folder", command=apply_rename, bg="#4CAF50", fg="white", font=("Arial", 12, "bold"))
rename_btn.pack(anchor="w", padx=10, pady=20, ipadx=10, ipady=5)

# Update preview when options change
folder_name_var.trace("w", preview_name)
type_var.trace("w", preview_name)
status_var.trace("w", preview_name)
year_var.trace("w", preview_name)
version_var.trace("w", preview_name)
client_var.trace("w", preview_name)

root.mainloop()

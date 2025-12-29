import os
import subprocess
import tkinter as tk
from tkinter import filedialog, messagebox
from tkinter import ttk
from PIL import Image, ImageTk

# --- Config ---
VIDEO_EXTENSIONS = ('.mov', '.mp4', '.mxf', '.avi', '.mkv')
SHOT_TYPES = ['Wide', 'Medium', 'Close-up', 'Over-the-shoulder', 'Tracking', 
              'Cutaway', 'Insert', 'POV', 'Establishing', 'Two-shot']

# --- Helper Functions ---
def get_video_duration(file_path):
    """Get video duration in seconds using ffprobe (from ffmpeg)"""
    try:
        result = subprocess.run(
            ['ffprobe', '-v', 'error', '-show_entries',
             'format=duration', '-of',
             'default=noprint_wrappers=1:nokey=1', file_path],
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT
        )
        return round(float(result.stdout), 2)
    except:
        return 0.0

def get_thumbnail(file_path):
    """Extract a thumbnail frame using ffmpeg"""
    thumb_path = os.path.join(thumbnails_folder, os.path.basename(file_path) + ".png")
    if not os.path.exists(thumb_path):
        subprocess.run([
            'ffmpeg', '-y', '-i', file_path, '-ss', '00:00:01', '-vframes', '1', thumb_path
        ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    return thumb_path

def import_clips():
    folder = filedialog.askdirectory()
    if not folder:
        return
    table.delete(*table.get_children())
    global clips_folder
    clips_folder = folder
    os.makedirs(thumbnails_folder, exist_ok=True)
    for file in os.listdir(folder):
        abs_path = os.path.join(folder, file)
        if os.path.isfile(abs_path) and file.lower().endswith(VIDEO_EXTENSIONS):
            duration = get_video_duration(abs_path)
            table.insert('', 'end', values=(file, '', '', '', duration, ''))

def export_csv():
    if not table.get_children():
        messagebox.showwarning("Warning", "No clips to export")
        return
    save_path = filedialog.asksaveasfilename(defaultextension=".csv", filetypes=[("CSV Files","*.csv")])
    if not save_path:
        return
    import csv
    with open(save_path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(['Clip Name', 'Scene', 'Take', 'Shot Type', 'Duration (s)', 'Notes'])
        for item in table.get_children():
            writer.writerow(table.item(item)['values'])
    messagebox.showinfo("Success", f"Shot list exported to {save_path}")

def show_thumbnail(event):
    selected = table.selection()
    if not selected:
        return
    item = selected[0]
    clip_name = table.item(item)['values'][0]
    clip_path = os.path.join(clips_folder, clip_name)
    thumb_path = get_thumbnail(clip_path)
    img = Image.open(thumb_path)
    img.thumbnail((250, 140))
    photo = ImageTk.PhotoImage(img)
    thumbnail_label.config(image=photo)
    thumbnail_label.image = photo

def play_clip():
    selected = table.selection()
    if not selected:
        messagebox.showwarning("No clip selected", "Please select a clip to play")
        return
    item = selected[0]
    clip_name = table.item(item)['values'][0]
    clip_path = os.path.join(clips_folder, clip_name)
    if os.path.exists(clip_path):
        subprocess.run(["open", "-a", "QuickTime Player", clip_path])
    else:
        messagebox.showerror("Error", f"Clip not found: {clip_path}")

# --- Editable Table with Shot Type Dropdown ---
def on_double_click(event):
    item = table.identify_row(event.y)
    column = table.identify_column(event.x)
    if not item:
        return
    col_index = int(column[1:]) - 1
    x, y, width, height = table.bbox(item, column)
    value = table.item(item)['values'][col_index]

    # If Shot Type column, use Combobox
    if columns[col_index] == "Shot Type":
        combo = ttk.Combobox(root, values=SHOT_TYPES, state="readonly")
        combo.place(x=x+table.winfo_rootx()-root.winfo_rootx(), y=y+table.winfo_rooty()-root.winfo_rooty(), width=width, height=height)
        combo.set(value)
        combo.focus()

        def save_edit(event):
            values = list(table.item(item)['values'])
            values[col_index] = combo.get()
            table.item(item, values=values)
            combo.destroy()

        combo.bind('<Return>', save_edit)
        combo.bind('<FocusOut>', lambda e: combo.destroy())
    else:
        # normal Entry for other columns
        entry = tk.Entry(root)
        entry.place(x=x+table.winfo_rootx()-root.winfo_rootx(), y=y+table.winfo_rooty()-root.winfo_rooty(), width=width, height=height)
        entry.insert(0, value)
        entry.focus()

        def save_edit(event):
            values = list(table.item(item)['values'])
            values[col_index] = entry.get()
            table.item(item, values=values)
            entry.destroy()

        entry.bind('<Return>', save_edit)
        entry.bind('<FocusOut>', lambda e: entry.destroy())

# --- GUI ---
root = tk.Tk()
root.title("Storyboard / Shot List Generator Full Version")
root.geometry("1200x550")

clips_folder = ''
thumbnails_folder = os.path.expanduser("~/.shotlist_thumbs")
os.makedirs(thumbnails_folder, exist_ok=True)

# Top buttons
btn_frame = tk.Frame(root)
btn_frame.pack(fill='x', padx=10, pady=5)
tk.Button(btn_frame, text="Import Clips", command=import_clips).pack(side='left', padx=5)
tk.Button(btn_frame, text="Export CSV", command=export_csv).pack(side='left', padx=5)
tk.Button(btn_frame, text="Play Clip", command=play_clip, bg="#2196F3", fg="white").pack(side='left', padx=5)

# Main frame
main_frame = tk.Frame(root)
main_frame.pack(fill='both', expand=True, padx=10, pady=5)

# Table Columns
columns = ('Clip Name', 'Scene', 'Take', 'Shot Type', 'Duration (s)', 'Notes')
table = ttk.Treeview(main_frame, columns=columns, show='headings', height=20)
for col in columns:
    table.heading(col, text=col)
    table.column(col, width=150 if col not in ['Notes'] else 250)
table.pack(side='left', fill='both', expand=True)

# Scrollbar
scrollbar = ttk.Scrollbar(main_frame, orient="vertical", command=table.yview)
scrollbar.pack(side='left', fill='y')
table.configure(yscrollcommand=scrollbar.set)

# Thumbnail preview
thumbnail_label = tk.Label(main_frame, text="Select a clip to see thumbnail", bg="#ddd", width=35, height=10)
thumbnail_label.pack(side='left', padx=10)

# Bindings
table.bind('<Double-1>', on_double_click)
table.bind('<<TreeviewSelect>>', show_thumbnail)

root.mainloop()

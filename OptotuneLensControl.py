import customtkinter as ctk
from lib import Lens
import serial.tools.list_ports
from tkinter import messagebox, PhotoImage

# ------------------ CustomTkinter Settings ------------------
ctk.set_appearance_mode("Light")
ctk.set_default_color_theme("blue")

# ------------------ Detect Lenses ------------------
ports = list(serial.tools.list_ports.comports())
if len(ports) == 0:
    messagebox.showerror("No Lenses Detected", "Please connect at least one lens and restart.")
    exit()

# ------------------ Initialize Lenses ------------------
lenses = []
lens_types = []
slider_ranges = []
preset_values_all = []

for p in ports:
    lens = Lens(p.name)
    lens.to_focal_power_mode()
    lenses.append(lens)

    serial_num = lens.get_lens_serial_number()

    if serial_num.startswith("ANAB"):  # EL-16-40
        lens_type = "EL-16-40"
        slider_min, slider_max = -10.0, 10.0
        presets = [-10, -5, -2, 0, 2, 5, 10]
    elif serial_num.startswith("CBAA"):  # Autofocal EL-35-45
        lens_type = "Autofocal EL-35-45"
        slider_min, slider_max = -2.0, 3.0
        presets = [-2, -1, 0, 1, 2, 3]
    else:
        lens_type = "Unknown"
        slider_min, slider_max = -2.0, 3.0
        presets = [-2, -1, 0, 1, 2, 3]

    lens_types.append(lens_type)
    slider_ranges.append((slider_min, slider_max))
    preset_values_all.append(presets)

# ------------------ Helper Functions ------------------
def center_window(window, width, height):
    window.update_idletasks()
    x = (window.winfo_screenwidth() // 2) - (width // 2)
    y = (window.winfo_screenheight() // 2) - (height // 2)
    window.geometry(f"{width}x{height}+{x}+{y}")

def update_current_label(val, slider_min, slider_max):
    val = float(val)
    current_label.configure(text=f"Current: {val:.2f} D")
    if slider_min <= val <= slider_max:
        current_label.configure(fg_color="green")
    elif -10 <= val <= 10:
        current_label.configure(fg_color="orange")
    else:
        current_label.configure(fg_color="red")

def set_lens_power(val):
    val = float(val)
    for lens in lenses:
        lens.set_diopter(val)
    update_current_label(val, slider_min_global, slider_max_global)
    entry_val.delete(0, ctk.END)
    entry_val.insert(0, f"{val:.2f}")
    if slider_min_global <= val <= slider_max_global:
        slider.set(val)

def set_from_slider(val):
    set_lens_power(val)

def step_value(step):
    try:
        val = float(entry_val.get())
        val += step
        val = max(-10, min(10, val))
        set_lens_power(val)
    except ValueError:
        messagebox.showerror("Error", "Invalid value in entry")

# ------------------ Determine global slider range and presets ----------
# If multiple lenses with different ranges, choose overlapping range
slider_min_global = max([rng[0] for rng in slider_ranges])
slider_max_global = min([rng[1] for rng in slider_ranges])
preset_values_global = preset_values_all[0]  # use first lens presets for simplicity


# ------------------ GUI ------------------
root = ctk.CTk()
root.title("Optotune Lens Driver")
center_window(root, 700, 500)
root.resizable(False, False)
from PIL import Image, ImageTk

# Load the image
logo = ctk.CTkImage(light_image=Image.open("Zeiss-logo2.png"),
                          dark_image=Image.open("Zeiss-logo2.png"),
                          size=(50, 50))

# Display in the GUI
top_frame = ctk.CTkFrame(root)
top_frame.pack(pady=2)
ctk.CTkLabel(top_frame, image=logo, text="").pack()

# ---------- Lens Info ----------
lens_info_text = "Connected Lenses: " + ", ".join(lens_types)
ctk.CTkLabel(root, text=lens_info_text, font=("Arial", 14)).pack(pady=10)

# ---------- Slider ----------
frame_slider = ctk.CTkFrame(root, corner_radius=10)
frame_slider.pack(pady=10, padx=20, fill="x")

ctk.CTkLabel(frame_slider, text="Adjust Focal Power", font=("Arial", 16)).pack(pady=5)

slider = ctk.CTkSlider(frame_slider, from_=slider_min_global, to=slider_max_global,
                       number_of_steps=50, width=600, command=set_from_slider)
slider.pack(pady=10)

frame_minmax = ctk.CTkFrame(frame_slider, corner_radius=0, fg_color="transparent")
frame_minmax.pack(fill="x", padx=10)
ctk.CTkLabel(frame_minmax, text=f"{slider_min_global:.1f} D").pack(side="left")
ctk.CTkLabel(frame_minmax, text=f"{slider_max_global:.1f} D").pack(side="right")

# ---------- Entry ----------
frame_entry = ctk.CTkFrame(root, corner_radius=10)
frame_entry.pack(pady=10, padx=20, fill="x")

ctk.CTkLabel(frame_entry, text=f"Enter a Focal Power value ({slider_min_global:.1f} to {slider_max_global:.1f} D)",
             font=("Arial", 16)).pack(pady=5)

entry_val = ctk.CTkEntry(frame_entry, placeholder_text=f"{slider_min_global} to {slider_max_global}", width=120, justify="center")
entry_val.pack(pady=5)
entry_val.insert(0, "0.00")
entry_val.bind("<Return>", lambda event: set_lens_power(entry_val.get()))

# Step buttons
frame_steps = ctk.CTkFrame(frame_entry, corner_radius=10)
frame_steps.pack(pady=5)
ctk.CTkButton(frame_steps, text="Increment +0.25", width=80, command=lambda: step_value(0.25)).pack(side="left", padx=5)
ctk.CTkButton(frame_steps, text="Decrement -0.25", width=80, command=lambda: step_value(-0.25)).pack(side="left", padx=5)

# ---------- Preset Buttons ----------
frame_presets = ctk.CTkFrame(root, corner_radius=10)
frame_presets.pack(pady=10, padx=20, fill="x")
ctk.CTkLabel(frame_presets, text=f"Select a Focal Power value",
             font=("Arial", 16)).pack(pady=5)
for val in preset_values_global:
    ctk.CTkButton(frame_presets, text=f"{val:+.2f}", width=60, command=lambda v=val: set_lens_power(v)).pack(side="left", padx=17, pady=5)

# ---------- Current Power ----------
current_label = ctk.CTkLabel(root, text="Current: 0.00 D", font=("Arial", 16, "bold"),
                             fg_color="green", corner_radius=10)
current_label.pack(side="bottom", pady=15, padx=20, fill="x")

# ---------- On Close ----------
def on_closing():
    for lens in lenses:
        lens.connection.close()
    if messagebox.askokcancel("Quit", "Do you want to quit?"):
        root.destroy()

root.protocol("WM_DELETE_WINDOW", on_closing)
root.mainloop()

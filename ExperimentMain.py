import customtkinter as ctk
from tkinter import messagebox
from lib import Lens
import serial.tools.list_ports
import os
import csv
from datetime import datetime
import time

# ------------------ CustomTkinter Settings ------------------
ctk.set_appearance_mode("Light")
ctk.set_default_color_theme("blue")

# ------------------ Helper Functions ------------------
def center_window(window, width, height):
    window.update_idletasks()
    x = (window.winfo_screenwidth() // 2) - (width // 2)
    y = (window.winfo_screenheight() // 2) - (height // 2)
    window.geometry(f"{width}x{height}+{x}+{y}")

def get_save_path(participant_id, condition, trial_number):
    base_dir = "data"
    participant_dir = os.path.join(base_dir, participant_id)
    condition_dir = os.path.join(participant_dir, condition.replace(" ", ""))
    os.makedirs(condition_dir, exist_ok=True)
    filename = f"trial_{trial_number}.csv"
    return os.path.join(condition_dir, filename)

def log_power_change(participant_id, trial_number, condition, right_power, left_power, save=True):
    if condition == "Testing lenses" or not save:
        return
    file_path = get_save_path(participant_id, condition, trial_number)
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")
    file_exists = os.path.isfile(file_path)
    with open(file_path, 'a', newline='') as csvfile:
        writer = csv.writer(csvfile)
        if not file_exists:
            writer.writerow(["timestamp","participant","trial","condition","right_power","left_power"])
        writer.writerow([timestamp, participant_id, trial_number, condition, right_power, left_power])

# ------------------ Participant Info Window ------------------
from tkinter import ttk

def get_participant_info_window(prev_info=None):
    """
    Returns a dictionary: {'participant': str, 'trial': int, 'condition': str}
    prev_info: optional dict to prefill fields
    """
    result = {}

    def confirm(event=None):
        """Validate input and close window if valid."""
        if not entry_participant.get():
            messagebox.showerror("Error", "Please enter Participant ID", parent=window)
            return
        if dropdown_condition.get() == "":
            messagebox.showerror("Error", "Please select a Condition", parent=window)
            return
        if not entry_trial.get().isdigit():
            messagebox.showerror("Error", "Please enter a valid Trial number", parent=window)
            return
        result['participant'] = entry_participant.get()
        result['trial'] = int(entry_trial.get())
        result['condition'] = dropdown_condition.get()
        window.wait_window(window)  # Ensure window is closed before returning
        window.destroy()

    # ------------------ Window Setup ------------------
    window = ctk.CTk()
    window.title("Participant Info")
    #window should be centered
    center_window(window, 300, 320)
    window.resizable(False, False)
    window.grab_set()  # modal
    normal_color = "#FFFFFF"
    highlight_color = "#D0E8FF"

    # ------------------ Participant ID ------------------
    ctk.CTkLabel(window, text="Participant ID:").pack(pady=(20,5))
    entry_participant = ctk.CTkEntry(window, width=220, fg_color=normal_color)
    entry_participant.pack()
    if prev_info:
        entry_participant.insert(0, prev_info.get('participant',''))
    entry_participant.bind("<FocusIn>", lambda e: entry_participant.configure(fg_color=highlight_color))
    entry_participant.bind("<FocusOut>", lambda e: entry_participant.configure(fg_color=normal_color))

    # ------------------ Trial Number ------------------
    ctk.CTkLabel(window, text="Trial Number:").pack(pady=(10,5))
    entry_trial = ctk.CTkEntry(window, width=220, fg_color=normal_color)
    entry_trial.pack()
    if prev_info:
        entry_trial.insert(0, str(prev_info.get('trial','')))
    entry_trial.bind("<FocusIn>", lambda e: entry_trial.configure(fg_color=highlight_color))
    entry_trial.bind("<FocusOut>", lambda e: entry_trial.configure(fg_color=normal_color))

    # ------------------ Condition Dropdown ------------------
    ctk.CTkLabel(window, text="Condition:").pack(pady=(10, 5))

    # Wrap combobox in a CTkFrame for highlight
    frame_dropdown = ctk.CTkFrame(window, fg_color="#FFFFFF", corner_radius=5)
    frame_dropdown.pack(pady=(0, 5), padx=20, fill="x")

    dropdown_values = ["Testing lenses", "Control", "Baseline", "Fixed Blur", "Adaptive Blur"]
    dropdown_condition = ttk.Combobox(frame_dropdown, values=dropdown_values, state="readonly", width=25)
    dropdown_condition.pack(fill="x", padx=5, pady=5)

    # Pre-fill previous info if available
    if prev_info:
        dropdown_condition.set(prev_info.get('condition', ''))
    else:
        dropdown_condition.set("")

    # ------------------ Highlight on Focus ------------------
    def highlight_dropdown(event=None):
        frame_dropdown.configure(fg_color="#D0E8FF")  # highlight color

    def reset_dropdown(event=None):
        frame_dropdown.configure(fg_color="#FFFFFF")  # normal color

    # Bind focus events
    dropdown_condition.bind("<FocusIn>", highlight_dropdown)
    dropdown_condition.bind("<FocusOut>", reset_dropdown)

    # ------------------ Confirm Button ------------------
    confirm_btn = ctk.CTkButton(window, text="Confirm", command=confirm)
    confirm_btn.pack(pady=20)

    # ------------------ Tab Order ------------------
    widgets = [entry_participant, entry_trial, dropdown_condition, confirm_btn]
    for i, w in enumerate(widgets):
        w.tk_focusNext = lambda i=i: widgets[(i+1) % len(widgets)]
        w.bind("<Tab>", lambda e, i=i: (widgets[(i+1) % len(widgets)].focus_set(), "break"))

    # Enter key triggers confirm
    window.bind("<Return>", confirm)

    # Set initial focus
    entry_participant.focus_set()

    window.mainloop()
    return result

participant_info = get_participant_info_window()
if not participant_info:
    print("User cancelled participant info input.")
    exit()  # User cancelled

while True:
    # Construct potential CSV path
    participant_id = participant_info['participant']
    trial_number = participant_info['trial']
    condition = participant_info['condition']
    file_path = os.path.join("data", participant_id, condition.replace(" ",""), f"trial_{trial_number}.csv")

    if os.path.exists(file_path):
        # File exists, warn user
        messagebox.showwarning("File Exists",
            f"A CSV file already exists for Participant {participant_id}, Trial {trial_number}, Condition {condition}.\n\n"
            "Please check the filename and re-enter participant info to avoid overwriting.")
        # Reopen participant info dialog with previous info pre-filled
        participant_info = get_participant_info_window(prev_info=participant_info)
    else:
        # File does not exist, proceed
        break


participant_id = participant_info['participant']
trial_number = participant_info['trial']
condition = participant_info['condition']

# ------------------ Detect EL-35-45 Lenses ------------------
ports = list(serial.tools.list_ports.comports())
if len(ports) < 2:
    messagebox.showerror("Error", "Please connect two EL-35-45 lenses")
    exit()

right_lens = Lens(ports[0].name)
left_lens = Lens(ports[1].name)
lenses = [right_lens, left_lens]

for lens in lenses:
    lens.to_focal_power_mode()

slider_min = -2.0
slider_max = 3.0
preset_values = [-2, -1, 0, 1, 2, 3]

# ------------------ Lens GUI Functions ------------------
def update_current_label(val):
    val = float(val)
    current_label.configure(text=f"Current: {val:.2f} D")

def set_lens_power(val):
    val = float(val)
    for lens in lenses:
        lens.set_diopter(val)
    if condition == "Testing lenses":
        update_current_label(val)
        entry_val.delete(0, ctk.END)
        entry_val.insert(0, f"{val:.2f}")
        log_power_change(participant_id, trial_number, condition, right_lens.get_diopter(), left_lens.get_diopter())
        slider.set(val)
    else:
        log_power_change(participant_id, trial_number, condition, right_lens.get_diopter(), left_lens.get_diopter())
def set_from_slider(val):
    set_lens_power(val)

def step_value(step):
    try:
        val = float(entry_val.get())
        val += step
        val = max(slider_min, min(slider_max, val))
        set_lens_power(val)
    except ValueError:
        messagebox.showerror("Error", "Invalid value in entry")

# ------------------ Condition Logic Templates ------------------
def run_control_condition():
    # Example: set both lenses to 0 D and log once
    set_lens_power(0)
    log_power_change(participant_id, trial_number, condition, right_lens.get_diopter(), left_lens.get_diopter())
    messagebox.showinfo("Control Condition", "Lenses are set to 0 D for Control condition.")

def run_baseline_condition():
    # Example: set both lenses to 0 D (or baseline value) and log
    baseline_value = 0  # You can change this if baseline needs a different starting power
    set_lens_power(baseline_value)
    log_power_change(participant_id, trial_number, condition, right_lens.get_diopter(), left_lens.get_diopter())
    messagebox.showinfo("Baseline Condition", f"Lenses are set to {baseline_value} D for Baseline condition.")

def run_task_fixed_blur(fixed_value=1.0):
    set_lens_power(fixed_value)
    log_power_change(participant_id, trial_number, condition, right_lens.get_diopter(), left_lens.get_diopter())
    messagebox.showinfo("Fixed Blur Condition", f"Lenses are set to {fixed_value} D for Fixed Blur condition.")

def run_task_adaptive_blur(duration=10, step_interval=0.5):
    """
    Runs an adaptive blur sequence for a total of 'duration' seconds.
    step_interval: seconds between power updates
    """
    start_time = time.time()
    # Example sequence of blur values that repeat
    sequence = [0, 1, 2, 3]
    idx = 0
    while time.time() - start_time < duration:
        val = sequence[idx % len(sequence)]
        set_lens_power(val)
        log_power_change(participant_id, trial_number, condition,
                         right_lens.get_diopter(), left_lens.get_diopter())
        time.sleep(step_interval)
        idx += 1
    # Use existing root as parent to avoid creating a new hidden Tk window
    messagebox.showinfo("Adaptive Blur Condition",
                        "Adaptive Blur sequence completed.")
# ------------------ Launch GUI for Testing Lenses ------------------
if condition == "Testing lenses":
    root = ctk.CTk()
    root.title(f"Lens Control - Participant {participant_id}")
    center_window(root, 700, 500)
    root.resizable(False, False)

    # Slider Frame
    frame_slider = ctk.CTkFrame(root, corner_radius=10)
    frame_slider.pack(pady=15, padx=20, fill="x")
    ctk.CTkLabel(frame_slider, text="Adjust Focal Power (EL-35-45)", font=("Arial", 16)).pack(pady=5)
    slider = ctk.CTkSlider(frame_slider, from_=slider_min, to=slider_max, number_of_steps=50, width=600, command=set_from_slider)
    slider.pack(pady=10)
    frame_minmax = ctk.CTkFrame(frame_slider, corner_radius=0, fg_color="transparent")
    frame_minmax.pack(fill="x", padx=10)
    ctk.CTkLabel(frame_minmax, text=f"{slider_min:.1f} D").pack(side="left")
    ctk.CTkLabel(frame_minmax, text=f"{slider_max:.1f} D").pack(side="right")

    # Entry + Step Buttons
    frame_entry = ctk.CTkFrame(root, corner_radius=10)
    frame_entry.pack(pady=10, padx=20, fill="x")
    ctk.CTkLabel(frame_entry, text=f"Enter a Focal Power value ({slider_min} to {slider_max} D)", font=("Arial", 16)).pack(pady=5)
    entry_val = ctk.CTkEntry(frame_entry, placeholder_text=f"{slider_min} to {slider_max}", width=120, justify="center")
    entry_val.pack(pady=5)
    entry_val.insert(0, "0.00")
    entry_val.bind("<Return>", lambda event: set_lens_power(entry_val.get()))
    frame_steps = ctk.CTkFrame(frame_entry, corner_radius=10)
    frame_steps.pack(pady=5)
    ctk.CTkButton(frame_steps, text="Increment +0.25", width=80, command=lambda: step_value(0.25)).pack(side="left", padx=5)
    ctk.CTkButton(frame_steps, text="Decrement -0.25", width=80, command=lambda: step_value(-0.25)).pack(side="left", padx=5)

    # Preset Buttons

    frame_presets = ctk.CTkFrame(root, corner_radius=10)
    frame_presets.pack(pady=10, padx=20, fill="x")
    ctk.CTkLabel(frame_presets, text=f"Select a Focal Power value",
                 font=("Arial", 16)).pack(pady=5)

    for val in preset_values:
        ctk.CTkButton(frame_presets, text=f"{val:+.2f}", width=60, command=lambda v=val: set_lens_power(v)).pack(side="left", padx=25, pady=5)

    # Current Power Label
    current_label = ctk.CTkLabel(root, text="Current: 0.00 D", font=("Arial", 16, "bold"), fg_color="green", corner_radius=10)
    current_label.pack(side="bottom", pady=15, padx=20, fill="x")

    def on_closing():
        for lens in lenses:
            lens.connection.close()
        if messagebox.askokcancel("Quit", "Do you want to quit?"):
            root.destroy()

    root.protocol("WM_DELETE_WINDOW", on_closing)
    root.mainloop()
else:
    # ------------------ Non-testing Conditions ------------------
    if condition.lower() == "control":
        run_control_condition()
    elif condition.lower() == "baseline":
        run_baseline_condition()
    elif condition.lower() == "fixed blur":
        run_task_fixed_blur()
    elif condition.lower() == "adaptive blur":
        run_task_adaptive_blur()
    else:
        messagebox.showerror("Error", f"Unknown condition: {condition}")

    # Close lenses after condition run
    for lens in lenses:
        lens.connection.close()

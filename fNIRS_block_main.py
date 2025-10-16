# ------------------ Imports ------------------
import customtkinter as ctk
from tkinter import messagebox, ttk
import serial.tools.list_ports
import os
import csv
from datetime import datetime
import time
from lib import Lens
from pylsl import StreamInfo, StreamOutlet
import random

# ------------------ CustomTkinter Settings ------------------
ctk.set_appearance_mode("Light")
ctk.set_default_color_theme("blue")

# ------------------ LSL Marker Stream ------------------
info = StreamInfo(name='MarkerStream', type='Markers', channel_count=1,
                  channel_format='int32', source_id='fNIRS_marker_001')
lsl_outlet = StreamOutlet(info)


def send_marker(code):
    lsl_outlet.push_sample([code])
    print(f"[LSL] Marker sent: {code} at {datetime.now()}")


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
            writer.writerow(["timestamp", "participant", "trial", "condition", "right_power", "left_power"])
        writer.writerow([timestamp, participant_id, trial_number, condition, right_power, left_power])


# ------------------ Participant Info Window ------------------
def get_participant_info_window(prev_info=None):
    result = {}

    def confirm(event=None):
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
        window.destroy()

    window = ctk.CTk()
    window.title("Participant Info")
    center_window(window, 300, 320)
    window.resizable(False, False)
    window.grab_set()  # modal
    normal_color = "#FFFFFF"
    highlight_color = "#D0E8FF"
    # Participant ID
    ctk.CTkLabel(window, text="Participant ID:").pack(pady=(20, 5))
    entry_participant = ctk.CTkEntry(window, width=220, fg_color=normal_color)
    entry_participant.pack()
    if prev_info:
        entry_participant.insert(0, prev_info.get('participant', ''))
    entry_participant.bind("<FocusIn>", lambda e: entry_participant.configure(fg_color=highlight_color))
    entry_participant.bind("<FocusOut>", lambda e: entry_participant.configure(fg_color=normal_color))
    # Trial Number
    ctk.CTkLabel(window, text="Trial Number:").pack(pady=(10, 5))
    entry_trial = ctk.CTkEntry(window, width=220, fg_color=normal_color)
    entry_trial.pack()
    if prev_info:
        entry_trial.insert(0, str(prev_info.get('trial', '')))
    entry_trial.bind("<FocusIn>", lambda e: entry_trial.configure(fg_color=highlight_color))
    entry_trial.bind("<FocusOut>", lambda e: entry_trial.configure(fg_color=normal_color))
    # Condition Dropdown
    ctk.CTkLabel(window, text="Condition:").pack(pady=(10, 5))
    frame_dropdown = ctk.CTkFrame(window, fg_color="#FFFFFF", corner_radius=5)
    frame_dropdown.pack(pady=(0, 5), padx=20, fill="x")
    dropdown_values = ["Testing lenses", "Control", "Baseline", "Fixed Blur", "Adaptive Blur"]
    dropdown_condition = ttk.Combobox(frame_dropdown, values=dropdown_values, state="readonly", width=25)
    dropdown_condition.pack(fill="x", padx=5, pady=5)
    if prev_info:
        dropdown_condition.set(prev_info.get('condition', ''))
    else:
        dropdown_condition.set("")

    def highlight_dropdown(event=None):
        frame_dropdown.configure(fg_color="#D0E8FF")

    def reset_dropdown(event=None):
        frame_dropdown.configure(fg_color="#FFFFFF")

    dropdown_condition.bind("<FocusIn>", highlight_dropdown)
    dropdown_condition.bind("<FocusOut>", reset_dropdown)
    # Confirm Button
    confirm_btn = ctk.CTkButton(window, text="Confirm", command=confirm)
    confirm_btn.pack(pady=20)
    window.bind("<Return>", confirm)
    entry_participant.focus_set()
    window.mainloop()
    return result


# ------------------ Detect Lenses ------------------
ports = list(serial.tools.list_ports.comports())
if len(ports) < 2:
    messagebox.showerror("Error", "Please connect two EL-35-45 lenses")
    exit()
right_lens = Lens(ports[0].name)
left_lens = Lens(ports[1].name)
lenses = [right_lens, left_lens]
for lens in lenses:
    lens.to_focal_power_mode()

# ------------------ Lens Control Functions ------------------
slider_min = -2.0
slider_max = 3.0
preset_values = [-2, -1, 0, 1, 2, 3]


def set_lens_power(val):
    val = float(val)
    for lens in lenses:
        lens.set_diopter(val)

    # Log power and send lens switch marker
    log_power_change(participant_id, trial_number, condition,
                     right_lens.get_diopter(), left_lens.get_diopter())
    send_marker(900)  # Lens switch trigger

    # Only update GUI label if it exists
    try:
        current_label.configure(text=f"Current: {val:.2f} D")
    except NameError:
        pass

    # Update entry and slider if GUI exists
    try:
        entry_val.delete(0, ctk.END)
        entry_val.insert(0, f"{val:.2f}")
        slider.set(val)
    except NameError:
        pass


# ------------------ GUI for Testing Lenses ------------------
#def update_current_label(val):
#    current_label.configure(text=f"Current: {val:.2f} D")


# ------------------ Experimental Block Runner ------------------
def run_block(load, blur, trial_num):
    """
    Run a single experimental block:
    Lens switch → Prep → Active Task → Post-task → Baseline
    """
    print(f"Running block: Load={load}, Blur={blur}, Trial={trial_num}")

    # Lens switch
    set_lens_power(blur)
    time.sleep(1)

    # Prep cue
    send_marker(910)
    time.sleep(3)

    # Active task
    task_code = (200 if load == "High" else 100) + blur_levels.index(blur) + 1
    send_marker(task_code)  # task onset
    time.sleep(20)
    send_marker(task_code + 500)  # task offset

    # Post-task
    send_marker(13)
    time.sleep(5)

    # Baseline
    send_marker(14)
    time.sleep(20)

    # Log block
    log_power_change(participant_id, trial_num, f"{load}_{blur}",
                     right_lens.get_diopter(), left_lens.get_diopter())


# ------------------ Main Script ------------------
participant_info = get_participant_info_window()
if not participant_info:
    print("User cancelled input.")
    exit()
participant_id = participant_info['participant']
trial_number = participant_info['trial']
condition = participant_info['condition']

# ------------------ Define Experiment Parameters ------------------
loads = ["Low", "High"]
blur_levels = [-2, -1, 0, 1, 2]
repeats = 3

# ------------------ Run Experiment ------------------
trial_counter = trial_number
for repeat in range(repeats):
    for load in loads:
        for blur in blur_levels:
            run_block(load, blur, trial_counter)
            trial_counter += 1

# ------------------ Close Lenses ------------------
for lens in lenses:
    lens.connection.close()

messagebox.showinfo("Experiment Complete", "All blocks finished successfully!")

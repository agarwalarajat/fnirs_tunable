# ------------------ Imports ------------------
import customtkinter as ctk
from tkinter import messagebox
import serial.tools.list_ports
import os
import csv
from datetime import datetime
import time
from lib import Lens
from pylsl import StreamInfo, StreamOutlet
import random
import pandas as pd
import simpleaudio as sa
import numpy as np
import winsound

# ------------------ CustomTkinter Settings ------------------
ctk.set_appearance_mode("Light")
ctk.set_default_color_theme("blue")

# ------------------ LSL Marker Stream ------------------
info = StreamInfo(name='MarkerStream', type='Markers', channel_count=1,
                  channel_format='int32', source_id='fNIRS_marker_001')
lsl_outlet = StreamOutlet(info)
def play_start_tone(frequency=440, duration=0.5):
    """
    Play a simple tone at given frequency (Hz) and duration (s)
    """
    fs = 44100  # sampling rate
    t = np.linspace(0, duration, int(fs * duration), False)
    tone = np.sin(frequency * t * 2 * np.pi)
    audio = (tone * 32767).astype(np.int16)
    play_obj = sa.play_buffer(audio, 1, 2, fs)
    play_obj.wait_done()
def send_marker(code, name=None):
    """Send numeric LSL marker; print name in console for reference."""
    lsl_outlet.push_sample([code])
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")
    if name:
        print(f"[LSL] Marker sent: {code} ({name}) at {timestamp}")
    else:
        print(f"[LSL] Marker sent: {code} at {timestamp}")

# ------------------ Helper Functions ------------------
def center_window(window, width, height):
    window.update_idletasks()
    x = (window.winfo_screenwidth() // 2) - (width // 2)
    y = (window.winfo_screenheight() // 2) - (height // 2)
    window.geometry(f"{width}x{height}+{x}+{y}")

def get_participant_info():
    """Prompt participant ID."""
    result = {}
    def confirm(event=None):
        if not entry.get():
            messagebox.showerror("Error", "Please enter Participant ID", parent=window)
            return
        result['participant'] = entry.get()
        window.destroy()

    window = ctk.CTk()
    window.title("Participant Info")
    center_window(window, 300, 150)
    window.resizable(False, False)
    window.grab_set()

    ctk.CTkLabel(window, text="Participant ID:").pack(pady=(20,5))
    entry = ctk.CTkEntry(window, width=200)
    entry.pack()
    entry.focus_set()
    ctk.CTkButton(window, text="Confirm", command=confirm).pack(pady=20)
    window.bind("<Return>", confirm)
    window.mainloop()
    return result.get('participant')

def get_trial_file_path(participant_id):
    folder = os.path.join("data", participant_id)
    os.makedirs(folder, exist_ok=True)
    return os.path.join(folder, f"{participant_id}_trials.csv")

def log_trial(participant_id, trial_number, condition, right_power, left_power, start_time, end_time):
    file_path = get_trial_file_path(participant_id)
    file_exists = os.path.isfile(file_path)
    with open(file_path, 'a', newline='') as f:
        writer = csv.writer(f)
        if not file_exists:
            writer.writerow(["participant","trial","condition","right_power","left_power","start_time","end_time"])
        writer.writerow([participant_id, trial_number, condition, right_power, left_power,
                         start_time.strftime("%Y-%m-%d %H:%M:%S.%f"),
                         end_time.strftime("%Y-%m-%d %H:%M:%S.%f")])

# ------------------ Participant & Lens Setup ------------------
participant_id = get_participant_info()
if not participant_id:
    exit()

ports = list(serial.tools.list_ports.comports())
simulation_mode = False
if len(ports) < 2:
    proceed = messagebox.askyesno(
        "Lenses Not Found",
        "Two EL-35-45 lenses not detected.\nRun in Simulation Mode?"
    )
    if not proceed:
        exit()
    simulation_mode = True
    print("[SIMULATION] Running without physical lenses.")
    class DummyLens:
        def __init__(self,name): self._diopter=0
        def to_focal_power_mode(self): pass
        def set_diopter(self,val): self._diopter=val
        def get_diopter(self): return self._diopter
        @property
        def connection(self): return self
        def close(self): pass
    right_lens, left_lens = DummyLens("R"), DummyLens("L")
    lenses = [right_lens, left_lens]
else:
    right_lens = Lens(ports[0].name)
    left_lens = Lens(ports[1].name)
    lenses = [right_lens, left_lens]
    for l in lenses: l.to_focal_power_mode()

# ------------------ Experiment Parameters ------------------
task_variants = ["Visuomotor","Motor-only","Visual-only","Baseline"]
blur_levels_vm_vo = [0,0.5,1.0,1.5,2.0]
blur_levels_motor = [0]
repeats = 3
marker_base = {"Visuomotor":200,"Motor-only":300,"Visual-only":400,"Baseline":500}

# Task-specific descriptions
task_descriptions = {
    "Visuomotor": "Move the bead from left to right \n follow the pattern.",
    "Motor-only": "Move the bead from left and right",
    "Visual-only": "Watch the board from left to right \n Do not move your head.",
    "Baseline": "+"
}

# ------------------ Generate Randomized Blocks ------------------
blocks = []
trial_counter = 1
for r in range(repeats):
    rep_blocks = []
    rep_blocks += [("Visuomotor",b) for b in blur_levels_vm_vo]
    rep_blocks += [("Motor-only",b) for b in blur_levels_motor]
    rep_blocks += [("Visual-only",b) for b in blur_levels_vm_vo]
    rep_blocks += [("Baseline", b) for b in blur_levels_vm_vo]
    random.shuffle(rep_blocks)
    print(rep_blocks)
    for task, blur in rep_blocks:
        blur_idx = 0 if task=="Motor-only" else blur_levels_vm_vo.index(blur)
        active_marker = marker_base[task] + blur_idx
        blocks.append({
            "Trial": trial_counter,
            "Task": task,
            "Blur(D)": blur,
            "Lens Switch":900,
            "Prep Cue":910,
            "Active Onset":active_marker,
            "Task Offset":active_marker+500,
            "Post-task":13,
            "Baseline":14
        })
        trial_counter += 1

# Save block randomization
folder = os.path.join("data", participant_id)
os.makedirs(folder, exist_ok=True)
pd.DataFrame(blocks).to_csv(os.path.join(folder,f"{participant_id}_blocks.csv"),index=False)
print(f"[INFO] Participant: {participant_id}")
print("[INFO] Randomized block order saved.")

# ------------------ Lens Control ------------------
def set_lens_power(val):
    val=float(val)
    for l in lenses:
        l.set_diopter(val)
    send_marker(900,"Lens Switch")

# ------------------ Instruction GUI ------------------
ctk.set_appearance_mode("Light")
ctk.set_default_color_theme("blue")
root = ctk.CTk()
width, height = 1000, 400
x_pos, y_pos = 550, 300  # 100 px from left, 200 px from top
root.geometry(f"{width}x{height}+{x_pos}+{y_pos}")
if root.winfo_screenwidth() > 1920:
    root.geometry(f"{width}x{height}+{x_pos+1920}+{y_pos}")
root.resizable(False, False)
root.attributes("-topmost", True)
root.title("Task Instructions")
instruction_label = ctk.CTkLabel(root,text="",font=("Arial",36))
instruction_label.pack(expand=True)
root.update()

# ------------------ Run a Single Block ------------------
def run_block(block):
    """
    Runs a single experimental block (trial).
    Displays task-specific instructions, controls lenses,
    plays tones, sends LSL markers, and logs results.
    """

    # --- Pre-block info ---
    next_info = f"{block['Task']} (Blur = {block['Blur(D)']}D)"
    choice = messagebox.askyesnocancel(
        "Next Block Info",
        f"Upcoming Trial {block['Trial']}:\n{next_info}\n\n"
        "Yes → Start\nNo → Pause\nCancel → Stop",
        parent=root
    )

    # Handle cancel / pause / resume
    if choice is None:
        messagebox.showinfo("Experiment Stopped", "Experiment terminated by user.", parent=root)
        return False
    elif choice is False:
        messagebox.showinfo("Paused", "Experiment paused. Press OK to continue.", parent=root)
        resume = messagebox.askyesnocancel(
            "Resume Experiment",
            f"Upcoming Trial {block['Trial']}:\n{next_info}\n\nYes → Start\nCancel → Stop",
            parent=root
        )
        if resume is None:
            return False

    # --- Begin block ---
    start_time = datetime.now()

    # ------------------ Lens Switching ------------------
    if block["Task"] != "Baseline":
        instruction_label.configure(text="Lens Switching...\n\nSetting blur value")
        root.update()
        set_lens_power(block["Blur(D)"])
        time.sleep(1)
        send_marker(block["Lens Switch"], "Lens Switch")

    # ------------------ Baseline Block (special case) ------------------
    if block["Task"] == "Baseline":
        instruction_label.configure(
            text="Baseline Period\n\n+",
            font=("Arial", 72)
        )
        root.update()
        send_marker(block["Active Onset"], "Baseline Start")
        time.sleep(20)
        send_marker(block["Task Offset"], "Baseline End")

    # ------------------ All Other Tasks ------------------
    else:
        # Prep Cue
        prep_text = (
            f"Prepare for the task: {block['Task']}\n\n"
            f"{task_descriptions[block['Task']]}"
        )
        instruction_label.configure(text=prep_text)
        root.update()
        send_marker(block["Prep Cue"], "Prep Cue")
        time.sleep(3)

        # Active Task
        play_start_tone(frequency=1000, duration=0.5)
        active_text = (
            f"Active Task: {block['Task']}\n\n"
            f"{task_descriptions[block['Task']]}"
        )
        instruction_label.configure(text=active_text)
        root.update()
        send_marker(
            block["Active Onset"],
            f"Active Onset - {block['Task']} Blur {block['Blur(D)']}D"
        )
        time.sleep(20)

        # Post-task
        instruction_label.configure(text="Task Complete.\n\nPlease remain still.")
        root.update()
        send_marker(block["Task Offset"], "Task Offset")
        send_marker(block["Post-task"], "Post-task")
        time.sleep(5)

    # ------------------ Log and Wrap Up ------------------
    end_time = datetime.now()
    log_trial(
        participant_id,
        block["Trial"],
        f"{block['Task']}_{block['Blur(D)']}",
        right_lens.get_diopter(),
        left_lens.get_diopter(),
        start_time,
        end_time
    )

    send_marker(999, "Block Complete")
    print(f"[INFO] Trial {block['Trial']} complete.")
    return True

# ------------------ Run Experiment ------------------
for block in blocks:
    continue_exp = run_block(block)
    if not continue_exp: break

# ------------------ Close Lenses ------------------
for l in lenses:
    l.connection.close()
root.destroy()
messagebox.showinfo("Experiment Complete","All blocks finished successfully!")
# ------------------ Imports ------------------
import customtkinter as ctk
from tkinter import Tk, messagebox
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
from screeninfo import get_monitors
import random

# ------------------ CustomTkinter Settings ------------------
ctk.set_appearance_mode("Light")
ctk.set_default_color_theme("blue")

# ------------------ LSL Marker Stream ------------------
info = StreamInfo(name='UnityTriggers', type='Markers', channel_count=1,
                  channel_format='int32', source_id='fNIRS_marker_001')
lsl_outlet = StreamOutlet(info)

def play_start_tone(frequency=440, duration=0.5):
    fs = 44100
    t = np.linspace(0, duration, int(fs * duration), False)
    tone = np.sin(frequency * t * 2 * np.pi)
    audio = (tone * 32767).astype(np.int16)
    sa.play_buffer(audio, 1, 2, fs).wait_done()

def send_marker(code, name=None):
    lsl_outlet.push_sample([code])
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")
    if name:
        print(f"[LSL] Marker sent: {code} ({name}) at {timestamp}")
    else:
        print(f"[LSL] Marker sent: {code} at {timestamp}")

# ------------------ Display Setup ------------------
monitors = get_monitors()
primary_monitor = next(m for m in monitors if m.is_primary)
#secondary_monitor = next(m for m in monitors if not m.is_primary)

secondary_monitor = next(m for m in monitors if m.is_primary)

# Hidden base root for all messageboxes
root_base = Tk()
root_base.withdraw()
root_base.geometry(f"+{primary_monitor.x + primary_monitor.width // 2}+{primary_monitor.y + primary_monitor.height // 2}")

# ------------------ Helper Functions ------------------
def center_window(window, width, height):
    window.update_idletasks()
    x = (window.winfo_screenwidth() // 2) - (width // 2)
    y = (window.winfo_screenheight() // 2) - (height // 2)
    window.geometry(f"{width}x{height}+{x}+{y}")

def get_participant_info():
    result = {}

    win = ctk.CTkToplevel()
    win.title("Participant Info")
    center_window(win, 300, 220)
    win.resizable(False, False)
    win.grab_set()

    ctk.CTkLabel(win, text="Participant ID:").pack(pady=(20, 5))
    entry = ctk.CTkEntry(win, width=200)
    entry.pack()
    entry.focus_set()

    ctk.CTkLabel(win, text="Run Type:").pack(pady=(15, 5))
    run_type_var = ctk.StringVar(value="Main")
    run_type_option = ctk.CTkOptionMenu(win, variable=run_type_var, values=["Main", "Practice"])
    run_type_option.pack()

    def confirm(event=None):
        pid = entry.get().strip()
        if not pid:
            messagebox.showerror("Error", "Please enter Participant ID", parent=root_base)
            return
        run_type = run_type_var.get()
        result['participant'] = f"{pid}_{run_type}"
        win.destroy()

    ctk.CTkButton(win, text="Confirm", command=confirm).pack(pady=20)
    win.bind("<Return>", confirm)
    win.wait_window()
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
            writer.writerow(["participant", "trial", "condition", "right_power", "left_power", "start_time", "end_time"])
        writer.writerow([
            participant_id,
            trial_number,
            condition,
            right_power,
            left_power,
            start_time.strftime("%Y-%m-%d %H:%M:%S.%f"),
            end_time.strftime("%Y-%m-%d %H:%M:%S.%f")
        ])

# ------------------ Participant & Lens Setup ------------------
participant_id = get_participant_info()
if not participant_id:
    exit()

ports = list(serial.tools.list_ports.comports())
simulation_mode = False
if len(ports) < 2:
    proceed = messagebox.askyesno(
        "Lenses Not Found",
        "Two EL-35-45 lenses not detected.\nRun in Simulation Mode?",
        parent=root_base
    )
    if not proceed:
        exit()
    simulation_mode = True
    print("[SIMULATION] Running without physical lenses.")
    class DummyLens:
        def __init__(self, name): self._diopter = 0
        def to_focal_power_mode(self): pass
        def set_diopter(self, val): self._diopter = val
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
    for l in lenses:
        l.to_focal_power_mode()

# ------------------ Experiment Parameters ------------------
task_variants = ["Visuomotor", "Motor-only", "Visual-only", "Baseline"]

# Detect if this is a practice run
is_practice = "Practice" in participant_id

if is_practice:
    blur_levels_vm_vo = [0, 0.5]
    blur_levels_motor = [0]
    repeats = 1
    print("[INFO] Practice run detected: Using reduced block set (1 repeat, 0 & 0.5 D)")
else:
    blur_levels_vm_vo = [0, 0.5, 1.0, 1.5, 2.0]
    blur_levels_motor = [0]
    repeats = 3
    print("[INFO] Main run detected: Using full block set (3 repeats, 5 blur levels)")

marker_base = {"Visuomotor": 200, "Motor-only": 300, "Visual-only": 400, "Baseline": 500}
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
    rep_blocks += [("Visuomotor", b) for b in blur_levels_vm_vo]
    rep_blocks += [("Motor-only", b) for b in blur_levels_motor]
    rep_blocks += [("Visual-only", b) for b in blur_levels_vm_vo]
    rep_blocks += [("Baseline", b) for b in blur_levels_vm_vo]
    random.shuffle(rep_blocks)
    for task, blur in rep_blocks:
        blur_idx = 0 if task == "Motor-only" else blur_levels_vm_vo.index(blur)
        active_marker = marker_base[task] + blur_idx
        blocks.append({
            "Trial": trial_counter,
            "Task": task,
            "Blur(D)": blur,
            "Lens Switch": 900,
            "Prep Cue": 910,
            "Active Onset": active_marker,
            "Task Offset": active_marker + 500,
            "Post-task": 13,
            "Baseline": 14
        })
        trial_counter += 1

# Save block randomization
folder = os.path.join("data", participant_id)
os.makedirs(folder, exist_ok=True)
pd.DataFrame(blocks).to_csv(os.path.join(folder, f"{participant_id}_blocks.csv"), index=False)
print(f"[INFO] Participant: {participant_id}")
print("[INFO] Randomized block order saved.")

# ------------------ Lens Control ------------------
def set_lens_power(val):
    val = float(val)
    for l in lenses:
        l.set_diopter(val)
    send_marker(900, "Lens Switch")

# ------------------ Instruction GUI ------------------
root = ctk.CTk()
width, height = 1280, 768
x = secondary_monitor.x - 9
y = secondary_monitor.y - 2
root.geometry(f"{width}x{height}+{x}+{y}")
root.resizable(False, False)
root.attributes("-topmost", True)
root.title("Task Instructions")
instruction_label = ctk.CTkLabel(root, text="", font=("Arial", 36))
instruction_label.pack(expand=True)
root.update()

# ------------------ Run a Single Block ------------------
def run_block(block):
    start_time = datetime.now()

    # Lens setting
    instruction_label.configure(text="Lens Switching...\n\n Setting blur value")
    root.update()
    set_lens_power(block["Blur(D)"])
    time.sleep(1)
    print(f"[INFO] Setting blur value: {block['Blur(D)']}")
    send_marker(block["Lens Switch"], "Lens Switch")

    # Task sequence
    if block["Task"] == "Baseline":
        prep_text = f"Prepare for the task: {block['Task']}\n\n Look at the fixation cross"
        instruction_label.configure(text=prep_text)
        root.update()
        send_marker(block["Prep Cue"], "Prep Cue")
        time.sleep(3)

        play_start_tone(frequency=1500, duration=0.3)
        instruction_label.configure(text="+", font=("Arial", 72))
        root.update()
        send_marker(block["Active Onset"], f"Active Onset - {block['Task']} Blur {block['Blur(D)']}D")
        time.sleep(10)
        send_marker(block["Task Offset"], "Baseline End")

        play_start_tone(frequency=2500, duration=0.3)
        instruction_label.configure(text="Task Complete.\n\nPlease remain still.", font=("Arial", 36))
        root.update()
        send_marker(block["Post-task"], "Post-task")
        post_task_duration = random.uniform(5, 10)  # Random float between 5 and 10 seconds
        print(f"[INFO] Post-task wait: {post_task_duration:.2f} seconds")
        time.sleep(post_task_duration)
    else:
        prep_text = f"Prepare for the task: {block['Task']}\n\n{task_descriptions[block['Task']]}"
        if is_practice:
            prep_text = f"[Practice Run]\n\n{prep_text}"
        instruction_label.configure(text=prep_text)
        root.update()
        send_marker(block["Prep Cue"], "Prep Cue")
        time.sleep(3)

        play_start_tone(frequency=1000, duration=0.3)
        active_text = f"Active Task: {block['Task']}"
        if is_practice:
            active_text = f"Active Task (Practice): {block['Task']}"
        instruction_label.configure(text=active_text)
        root.update()
        send_marker(block["Active Onset"], f"Active Onset - {block['Task']} Blur {block['Blur(D)']}D")
        time.sleep(10)

        play_start_tone(frequency=2000, duration=0.3)
        instruction_label.configure(text="Task Complete.\n\nPlease remain still.")
        root.update()
        send_marker(block["Task Offset"], "Task Offset")
        send_marker(block["Post-task"], "Post-task")
        post_task_duration = random.uniform(5, 10)  # Random float between 5 and 10 seconds
        print(f"[INFO] Post-task wait: {post_task_duration:.2f} seconds")
        time.sleep(post_task_duration)

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
    if not continue_exp:
        break

# ------------------ Cleanup ------------------
for l in lenses:
    l.connection.close()
root.destroy()
messagebox.showinfo("Experiment Complete", "All blocks finished successfully!", parent=root_base)
root_base.destroy()

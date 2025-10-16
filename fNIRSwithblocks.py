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
import pandas as pd

# ------------------ CustomTkinter Settings ------------------
ctk.set_appearance_mode("Light")
ctk.set_default_color_theme("blue")

# ------------------ LSL Marker Stream ------------------
info = StreamInfo(name='MarkerStream', type='Markers', channel_count=1,
                  channel_format='int32', source_id='fNIRS_marker_001')
lsl_outlet = StreamOutlet(info)

def save_block_randomization(participant_id, blocks):
    base_dir = "data"
    participant_dir = os.path.join(base_dir, participant_id)
    os.makedirs(participant_dir, exist_ok=True)
    file_path = os.path.join(participant_dir, f"{participant_id}_blocks.csv")
    df_blocks = pd.DataFrame(blocks)
    df_blocks.to_csv(file_path, index=False)
    print(f"[INFO] Randomized block order saved to {file_path}")

def get_trial_data_path(participant_id):
    base_dir = "data"
    participant_dir = os.path.join(base_dir, participant_id)
    os.makedirs(participant_dir, exist_ok=True)
    file_path = os.path.join(participant_dir, f"{participant_id}_trials.csv")
    return file_path

def send_marker(code, name=None):
    lsl_outlet.push_sample([code])
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")
    if name is not None:
        print(f"[LSL] Marker sent: {code} ({name}) at {timestamp}")
    else:
        print(f"[LSL] Marker sent: {code} at {timestamp}")

# ------------------ Helper Functions ------------------
def center_window(window, width, height):
    window.update_idletasks()
    x = (window.winfo_screenwidth() // 2) - (width // 2)
    y = (window.winfo_screenheight() // 2) - (height // 2)
    window.geometry(f"{width}x{height}+{x}+{y}")

def get_save_path(participant_id):
    base_dir = "data"
    participant_dir = os.path.join(base_dir, participant_id)
    os.makedirs(participant_dir, exist_ok=True)
    filename = f"{participant_id}_blocks.csv"  # single CSV for all trials
    return os.path.join(participant_dir, filename)

def log_trial(participant_id, trial_number, condition, right_power, left_power, start_time, end_time):
    file_path = get_trial_data_path(participant_id)
    file_exists = os.path.isfile(file_path)

    with open(file_path, 'a', newline='') as csvfile:
        writer = csv.writer(csvfile)
        if not file_exists:
            writer.writerow(["participant", "trial", "condition", "right_power", "left_power",
                             "start_time", "end_time"])
        writer.writerow([participant_id, trial_number, condition, right_power, left_power,
                         start_time.strftime("%Y-%m-%d %H:%M:%S.%f"),
                         end_time.strftime("%Y-%m-%d %H:%M:%S.%f")])

def log_power_change(participant_id, trial_number, condition, right_power, left_power):
    file_path = get_save_path(participant_id)
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")
    file_exists = os.path.isfile(file_path)
    with open(file_path, 'a', newline='') as csvfile:
        writer = csv.writer(csvfile)
        if not file_exists:
            writer.writerow(["participant", "trial", "condition", "right_power", "left_power","timestamp"])
        writer.writerow([participant_id, trial_number, condition, right_power, left_power,timestamp])

# ------------------ Participant Info Window ------------------
def get_participant_info_window(prev_info=None):
    result = {}

    def confirm(event=None):
        if not entry_participant.get():
            messagebox.showerror("Error", "Please enter Participant ID", parent=window)
            return
        result['participant'] = entry_participant.get()
        window.destroy()

    window = ctk.CTk()
    window.title("Participant Info")
    center_window(window, 300, 200)
    window.resizable(False, False)
    window.grab_set()

    ctk.CTkLabel(window, text="Participant ID:").pack(pady=(20, 5))
    entry_participant = ctk.CTkEntry(window, width=220)
    entry_participant.pack()
    if prev_info:
        entry_participant.insert(0, prev_info.get('participant', ''))
    confirm_btn = ctk.CTkButton(window, text="Confirm", command=confirm)
    confirm_btn.pack(pady=20)

    window.bind("<Return>", confirm)
    entry_participant.focus_set()
    window.mainloop()
    return result

participant_info = get_participant_info_window()
if not participant_info:
    print("User cancelled input.")
    exit()

participant_id = participant_info['participant']
# Print participant name once
print(f"\n[INFO] Starting experiment for Participant: {participant_id}\n")

# ------------------ Detect Lenses or Use Simulation ------------------
ports = list(serial.tools.list_ports.comports())
simulation_mode = False

if len(ports) < 2:
    proceed = messagebox.askyesno(
        "Lenses Not Found",
        "Two EL-35-45 lenses were not detected.\nDo you want to run in Simulation Mode?"
    )
    if not proceed:
        exit()
    else:
        simulation_mode = True
        print("[SIMULATION] Running without physical lenses.")
        # Create dummy lens objects
        class DummyLens:
            def __init__(self, name):
                self.name = name
                self._diopter = 0.0
            def to_focal_power_mode(self):
                pass
            def set_diopter(self, val):
                self._diopter = val
            def get_diopter(self):
                return self._diopter
            @property
            def connection(self):
                return self
            def close(self):
                pass

        right_lens = DummyLens("RightLens")
        left_lens = DummyLens("LeftLens")
        lenses = [right_lens, left_lens]
else:
    # Physical lenses connected
    right_lens = Lens(ports[0].name)
    left_lens = Lens(ports[1].name)
    lenses = [right_lens, left_lens]
    for lens in lenses:
        lens.to_focal_power_mode()

# ------------------ Experimental Parameters ------------------
task_variants = ["Visuomotor", "Motor-only", "Visual-only"]
blur_levels_vm_vo = [0, 0.5, 1.0, 1.5, 2.0]
blur_levels_motor = [0]
repeats = 3
marker_base = {"Visuomotor": 200, "Motor-only": 300, "Visual-only": 400}

# ------------------ Generate Randomized Blocks ------------------
blocks = []
trial_counter = 1
for rep in range(1, repeats+1):
    rep_blocks = []
    rep_blocks += [("Visuomotor", blur) for blur in blur_levels_vm_vo]
    rep_blocks += [("Motor-only", blur) for blur in blur_levels_motor]
    rep_blocks += [("Visual-only", blur) for blur in blur_levels_vm_vo]
    random.shuffle(rep_blocks)
    for task, blur in rep_blocks:
        if task == "Motor-only":
            blur_index = 0
        else:
            blur_index = blur_levels_vm_vo.index(blur)
        active_marker = marker_base[task] + blur_index
        task_offset_marker = active_marker + 500
        blocks.append({
            "Trial": trial_counter,
            "Task": task,
            "Blur(D)": blur,
            "Lens Switch": 900,
            "Prep Cue": 910,
            "Active Onset": active_marker,
            "Task Offset": task_offset_marker,
            "Post-task": 13,
            "Baseline": 14
        })
        trial_counter += 1

# Save randomized block order
df_blocks = pd.DataFrame(blocks)
df_blocks.to_csv(get_save_path(participant_id), index=False)

# ------------------ Lens Control ------------------
def set_lens_power(val):
    val = float(val)
    for lens in lenses:
        lens.set_diopter(val)
    send_marker(900)

# ------------------ Run Single Block ------------------
def run_block(block):
    """
    Run a single experimental block.
    Logs start/end times, controls lens, sends LSL markers, prints marker names.
    """
    print(f"\n[INFO] Running Trial {block['Trial']}: {block['Task']} Blur={block['Blur(D)']}D")

    start_time = datetime.now()  # record trial start

    # Lens switch
    set_lens_power(block['Blur(D)'])
    send_marker(block['Lens Switch'], "Lens Switch")
    time.sleep(1)  # Lens stabilization

    # Prep cue
    send_marker(block['Prep Cue'], "Prep Cue")
    time.sleep(3)

    # Active task
    send_marker(block['Active Onset'], f"Active Onset - {block['Task']} Blur {block['Blur(D)']}D")
    time.sleep(20)  # Active task duration

    # Task offset and post-task
    send_marker(block['Task Offset'], "Task Offset")
    send_marker(block['Post-task'], "Post-task")
    time.sleep(5)

    # Baseline
    send_marker(block['Baseline'], "Baseline")
    time.sleep(20)  # Baseline duration

    end_time = datetime.now()  # record trial end

    # Log lens powers and trial times
    log_trial(
        participant_id,
        block['Trial'],
        f"{block['Task']}_{block['Blur(D)']}",
        right_lens.get_diopter(),
        left_lens.get_diopter(),
        start_time,
        end_time
    )

    # Send explicit block-complete marker
    send_marker(999, "Block Complete")
    print(f"[INFO] Trial {block['Trial']} complete.\n")


# ------------------ Run Experiment ------------------
for i, block in enumerate(blocks):
    # Next block info
    next_info = f"{block['Task']} Blur={block['Blur(D)']}D"

    # Pre-block dialog: Yes=Start, No=Pause, Cancel=Stop
    choice = messagebox.askyesnocancel(
        "Next Block Info",
        f"Upcoming Trial {block['Trial']}:\n{next_info}\n\n"
        "Yes → Start this block\nNo → Pause\nCancel → Stop Experiment"
    )

    if choice is None:  # Cancel → stop experiment
        messagebox.showinfo("Experiment Stopped", "Experiment terminated by user.")
        break
    elif choice is False:  # No → pause
        messagebox.showinfo("Paused", "Experiment paused. Press OK to continue.")
        # After pause, show same pre-block dialog again
        resume_choice = messagebox.askyesnocancel(
            "Resume Experiment",
            f"Upcoming Trial {block['Trial']}:\n{next_info}\n\n"
            "Yes → Start this block\nCancel → Stop Experiment"
        )
        if resume_choice is None:  # Cancel → stop
            messagebox.showinfo("Experiment Stopped", "Experiment terminated by user.")
            break
        # Yes → continue automatically

    # Yes → run block
    run_block(block)

# ------------------ Close Lenses ------------------
for lens in lenses:
    lens.connection.close()

messagebox.showinfo("Experiment Complete", "All blocks finished successfully!")

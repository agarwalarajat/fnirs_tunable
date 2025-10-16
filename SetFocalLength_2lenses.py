# -*- coding: utf-8 -*-
"""
Created on Mon Feb 15 13:47:04 2021

@author: Rajat Agarwala, ZVSL
"""

from lib import Lens
import serial.tools.list_ports
import time
import numpy

import tkinter as tk
import tkinter.messagebox as tkMessageBox
from tkinter.messagebox import _show
from tkinter import *
from PIL import ImageTk, Image
from functools import partial

##Determine COM port to which the serial device is connected
# only 1st four characters contain COM port number
ports = list(serial.tools.list_ports.comports())

# def set_D(val):
#     #i=float(input("Enter Diopter: "))
#     right_lens.set_diopter(float(val));
#     left_lens.set_diopter(float(val));
#     print(right_lens.get_diopter());
#     print(left_lens.get_diopter());

# def terminate_prog():

#     right_lens.connection.close()
#     left_lens.connection.close()
#     root.destroy()

def set_D(val):
    right_lens.set_diopter(float(val))
    left_lens.set_diopter(float(val))
    print(right_lens.get_diopter())
    print(left_lens.get_diopter())

for p in ports:
    comp = str(p)
    print(comp)
port = comp[:4]

if len(ports) > 1:
    right_port = ports[0].name;
    left_port = ports[1].name;
    print("Two lenses detected")

    right_lens = Lens(right_port,debug=False)  # set debug to True to see a serial communication log #for e.g. port=COM3
    left_lens = Lens(left_port, debug=False)  # set debug to True to see a serial communication log #for e.g. port=COM3

    diopter_initRight = right_lens.get_diopter()  # read diopter value
    diopter_initLeft = left_lens.get_diopter()  # read diopter value
    print('Initial Diopter value (Right Lens):', diopter_initRight)  # print current diopter value
    print('Initial Diopter value (Left lens):', diopter_initLeft)  # print current diopter value

    right_lens.to_focal_power_mode()
    left_lens.to_focal_power_mode()

    root = tk.Tk()
    root.title('Optotune Lens driver-ZVSL')
    root.geometry("600x400")
    root.resizable(width=True, height=True)
    root['background'] = '#FFFFFF'

    top_frame = tk.Frame(root).pack()

    def call_result(label_result, n1):
        num1 = float(n1.get())
        right_lens.set_diopter(num1)
        left_lens.set_diopter(num1)
        print(right_lens.get_diopter())
        print(left_lens.get_diopter())


    zeiss_logo = tk.PhotoImage(file="Zeiss-logo2.png")
    imgLabel = tk.Label(top_frame,bg='white',
                 image=zeiss_logo,
                 anchor=NE,
                 justify ="right").pack(ipadx = 0, ipady= 0)

    optotune_logo = tk.PhotoImage(file="opto1.png")
    imgLabel = tk.Label(top_frame,bg='white',
                 image=optotune_logo,
                 anchor= NE,
                 justify ="right").pack(ipadx = 0, ipady= 0)
    number1 = tk.StringVar()
    labelResult = tk.Label(root)
    call_result = partial(call_result, labelResult, number1)

    L1 = tk.Label(root,bg='white', text="Choose desired focal power (D)").pack(ipady= 4)

    FP = tk.Scale(root,from_=-2.00, to=3.00,bg='white', tickinterval=0.25, digits=3, sliderlength= 20,length= 300, resolution=0.25, command=set_D,orient=HORIZONTAL).pack()

    L2 = tk.Label(root,bg='white', text="Type desired focal power (D)").pack(ipady= 4)

    val_D = tk.Entry(root, textvariable=number1, bd=5).pack()

    B7 = tk.Button(root,text='Set',command=call_result).pack()

    def on_closing():
        right_lens.connection.close()
        left_lens.connection.close()
        if tk.messagebox.askokcancel("Quit", "Do you want to quit?"):
            root.destroy()


    root.protocol("WM_DELETE_WINDOW", on_closing)
    root.mainloop()

else:
    single_port = ports[0].name;
    print("Single lens detected")

    single_lens = Lens(single_port,
                       debug=False)  # set debug to True to see a serial communication log #for e.g. port=COM3

    diopter_initSingle = single_lens.get_diopter()  # read diopter value
    print('Initial Diopter value:', diopter_initSingle)  # print current diopter value

    single_lens.to_focal_power_mode()

    root1 = tk.Tk()
    root1.title('Optotune Lens driver-ZVSL')

    top_frame = tk.Frame(root1).pack()


    def call_result(label_result, n1):
        num1 = float(n1.get())
        single_lens.set_diopter(num1)
        print(single_lens.get_diopter());

    number1 = tk.StringVar()
    labelResult = tk.Label(root1)
    call_result = partial(call_result, labelResult, number1)

    L1 = tk.Label(root1, text="Enter desired focal power (D)").pack()

    val_D = tk.Entry(root1, textvariable=number1, bd=5).pack()

    B7 = tk.Button(root1,
                   text='Set',
                   command=call_result).pack()

    def on_closing():
        single_lens.connection.close()
        if tk.messagebox.askokcancel("Quit", "Do you want to quit?"):
            root1.destroy()

    root1.protocol("WM_DELETE_WINDOW", on_closing)
    root1.mainloop()
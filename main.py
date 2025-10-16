# -*- coding: utf-8 -*-
"""
Created on Tue Dec  1 09:19:38 2020

@author: Maxwell
"""

from lib import Lens
import serial.tools.list_ports
import time
import numpy
from functiondef import *

try:
    import tkinter as tk
except ImportError:
    import Tkinter as tk # Module name has changed from Tkinter in Python 2 to tkinter in Python 3
import tkinter.messagebox as tkMessageBox
from tkinter.messagebox import _show 
from tkinter import *
from PIL import ImageTk, Image
from functools import partial

ports = list(serial.tools.list_ports.comports())  

if len(ports)>1:
    port1=ports[0].name;
    port2=ports[1].name;
    print("2 lenses detected")
    lens1 = Lens(port1, debug=False)  # set debug to True to see a serial communication log #for e.g. port=COM3 
    lens2 = Lens(port2, debug=False)  # set debug to True to see a serial communication log #for e.g. port=COM3 
    lens_info(lens1)
    lens_info(lens2)
    
elif len(ports)==1:
    port1 = ports[0].name;
    print("1 lens detected")
    lens1 = Lens(port1, debug=False)  # set debug to True to see a serial communication log #for e.g. port=COM3 
    lens_info(lens1)
else:
    print("No lens detected")

import numpy as np
from labjack import ljm
import time
import venus_data_utils.venusplc as venusplc

venus = venusplc.VENUSController(read_only=True)

handle = ljm.openS("T8","usb","ANY")

#print(ljm.getHandleInfo(handle))

again = 1

while again:
    current = input('new current (q to quit): ')
    inow = venus.read(['batman_i'])
    try:
        current = float(current)
        if np.abs(inow-current)<2:
            ljm.eWriteName(handle,"DAC0",current*.04)
        else:
            isteps = np.linspace(inow,current,int(3*np.ceil(np.abs(inow-current))))
            print(f'   start: {inow:.2f} end: {current:.2f} steps:{len(isteps)}')
            for ireq in isteps:
                ljm.eWriteName(handle,"DAC0",ireq*.04)
                time.sleep(0.003)

    except:
        again = 0

ljm.close(handle)

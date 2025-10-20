# -*- coding: utf-8 -*-
"""
author: SBModre
"""
import numpy as np
import time
from labjack import ljm 
import matplotlib.pyplot as plt
from datetime import datetime
import json
import re
import telnetlib3 as telnetlib

class FatalError(Exception): #just to later raise a custom Error
    pass

class Variables:
    def __init__(self):
        """
        This initiates the Variable class.
        In here, most of the important Variables are stored.
        The variables, that are initially None, are supposed to be entered by the user.
        d, and L, are the Scanner's Plate's distance and Length.
        """
        self.xp_max = None #maximal x'; the smallest x' is going to be -maximal x'
        self.yp_max = None #maximal y'; the smallest y' is going to be -maximal y'
        self.Q = None #particle charge number
        self.M = None #particle mass number
        self.V_extr = None #Extraction Voltage
        self.xp_step = None #x' step size
        self.yp_step = None #y' step size
        self.x_step = None #x step size
        self.y_step = None #y step size
        self.x_max = None #biggest x; smallest x is going to be -biggest x
        self.y_max = None #biggest y; smallest y is going to be -biggest y
        self.x_min = None
        self.y_min = None
        self.xp_min = None
        self.yp_min = None
        self.d = 0.0189992 #Capacitor Plate distance [m] (0.748")
        self.L = 0.1199896 #Capacitor Length [m] (4.724")

    def get_V(self, momentum):
        """
        Parameters
        ----------
        momentum : Float, Int or Array
            particles' momenta x'/y'

        Returns
        -------
        V : Float, Int or Array
            Plate Voltage depending on momentum (for Emittance Scanner with delta1 = delta2)

        """
        V = 2*momentum*self.d*self.V_extr/self.L
        return V
    
    def write_and_save_file(self):
        """
        Saves the class Variables as a dictionary in a txt file named: Emittance_Scanner_Variables_yyyy-mm-dd.txt

        Returns
        -------
        file_name : str
            name of trhe file where the dictionary is stored

        """
        Date_Time = datetime.now().strftime("%Y-%m-%d %Hh%Mm%Ss")
        file_name = 'Emittance_Scanner_Variables_' + Date_Time + ".txt" #create a filename including the date and time, so that each new file that is written and saved has a unique name. Can be used to next time load variables.
        variables = {"Maximal x' [mrad]": self.xp_max, "Minimal x' [mrad]":self.xp_min, "Maximal y' [mrad]":self.yp_max, "Minimal y' [mrad]":self.yp_min, "Maximal x [mm]":self.x_max, "Minimal x [mm]":self.y_min, "Maximal y [mm]":self.y_max, "Minimal y [mm]":self.y_min,
                     "Charge Number Q": self.Q, "Mass Number M":self.M,"Extraction Voltage U [V]":self.V_extr, "x' Step Size [mrad]":self.xp_step,
                     "y' Step Size [mrad]":self.yp_step, "x Step Size [mm]":self.x_step, "y Step Size [mm]":self.y_step}
        with open(file_name, 'w') as f:
            f.write(json.dumps(variables))
        return file_name
            
    def open_and_read_file(self, file_name):
        """
        Opens a Variables file and uses the dictionary in the file to define the class Variables.

        Parameters
        ----------
        file_name : str
            File to be opened and read

        Raises
        ------
        ValueError
            if file_name does not have the proper pattern and format.
        

        Returns
        -------
        None.

        """
        pattern = r".*[/\\]Emittance_Scanner_Variables_\d{4}-\d{2}-\d{2} \d{2}h\d{2}m\d{2}s\.txt$"
        if re.match(pattern, file_name): #check if the file that we are trying to read has the correct file name
            with open(file_name) as f:
                data =f.read()
            variables = json.loads(data)
        else:
            raise ValueError("Wrong file format")
        try:
            self.xp_max = variables["Maximal x' [mrad]"]
            self.yp_max = variables["Maximal y' [mrad]"]
            self.Q = variables["Charge Number Q"]
            self.M = variables["Mass Number M"]
            self.V_extr = variables["Extraction Voltage U [V]"]
            self.xp_step = variables["x' Step Size [mrad]"]
            self.yp_step = variables["y' Step Size [mrad]"]
            self.x_step = variables["x Step Size [mm]"]
            self.y_step = variables["y Step Size [mm]"]
            self.x_max = variables["Maximal x [mm]"]
            self.y_max = variables["Maximal y [mm]"]
            self.x_min = variables["Minimal x [mm]"]
            self.y_min = variables["Minimal y [mm]"]
            self.xp_min = variables["Minimal x' [mm]"]
            self.yp_min = variables["Minimal y' [mm]"]
        except KeyError: #KeyError would only be raised if somehow a file got the correct filename pattern and format but variables are missing
            print('Wrong Key')
        
class Motor:
    def __init__(self, beam_line=None):
        """
        This initiates the Motor Class. In this class all methods that control the motors behaviour can be found
        
        After defining some variables, communication with the Drive Controller is opened
        """
        self.factor = 19685 #steps/unit (by default = steps/mm) (after gearbox)     
        self.beam_line = beam_line #0 (VENUS) or 1 (AECR)
        self.centered = [False, False, False, False] #list to confirm if centering has been done (i.e. if 0 position has been redefined)
        self.mid_point_offsets = [30.18, 36.50, 31.75, 31.75] #Midpoint Offsets, i.e. the difference between the In/positive Limit and true 0 position [mm]
        #midpoint offsets for VENUS from LabView program
        self.tn = telnetlib.Telnet("10.10.100.60", 5002, timeout=3) #opens connection to controller
        self.send_command("PROG0") #opens Program0 prompt. Because Master = 0 all commands have to be sent in Prog0
        self.send_command("ACC 5 DEC 5 VEL 15 STP 100") #sets Acceleration Ramp, Decceleration Ramp, Velocity and Stop Ramp
        self.Voltagecurrentfactor = 1e8 #V/A Scan cup - gain from Keithley 428
        self.axis_names = ["X", "Y", "Z", "A"]
        self.unit = None #while we cannot directly access information about the unit the controller is working in, it might be worth it to figure that out, and add the possibility for the user to change units
        self.frontshield_gain = 1e8
        #self.send_command('ATTACH SLAVE0 AXIS0 "X" : ATTACH SLAVE1 AXIS1 "Y" : ATTACH SLAVE2 AXIS2 "Z" : ATTACH SLAVE3 AXIS3 "A"', True)
    
#axis goes from 0-3. 0,1 are venus horizontal, vertical and 2,3 aecr horizontal, vertical respectively
    def check_FC(self):
        """
        This method checks if the beam current measuring Farady Cup is out or not

        Returns
        -------
        Out: boolean
            True if FC is out, False, if not.
        """
        #method to see if FC is out
        #placeholder
        Out = True
        return Out

    def check_unit(self, axis):
        """
        A way to check what Unit the controller is configurated in. This is probably unnecessary, since the units wouldn't change.
        

        Parameters
        ----------
        axis : Int in [0,1,2,3]
            Driving Axis

        Raises
        ------
        ValueError
            if unknown unit is encountered

        Returns
        -------
        str
            Unit

        """
        if not self.axis_clear(axis):
            self.move_out([1,0,3,2][axis])
            while self.send_command("?BIT(516)"): #"In Motion"-Bit
                continue
        position = self.send_command(f"?P(12288 + {axis} * 256)")
        self.relative_move(1, axis)
        while self.send_command("?BIT(516)"): #"In Motion"-Bit
            continue
        new_position = self.send_command(f"?P(12288 + {axis} * 256)")
        distance = new_position-position
        if distance == 1:
            self.factor = 1
            return "steps"
        elif distance == 19685:
            self.factor = 19685
            return "mm"
        elif distance == 500000: 
            self.factor = 500000
            return "inch"
        else:
            raise ValueError("Unknown Unit")
            
    def test_connection(self):
        """
        Checks if the connection is still open. If Somehow it isn't, it opens connection again and if it times out, a TimeoutError is raised

        Raises
        ------
        TimeoutError
            If opening connection takes longer than 3 seconds


        """
        if not self.tn:
            try:
                self.tn = telnetlib.Telnet("10.10.100.60", 5002, timeout=3)
            except:
                raise TimeoutError("Cannot open Communication")
        else:
            pass

    def move_to(self, position, axis): #positon in units (depends on what the acr is calibrated to); axis = 0,1,2,3
        """
        First checks if axis is clear to move, i.e. if other axis is at out limit. If not, other axis is moved to out Limit.
        Then sends command to Drive on axis
        
        Axis Drive has to be turned on because after Kill All Motion Request is set and cleared, Axis won't move until Drive is turned off and on again
        
        Then sends command to move axis to absolute position. E.g. if current position is -10, move_to(10, 3) moves axis 3 20mm in positive direction
        KeyboardInterrupt stops all motion immediately
        
        In the end drive is turned off.

        Parameters
        ----------
        position : float
            position in mm
        axis : Int
            in [0,1,2,3] (Venus x, Venus y, Aecr x, Aecr y)

        Returns
        -------
        None.

        """
        if not self.axis_clear(axis):
            self.move_to(200, [1,0,3,2][axis])  #make big enough move, so that motor will travel to positive EOT limit switch
            self.send_command(f"CLR BIT({8467 + axis * 32})") #clear kill all moves (hitting limit switch sets kill all moves request)
            self.send_command(f"DRIVE OFF {self.axis_names[axis]}")
            while self.send_command("?BIT(516)"): #"In Motion"-Bit for Master 0
                continue
            if not self.axis_clear(axis):
                self.send_command(f"DRIVE OFF {self.axis_names[axis]}")
                raise FatalError("Axis can not be cleared")
        if not self.check_FC():
            raise FatalError("Faraday Cup is not Out")
        
        self.send_command(f"DRIVE ON {self.axis_names[axis]}")
        self.send_command(f'{self.axis_names[axis]}{position}')
        try:
            while self.send_command("?BIT(516)"): #"In Motion"-Bit for Master 0
                continue
        except KeyboardInterrupt:
            self.send_command(f"SET BIT({8467 + axis * 32})")
            self.send_command(f"CLR BIT({8467 + axis * 32})")
            self.send_command(f"DRIVE OFF {self.axis_names[axis]}")
            raise KeyboardInterrupt()
        self.send_command(f"DRIVE OFF {self.axis_names[axis]}")
        
    def relative_move(self, position, axis):
        """
        Moves axis to position relative to current position. E.g. If current position is -10, relative_move(10, 3) moves axis 3 10mm in positive direction.
        
        Checks if axis is clear, if not moves out other axis.

        Parameters
        ----------
        position : float
            position in mm
        axis : int
            in [0,1,2,3]

        Raises
        ------
        FatalError
            custom error that is raised when seemingly other axis cannot be moved out.

        Returns
        -------
        None.
        """
        if not self.axis_clear(axis):
            self.move_to(200, [0,1,3,2][axis])  #make big enough move, so that motor will travel to positive EOT limit switch
            self.send_command(f"CLR BIT({8467 + axis * 32})") #clear kill all moves (hitting limit switch sets kill all moves request)
            self.send_command(f"DRIVE OFF {self.axis_names[axis]}")
            while self.send_command("?BIT(516)"): #"In Motion"-Bit for Master 0
                continue
            if not self.axis_clear(axis):
                self.send_command(f"DRIVE OFF {self.axis_names[axis]}")
                raise FatalError("Axis can not be cleared") 
      
        self.send_command(f"DRIVE ON {self.axis_names[axis]}")
        self.send_command(f'{self.axis_names[axis]}/{position}')
        try:
            while self.send_command("?BIT(516)"): #"In Motion"-Bit for Master 0
                continue
            self.send_command(f"DRIVE OFF {self.axis_names[axis]}")
        except KeyboardInterrupt:
            self.send_command(f"SET BIT({8467 + axis * 32})")
            self.send_command(f"CLR BIT({8467 + axis * 32})")
        self.send_command(f"DRIVE OFF {self.axis_names[axis]}")


    def send_command(self, command, Print=False):
        """
        Sends command to ACR74C Controller

        Parameters
        ----------
        command : str
            command to be sent to controller
        Print : Bool, Optional
            If True, the entire response of the controller is printed. The default is False.

        Returns
        -------
        output : float
            Returns controller response if it is a float, i.e. position, in motion bit, etc.
            Returns None otherwise

        """
        self.test_connection
        self.tn.write(command.encode('ascii') + b'\r') #writes encoded command to socket
        time.sleep(0.07) #need to await response from controller. If the delay here is too small we might not catch the enire response which will lead to errors in reading position or other relevant information
        response = self.tn.read_very_eager().decode('ascii').strip()
        if Print:
            print(f"Full Response:\n{response}")
        lines= response.splitlines()
        if lines:
            try:
                output = float(lines[-2]) #if float output, it is always in last line of response. However read_very_eager also reads next prompt line as response, so output is on second to last line
                return output
            except:
                return None

    def axis_clear(self, axis): 
        """
        Checks if the axis is clear, i.e. when input is axis 0, axis 1 should be in outside (clear) position and vice versa
                                            same for axis 2 and 3
        
        Parameters
        ----------
        axis : int
            in [0,1,2,3]
            
        Returns
        -------
        Boolean: True = axis clear
                 False = axis not clear          

        """
        if type(axis) is not int:
            try:
                axis = int(axis)
            except:
                raise TypeError("Axis has to be int or float!") #(0,1,2,3)
        other_axis = [1,0,3,2][axis] #if axis = 0, then other axis = 1, if axis = 2, other axis = 3 and vice versa
        bit = 16128 + other_axis * 32 #positive EOT Limit Current State
        return bool(self.send_command(f"?BIT({bit})")) 

    
    def move_out(self, axis):
        """
        Moving axis to positive EOT Limit

        Parameters
        ----------
        axis : int
            in [0,1,2,3]

        Returns
        -------
        None.

        """
        self.move_to(200, axis)  #make big enough move, so that motor will travel to positive EOT limit switch
        self.send_command(f"CLR BIT({8467 + axis * 32})") #clear kill all moves (hitting limit switch sets kill all moves request)
        self.send_command(f"DRIVE OFF {self.axis_names[axis]}")
     
        
    def centering(self, axis):
        """
        If axis is clear moves to positive EOT Limit. From there, moves back to Midpointoffset. 
        Resets Axis, so center position is 0.
        sets self.centered to True for this axis
        If this axis has been centered before, this moves the axis to 0

        Parameters
        ----------
        axis : int
            in [0,1,2,3]

        Raises
        ------
        FatalError
            if perpendicular axis cannot be cleared.

        Returns
        -------
        None.

        """
        if not self.axis_clear(axis):
            try:
                self.move_out([1,0,3,2][axis])
            except KeyboardInterrupt:
                return
            while self.send_command("?BIT(516)"): #"In Motion"-Bit for Master 0
                continue
            if not self.axis_clear(axis):
                self.send_command(f"DRIVE OFF {self.axis_names[axis]}")
                raise FatalError("Axis can not be cleared")
        if self.centered[axis]: #If the axis has already been centered before just move to 0.
            self.move_to(0, axis)
            return
    
        self.move_to(-200, axis)
        while self.send_command("?BIT(516)"): 
            try:
                continue
            except KeyboardInterrupt:
                return
        self.relative_move(self.mid_point_offsets[axis], axis)
        while self.send_command("?BIT(516)"): #"In Motion"-Bit
            try:
                continue
            except KeyboardInterrupt:
                return
        self.send_command(f"RES AXIS{axis}")
        self.send_command(f"DRIVE OFF {self.axis_names[axis]}")
        self.centered[axis] = True
        
        
class Read_and_Analyze:
    def __init__(self, Variables_instance, Motor_instance):
        """
        Initiates the analysing class. Initates a Variables and Motor instance.
        creates arrays for the positions x and y and the momenta x' and y'

        Parameters
        ----------
        Variables_instance : object
            instance of Variables() class
        Motor_instance : object
            instance of Motor() class

        Returns
        -------
        None.

        """
        self.Var = Variables_instance
        self.Mot = Motor_instance
        self.x = np.arange(self.Var.x_min, self.Var.x_max+self.Var.x_step, self.Var.x_step) #x-array
        self.y = np.arange(self.Var.y_min, self.Var.y_step + self.Var.y_max, self.Var.y_step) #y-array
        self.x_prime = np.arange(self.Var.xp_min,self.Var.xp_step + self.Var.xp_max, self.Var.xp_step) #x' array
        self.y_prime = np.arange(self.Var.yp_min, self.Var.yp_step + self.Var.yp_max, self.Var.yp_step) # y' array
        
        
    def get_current(self, axis):
        """
        Calculates the Voltage from the momentum array. Then iterates through each positions of the position array.
        At each position it iterates through different plate voltages and measures Scan Cup Voltage for each Plate Voltage.
        Scan Cup Voltage measurement is turned to current by dividing through scan cup gain
        
        Input
        -------
        axis: int
            in [0,1,2,3]
        
        Returns
        -------
        I: numpy.ndarray
            2-D Array of the current depending on position and momentum.
            columns = positions
            rows = momentum/Voltage
            
        file_name: str
            file where the data is saved
        
        """
       
        position = [self.x, self.y][axis%2] #mm
        momentum = [self.x_prime, self.y_prime][axis%2] #mrad
        V = self.Var.get_V(momentum*1e-3)/100 #this is output from labjack which is amplified bz a factor of 100
        m = len(V)
        n = len(position)
        I = np.zeros((m,n))
        handle = ljm.openS("T8","usb","ANY")
        output = "DAC1" #!!!
        Input = "AIN0" #!!!
        delay = 0.01 #need to figure out the delay
        for i in position:
            self.Mot.move_to(i, axis)
            I_ = np.array([])
            for j in V: 
                #two 1.5V batteries drop the Voltage. Labjack can only output from 0-10
                ljm.eWriteName(handle, output, j+3.188) #according to measurements from Powersupply Voltagedrop is approx. 3.188V
                time.sleep(delay) #!!!delay for some time so that signal can reach capacitor
                current = 0
                for k in range(2000): #take 2000 samples
                    current += ljm.eReadName(handle, Input)/self.Mot.Voltagecurrentfactor #actually reading voltage that depends on current
                    time.sleep(0.02) #LabView Program took 2000 samples at a sampling rate of 1000000S/s, so 0.02s in between samples
                current *= -1/2000 #minus because of inverting output on keithley 428
                current = (abs(I_) + I_)/2 #turns negative currents to 0 (non physical; noise)
                I_ = np.append(I, current) # append the everage current                   
            I[:,i] = I_ #columns = position, rows = Voltage
        ljm.close(handle)
        variables = {"Maximal x' [mrad]": self.Var.xp_max,"Minimal x' [mrad]":self.Var.xp_min, "Minimal y' [mrad]":self.Var.yp_min, "Maximal y' [mrad]":self.Var.yp_max, "Maximal x [mm]":self.Var.x_max, "Minimal x [mm]":self.Var.x_min, "Maximal y [mm]":self.Var.y_max, "Minimal y [mm]":self.Var.y_min,
                     "Charge Number Q": self.Var.Q, "Mass Number M":self.Var.M,"Extraction Voltage U [V]":self.Var.V_extr, "x' Step Size [mrad]":self.Var.xp_step,
                     "y' Step Size [mrad]":self.Var.yp_step, "x Step Size [mm]":self.Var.x_step, "y Step Size [mm]":self.Var.y_step}
        Date_Time = datetime.now().strftime("%Y-%m-%d %Hh%Mm%Ss")
        E, A, B, G = self.emittance(axis, I)
        file_name = "Emittance_Scanner_Data_"+ Date_Time + f" {['Venus_x_', 'Venus_y_', 'AECR_x_', 'AECR_y_'][axis]}" + ".txt"
        with open(file_name, 'w') as f: #save data in a text file
            f.write("Variables\n")
            f.write(json.dumps(variables))
            f.write("\nBeam Line:\n")
            f.write(f"{['VENUS', 'VENUS', 'AECR', 'AECR'][axis]}\n")
            f.write("Axis:\n") 
            f.write(f"{['X', 'Y', 'X', 'Y'][axis]}\n")
            f.write("Position Array:\n")
            json.dump(position.tolist(), f)
            f.write('\nMomentum Array: \n')
            json.dump(momentum.tolist(), f)
            f.write('\nVoltage Array: \n')
            json.dump(V.tolist(), f)
            f.write("\nCurrent Matrix: \n")
            json.dump(I.tolist(), f)
            f.write("\nRMS Emittance: \n")
            f.write(str(E))
            f.write("\nTwiss Parameter Alpha: \n")
            f.write(str(A))
            f.write("\nTwiss Parameter Beta: \n")
            f.write(str(B))
            f.write("\nTwiss Parameter Gamma: \n")
            f.write(str(G))
        return I, file_name
    
    def emittance(self, axis, I):
        """
        Calculates the RMS emittance. The Emittance is 4*the Root mean square emittance
        

        Parameters
        ----------
        axis : int
            in [0,1,2,3]
        I : numpy.ndarray
            2-D current matrix

        Returns
        -------
        E_rms : float
            rms emittance
        alpha : float
            Twiss Parameter Alpha
        beta : float
            Twiss Parameter Beta
        gamma : float
            Twiss Parameter gamma
        """
        position = [self.x*1e-3, self.y*1e-3][axis%2] #m
        momentum = [self.x_prime*1e-3, self.y_prime*1e-3][axis%2] #rad
        position_mean = sum(I@position)/np.sum(I) #sum(x_i*I_i)/sum(I_i)
        momentum_mean = sum(I.T@momentum)/np.sum(I) #sum(x'_i*I_i)/sum(I_i)
        sigma_position_squared = sum((I@(position-position_mean)**2))/np.sum(I) #sqrt(sum((x_i-<x>)^2*I_i)\sum()
        sigma_momentum_squared = sum((I.T@(momentum-momentum_mean)**2))/np.sum(I)
        sigma_position_sigma_momentum = (momentum-momentum_mean).T@I@(position-position_mean)/np.sum(I)
        E_rms = np.sqrt(sigma_position_squared*sigma_momentum_squared-(sigma_position_sigma_momentum)**2) #RMS Emittance. Actual Emittance is 4* RMS Emittance
        
        alpha = -sigma_position_sigma_momentum/E_rms
        beta = sigma_position_squared/E_rms
        gamma = sigma_momentum_squared/E_rms
        #E_rms in m rad
        return E_rms, alpha, beta, gamma
    
    def phase_space_plot(self, filename): 
        """
        Plots emittance scan data. plus an ellipses whose area is the emittance.
        
        Parameters
        ----------
        filename : str
            Filename of data to be plotted. 
        E_rms : float
            Root mean square Emittance
        A : float
            Twiss Parameter Alpha
        B : float
            Twiss Parameters Alpha

        Returns
        -------
        None.

        """
        data = []
        with open(filename) as f:
            for i, line in enumerate(f):
                if i >= 2 and i%2 == 1:
                    try:
                        data.append(json.loads(line))
                    except:
                        data.append(line.strip())
                    
        beam_line = data[0]
        axis = data[1]
        position = np.array(data[2]) #unit to mm
        momentum = np.array(data[3]) #unit to mrad
        I = np.array(data[5])*1e9 # unit nA
        theta = np.linspace(0, 2*np.pi, 100)
        E_rms = float(data[6])*1e6 #convert to mm mrad
        A = float(data[7])
        B = float(data[8])
        x_e = np.sqrt(4*E_rms*B)*np.cos(theta)
        x_prime_e = -np.sqrt(4*E_rms/B)*(A*np.cos(theta)+np.sin(theta)) #parametrisizing the ellipse (Epsilon = 4*Epsilon_rms)  
        img_filename = filename.strip("txt") + "jpeg" #create valid format for picture with same name as the data
        m,n = I.shape
        binlength_position = (max(position)-min(position))/n
        binlength_momentum = (max(momentum)-min(momentum))/m
        plt.imshow(I,cmap="inferno", origin="lower", extent=(min(position)-binlength_position/2, max(position)+binlength_position/2, min(momentum)-binlength_momentum/2, max(momentum)+binlength_momentum/2))
        plt.plot(x_e, x_prime_e,'r--', label ="$\epsilon_{rms}$ = "+f"{round(E_rms,4)} [mm mrad]")
        plt.colorbar(label = "Current [nA]")
        plt.xlabel(f"Position {axis} [mm]")
        plt.ylabel(f"Momentum {axis}' [mrad]")
        plt.title(f"{beam_line} {axis}-Axis Emittance Scan")
        #plt.legend()
        plt.savefig(img_filename) #saving plot
        #plt.close()


def main():
    """
    Combines all methods to one interactive Main function.
    First, the user is asked to enter or load Variables like x_max, y_max, extraction Voltage, etc.
    Then the Motor is initialised.
    And the User is asked to either load Emittance Scan data to create a plot, or start a new scan.
    If a new scan is made, the user is asked for which Beam Line to drive on, how many scans to do on each axis and what the Scan Cup Gain is. 
    Then the program runs a number of x scans followed by a number of y scans.
    
    The variables are saved (if the user wants them to) in a file named 'Emittance_Scanner_Variables_YYYY-MM-DD HHhMMmSSs.txt'
    The data and plots are saved in the files "Emittance_Scanner_Data_YYYY-MM-DD HHhMMmSSs {Beam Line}_{axis}_.txt", "Emittance_Scanner_Data_YYYY-MM-DD HHhMMmSSs {Beam Line}_{axis}_.png" respectively 

    """
    V = Variables() #initiate variables class
    variables_dict = np.array([
        ["Extraction Voltage U [V]", "V_extr", V.V_extr],
        ["Maximal x' [mrad]", "xp_max", V.xp_max],
        ["x' Step Size [mrad]", "xp_step", V.xp_step],
        ["Minimal x' [mm]", "xp_min", V.xp_min],
        ["Maximal y' [mrad]", "yp_max", V.yp_max], 
        ["y' Step Size [mrad]", "yp_step", V.yp_step],
        ["Minimal y' [mm]", "yp_min", V.yp_min],
        ["Maximal x [mm]", "x_max", V.x_max],
        ["x Step Size [mm]", "x_step", V.x_step],
        ["Minimal x [mm]", "x_min", V.x_min],        
        ["Maximal y [mm]", "y_max", V.y_max],
        ["y Step Size [mm]", "y_step", V.y_step],
        ["Minimal y [mm]", "y_min", V.y_min],        
        ["Charge Number Q", "Q", V.Q], 
        ["Mass Number M", "M", V.M]
    ])
    file_bool = bool(int(input("To load existing variables from a file enter 1. To set new variables enter 0: ")))
    if file_bool:
        while True:
            Varfile = str(input("Enter file name (i.e. 'Emittance_Scanner_Variables_mm-dd-yyyy HHhMMmSSs.txt'): "))
            try:
                V.open_and_read_file(Varfile)
            except ValueError:
                print("This looks like the wrong file. Check if the file has the format 'Emittance_Scanner_Variables_mm-dd-yyyy HHhMMmSSs.txt'")
                print("Your file is: ", Varfile)
                continue
            break
    else:
        for i, (var_label, var_name, value) in enumerate(variables_dict):
            if var_name in ["Q", "M"]:
                while True:
                    try: 
                        setattr(V, var_name, int(input("Enter " + var_label + ": ")))
                        break
                    except ValueError:
                        print(var_label + ' must be an integer')
            elif var_name in ["xp_max", "yp_max"]:
                while True:
                    try:
                        value = float(input("Enter " + var_label + ": "))
                        break
                    except ValueError:
                        print(var_label + " must be a float!")
                        continue
                if V.get_V(value*1e-3) > 200:
                    value = round(200/V.d/V.V_extr*V.L/2*1e3,3) #if momentum too big, set to maximum
                    print(var_label + " is too big. The Maximum is set to " + str(value))
                setattr(V, var_name, max(0,value)) #set variable, but can't be negative --> max(0,value)
            elif var_name in ["xp_step", "yp_step", "x_step", "y_step"]:
                while True:
                    try:
                        value = abs(float(input("Enter " + var_label + ": ")))
                        if value > 2*getattr(V, variables_dict[np.where(variables_dict == var_name)[0].item()-1][1]):
                            print("Step size is too big!")
                            continue
                        break
                    except ValueError:
                        print(var_label + " must be a float!")
                        continue
                    setattr(V, var_name, value)
            elif var_name in ["x_min", "y_min", "xp_min", "yp_min"]:
                while True:
                    value = input("Enter " + var_label + " (Entering Nothing sets the minimum to -maximum): " )
                    if value == '':
                        setattr(V, var_name, -getattr(V, variables_dict[np.where(variables_dict == var_name)[0]-2, [1]].item()))
                        break
                    else:
                        try:
                            value = float(value)
                            if var_name in ["xp_min", "yp_min"] and V.get_V(value*1e-3) < -200:
                                value = round(-200/V.d/V.V_extr*V.L/2*1e3,3)
                                print(var_label + "is too small. The Minimum is set to " + str(value))
                                setattr(V, var_name, value)
                            else:
                                value = min(0, value) #x_min, y_min, xp_min, yp_min is negative --> min(0,value)
                                setattr(V, var_name, value)
                            break
                        except ValueError:
                            print(var_label + " must be a float!")
                            continue
            else:
                while True:
                    try:
                        setattr(V, var_name, float(input("Enter " + var_label + ": ")))
                        break
                    except ValueError:
                        print("Must be an float")
                        continue
        while True:
            try:
                save = np.where(np.array(["no", "yes"])==input("Do you want to save those variables? (yes or no): "))[0].item()
                if save:
                    V.write_and_save_file()
                else:
                    pass
                break
            except:
                continue
    M = Motor()
    while True: 
        try: 
            plot_data = np.where(np.array(["no", "yes"])==input("Do you want to load and plot existing Measuremnts? (yes or no): "))[0].item()
            break
        except:
            print("Undefined Input. Try Again")
    if plot_data:
        while True:
            data_file = input("Enter the file name (i.e. Emittance_Scanner_Data_{beam_line}_{axis}_mm-dd-yyyy HHhMMmSSs.txt : ")
            try:
                data = []
                with open(data_file) as f:
                    for i, line in enumerate(f):
                        if i%2 == 1:
                            try:
                                data.append(json.loads(line))
                            except:
                                data.append(line.strip())
                dic = data[0]
                for row, (var_label, var_name, var_value) in enumerate(variables_dict):
                    setattr(V, var_name, dic[var_label])
                axis = data[2]
                beam_line= data[1]
                I = np.array(data[6])
                RnA = Read_and_Analyze(V, M)
                beam_line = np.where(np.array(["VENUS", "AECR"])==beam_line)[0].item()
                axis = np.where(np.array(["X", "Y", "X", "Y"])==axis)[0][beam_line].item()
                RnA.phase_space_plot(data_file)
                return
            except:
                while True:
                    try:
                        again = np.where(np.array(["no", "yes"]) == input("Uncompatible file! Do you want to enter a new file? (yes or no) (if 'no', the program is closed)"))[0].item()
                        break 
                    except:
                        print("Invalid Input.")
                        continue
                if again:
                    continue
                else:
                    return
    while True:
        try: 
            M.beam_line = np.where(np.array(["VENUS", "AECR"])==input("Enter the Beam Line (VENUS or AECR): "))[0].item()
            V.x_min = max(-M.mid_point_offsets[[0,2][M.beam_line]], V.x_min)
            V.y_min = max(-M.mid_point_offsets[[1,3][M.beam_line]], V.y_min)
            V.x_max = max(50, V.x_max)
            V.y_min = max(50, V.y_max)
            break
        except:
            print("Unknown beam line. Try Again")
    while True:
        try:
            x_scans = int(input("Enter the Number of Scans on the x-Axis: "))
            break
        except:
            continue
    while True:
        try:
            y_scans = int(input("Enter the Number of Scans on the y-Axis: "))
            break
        except:
            continue
    while True:
        try:
            M.Voltagecurrentfactor = float(input("Enter the Current to Voltage Gain factor [1e3, 1e4, ..., 1e11] [V/A]: "))
            if M.Voltagecurrentfactor not in [1e3, 1e4, 1e5, 1e6, 1e7, 1e8, 1e9, 1e10, 1e11]:
                M.Voltagecurrentfactor = 1e8
                print("Must be in [1e3, 1e4, ... , 1e11]!")
                continue
            break
        except ValueError:
            print("Must be a float!")
            continue
    RnA = Read_and_Analyze(V, M)
    input("When ready to start x-Axis Scans, hit Enter")
    axis = [0,2][M.beam_line]
    M.centering(axis)
    for i in range(x_scans):
        I, filename = RnA.get_current(axis)
        RnA.phase_space_plot(filename)
    M.move_out(axis)
    input("When ready to start y-Axis Scans, hit Enter")
    axis = [1,3][M.beam_line]
    M.centering(axis)
    for i in range(y_scans):
        I, filename = RnA.get_current(axis)
        RnA.phase_space_plot(filename)
    M.move_out(axis)
    M.tn.close()
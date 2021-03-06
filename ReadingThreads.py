# %%
# python packages
import serial
import RPi.GPIO as GPIO
import numpy as np
import time
from datetime import datetime
import threading
import re

# custome modules
import Modbus
import config

print('Import: succeed')

#-----------------Serial port setting------------------------------
# Set the USB devices to have a default name
RS485_port_path = '/dev/ttyUSB_RS485'
RS232_port_path = '/dev/ttyUSB_RS232'
Scale_port_path = '/dev/ttyUSB_Scale'
Server_port_path = '/dev/ttyUSB_PC'
lst_port = []

## device ID
ADAM_TC_id = '03'
GA_id = '11'
MFC_id = 'a'
Rpi_id = '06'

#-----------------Serial port instances------------------------------
## RS485
### set the baudrate of ADAM to 19200
RS485_port = serial.Serial(
    port=RS485_port_path,
    baudrate=19200, 
    bytesize=8, 
    stopbits=1, 
    parity='N'
    )
lst_port.append(RS485_port)
ADAM_TC_RTU = Modbus.RTU(ADAM_TC_id, '03', '0000', '0008')
ADAM_TC_slave = Modbus.Slave(ADAM_TC_id, ADAM_TC_RTU.rtu)

## RS232
### set the baudrate of GA & MFC to 9600
RS232_port = serial.Serial(
    port=RS232_port_path,
    baudrate=9600, 
    bytesize=8, 
    stopbits=1, 
    parity='N'
    )
lst_port.append(RS232_port)
GA_RTU = '11 01 60 8E'
GA_slave = Modbus.Slave(GA_id, GA_RTU)

MFC_RTU = MFC_id + '\r'
MFC_slave = Modbus.Slave(MFC_id, MFC_RTU)

# Scale USB
Scale_port = serial.Serial(
    port=Scale_port_path,
    baudrate=9600, 
    bytesize=8, 
    stopbits=1, 
    parity='N'
    )
lst_port.append(Scale_port)
Scale_slave = Modbus.Slave()

#-----GPIO port setting----------------------------------------------------------------
## DFM
# read High as 3.3V
channel_DFM = 18
GPIO.setmode(GPIO.BCM)
DFM_slave = Modbus.Slave()

BUTTON_PIN = 24

#-----RPi Server port setting----------------------------------------------------------------
RPi_Server_port = serial.Serial(
    port=Server_port_path,
    baudrate=115200, 
    bytesize=8, 
    stopbits=1, 
    parity='N'
    )
lst_port.append(RPi_Server_port)
RPi_Server_RTU = Modbus.RTU(Rpi_id, '03', '0000', '0017') # RTU: '06 03 0000 0017 042F'
RPi_Server = Modbus.Slave(Rpi_id, RPi_Server_RTU.rtu)

# initiate the server data sites
RPi_Server.readings = [0] * 17 # 17 data entries

# RPi run as a PyModbus slave 
# server_DB = Modbus.serverDB_gen(slave_id=0x06)

print('Port setting: succeed')

#-------------------------define Threads and Events-----------------------------------------
timeit = datetime.now().strftime('%Y_%m_%d_%H_%M')
print(f'Execution time is {timeit}')
print('=='*30)
start = time.time()

lst_thread = []
## RS485
Adam_data_collect = threading.Thread(
    target=Modbus.Adam_data_collect, 
    args=(start, RS485_port, ADAM_TC_slave, 21,),
    )
Adam_data_analyze = threading.Thread(
    target=Modbus.Adam_data_analyze, 
    args=(start, ADAM_TC_slave, RPi_Server,),
    )
lst_thread.append(Adam_data_collect)
lst_thread.append(Adam_data_analyze)

## RS232
def RS232_data_collect(port):
    count_err = [0,0] # [collect_err, set_err]
    while not config.kb_event.isSet():
        count_err = Modbus.GA_data_comm(start, port, GA_slave, 31, count_err)
        #Modbus.MFC_data_comm(start, port, MFC_slave, 49)
    port.close()
    print('kill GA_data_comm')
    print(f'Final GA_data_comm: {count_err} errors occured')
    #print('kill MFC_data_comm')
    #Modbus.barrier_kill.wait()

RS232_data_collect = threading.Thread(
    target=RS232_data_collect, 
    args=(RS232_port,)
    )
GA_data_analyze = threading.Thread(
    target=Modbus.GA_data_analyze, 
    args=(start, GA_slave, RPi_Server,),
    )
'''
MFC_data_analyze = threading.Thread(
    target=Modbus.MFC_data_analyze, 
    args=(start, MFC_slave, RPi_Server,),
    )
'''
lst_thread.append(RS232_data_collect)
lst_thread.append(GA_data_analyze)
#lst_thread.append(MFC_data_analyze)

## Scale USB
Scale_data_collect = threading.Thread(
    target=Modbus.Scale_data_collect, 
    args=(start, Scale_port, Scale_slave, 0,),
    )
Scale_data_analyze = threading.Thread(
    target=Modbus.Scale_data_analyze, 
    args=(start, Scale_slave, RPi_Server,),
    )
lst_thread.append(Scale_data_collect)
lst_thread.append(Scale_data_analyze)

## GPIO
# Edge detection
def DFM_data_collect(channel_DFM):
    DFM_slave.time_readings.append(time.time())
DFM_data_analyze = threading.Thread(
    target=Modbus.DFM_data_analyze, 
    args=(start, DFM_slave, RPi_Server,),
    )
lst_thread.append(DFM_data_analyze)


# RPi run as a server 
RPi_Server_process = threading.Thread(
    target=Modbus.RPiserver, 
    args=(start, RPi_Server_port, RPi_Server, 8,),
    )
lst_thread.append(RPi_Server_process)

'''
# RPi run as a PyModbus slave 
server_thread = threading.Thread(
    target=Modbus.run_server, 
    args=(server_DB, Server_port_path, 1, 115200, 1, 8, 'N')
    )
lst_thread.append(server_thread)
'''
#-------------------------Open ports--------------------------------------
try:
    for port in lst_port: 
        if not port.is_open:
            port.open() # code here........
        port.reset_input_buffer() #flush input buffer
        port.reset_output_buffer() #flush output buffer
    print('serial ports open')
    
    GPIO.setup(BUTTON_PIN, GPIO.IN, pull_up_down=GPIO.PUD_UP)
    GPIO.setup(channel_DFM, GPIO.IN, pull_up_down=GPIO.PUD_DOWN)
    print('GPIO ports open')
    
except Exception as ex:
    print ("open serial port error: " + str(ex))
    for port in lst_port: 
        port.close()
    exit() 

#-------------------------Sub Threadingggg-----------------------------------------
for subthread in lst_thread:
    subthread.start()

GPIO.add_event_detect(channel_DFM, GPIO.RISING, callback=DFM_data_collect)

#-------------------------Main Threadingggg-----------------------------------------
try:
    while not config.kb_event.isSet():
        if not config.ticker.wait(config.sample_time):
        #Modbus.barrier_analyze.wait()
            print("=="*10 + f'Elapsed time: {round((time.time()-start),2)}' + "=="*10)
        #Modbus.barrier_cast.wait()
            #print("=="*10 + f'Casting done. Elapsed time: {time.time()-start}' + "=="*10)
        
except KeyboardInterrupt: 
    print(f"Keyboard Interrupt in main thread!")
    print("=="*30)
except Exception as ex:
    print ("Main threading error: " + str(ex))    
    print("=="*30)
finally:
    #Modbus.barrier_kill.wait()
    print("=="*30)
    GPIO.cleanup()
    print(f"Program duration: {time.time() - start}")
    print('kill main thread')
    exit()
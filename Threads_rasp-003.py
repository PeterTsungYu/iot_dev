# %%
# python packages
import RPi.GPIO as GPIO
import numpy as np
import time
from datetime import datetime
import threading
import re

# custome modules
import Modbus
import config
import MQTT_config
import Mariadb_config

print('Import: succeed')


#-----port and slave setting----------------------------------------------------------------
lst_port = []
lst_port.append(config.RS485_port)
lst_port.append(config.Scale_port)
lst_port.append(config.ADAM_port)

# TCHeader Rreading, RTU func code 03, PV value site at '008A', data_len is 1 ('0001')
TCHeader_0_RTU_R = Modbus.RTU(config.TCHeader_0_id, '03', '008A', '0001')
TCHeader_0_slave = Modbus.Slave(config.TCHeader_0_id, TCHeader_0_RTU_R.rtu,)

TCHeader_1_RTU_R = Modbus.RTU(config.TCHeader_1_id, '03', '008A', '0001')
TCHeader_1_slave = Modbus.Slave(config.TCHeader_1_id, TCHeader_1_RTU_R.rtu,)

# Scale slave
Scale_slave = Modbus.Slave()

# ADAM_4024_slave, RTU func code 03, channel site at '0000-0003', data_len is 1 ('0001')
## ch00:+-10V, ch01:4-20mA, ch02:0-20mA, ch03:0-20mA
ADAM_4024_RTU_R = Modbus.RTU(config.ADAM_4024_id, '03', '0000', '0001') # ch0
ADAM_4024_slave = Modbus.Slave(config.ADAM_4024_id, ADAM_4024_RTU_R.rtu,)

#print(TCHeader_1_slave.rtu)
print('Port setting: succeed')

#-------------------------define Threads and Events-----------------------------------------
timeit = datetime.now().strftime('%Y_%m_%d_%H_%M')
print(f'Execution time is {timeit}')
print('=='*30)
start = time.time()


TCHeader_0_count_err = [0,0] # [collect_err, set_err] #todo: make it global and in a class
TCHeader_1_count_err = [0,0] # [collect_err, set_err]
## RS485
def RS485_data_collect(port):
    global TCHeader_0_count_err, TCHeader_1_count_err
    while not config.kb_event.isSet():
        TCHeader_0_count_err = Modbus.TCHeader_comm(
            start, port, TCHeader_0_slave, 7, TCHeader_0_count_err, 
            MQTT_config.sub_Topics['TCHeader/SV0']['event'], #todo: config a general slave class
            MQTT_config.sub_Topics['TCHeader/SV0']['value'], 
            ) # wait for 7 bytes
        #print(TCHeader_0_count_err)
        TCHeader_1_count_err = Modbus.TCHeader_comm(
            start, port, TCHeader_1_slave, 7, TCHeader_1_count_err, 
            MQTT_config.sub_Topics['TCHeader/SV1']['event'], #todo: config a general slave class
            MQTT_config.sub_Topics['TCHeader/SV1']['value'],
            ) # wait for 7 bytes
        #print(TCHeader_1_count_err)
    port.close()
    print('kill TCHeader_comm')
    print(f'Final TCHeader_comm: {TCHeader_0_count_err} and {TCHeader_1_count_err} errors occured')
    #print('kill MFC_data_collect')
    #Modbus.barrier_kill.wait()

# RS485
RS485_data_collect = threading.Thread(
    target=RS485_data_collect, 
    args=(config.RS485_port,)
    )
TCHeader_0_analyze = threading.Thread(
    target=Modbus.TCHeader_analyze, 
    args=(start, TCHeader_0_slave, 'TCHeader/PV0',),
    )
TCHeader_1_analyze = threading.Thread(
    target=Modbus.TCHeader_analyze, 
    args=(start, TCHeader_1_slave, 'TCHeader/PV1',),
    )

# Scale
Scale_data_collect = threading.Thread(
    target=Modbus.Scale_data_collect, 
    args=(start, config.Scale_port, Scale_slave, 0,),
    )
Scale_data_analyze = threading.Thread(
    target=Modbus.Scale_data_analyze, 
    args=(start, Scale_slave, 'Scale',),
    )

# ADAM
ADAM_4024_count_err = [0,0] # [collect_err, set_err] #todo: make it global and in a class
def ADAM_data_collect(port):
    global ADAM_4024_count_err
    while not config.kb_event.isSet():
        ADAM_4024_count_err = Modbus.ADAM_4024_comm(
            start, port, ADAM_4024_slave, 7, ADAM_4024_count_err, 
            MQTT_config.sub_Topics['ADAM_4024/SV0']['event'], #todo: config a general slave class
            MQTT_config.sub_Topics['ADAM_4024/SV0']['value'], 
            ) # wait for 7 bytes == 7 Hex numbers
    port.close()
    print('kill ADAM_4024_comm')
    print(f'Final ADAM_4024_comm: {ADAM_4024_count_err} errors occured')
    
# RS485
ADAM_data_collect = threading.Thread(
    target=ADAM_data_collect, 
    args=(config.ADAM_port,)
    )
ADAM_4024_analyze = threading.Thread(
    target=Modbus.ADAM_4024_analyze, 
    args=(start, ADAM_4024_slave, 'ADAM_4024/PV0',),
    )


lst_thread = []
lst_thread.append(RS485_data_collect)
lst_thread.append(TCHeader_0_analyze)
lst_thread.append(TCHeader_1_analyze)
lst_thread.append(Scale_data_collect)
lst_thread.append(Scale_data_analyze)
lst_thread.append(ADAM_data_collect)
lst_thread.append(ADAM_4024_analyze)

#-------------------------Open ports--------------------------------------
try:
    for port in lst_port: 
        if not port.is_open:
            port.open() # code here........
        port.reset_input_buffer() #flush input buffer
        port.reset_output_buffer() #flush output buffer
    print('serial ports open')
    
    #GPIO.setup(BUTTON_PIN, GPIO.IN, pull_up_down=GPIO.PUD_UP)
    #GPIO.setup(channel_DFM, GPIO.IN, pull_up_down=GPIO.PUD_DOWN)
    #print('GPIO ports open')
    
except Exception as ex:
    print ("open serial port error: " + str(ex))
    for port in lst_port: 
        port.close()
    exit() 

#-------------------------Sub Threadingggg-----------------------------------------
for subthread in lst_thread:
    subthread.start()

#GPIO.add_event_detect(channel_DFM, GPIO.RISING, callback=DFM_data_collect)

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
    #GPIO.cleanup()
    print(f"Program duration: {time.time() - start}")
    Mariadb_config.conn.close()
    print("close connection to MariaDB")
    MQTT_config.client_0.loop_stop()
    MQTT_config.client_0.disconnect()
    print("close connection to MQTT broker")
    print('kill main thread')
    exit()


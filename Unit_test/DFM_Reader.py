# %% 
import numpy as np
import RPi.GPIO as GPIO
import time
import threading

print('Import Succeed')

# %% 
pulse_times_min = []
pulse_times = []

# %%
# def func for reading 
def read(channel_DGM):
    # while a >=1.6V(3.3/2) input to the pin, it will detect as 1
    #print('read in')
    global pulse_times
    pulse_times.append(time.time())    


def flag_min():
    global pulse_times
    global pulse_times_min
    #print(pulse_times)
    pulse_times_min.append(pulse_times)
    pulse_times = []

# %%
# def func for data analysis
def calc_average_flow_rate(pulse_times_min):

    # initiate an empty list for storing average min flow rate by each interval 
    average_min_lst = []

    # calc average min flow rate by each interval 
    for pulse in pulse_times_min: # [[1st min pulse_times], [2nd min pulse_times], [3rd min pulse_times], ...]
        average_interval_lst = []

        for interval in range(30, 55, 5): # [[1st min intervals], [2nd min intervals], [3rd min intervals], ...]
            #print(interval)
            flow_rate_interval_lst = [] 

            # for each interval, calculate the average flow rate
            for i in range(interval, len(pulse), interval):
                try:
                    # flow rate in [liter/s]
                    # 0.1 liter / pulse
                    flow_rate = 60 * 0.1 * (interval-1) / (pulse[i-1] - pulse[i-interval])
                    flow_rate_interval_lst.append(round(flow_rate, 2)) 
                except Exception as ex:
                    print("Error: " + str(ex))

            average_flow_rate_interval = round(sum(flow_rate_interval_lst) / len(flow_rate_interval_lst), 2)
            average_interval_lst.append(average_flow_rate_interval)
        average_min_lst.append(average_interval_lst)

    print(average_min_lst)
    result = np.round(np.mean(np.array(average_min_lst), axis=1), 1)
    np.savetxt('result.csv', result, delimiter=',')
    print(result)

# %%
def main():
    try:
        WAIT_TIME_SECONDS = 60 # per min
        ticker = threading.Event()
        #count = 0

        # read High as 3.3V
        channel_DGM = 18
        GPIO.setmode(GPIO.BCM)
        # make sure it is not a float port
        GPIO.setup(channel_DGM, GPIO.IN, pull_up_down=GPIO.PUD_DOWN)
        # Edge detection
        GPIO.add_event_detect(channel_DGM, GPIO.RISING, callback=read)
        print('Port setup')

        input("Press Enter when ready\n>")
        print("Start now...")  
        start = time.time()
        flag_time = start

        while not ticker.wait(WAIT_TIME_SECONDS):    
            flag_min()
            print(f"Flag time is {time.time() - flag_time}")
            flag_time = time.time()
            
            '''count += 1
            if count == 5: # record for mins
                break
            '''
    except KeyboardInterrupt:  
        print(f"Program duration: {time.time() - start}")
        print(f"Keyboard Interrupt...")
        print("=="*30)
    except Exception as ex:
        print ("communicating error " + str(ex))    
        print("=="*30)
    finally:
        print("Clean up ports...")  
        GPIO.cleanup()
        print("=="*30)
        print("Data Analysis...")
        calc_average_flow_rate(pulse_times_min=pulse_times_min)  

# %%
if __name__ == "__main__":
    main()

import matplotlib.pyplot as plt
import pandas as pd

# "Time[ms],BATT[V],5V[V],RADIO[V],PT1[psi],PT2[psi],PT3[psi],PT4[psi],PT5[psi],PT6[psi],LC[lbf],C1,C2,FILL,VENT,MOV,ARM,PY1,PY2"


# Read the CSV file into a DataFrame

#df = pd.read_csv(fd.askopenfilename())
df1 = pd.read_csv('C:/Users/timdrake/OneDrive/Pitot Rocket/SD Card Hot Fire/data10.csv')
df2 = pd.read_csv('E:\data_attempt2.csv')
df3 = pd.read_csv('E:\data_attempt3.csv')
#df = pd.read_csv('E:\data3.csv')
df1["Time[ms]"] = round(df1['Time[ms]'].multiply(0.001),1)
#df['Time[ms]'] = pd.to_datetime(df['Time[ms]'], format = '%Y-%m-%d %H:%M')

def getFillindex(df):
    i=0
    fbool = 0       
    for f in df['FILL']:
        i=i+1
        if f == 1 and fbool == 0:
            return i

i=0
abool = 0
bbool = 0
for a in df1['ARM']:
    i=i+1
    if a == 1 and abool == 0:
        armBegin_index = i
        abool = 1
    
    if a == 0 and abool == 1 and bbool == 0:
        armEnd_index = i-1
        bbool = 1
 


print(getFillindex(df1))
print(getFillindex(df2))
print(getFillindex(df3))
    
#print(df['Time[ms]'][armBegin_index])
#print(df['Time[ms]'][armEnd_index])

# Voltage Plot
"""
fig, voltages = plt.subplots(figsize = (20,5)) #figsize = (40,10)
voltages.plot(df1['Time[ms]'], df1['BATT[V]'], label = 'Battery')
voltages.plot(df1['Time[ms]'], df1['5V[V]'], label = '5V')
voltages.plot(df1['Time[ms]'], df1['RADIO[V]'], label = 'Radio')

voltages.legend()
voltages.set_xlabel('Time [sec]')
voltages.set_ylabel('Volts [V]')
voltages.set_title('Voltage')
voltages.grid()

#plt.axvline(df['Time[ms]'][armBegin_index], color='0.8', label = 'ARM')
#plt.axvline(df['Time[ms]'][armEnd_index], color='0.8', label = 'ARM')
"""

                                                           

# Pressure Transducer Plot
fig, pressures = plt.subplots(figsize = (20,5)) #figsize = (40,10)

# Attempt 1 data
pressures.plot(df1['Time[ms]'], df1['PT1[psi]'], label = 'PHIL1')
pressures.plot(df1['Time[ms]'], df1['PT4[psi]'], label = 'TANK1')

# Attempt 2 data
#pressures.plot(df2['Time[ms]'], df2['PT1[psi]'], label = 'PHIL2')
#pressures.plot(df2['Time[ms]'], df2['PT4[psi]'], label = 'TANK2')
#
## Attempt 3 data
#pressures.plot(df3['Time[ms]'], df3['PT2[psi]'], label = 'PHIL3')
#pressures.plot(df3['Time[ms]'], df3['PT4[psi]'], label = 'TANK3')

pressures.legend()
pressures.set_xlabel('Time [sec]')
pressures.set_ylabel('PSI')
pressures.set_title('Pressure')
pressures.grid()

#plt.axvline(df['Time[ms]'][armBegin_index], color='0.8', label = 'ARM')
#plt.axvline(df['Time[ms]'][armEnd_index], color='0.8', label = 'ARM')

"""
# Load Cell Plot
fig, load_cell = plt.subplots(figsize = (20,5)) #figsize = (40,10)
load_cell.plot(df['Time[ms]'], df['LC[lbf]'], label = 'Load Cell')

load_cell.legend()
load_cell.set_xlabel('Time [sec]')
load_cell.set_ylabel('Thrust [lbf]')
load_cell.set_title('Load Cell')
load_cell.grid()

#plt.axvline(df['Time[ms]'][armBegin_index], color='0.8', label = 'ARM')
#plt.axvline(df['Time[ms]'][armEnd_index], color='0.8', label = 'ARM')

#plt.xlim(df['Time[ms]'][armBegin_index], df['Time[ms]'][armEnd_index])
"""



# Discretes Plot
fig, discretes = plt.subplots(figsize = (20,5)) #figsize = (40,10)
discretes.plot(df1['Time[ms]'], df1['C1'] + 14, label = 'C1')
discretes.plot(df1['Time[ms]'], df1['C2'] + 12, label = 'C2')
discretes.plot(df1['Time[ms]'], df1['FILL'] + 10, label = 'FILL')
discretes.plot(df1['Time[ms]'], df1['VENT'] + 8, label = 'VENT')
discretes.plot(df1['Time[ms]'], df1['MOV'] + 6, label = 'MOV')
discretes.plot(df1['Time[ms]'], df1['ARM'] + 4, label = 'ARM')
discretes.plot(df1['Time[ms]'], df1['PY1'] + 2, label = 'PY1')
discretes.plot(df1['Time[ms]'], df1['PY2'] + 0, label = 'PY2')

discretes.legend()
discretes.set_xlabel('Time [sec]')
#discretes.set_ylabel('Discretes')
discretes.set_title('Discretes')
discretes.grid()

#plt.axvline(df['Time[ms]'][armBegin_index], color='0.8', label = 'ARM')
#plt.axvline(df['Time[ms]'][armEnd_index], color='0.8', label = 'ARM')












plt.show()

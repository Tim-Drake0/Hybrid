import matplotlib.pyplot as plt
import pandas as pd

# "Time[ms],BATT[V],5V[V],RADIO[V],PT1[psi],PT2[psi],PT3[psi],PT4[psi],PT5[psi],PT6[psi],LC[lbf],C1,C2,FILL,VENT,MOV,ARM,PY1,PY2"


# Read the CSV file into a DataFrame

#df = pd.read_csv(fd.askopenfilename())
df = pd.read_csv('E:\data32.csv')
#df = pd.read_csv('E:\data3.csv')
df["Time[ms]"] = round(df['Time[ms]'].multiply(0.001),1)
#df['Time[ms]'] = pd.to_datetime(df['Time[ms]'], format = '%Y-%m-%d %H:%M')


i=0
abool = 0
bbool = 0
for a in df['ARM']:
    i=i+1
    if a == 1 and abool == 0:
        armBegin_index = i
        abool = 1
    
    if a == 0 and abool == 1 and bbool == 0:
        armEnd_index = i-1
        bbool = 1
    
#print(df['Time[ms]'][armBegin_index])
#print(df['Time[ms]'][armEnd_index])

# Voltage Plot
fig, voltages = plt.subplots(figsize = (20,5)) #figsize = (40,10)
voltages.plot(df['Time[ms]'], df['BATT[V]'], label = 'Battery')
voltages.plot(df['Time[ms]'], df['5V[V]'], label = '5V')
voltages.plot(df['Time[ms]'], df['RADIO[V]'], label = 'Radio')

voltages.legend()
voltages.set_xlabel('Time [sec]')
voltages.set_ylabel('Volts [V]')
voltages.set_title('Voltage')
voltages.grid()

#plt.axvline(df['Time[ms]'][armBegin_index], color='0.8', label = 'ARM')
#plt.axvline(df['Time[ms]'][armEnd_index], color='0.8', label = 'ARM')


                                                           

# Pressure Transducer Plot
fig, pressures = plt.subplots(figsize = (20,5)) #figsize = (40,10)
pressures.plot(df['Time[ms]'], df['PT1[psi]'], label = 'PT1')
pressures.plot(df['Time[ms]'], df['PT2[psi]'], label = 'PT2')
pressures.plot(df['Time[ms]'], df['PT3[psi]'], label = 'PT3')
pressures.plot(df['Time[ms]'], df['PT4[psi]'], label = 'PT4')
pressures.plot(df['Time[ms]'], df['PT5[psi]'], label = 'PT5')
pressures.plot(df['Time[ms]'], df['PT6[psi]'], label = 'PT6')

pressures.legend()
pressures.set_xlabel('Time [sec]')
pressures.set_ylabel('PSI')
pressures.set_title('Pressure')
pressures.grid()

#plt.axvline(df['Time[ms]'][armBegin_index], color='0.8', label = 'ARM')
#plt.axvline(df['Time[ms]'][armEnd_index], color='0.8', label = 'ARM')


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




# Discretes Plot
fig, discretes = plt.subplots(figsize = (20,5)) #figsize = (40,10)
discretes.plot(df['Time[ms]'], df['C1'] + 14, label = 'C1')
discretes.plot(df['Time[ms]'], df['C2'] + 12, label = 'C2')
discretes.plot(df['Time[ms]'], df['FILL'] + 10, label = 'FILL')
discretes.plot(df['Time[ms]'], df['VENT'] + 8, label = 'VENT')
discretes.plot(df['Time[ms]'], df['MOV'] + 6, label = 'MOV')
discretes.plot(df['Time[ms]'], df['ARM'] + 4, label = 'ARM')
discretes.plot(df['Time[ms]'], df['PY1'] + 2, label = 'PY1')
discretes.plot(df['Time[ms]'], df['PY2'] + 0, label = 'PY2')

discretes.legend()
discretes.set_xlabel('Time [sec]')
#discretes.set_ylabel('Discretes')
discretes.set_title('Discretes')
discretes.grid()

#plt.axvline(df['Time[ms]'][armBegin_index], color='0.8', label = 'ARM')
#plt.axvline(df['Time[ms]'][armEnd_index], color='0.8', label = 'ARM')












plt.show()

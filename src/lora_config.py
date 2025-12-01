import numpy as np

# --- Radio Constants ---
# Sensitivity values (SF, BW125, BW250, BW500) in dBm
# Based on the original code's modified values
SF7 = np.array([7, -123, -120, -117.0])
SF8 = np.array([8, -126, -123, -120.0])
SF9 = np.array([9, -129, -126, -123.0])
SF10 = np.array([10, -132, -129, -126.0])
SF11 = np.array([11, -134.53, -131.52, -128.51])
SF12 = np.array([12, -137, -134, -131.0])
SENSI = np.array([SF7, SF8, SF9, SF10, SF11, SF12])

# Isolation Thresholds (Inter-SF Interference - Pseudo-Orthogonality)
# Row index is interfering SF, Column index is desired SF (both 7-12, index 0-5)
IS7 = np.array([1, -8, -9, -9, -9, -9])
IS8 = np.array([-11, 1, -11, -12, -13, -13])
IS9 = np.array([-15, -13, 1, -13, -14, -15])
IS10 = np.array([-19, -18, -17, 1, -17, -18])
IS11 = np.array([-22, -22, -21, -20, 1, -20])
IS12 = np.array([-25, -25, -25, -24, -23, 1])
ISO_THRESHOLDS = np.array([IS7, IS8, IS9, IS10, IS11, IS12])

# LoRaWAN Parameters
BANDWIDTH = 125  # kHz (changed from 126 to match standard LoRa bandwidths)
CODING_RATE = 1  # CR 4/5
LORAWAN_HEADER = 7  # Bytes
PCKT_LENGTH_SF = [20, 20, 20, 20, 20, 20]  # Packet size per SFs (index 0=SF7, 5=SF12)
ACK_MESS_LEN = 0 # Length of the ACK payload

# Transmission Power (dBm)
TX_POWER = 14

# Path Loss Model (Log-Distance Path Loss with Shadowing)
PTX = 9.75
GAMMA = 2.00
D0 = 150.0
VAR = 2.0  # Variance for shadowing
LPLD0 = 127.41
GL = 0.0

# Energy Consumption (mA at 3.0V)
# TX consumption from -2 to +17 dBm (index 0 is -2 dBm, 19 is +17 dBm)
TX_MA = [22, 22, 22, 23, 24, 24, 24, 25, 25, 25, 25, 26, 31, 32, 34, 35, 44, 82, 85, 90] 
RX_MA = 16
VOLTAGE = 3.0  # V

# --- Simulation Parameters (Initializable in main) ---
MAX_BS_RECEIVES = 8 # Maximum number of packets the BS can receive at the same time

# ACK Duty Cycle Logic
# nearstACK1p = [0, 0, 0]  # 3 channels with 1% duty cycle
# nearstACK10p = 0  # one channel with 10% duty cycle
# FREQUENCIES = [872000000, 864000000, 860000000]

# ADR++ Related (for future implementation of the actual ADR++ logic)
# EFFICIENCY_CONTROLLER_A = ...
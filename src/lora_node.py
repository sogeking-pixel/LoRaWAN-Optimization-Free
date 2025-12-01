import numpy as np
import math
import random
import simpy
from typing import List, TYPE_CHECKING
from .lora_config import *
from .lora_propagation import airtime
import sys

if TYPE_CHECKING:
    class SimPyEnv:
        now: float
    class myNode:
        env: SimPyEnv

class myPacket:
    def __init__(self, nodeid: int, freq: int, sf: int, bw: int, cr: int, txpow: float, distance: float):
        self.nodeid = nodeid
        self.freq = freq
        self.sf = sf
        self.bw = bw
        self.cr = cr
        self.txpow = txpow
        # payload length uses data_size from config later, LORAWAN_HEADER is a constant
        self.pl = LORAWAN_HEADER + PCKT_LENGTH_SF[self.sf - 7] 
        self.rectime = airtime(self.sf, self.cr, self.pl, self.bw)
        
        # path loss and rssi calculation
        Lpl = LPLD0 + 10 * GAMMA * math.log10(distance / D0)
        if VAR > 0:
            Lpl += np.random.normal(0, VAR)

        self.rssi = self.txpow - GL - Lpl
        
        # status flags
        self.collided = 0
        self.processed = 0
        self.lost = False
        self.perror = False
        self.acked = 0
        self.acklost = 0
        self.addTime = 0.0 # time when packet is added to bs queue


class assignParameters:
    """assigns initial sf and parameters based on distance (adr-like)."""
    def __init__(self, nodeid: int, distance: float):
        self.nodeid = nodeid
        self.txpow = TX_POWER
        self.bw = BANDWIDTH
        self.cr = CODING_RATE
        self.sf = 12
        self.freq = random.choice([872000000, 864000000, 860000000])

        Lpl = LPLD0 + 10 * GAMMA * math.log10(distance / D0)
        Prx = self.txpow - GL - Lpl
        
        min_airtime = 9999
        min_sf = 0
        
        # find the smallest sf (lowest airtime) that satisfies the link budget
        for i in range(0, 6):  # SFs 7 to 12
            sf_check = i + 7
            bw_index = [125, 250, 500].index(self.bw) + 1 # 500kHz -> index 3
            
            if SENSI[i, bw_index] < Prx:
                at = airtime(sf_check, self.cr, LORAWAN_HEADER + PCKT_LENGTH_SF[i], self.bw)
                if at < min_airtime:
                    min_airtime = at
                    min_sf = sf_check
                    
        if min_sf != 0:
            self.rectime = min_airtime
            self.sf = min_sf

class myNode:
    def __init__(self, nodeid: int, bs: int, period: float, datasize: float, max_dist: float, bsx: float, bsy: float, nodes_list: List):
        self.nodeid = nodeid
        self.buffer = datasize
        self.bs = bs
        self.period = period
        self.lstretans = 0 
        self.sent = 0
        self.coll = 0
        self.lost = 0
        self.noack = 0
        self.acklost = 0
        self.recv = 0
        self.losterror = 0
        self.rxtime = 0.0 
        self.env = None 

        self.last_sent_count = 0
        self.last_recv_count = 0
        self.sf_history = []
        self.adr_change_pending = False
        
        self.x, self.y = self._place_node(max_dist, bsx, bsy, nodes_list)
        self.dist = np.sqrt((self.x - bsx)**2 + (self.y - bsy)**2)

        self.txpow = TX_POWER 
        self.parameters = None
        self.packet = None
        
        # --- event-based transmission logic ---
        self.last_value = 0.0 
        self.value_threshold = 0.4

    def _place_node(self, max_dist, bsx, bsy, nodes_list):
        """place node using an adapted radial distribution."""
        rounds = 0
        min_dist_check = 10 
        while rounds < 1000:
            a, b = random.random(), random.random()
            if b < a: a, b = b, a
            posx = b * max_dist * math.cos(2 * math.pi * a / b) + bsx
            posy = b * max_dist * math.sin(2 * math.pi * a / b) + bsy
            
            if not nodes_list: return posx, posy

            found = True
            for n in nodes_list:
                dist = np.sqrt(((abs(n.x - posx))**2) + ((abs(n.y - posy))**2))
                if dist < min_dist_check:
                    found = False; break
            
            if found: return posx, posy
            rounds += 1
        
        print("Could not place new node, giving up")
        sys.exit(-1)
        
    def check_event(self) -> bool:
        """simulates event-based sensing."""
        current_value = self.last_value + np.random.normal(0, 2.0)
        
        if abs(current_value - self.last_value) > self.value_threshold:
            self.last_value = current_value
            return True
        else:
            self.last_value = current_value
            return False
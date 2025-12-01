import math
from typing import List, Tuple, TYPE_CHECKING
from .lora_config import ISO_THRESHOLDS, BANDWIDTH, LORAWAN_HEADER, ACK_MESS_LEN
from .lora_propagation import airtime

# type hinting setup
if TYPE_CHECKING:
    from .lora_node import myPacket, myNode # avoid circular imports at runtime

def frequency_collision(p1: 'myPacket', p2: 'myPacket') -> bool:
    """checks for frequency collision based on BW."""
    freq_diff = abs(p1.freq - p2.freq)
    
    if (freq_diff <= 120000 and (p1.bw == 500 or p2.bw == 500)):
        # print("frequency coll 500")
        return True
    elif (freq_diff <= 60000 and (p1.bw == 250 or p2.bw == 250)):
        # print("frequency coll 250")
        return True
    elif (freq_diff <= 30000): # Assuming 125kHz is the remaining case
        # print("frequency coll 125")
        return True
    
    return False

def timing_collision(p1: 'myPacket', p2: 'myPacket', env_now: float) -> bool:
    """checks for timing collision based on preamble overlap."""
    # the original logic assumes p1 is the newly arrived packet (env_now is p1's arrival time)
    # Npream is 8. Critical section is when the first 5 symbols of the preamble are lost.
    Npream = 8
    
    # max loss is (Npream - 5) * Tsym
    Tsym = (2**p1.sf) / (p1.bw * 1000.0) # seconds
    Tpreamb = (Npream - 5) * Tsym
    
    # p1's critical section starts at arrival time and ends Tpreamb later
    p1_cs = env_now + Tpreamb
    p2_end = p2.addTime + p2.rectime
    
    if p1_cs < p2_end:
        # p2 ends after p1's critical section ends -> p1 is corrupted
        return True
    
    return False

def power_collision_2(p1: 'myPacket', p2: 'myPacket') -> Tuple['myPacket', ...]:
    """
    checks for capture effect + non-orthogonality SFs effects.
    returns a tuple of the casualty packets.
    """
    casualties = []
    
    sf1_idx = p1.sf - 7
    sf2_idx = p2.sf - 7
    
    if p1.sf == p2.sf:
        # same SF
        iso_threshold = ISO_THRESHOLDS[sf1_idx][sf2_idx]
        rssi_diff = abs(p1.rssi - p2.rssi)
        
        if rssi_diff < iso_threshold:
            # too close, both collide
            casualties = (p1, p2)
        elif p1.rssi - p2.rssi < iso_threshold:
            # p2 is significantly stronger, p1 is lost
            casualties = (p1,)
        else:
            # p1 is significantly stronger, p2 is lost
            casualties = (p2,)
    else:
        # different SFs (Non-orthogonality)
        
        # check if p1 wins against p2
        if p1.rssi - p2.rssi <= ISO_THRESHOLDS[sf1_idx][sf2_idx]:
            # p1 is lost
            casualties.append(p1)
            
        # check if p2 wins against p1
        if p2.rssi - p1.rssi <= ISO_THRESHOLDS[sf2_idx][sf1_idx]:
            # p2 is lost
            casualties.append(p2)
            
    return tuple(casualties)

def check_collision(packet: 'myPacket', packets_at_bs: List['myNode'], 
                    max_bs_receives: int, full_collision: int) -> int:
    """
    checks if a newly arrived packet collides with any packet already at the BS.
    returns 1 if the 'packet' is a casualty, 0 otherwise.
    """
    col = 0
    processing = sum(1 for n in packets_at_bs if n.packet.processed == 1)
    
    # check if BS is overloaded
    if processing >= max_bs_receives:
        packet.processed = 0
        return 1
    else:
        packet.processed = 1
    
    if not packets_at_bs:
        return 0
    
    for other_node in packets_at_bs:
        other_packet = other_node.packet
        if other_packet.nodeid != packet.nodeid:
            
            if frequency_collision(packet, other_packet) and timing_collision(packet, other_packet, other_node.env.now):
                
                # check who collides in the power domain
                if full_collision == 1:
                    # capture effect only
                    casualties = power_collision_2(packet, other_packet) # Power collision 1 is a subset of 2
                elif full_collision == 2:
                    # capture + Non-orthogonality SFs effects
                    casualties = power_collision_2(packet, other_packet)
                else:
                    # simplified collision (SF + Timing + Frequency)
                    if packet.sf == other_packet.sf:
                        casualties = (packet, other_packet)
                    else:
                        casualties = () # only simplified collision checks same SF
                
                for p in casualties:
                    p.collided = 1
                    if p is packet:
                        col = 1
                        
    return col

def check_ack(packet: 'myPacket', env_now: float, node: 'myNode', 
              nearst_ack_1p: List[float], nearst_ack_10p: float) -> Tuple[bool, float, List[float], float]:
    """
    checks if the gateway can ack this packet based on duty cycle.
    returns: (acked, ack_airtime, updated_nearst_ack_1p, updated_nearst_ack_10p)
    """

    updated_1p = list(nearst_ack_1p)
    updated_10p = nearst_ack_10p
    
    # channel frequencies (assuming the same as the original)
    FREQUENCIES = [872000000, 864000000, 860000000]

    # 1. check ACK in the first window (1 sec after reception)
    try:
        chanl_index = FREQUENCIES.index(packet.freq)
    except ValueError:
        # if the packet frequency is not one of the 3 channels, assume it can't be acked on the 1% channels
        chanl_index = -1 
        
    ack_airtime = 0.0
    
    if chanl_index != -1:
        time_of_acking_1 = env_now + 1.0 
        
        if time_of_acking_1 >= updated_1p[chanl_index]:
            # this packet can be acked in the first window
            ack_airtime = airtime(packet.sf, 1, ACK_MESS_LEN + LORAWAN_HEADER, BANDWIDTH)
            updated_1p[chanl_index] = time_of_acking_1 + (ack_airtime / 0.01)
            node.rxtime += ack_airtime
            return True, ack_airtime, updated_1p, updated_10p
        else:
            # ACK not possible in first window (must listen for preamble)
            Tsym = (2**packet.sf) / (BANDWIDTH * 1000.0) # seconds
            Tpream = (8 + 4.25) * Tsym
            node.rxtime += Tpream

    # 2. check ACK in the second window (2 sec after reception, SF12, 10% duty cycle)
    time_of_acking_2 = env_now + 2.0 
    
    if time_of_acking_2 >= updated_10p:
        # this packet can be acked in the second window
        ack_airtime = airtime(12, 1, ACK_MESS_LEN + LORAWAN_HEADER, BANDWIDTH)
        updated_10p = time_of_acking_2 + (ack_airtime / 0.1)
        node.rxtime += ack_airtime
        return True, ack_airtime, updated_1p, updated_10p
    else:
        Tsym = (2.0**12) / (BANDWIDTH * 1000.0)
        Tpream = (8 + 4.25) * Tsym
        node.rxtime += Tpream
        return False, 0.0, updated_1p, updated_10p
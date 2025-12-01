import simpy
import random
import numpy as np
import math
from typing import List
from .lora_config import *
from .lora_propagation import per, airtime
from .lora_collision import check_collision, check_ack
from .lora_node import myNode

# --- Global Statistics (Counters) ---
NR_COLLISIONS = 0
NR_RECEIVED = 0
NR_LOST = 0
NR_LOST_ERROR = 0
NR_NO_ACK = 0
NR_ACK_LOST = 0
NR_PROCESSED = 0

def transmit(env: simpy.Environment, node: myNode, full_collision: int, max_bs_receives: int,
             packets_at_bs: List[myNode], nearst_ack_1p: List[float], nearst_ack_10p: float,
             adr_enabled: bool, adr_check_interval: float):
    """
    Main discrete event loop for a node. 
    Implements Event-Based Tx and optionally ADR++ (via network_server process).
    """
    node.env = env
    
    global NR_COLLISIONS, NR_RECEIVED, NR_LOST, NR_LOST_ERROR, NR_NO_ACK, NR_ACK_LOST, NR_PROCESSED

    last_adr_check = 0.0

    while node.buffer > 0.0:
        

        if adr_enabled and node.adr_change_pending:
            # Apply a new configuration
            old_sf = node.parameters.sf
            
            # Reassign packet parameters with the new SF/TXPower
            node.packet.sf = node.parameters.sf
            node.packet.txpow = node.parameters.txpow
            
            # Recalculate Airtime (Transmission Time)
            node.packet.pl = LORAWAN_HEADER + PCKT_LENGTH_SF[node.parameters.sf - 7]
            node.packet.rectime = airtime(node.parameters.sf, node.parameters.cr, node.packet.pl, node.parameters.bw)
            
            node.sf_history.append(node.parameters.sf)
            node.adr_change_pending = False
            
            # Wait for a minimum time as if a Downlink command had been received
            yield env.timeout(node.packet.rectime * 0.01) # Small penalty/delay
        
        send_packet = False
        if adr_enabled:
            send_packet = node.check_event()
        else:
            node.check_event()
            send_packet = True
        
        if send_packet:
            # Delay/Retransmission Logic
            if node.lstretans > 0 and node.lstretans <= 8:
                node.buffer += node.packet.pl - LORAWAN_HEADER # Restore payload
                yield env.timeout(max(2.0 + airtime(12, CODING_RATE, ACK_MESS_LEN + LORAWAN_HEADER, BANDWIDTH), 
                                      node.packet.rectime * ((1 - 0.01) / 0.01)) 
                                      + (random.expovariate(1.0 / 2000.0)))
            else:
                yield env.timeout(random.expovariate(1.0 / node.period))
            
            # Update payload length based on current parameters (important for retransmissions)
            node.packet.pl = LORAWAN_HEADER + (node.parameters.pl_bytes if hasattr(node.parameters, 'pl_bytes') else PCKT_LENGTH_SF[node.parameters.sf - 7])
            node.buffer -= node.packet.pl - LORAWAN_HEADER
            
            # Re-evaluate RSSI with shadowing for this transmission
            Lpl = LPLD0 + 10 * GAMMA * math.log10(node.dist / D0)
            if VAR > 0: Lpl += np.random.normal(0, VAR)
            node.packet.rssi = node.packet.txpow - GL - Lpl

            # 2. Packet Arrival at BS (Propagation Delay is assumed minimal/ignored)
            node.sent += 1
            node.packet.addTime = env.now
            
            # Check Link Loss
            sensitivity = SENSI[node.packet.sf - 7, [125, 250, 500].index(node.packet.bw) + 1]
            if node.packet.rssi < sensitivity:
                node.packet.lost = True
            else:
                node.packet.lost = False
                
                # Check Packet Error (PER)
                if per(node.packet.sf, node.packet.bw, node.packet.cr, node.packet.rssi, node.packet.pl) >= random.uniform(0, 1):
                    node.packet.perror = True
                else:
                    # Check for Collision
                    collision_result = check_collision(node.packet, packets_at_bs, max_bs_receives, full_collision)
                    if collision_result == 1: node.packet.collided = 1
                
                # Add to queue if not lost
                if not node.packet.lost and not node.packet.perror:
                    packets_at_bs.append(node)
        
            # 3. Packet Reception Time
            yield env.timeout(node.packet.rectime)

            # 4. Process Result and Check ACK
            is_acked = False
            
            if (not node.packet.lost and not node.packet.perror and node.packet.collided == 0):
                is_acked, _, nearst_ack_1p[:], nearst_ack_10p = check_ack(node.packet, env.now, node, nearst_ack_1p, nearst_ack_10p)
                if is_acked:
                    node.packet.acked = 1
                    
                    # Check for ACK Loss (Downlink link budget)
                    dl_rssi = TX_POWER - LPLD0 - 10 * GAMMA * math.log10(node.dist / D0)
                    if VAR > 0: dl_rssi -= np.random.normal(0, VAR)
                    
                    if dl_rssi < sensitivity:
                        node.packet.acklost = 1
                    else:
                        node.packet.acklost = 0
                else:
                    node.packet.acked = 0
            else:
                node.packet.acked = 0

            # 5. Update Statistics and Retransmission Status
            if node.packet.processed == 1: NR_PROCESSED += 1
            
            if node.packet.lost:
                node.lost += 1; node.lstretans += 1; NR_LOST += 1
            elif node.packet.perror:
                node.losterror += 1; NR_LOST_ERROR += 1
            elif node.packet.collided == 1:
                node.coll += 1; node.lstretans += 1; NR_COLLISIONS += 1
            elif node.packet.acked == 0:
                node.noack += 1; node.lstretans += 1; NR_NO_ACK += 1
            elif node.packet.acklost == 1:
                node.acklost += 1; node.lstretans += 1; NR_ACK_LOST += 1
            else:
                node.recv += 1; node.lstretans = 0; NR_RECEIVED += 1

            if adr_enabled:
                if node.packet.collided == 0 and not node.packet.lost and not node.packet.perror:
                    node.last_recv_count += 1
                node.last_sent_count += 1

            # Clean up
            if node in packets_at_bs: packets_at_bs.remove(node)
            node.packet.collided = 0; node.packet.processed = 0
            node.packet.lost = False; node.packet.acked = 0; node.packet.acklost = 0
            
        else:
            # No event, wait
            yield env.timeout(random.uniform(0.5, 1.5) * node.period / 2.0)
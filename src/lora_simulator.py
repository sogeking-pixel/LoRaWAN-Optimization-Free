import simpy
import random
import sys
import math
import numpy as np
import os
import re
import json
import matplotlib.pyplot as plt
from typing import List, Tuple

# import modules
import src.lora_events as lora_events
from .lora_config import *
from .lora_node import myNode, assignParameters, myPacket
from .lora_events import transmit
from .lora_events import NR_COLLISIONS, NR_RECEIVED, NR_LOST, NR_LOST_ERROR, NR_NO_ACK, NR_ACK_LOST 

# global configuration holder
CONFIG = {}

def load_config(config_file: str):
    """loads configuration parameters from a JSON file."""
    global CONFIG
    try:
        with open(config_file, 'r') as f:
            CONFIG = json.load(f)
        
        # Override DATA_SIZE in global array
        payload_size = CONFIG['SIMULATION_PARAMS']['DATA_SIZE']
        for i in range(len(PCKT_LENGTH_SF)):
             PCKT_LENGTH_SF[i] = payload_size
             
    except Exception as e:
        print(f"Error loading config file: {e}")
        sys.exit(-1)

def reset_global_counters():
    """resets all global statistics counters in the lora_events module."""
    counter_names = [
        'NR_COLLISIONS', 'NR_RECEIVED', 'NR_LOST', 'NR_LOST_ERROR', 
        'NR_NO_ACK', 'NR_ACK_LOST', 'NR_PROCESSED'
    ]
    for name in counter_names:
        if hasattr(lora_events, name):
            setattr(lora_events, name, 0)

def network_server_process(env: simpy.Environment, nodes: List['myNode'], config: dict):
    """
    simulates the Network Server responsible for calculating and enforcing ADR++ policy.
    """
    adr_config = config['ADR_PLUS_PLUS']
    adr_interval = adr_config['ADR_CHECK_INTERVAL']
    efficiency_threshold = adr_config['EFFICIENCY_THRESHOLD']
    
    while True:
        yield env.timeout(adr_interval)
        
        total_sent_interval = sum(n.last_sent_count for n in nodes)
        total_recv_interval = sum(n.last_recv_count for n in nodes)
        
        # NSR - Network Success Rate
        network_success_rate = (total_recv_interval / total_sent_interval) if total_sent_interval > 0 else 0
        is_congested = network_success_rate < efficiency_threshold
        
        for node in nodes:
            if node.last_sent_count == 0:
                continue

            isr = node.last_recv_count / node.last_sent_count
            new_sf = node.parameters.sf

            if isr >= efficiency_threshold:
                # reward
                if new_sf > 7:
                    new_sf -= 1       
            elif is_congested or isr < (efficiency_threshold * 0.6):
                # penalty
                if new_sf < 12:
                    new_sf += 1
            
            if new_sf != node.parameters.sf:
                node.parameters.sf = new_sf
                node.adr_change_pending = True
                
            node.last_sent_count = 0
            node.last_recv_count = 0

def run_simulation(config: dict, nr_nodes: int, is_modified: bool):
    """runs a single simulation instance (Base or Modified)."""
    
    # 1. parameter extraction
    sim_params = config['SIMULATION_PARAMS']
    exp_ctrl = config['EXPERIMENT_CONTROL']
    adr_config = config['ADR_PLUS_PLUS']

    full_collision = sim_params['FULL_COLLISION_MODEL']
    max_bs_receives = exp_ctrl['MAX_BS_RECEIVES']
    avg_send_time = sim_params['AVG_SEND_TIME']
    datasize = sim_params['DATA_SIZE']
    
    # 2. setup environment and geometry (correction)
    env = simpy.Environment()
    
    # distance calculation (before it was missing)
    # using constants imported from lora_config
    min_sensi = np.amin(SENSI[:, [125, 250, 500].index(BANDWIDTH) + 1])
    lpl = PTX - min_sensi
    max_dist = D0 * (10**((lpl - LPLD0) / (10.0 * GAMMA)))
    bsx = max_dist + 10
    bsy = max_dist + 10

    packets_at_bs: List['myNode'] = []
    nearst_ack_1p: List[float] = [0.0, 0.0, 0.0]
    nearst_ack_10p: float = 0.0
    nodes: List['myNode'] = []

    # 3. node creation
    for i in range(nr_nodes):
        node = myNode(i, 1, avg_send_time, datasize, max_dist, bsx, bsy, nodes)
        nodes.append(node)
        
        node.parameters = assignParameters(node.nodeid, node.dist)
        node.packet = myPacket(node.nodeid, node.parameters.freq, node.parameters.sf, 
                                 node.parameters.bw, node.parameters.cr, node.parameters.txpow, 
                                 node.dist)
        
        if is_modified:
            # modified: event-based tx + adr++ logic
            env.process(transmit(env, node, full_collision, max_bs_receives, 
                                 packets_at_bs, nearst_ack_1p, nearst_ack_10p,
                                 adr_enabled=adr_config['ENABLED'], adr_check_interval=adr_config['ADR_CHECK_INTERVAL']))
        else:
            # base: periodic tx
            env.process(transmit(env, node, full_collision, max_bs_receives, 
                                 packets_at_bs, nearst_ack_1p, nearst_ack_10p,
                                 adr_enabled=False, adr_check_interval=0.0))
            
    # 4. start network server if modified
    if is_modified and adr_config['ENABLED']:
        env.process(network_server_process(env, nodes, config))

    # 5. run simulation
    env.run(until=exp_ctrl['SIMULATION_TIME'])
    
    return nodes, env.now

def calculate_stats(nodes: List[myNode], sim_time: float, config: dict):
    """calculates and prints final statistics."""
    
    sent = sum(n.sent for n in nodes)
    nr_received = lora_events.NR_RECEIVED
    nr_collisions = lora_events.NR_COLLISIONS
    nr_lost = lora_events.NR_LOST
    nr_lost_error = lora_events.NR_LOST_ERROR
    nr_no_ack = lora_events.NR_NO_ACK
    nr_ack_lost = lora_events.NR_ACK_LOST

    # energy calculation
    energy = 0.0
    for node in nodes:
        tx_index = int(node.packet.txpow) + 2
        tx_current = TX_MA[min(tx_index, len(TX_MA) - 1)]
        node_tx_energy = (node.packet.rectime * node.sent * tx_current * VOLTAGE) / 1000.0
        node_rx_energy = (node.rxtime * RX_MA * VOLTAGE) / 1000.0
        energy += node_tx_energy + node_rx_energy
        
    # fairness index
    if sent > 0:
        recv_rates = np.array([n.recv / n.sent for n in nodes if n.sent > 0])
        nodefair = (np.sum(recv_rates)**2) / (len(recv_rates) * np.sum(recv_rates**2)) if len(recv_rates) > 0 else 0
    else:
        nodefair = 0
        
    # sf distribution
    sf_counts = {sf: 0 for sf in range(7, 13)}
    for n in nodes: sf_counts[n.parameters.sf] += 1
    sf_distribution = [sf_counts[sf] for sf in range(7, 13)] 

    # der
    der1 = (sent - nr_collisions - nr_lost - nr_lost_error - nr_no_ack - nr_ack_lost) / float(sent) if sent != 0 else 0
    der2 = nr_received / float(sent) if sent != 0 else 0
    
    # throughput
    total_data_bits = nr_received * (LORAWAN_HEADER + config['SIMULATION_PARAMS']['DATA_SIZE']) * 8
    throughput = total_data_bits / sim_time if sim_time > 0 else 0
    
    print("\n=================== Results ===================")
    print(f"Nodes: {len(nodes)} | Time: {sim_time:.2f}s")
    print(f"Sent: {sent} | Received: {nr_received}")
    print(f"DER: {der2:.4f} | Energy: {energy:.4f} J")
    print(f"Collisions: {nr_collisions}")
    print("==================================================")
    
    return (sent, nr_collisions, nr_lost, nr_lost_error, nr_no_ack, nr_ack_lost, 
            sim_time, der1, der2, energy, nodefair, sf_distribution)

def save_results(config, results, scenario_type="UNKNOWN", nr_nodes=0):
    """saves results to a .dat file."""
    
    sim_params = config['SIMULATION_PARAMS']
    exp_ctrl = config['EXPERIMENT_CONTROL']
    
    rnd_seed = sim_params['RND_SEED']
    full_collision = sim_params['FULL_COLLISION_MODEL']
    nodes_count = nr_nodes if nr_nodes > 0 else sim_params['NR_NODES']
    avg_send_time = sim_params['AVG_SEND_TIME']
    datasize = sim_params['DATA_SIZE']
    fname = exp_ctrl['OUTPUT_FILENAME']
    
    (sent, nr_collisions, nr_lost, nr_lost_error, nr_no_ack, nr_ack_lost, 
     sim_time, der1, der2, energy, nodefair, sf_distribution) = results
    
    sf_str = "_".join(map(str, sf_distribution))
    
    # add scenario_type to the results
    res = (f"{rnd_seed}, {full_collision}, {nodes_count}, {avg_send_time}, {datasize}, {sent}, "
           f"{nr_collisions}, {nr_lost}, {nr_lost_error}, {nr_no_ack}, {nr_ack_lost}, "
           f"{sim_time}, {der1:.4f}, {der2:.4f}, {energy:.4f}, {nodefair:.4f}, {sf_str}, {scenario_type}")

    if not os.path.isfile(fname):
        header = "#seed, collType, nodes, rate, size, sent, coll, lost, lostErr, noAck, ackLost, time, DER1, DER2, Energy, Fair, SFs, Type\n"
        res = header + res

    new_res = re.sub(r'[^\#a-zA-Z0-9 \n\.\,\"_]', '', res)
    
    # create directory if it doesn't exist
    os.makedirs(os.path.dirname(fname), exist_ok=True)
    
    with open(fname, "a") as myfile:
        myfile.write(new_res + "\n")
    print(f"Results saved to {fname}")

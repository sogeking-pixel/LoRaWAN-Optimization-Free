"""
 LoraFreeSim
 author: Khaled Abdelfadeel - khaled.abdelfadeel@mycit.ie
 repository: https://github.com/kqorany/FREE.git 

 Modified by: Yerson Sanchez - ysanchezl@unitru.edu.pe
 Update Project python2 to Python3
 Added algorithm ADR++ and Event based
"""

import json
import os
import numpy as np
import matplotlib.pyplot as plt

# Import core simulation logic
from src.lora_simulator import run_simulation, calculate_stats, reset_global_counters, save_results

def run_automated_experiments():
    """Reads JSON, runs Base and Modified scenarios for all node counts, and plots comparison."""
    
    CONFIG_FILE = 'config/config.json'
    try:
        with open(CONFIG_FILE, 'r') as f:
            config = json.load(f)
    except FileNotFoundError:
        # Try fallback to local path if src path fails
        try:
            with open('config.json', 'r') as f:
                config = json.load(f)
        except:
            print(f"Error: config.json not found.")
            return
    DATA_FILE = 'results/row_data/simulation_results.dat'
    try:
        os.remove(DATA_FILE)
    except FileNotFoundError:
        print(f"Error: {DATA_FILE} not found.")

    node_scenarios = config['NODE_SCENARIOS']
    all_results = {}
    
    print("--- STARTING EXPERIMENTS ---")
    
    for nr_nodes in node_scenarios:
        print(f"\n[SCENARIO: {nr_nodes} NODOS]")
        
        # Update config for this scenario
        config['SIMULATION_PARAMS']['NR_NODES'] = nr_nodes
        
        # 1. RUN BASE SIMULATION
        print(" -> Running Base...")
        reset_global_counters()
        base_nodes, base_time = run_simulation(config, nr_nodes, is_modified=False)
        base_stats = calculate_stats(base_nodes, base_time, config)
        
        # 2. RUN MODIFIED SIMULATION
        print(" -> Running Modified (ADR++ and Event-based)...")
        reset_global_counters()
        mod_nodes, mod_time = run_simulation(config, nr_nodes, is_modified=True)
        mod_stats = calculate_stats(mod_nodes, mod_time, config)
        
        all_results[nr_nodes] = {
            'base': base_stats,
            'modified': mod_stats
        }
        
        # save result
        save_results(config, base_stats, scenario_type='BASE', nr_nodes=nr_nodes)
        save_results(config, mod_stats, scenario_type='MODIFIED', nr_nodes=nr_nodes)
        
    print("\n--- EXPERIMENTS COMPLETED ---")

if __name__ == '__main__':
    run_automated_experiments()
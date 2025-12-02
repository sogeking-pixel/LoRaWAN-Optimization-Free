# LoRaWAN Simulation with Congestion-Resilient ADR and Event Optimization

## Overview

This repository is a **refactored and enhanced version** of the LoRaFREE simulator, originally developed for the research presented in [1]. This version has been modernized and extended with new capabilities to support advanced LoRaWAN simulation scenarios.

## About LoRaFREE

LoRaFREE is a comprehensive SimPy-based simulator for LoRaWAN networks that extends the capabilities of the original LoRaSim simulator. It provides a more realistic simulation environment by considering:

- **Packet Error Model**: Realistic packet loss modeling
- **Imperfect Orthogonality**: Accounts for spreading factor interference
- **Fading Impact**: Channel fading effects on transmission
- **Duty Cycle Limitations**: Compliance with both device and gateway duty cycle restrictions
- **Bidirectional Communication**: Full downlink capability support
- **Retransmission Strategy**: Confirmable uplink transmission handling
- **Enhanced Energy Model**: Energy consumption during both transmission and reception
- **Synchronized Transmission Scheduling**: Implementation of the FREE scheduling algorithm

## What's New in This Version

This repository is based on the original [LoRaFREE simulator](https://github.com/kqorany/FREE.git), which was written in **Python 2**. The following improvements have been made:

### Key Enhancements

- **Python 3 Migration**: Complete refactoring from Python 2 to Python 3 for modern compatibility
- **Event-Driven Simulation**: Added support for discrete event simulation capabilities
- **Congestion-Resilient ADR**: Implementation of the enhanced Congestion-Resilient ADR algorithm
- **Code Refactoring**: Improved code structure, modularity, and maintainability

## Requirements

- Python 3.7+
- SimPy
- NumPy
- Matplotlib
- Seaborn (for visualization)

## Installation

```bash
pip install -r requirements.txt
```

## Usage

Run the main simulation:

```bash
python main.py
```


## Original Repository

This project is based on the original LoRaFREE simulator: [https://github.com/kqorany/FREE.git](https://github.com/kqorany/FREE.git)

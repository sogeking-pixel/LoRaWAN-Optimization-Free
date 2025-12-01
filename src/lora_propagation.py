import math
import numpy as np
from scipy.stats import norm
from .lora_config import BANDWIDTH, CODING_RATE, LORAWAN_HEADER, PCKT_LENGTH_SF, SENSI

# packet error model (based on Reynders)
def ber_reynders(eb_no: float, sf: int) -> float:
    """given the energy per bit to noise ratio (in db), compute the bit error for the SF"""
    return norm.sf(math.log(sf, 12) / math.sqrt(2) * eb_no)

def ber_reynders_snr(snr: float, sf: int, bw: int, cr: int) -> float:
    """compute the bit error given the SNR (db), SF, BW (kHz), and CR"""
    cr_map = {1: 4/5, 2: 4/6, 3: 4/7, 4: 4/8}
    CR = cr_map.get(cr, 4/5)
    BW = bw * 1000.0  # to Hz

    # calculate Eb/No
    eb_no = snr - 10 * math.log10(BW / (2**sf)) - 10 * math.log10(sf) - 10 * math.log10(CR) + 10 * math.log10(BW)
    return ber_reynders(eb_no, sf)

def per(sf: int, bw: int, cr: int, rssi: float, pl: int) -> float:
    """compute the packet error rate (PER)"""
    snr = rssi + 174 - 10 * math.log10(bw * 1000) - 6
    return 1 - (1 - ber_reynders_snr(snr, sf, bw, cr))**(pl * 8)

# airtime calculation
def airtime(sf: int, cr: int, pl: int, bw: int) -> float:
    """
    computes the airtime of a packet (in seconds)
    sf: spreading factor (7-12)
    cr: coding rate (1-4, mapped to 4/5 - 4/8)
    pl: payload length (bytes)
    bw: bandwidth (kHz)
    """
    H = 0          # implicit header disabled (H=0) or not (H=1)
    DE = 0         # low data rate optimization enabled (=1) or not (=0)
    Npream = 8     # number of preamble symbols

    if bw == 125 and sf in [11, 12]:
        DE = 1
    if sf == 6:
        H = 1

    Tsym = (2.0**sf) / bw  # msec
    Tpream = (Npream + 4.25) * Tsym
    
    # calculate payload symbol number (payloadSymbNB)
    numerator = 8.0 * pl - 4.0 * sf + 28 + 16 - 20 * H
    denominator = 4.0 * (sf - 2 * DE)
    payload_symb_nb = 8 + max(math.ceil(numerator / denominator) * (cr + 4), 0)
    
    Tpayload = payload_symb_nb * Tsym
    
    # return time in seconds
    return (Tpream + Tpayload) / 1000.0
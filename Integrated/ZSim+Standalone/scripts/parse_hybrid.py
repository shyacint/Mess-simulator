import argparse
import h5py
import numpy as np
import pandas as pd
from pathlib import Path
import re

h5_path = "/mnt/ssd/Mess-simulator/Integrated/ZSim+Standalone/runs.20260216_233737/10_web_search_serial_koala/zsim.h5"
with h5py.File(h5_path, 'r') as f:
    dset = f['stats']['root']
    print(dset.dtype.names)
    mem_data = dset['hybrid-mem']
    
    # Print the shape (dimensions)
    print(f"Shape of 'mem': {mem_data['mem-6'].shape}")
    
    print(f"Number of elements in 'mem': {mem_data['mem-6'].size}")
    
    if mem_data.dtype.names:
        print(f"Fields in 'mem': {mem_data['mem-6'].dtype.names}")

    print(f"Samples of during sim: {len(mem_data['mem-6'])}")

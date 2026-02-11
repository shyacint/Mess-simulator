import argparse
import h5py
import numpy as np
import pandas as pd
from pathlib import Path
import re

h5_path = Path("/mnt/ssd/Mess-simulator/Integrated/ZSim+Standalone/runs.20260211_125037/10_web_search_serial_koala/zsim.h5")

with h5py.File(h5_path, 'r') as f:
    dset =f['stats']['root']


    print(dset["mem"])

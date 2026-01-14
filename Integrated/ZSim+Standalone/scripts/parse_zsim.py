#!/usr/bin/env python3
"""
Script to aggregate ZSim simulation statistics across multiple applications.
Extracts IPC and execution time from zsim-ev.h5 files in application directories.
"""

import argparse
import h5py
import numpy as np
import pandas as pd
from pathlib import Path
import re


def parse_app_folder(folder_name):
    """
    Parse application folder name to extract app number, name, and type.
    Expected format: ##_app_name_type or ##_app_name
    """
    # Extract number and rest
    match = re.match(r'(\d+)_(.+)', folder_name)
    if not match:
        return None, folder_name, None
    
    app_num = int(match.group(1))
    rest = match.group(2).lower()
    
    # Check if rest contains serial or parallel
    if 'serial' in rest:
        app_type = 'serial'
        app_name = rest.replace('_serial', '').replace('serial', '').strip('_')
    elif 'parallel' in rest:
        app_type = 'parallel'
        app_name = rest.replace('_parallel', '').replace('parallel', '').strip('_')
    else:
        app_type = None
        app_name = rest
    
    return app_num, app_name, app_type


def extract_stats(h5_path, freq_ghz=2.4):
    """
    Extract IPC and execution time from zsim-ev.h5 file.
    
    Args:
        h5_path: Path to zsim-ev.h5 file
        freq_ghz: CPU frequency in GHz for time calculation
    
    Returns:
        dict with ipc, execution_time_s, max_cycles, total_instrs
    """
    try:
        with h5py.File(h5_path, 'r') as f:
            dset = f["stats"]["root"]
            stats = dset[-1]
            
            core_cycles = stats['skylake']['cycles']
            core_instrs = stats['skylake']['instrs']
            
            # Use max cycles as total execution time
            max_cycles = np.max(core_cycles)
            total_instrs = np.sum(core_instrs)
            
            # Handle divide by zero for IPC
            if max_cycles > 0:
                overall_ipc = total_instrs / max_cycles
            else:
                overall_ipc = np.nan
                print(f"Warning: max_cycles is 0 for {h5_path}, setting IPC to NaN")
            
            # Handle divide by zero for execution time
            if freq_ghz > 0 and max_cycles > 0:
                execution_time_s = max_cycles / (freq_ghz * 1e9)
            else:
                execution_time_s = np.nan
                if freq_ghz <= 0:
                    print(f"Warning: invalid frequency {freq_ghz} GHz for {h5_path}")
                if max_cycles <= 0:
                    print(f"Warning: max_cycles is 0 for {h5_path}, setting execution_time to NaN")
            
            return {
                'ipc': overall_ipc,
                'execution_time_s': execution_time_s,
                'max_cycles': max_cycles,
                'total_instrs': total_instrs,
                'num_cores': len(core_cycles)
            }
    except Exception as e:
        print(f"Error reading {h5_path}: {e}")
        return None


def collect_stats(run_dir, freq_ghz=2.4):
    """
    Collect statistics from all application directories in run_dir.
    
    Args:
        run_dir: Path to run directory containing application folders
        freq_ghz: CPU frequency in GHz
    
    Returns:
        pandas DataFrame with collected statistics
    """
    run_path = Path(run_dir)
    
    if not run_path.exists():
        raise FileNotFoundError(f"Run directory not found: {run_dir}")
    
    results = []
    
    # Find all application directories (match pattern ##_*)
    app_dirs = sorted([d for d in run_path.iterdir() 
                      if d.is_dir() and re.match(r'\d+_', d.name)])
    
    print(f"Found {len(app_dirs)} application directories")
    
    for app_dir in app_dirs:
        h5_file = app_dir / "zsim-ev.h5"
        
        if not h5_file.exists():
            print(f"Warning: {h5_file} not found, skipping {app_dir.name}")
            continue
        
        # Parse folder name
        app_num, app_name, app_type = parse_app_folder(app_dir.name)
        
        # Extract stats
        stats = extract_stats(h5_file, freq_ghz)
        
        if stats:
            results.append({
                'app_number': app_num,
                'app_name': app_name,
                'app_type': app_type,
                'ipc': stats['ipc'],
                'execution_time_s': stats['execution_time_s'],
                'execution_time_ms': stats['execution_time_s'] * 1000,
                'max_cycles': stats['max_cycles'],
                'total_instrs': stats['total_instrs'],
                'num_cores': stats['num_cores'],
                'folder_name': app_dir.name
            })
            print(f"Processed {app_dir.name}: IPC={stats['ipc']:.3f}, Time={stats['execution_time_s']:.6f}s")
        else:
            print(f"Failed to process {app_dir.name}")
    
    df = pd.DataFrame(results)
    
    # Sort by app number, then by app_type (serial before parallel)
    if not df.empty and 'app_number' in df.columns:
        # Create a sort key for app_type: serial=0, parallel=1, None=2
        df['_sort_key'] = df['app_type'].map({'serial': 0, 'parallel': 1}).fillna(2)
        df = df.sort_values(['app_number', '_sort_key']).reset_index(drop=True)
        df = df.drop(columns=['_sort_key'])
    
    return df


def main():
    parser = argparse.ArgumentParser(
        description='Aggregate ZSim statistics from multiple application runs'
    )
    parser.add_argument(
        'run_dir',
        type=str,
        help='Path to run directory containing application folders'
    )
    parser.add_argument(
        '-o', '--output',
        type=str,
        default='zsim_stats.csv',
        help='Output CSV file name (default: zsim_stats.csv)'
    )
    parser.add_argument(
        '-f', '--frequency',
        type=float,
        default=2.4,
        help='CPU frequency in GHz (default: 2.4)'
    )
    
    args = parser.parse_args()
    
    print(f"Collecting statistics from: {args.run_dir}")
    print(f"CPU frequency: {args.frequency} GHz")
    
    df = collect_stats(args.run_dir, args.frequency)
    
    if df.empty:
        print("\nNo data collected!")
        return
    
    # Save to CSV
    output_path = Path(args.output)
    df.to_csv(output_path, index=False)
    
    print(f"\n{'='*60}")
    print(f"Results saved to: {output_path}")
    print(f"Total applications processed: {len(df)}")
    print(f"\nSummary statistics:")
    print(f"  Mean IPC: {df['ipc'].mean():.3f}")
    print(f"  Mean execution time: {df['execution_time_s'].mean():.6f} s")
    print(f"\nDataFrame preview:")
    print(df[['app_number', 'app_name', 'app_type', 'ipc', 'execution_time_s']].to_string())


if __name__ == '__main__':
    main()
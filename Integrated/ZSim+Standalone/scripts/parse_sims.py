#!/usr/bin/env python3

import argparse
import h5py
import numpy as np
import pandas as pd
from pathlib import Path
import re


def parse_args():
    parser = argparse.ArgumentParser(
        description='Aggregate ZSim statistics from multiple application runs'
    )
    parser.add_argument(
        'input_dir',
        type=str,
        help='Path to run directory containing application folders'
    )
    parser.add_argument(
        '-o', '--output',
        type=str,
        default='summary_sim_stats.csv',
        help='Output CSV file name (default: summary_sim_stats.csv)'
    )
    parser.add_argument(
        '-f', '--frequency',
        type=float,
        default=2.4,
        help='CPU frequency in GHz (default: 2.4)'
    )
    return parser.parse_args()


def parse_folder_name(folder_name):
    """
    Expected format: ##_<benchmark>_<variant>_<input-size>
    Example: 08_lzw_compression_serial_koala
    
    Returns: (benchmark, input_size, variant)
    """
    name = folder_name.strip()
    
    # Must start with digits_
    m = re.match(r'(?P<prefix>\d+)_', name)
    if not m:
        print(f"[parse] no numeric prefix: {folder_name}")
        return None, None, None
    
    prefix = m.group('prefix')
    rest = name[m.end():]  # Everything after "##_"
    
    parts = rest.split('_')
    
    if len(parts) < 3:
        print(f"[parse] not enough parts in: {folder_name}")
        return None, None, None
    
    # Find variant (should be 'serial' or 'parallel')
    variant_idx = None
    for i, part in enumerate(parts):
        if part.lower() in ('serial', 'parallel'):
            variant_idx = i
            break
    
    if variant_idx is None:
        print(f"[parse] no variant (serial/parallel) found in: {folder_name}")
        return None, None, None
    
    # Everything before variant = benchmark
    benchmark_parts = parts[:variant_idx]
    benchmark = f"{prefix}_{'_'.join(benchmark_parts)}"
    
    # Variant
    variant = parts[variant_idx].lower()
    
    # Everything after variant = input
    input_parts = parts[variant_idx + 1:]
    input_size = '_'.join(input_parts) if input_parts else 'unknown'
    
    return benchmark, input_size, variant


def extract_stats_from_h5(h5_path, freq_ghz):
    """Extract statistics from a single zsim.h5 file."""
    try:
        with h5py.File(h5_path, 'r') as f:
            CORE_CFG_NAME = 'c'
            dset = f["stats"]["root"]
            
            num_samps = len(dset)
            start_idx = int(num_samps * 0.35)
            final_idx = -1 #int(num_samps * 0.90)
            
            print(f'start idx = {start_idx} | final idx = {final_idx}')
            
            if start_idx >= final_idx and not final_idx < 0:
                raise Exception("Number of samples is suspiciously low")
            
            samp_start = dset[start_idx]
            samp_final = dset[final_idx]
            
            print(samp_final[CORE_CFG_NAME]['cycles'])
            print(samp_start[CORE_CFG_NAME]['cycles'])
            
            # Calculate IPC over middle 50% interval
            cycles_interval = samp_final[CORE_CFG_NAME]['cycles'].sum() - samp_start[CORE_CFG_NAME]['cycles'].sum()
            insts_interval = samp_final[CORE_CFG_NAME]['instrs'].sum() - samp_start[CORE_CFG_NAME]['instrs'].sum()

            if cycles_interval > 0:
                ipc = round(insts_interval / cycles_interval, 4)
            else:
                ipc = np.nan
            
            # Total cycles and instructions
            total_cycles = dset[-1][CORE_CFG_NAME]['cycles'].sum()
            total_insts = dset[-1][CORE_CFG_NAME]['instrs'].sum() 
            
            cache_ratios = {}
            
            for cache in ['l1i', 'l1d', 'l2', 'l3']:
                read_hits = samp_final[cache]['hGETS'].sum() - samp_start[cache]['hGETS'].sum()
                read_misses = samp_final[cache]['mGETS'].sum() - samp_start[cache]['mGETS'].sum()
                
                write_hits = samp_final[cache]['hGETX'].sum() - samp_start[cache]['hGETX'].sum()
                write_misses = (samp_final[cache]['mGETXIM'].sum() - samp_start[cache]['mGETXIM'].sum() +
                                samp_final[cache]['mGETXSM'].sum() - samp_start[cache]['mGETXSM'].sum())
                
                cache_hits = read_hits + write_hits
                cache_misses = read_misses + write_misses

                if 'l1' in cache:
                    cache_hits += (samp_final[cache]['fhGETS'].sum() - samp_start[cache]['fhGETS'].sum()) + \
                                (samp_final[cache]['fhGETX'].sum() - samp_start[cache]['fhGETX'].sum())

                # DEBUG
                print(f"\n{cache}:")
                print(f"  read_hits={read_hits}, read_misses={read_misses}")
                print(f"  write_hits={write_hits}, write_misses={write_misses}")
                print(f"  cache_hits={cache_hits}, cache_misses={cache_misses}")

                total_accesses = cache_hits + cache_misses
                if total_accesses > 0:
                    cache_ratios[cache] = round(cache_misses / total_accesses, 2)
                else:
                    cache_ratios[cache] = np.nan
                
            if cache_hits > 0:
                cache_ratios[cache] = round( cache_misses / (cache_hits), 2)
            else:
                cache_ratios[cache] = np.nan
                                
            for key, value in cache_ratios.items():
                print(f"{key}: {value}")
            
            return {
                'instructions': total_insts,
                'cycles': total_cycles,
                'l1i-miss-ratio': cache_ratios['l1i'],
                'l1d-miss-ratio': cache_ratios['l1d'],
                'llc-miss-ratio': cache_ratios['l3'],
                'ipc': ipc,
            }

    except Exception as e:
        print(f"Error reading {h5_path}: {e}")
        import traceback
        traceback.print_exc()
        return None


def extract_time_from_log(log_path):
    EXECUTION_TIME_PATTERN = r"Execution time:\s*(\d+\.?\d*)"
    ROI_START_STRING = "[HOOKS] ROI begin"
    COLUMN_NAME = "exec-time(s)"

    try:

        with open(log_path, 'r', encoding='utf-8', errors='replace') as log_file:
            log_content = log_file.read()

            if ROI_START_STRING not in log_content:
                return {COLUMN_NAME: "Timeout too low"}

            match = re.search(EXECUTION_TIME_PATTERN, log_content)
            
            if match:
                return {COLUMN_NAME: float(match.group(1))}
            else:
                return {COLUMN_NAME: "Sim Time out"}

    except Exception as e:
        print(f"Error reading {log_path}: {e}")
        import traceback
        traceback.print_exc()
        return None


def collect_all_stats(input_dir, freq_ghz):
    """Collect statistics from all application directories."""
    input_path = Path(input_dir)
    
    if not input_path.exists():
        raise FileNotFoundError(f"Directory not found: {input_dir}")
    
    # Find all application directories matching pattern ##_*
    app_dirs = sorted([d for d in input_path.iterdir() 
                      if d.is_dir() and re.match(r'\d+_', d.name)])
    
    if not app_dirs:
        raise Exception(f'No application directories found in {input_dir}')
    
    print(f"\nFound {len(app_dirs)} directories to process\n")
    
    results = []
    
    for app_dir in app_dirs:
        h5_file = app_dir / "zsim.h5"
        log_file = app_dir / "log.txt"
        
        if not h5_file.exists():
            print(f"Warning: {h5_file} not found, skipping {app_dir.name}")
            continue
        
        benchmark, input_size, variant = parse_folder_name(app_dir.name)
        
        if benchmark is None:
            print(f"Skipping {app_dir.name} - could not parse folder name")
            continue
        
        print(f"Processing: {app_dir.name}")
        print(f"  Parsed as: benchmark={benchmark}, variant={variant}, input={input_size}")
        
        stats = extract_stats_from_h5(h5_file, freq_ghz)
        time_stats = extract_time_from_log(log_file)
        
        if stats:
            results.append({
                'benchmark': benchmark,
                'variant': variant,
                'input': input_size,
                **stats,
                **(time_stats if time_stats is not None else {'exec-time(s)': 'ERROR'}),
            })
            print(f"  [OK] IPC: {stats['ipc']}, Instructions: {stats['instructions']}")
        else:
            print(f"  [FAIL] Failed to extract stats")
        
        print()
    
    return pd.DataFrame(results)


def sort_dataframe(df):
    """Sort dataframe by benchmark and variant (serial before parallel)."""
    if df.empty:
        return df
    
    variant_order = {'serial': 0, 'parallel': 1}
    df['variant_sort'] = df['variant'].map(variant_order)
    df = df.sort_values(['benchmark', 'variant_sort', 'input'])
    df = df.drop('variant_sort', axis=1)
    
    return df


def main():
    args = parse_args()
    
    print("=" * 60)
    print("ZSim Statistics Aggregator")
    print("=" * 60)
    print(f"Input directory: {args.input_dir}")
    print(f"CPU frequency: {args.frequency} GHz")
    print(f"Output file: {args.output}")
    print()
    
    df = collect_all_stats(args.input_dir, args.frequency)
    
    if df.empty:
        print("No data collected!")
        return
    
    df = sort_dataframe(df)
    
    # Enforce column ordering
    desired_columns = [
        'benchmark', 'variant', 'input',
        'instructions', 'cycles', 'exec-time(s)','l1i-miss-ratio', 
        'l1d-miss-ratio', 'llc-miss-ratio', 'ipc'
    ]
    
    df = df[desired_columns]
    
    df.to_csv(args.output, index=False)
    
    print("=" * 60)
    print("SUMMARY")
    print("=" * 60)
    print(f"Processed: {len(df)} applications")
    print(f"Output: {args.output}")


if __name__ == '__main__':
    main()
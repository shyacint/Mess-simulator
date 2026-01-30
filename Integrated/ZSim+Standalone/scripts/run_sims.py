#!/usr/bin/env python3

import argparse
import os
import sys
import re
import subprocess

from datetime import datetime


DIR_PATTERN = re.compile(r"^\d{2}_")


def parse_args():
    parser = argparse.ArgumentParser(
        description="Process directories prefixed with ##_ (i.e 01_passgen) and run the series and parallel executables"
    )
    parser.add_argument(
        "--cfg",
        required=True,
        type=str,
        help="ZSim simulation configuration(cfg) file"
    )
    parser.add_argument(
        "--apps-dir",
        required=True,
        help="Workload applications directory to scan"
    )
    parser.add_argument(
        "--dataset",
        required=True,
        help="Comma-separated list of datasets (e.g. koala,panda)"
    )
    parser.add_argument(
        "--variant",
        default="serial,parallel",
        help="Comma-separated list of variants (e.g. serial,parallel)"
    )
    parser.add_argument(
        "--quick-run",
        type=int,
        default=-1,
        help="Set the maximum number of inst to simulate (multiple of 1k inst)"
    )
    parser.add_argument(
        "--apps",
        type=str,
        default=None,
        help="Apps to run. Supports ranges (00-10), lists (01,05,12), or mixed (01-05,08,12-15)"
    )
    parser.add_argument(
        "--max-concurrent",
        type=int,
        default=-1,
        help="Maximum number of concurrent simulations (default: unlimited)"
    )
    return parser.parse_args()


def assert_file_exists(filePath):
    if not os.path.isfile(filePath):
        raise FileNotFoundError(f"File {filePath} does not exist. file=__file__, line={sys._getframe().f_lineno}, function={sys._getframe().f_code.co_name}, caller={sys._getframe().f_back.f_code.co_name}")


def parse_apps(apps_str):
    """
    Parse app specification into a set of app numbers.
    Supports:
    - Ranges: '00-10' 
    - Lists: '01,05,12'
    - Mixed: '01-05,08,12-15'
    
    Returns a set of integers representing app numbers to run, or None if not specified.
    """
    if not apps_str:
        return None
    
    app_numbers = set()
    
    # Split by comma to get individual parts
    parts = apps_str.split(',')
    
    for part in parts:
        part = part.strip()
        if not part:
            continue
            
        # Check if it's a range (contains dash)
        if '-' in part:
            range_parts = part.split('-')
            if len(range_parts) != 2:
                raise ValueError(f"Invalid range format: {part}. Expected format: '00-10'")
            
            try:
                start = int(range_parts[0])
                end = int(range_parts[1])
            except ValueError as e:
                raise ValueError(f"Invalid range values in: {part}") from e
            
            if start > end:
                raise ValueError(f"Invalid range: start ({start}) > end ({end}) in {part}")
            
            if start < 0 or end > 99:
                raise ValueError(f"App numbers must be between 0 and 99: {part}")
            
            # Add all numbers in the range
            app_numbers.update(range(start, end + 1))
        else:
            # Single app number
            try:
                app_num = int(part)
                if app_num < 0 or app_num > 99:
                    raise ValueError(f"App number must be between 0 and 99: {app_num}")
                app_numbers.add(app_num)
            except ValueError as e:
                raise ValueError(f"Invalid app number: {part}") from e
    
    return app_numbers if app_numbers else None


def app_should_run(app_name, app_numbers):
    """Check if app should run based on the parsed app numbers set."""
    if not app_numbers:
        return True
    
    match = DIR_PATTERN.match(app_name)
    if not match:
        return False
    
    app_num = int(app_name[:2])
    return app_num in app_numbers


def create_exe_cmd(dir_path, dataset):
    run_script = os.path.join(dir_path, "run.sh")
    
    if os.path.exists(run_script):
        
        run_script_dict = {}
        # loop through line in run.sh
        with open(run_script, "r") as f:
            for line in f:
                if "=" in line:
                    key, val = [e.strip().replace("'","").replace('"','') for e in line.split("=")]
                    
                    # resolve all file paths
                    resolved_args = []
                    for arg in val.split(" "):
                        full_arg_path = os.path.join(dir_path, arg)
                        
                        if os.path.isfile(full_arg_path) or os.path.isdir(full_arg_path):
                            abs_path = os.path.realpath(full_arg_path)
                            resolved_args.append(abs_path)
                        else:
                            resolved_args.append(arg)
                            
                    # only add the args for the proper dataset requested
                    if key == "BINARY" or dataset in key.lower(): 
                        run_script_dict[key] = resolved_args
                        
        # Combine dict values into executable command string
        binary = run_script_dict.get("BINARY", [])
        args = [arg for key, val in run_script_dict.items() if key != "BINARY" for arg in val]
        return " ".join(binary + args)
    
    return None


def process_directory(dir_path, dataset, variant):
    """Process directory and return executable command."""
    full_path_dir = os.path.join(dir_path, variant)
    exe_cmd = create_exe_cmd(full_path_dir, dataset)
    return exe_cmd
            
def main():
  
    args = parse_args()

    os.chdir("/mnt/ssd/Mess-simulator/Integrated/ZSim+Standalone")
    apps_dir = os.path.abspath(args.apps_dir)

    if not os.path.isdir(apps_dir):
        raise NotADirectoryError(f"{apps_dir} is not a valid directory")

    #TODO: add code that will build all zoo applications
    
    zsim_binary = "build/opt/zsim"
    assert_file_exists(zsim_binary)
    zsim_binary = os.path.realpath(zsim_binary)

    proc_cfg = os.path.basename(args.cfg)
    cfgs_dir = os.path.realpath("tests/")
    date = datetime.now().strftime('%Y%m%d_%H%M%S')
    run_dir = f"runs.{date}"
    os.mkdir(run_dir)
    run_dir = os.path.realpath(run_dir)
    os.chdir(run_dir)
    
    # Parse app specification
    app_numbers = parse_apps(args.apps)
    
    # Clean up and parse comma-separated lists
    datasets = [d.strip() for d in args.dataset.split(",")]
    variants = [v.strip() for v in args.variant.split(",")]
    
    # Print configuration for debugging
    print("=" * 60)
    print("Simulation Configuration:")
    print(f"  Datasets: {datasets}")
    print(f"  Variants: {variants}")
    print(f"  Apps: {args.apps if args.apps else 'All'}")
    print("=" * 60)
    print()
    
    processes = []

    for app in sorted(os.listdir(apps_dir)):
        if not DIR_PATTERN.match(app):
            continue
        
        # Check if this app should run
        if not app_should_run(app, app_numbers):
            continue

        full_path = os.path.join(apps_dir, app)

        if not os.path.isdir(full_path):
            continue

        print(f"Processing {app}...")
        
        for dataset in datasets:
            for variant in variants:
                # Create run name in format: app_variant_dataset
                run_name = f"{app}_{variant}_{dataset}"
                print(f"  Creating run: {run_name}")
                
                # Create absolute path for run directory
                run_path = os.path.join(run_dir, run_name)
                os.makedirs(run_path, exist_ok=True)
                
                cfg_file = f"{cfgs_dir}/{proc_cfg}"
                assert_file_exists(cfg_file)
                
                with open(cfg_file, "r") as f: 
                    config = f.read()
                
                if args.quick_run > 0: 
                    config = config.replace('100000000000L', f'{int(args.quick_run) * 1000}L')
                
                new_cmd = process_directory(full_path, dataset, variant)
                
                if new_cmd is None:
                    print(f"    WARNING: No executable command found for {app}/{variant}")
                    continue
                    
                config = config.replace('<enter command>', f"{new_cmd}")
                
                # Write config to the run directory
                cfg_path = os.path.join(run_path, "run.cfg")
                with open(cfg_path, "w") as f: f.write(config)
                
                # Launch process with explicit cwd
                log_path = os.path.join(run_path, "log.txt")
                process = subprocess.Popen(
                    [zsim_binary, cfg_path], 
                    stdout=open(log_path, "w"), 
                    stderr=subprocess.STDOUT,
                    cwd=run_path
                )
                processes.append((run_name, process))
                
                # Wait for batch if max concurrent limit is set
                if args.max_concurrent > 0 and len(processes) >= args.max_concurrent:
                    print(f"Reached max concurrent limit ({args.max_concurrent}). Waiting for batch to complete...")
                    for run_name, p in processes:
                        p.wait()
                        if p.returncode != 0:
                            print(f"    WARNING: {run_name} failed with return code {p.returncode}")
                    processes = []
                
        print(f"Submitted all runs for {app}.\n")
    
    # Wait for remaining processes
    print(f"Waiting for remaining {len(processes)} processes to complete...")
    for run_name, process in processes:
        process.wait()
        if process.returncode != 0:
            print(f"    WARNING: {run_name} failed with return code {process.returncode}")
        
    print(f"All runs completed!")

if __name__ == "__main__":
    main()
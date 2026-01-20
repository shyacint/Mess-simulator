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
        help="Workload applications directory to scan (default: current working directory)"
    )
    parser.add_argument(
        "--dataset",
        required=True,
        default="koala",
        help="Comma-separated list (e.g. koala,panda)"
    )
    parser.add_argument(
        "--app-type",
        default="serial",
        help="Comma-separated list (e.g. serial,parallel)"
    )
    parser.add_argument(
        "--quick-run",
        type=int,
        default= -1,
        help="Set the maximum number of inst to simulate (multiple of 1k inst)"
    )
    parser.add_argument(
        "--app-range",
        type=str,
        default=None,
        help="Range of apps to run (e.g., '00-10' runs apps 00_ through 10_)"
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


def parse_app_range(range_str):
    if not range_str:
        return None
    
    parts = range_str.split('-')
    if len(parts) != 2:
        raise ValueError(f"Invalid app range format: {range_str}. Expected format: '00-10'")
    
    start = int(parts[0])
    end = int(parts[1])
    
    if start > end:
        raise ValueError(f"Invalid app range: start ({start}) > end ({end})")
    
    return (start, end)


def app_in_range(app_name, app_range):
    if not app_range:
        return True
    
    match = DIR_PATTERN.match(app_name)
    if not match:
        return False
    
    app_num = int(app_name[:2])
    start, end = app_range
    return start <= app_num <= end


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


def process_directory(dir_path, dataset, app_type):
    
    full_path_dir = os.path.join(dir_path, app_type)
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

    cfgs_dir = os.path.realpath("tests/")
    date = datetime.now().strftime('%Y%m%d_%H%M%S')
    run_dir = f"runs.{date}"
    os.mkdir(run_dir)
    run_dir = os.path.realpath(run_dir)
    os.chdir(run_dir)
    
    # Parse app range if provided
    app_range = parse_app_range(args.app_range)
    
    # clean up for the csv
    datasets = args.dataset.split(",")
    app_types = args.app_type.split(",")
    
    processes = []

    for app in sorted(os.listdir(apps_dir)):
        if not DIR_PATTERN.match(app):
            continue
        
        # Skip apps outside the specified range
        if not app_in_range(app, app_range):
            continue

        full_path = os.path.join(apps_dir, app)

        if not os.path.isdir(full_path):
            continue

        print(f"Processing {app}...")
        
        for dataset in datasets:
            for app_type in app_types:
                run_name = f"{app}_{app_type}_{dataset}"
                
                # Create absolute path for run directory
                run_path = os.path.join(run_dir, run_name)
                os.makedirs(run_path, exist_ok=True)
                
                cfg_file = f"{cfgs_dir}/orca_cxl.cfg"
                assert_file_exists(cfg_file)
                
                with open(cfg_file, "r") as f: 
                    config = f.read()
                
                if args.quick_run > 0: 
                    config = config.replace('100000000000L', f'{int(args.quick_run) * 1000}L')
                
                new_cmd = process_directory(full_path, dataset, app_type)
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
                processes.append(process)
                
                # Wait for batch if max concurrent limit is set
                if args.max_concurrent > 0 and len(processes) >= args.max_concurrent:
                    print(f"Reached max concurrent limit ({args.max_concurrent}). Waiting for batch to complete...")
                    for p in processes:
                        p.wait()
                        if p.returncode != 0:
                            print(f"Warning: Process failed with return code {p.returncode}")
                    processes = []
                
        print(f"Submitted all runs for {app}.\n")
    
    # Wait for remaining processes
    print(f"Waiting for remaining {len(processes)} processes to complete...")
    for process in processes:
        process.wait()
        assert process.returncode == 0
        
    print(f"All runs completed successfully!")

if __name__ == "__main__":
    main()
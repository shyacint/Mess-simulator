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
    "--dataset",
    default="koala",
    help="Comma-separated list (e.g. koala,panda)"
    )
    parser.add_argument(
        "--app-type",
        default="serial",
        help="Comma-separated list (e.g. serial,parallel)"
    )
    parser.add_argument(
        "--apps-dir",
        default=os.getcwd(),
        help="Workload applications directory to scan (default: current working directory)"
    )
    parser.add_argument(
        "--quick-run",
        type=int,
        default= -1,
        help="Set the maximum number of inst to simulate (multiple of 1k inst)"
    )
    return parser.parse_args()


def assert_file_exists(filePath):
    if not os.path.isfile(filePath):
        raise FileNotFoundError(f"File {filePath} does not exist. file=__file__, line={sys._getframe().f_lineno}, function={sys._getframe().f_code.co_name}, caller={sys._getframe().f_back.f_code.co_name}")



def create_exe_cmd(dir_path, dataset):
    run_script = os.path.join(dir_path, "run.sh")
    
    if os.path.exists(run_script):
        # print(f"Run Script Path: {run_script}")
        
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
                        print(full_arg_path)
                        
                        if os.path.isfile(full_arg_path) or os.path.isdir(full_arg_path):
                            original_dir =os.getcwd()
                            os.chdir(dir_path)
                            abs_path = os.path.abspath(arg)
                            os.chdir(original_dir)
                            print(abs_path)
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
    
    # clean up for the csv
    datasets = args.dataset.split(",")
    app_types = args.app_type.split(",")
    
    processes = []

    for app in sorted(os.listdir(apps_dir)):
        if not DIR_PATTERN.match(app):
            continue

        full_path = os.path.join(apps_dir, app)

        if not os.path.isdir(full_path):
            continue

        print(full_path)     
        for dataset in datasets:
            for app_type in app_types:
                run_name = f"{app}_{app_type}_{dataset}"
                
                os.makedirs(run_name, exist_ok=True)
                os.chdir(run_name)
                
                cfg_file = f"{cfgs_dir}/orca_cxl.cfg"
                assert_file_exists(cfg_file)
                
                with open(cfg_file, "r") as f: 
                    config = f.read()
                
                if args.quick_run > 0: 
                    config = config.replace('100000000000L', f'{int(args.quick_run) * 1000}L')
                
                new_cmd = process_directory(full_path, dataset, app_type)
                config = config.replace('<enter command>', f"{new_cmd}")
                
                with open("run.cfg", "w") as f: f.write(config)
                
                process = subprocess.Popen([zsim_binary, "run.cfg"], stdout=open("log.txt","w"), stderr=subprocess.STDOUT)
                processes.append(process)
                os.chdir("..")
                
        print(f"Submitted all runs for {app}. Waiting for completion...\n")
        
    for process in processes:
        process.wait()
        assert process.returncode == 0
        
    print(f"All runs completed successfully!")

if __name__ == "__main__":
    main()

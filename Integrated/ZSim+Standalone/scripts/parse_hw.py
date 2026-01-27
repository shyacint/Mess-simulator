#!/usr/bin/env python3

import argparse
import pandas as pd 
import numpy as np

from pathlib import Path


def parse_args():
    parser = argparse.ArgumentParser(
        description='Aggregates perfs counters (mean) collected using the collect_cpu_perf.py in the Zoo benchmark'
    )
    parser.add_argument(
        'input_dir',
        type = str,
        help = 'Directory containing results from the collect_cpu.py script in the Zoo repository'
    )
    parser.add_argument(
        '-o', '--output',
        type=str,
        default='summary_hw_stats.csv',
        help='Output CSV file name (default summary_hw_stats.csv)'
    )
    return parser.parse_args()


def combine_csv_files(csv_files, desired_cols):
    dfs = []
    for csv in csv_files:
        df = pd.read_csv(csv)
        dfs.append(df[desired_cols])
    return pd.concat(dfs, ignore_index=True)


def identify_groupby_columns(df):
    groupby_cols = []
    for col in ['benchmark', 'variant', 'input']:
        if col in df.columns:
            groupby_cols.append(col)
    return groupby_cols


def calc_mean(df, groupby_cols, numeric_cols):
    col_types = {}
    for col in numeric_cols:
        if df[col].dtype in ['int64', 'int32', 'int16', 'int8']:
            col_types[col] = 'int'
        else:
            col_types[col] = 'float'
            
    mean_df = df.groupby(groupby_cols)[numeric_cols].mean().reset_index()
    for col in numeric_cols:
        if col_types[col] == 'int':
            mean_df[col] = np.ceil(mean_df[col]).astype('int')
        else:
            mean_df[col] = mean_df[col].round(2)
    return mean_df


def calc_l1_ratio(df):
    total_misses = 0
    total_accesses = 0

    # dcache
    if 'L1-dcache-load-misses' in df.columns and  'L1-dcache-loads' in df.columns:
        total_misses += df['L1-dcache-load-misses']
        total_accesses += df['L1-dcache-loads']
        
    if 'L1-dcache-store-misses' in df.columns and  'L1-dcache-stores' in df.columns:
        total_misses += df['L1-dcache-store-misses']
        total_accesses += df['L1-dcache-stores']
        
    # icache
    if  'L1-icache-loads'in df.columns and 'L1-icache-load-misses' in df.columns:
        total_misses +=  df['L1-icache-load-misses']
        total_accesses += df['L1-icache-loads']
        
    df['L1-miss-ratio'] = (total_misses / total_accesses)
    
    return df


COLUMNS_TO_AGGREGATE = [
            'benchmark', 'variant', 'input','instructions', 'cache-references',  
            'L1-dcache-loads', 'L1-dcache-load-misses', 'L1-dcache-stores', 
            'L1-dcache-store-misses', 'L1-icache-loads', 'L1-icache-load-misses', 
            'LLC-miss-ratio', 'ipc'
        ] #None 

FINAL_COLUMNS_TO_REMOVE = [
            'L1-dcache-loads', 'L1-dcache-load-misses', 'L1-dcache-stores', 
            'L1-dcache-store-misses', 'L1-icache-loads', 'L1-icache-load-misses',  
        ]

FINAL_ORDERING = [
            'benchmark', 'variant', 'input','instructions', 'cache-references', 'L1-miss-ratio', 'LLC-miss-ratio', 'ipc'
        ]


def main():   
    
    args = parse_args()
       
    cpu_csv_files = [file for file in Path(args.input_dir).glob('*.csv') if file.name.startswith('cpu_')]
    if not cpu_csv_files:
        raise Exception(f'No cpu_*.csv files found in {args.input_dir}')
    
    total_csv_files = len(cpu_csv_files)

    combined_df = combine_csv_files(cpu_csv_files, COLUMNS_TO_AGGREGATE)
    groupby_cols = identify_groupby_columns(combined_df)
    
    numeric_cols = combined_df.select_dtypes(include='number').columns.tolist()
    
    mean_df = calc_mean(combined_df, groupby_cols, numeric_cols)
    mean_df = calc_l1_ratio(mean_df)
    
    mean_df['L1-miss-ratio'] =  (mean_df['L1-miss-ratio'] * 100).round(2)
    mean_df['LLC-miss-ratio'] = (mean_df['LLC-miss-ratio'] * 100).round(2)
    
    cleaned_df =  mean_df.drop(columns=FINAL_COLUMNS_TO_REMOVE)
    sorted_df = cleaned_df.sort_values(by=['benchmark', 'variant', 'input'], ascending=[True, False, True])
    final_df = sorted_df.reindex(columns=FINAL_ORDERING)
    
    final_df.to_csv(args.output, index=False)
    print(final_df)

if __name__ == '__main__':
    main()
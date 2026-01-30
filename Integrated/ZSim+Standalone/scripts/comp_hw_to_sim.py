#!/usr/bin/env python3
"""
Compare hardware and simulation metrics from CSV files.
Calculate percent differences and generate comparison CSV.
"""

import argparse
import pandas as pd
import sys


def parse_args():
    parser = argparse.ArgumentParser(
        description="Compare hardware and simulation metrics"
    )
    parser.add_argument('--hardware', '-hw', required=True,
                       help='Hardware results CSV')
    parser.add_argument('--simulation', '-sim', required=True,
                       help='Simulation results CSV')
    parser.add_argument('--output', '-o', default='comparison.csv',
                       help='Output CSV (default: comparison.csv)')
    
    return parser.parse_args()


def load_csv(filepath):
    """Load CSV file."""
    try:
        df = pd.read_csv(filepath)
        print(f"Loaded {filepath}: {len(df)} rows, {len(df.columns)} columns")
        return df
    except Exception as e:
        print(f"Error loading {filepath}: {e}")
        sys.exit(1)


def calculate_percent_diff(hw_val, sim_val):
    """Calculate percent difference: ((sim - hw) / hw) * 100"""
    if pd.isna(hw_val) or pd.isna(sim_val) or hw_val == 0:
        return None
    return ((sim_val - hw_val) / hw_val) * 100


def compare_metrics(hw_df, sim_df):
    """
    Compare hardware and simulation metrics.
    Merges on benchmark, variant, input and calculates percent differences.
    """
    # Key columns for merging
    key_cols = ['benchmark', 'variant', 'input']
    
    # Find common metric columns (exclude keys)
    hw_metrics = set(hw_df.columns) - set(key_cols)
    sim_metrics = set(sim_df.columns) - set(key_cols)
    common_metrics = sorted(list(hw_metrics & sim_metrics))
    
    print(f"\nComparing metrics: {common_metrics}")
    
    # Merge on key columns
    result = pd.merge(
        hw_df[key_cols + common_metrics],
        sim_df[key_cols + common_metrics],
        on=key_cols,
        how='inner',
        suffixes=('_hw', '_sim')
    )
    
    print(f"Matched {len(result)} rows")
    
    # Calculate percent differences for each metric
    for metric in common_metrics:
        hw_col = f"{metric}_hw"
        sim_col = f"{metric}_sim"
        diff_col = f"{metric}_diff_%"
        
        result[diff_col] = result.apply(
            lambda row: calculate_percent_diff(row[hw_col], row[sim_col]),
            axis=1
        )
    
    return result


def print_summary(df, metrics):
    """Print summary statistics."""
    print("\n" + "="*60)
    print("SUMMARY")
    print("="*60)
    
    for metric in metrics:
        diff_col = f"{metric}_diff_%"
        valid = df[diff_col].dropna()
        
        if len(valid) > 0:
            mean_abs = valid.abs().mean()
            max_abs = valid.abs().max()
            acceptable = (valid.abs() <= 20).sum()
            total = len(valid)
            
            print(f"\n{metric}:")
            print(f"  ≤20%: {acceptable}/{total} ({100*acceptable/total:.1f}%)")


def main():

    args = parse_args()
    
    # Load CSVs
    hw_df = load_csv(args.hardware)
    sim_df = load_csv(args.simulation)
    
    # Compare
    result = compare_metrics(hw_df, sim_df)
    
    # Save
    result.to_csv(args.output, index=False)
    print(f"\nSaved: {args.output}")
    
    # Summary
    key_cols = ['benchmark', 'variant', 'input']
    metrics = sorted([c.replace('_hw', '') for c in result.columns 
                     if c.endswith('_hw')])
    print_summary(result, metrics)


if __name__ == "__main__":
    main()
#!/usr/bin/env python3
import argparse
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.ticker as ticker
import numpy as np

def load_csv(path, label):
    df = pd.read_csv(path)
    df['source'] = label
    # Coerce exec-time to numeric, anything non-numeric becomes NaN
    df['exec-time(s)'] = pd.to_numeric(df['exec-time(s)'], errors='coerce')
    return df

def plot_variant(ax, df1, df2, label1, label2, variant, color1, color2):
    v1_all = df1[df1['variant'] == variant][['benchmark', 'exec-time(s)']]
    v2_all = df2[df2['variant'] == variant][['benchmark', 'exec-time(s)']]

    all_benchmarks = sorted(set(v1_all['benchmark']) | set(v2_all['benchmark']))

    skipped = []
    common = []
    for b in all_benchmarks:
        r1 = v1_all[v1_all['benchmark'] == b]
        r2 = v2_all[v2_all['benchmark'] == b]

        missing1 = r1.empty or pd.isna(r1['exec-time(s)'].values[0]) if not r1.empty else True
        missing2 = r2.empty or pd.isna(r2['exec-time(s)'].values[0]) if not r2.empty else True

        reasons = []
        if r1.empty:
            reasons.append(f'{label1}: not in CSV')
        elif pd.isna(r1['exec-time(s)'].values[0]):
            reasons.append(f'{label1}: exec-time is NaN/Timeout')

        if r2.empty:
            reasons.append(f'{label2}: not in CSV')
        elif pd.isna(r2['exec-time(s)'].values[0]):
            reasons.append(f'{label2}: exec-time is NaN/Timeout')

        if reasons:
            skipped.append((b, variant, ', '.join(reasons)))
        else:
            common.append(b)

    if skipped:
        print(f"\n[{variant.upper()}] Skipped benchmarks:")
        for b, v, reason in skipped:
            print(f"  {b}: {reason}")

    if not common:
        ax.set_visible(False)
        return

    v1 = v1_all.set_index('benchmark').loc[common]
    v2 = v2_all.set_index('benchmark').loc[common]

    x = np.arange(len(common))
    width = 0.35

    ax.bar(x - width/2, v1['exec-time(s)'], width, label=label1, color=color1, alpha=0.85, edgecolor='black', linewidth=0.5)
    ax.bar(x + width/2, v2['exec-time(s)'], width, label=label2, color=color2, alpha=0.85, edgecolor='black', linewidth=0.5)

    ax.set_xticks(x)
    ax.set_xticklabels(common, rotation=45, ha='right', fontsize=8)
    ax.set_ylabel('Execution Time (s)', fontsize=10)
    ax.set_title(f'{variant.capitalize()} — Execution Time by Benchmark', fontsize=12, fontweight='bold')
    ax.legend(fontsize=9)
    ax.set_yscale('log')
    ax.yaxis.set_major_formatter(ticker.FuncFormatter(lambda x, _: f'{x:,.1f}'))
    ax.grid(axis='y', linestyle='--', alpha=0.4)
    ax.set_axisbelow(True)

def main():
    parser = argparse.ArgumentParser(description='Plot execution time: serial vs parallel, two CSVs overlapped.')
    parser.add_argument('csv1', help='First CSV file (e.g. DDR4)')
    parser.add_argument('csv2', help='Second CSV file (e.g. CXL)')
    parser.add_argument('--label1', default='DDR4', help='Legend label for csv1')
    parser.add_argument('--label2', default='CXL',  help='Legend label for csv2')
    parser.add_argument('--output', default='exec_time_comparison.png', help='Output image filename')
    args = parser.parse_args()

    df1 = load_csv(args.csv1, args.label1)
    df2 = load_csv(args.csv2, args.label2)

    fig, (ax_serial, ax_parallel) = plt.subplots(2, 1, figsize=(18, 12))
    fig.suptitle(f'Execution Time: {args.label1} vs {args.label2}', fontsize=14, fontweight='bold', y=1.01)

    plot_variant(ax_serial,   df1, df2, args.label1, args.label2, 'serial',   '#2196F3', '#FF5722')
    plot_variant(ax_parallel, df1, df2, args.label1, args.label2, 'parallel', '#2196F3', '#FF5722')

    plt.tight_layout()
    plt.savefig(args.output, dpi=150, bbox_inches='tight')
    print(f"Saved to {args.output}")

if __name__ == '__main__':
    main()
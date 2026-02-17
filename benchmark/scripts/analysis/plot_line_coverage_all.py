#!/usr/bin/env python3
"""
Generate line coverage (count) plots for all protocols with results.
Each protocol gets its own subplot.
"""

import pandas as pd
import matplotlib.pyplot as plt
from pathlib import Path
import numpy as np
import warnings
from datetime import datetime
warnings.filterwarnings('ignore')

# Protocol information mapping
PROTOCOLS = {
    'exim': 'SMTP (Exim)',
    'lighttpd1': 'HTTP (Lighttpd1)',
    'pure-ftpd': 'FTP (Pure-FTPd)',
    'proftpd': 'FTP (ProFTPd)',
    'live555': 'RTSP (Live555)',
    'forked-daapd': 'DAAP (Forked-daapd)',
    'kamailio': 'SIP (Kamailio)',
    'lightftp': 'FTP (LightFTP)',
    'bftpd': 'FTP (BFTPd)'
}

FUZZERS = ['aflnet', 'chatafl', 'xpgfuzz', 'aflnet+s1']
FUZZER_COLORS = {
    'aflnet': '#3498db',
    'chatafl': '#e74c3c',
    'xpgfuzz': '#2ecc71',
    'aflnet+s1': '#9b59b6'
}

FUZZER_LABELS = {
    'aflnet': 'AFLNet',
    'chatafl': 'chatafl',
    'xpgfuzz': 'XPGfuzz',
    'aflnet+s1': 'aflnet+s1'
}


def find_protocols_with_results(benchmark_dir):
    """Find all protocols that have results.csv files."""
    benchmark_path = Path(benchmark_dir)
    protocols_found = []
    
    # First, try to find all results-* directories
    result_dirs = list(benchmark_path.glob("results-*"))
    
    if not result_dirs:
        print(f"Warning: No results-* directories found in {benchmark_path}")
        return []
    
    # Extract protocol names from directory names
    found_protocols = set()
    for result_dir in result_dirs:
        protocol = result_dir.name.replace("results-", "")
        found_protocols.add(protocol)
    
    # Check each found protocol for results.csv
    for protocol in sorted(found_protocols):
        result_dir = benchmark_path / f"results-{protocol}"
        results_file = result_dir / "results.csv"
        
        if results_file.exists():
            protocols_found.append(protocol)
            print(f"✓ Found results for: {protocol}")
        else:
            print(f"✗ No results.csv found for: {protocol} (directory exists)")
    
    # Also check protocols in PROTOCOLS dict
    for protocol in PROTOCOLS.keys():
        if protocol not in found_protocols:
            result_dir = benchmark_path / f"results-{protocol}"
            results_file = result_dir / "results.csv"
            if results_file.exists():
                if protocol not in protocols_found:
                    protocols_found.append(protocol)
                    print(f"✓ Found results for: {protocol}")
    
    return protocols_found


def load_coverage_data(benchmark_dir, protocol):
    """Load line coverage data for a protocol."""
    benchmark_path = Path(benchmark_dir)
    results_file = benchmark_path / f"results-{protocol}" / "results.csv"
    
    if not results_file.exists():
        return None
    
    df = pd.read_csv(results_file)
    
    # Filter for line coverage absolute values
    df_line = df[df['cov_type'] == 'l_abs'].copy()
    
    if df_line.empty:
        return None
    
    return df_line


def calculate_coverage_over_time(df, time_limit=1440, step=10):
    """Calculate average line coverage over time for each fuzzer."""
    coverage_data = {}
    
    for fuzzer in FUZZERS:
        fuzzer_data = df[df['fuzzer'] == fuzzer]
        if fuzzer_data.empty:
            continue
        
        runs = fuzzer_data['run'].unique()
        time_points = []
        coverage_values = []
        coverage_stds = []
        
        # Always include time=0 (starting point)
        values_at_time_0 = []
        for run in runs:
            run_data = fuzzer_data[fuzzer_data['run'] == run]
            if run_data.empty:
                continue
            # Get initial coverage value (first data point)
            values_at_time_0.append(run_data.iloc[0]['cov'])
        
        if values_at_time_0:
            time_points.append(0)
            coverage_values.append(np.mean(values_at_time_0))
            coverage_stds.append(np.std(values_at_time_0))
        
        # Process other time points
        for time_min in range(step, time_limit + 1, step):
            values_at_time = []
            
            for run in runs:
                run_data = fuzzer_data[fuzzer_data['run'] == run]
                if run_data.empty:
                    continue
                
                # Get start time for this run
                start_time = run_data.iloc[0]['time']
                target_time = start_time + time_min * 60
                
                # Get coverage at or before target time
                time_filtered = run_data[run_data['time'] <= target_time]
                if not time_filtered.empty:
                    values_at_time.append(time_filtered['cov'].iloc[-1])
            
            if values_at_time:
                time_points.append(time_min)
                coverage_values.append(np.mean(values_at_time))
                coverage_stds.append(np.std(values_at_time))
        
        if time_points:
            coverage_data[fuzzer] = {
                'time': time_points,
                'coverage': coverage_values,
                'std': coverage_stds
            }
    
    return coverage_data


def plot_line_coverage_all(benchmark_dir, output_file=None, 
                            time_limit=1440, step=30):
    """Generate line coverage plots for all protocols."""
    
    # Find protocols with results
    protocols = find_protocols_with_results(benchmark_dir)
    
    if not protocols:
        print("\n" + "="*80)
        print("ERROR: No protocols with results found!")
        print("="*80)
        print("\nTo generate results.csv files, you need to:")
        print("1. Extract tar files from fuzzing runs")
        print("2. Run profuzzbench_generate_csv.sh for each protocol")
        print("\nExample:")
        print("  cd benchmark/results-proftpd")
        print("  profuzzbench_generate_csv.sh proftpd <NUM_RUNS> aflnet results.csv 0 states.csv")
        print("  profuzzbench_generate_csv.sh proftpd <NUM_RUNS> chatafl results.csv 1 states.csv")
        print("  profuzzbench_generate_csv.sh proftpd <NUM_RUNS> xpgfuzz results.csv 1 states.csv")
        print("\nThen run this script again.")
        return
    
    # Generate output filename with date and time if not provided
    if output_file is None:
        now = datetime.now()
        date_str = now.strftime("%m月-%d_%H-%M-%S")
        output_file = f'line_coverage_all_protocols_{date_str}.png'
    
    # Calculate number of rows and columns for subplots
    n_protocols = len(protocols)
    n_cols = 3
    n_rows = (n_protocols + n_cols - 1) // n_cols
    
    # Create figure
    fig, axes = plt.subplots(n_rows, n_cols, figsize=(18, 5*n_rows))
    fig.suptitle('Line Coverage (Count) Over Time - All Protocols', 
                 fontsize=16, fontweight='bold')
    
    # Font sizes matching profuzzbench style
    fontsize_xy = 16
    legend_fontsize = 16
    tick_fontsize = 14
    
    # Handle single row case
    if n_rows == 1:
        axes = axes.reshape(1, -1)
    elif n_protocols == 1:
        axes = np.array([[axes]])
    
    # Plot each protocol
    for idx, protocol in enumerate(protocols):
        row = idx // n_cols
        col = idx % n_cols
        ax = axes[row, col]
        
        # Load data
        df = load_coverage_data(benchmark_dir, protocol)
        if df is None:
            ax.text(0.5, 0.5, f'No data for {protocol}', 
                   ha='center', va='center', transform=ax.transAxes)
            ax.set_title(PROTOCOLS.get(protocol, protocol), fontsize=12, fontweight='bold')
            continue
        
        # Calculate coverage over time
        coverage_data = calculate_coverage_over_time(df, time_limit, step)
        
        if not coverage_data:
            ax.text(0.5, 0.5, f'No coverage data for {protocol}', 
                   ha='center', va='center', transform=ax.transAxes)
            ax.set_title(PROTOCOLS.get(protocol, protocol), fontsize=12, fontweight='bold')
            continue
        
        # Plot each fuzzer
        for fuzzer in FUZZERS:
            if fuzzer in coverage_data:
                data = coverage_data[fuzzer]
                ax.plot(data['time'], data['coverage'], 
                       label=FUZZER_LABELS.get(fuzzer, fuzzer),
                       color=FUZZER_COLORS.get(fuzzer, '#95a5a6'),
                       linewidth=2)
        
        # Customize subplot - matching profuzzbench style
        ax.set_xlabel('Time (in min)', fontsize=fontsize_xy)
        ax.set_ylabel('Line Coverage (Count)', fontsize=fontsize_xy)
        ax.set_title(PROTOCOLS.get(protocol, protocol), fontsize=12, fontweight='bold')
        ax.tick_params(axis='both', labelsize=tick_fontsize)
        # Get fuzzer labels for legend
        fuzzer_labels = [FUZZER_LABELS.get(f, f) for f in FUZZERS if f in coverage_data]
        ax.legend(fuzzer_labels, loc='lower right', fontsize=legend_fontsize)
        ax.grid()
        ax.set_ylim([0, None])
    
    # Hide unused subplots
    for idx in range(n_protocols, n_rows * n_cols):
        row = idx // n_cols
        col = idx % n_cols
        axes[row, col].axis('off')
    
    plt.tight_layout()
    
    # Save figure
    output_path = Path(benchmark_dir) / output_file
    plt.savefig(output_path, dpi=300, bbox_inches='tight')
    print(f"\nPlot saved to: {output_path}")
    plt.close()


def main():
    import sys
    
    # Default to benchmark directory
    if len(sys.argv) > 1:
        benchmark_dir = sys.argv[1]
    else:
        # Try to find benchmark directory
        script_dir = Path(__file__).parent
        benchmark_dir = script_dir.parent.parent
    
    print(f"Analyzing benchmark directory: {benchmark_dir}")
    print("="*80)
    
    plot_line_coverage_all(benchmark_dir)
    
    print("\n" + "="*80)
    print("Analysis complete!")


if __name__ == '__main__':
    main()


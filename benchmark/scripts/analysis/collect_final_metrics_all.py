#!/usr/bin/env python3
"""
Collect final coverage metrics for all fuzzers across all protocols.
Generates a comprehensive summary table with:
- Branch coverage (count and percentage)
- Line coverage (count and percentage)
- State coverage (nodes count)
- State transition coverage (edges count)
"""

import pandas as pd
import numpy as np
from pathlib import Path
from datetime import datetime
import warnings
warnings.filterwarnings('ignore')

# Protocol information mapping
PROTOCOLS = {
    'exim': 'Exim（SMTP）',
    'forked-daapd': 'Forked-daapd（DAAP）',
    'kamailio': 'Kamailio（SIP）',
    'lighttpd1': 'Lighttpd1（HTTP）',
    'live555': 'Live555（RTSP）',
    'bftpd': 'BFTPd（FTP）',
    'lightftp': 'LightFTP（FTP）',
    'pure-ftpd': 'PureFTPd（FTP）',
    'proftpd': 'ProFTPd（FTP）',
}

FUZZERS = ['aflnet', 'chatafl', 'xpgfuzz']


def find_protocols_with_data(benchmark_dir):
    """Find all protocols that have results.csv or states.csv files."""
    benchmark_path = Path(benchmark_dir)
    protocols_found = set()
    
    # Find all results-* directories
    result_dirs = list(benchmark_path.glob("results-*"))
    
    for result_dir in result_dirs:
        protocol = result_dir.name.replace("results-", "")
        results_file = result_dir / "results.csv"
        states_file = result_dir / "states.csv"
        
        if results_file.exists() or states_file.exists():
            protocols_found.add(protocol)
    
    return sorted(protocols_found)


def get_final_coverage_metrics(benchmark_dir, protocol):
    """Get final coverage metrics for a protocol."""
    benchmark_path = Path(benchmark_dir)
    results_file = benchmark_path / f"results-{protocol}" / "results.csv"
    
    if not results_file.exists():
        return None
    
    df = pd.read_csv(results_file)
    metrics = {}
    
    for fuzzer in FUZZERS:
        fuzzer_data = df[df['fuzzer'] == fuzzer]
        if fuzzer_data.empty:
            continue
        
        # Get unique runs
        runs = fuzzer_data['run'].unique()
        fuzzer_metrics = {}
        
        # For each coverage type, get final value from each run and calculate mean
        for cov_type in ['l_per', 'b_per', 'l_abs', 'b_abs']:
            values = []
            for run in runs:
                run_data = fuzzer_data[(fuzzer_data['run'] == run) & 
                                       (fuzzer_data['cov_type'] == cov_type)]
                if not run_data.empty:
                    # Get the final (maximum) value for this run
                    final_value = run_data['cov'].iloc[-1]
                    values.append(final_value)
            
            if values:
                fuzzer_metrics[cov_type] = {
                    'mean': np.mean(values),
                    'std': np.std(values) if len(values) > 1 else 0.0
                }
        
        if fuzzer_metrics:
            metrics[fuzzer] = fuzzer_metrics
    
    return metrics


def get_final_state_metrics(benchmark_dir, protocol):
    """Get final state metrics for a protocol."""
    benchmark_path = Path(benchmark_dir)
    states_file = benchmark_path / f"results-{protocol}" / "states.csv"
    
    if not states_file.exists():
        return None
    
    df = pd.read_csv(states_file)
    metrics = {}
    
    for fuzzer in FUZZERS:
        fuzzer_data = df[df['fuzzer'] == fuzzer]
        if fuzzer_data.empty:
            continue
        
        # Get unique runs
        runs = fuzzer_data['run'].unique()
        fuzzer_metrics = {}
        
        # For each state type (nodes, edges), get final value from each run
        for state_type in ['nodes', 'edges']:
            values = []
            for run in runs:
                run_data = fuzzer_data[(fuzzer_data['run'] == run) & 
                                       (fuzzer_data['state_type'] == state_type)]
                if not run_data.empty:
                    # Get the final (maximum) value for this run
                    final_value = run_data['state'].iloc[-1]
                    values.append(final_value)
            
            if values:
                fuzzer_metrics[state_type] = {
                    'mean': np.mean(values),
                    'std': np.std(values) if len(values) > 1 else 0.0
                }
        
        if fuzzer_metrics:
            metrics[fuzzer] = fuzzer_metrics
    
    return metrics


def collect_all_metrics(benchmark_dir, output_file=None):
    """Collect final metrics for all protocols and fuzzers."""
    
    print("="*80)
    print("Collecting Final Coverage Metrics for All Protocols")
    print("="*80)
    
    # Find protocols with data
    protocols = find_protocols_with_data(benchmark_dir)
    
    if not protocols:
        print("\nERROR: No protocols with data found!")
        print("Make sure results.csv and/or states.csv files exist in results-* directories.")
        return None
    
    print(f"\nFound {len(protocols)} protocols: {', '.join(protocols)}\n")
    
    # Collect all metrics
    all_data = []
    
    for protocol in protocols:
        protocol_name = PROTOCOLS.get(protocol, protocol)
        print(f"Processing {protocol} ({protocol_name})...")
        
        # Get coverage metrics
        cov_metrics = get_final_coverage_metrics(benchmark_dir, protocol)
        
        # Get state metrics
        state_metrics = get_final_state_metrics(benchmark_dir, protocol)
        
        # Create a row for each fuzzer
        for fuzzer in FUZZERS:
            row = {
                'Protocol': protocol_name,
                'Protocol_Code': protocol,
                'Fuzzer': fuzzer.upper()
            }
            
            # Add coverage metrics
            if cov_metrics and fuzzer in cov_metrics:
                metrics = cov_metrics[fuzzer]
                
                # Branch coverage (count and percentage)
                if 'b_abs' in metrics:
                    row['Branch_Coverage_Count'] = f"{metrics['b_abs']['mean']:.1f}"
                else:
                    row['Branch_Coverage_Count'] = 'N/A'
                
                if 'b_per' in metrics:
                    row['Branch_Coverage_Percent'] = f"{metrics['b_per']['mean']:.2f}%"
                else:
                    row['Branch_Coverage_Percent'] = 'N/A'
                
                # Line coverage (count and percentage)
                if 'l_abs' in metrics:
                    row['Line_Coverage_Count'] = f"{metrics['l_abs']['mean']:.1f}"
                else:
                    row['Line_Coverage_Count'] = 'N/A'
                
                if 'l_per' in metrics:
                    row['Line_Coverage_Percent'] = f"{metrics['l_per']['mean']:.2f}%"
                else:
                    row['Line_Coverage_Percent'] = 'N/A'
            else:
                row['Branch_Coverage_Count'] = 'N/A'
                row['Branch_Coverage_Percent'] = 'N/A'
                row['Line_Coverage_Count'] = 'N/A'
                row['Line_Coverage_Percent'] = 'N/A'
            
            # Add state metrics
            if state_metrics and fuzzer in state_metrics:
                metrics = state_metrics[fuzzer]
                
                if 'nodes' in metrics:
                    row['State_Count'] = f"{metrics['nodes']['mean']:.1f}"
                else:
                    row['State_Count'] = 'N/A'
                
                if 'edges' in metrics:
                    row['State_Transition_Count'] = f"{metrics['edges']['mean']:.1f}"
                else:
                    row['State_Transition_Count'] = 'N/A'
            else:
                row['State_Count'] = 'N/A'
                row['State_Transition_Count'] = 'N/A'
            
            all_data.append(row)
    
    # Create DataFrame
    df_summary = pd.DataFrame(all_data)
    
    # Generate output filename with date and time if not provided
    if output_file is None:
        now = datetime.now()
        date_str = now.strftime("%m月-%d_%H-%M-%S")
        output_file = f'final_metrics_all_protocols_{date_str}.csv'
    
    # Save to CSV
    output_path = Path(benchmark_dir) / output_file
    df_summary.to_csv(output_path, index=False)
    
    print("\n" + "="*80)
    print("SUMMARY")
    print("="*80)
    print(f"\nTotal protocols: {len(protocols)}")
    print(f"Total fuzzers: {len(FUZZERS)}")
    print(f"Total rows: {len(df_summary)}")
    print(f"\nResults saved to: {output_path}")
    print("\n" + "="*80)
    
    # Print formatted table
    print("\nFinal Metrics Summary:")
    print("="*140)
    pd.set_option('display.max_columns', None)
    pd.set_option('display.width', None)
    pd.set_option('display.max_colwidth', 20)
    print(df_summary.to_string(index=False))
    print("="*140)
    
    # Print summary statistics by fuzzer
    print("\n\nSummary Statistics by Fuzzer:")
    print("="*140)
    
    for fuzzer in FUZZERS:
        fuzzer_data = df_summary[df_summary['Fuzzer'] == fuzzer.upper()]
        if fuzzer_data.empty or fuzzer_data['Branch_Coverage_Count'].eq('N/A').all():
            continue
        
        print(f"\n{fuzzer.upper()}:")
        print("-" * 140)
        
        # Count protocols with data
        protocols_with_data = fuzzer_data[fuzzer_data['Branch_Coverage_Count'] != 'N/A']
        print(f"  Protocols with data: {len(protocols_with_data)}/{len(protocols)}")
        
        # Calculate averages (only for numeric values)
        numeric_cols = ['Branch_Coverage_Count', 'Line_Coverage_Count', 'State_Count', 'State_Transition_Count']
        for col in numeric_cols:
            numeric_data = pd.to_numeric(fuzzer_data[col], errors='coerce')
            valid_data = numeric_data.dropna()
            if len(valid_data) > 0:
                print(f"  Average {col.replace('_', ' ')}: {valid_data.mean():.1f} (range: {valid_data.min():.1f} - {valid_data.max():.1f})")
    
    print("\n" + "="*140)
    
    return df_summary


def main():
    import sys
    
    # Default to benchmark directory
    if len(sys.argv) > 1:
        benchmark_dir = sys.argv[1]
    else:
        # Try to find benchmark directory
        script_dir = Path(__file__).parent
        benchmark_dir = script_dir.parent.parent
    
    collect_all_metrics(benchmark_dir)


if __name__ == '__main__':
    main()


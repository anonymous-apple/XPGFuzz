#!/usr/bin/env python3
"""
Calculate A12 effect size and Speed-up metrics for XPGFuzz compared to baselines.
Generates two CSV files:
1. a12_statistics.csv
2. speedup_statistics.csv
"""

import pandas as pd
import numpy as np
from pathlib import Path
import bisect
import warnings
warnings.filterwarnings('ignore')

# Protocol mapping
PROTOCOLS = {
    'exim': 'Exim',
    'forked-daapd': 'Forked-daapd',
    'kamailio': 'Kamailio',
    'lighttpd1': 'Lighttpd1',
    'live555': 'Live555',
    'bftpd': 'BFTPd',
    'lightftp': 'LightFTP',
    'pure-ftpd': 'Pure-FTPd',
    'proftpd': 'ProFTPd',
}

FUZZERS = ['aflnet', 'chatafl', 'xpgfuzz']
TARGET_FUZZER = 'xpgfuzz'
BASELINES = ['aflnet', 'chatafl']

METRICS = {
    'Branch': {'file': 'results.csv', 'type_col': 'cov_type', 'val_col': 'cov', 'type_val': 'b_abs'},
    'Line': {'file': 'results.csv', 'type_col': 'cov_type', 'val_col': 'cov', 'type_val': 'l_abs'},
    'State': {'file': 'states.csv', 'type_col': 'state_type', 'val_col': 'state', 'type_val': 'nodes'},
    'Transition': {'file': 'states.csv', 'type_col': 'state_type', 'val_col': 'state', 'type_val': 'edges'},
}

def measure_a12(list1, list2):
    """
    Calculate Vargha-Delaney A12 effect size.
    A12 > 0.5 means list1 is likely larger than list2.
    """
    m = len(list1)
    n = len(list2)
    if m == 0 or n == 0:
        return None
    
    more = 0
    same = 0
    
    for x in list1:
        for y in list2:
            if x > y:
                more += 1
            elif x == y:
                same += 1
    
    return (more + 0.5 * same) / (m * n)

def find_protocols(benchmark_dir):
    path = Path(benchmark_dir)
    protocols = set()
    for p in path.glob("results-*"):
        name = p.name.replace("results-", "")
        if (p / "results.csv").exists() or (p / "states.csv").exists():
            protocols.add(name)
    return sorted(list(protocols))

def load_data(benchmark_dir, protocol, metric_info):
    file_path = Path(benchmark_dir) / f"results-{protocol}" / metric_info['file']
    if not file_path.exists():
        return None
    
    df = pd.read_csv(file_path)
    # Filter specific metric type
    df = df[df[metric_info['type_col']] == metric_info['type_val']]
    return df

def get_final_values(df, fuzzer):
    fuzzer_data = df[df['fuzzer'] == fuzzer]
    if fuzzer_data.empty:
        return []
    
    final_values = []
    for run in fuzzer_data['run'].unique():
        run_data = fuzzer_data[fuzzer_data['run'] == run]
        if not run_data.empty:
            final_values.append(run_data[METRICS['Branch']['val_col'] if 'cov' in run_data.columns else 'state'].iloc[-1])
    return final_values

def calculate_time_to_coverage(df, fuzzer, target_cov):
    """
    Calculate the time (in minutes) it takes for a fuzzer to reach a target coverage.
    Returns a list of times for each run. If a run doesn't reach the target, use max time (or None).
    Here we use the logic: if not reached, we can't calculate speedup for that run based on that target.
    But for "Speedup" metric in papers, it's usually: Time_Baseline / Time_Target.
    We will calculate the average time to reach the target coverage.
    """
    fuzzer_data = df[df['fuzzer'] == fuzzer]
    if fuzzer_data.empty:
        return []

    times = []
    for run in fuzzer_data['run'].unique():
        run_data = fuzzer_data[fuzzer_data['run'] == run].sort_values('time')
        if run_data.empty:
            continue
            
        start_time = run_data.iloc[0]['time']
        
        # Check if it ever reaches target
        reached_data = run_data[run_data[METRICS['Branch']['val_col'] if 'cov' in run_data.columns else 'state'] >= target_cov]
        
        if not reached_data.empty:
            reach_time = reached_data.iloc[0]['time']
            minutes = (reach_time - start_time) / 60.0
            times.append(minutes)
        else:
            # Did not reach
            times.append(None)
            
    return times

def main():
    import sys
    
    if len(sys.argv) > 1:
        benchmark_dir = sys.argv[1]
    else:
        benchmark_dir = str(Path(__file__).parent.parent.parent)

    protocols = find_protocols(benchmark_dir)
    
    a12_results = []
    speedup_results = []
    
    print(f"Analyzing {len(protocols)} protocols for A12 and Speedup...")
    
    for protocol in protocols:
        print(f"Processing {protocol}...")
        
        for metric_name, metric_info in METRICS.items():
            df = load_data(benchmark_dir, protocol, metric_info)
            if df is None:
                continue
                
            # Get data for target fuzzer
            xpg_finals = get_final_values(df, TARGET_FUZZER)
            if not xpg_finals:
                continue
                
            for baseline in BASELINES:
                base_finals = get_final_values(df, baseline)
                if not base_finals:
                    continue
                
                # --- A12 Calculation ---
                a12 = measure_a12(xpg_finals, base_finals)
                
                a12_results.append({
                    'Protocol': PROTOCOLS.get(protocol, protocol),
                    'Metric': metric_name,
                    'Comparison': f"{TARGET_FUZZER.upper()} vs {baseline.upper()}",
                    'A12': f"{a12:.3f}" if a12 is not None else "N/A"
                })
                
                # --- Speedup Calculation ---
                # Strategy:
                # 1. Determine "Goal Coverage". Usually the average final coverage of the baseline.
                # 2. Calculate avg time for Baseline to reach Goal. (Often this is the full duration if Goal is final avg)
                #    Actually, if Goal is avg final coverage, some baseline runs might reach it earlier, some later, some never.
                #    Simpler approach often used: 
                #    Speedup = (Total Experiment Time) / (Time for Target to reach Baseline's Final Avg Coverage)
                
                base_avg_cov = np.mean(base_finals)
                
                # Time for XPG to reach base_avg_cov
                xpg_times = calculate_time_to_coverage(df, TARGET_FUZZER, base_avg_cov)
                valid_xpg_times = [t for t in xpg_times if t is not None]
                
                if valid_xpg_times:
                    avg_time_xpg = np.mean(valid_xpg_times)
                    
                    # Assume experiment duration is the max time found in data or 24h (1440m)
                    # We can infer max duration from the data
                    max_time_data = df['time'].max()
                    min_time_data = df['time'].min()
                    # A safer bet is 24h (1440 mins) as per standard benchmarks, or use the max duration observed for baseline
                    # Let's use the average duration of baseline runs
                    
                    # But simpler definition: Time taken by Baseline / Time taken by Target to reach SAME coverage.
                    # If we use Baseline's final coverage as target, Baseline takes ~Total Time.
                    # Let's look for the Total Time configured.
                    # We'll estimate total time from the max timestamp in the dataframe relative to start.
                    
                    # Better: Time for XPG to reach Base_Avg vs Time for Base to reach Base_Avg
                    # But Base reaches Base_Avg roughly at the end (on average).
                    # Let's use 1440 minutes (24h) as the numerator if not specified, 
                    # OR calculate max relative time in the dataset.
                    
                    # Let's Calculate the average duration of the baseline runs
                    base_durations = []
                    fuzzer_data = df[df['fuzzer'] == baseline]
                    for run in fuzzer_data['run'].unique():
                        run_df = fuzzer_data[fuzzer_data['run'] == run]
                        if not run_df.empty:
                            base_durations.append((run_df['time'].max() - run_df['time'].min()) / 60.0)
                    
                    avg_base_duration = np.mean(base_durations) if base_durations else 1440.0
                    
                    if avg_time_xpg > 0:
                        speedup = avg_base_duration / avg_time_xpg
                    else:
                        speedup = 0 # Should not happen if > 0
                        
                    # If XPG average final coverage is LESS than Baseline average, Speedup is invalid/negative
                    if np.mean(xpg_finals) < base_avg_cov:
                        speedup_str = f"Not Reached (Cov: {np.mean(xpg_finals):.1f} < {base_avg_cov:.1f})"
                    else:
                        speedup_str = f"{speedup:.2f}x"
                else:
                    speedup_str = "Not Reached"
                
                speedup_results.append({
                    'Protocol': PROTOCOLS.get(protocol, protocol),
                    'Metric': metric_name,
                    'Comparison': f"{TARGET_FUZZER.upper()} vs {baseline.upper()}",
                    'Speedup': speedup_str
                })

    # Save results
    df_a12 = pd.DataFrame(a12_results)
    df_speedup = pd.DataFrame(speedup_results)
    
    # Sort for better readability
    sort_cols = ['Protocol', 'Metric', 'Comparison']
    if not df_a12.empty:
        df_a12 = df_a12.sort_values(sort_cols)
        output_a12 = Path(benchmark_dir) / "a12_statistics.csv"
        df_a12.to_csv(output_a12, index=False)
        print(f"Saved A12 statistics to {output_a12}")
        
    if not df_speedup.empty:
        df_speedup = df_speedup.sort_values(sort_cols)
        output_speedup = Path(benchmark_dir) / "speedup_statistics.csv"
        df_speedup.to_csv(output_speedup, index=False)
        print(f"Saved Speedup statistics to {output_speedup}")

if __name__ == "__main__":
    main()

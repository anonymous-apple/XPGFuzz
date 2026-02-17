#!/usr/bin/env python3
"""
Comprehensive analysis of AFLNet, chatafl, and XPGfuzz performance across multiple protocols.
"""

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from pathlib import Path
import os
import warnings
warnings.filterwarnings('ignore')

try:
    import seaborn as sns
    HAS_SEABORN = True
except ImportError:
    HAS_SEABORN = False

try:
    from scipy import stats
    HAS_SCIPY = True
except ImportError:
    HAS_SCIPY = False

# Set style
try:
    plt.style.use('seaborn-v0_8-darkgrid')
except:
    try:
        plt.style.use('seaborn-darkgrid')
    except:
        plt.style.use('default')

if HAS_SEABORN:
    sns.set_palette("husl")

# Protocol information
PROTOCOLS = {
    'exim': 'SMTP',
    'lighttpd1': 'HTTP',
    'pure-ftpd': 'FTP',
    'proftpd': 'FTP',
    'live555': 'RTSP',
    'forked-daapd': 'DAAP',
    'kamailio': 'SIP'
}

FUZZERS = ['aflnet', 'chatafl', 'xpgfuzz', 'aflnet+s1']
FUZZER_COLORS = {
    'aflnet': '#3498db',
    'chatafl': '#e74c3c',
    'xpgfuzz': '#2ecc71',
    'aflnet+s1': '#9b59b6'
}

class FuzzerAnalyzer:
    def __init__(self, benchmark_dir):
        self.benchmark_dir = Path(benchmark_dir)
        self.protocols = PROTOCOLS
        self.fuzzers = FUZZERS
        self.data = {}
        
    def load_data(self):
        """Load all results.csv and states.csv files for all protocols."""
        print("Loading data from benchmark directory...")
        
        for protocol in self.protocols.keys():
            result_dir = self.benchmark_dir / f"results-{protocol}"
            
            if not result_dir.exists():
                print(f"Warning: {result_dir} does not exist, skipping...")
                continue
                
            results_file = result_dir / "results.csv"
            states_file = result_dir / "states.csv"
            
            if results_file.exists():
                self.data[f"{protocol}_coverage"] = pd.read_csv(results_file)
                print(f"  Loaded coverage data for {protocol}")
            else:
                print(f"  Warning: results.csv not found for {protocol}")
                
            if states_file.exists():
                self.data[f"{protocol}_states"] = pd.read_csv(states_file)
                print(f"  Loaded state data for {protocol}")
            else:
                print(f"  Warning: states.csv not found for {protocol}")
        
        print(f"Loaded data for {len([k for k in self.data.keys() if '_coverage' in k])} protocols")
    
    def calculate_final_metrics(self, protocol, metric_type='coverage'):
        """Calculate final metrics for each fuzzer on a protocol."""
        key = f"{protocol}_{metric_type}"
        if key not in self.data:
            return None
            
        df = self.data[key]
        metrics = {}
        
        if metric_type == 'coverage':
            for fuzzer in self.fuzzers:
                fuzzer_data = df[df['fuzzer'] == fuzzer]
                if fuzzer_data.empty:
                    continue
                    
                # Get final coverage values for each run
                runs = fuzzer_data['run'].unique()
                final_values = {}
                
                for cov_type in ['l_per', 'b_per', 'l_abs', 'b_abs']:
                    values = []
                    for run in runs:
                        run_data = fuzzer_data[(fuzzer_data['run'] == run) & 
                                               (fuzzer_data['cov_type'] == cov_type)]
                        if not run_data.empty:
                            values.append(run_data['cov'].iloc[-1])
                    
                    if values:
                        final_values[cov_type] = {
                            'mean': np.mean(values),
                            'std': np.std(values),
                            'min': np.min(values),
                            'max': np.max(values)
                        }
                
                metrics[fuzzer] = final_values
                
        elif metric_type == 'states':
            for fuzzer in self.fuzzers:
                fuzzer_data = df[df['fuzzer'] == fuzzer]
                if fuzzer_data.empty:
                    continue
                    
                runs = fuzzer_data['run'].unique()
                final_values = {}
                
                for state_type in ['nodes', 'edges']:
                    values = []
                    for run in runs:
                        run_data = fuzzer_data[(fuzzer_data['run'] == run) & 
                                               (fuzzer_data['state_type'] == state_type)]
                        if not run_data.empty:
                            values.append(run_data['state'].iloc[-1])
                    
                    if values:
                        final_values[state_type] = {
                            'mean': np.mean(values),
                            'std': np.std(values),
                            'min': np.min(values),
                            'max': np.max(values)
                        }
                
                metrics[fuzzer] = final_values
        
        return metrics
    
    def calculate_coverage_over_time(self, protocol, time_limit=1440, step=10):
        """Calculate coverage over time for each fuzzer."""
        key = f"{protocol}_coverage"
        if key not in self.data:
            return None
            
        df = self.data[key]
        coverage_over_time = {}
        
        for fuzzer in self.fuzzers:
            fuzzer_data = df[df['fuzzer'] == fuzzer]
            if fuzzer_data.empty:
                continue
                
            runs = fuzzer_data['run'].unique()
            time_series = {}
            
            for cov_type in ['l_per', 'b_per']:
                time_points = []
                coverage_values = []
                
                for time_min in range(0, time_limit + 1, step):
                    values_at_time = []
                    
                    for run in runs:
                        run_data = fuzzer_data[(fuzzer_data['run'] == run) & 
                                               (fuzzer_data['cov_type'] == cov_type)]
                        if run_data.empty:
                            continue
                            
                        start_time = run_data.iloc[0]['time']
                        target_time = start_time + time_min * 60
                        
                        time_filtered = run_data[run_data['time'] <= target_time]
                        if not time_filtered.empty:
                            values_at_time.append(time_filtered['cov'].iloc[-1])
                    
                    if values_at_time:
                        time_points.append(time_min)
                        coverage_values.append(np.mean(values_at_time))
                
                time_series[cov_type] = {
                    'time': time_points,
                    'coverage': coverage_values
                }
            
            coverage_over_time[fuzzer] = time_series
        
        return coverage_over_time
    
    def generate_summary_table(self):
        """Generate a comprehensive summary table."""
        print("\n" + "="*80)
        print("COMPREHENSIVE FUZZER PERFORMANCE SUMMARY")
        print("="*80)
        
        summary_data = []
        
        for protocol, protocol_name in self.protocols.items():
            cov_metrics = self.calculate_final_metrics(protocol, 'coverage')
            state_metrics = self.calculate_final_metrics(protocol, 'states')
            
            if not cov_metrics:
                continue
            
            for fuzzer in self.fuzzers:
                if fuzzer not in cov_metrics:
                    continue
                    
                row = {
                    'Protocol': protocol_name,
                    'Protocol_Code': protocol,
                    'Fuzzer': fuzzer.upper(),
                    'Line_Cov_%': f"{cov_metrics[fuzzer].get('l_per', {}).get('mean', 0):.2f}",
                    'Branch_Cov_%': f"{cov_metrics[fuzzer].get('b_per', {}).get('mean', 0):.2f}",
                    'Line_Cov_Abs': f"{cov_metrics[fuzzer].get('l_abs', {}).get('mean', 0):.0f}",
                    'Branch_Cov_Abs': f"{cov_metrics[fuzzer].get('b_abs', {}).get('mean', 0):.0f}",
                }
                
                if state_metrics and fuzzer in state_metrics:
                    row['State_Nodes'] = f"{state_metrics[fuzzer].get('nodes', {}).get('mean', 0):.1f}"
                    row['State_Edges'] = f"{state_metrics[fuzzer].get('edges', {}).get('mean', 0):.1f}"
                else:
                    row['State_Nodes'] = 'N/A'
                    row['State_Edges'] = 'N/A'
                
                summary_data.append(row)
        
        df_summary = pd.DataFrame(summary_data)
        
        # Save to CSV
        output_file = self.benchmark_dir / "comprehensive_summary.csv"
        df_summary.to_csv(output_file, index=False)
        print(f"\nSummary table saved to: {output_file}")
        
        # Print formatted table
        print("\n" + df_summary.to_string(index=False))
        
        return df_summary
    
    def generate_comparison_analysis(self):
        """Generate detailed comparison analysis."""
        print("\n" + "="*80)
        print("DETAILED COMPARISON ANALYSIS")
        print("="*80)
        
        comparison_results = []
        
        for protocol, protocol_name in self.protocols.items():
            cov_metrics = self.calculate_final_metrics(protocol, 'coverage')
            
            if not cov_metrics or len(cov_metrics) < 2:
                continue
            
            print(f"\n--- {protocol_name} ({protocol}) ---")
            
            # Compare line coverage
            line_covs = {}
            branch_covs = {}
            
            for fuzzer in self.fuzzers:
                if fuzzer in cov_metrics:
                    line_covs[fuzzer] = cov_metrics[fuzzer].get('l_per', {}).get('mean', 0)
                    branch_covs[fuzzer] = cov_metrics[fuzzer].get('b_per', {}).get('mean', 0)
            
            if len(line_covs) >= 2:
                # Find best performer
                best_line = max(line_covs.items(), key=lambda x: x[1])
                best_branch = max(branch_covs.items(), key=lambda x: x[1])
                
                print(f"  Line Coverage:")
                for fuzzer, cov in sorted(line_covs.items(), key=lambda x: x[1], reverse=True):
                    improvement = ""
                    if fuzzer != best_line[0]:
                        diff = cov - best_line[1]
                        pct_diff = (diff / best_line[1] * 100) if best_line[1] > 0 else 0
                        improvement = f" ({pct_diff:+.1f}% vs {best_line[0]})"
                    print(f"    {fuzzer.upper():10s}: {cov:6.2f}%{improvement}")
                
                print(f"  Branch Coverage:")
                for fuzzer, cov in sorted(branch_covs.items(), key=lambda x: x[1], reverse=True):
                    improvement = ""
                    if fuzzer != best_branch[0]:
                        diff = cov - best_branch[1]
                        pct_diff = (diff / best_branch[1] * 100) if best_branch[1] > 0 else 0
                        improvement = f" ({pct_diff:+.1f}% vs {best_branch[0]})"
                    print(f"    {fuzzer.upper():10s}: {cov:6.2f}%{improvement}")
                
                comparison_results.append({
                    'Protocol': protocol_name,
                    'Best_Line_Cov': best_line[0],
                    'Best_Branch_Cov': best_branch[0],
                    'Line_Cov_Range': max(line_covs.values()) - min(line_covs.values()),
                    'Branch_Cov_Range': max(branch_covs.values()) - min(branch_covs.values())
                })
        
        return pd.DataFrame(comparison_results)
    
    def plot_coverage_comparison(self):
        """Generate comparison plots for all protocols."""
        print("\nGenerating comparison plots...")
        
        n_protocols = len(self.protocols)
        fig, axes = plt.subplots(n_protocols, 2, figsize=(16, 4*n_protocols))
        if n_protocols == 1:
            axes = axes.reshape(1, -1)
        
        fig.suptitle('Fuzzer Performance Comparison Across Protocols', fontsize=16, fontweight='bold')
        
        for idx, (protocol, protocol_name) in enumerate(self.protocols.items()):
            cov_metrics = self.calculate_final_metrics(protocol, 'coverage')
            
            if not cov_metrics:
                continue
            
            # Line coverage
            fuzzers_list = []
            line_covs = []
            line_stds = []
            
            for fuzzer in self.fuzzers:
                if fuzzer in cov_metrics:
                    fuzzers_list.append(fuzzer.upper())
                    line_covs.append(cov_metrics[fuzzer].get('l_per', {}).get('mean', 0))
                    line_stds.append(cov_metrics[fuzzer].get('l_per', {}).get('std', 0))
            
            if fuzzers_list:
                x_pos = np.arange(len(fuzzers_list))
                colors = [FUZZER_COLORS.get(f.lower(), '#95a5a6') for f in fuzzers_list]
                
                bars = axes[idx, 0].bar(x_pos, line_covs, yerr=line_stds, 
                                       capsize=5, color=colors, alpha=0.7, edgecolor='black')
                axes[idx, 0].set_ylabel('Line Coverage (%)', fontsize=10)
                axes[idx, 0].set_title(f'{protocol_name} - Line Coverage', fontsize=12, fontweight='bold')
                axes[idx, 0].set_xticks(x_pos)
                axes[idx, 0].set_xticklabels(fuzzers_list)
                axes[idx, 0].grid(axis='y', alpha=0.3)
                
                # Add value labels on bars
                for bar, val in zip(bars, line_covs):
                    height = bar.get_height()
                    axes[idx, 0].text(bar.get_x() + bar.get_width()/2., height,
                                     f'{val:.2f}%', ha='center', va='bottom', fontsize=9)
            
            # Branch coverage
            fuzzers_list = []
            branch_covs = []
            branch_stds = []
            
            for fuzzer in self.fuzzers:
                if fuzzer in cov_metrics:
                    fuzzers_list.append(fuzzer.upper())
                    branch_covs.append(cov_metrics[fuzzer].get('b_per', {}).get('mean', 0))
                    branch_stds.append(cov_metrics[fuzzer].get('b_per', {}).get('std', 0))
            
            if fuzzers_list:
                x_pos = np.arange(len(fuzzers_list))
                colors = [FUZZER_COLORS.get(f.lower(), '#95a5a6') for f in fuzzers_list]
                
                bars = axes[idx, 1].bar(x_pos, branch_covs, yerr=branch_stds,
                                       capsize=5, color=colors, alpha=0.7, edgecolor='black')
                axes[idx, 1].set_ylabel('Branch Coverage (%)', fontsize=10)
                axes[idx, 1].set_title(f'{protocol_name} - Branch Coverage', fontsize=12, fontweight='bold')
                axes[idx, 1].set_xticks(x_pos)
                axes[idx, 1].set_xticklabels(fuzzers_list)
                axes[idx, 1].grid(axis='y', alpha=0.3)
                
                # Add value labels on bars
                for bar, val in zip(bars, branch_covs):
                    height = bar.get_height()
                    axes[idx, 1].text(bar.get_x() + bar.get_width()/2., height,
                                     f'{val:.2f}%', ha='center', va='bottom', fontsize=9)
        
        plt.tight_layout()
        output_file = self.benchmark_dir / "fuzzer_comparison_all_protocols.png"
        plt.savefig(output_file, dpi=300, bbox_inches='tight')
        print(f"  Saved comparison plot to: {output_file}")
        plt.close()
    
    def plot_coverage_over_time(self, time_limit=1440, step=30):
        """Plot coverage over time for all protocols."""
        print("\nGenerating coverage-over-time plots...")
        
        n_protocols = len(self.protocols)
        fig, axes = plt.subplots(n_protocols, 2, figsize=(16, 4*n_protocols))
        if n_protocols == 1:
            axes = axes.reshape(1, -1)
        
        fig.suptitle('Coverage Over Time Comparison', fontsize=16, fontweight='bold')
        
        for idx, (protocol, protocol_name) in enumerate(self.protocols.items()):
            coverage_over_time = self.calculate_coverage_over_time(protocol, time_limit, step)
            
            if not coverage_over_time:
                continue
            
            # Line coverage over time
            for fuzzer in self.fuzzers:
                if fuzzer in coverage_over_time and 'l_per' in coverage_over_time[fuzzer]:
                    data = coverage_over_time[fuzzer]['l_per']
                    axes[idx, 0].plot(data['time'], data['coverage'], 
                                     label=fuzzer.upper(), 
                                     color=FUZZER_COLORS.get(fuzzer, '#95a5a6'),
                                     linewidth=2, alpha=0.8)
            
            axes[idx, 0].set_xlabel('Time (minutes)', fontsize=10)
            axes[idx, 0].set_ylabel('Line Coverage (%)', fontsize=10)
            axes[idx, 0].set_title(f'{protocol_name} - Line Coverage Over Time', fontsize=12, fontweight='bold')
            axes[idx, 0].legend(fontsize=9)
            axes[idx, 0].grid(alpha=0.3)
            axes[idx, 0].set_ylim([0, None])
            
            # Branch coverage over time
            for fuzzer in self.fuzzers:
                if fuzzer in coverage_over_time and 'b_per' in coverage_over_time[fuzzer]:
                    data = coverage_over_time[fuzzer]['b_per']
                    axes[idx, 1].plot(data['time'], data['coverage'],
                                     label=fuzzer.upper(),
                                     color=FUZZER_COLORS.get(fuzzer, '#95a5a6'),
                                     linewidth=2, alpha=0.8)
            
            axes[idx, 1].set_xlabel('Time (minutes)', fontsize=10)
            axes[idx, 1].set_ylabel('Branch Coverage (%)', fontsize=10)
            axes[idx, 1].set_title(f'{protocol_name} - Branch Coverage Over Time', fontsize=12, fontweight='bold')
            axes[idx, 1].legend(fontsize=9)
            axes[idx, 1].grid(alpha=0.3)
            axes[idx, 1].set_ylim([0, None])
        
        plt.tight_layout()
        output_file = self.benchmark_dir / "coverage_over_time_all_protocols.png"
        plt.savefig(output_file, dpi=300, bbox_inches='tight')
        print(f"  Saved coverage-over-time plot to: {output_file}")
        plt.close()
    
    def generate_statistical_analysis(self):
        """Generate statistical analysis comparing fuzzers."""
        print("\n" + "="*80)
        print("STATISTICAL ANALYSIS")
        print("="*80)
        
        stats_results = []
        
        for protocol, protocol_name in self.protocols.items():
            cov_metrics = self.calculate_final_metrics(protocol, 'coverage')
            
            if not cov_metrics or len(cov_metrics) < 2:
                continue
            
            # Collect data for statistical tests
            line_cov_data = {}
            branch_cov_data = {}
            
            key = f"{protocol}_coverage"
            df = self.data[key]
            
            for fuzzer in self.fuzzers:
                fuzzer_data = df[df['fuzzer'] == fuzzer]
                if fuzzer_data.empty:
                    continue
                
                runs = fuzzer_data['run'].unique()
                line_values = []
                branch_values = []
                
                for run in runs:
                    line_data = fuzzer_data[(fuzzer_data['run'] == run) & 
                                            (fuzzer_data['cov_type'] == 'l_per')]
                    branch_data = fuzzer_data[(fuzzer_data['run'] == run) & 
                                              (fuzzer_data['cov_type'] == 'b_per')]
                    
                    if not line_data.empty:
                        line_values.append(line_data['cov'].iloc[-1])
                    if not branch_data.empty:
                        branch_values.append(branch_data['cov'].iloc[-1])
                
                if line_values:
                    line_cov_data[fuzzer] = line_values
                if branch_values:
                    branch_cov_data[fuzzer] = branch_values
            
            if len(line_cov_data) >= 2:
                print(f"\n{protocol_name} ({protocol}):")
                
                # Perform pairwise comparisons
                fuzzers_list = list(line_cov_data.keys())
                for i in range(len(fuzzers_list)):
                    for j in range(i+1, len(fuzzers_list)):
                        f1, f2 = fuzzers_list[i], fuzzers_list[j]
                        
                        # Line coverage comparison
                        if len(line_cov_data[f1]) > 1 and len(line_cov_data[f2]) > 1:
                            mean_diff = np.mean(line_cov_data[f1]) - np.mean(line_cov_data[f2])
                            
                            if HAS_SCIPY:
                                t_stat, p_value = stats.ttest_ind(line_cov_data[f1], line_cov_data[f2])
                                significance = "***" if p_value < 0.001 else "**" if p_value < 0.01 else "*" if p_value < 0.05 else "ns"
                            else:
                                p_value = None
                                significance = "N/A"
                            
                            stats_results.append({
                                'Protocol': protocol_name,
                                'Metric': 'Line Coverage',
                                'Fuzzer1': f1.upper(),
                                'Fuzzer2': f2.upper(),
                                'Mean_Diff': mean_diff,
                                'P_Value': p_value if HAS_SCIPY else 'N/A',
                                'Significance': significance
                            })
                            
                            print(f"  Line Coverage: {f1.upper()} vs {f2.upper()}")
                            print(f"    Mean difference: {mean_diff:+.2f}%")
                            if HAS_SCIPY:
                                print(f"    p-value: {p_value:.4f} {significance}")
                            else:
                                print(f"    Statistical test: N/A (scipy not available)")
        
        stats_df = pd.DataFrame(stats_results)
        if not stats_df.empty:
            output_file = self.benchmark_dir / "statistical_analysis.csv"
            stats_df.to_csv(output_file, index=False)
            print(f"\nStatistical analysis saved to: {output_file}")
        
        return stats_df
    
    def generate_rankings(self):
        """Generate rankings of fuzzers across all protocols."""
        print("\n" + "="*80)
        print("FUZZER RANKINGS")
        print("="*80)
        
        rankings = {fuzzer: {'wins': 0, 'total': 0, 'avg_rank': 0} for fuzzer in self.fuzzers}
        rank_scores = {fuzzer: [] for fuzzer in self.fuzzers}
        
        for protocol, protocol_name in self.protocols.items():
            cov_metrics = self.calculate_final_metrics(protocol, 'coverage')
            
            if not cov_metrics:
                continue
            
            # Rank by line coverage
            line_ranks = sorted(cov_metrics.items(), 
                               key=lambda x: x[1].get('l_per', {}).get('mean', 0), 
                               reverse=True)
            
            print(f"\n{protocol_name} ({protocol}) - Line Coverage Ranking:")
            for rank, (fuzzer, metrics) in enumerate(line_ranks, 1):
                cov = metrics.get('l_per', {}).get('mean', 0)
                print(f"  {rank}. {fuzzer.upper():10s}: {cov:6.2f}%")
                rankings[fuzzer]['total'] += 1
                rank_scores[fuzzer].append(rank)
                if rank == 1:
                    rankings[fuzzer]['wins'] += 1
        
        print("\n" + "-"*80)
        print("Overall Rankings:")
        print("-"*80)
        
        # Calculate average ranks
        for fuzzer in self.fuzzers:
            if rank_scores[fuzzer]:
                rankings[fuzzer]['avg_rank'] = np.mean(rank_scores[fuzzer])
        
        sorted_rankings = sorted(rankings.items(), key=lambda x: x[1]['avg_rank'])
        
        for rank, (fuzzer, stats) in enumerate(sorted_rankings, 1):
            print(f"{rank}. {fuzzer.upper():10s}: "
                  f"Wins: {stats['wins']:2d}, "
                  f"Avg Rank: {stats['avg_rank']:.2f}, "
                  f"Protocols: {stats['total']}")
        
        return rankings
    
    def run_comprehensive_analysis(self):
        """Run all analyses and generate reports."""
        print("="*80)
        print("COMPREHENSIVE FUZZER PERFORMANCE ANALYSIS")
        print("="*80)
        
        # Load data
        self.load_data()
        
        if not self.data:
            print("Error: No data loaded. Please check the benchmark directory.")
            return
        
        # Generate all analyses
        summary_df = self.generate_summary_table()
        comparison_df = self.generate_comparison_analysis()
        stats_df = self.generate_statistical_analysis()
        rankings = self.generate_rankings()
        
        # Generate plots
        self.plot_coverage_comparison()
        self.plot_coverage_over_time()
        
        print("\n" + "="*80)
        print("ANALYSIS COMPLETE!")
        print("="*80)
        print("\nGenerated files:")
        print("  - comprehensive_summary.csv")
        print("  - statistical_analysis.csv")
        print("  - fuzzer_comparison_all_protocols.png")
        print("  - coverage_over_time_all_protocols.png")
        print("\nAll files saved to:", self.benchmark_dir)


if __name__ == '__main__':
    import sys
    
    benchmark_dir = Path(__file__).parent if '__file__' in globals() else Path.cwd()
    
    if len(sys.argv) > 1:
        benchmark_dir = Path(sys.argv[1])
    
    analyzer = FuzzerAnalyzer(benchmark_dir)
    analyzer.run_comprehensive_analysis()


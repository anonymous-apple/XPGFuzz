#!/usr/bin/env python3
"""
Generate plots for all metrics (branch, line, state nodes, state edges).
Each protocol gets its own subplot.
"""

import pandas as pd
import matplotlib.pyplot as plt
from pathlib import Path
import numpy as np
from datetime import datetime
import warnings
warnings.filterwarnings('ignore')
import matplotlib.font_manager as fm

# 字体路径配置
def _pick_cjk_font_path():
    for p in (
        "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
        "/usr/share/fonts/opentype/noto/NotoSerifCJK-Regular.ttc",
        "/usr/share/fonts/truetype/wqy/wqy-microhei.ttc",
    ):
        if Path(p).exists():
            return p
    return ""

_CJK_FONT_PATH = _pick_cjk_font_path()
_CJK_FONT_NAME = ""
_CJK_FONT = None
if _CJK_FONT_PATH:
    fm.fontManager.addfont(_CJK_FONT_PATH)
    _CJK_FONT = fm.FontProperties(fname=_CJK_FONT_PATH)
    _CJK_FONT_NAME = _CJK_FONT.get_name()

# Ensure Chinese labels render + embed TrueType in PDF
plt.rcParams.update({
    'axes.unicode_minus': False,
    'pdf.fonttype': 42,
    'ps.fonttype': 42,
})
if _CJK_FONT_NAME:
    plt.rcParams.update({
        'font.family': 'sans-serif',
        'font.sans-serif': [_CJK_FONT_NAME, 'DejaVu Sans'],
    })

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
FUZZER_COLORS = {
    'aflnet': '#3498db',
    'chatafl': '#e74c3c',
    'xpgfuzz': '#2ecc71',
}

FUZZER_LABELS = {
    'aflnet': 'AFLNet',
    'chatafl': 'chatafl',
    'xpgfuzz': 'XPGFuzz',
}

METRICS_CONFIG = {
    'branch_coverage': {
        'filename': 'results.csv',
        'type_col': 'cov_type',
        'val_col': 'cov',
        'type_val': 'b_abs',
        'ylabel': '分支数（个）',
        'title': '各协议分支覆盖数量（单位：个）随时间变化'
    },
    'line_coverage': {
        'filename': 'results.csv',
        'type_col': 'cov_type',
        'val_col': 'cov',
        'type_val': 'l_abs',
        'ylabel': '行数（行）',
        'title': '各协议行覆盖数量（单位：行）随时间变化'
    },
    'state_count': {
        'filename': 'states.csv',
        'type_col': 'state_type',
        'val_col': 'state',
        'type_val': 'nodes',
        'ylabel': '状态数（个）',
        'title': '各协议状态数量（单位：个）随时间变化'
    },
    'state_transitions': {
        'filename': 'states.csv',
        'type_col': 'state_type',
        'val_col': 'state',
        'type_val': 'edges',
        'ylabel': '状态迁移数（个）',
        'title': '各协议状态迁移数量（单位：个）随时间变化'
    }
}


def find_protocols_with_results(benchmark_dir):
    """Find all protocols that have results.csv files."""
    benchmark_path = Path(benchmark_dir)
    protocols_found = []
    
    # First, try to find all results-* directories
    result_dirs = list(benchmark_path.glob("results-*"))
    
    if not result_dirs:
        return []
    
    # Extract protocol names from directory names
    found_protocols = set()
    for result_dir in result_dirs:
        protocol = result_dir.name.replace("results-", "")
        found_protocols.add(protocol)
    
    # Check each found protocol for results.csv (keep a stable, explicit order)
    ordered = [p for p in PROTOCOLS.keys() if p in found_protocols] + \
              sorted([p for p in found_protocols if p not in PROTOCOLS])
    for protocol in ordered:
        result_dir = benchmark_path / f"results-{protocol}"
        results_file = result_dir / "results.csv"
        
        if results_file.exists():
            protocols_found.append(protocol)
    
    # Also check protocols in PROTOCOLS dict
    for protocol in PROTOCOLS.keys():
        if protocol not in found_protocols:
            result_dir = benchmark_path / f"results-{protocol}"
            results_file = result_dir / "results.csv"
            if results_file.exists():
                if protocol not in protocols_found:
                    protocols_found.append(protocol)
    
    return protocols_found


def load_data(benchmark_dir, protocol, metric_config):
    """Load data for a protocol based on metric configuration."""
    benchmark_path = Path(benchmark_dir)
    data_file = benchmark_path / f"results-{protocol}" / metric_config['filename']
    
    if not data_file.exists():
        return None
    
    df = pd.read_csv(data_file)
    
    # Filter for specific type
    df_filtered = df[df[metric_config['type_col']] == metric_config['type_val']].copy()
    
    if df_filtered.empty:
        return None
    
    # Rename value column to 'value' for consistency
    df_filtered = df_filtered.rename(columns={metric_config['val_col']: 'value'})
    
    return df_filtered


def calculate_average_over_time(df, time_limit=1440, step=10):
    """Calculate average value over time for each fuzzer."""
    processed_data = {}
    
    for fuzzer in FUZZERS:
        fuzzer_data = df[df['fuzzer'] == fuzzer]
        if fuzzer_data.empty:
            continue
        
        runs = fuzzer_data['run'].unique()
        time_points = []
        values = []
        stds = []
        
        # Always include time=0 (starting point)
        values_at_time_0 = []
        for run in runs:
            run_data = fuzzer_data[fuzzer_data['run'] == run]
            if run_data.empty:
                continue
            # Get initial value (first data point)
            values_at_time_0.append(run_data.iloc[0]['value'])
        
        if values_at_time_0:
            time_points = [0]
            values = [np.mean(values_at_time_0)]
            stds = [np.std(values_at_time_0)]
        
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
                
                # Get value at or before target time
                time_filtered = run_data[run_data['time'] <= target_time]
                if not time_filtered.empty:
                    values_at_time.append(time_filtered['value'].iloc[-1])
            
            if values_at_time:
                time_points.append(time_min)
                values.append(np.mean(values_at_time))
                stds.append(np.std(values_at_time))
        
        if time_points:
            processed_data[fuzzer] = {
                'time': time_points,
                'value': values,
                'std': stds
            }
    
    return processed_data


def plot_metric(benchmark_dir, metric_key, output_file=None, time_limit=1440, step=30):
    """Generate plots for a specific metric."""
    config = METRICS_CONFIG[metric_key]
    
    # Find protocols with results
    protocols = find_protocols_with_results(benchmark_dir)
    
    if not protocols:
        print(f"No protocols found for {metric_key}")
        return
    
    if output_file is None:
        now = datetime.now()
        date_str = now.strftime("%m月-%d_%H-%M-%S")
        output_file = f'{metric_key}_all_protocols_{date_str}.pdf'
    
    # Calculate number of rows and columns for subplots
    n_protocols = len(protocols)
    n_cols = 3
    n_rows = (n_protocols + n_cols - 1) // n_cols
    
    # Font sizes
    title_fontsize = 20      # 总标题
    subtitle_fontsize = 16   # 子图标题
    fontsize_xy = 14         # 轴标签
    tick_fontsize = 12       # 刻度
    legend_fontsize = 12     # 图例
    
    fig, axes = plt.subplots(n_rows, n_cols, figsize=(18, 5*n_rows))
    fig.suptitle(
        config['title'],
        fontsize=title_fontsize,
        fontweight='bold',
        fontproperties=_CJK_FONT,
    )
    
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
        df = load_data(benchmark_dir, protocol, config)
        if df is None:
            ax.text(0.5, 0.5, f'No data for {protocol}', 
                   ha='center', va='center', transform=ax.transAxes)
            ax.set_title(PROTOCOLS.get(protocol, protocol), fontsize=subtitle_fontsize, fontweight='bold', fontproperties=_CJK_FONT)
            continue
        
        # Calculate averages over time
        plot_data = calculate_average_over_time(df, time_limit, step)
        
        if not plot_data:
            ax.text(0.5, 0.5, f'No data for {protocol}', 
                   ha='center', va='center', transform=ax.transAxes)
            ax.set_title(PROTOCOLS.get(protocol, protocol), fontsize=subtitle_fontsize, fontweight='bold', fontproperties=_CJK_FONT)
            continue
        
        # Plot each fuzzer
        markers = {'aflnet': 'o', 'chatafl': '^', 'xpgfuzz': 's'}
        linestyles = {'aflnet': '-', 'chatafl': '--', 'xpgfuzz': '-.'}
        
        for fuzzer in FUZZERS:
            if fuzzer in plot_data:
                data = plot_data[fuzzer]
                times = np.array(data['time'])
                means = np.array(data['value'])
                stds = np.array(data['std'])
                
                # Plot mean line with markers
                ax.plot(times, means, 
                       label=FUZZER_LABELS.get(fuzzer, fuzzer),
                       color=FUZZER_COLORS.get(fuzzer, '#666'),
                       linewidth=1.5,
                       linestyle=linestyles.get(fuzzer, '-'),
                       marker=markers.get(fuzzer, ''),
                       markersize=5,
                       markevery=len(times)//8 if len(times) > 8 else 1)
        
        ax.set_xlabel('时间（分）', fontsize=fontsize_xy, fontproperties=_CJK_FONT)
        ax.set_ylabel(config['ylabel'], fontsize=fontsize_xy, fontproperties=_CJK_FONT)
        ax.set_title(PROTOCOLS.get(protocol, protocol), fontsize=subtitle_fontsize, fontweight='bold', fontproperties=_CJK_FONT)
        ax.tick_params(axis='both', labelsize=tick_fontsize)
        
        # Legend styling
        fuzzer_labels = [FUZZER_LABELS.get(f, f) for f in FUZZERS if f in plot_data]
        if fuzzer_labels:
            ax.legend(loc='lower right', fontsize=legend_fontsize, frameon=True, fancybox=False, framealpha=0.9, edgecolor='black')
            
        ax.grid(True, linestyle='--', alpha=0.6)
        ax.set_ylim([0, None])
        ax.set_xlim([0, None])
    
    # Hide unused subplots
    for idx in range(n_protocols, n_rows * n_cols):
        row = idx // n_cols
        col = idx % n_cols
        axes[row, col].axis('off')
    
    plt.tight_layout(rect=[0, 0.03, 1, 0.95])
    plt.subplots_adjust(wspace=0.25, hspace=0.35)
    
    # Save figure
    output_path = Path(benchmark_dir) / output_file
    plt.savefig(output_path, bbox_inches='tight')
    print(f"Plot saved to: {output_path}")
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
    
    # Generate all plots
    for metric in METRICS_CONFIG:
        print(f"\nGenerating plot for: {metric}...")
        plot_metric(benchmark_dir, metric)
    
    print("\n" + "="*80)
    print("All analyses complete!")


if __name__ == '__main__':
    main()

#!/bin/bash

# Log analysis script for replay logs
# Can run inside docker container or on host
# Analyzes collected logs and generates summary report

logdir=$1      #log directory (default: logs)
reportfile=$2  #report file (default: log_analysis_report.txt)

# Set defaults if not provided
if [ -z "$logdir" ]; then
  logdir="logs"
fi

if [ -z "$reportfile" ]; then
  reportfile="log_analysis_report.txt"
fi

# Check if running inside docker (WORKDIR exists) or on host
if [ -d "/home/ubuntu/experiments" ]; then
  WORKDIR="/home/ubuntu/experiments"
  # If logdir is relative, make it relative to WORKDIR
  if [[ ! "$logdir" = /* ]]; then
    logdir="${WORKDIR}/${logdir}"
  fi
else
  WORKDIR=""
fi

if [ ! -d "$logdir" ]; then
  echo "Error: Log directory '$logdir' does not exist"
  exit 1
fi

echo "Analyzing logs in: $logdir"
echo "Generating report: $reportfile"
echo ""

# Initialize report
> $reportfile
echo "==========================================" >> $reportfile
echo "Log Analysis Report" >> $reportfile
echo "Generated: $(date)" >> $reportfile
echo "Log Directory: $logdir" >> $reportfile
echo "==========================================" >> $reportfile
echo "" >> $reportfile

# Count log files
crash_logs=$(find $logdir -name "crash_*.log" 2>/dev/null | wc -l)
hang_logs=$(find $logdir -name "hang_*.log" 2>/dev/null | wc -l)
total_logs=$(find $logdir -name "*.log" 2>/dev/null | wc -l)

echo "Summary Statistics" >> $reportfile
echo "------------------" >> $reportfile
echo "Total log files: $total_logs" >> $reportfile
echo "Crash logs: $crash_logs" >> $reportfile
echo "Hang logs: $hang_logs" >> $reportfile
echo "" >> $reportfile

# Analyze each log file
echo "Detailed Analysis" >> $reportfile
echo "-----------------" >> $reportfile
echo "" >> $reportfile

error_count_total=0
warning_count_total=0
timeout_count=0
signal_count=0

for logfile in $(find $logdir -name "*.log" 2>/dev/null | sort); do
  basename=$(basename $logfile)
  echo "Processing: $basename" >> $reportfile
  echo "----------------------------------------" >> $reportfile
  
  # Extract exit status
  exit_status=$(grep "=== Exit Status:" $logfile | tail -1 | awk '{print $3}')
  test_type=$(grep "=== Test Type:" $logfile | tail -1 | awk '{print $3}')
  test_file=$(grep "=== Test File:" $logfile | tail -1 | sed 's/=== Test File: //')
  
  echo "  Type: $test_type" >> $reportfile
  echo "  Exit Status: $exit_status" >> $reportfile
  if [ -n "$test_file" ]; then
    echo "  Test File: $test_file" >> $reportfile
  fi
  
  # Count error patterns
  error_count=$(grep -i "error\|fatal\|segmentation\|abort\|assert\|crash" $logfile 2>/dev/null | wc -l)
  warning_count=$(grep -i "warning" $logfile 2>/dev/null | wc -l)
  error_count_total=$((error_count_total + error_count))
  warning_count_total=$((warning_count_total + warning_count))
  
  echo "  Errors/Warnings: $error_count errors, $warning_count warnings" >> $reportfile
  
  # Extract last few lines if there are errors
  if [ $error_count -gt 0 ]; then
    echo "  Last error lines:" >> $reportfile
    grep -i "error\|fatal\|segmentation\|abort\|assert\|crash" $logfile 2>/dev/null | tail -3 | sed 's/^/    /' >> $reportfile
  fi
  
  # Check for timeout
  if grep -q "Terminated\|timeout\|SIGUSR1" $logfile 2>/dev/null; then
    echo "  Status: TIMEOUT/TERMINATED" >> $reportfile
    timeout_count=$((timeout_count + 1))
  fi
  
  # Check for signal termination
  if [ -n "$exit_status" ] && [ "$exit_status" -ge 128 ] 2>/dev/null; then
    signal_count=$((signal_count + 1))
    signal_num=$((exit_status - 128))
    echo "  Signal: $signal_num (SIG$(kill -l $signal_num 2>/dev/null || echo "UNKNOWN"))" >> $reportfile
  fi
  
  # Log file size
  log_size=$(wc -l < $logfile 2>/dev/null || echo "0")
  echo "  Log size: $log_size lines" >> $reportfile
  echo "" >> $reportfile
done

# Generate summary of common errors
echo "" >> $reportfile
echo "Common Error Patterns" >> $reportfile
echo "---------------------" >> $reportfile
echo "" >> $reportfile

# Count common error patterns across all logs
grep -h -i "error\|fatal\|segmentation\|abort\|assert\|crash" $logdir/*.log 2>/dev/null | \
  sort | uniq -c | sort -rn | head -20 | \
  sed 's/^/  /' >> $reportfile

# Overall statistics
echo "" >> $reportfile
echo "Overall Statistics" >> $reportfile
echo "------------------" >> $reportfile
echo "Total errors found: $error_count_total" >> $reportfile
echo "Total warnings found: $warning_count_total" >> $reportfile
echo "Timeouts/terminations: $timeout_count" >> $reportfile
echo "Signal terminations: $signal_count" >> $reportfile
echo "" >> $reportfile
echo "==========================================" >> $reportfile
echo "Report saved to: $reportfile" >> $reportfile

# Print summary to console
echo "Analysis complete!"
echo "  Total logs: $total_logs"
echo "  Crash logs: $crash_logs"
echo "  Hang logs: $hang_logs"
echo "  Total errors: $error_count_total"
echo "  Total warnings: $warning_count_total"
echo "  Timeouts: $timeout_count"
echo "  Signal terminations: $signal_count"
echo "  Report: $reportfile"


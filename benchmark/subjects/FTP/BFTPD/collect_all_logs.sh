#!/bin/bash

# Script to collect all crash and hang logs, deduplicate them, and generate reports
# This script should be called after coverage collection

OUTDIR=$1      #name of the output folder (e.g., out-bftpd-aflnet)
FUZZER=$2      #fuzzer name (e.g., aflnet) -- used to determine file mode
TARGET_DIR=${TARGET_DIR:-"bftpd"}

strstr() {
  [ "${1#*$2*}" = "$1" ] && return 1
  return 0
}

# Determine file mode based on fuzzer
# 0: the test case is a concatenated message sequence -- there is no message boundary
# 1: the test case is a structured file keeping several request messages
if [ "$FUZZER" = "aflnwe" ]; then
  FMODE=0
else
  FMODE=1
fi

# Move to fuzzing folder
cd $WORKDIR/${TARGET_DIR}

# Create directories for collected logs
mkdir -p ${OUTDIR}/replay_logs
mkdir -p ${OUTDIR}/replay_logs/logs
mkdir -p ${OUTDIR}/replay_logs/deduplicated

echo "=========================================="
echo "Collecting crash and hang logs"
echo "Output directory: ${OUTDIR}"
echo "Fuzzer: ${FUZZER}"
echo "File mode: ${FMODE}"
echo "=========================================="

# Step 1: Collect crash logs
CRASH_DIR="${OUTDIR}/replayable-crashes"
if [ -d "$CRASH_DIR" ] && [ "$(find "$CRASH_DIR" -type f ! -name "README.txt" 2>/dev/null | wc -l)" -gt 0 ]; then
  echo ""
  echo "Processing crashes from: $CRASH_DIR"
  ${WORKDIR}/${TARGET_DIR}/collect_log.sh "$CRASH_DIR" 21 1 "${OUTDIR}/replay_logs/crash_logs.csv" $FMODE
  CRASH_STATUS=$?
  if [ $CRASH_STATUS -eq 0 ]; then
    echo "Crash log collection completed successfully"
  else
    echo "Warning: Crash log collection returned status $CRASH_STATUS"
  fi
else
  echo ""
  echo "No crash files found in $CRASH_DIR"
  touch "${OUTDIR}/replay_logs/crash_logs.csv"
  echo "BugFile,Status,LogFile,Timestamp" > "${OUTDIR}/replay_logs/crash_logs.csv"
fi

# Step 2: Collect hang logs
HANG_DIR="${OUTDIR}/replayable-hangs"
if [ -d "$HANG_DIR" ] && [ "$(find "$HANG_DIR" -type f ! -name "README.txt" 2>/dev/null | wc -l)" -gt 0 ]; then
  echo ""
  echo "Processing hangs from: $HANG_DIR"
  ${WORKDIR}/${TARGET_DIR}/collect_log.sh "$HANG_DIR" 21 1 "${OUTDIR}/replay_logs/hang_logs.csv" $FMODE
  HANG_STATUS=$?
  if [ $HANG_STATUS -eq 0 ]; then
    echo "Hang log collection completed successfully"
  else
    echo "Warning: Hang log collection returned status $HANG_STATUS"
  fi
else
  echo ""
  echo "No hang files found in $HANG_DIR"
  touch "${OUTDIR}/replay_logs/hang_logs.csv"
  echo "BugFile,Status,LogFile,Timestamp" > "${OUTDIR}/replay_logs/hang_logs.csv"
fi

# Step 3: Deduplicate logs based on file content hash
echo ""
echo "=========================================="
echo "Deduplicating logs based on content hash"
echo "=========================================="

# Function to compute MD5 hash of a file
compute_hash() {
  if command -v md5sum &> /dev/null; then
    md5sum "$1" | cut -d' ' -f1
  elif command -v md5 &> /dev/null; then
    md5 -q "$1"
  else
    # Fallback: use first 1000 bytes as identifier
    head -c 1000 "$1" | sha256sum | cut -d' ' -f1
  fi
}

# Collect all log files
ALL_LOGS_DIR="${OUTDIR}/replay_logs/logs"
DEDUP_DIR="${OUTDIR}/replay_logs/deduplicated"
mkdir -p "$DEDUP_DIR"

declare -A hash_map
declare -A file_map
duplicate_count=0
unique_count=0

if [ -d "$ALL_LOGS_DIR" ]; then
  echo "Scanning log files for duplicates..."
  
  for log_file in "$ALL_LOGS_DIR"/*.log; do
    if [ ! -f "$log_file" ]; then
      continue
    fi
    
    file_hash=$(compute_hash "$log_file")
    basename_log=$(basename "$log_file")
    
    if [ -z "${hash_map[$file_hash]}" ]; then
      # First occurrence of this hash - keep it
      hash_map[$file_hash]=1
      file_map[$file_hash]="$basename_log"
      cp "$log_file" "$DEDUP_DIR/$basename_log"
      unique_count=$((unique_count + 1))
    else
      # Duplicate found
      duplicate_count=$((duplicate_count + 1))
      echo "Duplicate found: $basename_log (same as ${file_map[$file_hash]})"
    fi
  done
  
  echo ""
  echo "Deduplication summary:"
  echo "  Total log files: $((unique_count + duplicate_count))"
  echo "  Unique logs: $unique_count"
  echo "  Duplicates removed: $duplicate_count"
else
  echo "No log files found in $ALL_LOGS_DIR"
fi

# Step 4: Generate summary report
echo ""
echo "=========================================="
echo "Generating summary report"
echo "=========================================="

SUMMARY_FILE="${OUTDIR}/replay_logs/summary.txt"
cat > "$SUMMARY_FILE" << EOF
Replay Log Collection Summary
=============================
Generated: $(date)

Fuzzer: ${FUZZER}
Output Directory: ${OUTDIR}
File Mode: ${FMODE}

Crash Logs:
-----------
EOF

if [ -f "${OUTDIR}/replay_logs/crash_logs.csv" ]; then
  crash_total=$(tail -n +2 "${OUTDIR}/replay_logs/crash_logs.csv" | wc -l)
  crash_confirmed=$(tail -n +2 "${OUTDIR}/replay_logs/crash_logs.csv" | awk -F',' '$2==1' | wc -l)
  echo "  Total crash test cases: $crash_total" >> "$SUMMARY_FILE"
  echo "  Confirmed crashes: $crash_confirmed" >> "$SUMMARY_FILE"
else
  echo "  No crash logs collected" >> "$SUMMARY_FILE"
fi

cat >> "$SUMMARY_FILE" << EOF

Hang Logs:
----------
EOF

if [ -f "${OUTDIR}/replay_logs/hang_logs.csv" ]; then
  hang_total=$(tail -n +2 "${OUTDIR}/replay_logs/hang_logs.csv" | wc -l)
  hang_confirmed=$(tail -n +2 "${OUTDIR}/replay_logs/hang_logs.csv" | awk -F',' '$2==1' | wc -l)
  echo "  Total hang test cases: $hang_total" >> "$SUMMARY_FILE"
  echo "  Confirmed hangs: $hang_confirmed" >> "$SUMMARY_FILE"
else
  echo "  No hang logs collected" >> "$SUMMARY_FILE"
fi

cat >> "$SUMMARY_FILE" << EOF

Deduplication:
--------------
  Total log files: $((unique_count + duplicate_count))
  Unique logs: $unique_count
  Duplicates removed: $duplicate_count

Files:
------
  Crash logs CSV: replay_logs/crash_logs.csv
  Hang logs CSV: replay_logs/hang_logs.csv
  All logs directory: replay_logs/logs/
  Deduplicated logs: replay_logs/deduplicated/
  Summary: replay_logs/summary.txt
EOF

cat "$SUMMARY_FILE"
echo ""
echo "Summary saved to: $SUMMARY_FILE"
echo ""
echo "=========================================="
echo "Log collection completed"
echo "=========================================="

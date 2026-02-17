#!/bin/bash

folder=$1   #bug files folder (e.g., in-ftp-bugs)
pno=$2      #port number
step=$3     #not used for bug replay, kept for compatibility
logfile=$4  #path to log summary file (CSV format)
fmode=$5    #file mode -- structured or not
            #fmode = 0: the test case is a concatenated message sequence -- there is no message boundary
            #fmode = 1: the test case is a structured file keeping several request messages

# Get absolute path of logfile directory for logs
LOGS_DIR=$(dirname "$logfile")/logs
mkdir -p $LOGS_DIR

# Delete and create the log summary file
rm -f $logfile; touch $logfile

# Output the header of the log file which is in the CSV format
# BugFile: bug file name, Status: exit status, LogFile: path to individual log file
echo "BugFile,Status,LogFile,Timestamp" >> $logfile

# Create necessary directories for ProFTPD (do this once at the beginning)
mkdir -p /usr/local/var
mkdir -p /home/ubuntu/ftpshare

# Files stored in replayable-* folders are structured
# In such a way that messages are separated
# For bug replay, we assume files are structured (from fuzzer output)
# So we use aflnet-replay by default, but check if file exists
if [ $fmode -eq "1" ]; then
  replayer="aflnet-replay"
else
  replayer="afl-replay"
fi

# Check if replayer exists in PATH, if not try to find it
if ! command -v $replayer &> /dev/null; then
  # Try to find replayer in common fuzzer directories
  for fuzzer_dir in aflnet chatafl xpgfuzz; do
    if [ -f "/home/ubuntu/${fuzzer_dir}/${replayer}" ]; then
      replayer="/home/ubuntu/${fuzzer_dir}/${replayer}"
      echo "Found replayer at: $replayer"
      break
    fi
  done
fi

# Final check
if ! command -v $replayer &> /dev/null && [ ! -f "$replayer" ]; then
  echo "Error: Cannot find replayer tool: $replayer"
  echo "Please ensure the fuzzer tools are in PATH or provide full path"
  exit 1
fi

echo "Using replayer: $replayer"

# Process all bug files in the folder
echo "Processing bug files from: $folder"
echo "Using replayer: $replayer"
echo "Logs will be saved to: $LOGS_DIR"

# Check if folder exists
if [ ! -d "$folder" ]; then
  echo "Error: Bug folder does not exist: $folder"
  exit 1
fi

# Count total bug files
total_bugs=$(find "$folder" -type f 2>/dev/null | wc -l)
if [ "$total_bugs" -eq 0 ]; then
  echo "Warning: No bug files found in $folder"
  exit 0
fi

current=0

# Process each bug file
for f in $(find "$folder" -type f 2>/dev/null | sort); do
  current=$((current + 1))
  bug_name=$(basename "$f")
  log_file="${LOGS_DIR}/${bug_name}.log"
  timestamp=$(date +%s)
  
  echo "[$current/$total_bugs] Replaying bug: $bug_name"
  
  # Terminate running server(s) - exactly like cov_script.sh
  pkill proftpd 2>/dev/null
  
  # Clear ftp data - exactly like cov_script.sh
  rm /home/ubuntu/ftpshare/*
  
  # Create necessary directories for ProFTPD (fixes mod_delay error)
  mkdir -p /usr/local/var
  
  # Set proper permissions for gcov files (if using gcov build) - exactly like cov_script.sh
  if [ -d "${WORKDIR}/proftpd-gcov" ]; then
    chown -R ubuntu:ubuntu /home/ubuntu/experiments/proftpd-gcov/{src,lib,modules} 2>/dev/null
    chmod -R go+rw /home/ubuntu/experiments/proftpd-gcov/{src,lib,modules} 2>/dev/null
  fi
  
  # Change to proftpd directory - exactly like cov_script.sh
  cd ${WORKDIR}/proftpd
  
  # Set ASAN_OPTIONS exactly like in Dockerfile (fuzzing environment)
  # Note: AFL uses setenv(..., 0) which does NOT override existing ASAN_OPTIONS
  # So during fuzzing, the ASAN_OPTIONS from Dockerfile are used
  # This ensures the replay environment matches the fuzzing environment exactly
  export ASAN_OPTIONS="abort_on_error=1:symbolize=0:detect_leaks=0:detect_stack_use_after_return=1:detect_container_overflow=0:poison_array_cookie=0:malloc_fill_byte=0:max_malloc_fill_size=16777216"
  
  # Add debug info to log
  echo "=== Bug Replay Start ===" >> "$log_file"
  echo "Bug file: $f" >> "$log_file"
  echo "Replayer: $replayer" >> "$log_file"
  echo "Port: $pno" >> "$log_file"
  echo "Working directory: $(pwd)" >> "$log_file"
  echo "ASAN_OPTIONS: $ASAN_OPTIONS" >> "$log_file"
  
  # Start replayer FIRST in background (like cov_script.sh line 42)
  # Capture replayer output to log file
  echo "=== Starting replayer ===" >> "$log_file"
  $replayer "$f" FTP $pno 1 >> "$log_file" 2>&1 &
  REPLAYER_PID=$!
  echo "Replayer PID: $REPLAYER_PID" >> "$log_file"
  
  # Then start server in foreground with timeout (exactly like cov_script.sh line 43)
  # Note: The UID error is just a warning, server can still run in --enable-devel mode
  # Capture server output to log file (cov_script.sh redirects to /dev/null)
  echo "=== Starting ProFTPD server ===" >> "$log_file"
  timeout -k 1s 10s ./proftpd -n -c ${WORKDIR}/basic.conf -X >> "$log_file" 2>&1
  SERVER_EXIT_CODE=$?
  echo "=== Server exited with code: $SERVER_EXIT_CODE ===" >> "$log_file"
  
  # Wait for both processes - exactly like cov_script.sh line 45
  wait
  
  # Check if server crashed (non-zero exit or signal)
  STATUS=0
  if [ -f "$log_file" ]; then
    # Check for crash indicators in log
    if grep -q "SIGSEGV\|SIGABRT\|SIGFPE\|AddressSanitizer\|Segmentation fault" "$log_file" 2>/dev/null; then
      STATUS=1
    fi
    # Check server exit code - if it was killed by signal (>= 128), might be a crash
    if [ $SERVER_EXIT_CODE -ge 128 ]; then
      # Server was killed by signal, check if it's a crash
      SIGNAL=$((SERVER_EXIT_CODE - 128))
      if [ $SIGNAL -eq 9 ] || [ $SIGNAL -eq 15 ]; then
        # SIGKILL (9) or SIGTERM (15) - likely timeout, not a crash
        :
      else
        # Other signals might indicate a crash
        STATUS=1
      fi
    fi
  fi
  
  # Record in summary (use relative path for log_file)
  log_file_rel="logs/${bug_name}.log"
  echo "$bug_name,$STATUS,$log_file_rel,$timestamp" >> $logfile
  
  # Clean up for next iteration
  rm -rf /home/ubuntu/ftpshare/*
done

echo "Bug replay completed. Processed $total_bugs bug files."
echo "Logs saved in: $LOGS_DIR"
echo "Summary saved in: $logfile"


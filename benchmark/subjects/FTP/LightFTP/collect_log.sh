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

# Clear ftp data
# This is a LightFTP-specific step
# We need to clean the ftp shared folder to prevent underterministic behaviors.
ftpclean

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
  
  # Terminate running server(s)
  pkill -9 fftp 2>/dev/null
  sleep 0.5
  
  # Clear ftp data
  ftpclean
  
  # Start server in background and capture output
  # Use timeout to ensure server doesn't hang forever
  timeout -k 1s -s SIGKILL 10s ./fftp fftp.conf $pno > "$log_file" 2>&1 &
  SERVER_PID=$!
  sleep 1
  
  # Replay the bug
  $replayer "$f" FTP $pno 1 >> "$log_file" 2>&1
  
  # Wait a bit for server to process
  sleep 2
  
  # Terminate server
  kill -9 $SERVER_PID 2>/dev/null
  pkill -9 fftp 2>/dev/null
  wait $SERVER_PID 2>/dev/null
  
  # Check if server crashed (non-zero exit or signal)
  STATUS=0
  if [ -f "$log_file" ]; then
    # Check for crash indicators in log
    if grep -q "SIGSEGV\|SIGABRT\|SIGFPE\|AddressSanitizer\|Segmentation fault" "$log_file" 2>/dev/null; then
      STATUS=1
    fi
  fi
  
  # Record in summary (use relative path for log_file)
  log_file_rel="logs/${bug_name}.log"
  echo "$bug_name,$STATUS,$log_file_rel,$timestamp" >> $logfile
  
  # Clean up for next iteration
  ftpclean
done

echo "Bug replay completed. Processed $total_bugs bug files."
echo "Logs saved in: $LOGS_DIR"
echo "Summary saved in: $logfile"

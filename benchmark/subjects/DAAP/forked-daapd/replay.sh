#!/bin/bash

# Replay script for crashes and hangs with log collection
# This script runs inside docker container, similar to run.sh

FUZZER=$1        #fuzzer name (e.g., aflnet) -- determines file mode
OUTDIR=$2        #name of the output folder containing crashes/hangs
PORT=$3          #port number (default: 3689)
LOGDIR=$4        #log directory name (default: logs)

# Set defaults
if [ -z "$PORT" ]; then
  PORT=3689
fi

if [ -z "$LOGDIR" ]; then
  LOGDIR="logs"
fi

WORKDIR="/home/ubuntu/experiments"

strstr() {
  [ "${1#*$2*}" = "$1" ] && return 1
  return 0
}

#Network deamons needed by forked-daapd
sudo /etc/init.d/dbus start
sudo /etc/init.d/avahi-daemon start

sudo /etc/init.d/dbus status
if [ $? -ne 0 ]
then
  echo "Unable to run DBUS"
  exit 1
fi

sudo /etc/init.d/avahi-daemon status
if [ $? -ne 0 ]
then
  echo "Unable to run AVAHI daemon"
  exit 1
fi

#Commands for afl-based fuzzers (e.g., aflnet, aflnwe)
if $(strstr $FUZZER "afl") || $(strstr $FUZZER "llm") || $(strstr $FUZZER "xpgfuzz"); then

  # Run fuzzer-specific commands (if any)
  if [ -e ${WORKDIR}/run-${FUZZER} ]; then
    source ${WORKDIR}/run-${FUZZER}
  fi

  TARGET_DIR=${TARGET_DIR:-"forked-daapd"}

  # Determine file mode based on fuzzer
  # 0: concatenated message sequence (aflnwe)
  # 1: structured file with message boundaries (aflnet, chatafl, xpgfuzz)
  if [ $FUZZER = "aflnwe" ]; then
    fmode=0
  else
    fmode=1
  fi

  # Create log directory
  mkdir -p ${WORKDIR}/${OUTDIR}/${LOGDIR}

  # Set up directories and replayer based on file mode
  if [ $fmode -eq "1" ]; then
    crashdir="replayable-crashes"
    hangdir="replayable-hangs"
    replayer="aflnet-replay"
  else
    crashdir="crashes"
    hangdir="hangs"
    replayer="afl-replay"
  fi

  # Function to replay a test case and collect logs
  replay_testcase() {
    local testfile=$1
    local testtype=$2  # "crash" or "hang"
    
    # Extract test case ID from filename
    local basename=$(basename $testfile)
    local logfile="${WORKDIR}/${OUTDIR}/${LOGDIR}/${testtype}_${basename}.log"
    
    echo "=========================================="
    echo "Replaying: $testfile"
    echo "Type: $testtype"
    echo "Log: $logfile"
    echo "=========================================="
    
    # Clear previous log
    > $logfile
    
    # Start replay in background and capture output
    (sleep 1 && $replayer $testfile HTTP $PORT 100 10000 >> $logfile 2>&1) &
    local replay_pid=$!
    
    # Run target with timeout and capture all output
    timeout -k 1s -s SIGUSR1 10s ${WORKDIR}/${TARGET_DIR}/src/forked-daapd -d 0 -c ${WORKDIR}/forked-daapd.conf -f >> $logfile 2>&1
    local exit_code=$?
    
    wait $replay_pid 2>/dev/null
    wait
    
    # Append exit status to log
    echo "" >> $logfile
    echo "=== Exit Status: $exit_code ===" >> $logfile
    echo "=== Test Type: $testtype ===" >> $logfile
    echo "=== Timestamp: $(date) ===" >> $logfile
    echo "=== Test File: $testfile ===" >> $logfile
    
    if [ $exit_code -ge 128 ]; then
      echo "Terminated with signal: $exit_code"
    fi
    
    echo ""
  }

  # Process crashes
  echo "Processing crashes..."
  count=0
  crash_dir="${WORKDIR}/${OUTDIR}/${crashdir}"
  if [ -d "$crash_dir" ]; then
    for f in $(echo $crash_dir/id* | grep -v "*"); do
      if [ -f "$f" ]; then
        replay_testcase "$f" "crash"
        count=$(expr $count + 1)
      fi
    done
  fi

  echo "Processed $count crash test cases"

  # Process hangs
  echo ""
  echo "Processing hangs..."
  hang_count=0
  hang_dir="${WORKDIR}/${OUTDIR}/${hangdir}"
  if [ -d "$hang_dir" ]; then
    for f in $(echo $hang_dir/id* | grep -v "*"); do
      if [ -f "$f" ]; then
        replay_testcase "$f" "hang"
        hang_count=$(expr $hang_count + 1)
      fi
    done
  fi

  echo "Processed $hang_count hang test cases"
  echo ""
  echo "Total: $count crashes, $hang_count hangs"
  echo "Logs saved to: ${WORKDIR}/${OUTDIR}/${LOGDIR}/"

  # Generate summary file
  summary_file="${WORKDIR}/${OUTDIR}/${LOGDIR}/summary.txt"
  echo "Replay Summary" > $summary_file
  echo "Generated: $(date)" >> $summary_file
  echo "Fuzzer: $FUZZER" >> $summary_file
  echo "Output Directory: $OUTDIR" >> $summary_file
  echo "File Mode: $fmode" >> $summary_file
  echo "" >> $summary_file
  echo "Crashes: $count" >> $summary_file
  echo "Hangs: $hang_count" >> $summary_file
  echo "Total: $(expr $count + $hang_count)" >> $summary_file

  exit 0
fi


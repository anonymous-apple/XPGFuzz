#!/bin/bash

FUZZER=$1     #fuzzer name (e.g., aflnet) -- this name must match the name of the fuzzer folder inside the Docker container
OUTDIR=$2     #name of the output folder
OPTIONS=$3    #all configured options -- to make it flexible, we only fix some options (e.g., -i, -o, -N) in this script
TIMEOUT=$4    #time for fuzzing
SKIPCOUNT=$5  #used for calculating cov over time. e.g., SKIPCOUNT=5 means we run gcovr after every 5 test cases

strstr() {
  [ "${1#*$2*}" = "$1" ] && return 1
  return 0
}

#Commands for afl-based fuzzers (e.g., aflnet, aflnwe)
if $(strstr $FUZZER "afl") || $(strstr $FUZZER "llm") || $(strstr $FUZZER "xpgfuzz"); then

  TARGET_DIR=${TARGET_DIR:-"live"}
  if $(strstr $FUZZER "aflnet+s1"); then
    INPUTS=${WORKDIR}/live555-2026-1-4
  elif $(strstr $FUZZER "xpgfuzz"); then
    INPUTS=${WORKDIR}/live555-2026-1-4
  else 
    INPUTS=${WORKDIR}/in-rtsp
  fi

  # Run fuzzer-specific commands (if any)
  if [ -e ${WORKDIR}/run-${FUZZER} ]; then
    source ${WORKDIR}/run-${FUZZER}
  fi

  #Step-1. Do Fuzzing
  #Move to fuzzing folder
  cd $WORKDIR/${TARGET_DIR}/testProgs
  # Add -b option for xpgfuzz to enable MAB by default (aflnet+s1 doesn't need -b)
  if $(strstr $FUZZER "xpgfuzz") && ! $(strstr $FUZZER "aflnet+s1"); then
    timeout -k 2s --preserve-status $TIMEOUT /home/ubuntu/${FUZZER}/afl-fuzz -b -d -i ${INPUTS} -x ${WORKDIR}/rtsp_xpgfuzz.dict -o $OUTDIR -N tcp://127.0.0.1/8554 $OPTIONS ./testOnDemandRTSPServer 8554
  else
    timeout -k 2s --preserve-status $TIMEOUT /home/ubuntu/${FUZZER}/afl-fuzz -d -i ${INPUTS} -x ${WORKDIR}/rtsp.dict -o $OUTDIR -N tcp://127.0.0.1/8554 $OPTIONS ./testOnDemandRTSPServer 8554
  fi

  STATUS=$?

  #Step-2. Collect code coverage over time
  #Move to gcov folder
  cd $WORKDIR/live-gcov/testProgs

  #The last argument passed to cov_script should be 0 if the fuzzer is afl/nwe and it should be 1 if the fuzzer is based on aflnet
  #0: the test case is a concatenated message sequence -- there is no message boundary
  #1: the test case is a structured file keeping several request messages
  if [ $FUZZER == "aflnwe" ]; then
    cov_script ${WORKDIR}/${TARGET_DIR}/testProgs/${OUTDIR}/ 8554 ${SKIPCOUNT} ${WORKDIR}/${TARGET_DIR}/testProgs/${OUTDIR}/cov_over_time.csv 0
  else
    cov_script ${WORKDIR}/${TARGET_DIR}/testProgs/${OUTDIR}/ 8554 ${SKIPCOUNT} ${WORKDIR}/${TARGET_DIR}/testProgs/${OUTDIR}/cov_over_time.csv 1
  fi

  cd $WORKDIR/live-gcov
  #copy .hh files since gcovr could not detect them
  for f in BasicUsageEnvironment liveMedia groupsock UsageEnvironment; do
    echo $f
    cp $f/include/*.hh $f/
  done
  cd testProgs

  gcovr -r .. --html --html-details -o index.html
  mkdir ${WORKDIR}/${TARGET_DIR}/testProgs/${OUTDIR}/cov_html/
  cp *.html ${WORKDIR}/live/testProgs/${OUTDIR}/cov_html/

  #Step-2.5. Reproduce crashes and deduplicate
  #Note: This step is optional and failures will not affect data collection
  #Save original STATUS to ensure fuzzing status is preserved
  ORIGINAL_STATUS=$STATUS
  
  #Move back to fuzzing folder for crash reproduction
  cd ${WORKDIR}/${TARGET_DIR}/testProgs || {
    echo "[!] Warning: Failed to change directory, skipping crash analysis"
    STATUS=$ORIGINAL_STATUS
  }
  
  if [ $STATUS -eq $ORIGINAL_STATUS ]; then
    # Determine replay binary based on fuzzer type
    if [ $FUZZER == "aflnwe" ]; then
      REPLAY_BIN="/home/ubuntu/${FUZZER}/afl-replay"
    else
      REPLAY_BIN="/home/ubuntu/${FUZZER}/aflnet-replay"
    fi
    
    # Check if replayable-crashes directory exists and has files
    CRASH_DIR="${OUTDIR}/replayable-crashes"
    REPORT_TXT="${OUTDIR}/crash_first_seen/report.txt"
    FUZZER_STATS="${OUTDIR}/fuzzer_stats"
    
    # Use set +e to prevent errors from affecting the script
    set +e
    
    # Step-2.5.1: First run crash_timing.py (if report.txt already exists)
    if [ -f "$REPORT_TXT" ] && [ -f "$FUZZER_STATS" ]; then
      echo "[*] Step 1: Running crash_timing.py on existing report.txt..."
      python3 ${WORKDIR}/crash_timing.py \
        --out-dir ${OUTDIR} \
        --fuzzer-stats ${FUZZER_STATS} \
        --report ${REPORT_TXT} 2>&1
    
      if [ $? -eq 0 ]; then
        echo "[*] crash_timing.py completed successfully"
      else
        echo "[!] Warning: crash_timing.py failed, but continuing..."
      fi
    else
      echo "[*] Step 1: Skipping crash_timing.py (report.txt or fuzzer_stats not found)"
    fi
    
    # Step-2.5.2: Then run first_seen_crash.py to reproduce crashes and deduplicate (if crashes exist)
    if [ -d "$CRASH_DIR" ] && [ "$(ls -A "$CRASH_DIR" 2>/dev/null)" ]; then
      echo "[*] Step 2: Running first_seen_crash.py for crash reproduction and deduplication..."
      
      # Run first_seen_crash.py to reproduce crashes and deduplicate
      python3 ${WORKDIR}/first_seen_crash.py \
        --out-dir ${OUTDIR} \
        --subdir replayable-crashes \
        --proto RTSP \
        --port 8554 \
        --host 127.0.0.1 \
        --server-cmd "./testOnDemandRTSPServer 8554" \
        --replay-bin ${REPLAY_BIN} \
        --server-start-timeout 2.0 \
        --replay-timeout 5.0 \
        --server-grace 1.0 \
        --tz UTC \
        --seed-regex '^id:' 2>&1
      
      CRASH_REPRO_STATUS=$?
      if [ $CRASH_REPRO_STATUS -eq 0 ]; then
        echo "[*] first_seen_crash.py completed successfully"
        
        # Step-2.5.3: Run crash_timing.py again after generating/updating report.txt
        if [ -f "$REPORT_TXT" ] && [ -f "$FUZZER_STATS" ]; then
          echo "[*] Step 3: Running crash_timing.py again on updated report.txt..."
          python3 ${WORKDIR}/crash_timing.py \
            --out-dir ${OUTDIR} \
            --fuzzer-stats ${FUZZER_STATS} \
            --report ${REPORT_TXT} 2>&1
          
          if [ $? -eq 0 ]; then
            echo "[*] crash_timing.py completed successfully"
          else
            echo "[!] Warning: crash_timing.py failed, but continuing..."
          fi
        else
          echo "[!] Warning: Missing fuzzer_stats or report.txt after first_seen_crash.py, skipping crash timing analysis"
        fi
      else
        echo "[!] Warning: first_seen_crash.py failed (exit code: $CRASH_REPRO_STATUS), but continuing..."
      fi
    else
      echo "[*] Step 2: No replayable crashes found, skipping first_seen_crash.py"
    fi
    set -e
    
    # Restore original STATUS - crash analysis failures should not affect fuzzing status
    STATUS=$ORIGINAL_STATUS
  fi
  
  echo "[*] Crash analysis step completed (failures are non-fatal)"

  #Step-3. Save the result to the ${WORKDIR} folder
  #Tar all results to a file
  #Ensure this step always executes regardless of crash analysis failures
  echo "[*] Saving results to tar archive..."
  cd ${WORKDIR}/${TARGET_DIR}/testProgs || {
    echo "[!] Error: Failed to change to testProgs directory"
    exit $STATUS
  }
  
  # Tar the results - this should always succeed if directory exists
  if [ -d "${OUTDIR}" ]; then
    tar -zcvf ${WORKDIR}/${OUTDIR}.tar.gz ${OUTDIR} || {
      echo "[!] Warning: Failed to create tar archive, but continuing..."
    }
    echo "[*] Results saved to ${WORKDIR}/${OUTDIR}.tar.gz"
  else
    echo "[!] Warning: Output directory ${OUTDIR} not found, skipping tar"
  fi

  # Exit with original fuzzing status - crash analysis failures should not affect this
  exit $STATUS
fi

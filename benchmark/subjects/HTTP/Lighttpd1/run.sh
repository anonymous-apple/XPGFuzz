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

  # # Run fuzzer-specific commands (if any)
  # if [ -e ${WORKDIR}/run-${FUZZER} ]; then
  #   source ${WORKDIR}/run-${FUZZER}
  # fi

  TARGET_DIR=${TARGET_DIR:-"lighttpd1"}  #小写
  if $(strstr $FUZZER "aflnet+s1"); then
    INPUTS=${WORKDIR}/in-http-1-5-agent
  elif $(strstr $FUZZER "xpgfuzz"); then
    INPUTS=${WORKDIR}/in-http-1-5-agent
  else 
    INPUTS=${WORKDIR}/in-http
  fi

  #Step-1. Do Fuzzing
  #Move to fuzzing folder
  cd $WORKDIR/${TARGET_DIR}/
  # Add -b option for xpgfuzz to enable MAB by default (aflnet+s1 doesn't need -b)
  if $(strstr $FUZZER "xpgfuzz") && ! $(strstr $FUZZER "aflnet+s1"); then
    timeout -k 2s --preserve-status $TIMEOUT /home/ubuntu/${FUZZER}/afl-fuzz -b -d -i ${INPUTS} -x ${WORKDIR}/http.dict -o $OUTDIR -N tcp://127.0.0.1/8080 $OPTIONS ./src/lighttpd -D -f ${WORKDIR}/lighttpd.conf -m $PWD/src/.libs
  else
    timeout -k 2s --preserve-status $TIMEOUT /home/ubuntu/${FUZZER}/afl-fuzz -d -i ${INPUTS}  -o $OUTDIR -N tcp://127.0.0.1/8080 $OPTIONS ./src/lighttpd -D -f ${WORKDIR}/lighttpd.conf -m $PWD/src/.libs
  fi

  STATUS=$?

  #Step-2. Collect code coverage over time
  #Move to gcov folder
  cd $WORKDIR/lighttpd1-gcov/

  #The last argument passed to cov_script should be 0 if the fuzzer is afl/nwe and it should be 1 if the fuzzer is based on aflnet
  #0: the test case is a concatenated message sequence -- there is no message boundary
  #1: the test case is a structured file keeping several request messages
  if [ $FUZZER == "aflnwe" ]; then
    cov_script ${WORKDIR}/${TARGET_DIR}/${OUTDIR}/ 8080 ${SKIPCOUNT} ${WORKDIR}/${TARGET_DIR}/${OUTDIR}/cov_over_time.csv 0
  else
    cov_script ${WORKDIR}/${TARGET_DIR}/${OUTDIR}/ 8080 ${SKIPCOUNT} ${WORKDIR}/${TARGET_DIR}/${OUTDIR}/cov_over_time.csv 1
  fi

  cd $WORKDIR/lighttpd1-gcov
  #copy .hh files since gcovr could not detect them

  gcovr -r .. --html --html-details -o index.html
  mkdir ${WORKDIR}/${TARGET_DIR}/${OUTDIR}/cov_html/
  cp *.html ${WORKDIR}/${TARGET_DIR}/${OUTDIR}/cov_html/

  #Step-2.5. Reproduce crashes and deduplicate (non-fatal)
  ORIGINAL_STATUS=$STATUS
  cd ${WORKDIR}/${TARGET_DIR}/ || {
    echo "[!] Warning: Failed to change directory, skipping crash analysis"
    STATUS=$ORIGINAL_STATUS
  }

  if [ $STATUS -eq $ORIGINAL_STATUS ]; then
    if [ $FUZZER == "aflnwe" ]; then
      REPLAY_BIN="/home/ubuntu/${FUZZER}/afl-replay"
      CRASH_SUBDIR="crashes"
    else
      REPLAY_BIN="/home/ubuntu/${FUZZER}/aflnet-replay"
      CRASH_SUBDIR="replayable-crashes"
    fi

    CRASH_DIR="${OUTDIR}/${CRASH_SUBDIR}"
    REPORT_TXT="${OUTDIR}/crash_first_seen/report.txt"
    FUZZER_STATS="${OUTDIR}/fuzzer_stats"

    set +e

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

    if [ -d "$CRASH_DIR" ] && [ "$(ls -A "$CRASH_DIR" 2>/dev/null)" ]; then
      echo "[*] Step 2: Running first_seen_crash.py for crash reproduction and deduplication..."

      python3 ${WORKDIR}/first_seen_crash.py \
        --out-dir ${OUTDIR} \
        --subdir ${CRASH_SUBDIR} \
        --proto HTTP \
        --port 8080 \
        --host 127.0.0.1 \
        --server-cmd "./src/lighttpd -D -f ${WORKDIR}/lighttpd.conf -m $PWD/src/.libs" \
        --replay-bin ${REPLAY_BIN} \
        --server-start-timeout 2.0 \
        --replay-timeout 5.0 \
        --server-grace 1.0 \
        --tz UTC \
        --seed-regex '^id:' 2>&1

      CRASH_REPRO_STATUS=$?
      if [ $CRASH_REPRO_STATUS -eq 0 ]; then
        echo "[*] first_seen_crash.py completed successfully"

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

    STATUS=$ORIGINAL_STATUS
  fi

  echo "[*] Crash analysis step completed (failures are non-fatal)"

  #Step-3. Save the result to the ${WORKDIR} folder
  #Tar all results to a file
  cd ${WORKDIR}/${TARGET_DIR}/
  tar -zcvf ${WORKDIR}/${OUTDIR}.tar.gz ${OUTDIR}

  exit $STATUS
fi

#!/bin/bash

FUZZER=$1     #fuzzer name (e.g., aflnet) -- this name must match the name of the fuzzer folder inside the Docker container
OUTDIR=$2     #name of the output folder
OPTIONS=$3    #all configured options -- not used for bug replay, kept for compatibility
TIMEOUT=$4    #timeout for each bug replay (not used for fuzzing)
SKIPCOUNT=$5  #not used for bug replay, kept for compatibility

strstr() {
  [ "${1#*$2*}" = "$1" ] && return 1
  return 0
}

#Commands for afl-based fuzzers (e.g., aflnet, aflnwe)
if $(strstr $FUZZER "afl") || $(strstr $FUZZER "llm") || $(strstr $FUZZER "xpgfuzz"); then

  # Run fuzzer-specific commands (if any)
  if [ -e ${WORKDIR}/run-${FUZZER} ]; then
    source ${WORKDIR}/run-${FUZZER}
  fi

  TARGET_DIR=${TARGET_DIR:-"LightFTP"}
  
  #Step-1. Create output directory for bug replay logs
  cd $WORKDIR/${TARGET_DIR}/Source/Release
  mkdir -p ${OUTDIR}
  mkdir -p ${OUTDIR}/logs
  
  echo "Starting bug replay for LightFTP"
  echo "Bug files location: ${WORKDIR}/in-ftp-bugs"
  echo "Output directory: ${WORKDIR}/${TARGET_DIR}/Source/Release/${OUTDIR}"

  #Step-2. Replay bugs and collect logs
  # Use collect_log to replay all bugs in in-ftp-bugs directory
  # collect_log will handle the replay and log collection
  cd $WORKDIR/${TARGET_DIR}/Source/Release
  collect_log ${WORKDIR}/in-ftp-bugs 2200 1 ${OUTDIR}/bug_replay_logs.csv 1

  STATUS=$?

  #Step-3. Save the result to the ${WORKDIR} folder
  #Tar all results to a file
  cd ${WORKDIR}/${TARGET_DIR}/Source/Release
  tar -zcvf ${WORKDIR}/${OUTDIR}.tar.gz ${OUTDIR}

  exit $STATUS
fi
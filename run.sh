#!/bin/bash

PFBENCH="$PWD/benchmark"
cd $PFBENCH

PATH=$PATH:$PFBENCH/scripts/execution:$PFBENCH/scripts/analysis
NUM_CONTAINERS=$1
TIMEOUT=$(( ${2:-1440} * 60))
SKIPCOUNT="${SKIPCOUNT:-1}"
TEST_TIMEOUT="${TEST_TIMEOUT:-5000}"

export TARGET_LIST=$3
export FUZZER_LIST=$4

if [[ "x$NUM_CONTAINERS" == "x" ]] || [[ "x$TIMEOUT" == "x" ]] || [[ "x$TARGET_LIST" == "x" ]] || [[ "x$FUZZER_LIST" == "x" ]]
then
    echo "Usage: $0 NUM_CONTAINERS TIMEOUT TARGET FUZZER [IMAGE_DATE]"
    echo ""
    echo "Arguments:"
    echo "  NUM_CONTAINERS: Number of containers to run"
    echo "  TIMEOUT: Timeout in minutes"
    echo "  TARGET: Protocol name (e.g., lighttpd1, bftpd, exim) or 'all'"
    echo "  FUZZER: Fuzzer name (e.g., xpgfuzz, aflnet, chatafl, aflnet+s1) or 'all'"
    echo ""
    echo "Environment variables:"
    echo "  IMAGE_DATE: Image date in MM-DD format (e.g., 12-5)"
    echo "              If not set, uses current date"
    echo ""
    echo "Examples:"
    echo "  # Use current date for images"
    echo "  $0 10 1440 lighttpd1 xpgfuzz"
    echo ""
    echo "  # Use images from December 5th"
    echo "  IMAGE_DATE=12-5 $0 10 1440 lighttpd1 xpgfuzz"
    exit 1
fi

PFBENCH=$PFBENCH PATH=$PATH NUM_CONTAINERS=$NUM_CONTAINERS TIMEOUT=$TIMEOUT SKIPCOUNT=$SKIPCOUNT TEST_TIMEOUT=$TEST_TIMEOUT IMAGE_DATE="${IMAGE_DATE}" scripts/execution/profuzzbench_exec_all.sh ${TARGET_LIST} ${FUZZER_LIST}
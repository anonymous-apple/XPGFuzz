#!/bin/bash

PFBENCH="$PWD/benchmark"
cd $PFBENCH

PATH=$PATH:$PFBENCH/scripts/execution:$PFBENCH/scripts/analysis
NUM_CONTAINERS=$1
TIMEOUT=$(( ${2:-60} * 60))  # Default 60 minutes for bug replay
SKIPCOUNT="${SKIPCOUNT:-1}"
TEST_TIMEOUT="${TEST_TIMEOUT:-20000}"

export TARGET_LIST=$3
export FUZZER_LIST=$4

if [[ "x$NUM_CONTAINERS" == "x" ]] || [[ "x$TIMEOUT" == "x" ]] || [[ "x$TARGET_LIST" == "x" ]] || [[ "x$FUZZER_LIST" == "x" ]]
then
    echo "Usage: $0 NUM_CONTAINERS TIMEOUT TARGET FUZZER [IMAGE_DATE]"
    echo ""
    echo "Arguments:"
    echo "  NUM_CONTAINERS: Number of containers to run (usually 1 for bug replay)"
    echo "  TIMEOUT: Timeout in minutes (default: 60)"
    echo "  TARGET: Protocol name (e.g., lightftp) or 'all'"
    echo "  FUZZER: Fuzzer name (e.g., xpgfuzz, aflnet, chatafl) or 'all'"
    echo ""
    echo "Environment variables:"
    echo "  IMAGE_DATE: Image date in MM-DD format (e.g., 12-5)"
    echo "              If not set, uses current date"
    echo ""
    echo "Examples:"
    echo "  # Replay bugs for lightftp with xpgfuzz"
    echo "  $0 1 60 lightftp xpgfuzz"
    echo ""
    echo "  # Use images from December 5th"
    echo "  IMAGE_DATE=12-5 $0 1 60 lightftp xpgfuzz"
    exit 1
fi

PFBENCH=$PFBENCH PATH=$PATH NUM_CONTAINERS=$NUM_CONTAINERS TIMEOUT=$TIMEOUT SKIPCOUNT=$SKIPCOUNT TEST_TIMEOUT=$TEST_TIMEOUT IMAGE_DATE="${IMAGE_DATE}" scripts/execution/profuzzbench_replay_all.sh ${TARGET_LIST} ${FUZZER_LIST}


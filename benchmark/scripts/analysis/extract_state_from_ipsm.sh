#!/bin/bash
# Extract state data from ipsm.dot files when plot_data is empty
# This is a workaround for fuzzers that don't write to plot_data

prog=$1
fuzzer=$2
run_index=$3
ifile=$4  # ipsm.dot file
ofile=$5  # states.csv file

# Count nodes and edges from ipsm.dot
if [ -f "$ifile" ]; then
    # Count unique node IDs (lines starting with a number)
    nodes=$(grep -E "^[[:space:]]*[0-9]+[[:space:]]*\[" "$ifile" | wc -l)
    
    # Count edges (lines containing "->")
    edges=$(grep -c "->" "$ifile" 2>/dev/null || echo "0")
    
    # Get current time
    current_time=$(date +%s)
    
    # Append to states.csv
    echo "$current_time,$prog,$fuzzer,$run_index,nodes,$nodes" >> "$ofile"
    echo "$current_time,$prog,$fuzzer,$run_index,edges,$edges" >> "$ofile"
    
    echo "Extracted from ipsm.dot: nodes=$nodes, edges=$edges"
else
    echo "Warning: $ifile not found"
fi


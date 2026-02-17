#!/bin/bash

DOCIMAGE=$1   #name of the docker image
RUNS=$2       #number of runs
SAVETO=$3     #path to folder keeping the results

FUZZER=$4     #fuzzer name (e.g., aflnet) -- this name must match the name of the fuzzer folder inside the Docker container
OUTDIR=$5     #name of the output folder created inside the docker container
OPTIONS=$6    #all configured options for fuzzing
TIMEOUT=$7    #time for fuzzing
SKIPCOUNT=$8  #used for calculating coverage over time. e.g., SKIPCOUNT=5 means we run gcovr after every 5 test cases
DELETE=$9

WORKDIR="/home/ubuntu/experiments"

# Convert SAVETO to absolute path if it's relative
# This ensures the path is correct regardless of where the script is called from
if [[ "$SAVETO" != /* ]]; then
  # If relative path, assume it's relative to PFBENCH (benchmark directory)
  # Try to find PFBENCH from environment or infer from script location
  if [ -n "$PFBENCH" ]; then
    SAVETO="$PFBENCH/$SAVETO"
  else
    # Infer PFBENCH from script location (assuming script is in benchmark/scripts/execution/)
    SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
    PFBENCH="$(cd "$SCRIPT_DIR/../.." && pwd)"
    SAVETO="$PFBENCH/$SAVETO"
  fi
fi

# Create the output directory if it doesn't exist
mkdir -p "$SAVETO"

# Generate container name: xpg-{月}-{日}-{协议}-replay-{fuzzer}-{随机哈希串}
# Extract protocol name from DOCIMAGE (e.g., xpg-12-5-lighttpd1-replay -> lighttpd1)
PROTOCOL=$(echo $DOCIMAGE | sed 's/^xpg-[0-9]*-[0-9]*-//' | sed 's/-replay$//')
MONTH=$(date +%-m)
DAY=$(date +%-d)
# Docker container names cannot include '+' (or other special chars).
# Keep FUZZER unchanged for in-container paths, but sanitize for container naming.
SAFE_FUZZER=$(echo "$FUZZER" | sed 's/[^a-zA-Z0-9_.-]/-/g')
CONTAINER_PREFIX="xpg-${MONTH}-${DAY}-${PROTOCOL}-${SAFE_FUZZER}"

#keep all container ids
cids=()

#create one container for each run
for i in $(seq 1 $RUNS); do
  # Generate unique random hash string (8 hex characters)
  # Retry if container name already exists
  MAX_RETRIES=10
  retry_count=0
  while [ $retry_count -lt $MAX_RETRIES ]; do
    RANDOM_HASH=$(openssl rand -hex 4)
    CONTAINER_NAME="${CONTAINER_PREFIX}-${RANDOM_HASH}"
    
    # Check if container name already exists
    if docker ps -a --format '{{.Names}}' | grep -q "^${CONTAINER_NAME}$"; then
      retry_count=$((retry_count + 1))
      if [ $retry_count -ge $MAX_RETRIES ]; then
        echo "Error: Failed to generate unique container name after ${MAX_RETRIES} attempts"
        exit 1
      fi
      continue
    fi
    
    # Container name is unique, create the container
    # Note: run_replay expects: FUZZER OUTDIR OPTIONS TIMEOUT SKIPCOUNT
    # Also, optionally copy in-ftp-bugs from host if it exists (for flexibility)
    id=$(docker run --name $CONTAINER_NAME --cpus=1 -d -it $DOCIMAGE /bin/bash -c "cd ${WORKDIR} && run_replay ${FUZZER} ${OUTDIR} '${OPTIONS}' ${TIMEOUT} ${SKIPCOUNT}")
    if [ $? -eq 0 ]; then
      cids+=(${id::12}) #store only the first 12 characters of a container ID
      break
    else
      # If docker run failed due to name conflict, retry
      retry_count=$((retry_count + 1))
      if [ $retry_count -ge $MAX_RETRIES ]; then
        echo "Error: Failed to create container after ${MAX_RETRIES} attempts"
        exit 1
      fi
    fi
  done
done

dlist="" #docker list
for id in ${cids[@]}; do
  dlist+=" ${id}"
done

#wait until all these dockers are stopped
printf "\n${FUZZER^^}: Bug replay in progress ..."
printf "\n${FUZZER^^}: Waiting for the following containers to stop: ${dlist}"
docker wait ${dlist} > /dev/null
wait

#collect the bug replay results from the containers
printf "\n${FUZZER^^}: Collecting results and save them to ${SAVETO}"
index=1
for id in ${cids[@]}; do
  printf "\n${FUZZER^^}: Collecting results from container ${id}"
  docker cp ${id}:/home/ubuntu/experiments/${OUTDIR}.tar.gz ${SAVETO}/${OUTDIR}_${index}.tar.gz > /dev/null
  if [ ! -z $DELETE ]; then
    printf "\nDeleting ${id}"
    docker rm ${id} # Remove container now that we don't need it
  fi
  index=$((index+1))
done

printf "\n${FUZZER^^}: I am done!\n"

#!/bin/bash

export NUM_CONTAINERS="${NUM_CONTAINERS:-10}"
export TIMEOUT="${TIMEOUT:-86400}"
export SKIPCOUNT="${SKIPCOUNT:-1}"
export TEST_TIMEOUT="${TEST_TIMEOUT:-20000}"

export TARGET_LIST=$1
export FUZZER_LIST=$2

if [[ "x$TARGET_LIST" == "x" ]] || [[ "x$FUZZER_LIST" == "x" ]]
then
    echo "Usage: $0 TARGET FUZZER"
    exit 1
fi

# Function to generate image name: xpg-月份-日-{协议}-replay
# If IMAGE_DATE is set (format: MM-DD), use it; otherwise use current date
# If the specified image doesn't exist, fallback to current date image
generate_image_name() {
    local protocol=$1
    local month
    local day
    local image_name
    local fallback_month
    local fallback_day
    local fallback_image_name
    
    if [ -n "$IMAGE_DATE" ]; then
        # IMAGE_DATE format: MM-DD (e.g., "12-5")
        month=$(echo $IMAGE_DATE | cut -d'-' -f1)
        day=$(echo $IMAGE_DATE | cut -d'-' -f2)
        image_name="xpg-${month}-${day}-${protocol}-replay"
        
        # Check if the specified image exists, if not, fallback to current date
        if ! docker images --format '{{.Repository}}:{{.Tag}}' | grep -q "^${image_name}:latest$"; then
            fallback_month=$(date +%-m)
            fallback_day=$(date +%-d)
            fallback_image_name="xpg-${fallback_month}-${fallback_day}-${protocol}-replay"
            
            # Check if fallback image exists
            if docker images --format '{{.Repository}}:{{.Tag}}' | grep -q "^${fallback_image_name}:latest$"; then
                echo "Warning: Image ${image_name}:latest not found, using ${fallback_image_name}:latest instead" >&2
                image_name="$fallback_image_name"
            else
                echo "Error: Neither ${image_name}:latest nor ${fallback_image_name}:latest found" >&2
                echo "Please build the image first or set IMAGE_DATE to match an existing image" >&2
                exit 1
            fi
        fi
    else
        # Use current date
        month=$(date +%-m)
        day=$(date +%-d)
        image_name="xpg-${month}-${day}-${protocol}-replay"
    fi
    
    echo "$image_name"
}

echo
echo "# NUM_CONTAINERS: ${NUM_CONTAINERS}"
echo "# TIMEOUT: ${TIMEOUT} s"
echo "# SKIPCOUNT: ${SKIPCOUNT}"
echo "# TEST TIMEOUT: ${TEST_TIMEOUT} ms"
echo "# TARGET LIST: ${TARGET_LIST}"
echo "# FUZZER LIST: ${FUZZER_LIST}"
if [ -n "$IMAGE_DATE" ]; then
    echo "# IMAGE DATE: ${IMAGE_DATE} (using images from this date)"
else
    echo "# IMAGE DATE: (using current date)"
fi
echo

for FUZZER in $(echo $FUZZER_LIST | sed "s/,/ /g")
do

    for TARGET in $(echo $TARGET_LIST | sed "s/,/ /g")
    do

        echo
        echo "***** REPLAYING BUGS FOR $FUZZER ON $TARGET *****"
        echo

##### FTP #####

        if [[ $TARGET == "lightftp" ]] || [[ $TARGET == "all" ]]
        then

            cd $PFBENCH
            mkdir -p results-lightftp-replay
            IMAGE_NAME=$(generate_image_name lightftp)

            if [[ $FUZZER == "aflnet" ]] || [[ $FUZZER == "all" ]]
            then
                profuzzbench_replay_common.sh $IMAGE_NAME $NUM_CONTAINERS results-lightftp-replay aflnet out-lightftp-aflnet-replay "" $TIMEOUT $SKIPCOUNT &
            fi

            if [[ $FUZZER == "chatafl" ]] || [[ $FUZZER == "all" ]]
            then
                profuzzbench_replay_common.sh $IMAGE_NAME $NUM_CONTAINERS results-lightftp-replay chatafl out-lightftp-chatafl-replay "" $TIMEOUT $SKIPCOUNT &
            fi

            if [[ $FUZZER == "xpgfuzz" ]] || [[ $FUZZER == "all" ]]
            then
                profuzzbench_replay_common.sh $IMAGE_NAME $NUM_CONTAINERS results-lightftp-replay xpgfuzz out-lightftp-xpgfuzz-replay "" $TIMEOUT $SKIPCOUNT &
            fi

            # aflnet+s1: seed-enrichment-only ablation variant
            if [[ $FUZZER == "aflnet+s1" ]] || [[ $FUZZER == "all" ]]
            then
                profuzzbench_replay_common.sh $IMAGE_NAME $NUM_CONTAINERS results-lightftp-replay aflnet+s1 out-lightftp-aflnet+s1-replay "" $TIMEOUT $SKIPCOUNT &
            fi
        fi


        if [[ $TARGET == "bftpd" ]] || [[ $TARGET == "all" ]]
        then

            cd $PFBENCH
            mkdir results-bftpd
            IMAGE_NAME=$(generate_image_name bftpd)

            if [[ $FUZZER == "aflnet" ]] || [[ $FUZZER == "all" ]]
            then
                profuzzbench_exec_common.sh $IMAGE_NAME $NUM_CONTAINERS results-bftpd aflnet out-bftpd-aflnet "-m none -P FTP -D 10000 -q 3 -s 3 -E -K -t ${TEST_TIMEOUT}+" $TIMEOUT $SKIPCOUNT &
            fi

            if [[ $FUZZER == "chatafl" ]] || [[ $FUZZER == "all" ]]
            then
                profuzzbench_exec_common.sh $IMAGE_NAME $NUM_CONTAINERS results-bftpd chatafl out-bftpd-chatafl "-m none -P FTP -D 10000 -q 3 -s 3 -E -K -t ${TEST_TIMEOUT}+" $TIMEOUT $SKIPCOUNT &
            fi

            if [[ $FUZZER == "xpgfuzz" ]] || [[ $FUZZER == "all" ]]
            then
                profuzzbench_exec_common.sh $IMAGE_NAME $NUM_CONTAINERS results-bftpd xpgfuzz out-bftpd-xpgfuzz "-P FTP -D 10000 -q 3 -s 3 -E -K -m none -t ${TEST_TIMEOUT}+" $TIMEOUT $SKIPCOUNT &
            fi

            if [[ $FUZZER == "aflnet+s1" ]] || [[ $FUZZER == "all" ]]
            then
                profuzzbench_exec_common.sh $IMAGE_NAME $NUM_CONTAINERS results-bftpd aflnet+s1 out-bftpd-aflnet+s1 "-P FTP -D 10000 -q 3 -s 3 -E -K -m none -t ${TEST_TIMEOUT}+" $TIMEOUT $SKIPCOUNT &
            fi
        fi


        if [[ $TARGET == "proftpd" ]] || [[ $TARGET == "all" ]]
        then

            cd $PFBENCH
            mkdir -p results-proftpd-replay
            IMAGE_NAME=$(generate_image_name proftpd)

            if [[ $FUZZER == "aflnet" ]] || [[ $FUZZER == "all" ]]
            then
                profuzzbench_replay_common.sh $IMAGE_NAME $NUM_CONTAINERS results-proftpd-replay aflnet out-proftpd-aflnet-replay "" $TIMEOUT $SKIPCOUNT &
            fi

            if [[ $FUZZER == "chatafl" ]] || [[ $FUZZER == "all" ]]
            then
                profuzzbench_replay_common.sh $IMAGE_NAME $NUM_CONTAINERS results-proftpd-replay chatafl out-proftpd-chatafl-replay "" $TIMEOUT $SKIPCOUNT &
            fi

            if [[ $FUZZER == "xpgfuzz" ]] || [[ $FUZZER == "all" ]]
            then
                profuzzbench_replay_common.sh $IMAGE_NAME $NUM_CONTAINERS results-proftpd-replay xpgfuzz out-proftpd-xpgfuzz-replay "" $TIMEOUT $SKIPCOUNT &
            fi

            if [[ $FUZZER == "aflnet+s1" ]] || [[ $FUZZER == "all" ]]
            then
                profuzzbench_replay_common.sh $IMAGE_NAME $NUM_CONTAINERS results-proftpd-replay aflnet+s1 out-proftpd-aflnet+s1-replay "" $TIMEOUT $SKIPCOUNT &
            fi
        fi

        if [[ $TARGET == "pure-ftpd" ]] || [[ $TARGET == "all" ]]
        then

            cd $PFBENCH
            mkdir results-pure-ftpd
            IMAGE_NAME=$(generate_image_name pure-ftpd)

            if [[ $FUZZER == "aflnet" ]] || [[ $FUZZER == "all" ]]
            then
                profuzzbench_exec_common.sh $IMAGE_NAME $NUM_CONTAINERS results-pure-ftpd aflnet out-pure-ftpd-aflnet "-m none -P FTP -D 10000 -q 3 -s 3 -E -K -t ${TEST_TIMEOUT}+" $TIMEOUT $SKIPCOUNT &
            fi

            if [[ $FUZZER == "chatafl" ]] || [[ $FUZZER == "all" ]]
            then
                profuzzbench_exec_common.sh $IMAGE_NAME $NUM_CONTAINERS results-pure-ftpd chatafl out-pure-ftpd-chatafl "-m none -P FTP -D 10000 -q 3 -s 3 -E -K -t ${TEST_TIMEOUT}+" $TIMEOUT $SKIPCOUNT &
            fi
            
            if [[ $FUZZER == "xpgfuzz" ]] || [[ $FUZZER == "all" ]]
            then
                profuzzbench_exec_common.sh $IMAGE_NAME $NUM_CONTAINERS results-pure-ftpd xpgfuzz out-pure-ftpd-xpgfuzz "-P FTP -D 10000 -q 3 -s 3 -E -K -m none -t ${TEST_TIMEOUT}+" $TIMEOUT $SKIPCOUNT &
            fi

            if [[ $FUZZER == "aflnet+s1" ]] || [[ $FUZZER == "all" ]]
            then
                profuzzbench_exec_common.sh $IMAGE_NAME $NUM_CONTAINERS results-pure-ftpd aflnet+s1 out-pure-ftpd-aflnet+s1 "-P FTP -D 10000 -q 3 -s 3 -E -K -m none -t ${TEST_TIMEOUT}+" $TIMEOUT $SKIPCOUNT &
            fi
        fi


##### SMTP #####

        if [[ $TARGET == "exim" ]] || [[ $TARGET == "all" ]]
        then

            cd $PFBENCH
            mkdir results-exim
            IMAGE_NAME=$(generate_image_name exim)

            if [[ $FUZZER == "aflnet" ]] || [[ $FUZZER == "all" ]]
            then
                profuzzbench_exec_common.sh $IMAGE_NAME $NUM_CONTAINERS results-exim aflnet out-exim-aflnet "-P SMTP -D 10000 -q 3 -s 3 -E -K -W 100 -m none -t ${TEST_TIMEOUT}+" $TIMEOUT $SKIPCOUNT &
            fi

            if [[ $FUZZER == "chatafl" ]] || [[ $FUZZER == "all" ]]
            then
                profuzzbench_exec_common.sh $IMAGE_NAME $NUM_CONTAINERS results-exim chatafl out-exim-chatafl "-P SMTP -D 10000 -q 3 -s 3 -E -K -W 100 -m none -t ${TEST_TIMEOUT}+" $TIMEOUT $SKIPCOUNT &
            fi

            if [[ $FUZZER == "xpgfuzz" ]] || [[ $FUZZER == "all" ]]
            then
                profuzzbench_exec_common.sh $IMAGE_NAME $NUM_CONTAINERS results-exim xpgfuzz out-exim-xpgfuzz "-P SMTP -D 10000 -q 3 -s 3 -E -K -W 100 -m none -t ${TEST_TIMEOUT}+" $TIMEOUT $SKIPCOUNT &
            fi

            if [[ $FUZZER == "aflnet+s1" ]] || [[ $FUZZER == "all" ]]
            then
                profuzzbench_exec_common.sh $IMAGE_NAME $NUM_CONTAINERS results-exim aflnet+s1 out-exim-aflnet+s1 "-P SMTP -D 10000 -q 3 -s 3 -E -K -W 100 -m none -t ${TEST_TIMEOUT}+" $TIMEOUT $SKIPCOUNT &
            fi
        fi


##### RTSP #####

        if [[ $TARGET == "live555" ]] || [[ $TARGET == "all" ]]
        then

            cd $PFBENCH
            mkdir results-live555

            if [[ $FUZZER == "aflnet" ]] || [[ $FUZZER == "all" ]]
            then
                profuzzbench_exec_common.sh live555 $NUM_CONTAINERS results-live555 aflnet out-live555-aflnet "-P RTSP -D 10000 -q 3 -s 3 -E -K -R -m none" $TIMEOUT $SKIPCOUNT &
            fi

            if [[ $FUZZER == "chatafl" ]] || [[ $FUZZER == "all" ]]
            then
                profuzzbench_exec_common.sh live555 $NUM_CONTAINERS results-live555 chatafl out-live555-chatafl "-P RTSP -D 10000 -q 3 -s 3 -E -K -R -m none" $TIMEOUT $SKIPCOUNT &
            fi

            if [[ $FUZZER == "xpgfuzz" ]] || [[ $FUZZER == "all" ]]
            then
                profuzzbench_exec_common.sh live555 $NUM_CONTAINERS results-live555 xpgfuzz out-live555-xpgfuzz "-P RTSP -D 10000 -q 3 -s 3 -E -K -R -m none" $TIMEOUT $SKIPCOUNT &
            fi

            if [[ $FUZZER == "aflnet+s1" ]] || [[ $FUZZER == "all" ]]
            then
                profuzzbench_exec_common.sh live555 $NUM_CONTAINERS results-live555 aflnet+s1 out-live555-aflnet+s1 "-P RTSP -D 10000 -q 3 -s 3 -E -K -R -m none" $TIMEOUT $SKIPCOUNT &
            fi

        fi

##### SIP #####

        if [[ $TARGET == "kamailio" ]] || [[ $TARGET == "all" ]]
        then

            cd $PFBENCH
            mkdir results-kamailio
            IMAGE_NAME=$(generate_image_name kamailio)

            if [[ $FUZZER == "aflnet" ]] || [[ $FUZZER == "all" ]]
            then
                profuzzbench_exec_common.sh $IMAGE_NAME $NUM_CONTAINERS results-kamailio aflnet out-kamailio-aflnet "-m none -P SIP -l 5061 -D 10000000+ -q 3 -s 3 -E -K -t 300000+" $TIMEOUT $SKIPCOUNT &
            fi
            
            if [[ $FUZZER == "chatafl" ]] || [[ $FUZZER == "all" ]]
            then
                profuzzbench_exec_common.sh $IMAGE_NAME $NUM_CONTAINERS results-kamailio chatafl out-kamailio-chatafl "-m none -P SIP -l 5061 -D 10000000+ -q 3 -s 3 -E -K -t 300000+" $TIMEOUT $SKIPCOUNT &
            fi

            if [[ $FUZZER == "xpgfuzz" ]] || [[ $FUZZER == "all" ]]
            then
                profuzzbench_exec_common.sh $IMAGE_NAME $NUM_CONTAINERS results-kamailio xpgfuzz out-kamailio-xpgfuzz "-m none -P SIP -l 5061 -D 10000000+ -q 3 -s 3 -E -K -t 300000+" $TIMEOUT $SKIPCOUNT &
            fi

            if [[ $FUZZER == "aflnet+s1" ]] || [[ $FUZZER == "all" ]]
            then
                profuzzbench_exec_common.sh $IMAGE_NAME $NUM_CONTAINERS results-kamailio aflnet+s1 out-kamailio-aflnet+s1 "-m none -P SIP -l 5061 -D 10000000+ -q 3 -s 3 -E -K -t 300000+" $TIMEOUT $SKIPCOUNT &
            fi
        fi

##### DAAPD #####

        if [[ $TARGET == "forked-daapd" ]] || [[ $TARGET == "all" ]]
        then

            cd $PFBENCH
            mkdir results-forked-daapd
            IMAGE_NAME=$(generate_image_name forked-daapd)

            if [[ $FUZZER == "aflnet" ]] || [[ $FUZZER == "all" ]]
            then
                profuzzbench_exec_common.sh $IMAGE_NAME $NUM_CONTAINERS results-forked-daapd aflnet out-forked-daapd-aflnet "-P HTTP -D 1000000+ -m none -q 3 -s 3 -E -K -t 600000+" $TIMEOUT $SKIPCOUNT &
            fi

            if [[ $FUZZER == "chatafl" ]] || [[ $FUZZER == "all" ]]
            then
                profuzzbench_exec_common.sh $IMAGE_NAME $NUM_CONTAINERS results-forked-daapd chatafl out-forked-daapd-chatafl "-P HTTP -D 1000000+ -m none -q 3 -s 3 -E -K -t 600000+" $TIMEOUT $SKIPCOUNT &
            fi

            if [[ $FUZZER == "xpgfuzz" ]] || [[ $FUZZER == "all" ]]
            then
                profuzzbench_exec_common.sh $IMAGE_NAME $NUM_CONTAINERS results-forked-daapd xpgfuzz out-forked-daapd-xpgfuzz "-P HTTP -D 1000000+ -m none -q 3 -s 3 -E -K -t 600000+" $TIMEOUT $SKIPCOUNT &
            fi

            if [[ $FUZZER == "aflnet+s1" ]] || [[ $FUZZER == "all" ]]
            then
                profuzzbench_exec_common.sh $IMAGE_NAME $NUM_CONTAINERS results-forked-daapd aflnet+s1 out-forked-daapd-aflnet+s1 "-P HTTP -D 1000000+ -m none -q 3 -s 3 -E -K -t 600000+" $TIMEOUT $SKIPCOUNT &
            fi
        fi

##### HTTP #####

        if [[ $TARGET == "lighttpd1" ]] || [[ $TARGET == "all" ]]
        then

            cd $PFBENCH
            mkdir results-lighttpd1
            IMAGE_NAME=$(generate_image_name lighttpd1)

            if [[ $FUZZER == "aflnet" ]] || [[ $FUZZER == "all" ]]
            then
                profuzzbench_exec_common.sh $IMAGE_NAME $NUM_CONTAINERS results-lighttpd1 aflnet out-lighttpd1-aflnet "-P HTTP -D 200000 -m none -q 3 -s 3 -E -K -R -t ${TEST_TIMEOUT}+" $TIMEOUT $SKIPCOUNT &
            fi

            if [[ $FUZZER == "chatafl" ]] || [[ $FUZZER == "all" ]]
            then
                profuzzbench_exec_common.sh $IMAGE_NAME $NUM_CONTAINERS results-lighttpd1 chatafl out-lighttpd1-chatafl "-P HTTP -D 200000 -m none -q 3 -s 3 -E -K -R -t ${TEST_TIMEOUT}+" $TIMEOUT $SKIPCOUNT &
            fi

            if [[ $FUZZER == "xpgfuzz" ]] || [[ $FUZZER == "all" ]]
            then
                profuzzbench_exec_common.sh $IMAGE_NAME $NUM_CONTAINERS results-lighttpd1 xpgfuzz out-lighttpd1-xpgfuzz "-P HTTP -D 200000 -m none -q 3 -s 3 -E -K -R -t ${TEST_TIMEOUT}+" $TIMEOUT $SKIPCOUNT &
            fi

            if [[ $FUZZER == "aflnet+s1" ]] || [[ $FUZZER == "all" ]]
            then
                profuzzbench_exec_common.sh $IMAGE_NAME $NUM_CONTAINERS results-lighttpd1 aflnet+s1 out-lighttpd1-aflnet+s1 "-P HTTP -D 200000 -m none -q 3 -s 3 -E -K -R -t ${TEST_TIMEOUT}+" $TIMEOUT $SKIPCOUNT &
            fi
        fi


        if [[ $TARGET == "all" ]]
        then
            # Quit loop -- all fuzzers and targets have already been executed
            exit
        fi

    done
done


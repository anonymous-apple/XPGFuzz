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

# Function to generate image name: xpg-月份-日-{协议}
# If IMAGE_DATE is set (format: MM-DD), use it; otherwise use current date
generate_image_name() {
    local protocol=$1
    local month
    local day
    
    if [ -n "$IMAGE_DATE" ]; then
        # IMAGE_DATE format: MM-DD (e.g., "12-5")
        month=$(echo $IMAGE_DATE | cut -d'-' -f1)
        day=$(echo $IMAGE_DATE | cut -d'-' -f2)
    else
        # Use current date
        month=$(date +%-m)
        day=$(date +%-d)
    fi
    
    echo "xpg-${month}-${day}-${protocol}"
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
        echo "***** RUNNING $FUZZER ON $TARGET *****"
        echo

##### FTP #####

        if [[ $TARGET == "lightftp" ]] || [[ $TARGET == "all" ]]
        then

            cd $PFBENCH
            mkdir results-lightftp
            IMAGE_NAME=$(generate_image_name lightftp)

            if [[ $FUZZER == "aflnet" ]] || [[ $FUZZER == "all" ]]
            then
                profuzzbench_exec_common.sh $IMAGE_NAME $NUM_CONTAINERS results-lightftp aflnet out-lightftp-aflnet "-P FTP -D 10000 -q 3 -s 3 -E -K -m none -t ${TEST_TIMEOUT}+" $TIMEOUT $SKIPCOUNT &
            fi

            if [[ $FUZZER == "chatafl" ]] || [[ $FUZZER == "all" ]]
            then
                profuzzbench_exec_common.sh $IMAGE_NAME $NUM_CONTAINERS results-lightftp chatafl out-lightftp-chatafl "-P FTP -D 10000 -q 3 -s 3 -E -K -m none -t ${TEST_TIMEOUT}+" $TIMEOUT $SKIPCOUNT &
            fi

            if [[ $FUZZER == "xpgfuzz" ]] || [[ $FUZZER == "all" ]]
            then
                profuzzbench_exec_common.sh $IMAGE_NAME $NUM_CONTAINERS results-lightftp xpgfuzz out-lightftp-xpgfuzz "-P FTP -D 10000 -q 3 -s 3 -E -K -m none -t ${TEST_TIMEOUT}+" $TIMEOUT $SKIPCOUNT &
            fi

            # aflnet+s1: seed-enrichment-only ablation variant
            if [[ $FUZZER == "aflnet+s1" ]] || [[ $FUZZER == "all" ]]
            then
                profuzzbench_exec_common.sh $IMAGE_NAME $NUM_CONTAINERS results-lightftp aflnet+s1 out-lightftp-aflnet+s1 "-P FTP -D 10000 -q 3 -s 3 -E -K -m none -t ${TEST_TIMEOUT}+" $TIMEOUT $SKIPCOUNT &
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
                profuzzbench_exec_common.sh $IMAGE_NAME $NUM_CONTAINERS results-bftpd xpgfuzz out-bftpd-xpgfuzz "-m none -P FTP -D 10000 -q 3 -s 3 -E -K -t ${TEST_TIMEOUT}+" $TIMEOUT $SKIPCOUNT &
            fi

            if [[ $FUZZER == "aflnet+s1" ]] || [[ $FUZZER == "all" ]]
            then
                profuzzbench_exec_common.sh $IMAGE_NAME $NUM_CONTAINERS results-bftpd aflnet+s1 out-bftpd-aflnet+s1 "-m none -P FTP -D 10000 -q 3 -s 3 -E -K -t ${TEST_TIMEOUT}+" $TIMEOUT $SKIPCOUNT &
            fi
        fi


        if [[ $TARGET == "proftpd" ]] || [[ $TARGET == "all" ]]
        then

            cd $PFBENCH
            mkdir results-proftpd
            IMAGE_NAME=$(generate_image_name proftpd)

            if [[ $FUZZER == "aflnet" ]] || [[ $FUZZER == "all" ]]
            then
                profuzzbench_exec_common.sh $IMAGE_NAME $NUM_CONTAINERS results-proftpd aflnet out-proftpd-aflnet "-m none -P FTP -D 10000 -q 3 -s 3 -E -K -t ${TEST_TIMEOUT}+" $TIMEOUT $SKIPCOUNT &
            fi

            if [[ $FUZZER == "chatafl" ]] || [[ $FUZZER == "all" ]]
            then
                profuzzbench_exec_common.sh $IMAGE_NAME $NUM_CONTAINERS results-proftpd chatafl out-proftpd-chatafl "-m none -P FTP -D 10000 -q 3 -s 3 -E -K -t ${TEST_TIMEOUT}+" $TIMEOUT $SKIPCOUNT &
            fi

            if [[ $FUZZER == "xpgfuzz" ]] || [[ $FUZZER == "all" ]]
            then
                profuzzbench_exec_common.sh $IMAGE_NAME $NUM_CONTAINERS results-proftpd xpgfuzz out-proftpd-xpgfuzz "-m none -P FTP -D 10000 -q 3 -s 3 -E -K -t ${TEST_TIMEOUT}+" $TIMEOUT $SKIPCOUNT &
            fi

            if [[ $FUZZER == "aflnet+s1" ]] || [[ $FUZZER == "all" ]]
            then
                profuzzbench_exec_common.sh $IMAGE_NAME $NUM_CONTAINERS results-proftpd aflnet+s1 out-proftpd-aflnet+s1 "-m none -P FTP -D 10000 -q 3 -s 3 -E -K -t ${TEST_TIMEOUT}+" $TIMEOUT $SKIPCOUNT &
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
                profuzzbench_exec_common.sh $IMAGE_NAME $NUM_CONTAINERS results-pure-ftpd xpgfuzz out-pure-ftpd-xpgfuzz "-m none -P FTP -D 10000 -q 3 -s 3 -E -K -t ${TEST_TIMEOUT}+" $TIMEOUT $SKIPCOUNT &
            fi

            if [[ $FUZZER == "aflnet+s1" ]] || [[ $FUZZER == "all" ]]
            then
                profuzzbench_exec_common.sh $IMAGE_NAME $NUM_CONTAINERS results-pure-ftpd aflnet+s1 out-pure-ftpd-aflnet+s1 "-m none -P FTP -D 10000 -q 3 -s 3 -E -K -t ${TEST_TIMEOUT}+" $TIMEOUT $SKIPCOUNT &
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
            IMAGE_NAME=$(generate_image_name live555)

            if [[ $FUZZER == "aflnet" ]] || [[ $FUZZER == "all" ]]
            then
                profuzzbench_exec_common.sh $IMAGE_NAME $NUM_CONTAINERS results-live555 aflnet out-live555-aflnet "-P RTSP -D 10000 -q 3 -s 3 -E -K -R -m none" $TIMEOUT $SKIPCOUNT &
            fi

            if [[ $FUZZER == "chatafl" ]] || [[ $FUZZER == "all" ]]
            then
                profuzzbench_exec_common.sh $IMAGE_NAME $NUM_CONTAINERS results-live555 chatafl out-live555-chatafl "-P RTSP -D 10000 -q 3 -s 3 -E -K -R -m none" $TIMEOUT $SKIPCOUNT &
            fi

            if [[ $FUZZER == "xpgfuzz" ]] || [[ $FUZZER == "all" ]]
            then
                profuzzbench_exec_common.sh $IMAGE_NAME $NUM_CONTAINERS results-live555 xpgfuzz out-live555-xpgfuzz "-P RTSP -D 10000 -q 3 -s 3 -E -K -R -m none" $TIMEOUT $SKIPCOUNT &
            fi

            if [[ $FUZZER == "aflnet+s1" ]] || [[ $FUZZER == "all" ]]
            then
                profuzzbench_exec_common.sh $IMAGE_NAME $NUM_CONTAINERS results-live555 aflnet+s1 out-live555-aflnet+s1 "-P RTSP -D 10000 -q 3 -s 3 -E -K -R -m none" $TIMEOUT $SKIPCOUNT &
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
                profuzzbench_exec_common.sh $IMAGE_NAME $NUM_CONTAINERS results-kamailio aflnet out-kamailio-aflnet "-m none -P SIP -l 5061 -D 50000 -q 3 -s 3 -E -K -t ${TEST_TIMEOUT}+" $TIMEOUT $SKIPCOUNT &
            fi
            
            if [[ $FUZZER == "chatafl" ]] || [[ $FUZZER == "all" ]]
            then
                profuzzbench_exec_common.sh $IMAGE_NAME $NUM_CONTAINERS results-kamailio chatafl out-kamailio-chatafl "-m none -P SIP -l 5061 -D 50000 -q 3 -s 3 -E -K -t ${TEST_TIMEOUT}+" $TIMEOUT $SKIPCOUNT &
            fi

            if [[ $FUZZER == "xpgfuzz" ]] || [[ $FUZZER == "all" ]]
            then
                profuzzbench_exec_common.sh $IMAGE_NAME $NUM_CONTAINERS results-kamailio xpgfuzz out-kamailio-xpgfuzz "-m none -P SIP -l 5061 -D 50000 -q 3 -s 3 -E -K -t ${TEST_TIMEOUT}+" $TIMEOUT $SKIPCOUNT &
            fi

            if [[ $FUZZER == "aflnet+s1" ]] || [[ $FUZZER == "all" ]]
            then
                profuzzbench_exec_common.sh $IMAGE_NAME $NUM_CONTAINERS results-kamailio aflnet+s1 out-kamailio-aflnet+s1 "-m none -P SIP -l 5061 -D 50000 -q 3 -s 3 -E -K -t ${TEST_TIMEOUT}+" $TIMEOUT $SKIPCOUNT &
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
                profuzzbench_exec_common.sh $IMAGE_NAME $NUM_CONTAINERS results-forked-daapd aflnet out-forked-daapd-aflnet "-P HTTP -D 200000 -m none -q 3 -s 3 -E -K -t 3000+" $TIMEOUT $SKIPCOUNT &
            fi

            if [[ $FUZZER == "chatafl" ]] || [[ $FUZZER == "all" ]]
            then
                profuzzbench_exec_common.sh $IMAGE_NAME $NUM_CONTAINERS results-forked-daapd chatafl out-forked-daapd-chatafl "-P HTTP -D 200000 -m none -q 3 -s 3 -E -K -t 3000+" $TIMEOUT $SKIPCOUNT &
            fi

            if [[ $FUZZER == "xpgfuzz" ]] || [[ $FUZZER == "all" ]]
            then
                profuzzbench_exec_common.sh $IMAGE_NAME $NUM_CONTAINERS results-forked-daapd xpgfuzz out-forked-daapd-xpgfuzz "-P HTTP -D 200000 -m none -q 3 -s 3 -E -K -t 3000+" $TIMEOUT $SKIPCOUNT &
            fi

            if [[ $FUZZER == "aflnet+s1" ]] || [[ $FUZZER == "all" ]]
            then
                profuzzbench_exec_common.sh $IMAGE_NAME $NUM_CONTAINERS results-forked-daapd aflnet+s1 out-forked-daapd-aflnet+s1 "-P HTTP -D 200000 -m none -q 3 -s 3 -E -K -t 3000+" $TIMEOUT $SKIPCOUNT &
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
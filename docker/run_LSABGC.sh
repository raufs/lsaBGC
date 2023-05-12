#!/bin/bash

# AUTHOR: Rauf Salamzade
# AFFILIATION: Kalan Lab, UW-Madison
# run_LSABGC.sh - wrapper to run lsaBGC-Easy.py and lsaBGC-Euk-Easy.py

# function
get_abs_filename() {
  # $1 : relative filename
  filename=$1
  parentdir=$(dirname "${filename}")

  if [ -d "${filename}" ]; then
      echo "$(cd "${filename}" && pwd)"
  elif [ -d "${parentdir}" ]; then
    echo "$(cd "${parentdir}" && pwd)/$(basename "${filename}")"
  fi
}

## The following is also adapted from analogous file from BIG-SCAPE
if [[ $# -eq 0 || $1 == "-h" || $1 == "--help" || $1 == "-v" || $1 == "--version" ]]; then
	docker pull raufs/lsabgc:latest
	docker run \
	--detach=false \
	--rm \
	--user=$(id -u):$(id -g) \
	raufs/lsabgc:latest \

elif [[ $1 == 'lsaBGC-Easy.py' ]]; then
	set -o errexit
	set -o nounset

	# Links within the container
	readonly CONTAINER_INPUT_DIR=/home/input
	readonly CONTAINER_OUTPUT_DIR=/home/output

  # variables for updating/input paths to account for Docker mounting

  DOCKER_VOLUME_ARGS=""
  EASY_ARGS=""
  OUTPUT_PARENT_DIR="NA"
    while [[ ! $# -eq 0 ]]; do
      if [[ "$1" == '-g' || "$1" == '--user_genomes_directory' ]]; then
        shift
        ABS_VALUE=$(get_abs_filename $1)
        INPUT_DIR=$(basename $ABS_VALUE)
        INPUT_PARENT_DIR=$(dirname $ABS_VALUE)
        EASY_ARGS+="-i $CONTAINER_INPUT_DIR/$INPUT_DIR "
        DOCKER_VOLUME_ARGS+="--volume $INPUT_PARENT_DIR:$CONTAINER_INPUT_DIR:ro "
        shift
      elif [[ "$1" == '-o' || "$1" == '--output_directory' ]]; then
        shift
        ABS_VALUE=$(get_abs_filename $1)
        OUTPUT_DIR=$(basename $ABS_VALUE)
        OUTPUT_PARENT_DIR=$(dirname $ABS_VALUE)
        EASY_ARGS+="-o $CONTAINER_OUTPUT_DIR/$OUTPUT_DIR "
        DOCKER_VOLUME_ARGS+="--volume $OUTPUT_PARENT_DIR:$CONTAINER_OUTPUT_DIR:rw "
        shift
      else
        EASY_ARGS+="$1 "
        shift
      fi
    done
    EASY_ARGS+="--docker_mode"    
    

	if [[ ! -d ${OUTPUT_PARENT_DIR} && $OUTPUT_PARENT_DIR != "NA" ]]; then
   		mkdir ${OUTPUT_PARENT_DIR}
	fi

  # run workflow
	docker pull raufs/lsabgc:latest
	docker run ${DOCKER_VOLUME_ARGS} --detach=false --rm --user=$(id -u):$(id -g) raufs/lsabgc:latest ${EASY_ARGS}

elif [[ $1 == 'lsaBGC-Euk-Easy.py' ]]; then
  set -o errexit
	set -o nounset

	# Links within the container
	readonly CONTAINER_INPUT_DIR=/home/input
	readonly CONTAINER_OUTPUT_DIR=/home/output

  # variables for updating/input paths to account for Docker mounting

  DOCKER_VOLUME_ARGS=""
  EASY_ARGS=""
  OUTPUT_PARENT_DIR="NA"
    while [[ ! $# -eq 0 ]]; do
      if [[ "$1" == '-g' || "$1" == '--user_genomes_directory' ]]; then
        shift
        ABS_VALUE=$(get_abs_filename $1)
        INPUT_DIR=$(basename $ABS_VALUE)
        INPUT_PARENT_DIR=$(dirname $ABS_VALUE)
        EASY_ARGS+="-i $CONTAINER_INPUT_DIR/$INPUT_DIR "
        DOCKER_VOLUME_ARGS+="--volume $INPUT_PARENT_DIR:$CONTAINER_INPUT_DIR:ro "
        shift
      elif [[ "$1" == '-o' || "$1" == '--output_directory' ]]; then
        shift
        ABS_VALUE=$(get_abs_filename $1)
        OUTPUT_DIR=$(basename $ABS_VALUE)
        OUTPUT_PARENT_DIR=$(dirname $ABS_VALUE)
        EASY_ARGS+="-o $CONTAINER_OUTPUT_DIR/$OUTPUT_DIR "
        DOCKER_VOLUME_ARGS+="--volume $OUTPUT_PARENT_DIR:$CONTAINER_OUTPUT_DIR:rw "
        shift
      else
        EASY_ARGS+="$1 "
        shift
      fi
    done
    EASY_ARGS+="--docker_mode"    
    

	if [[ ! -d ${OUTPUT_PARENT_DIR} && $OUTPUT_PARENT_DIR != "NA" ]]; then
   		mkdir ${OUTPUT_PARENT_DIR}
	fi

  # run workflow
	docker pull raufs/lsabgc:latest
	docker run ${DOCKER_VOLUME_ARGS} --detach=false --rm --user=$(id -u):$(id -g) raufs/lsabgc:latest ${EASY_ARGS}

else
	docker pull raufs/lsabgc:latest
	docker run \
	--detach=false \
	--rm \
	--user=$(id -u):$(id -g) \
	raufs/lsabgc:latest \

fi

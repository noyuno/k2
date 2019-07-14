#!/usr/bin/env bash

# Get the env variables so crond has them

# Create the environment file for crond
printenv | sed 's/^\([a-zA-Z0-9_]*\)=\(.*\)$/export \1="\2"/g' | grep -E "^export RCLONE" > /cron/rclone.env

source /cron/rclone.env

# Possibly convert docker secrets marked variables.
#source /env_secrets.sh

function message() {
    echo "$1"
    curl -XPOST -sd '{"message": "'"$CONTAINER_NAME"': '"$1"'"}' http://discordbot >/dev/null
    if [ $? -ne 0 ]; then
        echo "$CONTAINER_NAME: failed to send message to discordbot"
    fi
}

function run(){
    "$@"
    local status=$?
    if [ $status -ne 0 ]; then
        message ":red_circle: error: returned $status"
    else
        message ":white_check_mark: finished"
        # Send the payload to the API
        if [[ -z $RCLONE_CROND_HEALTHCHECK_URL ]]; then
            echo "INFO: A health check has not been set. Not using health check services"
        else
            echo "OK: All tests passed, sending message to API..."
            POST=$(curl -s -S "$RCLONE_CROND_HEALTHCHECK_URL");
            # Check if the message posted to the API. It should return "ok". Anything other than "ok" indicates an issue
            if test "${POST}" != OK; then
                echo "ERROR: The check to the API failed (${POST})"
                return 1
            else
                echo "OK: Message successfully sent to the health check"
            fi
        fi
    fi
    return $status
}

function sync() {
    (
        flock -n 200 || exit 1
        sync_command="rclone sync ${RCLONE_CROND_OPTIONS} ${RCLONE_CROND_SOURCE_PATH} ${RCLONE_CROND_DESTINATION_PATH}"
        if [ "$RCLONE_SYNC_COMMAND" ]; then
            sync_command="$RCLONE_SYNC_COMMAND"
        else
            if [[ -z "$RCLONE_CROND_SOURCE_PATH" ]] || [[ -z "$RCLONE_CROND_DESTINATION_PATH" ]]; then
                echo "Error: A RCLONE PATH environment variable was not set or passed to the container. Please review your RCLONE source/destination paths."
                exit 1
            fi
        fi
        echo "Executing => $sync_command"
        eval "$sync_command"
    ) 200>/run/rclone.lock
}

function foldersize() {
    if [[ -z $RCLONE_CROND_SOURCE_PATH ]] || [[ -z $RCLONE_CROND_SOURCE_SIZE ]]; then
        echo "INFO: A local folder path and/or size has not been set. Not using folder monitor"
    else
        SIZE=$(/usr/bin/du -s ${RCLONE_CROND_SOURCE_PATH} | /usr/bin/awk '{print $1}')
        MBSIZE=$((SIZE / 1024))
        echo "$RCLONE_CROND_SOURCE_PATH is $MBSIZE MB"
        if [[ $MBSIZE -gt $(( ${RCLONE_CROND_SOURCE_SIZE} )) ]]; then
            rclone_move
        fi
    fi
}

"$@"

#!/usr/bin/env bash
# Run the tool's container for one leg, and say plainly how it ended.
#
#   harness/run_container.sh <name> <minutes> <log> <docker run args...>
#
# Why not `docker run` straight from the step. When a step hit its
# `timeout-minutes`, Actions killed the docker CLI and the container kept
# going: bash was PID 1 and ignored the signal. It went on writing into
# /data/out after the Runs gate had failed, competed with the next leg for the
# CPU, and the report said "the tool exited with an error". And a process our
# own memory ceiling killed left no line in the log at all, so it was
# published as the tool failing rather than as the ceiling it is.
#
# So: the time limit is enforced here, before the step's own; the container
# always dies with the script; and two lines of our own go into the log for
# diagnose_log to read, one for the time limit and one for the memory ceiling.
# The exit status is the container's, or 124 when the limit stopped it.
set -uo pipefail

name=$1; minutes=$2; log=$3; shift 3
trap 'docker rm -f "$name" >/dev/null 2>&1 || true' EXIT

limit=$(( minutes * 60 ))
start=$SECONDS
# --init: signals reach the tool's processes instead of stopping at bash.
timeout --kill-after=20 "$limit" docker run --init --name "$name" "$@" 2>&1 | tee "$log"
rc=${PIPESTATUS[0]}
elapsed=$(( SECONDS - start ))

if [ "$elapsed" -ge "$limit" ]; then
  docker kill "$name" >/dev/null 2>&1 || true
  echo "STRhub: the run was stopped at the time limit of ${minutes} minutes." | tee -a "$log"
  exit 124
fi
if [ "$(docker inspect -f '{{.State.OOMKilled}}' "$name" 2>/dev/null)" = "true" ]; then
  echo "STRhub: the container was killed on reaching its memory limit (out of memory)." | tee -a "$log"
fi
exit "$rc"

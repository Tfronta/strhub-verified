#!/usr/bin/env bash
# Capture the argv at launch and the process's combined output in one file.
# Keep the output-only log for the engine's existing diagnostics.
record_terminal() {
  local log=$1
  shift
  local transcript="$log.terminal"
  local rc

  : > "$log" || return
  {
    printf '$'
    printf ' %q' "$@"
    printf '\n'
  } > "$transcript" || return

  if "$@" 2>&1 | tee -a "$log" "$transcript"; then
    rc=0
  else
    rc=${PIPESTATUS[0]}
  fi
  printf '\n[exit %d]\n' "$rc" >> "$transcript"
  return "$rc"
}

if [[ "$0" == "${BASH_SOURCE[0]}" ]]; then
  set -o pipefail
  record_terminal "$@"
fi

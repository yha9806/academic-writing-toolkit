#!/usr/bin/env bash
# scripts/lib.sh — shared helpers for foolproofing scripts.
# Source this file from any script that needs the pass/fail/die helpers.
# Compatible with bash 3.2 (macOS default) through bash 5+.

# Initialise the failure counter so `set -u` (in callers) does not trip
# when a script sources lib.sh without having set FAILS yet.
FAILS=${FAILS:-0}

pass()   { printf "  \033[32m[\xe2\x9c\x93]\033[0m %s\n" "$*"; }
fail()   { printf "  \033[31m[\xe2\x9c\x97]\033[0m %s\n" "$*"; FAILS=$((FAILS+1)); }   # soft fail — accumulates, does not exit
warn()   { printf "  \033[33m[!]\033[0m %s\n" "$*"; }
hint()   { printf "       fix: %s\n" "$*"; }
header() { printf "\n%s\n" "$*"; }
ok()     { printf "  \033[32m[\xe2\x9c\x93]\033[0m %s\n" "$*"; }
die()    { printf "\033[31merror:\033[0m %s\n" "$*" >&2; exit 2; }                      # hard fail — exits immediately

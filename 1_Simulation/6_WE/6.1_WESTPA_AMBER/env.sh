#!/usr/bin/env bash

export WEST_SIM_ROOT
WEST_SIM_ROOT=${WEST_SIM_ROOT:-.}
export WORK_DIR=${WORK_DIR:-work}
export AMBER_ENGINE=${AMBER_ENGINE:-pmemd.cuda}
export CPPTRAJ=${CPPTRAJ:-cpptraj}
export WESTPA_WORK_MANAGER=${WESTPA_WORK_MANAGER:-serial}
export WESTPA_WORKERS=${WESTPA_WORKERS:-1}

#!/usr/bin/env bash

export WEST_SIM_ROOT
WEST_SIM_ROOT=${WEST_SIM_ROOT:-$PWD}
export WORK_DIR=$WEST_SIM_ROOT/work
export AMBER_ENGINE=${AMBER_ENGINE:-pmemd.cuda}
export CPPTRAJ=${CPPTRAJ:-cpptraj}

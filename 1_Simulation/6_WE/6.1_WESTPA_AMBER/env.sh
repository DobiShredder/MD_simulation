#!/usr/bin/env bash

export WEST_SIM_ROOT
WEST_SIM_ROOT=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
export AMBER_ENGINE=${AMBER_ENGINE:-sander}

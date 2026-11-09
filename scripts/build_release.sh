#!/usr/bin/env bash
set -Eeuo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
WORKSPACE_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
ROS_SETUP="${ROS_SETUP:-/opt/ros/humble/setup.bash}"
COLCON_PARALLEL_WORKERS="${COLCON_PARALLEL_WORKERS:-1}"
MAKE_JOBS="${MAKE_JOBS:-2}"

if [[ ! -f "$ROS_SETUP" ]]; then
  printf 'ERROR: ROS 2 setup file not found: %s\n' "$ROS_SETUP" >&2
  exit 1
fi

if [[ ! "$COLCON_PARALLEL_WORKERS" =~ ^[1-9][0-9]*$ ]]; then
  printf 'ERROR: COLCON_PARALLEL_WORKERS must be a positive integer\n' >&2
  exit 1
fi

if [[ ! "$MAKE_JOBS" =~ ^[1-9][0-9]*$ ]]; then
  printf 'ERROR: MAKE_JOBS must be a positive integer\n' >&2
  exit 1
fi

set +u
source "$ROS_SETUP"
set -u

cd "$WORKSPACE_ROOT"
export MAKEFLAGS="-j${MAKE_JOBS}"
export CMAKE_BUILD_PARALLEL_LEVEL="$MAKE_JOBS"

printf 'Release 构建并行限制：colcon 包数=%s，单包编译任务数=%s\n' \
  "$COLCON_PARALLEL_WORKERS" "$MAKE_JOBS"

exec colcon build \
  --parallel-workers "$COLCON_PARALLEL_WORKERS" \
  --cmake-args \
    -DCMAKE_BUILD_TYPE=Release \
    -DAMENT_CMAKE_SYMLINK_INSTALL=OFF

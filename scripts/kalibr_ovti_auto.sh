#!/usr/bin/env bash
set -Eeuo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
KALIBR_ROS2_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
KALIBR_MY_ROOT="${KALIBR_MY_ROOT:-$(cd "$KALIBR_ROS2_ROOT/../kalibr_my" && pwd)}"

BAG_DIR="${BAG_DIR:-$KALIBR_MY_ROOT/bags/ovti_rp/ovti_1}"
TARGET_YAML="${TARGET_YAML:-$KALIBR_MY_ROOT/data/ovti/new_april_6x6.yaml}"
IMU_YAML="${IMU_YAML:-$KALIBR_MY_ROOT/data/ovti/ovti1-imu.yaml}"
CAMERA_TOPICS="${CAMERA_TOPICS:-/left/image_raw /right/image_raw}"
CAMERA_MODELS="${CAMERA_MODELS:-pinhole-equi pinhole-equi}"
IMU_MODEL="${IMU_MODEL:-calibrated}"
CAMERA_BAG_FREQ="${CAMERA_BAG_FREQ:-5.0}"
IMU_CAMERA_BAG_FREQ="${IMU_CAMERA_BAG_FREQ:-3.0}"
MI_TOL="${MI_TOL:-0.2}"
ROS_SETUP="${ROS_SETUP:-/opt/ros/humble/setup.bash}"
WORKSPACE_SETUP="${WORKSPACE_SETUP:-$KALIBR_ROS2_ROOT/install/setup.bash}"
OUTPUT_DIR="${OUTPUT_DIR:-$KALIBR_ROS2_ROOT/results/ovti_1_$(date '+%Y%m%d_%H%M%S')}"

usage() {
  cat <<EOF
用法: $(basename "$0") [--help]

依次运行相机内参标定和相机-IMU联合标定，默认使用 ovti_1 rosbag2。
结果保存在独立目录: $OUTPUT_DIR

可通过环境变量修改输入和参数:
  KALIBR_MY_ROOT          kalibr_my 数据目录
  BAG_DIR                 rosbag2 目录
  TARGET_YAML             AprilGrid 配置
  IMU_YAML                IMU 噪声参数配置
  CAMERA_TOPICS           空格分隔的图像 topic
  CAMERA_MODELS           空格分隔的相机模型
  CAMERA_BAG_FREQ         内参标定抽帧频率，默认 $CAMERA_BAG_FREQ Hz
  IMU_CAMERA_BAG_FREQ     联合标定抽帧频率，默认 $IMU_CAMERA_BAG_FREQ Hz
  IMU_MODEL               IMU 模型，默认 $IMU_MODEL
  MI_TOL                  相机标定图像选择容差，默认 $MI_TOL
  OUTPUT_DIR              本次运行的输出目录
  ROS_SETUP               ROS 2 Humble setup.bash 路径
  WORKSPACE_SETUP         kalibr_ros2 install/setup.bash 路径
EOF
}

die() {
  printf 'ERROR: %s\n' "$*" >&2
  exit 1
}

if [[ "${1:-}" == "--help" || "${1:-}" == "-h" ]]; then
  usage
  exit 0
fi
[[ $# -eq 0 ]] || die "unknown argument: $1 (use --help)"

[[ -d "$BAG_DIR" ]] || die "rosbag2 directory not found: $BAG_DIR"
[[ -f "$BAG_DIR/metadata.yaml" ]] || die "metadata.yaml not found under rosbag2 directory: $BAG_DIR"
[[ -f "$TARGET_YAML" ]] || die "target configuration not found: $TARGET_YAML"
[[ -f "$IMU_YAML" ]] || die "IMU configuration not found: $IMU_YAML"
[[ -f "$ROS_SETUP" ]] || die "ROS setup file not found: $ROS_SETUP"
[[ -f "$WORKSPACE_SETUP" ]] || die "kalibr_ros2 setup file not found: $WORKSPACE_SETUP"

if [[ -e "$OUTPUT_DIR" ]]; then
  die "output directory already exists; choose a new OUTPUT_DIR: $OUTPUT_DIR"
fi

# Source Humble and this workspace so ros2 run resolves the kalibr_ros2 install.
set +u
source "$ROS_SETUP"
source "$WORKSPACE_SETUP"
set -u

# Keep ROS Humble's system NumPy/SciPy pair isolated from incompatible
# user-site packages. Kalibr imports wx through its plotting helpers even
# when report generation is disabled, so expose only a user-site wx package
# when one is available.
export PYTHONNOUSERSITE=1
export MPLBACKEND="${MPLBACKEND:-Agg}"
# `python -m site --user-site` exits with status 1 when PYTHONNOUSERSITE is
# enabled, even though it prints the path. Query the API directly so `set -e`
# does not stop the script before calibration starts.
PYTHON_USER_SITE="$(python3 -c 'import site; print(site.getusersitepackages())')"
PYTHON_OVERRIDE_DIR=""

cleanup_python_override() {
  if [[ -n "$PYTHON_OVERRIDE_DIR" ]]; then
    rm -rf -- "$PYTHON_OVERRIDE_DIR"
  fi
}
trap cleanup_python_override EXIT

if [[ -d "$PYTHON_USER_SITE/wx" ]]; then
  PYTHON_OVERRIDE_DIR="$(mktemp -d "${TMPDIR:-/tmp}/kalibr-ros2-python.XXXXXX")"
  ln -s "$PYTHON_USER_SITE/wx" "$PYTHON_OVERRIDE_DIR/wx"
  export PYTHONPATH="$PYTHON_OVERRIDE_DIR${PYTHONPATH:+:$PYTHONPATH}"
fi

command -v ros2 >/dev/null 2>&1 || die "ros2 command is unavailable after sourcing setup files"

read -r -a camera_topics <<< "$CAMERA_TOPICS"
read -r -a camera_models <<< "$CAMERA_MODELS"
[[ ${#camera_topics[@]} -eq ${#camera_models[@]} ]] || die "CAMERA_TOPICS and CAMERA_MODELS must have the same number of values"
[[ ${#camera_topics[@]} -gt 0 ]] || die "at least one camera topic/model pair is required"

mkdir -p "$OUTPUT_DIR"
OUTPUT_DIR="$(cd "$OUTPUT_DIR" && pwd)"
BAG_LINK="$OUTPUT_DIR/$(basename "$BAG_DIR")"
ln -s "$(realpath "$BAG_DIR")" "$BAG_LINK"

CAMCHAIN_YAML="$OUTPUT_DIR/$(basename "$BAG_DIR")-camchain.yaml"

printf '\n[1/2] 相机内参标定\n'
printf '  rosbag2: %s\n  topics: %s\n  models: %s\n  bag frequency: %s Hz\n' \
  "$BAG_DIR" "${camera_topics[*]}" "${camera_models[*]}" "$CAMERA_BAG_FREQ"
ros2 run kalibr kalibr_calibrate_cameras \
  --bag "$BAG_LINK" \
  --topics "${camera_topics[@]}" \
  --models "${camera_models[@]}" \
  --target "$TARGET_YAML" \
  --bag-freq "$CAMERA_BAG_FREQ" \
  --mi-tol "$MI_TOL" \
  --dont-show-report \
  --skip-report

[[ -f "$CAMCHAIN_YAML" ]] || die "camera calibration did not create camchain: $CAMCHAIN_YAML"

printf '\n[2/2] 相机-IMU 联合标定\n'
printf '  IMU config: %s\n  bag frequency: %s Hz\n' "$IMU_YAML" "$IMU_CAMERA_BAG_FREQ"
ros2 run kalibr kalibr_calibrate_imu_camera \
  --bag "$BAG_LINK" \
  --cams "$CAMCHAIN_YAML" \
  --imu "$IMU_YAML" \
  --imu-models "$IMU_MODEL" \
  --target "$TARGET_YAML" \
  --bag-freq "$IMU_CAMERA_BAG_FREQ" \
  --dont-show-report \
  --skip-report

printf '\n标定完成，结果目录：%s\n' "$OUTPUT_DIR"
printf '相机链：%s\n' "$CAMCHAIN_YAML"
printf '相机-IMU：%s/%s-camchain-imucam.yaml\n' "$OUTPUT_DIR" "$(basename "$BAG_DIR")"

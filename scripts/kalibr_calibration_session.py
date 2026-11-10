#!/usr/bin/env python3
"""Run a strict, resumable Kalibr ROS 2 calibration session.

The script deliberately keeps recording, bag validation, calibration and
result validation in one stateful session directory.  It is intended as a
temporary integration boundary until a ROS 2 service/action interface is
introduced.

基本使用（先在 kalibr_ros2 目录执行）：

    source /opt/ros/humble/setup.bash
    source install/setup.bash
    python3 scripts/kalibr_calibration_session.py start

``start`` 会启动 rosbag2 录制并输出 ``session_dir``。使用该目录查看状态、
结束标定或取消标定：

    python3 scripts/kalibr_calibration_session.py status --session-dir <session_dir>
    python3 scripts/kalibr_calibration_session.py finish --session-dir <session_dir>
    python3 scripts/kalibr_calibration_session.py cancel --session-dir <session_dir>

``finish`` 默认保留录制的 bag。需要在数据检查、相机内参标定、相机 IMU
联合标定和结果验证全部成功后删除 bag 时，显式添加 ``--delete-bag``：

    python3 scripts/kalibr_calibration_session.py finish \
        --session-dir <session_dir> --delete-bag

``cancel`` 会停止录制并删除本次会话的 bag。标定或验证失败时始终保留 bag
和日志，便于诊断。默认 topic、频率和阈值见同目录下的
``kalibr_calibration_session.yaml``。
"""

from __future__ import annotations

import argparse
import copy
import datetime as dt
import fcntl
import json
import math
import os
import re
import shlex
import shutil
import signal
import sqlite3
import struct
import subprocess
import sys
import time
import uuid
from pathlib import Path

import yaml


SCRIPT_PATH = Path(__file__).resolve()
SCRIPT_DIR = SCRIPT_PATH.parent
DEFAULT_CONFIG = SCRIPT_DIR / "kalibr_calibration_session.yaml"
USAGE = """\
使用流程：
  1. source /opt/ros/humble/setup.bash
  2. source install/setup.bash
  3. python3 scripts/kalibr_calibration_session.py start
  4. 使用 start 输出的 session_dir 执行 status、finish 或 cancel

示例：
  python3 scripts/kalibr_calibration_session.py status --session-dir <session_dir>
  python3 scripts/kalibr_calibration_session.py finish --session-dir <session_dir>
  python3 scripts/kalibr_calibration_session.py finish \\
      --session-dir <session_dir> --delete-bag
  python3 scripts/kalibr_calibration_session.py cancel --session-dir <session_dir>

finish 默认保留 bag；--delete-bag 只在所有标定和结果验证成功后，于最后一步删除 bag。
cancel 始终删除本次会话的 bag；标定失败时保留 bag 和日志。
"""
STATE_FILE = "state.json"
LOCK_FILE = ".session.lock"
RECORDER_INFO_FILE = "recorder.json"
VALIDATION_FILE = "validation.json"
SESSION_MARKER = ".kalibr_session"

TERMINAL_STATES = {"SUCCEEDED", "FAILED", "CANCELLED"}


class SessionError(RuntimeError):
    """An expected session failure with a machine-readable error code."""

    def __init__(self, code, message):
        super().__init__(message)
        self.code = code
        self.message = message


def now_utc():
    return dt.datetime.now(dt.timezone.utc).isoformat()


def atomic_json_write(path, value):
    path = Path(path)
    tmp = path.with_name(".{0}.{1}.tmp".format(path.name, os.getpid()))
    with tmp.open("w", encoding="utf-8") as stream:
        json.dump(value, stream, indent=2, ensure_ascii=False, sort_keys=True)
        stream.write("\n")
    os.replace(tmp, path)


def read_json(path):
    with Path(path).open(encoding="utf-8") as stream:
        return json.load(stream)


def write_log(session_dir, message, filename="session.log"):
    line = "[{0}] {1}\n".format(now_utc(), message)
    print(message, flush=True)
    with (Path(session_dir) / filename).open("a", encoding="utf-8") as stream:
        stream.write(line)


def set_state(session_dir, state, **updates):
    state_path = Path(session_dir) / STATE_FILE
    current = read_json(state_path) if state_path.exists() else {}
    current.update(updates)
    current["state"] = state
    current["updated_at"] = now_utc()
    atomic_json_write(state_path, current)
    return current


def load_state(session_dir):
    session_dir = Path(session_dir).resolve()
    if not (session_dir / SESSION_MARKER).is_file():
        raise SessionError("INVALID_SESSION", "not a Kalibr calibration session: {0}".format(session_dir))
    try:
        return read_json(session_dir / STATE_FILE)
    except (OSError, ValueError) as exc:
        raise SessionError("INVALID_SESSION", "cannot read session state: {0}".format(exc)) from exc


class SessionLock:
    def __init__(self, session_dir):
        self.path = Path(session_dir) / LOCK_FILE
        self.stream = None

    def __enter__(self):
        self.stream = self.path.open("a+")
        fcntl.flock(self.stream.fileno(), fcntl.LOCK_EX)
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        fcntl.flock(self.stream.fileno(), fcntl.LOCK_UN)
        self.stream.close()


def expand_value(value):
    if isinstance(value, str):
        return os.path.expanduser(os.path.expandvars(value))
    if isinstance(value, list):
        return [expand_value(item) for item in value]
    if isinstance(value, dict):
        return {key: expand_value(item) for key, item in value.items()}
    return value


def resolve_path(value, base_dir):
    value = expand_value(value)
    path = Path(value)
    if not path.is_absolute():
        path = Path(base_dir) / path
    return str(path.resolve())


def load_config(config_path):
    config_path = Path(config_path).expanduser().resolve()
    try:
        with config_path.open(encoding="utf-8") as stream:
            config = yaml.safe_load(stream) or {}
    except OSError as exc:
        raise SessionError("CONFIG_INVALID", "cannot read config: {0}".format(exc)) from exc
    except yaml.YAMLError as exc:
        raise SessionError("CONFIG_INVALID", "invalid YAML config: {0}".format(exc)) from exc

    if not isinstance(config, dict):
        raise SessionError("CONFIG_INVALID", "the top-level config must be a mapping")
    config = expand_value(config)
    config["_config_path"] = str(config_path)
    config["_config_dir"] = str(config_path.parent)
    return normalize_config(config)


def normalize_config(config):
    base_dir = config["_config_dir"]
    calibration = config.setdefault("calibration", {})
    validation = config.setdefault("validation", {})
    recorder = config.setdefault("recorder", {})

    camera_topics = calibration.get("camera_topics")
    camera_models = calibration.get("camera_models")
    if not camera_topics or not camera_models or len(camera_topics) != len(camera_models):
        raise SessionError("CONFIG_INVALID", "camera_topics and camera_models must have equal non-zero length")
    if not calibration.get("imu_topic"):
        raise SessionError("CONFIG_INVALID", "calibration.imu_topic is required")
    if not calibration.get("target_yaml") or not calibration.get("imu_yaml"):
        raise SessionError("CONFIG_INVALID", "calibration.target_yaml and imu_yaml are required")

    calibration["target_yaml"] = resolve_path(calibration["target_yaml"], base_dir)
    calibration["imu_yaml"] = resolve_path(calibration["imu_yaml"], base_dir)
    config["ros_setup"] = resolve_path(config.get("ros_setup", "/opt/ros/humble/setup.bash"), base_dir)
    config["workspace_setup"] = resolve_path(
        config.get("workspace_setup", str(SCRIPT_DIR.parent / "install/setup.bash")), base_dir)
    config["session_root"] = resolve_path(
        config.get("session_root", str(SCRIPT_DIR.parent / "results/calibration_sessions")), base_dir)

    command = recorder.get("command")
    if isinstance(command, str):
        command = shlex.split(command)
    if not isinstance(command, list) or not command or not all(isinstance(item, str) for item in command):
        raise SessionError("CONFIG_INVALID", "recorder.command must be a non-empty string or argument list")
    if not any("{bag_dir}" in item for item in command):
        raise SessionError("CONFIG_INVALID", "recorder.command must contain the {bag_dir} placeholder")
    recorder["command"] = command

    camera_validation = validation.get("camera", {})
    if isinstance(camera_validation, list):
        if len(camera_validation) != len(camera_topics):
            raise SessionError("CONFIG_INVALID", "validation.camera list must match camera_topics")
        camera_validation = {item["topic"]: item for item in camera_validation}
    elif not isinstance(camera_validation, dict):
        raise SessionError("CONFIG_INVALID", "validation.camera must be a list or mapping")
    for topic in camera_topics:
        item = camera_validation.setdefault(topic, {})
        item.setdefault("expected_rate_hz", 30.0)
        item.setdefault("max_drop_rate", 0.01)
        item.setdefault("max_gap_periods", 3.0)
        item.setdefault("min_messages", 30)
    validation["camera"] = camera_validation

    imu_validation = validation.setdefault("imu", {})
    imu_validation.setdefault("expected_rate_hz", calibration.get("imu_rate_hz", 240.0))
    imu_validation.setdefault("max_drop_rate", 0.01)
    imu_validation.setdefault("max_gap_periods", 5.0)
    imu_validation.setdefault("min_messages", 100)
    validation.setdefault("min_duration_sec", 20.0)
    validation.setdefault("min_overlap_sec", 10.0)
    result_validation = validation.setdefault("results", {})
    result_validation.setdefault("camera_reprojection_std_max_px", 0.5)
    result_validation.setdefault("imu_reprojection_mean_max_px", 0.5)
    result_validation.setdefault("imu_gyro_normalized_mean_max", 3.0)
    result_validation.setdefault("imu_accel_normalized_mean_max", 3.0)
    result_validation.setdefault("max_time_offset_sec", 0.1)
    return config


def save_config_snapshot(session_dir, config):
    snapshot = copy.deepcopy(config)
    snapshot.pop("_config_path", None)
    snapshot.pop("_config_dir", None)
    with (Path(session_dir) / "config.yaml").open("w", encoding="utf-8") as stream:
        yaml.safe_dump(snapshot, stream, allow_unicode=True, sort_keys=False)


def command_for_bag(config, bag_dir):
    return [item.replace("{bag_dir}", str(bag_dir)) for item in config["recorder"]["command"]]


def process_alive(pid):
    if not pid:
        return False
    try:
        pid = int(pid)
        os.kill(pid, 0)
    except (ProcessLookupError, PermissionError, ValueError):
        return False
    # ``kill(pid, 0)`` also succeeds for a zombie.  A recorder worker can
    # briefly remain in that state after its child exits, so do not make the
    # session wait for the full stop timeout in that case.
    proc_stat = Path("/proc/{0}/stat".format(pid))
    try:
        stat_fields = proc_stat.read_text(encoding="utf-8").rsplit(") ", 1)[1].split()
    except (OSError, IndexError):
        return True
    return not stat_fields or stat_fields[0] != "Z"


def sourced_ros_environment(config):
    """Return the environment after sourcing Humble and this workspace."""
    environment = os.environ.copy()
    setup_files = [config["ros_setup"], config["workspace_setup"]]
    missing = [path for path in setup_files if not Path(path).is_file()]
    if missing:
        raise SessionError("ROS2_NOT_SOURCED", "setup file not found: {0}".format(", ".join(missing)))
    source_command = "set +u; source {0}; source {1}; env -0".format(
        shlex.quote(setup_files[0]), shlex.quote(setup_files[1]))
    try:
        output = subprocess.check_output(["bash", "-c", source_command], env=environment)
    except subprocess.CalledProcessError as exc:
        raise SessionError("ROS2_SETUP_FAILED", "could not source ROS 2 setup files") from exc
    for item in output.split(b"\0"):
        if b"=" in item:
            key, value = item.split(b"=", 1)
            environment[key.decode()] = value.decode()
    if not shutil.which("ros2", path=environment.get("PATH")):
        raise SessionError("ROS2_NOT_SOURCED", "ros2 is unavailable after sourcing setup files")
    return environment


def recorder_info(session_dir):
    path = Path(session_dir) / RECORDER_INFO_FILE
    return read_json(path) if path.exists() else {}


def write_recorder_info(session_dir, **updates):
    path = Path(session_dir) / RECORDER_INFO_FILE
    current = read_json(path) if path.exists() else {}
    current.update(updates)
    atomic_json_write(path, current)
    return current


def signal_process_group(pid, sig):
    if not pid:
        return
    try:
        os.killpg(int(pid), sig)
    except ProcessLookupError:
        pass


def record_worker(session_dir):
    """Run as a child process so finish/cancel can observe recorder exit status."""
    session_dir = Path(session_dir).resolve()
    state = load_state(session_dir)
    command = state["record_command"]
    log_path = session_dir / "record.log"
    with log_path.open("a", encoding="utf-8") as log_stream:
        child = subprocess.Popen(command, cwd=session_dir, stdout=log_stream,
                                 stderr=subprocess.STDOUT, start_new_session=True)
        write_recorder_info(session_dir, worker_pid=os.getpid(), child_pid=child.pid,
                            started_at=now_utc())

        def forward(signum, _frame):
            signal_process_group(child.pid, signum)

        signal.signal(signal.SIGINT, forward)
        signal.signal(signal.SIGTERM, forward)
        return_code = child.wait()
    write_recorder_info(session_dir, return_code=return_code, stopped_at=now_utc())
    return return_code


def start_session(config_path, session_name=None, record_command=None):
    config = load_config(config_path)
    session_root = Path(config["session_root"])
    session_root.mkdir(parents=True, exist_ok=True)
    safe_name = re.sub(r"[^A-Za-z0-9_.-]+", "_", session_name or "calibration")
    session_id = "{0}_{1}_{2}".format(
        dt.datetime.now().strftime("%Y%m%d_%H%M%S"), safe_name, uuid.uuid4().hex[:8])
    session_dir = (session_root / session_id).resolve()
    session_dir.mkdir(parents=True)
    (session_dir / SESSION_MARKER).write_text("kalibr_ros2 calibration session\n", encoding="utf-8")

    if record_command is None:
        command = command_for_bag(config, session_dir / "bag")
    else:
        command = shlex.split(record_command)
        command = [item.replace("{bag_dir}", str(session_dir / "bag")) for item in command]
    if not command:
        raise SessionError("CONFIG_INVALID", "record command is empty")
    if not any(str(session_dir / "bag") in item for item in command):
        raise SessionError("CONFIG_INVALID", "record command must include {bag_dir}")

    save_config_snapshot(session_dir, config)
    state = {
        "session_id": session_id,
        "session_dir": str(session_dir),
        "bag_dir": str(session_dir / "bag"),
        "record_command": command,
        "config_path": str(session_dir / "config.yaml"),
        "state": "STARTING",
        "created_at": now_utc(),
    }
    atomic_json_write(session_dir / STATE_FILE, state)

    recorder_environment = sourced_ros_environment(config)
    worker = subprocess.Popen([sys.executable, str(SCRIPT_PATH), "_record-worker", str(session_dir)],
                              cwd=session_dir, env=recorder_environment, start_new_session=True,
                              stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                              stderr=subprocess.DEVNULL)
    write_recorder_info(session_dir, worker_pid=worker.pid)
    state = set_state(session_dir, "RECORDING", recorder_pid=worker.pid, started_at=now_utc())
    time.sleep(0.5)
    if not process_alive(worker.pid):
        info = recorder_info(session_dir)
        set_state(session_dir, "FAILED", error_code="RECORDER_FAILED",
                  error_message="recorder process exited during startup", recorder=info)
        raise SessionError("RECORDER_FAILED", "recorder process exited during startup; see record.log")
    print(json.dumps({"accepted": True, "session_id": session_id,
                      "session_dir": str(session_dir), "bag_dir": state["bag_dir"]},
                     ensure_ascii=False, indent=2))


def stop_recorder(session_dir, timeout_sec=15.0):
    info = recorder_info(session_dir)
    worker_pid = info.get("worker_pid") or load_state(session_dir).get("recorder_pid")
    child_pid = info.get("child_pid")
    signal_process_group(worker_pid, signal.SIGINT)
    signal_process_group(child_pid, signal.SIGINT)
    deadline = time.monotonic() + timeout_sec
    while time.monotonic() < deadline:
        info = recorder_info(session_dir)
        if info.get("return_code") is not None and not process_alive(worker_pid):
            return int(info["return_code"])
        time.sleep(0.2)
    signal_process_group(worker_pid, signal.SIGTERM)
    signal_process_group(child_pid, signal.SIGTERM)
    time.sleep(2.0)
    info = recorder_info(session_dir)
    if process_alive(worker_pid) or process_alive(child_pid):
        signal_process_group(worker_pid, signal.SIGKILL)
        signal_process_group(child_pid, signal.SIGKILL)
        raise SessionError("RECORDER_STOP_TIMEOUT", "recorder did not stop within timeout")
    return int(info.get("return_code", 1))


def cdr_header_stamp(data):
    if data is None or len(data) < 12:
        return None
    representation = bytes(data[:2])
    if representation in (b"\x00\x01", b"\x00\x03", b"\x00\x07"):
        byte_order = "<"
    elif representation in (b"\x00\x00", b"\x00\x02", b"\x00\x06"):
        byte_order = ">"
    else:
        return None
    sec, nanosec = struct.unpack_from(byte_order + "iI", data, 4)
    if not 0 <= nanosec < 1_000_000_000:
        return None
    return sec + nanosec * 1e-9


def topic_records(bag_dir):
    bag_dir = Path(bag_dir)
    databases = sorted(bag_dir.glob("*.db3"))
    if not databases:
        raise SessionError("BAG_MISSING", "no SQLite3 database found in {0}".format(bag_dir))
    topics = {}
    for database in databases:
        connection = sqlite3.connect(str(database))
        try:
            topic_rows = connection.execute("SELECT id, name, type FROM topics").fetchall()
            for topic_id, name, type_name in topic_rows:
                rows = connection.execute(
                    "SELECT timestamp, substr(data, 1, 12) FROM messages "
                    "WHERE topic_id = ? ORDER BY id", (topic_id,)).fetchall()
                entry = topics.setdefault(name, {"type": type_name, "records": [],
                                                 "stamps": [], "bag_stamps": []})
                entry["records"].extend(
                    (timestamp * 1e-9, cdr_header_stamp(data)) for timestamp, data in rows)
        finally:
            connection.close()
    for entry in topics.values():
        entry["records"].sort(key=lambda record: record[0])
        entry["bag_stamps"] = [bag_stamp for bag_stamp, _ in entry["records"]]
        entry["stamps"] = [header_stamp for _, header_stamp in entry["records"]
                           if header_stamp is not None]
    return topics


def validate_topic(name, entry, settings, minimum_duration):
    stamps = entry["stamps"]
    expected_rate = float(settings["expected_rate_hz"])
    if expected_rate <= 0:
        raise SessionError("CONFIG_INVALID", "expected_rate_hz must be positive for {0}".format(name))
    if len(stamps) < int(settings.get("min_messages", 1)):
        raise SessionError("MESSAGE_COUNT_TOO_LOW", "{0}: only {1} messages".format(name, len(stamps)))
    if len(stamps) < 2:
        raise SessionError("TIMESTAMP_INVALID", "{0}: fewer than two valid header timestamps".format(name))
    if len(stamps) != len(entry["records"]):
        raise SessionError("TIMESTAMP_INVALID", "{0}: one or more CDR header timestamps are invalid".format(name))
    gaps = [right - left for left, right in zip(stamps, stamps[1:])]
    if any(gap <= 0 for gap in gaps):
        raise SessionError("TIMESTAMP_INVALID", "{0}: timestamps are not strictly increasing".format(name))
    duration = stamps[-1] - stamps[0]
    if duration < minimum_duration:
        raise SessionError("DURATION_TOO_SHORT", "{0}: duration {:.3f}s < {:.3f}s".format(
            name, duration, minimum_duration))
    period = 1.0 / expected_rate
    missing = sum(max(0, int(math.floor(gap / period + 0.5)) - 1) for gap in gaps)
    drop_rate = missing / float(len(stamps) + missing)
    max_gap_periods = max(gaps) / period
    if drop_rate > float(settings["max_drop_rate"]):
        raise SessionError("DROP_RATE_EXCEEDED", "{0}: drop rate {:.3%} > {:.3%}".format(
            name, drop_rate, float(settings["max_drop_rate"])))
    if max_gap_periods > float(settings["max_gap_periods"]):
        raise SessionError("GAP_TOO_LARGE", "{0}: max gap {:.2f} periods > {:.2f}".format(
            name, max_gap_periods, float(settings["max_gap_periods"])))
    return {
        "topic": name,
        "type": entry["type"],
        "messages": len(stamps),
        "duration_sec": duration,
        "measured_rate_hz": (len(stamps) - 1) / duration,
        "expected_rate_hz": expected_rate,
        "estimated_missing_messages": missing,
        "drop_rate": drop_rate,
        "max_gap_periods": max_gap_periods,
        "first_stamp": stamps[0],
        "last_stamp": stamps[-1],
    }


def validate_bag(config, bag_dir):
    bag_dir = Path(bag_dir).resolve()
    if not bag_dir.is_dir() or not (bag_dir / "metadata.yaml").is_file():
        raise SessionError("BAG_MISSING", "rosbag2 metadata.yaml is missing: {0}".format(bag_dir))
    topics = topic_records(bag_dir)
    calibration = config["calibration"]
    validation = config["validation"]
    report = {"bag_dir": str(bag_dir), "topics": {}, "validated_at": now_utc()}
    required = list(calibration["camera_topics"]) + [calibration["imu_topic"]]
    for topic in required:
        if topic not in topics:
            raise SessionError("TOPIC_MISSING", "configured topic is absent: {0}".format(topic))
    for topic in calibration["camera_topics"]:
        entry = topics[topic]
        if entry["type"] not in ("sensor_msgs/msg/Image", "sensor_msgs/msg/CompressedImage"):
            raise SessionError("TOPIC_TYPE_INVALID", "{0} has type {1}".format(topic, entry["type"]))
        report["topics"][topic] = validate_topic(
            topic, entry, validation["camera"][topic], float(validation["min_duration_sec"]))
    imu_topic = calibration["imu_topic"]
    if topics[imu_topic]["type"] != "sensor_msgs/msg/Imu":
        raise SessionError("TOPIC_TYPE_INVALID", "{0} has type {1}".format(imu_topic, topics[imu_topic]["type"]))
    report["topics"][imu_topic] = validate_topic(
        imu_topic, topics[imu_topic], validation["imu"], float(validation["min_duration_sec"]))

    starts = [item["first_stamp"] for item in report["topics"].values()]
    ends = [item["last_stamp"] for item in report["topics"].values()]
    overlap = min(ends) - max(starts)
    report["overlap_duration_sec"] = overlap
    if overlap < float(validation["min_overlap_sec"]):
        raise SessionError("TIME_RANGE_INVALID", "topic overlap {:.3f}s is below {:.3f}s".format(
            overlap, float(validation["min_overlap_sec"])))
    report["passed"] = True
    return report


def run_command(command, env, log_path, cwd):
    with Path(log_path).open("a", encoding="utf-8") as log_stream:
        log_stream.write("\n$ {0}\n".format(shlex.join(command)))
        log_stream.flush()
        try:
            completed = subprocess.run(command, cwd=cwd, env=env,
                                       stdout=log_stream, stderr=subprocess.STDOUT)
        except OSError as exc:
            raise SessionError("COMMAND_START_FAILED", "cannot start {0}: {1}".format(command[0], exc)) from exc
    return completed.returncode


def calibration_environment(session_dir, config, base_environment):
    env = base_environment.copy()
    env["PYTHONNOUSERSITE"] = "1"
    env["MPLBACKEND"] = "Agg"
    mpl_dir = Path(session_dir) / "matplotlib"
    mpl_dir.mkdir(exist_ok=True)
    env["MPLCONFIGDIR"] = str(mpl_dir)
    user_site = subprocess.check_output(
        [sys.executable, "-c", "import site; print(site.getusersitepackages())"], text=True).strip()
    wx_dir = Path(user_site) / "wx"
    if wx_dir.is_dir():
        override = Path(session_dir) / "python_override"
        override.mkdir(exist_ok=True)
        link = override / "wx"
        if not link.exists():
            link.symlink_to(wx_dir, target_is_directory=True)
        env["PYTHONPATH"] = str(override) + os.pathsep + env.get("PYTHONPATH", "")
    return env


def ros2_command(config, environment, *args):
    ros2 = shutil.which("ros2", path=environment.get("PATH"))
    if not ros2:
        raise SessionError("ROS2_NOT_SOURCED", "ros2 is unavailable; source ROS 2 Humble and install/setup.bash first")
    return [ros2, "run", "kalibr", *args]


def expected_output_paths(bag_dir):
    bag_tag = str(Path(bag_dir).resolve())
    return {
        "camera_chain": Path(bag_tag + "-camchain.yaml"),
        "camera_results": Path(bag_tag + "-results-cam.txt"),
        "imu_camera_chain": Path(bag_tag + "-camchain-imucam.yaml"),
        "imu": Path(bag_tag + "-imu.yaml"),
        "imu_camera_results": Path(bag_tag + "-results-imucam.txt"),
    }


def ensure_finite(value, path="value"):
    if isinstance(value, bool) or value is None or isinstance(value, str):
        return
    if isinstance(value, (int, float)):
        if not math.isfinite(float(value)):
            raise SessionError("RESULT_INVALID", "non-finite value at {0}".format(path))
        return
    if isinstance(value, list):
        for index, item in enumerate(value):
            ensure_finite(item, "{0}[{1}]".format(path, index))
        return
    if isinstance(value, dict):
        for key, item in value.items():
            ensure_finite(item, "{0}.{1}".format(path, key))


def validate_transform(matrix, path):
    if not isinstance(matrix, list) or len(matrix) != 4 or any(not isinstance(row, list) or len(row) != 4 for row in matrix):
        raise SessionError("RESULT_INVALID", "invalid transform shape at {0}".format(path))
    rotation = [[float(matrix[row][col]) for col in range(3)] for row in range(3)]
    orthogonal_error = max(abs(sum(rotation[row][k] * rotation[col][k] for k in range(3)) - (1.0 if row == col else 0.0))
                           for row in range(3) for col in range(3))
    determinant = (
        rotation[0][0] * (rotation[1][1] * rotation[2][2] - rotation[1][2] * rotation[2][1])
        - rotation[0][1] * (rotation[1][0] * rotation[2][2] - rotation[1][2] * rotation[2][0])
        + rotation[0][2] * (rotation[1][0] * rotation[2][1] - rotation[1][1] * rotation[2][0]))
    if orthogonal_error > 1e-2 or determinant <= 0.0:
        raise SessionError("RESULT_INVALID", "invalid rotation at {0}".format(path))


def validate_yaml_result(path, config, joint=False):
    try:
        with Path(path).open(encoding="utf-8") as stream:
            data = yaml.safe_load(stream)
    except (OSError, yaml.YAMLError) as exc:
        raise SessionError("RESULT_INVALID", "cannot parse {0}: {1}".format(path, exc)) from exc
    ensure_finite(data, str(path))
    if not isinstance(data, dict):
        raise SessionError("RESULT_INVALID", "result is not a YAML mapping: {0}".format(path))
    expected_topics = config["calibration"]["camera_topics"]
    for index, topic in enumerate(expected_topics):
        camera = data.get("cam{0}".format(index))
        if not isinstance(camera, dict) or camera.get("rostopic") != topic:
            raise SessionError("RESULT_INVALID", "camera topic mismatch in {0}".format(path))
        if joint:
            validate_transform(camera.get("T_cam_imu"), "{0}.cam{1}.T_cam_imu".format(path, index))
            shift = camera.get("timeshift_cam_imu")
            if abs(float(shift)) > float(config["validation"]["results"]["max_time_offset_sec"]):
                raise SessionError("RESULT_INVALID", "time offset exceeds threshold in {0}".format(path))
    if not joint and "cam1" in data:
        validate_transform(data["cam1"].get("T_cn_cnm1"), "{0}.cam1.T_cn_cnm1".format(path))
    return data


def numbers_for(pattern, text):
    return [float(value) for value in re.findall(pattern, text, flags=re.MULTILINE)]


def validate_text_results(paths, config):
    camera_text = Path(paths["camera_results"]).read_text(encoding="utf-8")
    camera_stds = re.findall(
        r"reprojection error:\s*\[[^\]]+\]\s*\+\-\s*\[([-+0-9.eE]+),\s*([-+0-9.eE]+)\]",
        camera_text, flags=re.MULTILINE)
    camera_std_values = [float(value) for pair in camera_stds for value in pair]
    if not camera_std_values or max(camera_std_values) > float(config["validation"]["results"]["camera_reprojection_std_max_px"]):
        raise SessionError("RESULT_INVALID", "camera reprojection standard deviation exceeds threshold")

    imu_text = Path(paths["imu_camera_results"]).read_text(encoding="utf-8")
    reprojection = numbers_for(r"Reprojection error \(cam\d+\):\s+mean\s+([-+0-9.eE]+)", imu_text)
    gyro = numbers_for(r"Gyroscope error \(imu\d+\):\s+mean\s+([-+0-9.eE]+)", imu_text)
    accel = numbers_for(r"Accelerometer error \(imu\d+\):\s+mean\s+([-+0-9.eE]+)", imu_text)
    limits = config["validation"]["results"]
    if not reprojection or max(reprojection) > float(limits["imu_reprojection_mean_max_px"]):
        raise SessionError("RESULT_INVALID", "IMU-camera reprojection mean exceeds threshold")
    if not gyro or max(gyro) > float(limits["imu_gyro_normalized_mean_max"]):
        raise SessionError("RESULT_INVALID", "normalized gyro residual exceeds threshold")
    if not accel or max(accel) > float(limits["imu_accel_normalized_mean_max"]):
        raise SessionError("RESULT_INVALID", "normalized accelerometer residual exceeds threshold")
    return {"camera_reprojection_std_px": camera_std_values,
            "imu_reprojection_mean_px": reprojection,
            "imu_gyro_normalized_mean": gyro,
            "imu_accel_normalized_mean": accel}


def finish_session(session_dir, keep_bag=True):
    session_dir = Path(session_dir).resolve()
    with SessionLock(session_dir):
        state = load_state(session_dir)
        if state["state"] != "RECORDING":
            raise SessionError("INVALID_STATE", "finish requires RECORDING, got {0}".format(state["state"]))
        config = load_config(state["config_path"])
        bag_dir = Path(state["bag_dir"])
        set_state(session_dir, "STOPPING")
        write_log(session_dir, "Stopping recorder")
        return_code = stop_recorder(session_dir)
        if return_code != 0:
            set_state(session_dir, "FAILED", error_code="RECORDER_FAILED",
                      error_message="recorder returned {0}".format(return_code))
            raise SessionError("RECORDER_FAILED", "recorder returned {0}; bag retained".format(return_code))

        set_state(session_dir, "VALIDATING_BAG")
        try:
            report = validate_bag(config, bag_dir)
            atomic_json_write(session_dir / VALIDATION_FILE, report)
        except SessionError as exc:
            set_state(session_dir, "FAILED", error_code=exc.code, error_message=exc.message)
            raise

        env = calibration_environment(session_dir, config, sourced_ros_environment(config))
        paths = expected_output_paths(bag_dir)
        calibration = config["calibration"]
        camera_topics = calibration["camera_topics"]
        camera_models = calibration["camera_models"]
        camera_command = ros2_command(
            config, env, "kalibr_calibrate_cameras", "--bag", str(bag_dir),
            "--topics", *camera_topics, "--models", *camera_models,
            "--target", calibration["target_yaml"], "--bag-freq", str(calibration.get("camera_bag_freq", 5.0)),
            "--mi-tol", str(calibration.get("mi_tol", 0.2)), "--dont-show-report", "--skip-report")

        set_state(session_dir, "CALIBRATING_CAMERA")
        write_log(session_dir, "Running camera calibration")
        if run_command(camera_command, env, session_dir / "calibration.log", session_dir) != 0:
            set_state(session_dir, "FAILED", error_code="CAMERA_CALIBRATION_FAILED",
                      error_message="camera calibration failed; bag retained")
            raise SessionError("CAMERA_CALIBRATION_FAILED", "camera calibration failed; bag retained")
        try:
            validate_yaml_result(paths["camera_chain"], config)
            if not paths["camera_results"].is_file():
                raise SessionError("RESULT_INVALID", "camera result text is missing")
        except SessionError as exc:
            set_state(session_dir, "FAILED", error_code=exc.code, error_message=exc.message)
            raise

        imu_command = ros2_command(
            config, env, "kalibr_calibrate_imu_camera", "--bag", str(bag_dir),
            "--cams", str(paths["camera_chain"]), "--imu", calibration["imu_yaml"],
            "--imu-models", str(calibration.get("imu_model", "calibrated")),
            "--target", calibration["target_yaml"], "--bag-freq",
            str(calibration.get("imu_camera_bag_freq", 3.0)), "--dont-show-report", "--skip-report")

        set_state(session_dir, "CALIBRATING_IMU_CAMERA")
        write_log(session_dir, "Running IMU-camera calibration")
        if run_command(imu_command, env, session_dir / "calibration.log", session_dir) != 0:
            set_state(session_dir, "FAILED", error_code="IMU_CAMERA_CALIBRATION_FAILED",
                      error_message="IMU-camera calibration failed; bag retained")
            raise SessionError("IMU_CAMERA_CALIBRATION_FAILED", "IMU-camera calibration failed; bag retained")
        try:
            validate_yaml_result(paths["imu_camera_chain"], config, joint=True)
            if not paths["imu_camera_results"].is_file() or not paths["imu"].is_file():
                raise SessionError("RESULT_INVALID", "IMU-camera result files are incomplete")
            metrics = validate_text_results(paths, config)
        except SessionError as exc:
            set_state(session_dir, "FAILED", error_code=exc.code, error_message=exc.message)
            raise

        if not keep_bag:
            set_state(session_dir, "CLEANING_BAG", result_metrics=metrics,
                      delete_bag_requested=True)
            write_log(session_dir, "Calibration passed; deleting recorded bag as the final step")
            try:
                validate_owned_bag_path(session_dir, bag_dir)
                shutil.rmtree(bag_dir)
            except SessionError as exc:
                set_state(session_dir, "FAILED", error_code=exc.code,
                          error_message="calibration passed but bag cleanup was refused: {0}".format(exc.message))
                raise
            except OSError as exc:
                set_state(session_dir, "FAILED", error_code="BAG_CLEANUP_FAILED",
                          error_message="calibration passed but bag deletion failed: {0}".format(exc))
                raise SessionError("BAG_CLEANUP_FAILED", str(exc)) from exc
        else:
            write_log(session_dir, "Calibration passed; keeping the recorded bag")
        final_state = set_state(
            session_dir, "SUCCEEDED", result_metrics=metrics, bag_deleted=not keep_bag,
            bag_retained=keep_bag,
            output_dir=str(session_dir), camera_chain_yaml=str(paths["camera_chain"]),
            imu_camera_chain_yaml=str(paths["imu_camera_chain"]), validation_json=str(session_dir / VALIDATION_FILE),
            finished_at=now_utc())
        print(json.dumps(final_state, ensure_ascii=False, indent=2))


def cancel_session(session_dir):
    session_dir = Path(session_dir).resolve()
    with SessionLock(session_dir):
        state = load_state(session_dir)
        if state["state"] in {"CANCELLED", "SUCCEEDED"}:
            print(json.dumps({"success": True, "state": state["state"]}, ensure_ascii=False, indent=2))
            return
        if state["state"] != "RECORDING":
            raise SessionError("INVALID_STATE", "cancel requires RECORDING, got {0}".format(state["state"]))
        set_state(session_dir, "STOPPING")
        stop_recorder(session_dir)
        bag_dir = Path(state["bag_dir"])
        if bag_dir.exists():
            validate_owned_bag_path(session_dir, bag_dir)
            shutil.rmtree(bag_dir)
        final_state = set_state(session_dir, "CANCELLED", bag_deleted=True, finished_at=now_utc())
        print(json.dumps(final_state, ensure_ascii=False, indent=2))


def status_session(session_dir):
    session_dir = Path(session_dir).resolve()
    state = load_state(session_dir)
    info = recorder_info(session_dir)
    output = dict(state)
    output["recorder_alive"] = process_alive(info.get("worker_pid") or state.get("recorder_pid"))
    output["bag_exists"] = Path(state.get("bag_dir", "")).exists()
    print(json.dumps(output, ensure_ascii=False, indent=2))


def validate_owned_bag_path(session_dir, bag_dir):
    session_dir = Path(session_dir).resolve()
    bag_dir = Path(bag_dir).resolve()
    if not (session_dir / SESSION_MARKER).is_file():
        raise SessionError("INVALID_SESSION", "session ownership marker is missing")
    if bag_dir.parent != session_dir or bag_dir.name != "bag":
        raise SessionError("INVALID_SESSION", "refusing to remove a bag outside the session directory")


def validate_only(config_path, bag_dir):
    config = load_config(config_path)
    report = validate_bag(config, bag_dir)
    print(json.dumps(report, ensure_ascii=False, indent=2))


def build_parser():
    parser = argparse.ArgumentParser(
        description="Kalibr ROS 2 strict calibration session manager",
        epilog=USAGE,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    subparsers = parser.add_subparsers(dest="command", required=True)

    start = subparsers.add_parser("start", help="start rosbag recording")
    start.add_argument("--config", default=str(DEFAULT_CONFIG))
    start.add_argument("--session-name", default="calibration")
    start.add_argument("--record-command", help="override command; use {bag_dir} as output placeholder")

    for name, help_text in (("status", "show session status"), ("cancel", "stop and delete the recorded bag"),
                            ("finish", "stop, validate and calibrate; keep the bag unless --delete-bag is set")):
        command = subparsers.add_parser(name, help=help_text)
        command.add_argument("--session-dir", required=True)
        if name == "finish":
            cleanup = command.add_mutually_exclusive_group()
            cleanup.add_argument(
                "--delete-bag", dest="keep_bag", action="store_false",
                help="delete the session bag after every validation succeeds (last step)")
            cleanup.add_argument(
                "--keep-bag", dest="keep_bag", action="store_true",
                help="keep the session bag after success (default)")
            command.set_defaults(keep_bag=True)

    validate = subparsers.add_parser("validate", help="validate an existing rosbag2 without calibrating")
    validate.add_argument("--config", default=str(DEFAULT_CONFIG))
    validate.add_argument("--bag", required=True)

    worker = subparsers.add_parser("_record-worker", help=argparse.SUPPRESS)
    worker.add_argument("session_dir")
    return parser


def main(argv=None):
    args = build_parser().parse_args(argv)
    try:
        if args.command == "_record-worker":
            return record_worker(args.session_dir)
        if args.command == "start":
            start_session(args.config, args.session_name, args.record_command)
        elif args.command == "status":
            status_session(args.session_dir)
        elif args.command == "cancel":
            cancel_session(args.session_dir)
        elif args.command == "finish":
            finish_session(args.session_dir, keep_bag=args.keep_bag)
        elif args.command == "validate":
            validate_only(args.config, args.bag)
        return 0
    except SessionError as exc:
        print("ERROR[{0}]: {1}".format(exc.code, exc.message), file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print("Interrupted", file=sys.stderr)
        return 130


if __name__ == "__main__":
    sys.exit(main())

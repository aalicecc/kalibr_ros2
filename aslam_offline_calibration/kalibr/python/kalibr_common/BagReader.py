"""Read ROS 1 bags and ROS 2 rosbag2 SQLite3 recordings for Kalibr.

The ROS 2 path intentionally uses rosbag2_py and generated ROS message classes,
so image/IMU decoding continues to use the message fields expected by Kalibr.
"""
import os
import glob
import sqlite3
import struct


def _is_ros2_bag(path):
    return os.path.isdir(path) and os.path.isfile(os.path.join(path, "metadata.yaml"))


def stamp_parts(stamp):
    """Return (seconds, nanoseconds) for ROS 1 or ROS 2 builtin time values."""
    sec = getattr(stamp, "secs", getattr(stamp, "sec", None))
    nsec = getattr(stamp, "nsecs", getattr(stamp, "nanosec", None))
    if sec is None or nsec is None:
        raise TypeError("Unsupported ROS timestamp: {}".format(type(stamp).__name__))
    return int(sec), int(nsec)


def stamp_seconds(stamp):
    sec, nsec = stamp_parts(stamp)
    return sec + nsec * 1e-9


def stamp_nanoseconds(stamp):
    sec, nsec = stamp_parts(stamp)
    return sec * 1000000000 + nsec


def message_type(message):
    ros1_type = getattr(message, "_type", None)
    if ros1_type:
        return ros1_type
    module = message.__class__.__module__.split(".")
    if len(module) >= 3 and module[-2].startswith("_"):
        return "{}/{}".format(module[-3], module[-2][1:])
    return "{}/{}".format(module[0], message.__class__.__name__)


class _Rosbag2Records:
    """Lazy random-access view over one rosbag2 topic."""
    def __init__(self, connection, topic_id, message_class):
        self._connection = connection
        self._topic_id = topic_id
        self._message_class = message_class
        self._entries = []

        cursor = connection.execute(
            "SELECT id, timestamp, substr(data, 1, 12) "
            "FROM messages WHERE topic_id = ? ORDER BY id", (topic_id,))
        for message_id, bag_timestamp, cdr_header in cursor:
            try:
                header_timestamp = _cdr_header_timestamp_nanoseconds(cdr_header)
            except (ValueError, struct.error):
                # Keep compatibility with non-standard CDR encodings. This
                # fallback is rare; standard ROS 2 sensor messages use CDR.
                payload = connection.execute(
                    "SELECT data FROM messages WHERE id = ? AND topic_id = ?",
                    (message_id, topic_id)).fetchone()[0]
                from rclpy.serialization import deserialize_message
                message = deserialize_message(payload, message_class)
                header_timestamp = stamp_nanoseconds(message.header.stamp)
            self._entries.append((message_id, header_timestamp, bag_timestamp))

    def __len__(self):
        return len(self._entries)

    def __getitem__(self, index):
        message_id, _, bag_timestamp = self._entries[index]
        payload = self._connection.execute(
            "SELECT data FROM messages WHERE id = ? AND topic_id = ?",
            (message_id, self._topic_id)).fetchone()
        if payload is None:
            raise IndexError(index)
        from rclpy.serialization import deserialize_message
        message = deserialize_message(payload[0], self._message_class)
        return message, _HeaderTimestamp(bag_timestamp)

    def timestamp(self, index):
        return self._entries[index][1]

    def header_timestamp_nanoseconds(self, index):
        return self._entries[index][1]


class _Rosbag1Records:
    """Lazy random-access view over the ROS 1 bag index."""
    def __init__(self, bag, topic):
        connections = bag._get_connections(topics=topic)
        indexes = bag._get_indexes(connections)
        try:
            self._index = next(indexes)
        except StopIteration:
            self._index = []
        self._bag = bag

    def __len__(self):
        return len(self._index)

    def __getitem__(self, index):
        entry = self._index[index]
        _, message, stamp = self._bag._read_message(entry.position)
        return message, stamp

    def header_timestamp_nanoseconds(self, index):
        message, _ = self[index]
        return stamp_nanoseconds(message.header.stamp)


class BagReader:
    """Small indexed reader shared by Kalibr's image and IMU datasets."""
    def __init__(self, path):
        self.path = path
        self._ros1 = not _is_ros2_bag(path)
        if self._ros1:
            try:
                import rosbag
            except ImportError as exc:
                raise RuntimeError("This is not a rosbag2 directory and ROS 1 rosbag is unavailable: {}".format(path)) from exc
            self._bag = rosbag.Bag(path)
            return

        try:
            from rosidl_runtime_py.utilities import get_message
        except ImportError as exc:
            raise RuntimeError("Reading rosbag2 requires a sourced ROS 2 Humble environment") from exc
        self._get_message = get_message

        database_paths = sorted(glob.glob(os.path.join(path, "*.db3")))
        if not database_paths:
            raise RuntimeError("No SQLite3 rosbag2 database files found in {}".format(path))
        self._connections = [sqlite3.connect("file:{}?mode=ro".format(os.path.abspath(db)), uri=True)
                             for db in database_paths]
        self._topic_metadata = []
        self._records = {}
        for connection_index, connection in enumerate(self._connections):
            topic_metadata = {}
            for topic_id, topic_name, type_name in connection.execute(
                    "SELECT id, name, type FROM topics"):
                topic_metadata[topic_name] = (topic_id, type_name)
            self._topic_metadata.append(topic_metadata)

    def records(self, topic):
        if self._ros1:
            return _Rosbag1Records(self._bag, topic)
        output = []
        for connection_index, connection in enumerate(self._connections):
            key = (connection_index, topic)
            metadata = self._topic_metadata[connection_index].get(topic)
            if metadata is None:
                continue
            if key not in self._records:
                topic_id, type_name = metadata
                self._records[key] = _Rosbag2Records(
                    connection, topic_id, self._get_message(type_name))
            records = self._records[key]
            if len(self._connections) == 1:
                return records
            output.extend(_IndexedMessage(records, index) for index in range(len(records)))
        return _IndexedRecords(output)

    def messages(self, topic):
        for record in self.records(topic):
            yield record[0], record[1]

    def close(self):
        if self._ros1:
            self._bag.close()
        else:
            for connection in self._connections:
                connection.close()


class _IndexedMessage:
    def __init__(self, records, index):
        self._records = records
        self._index = index

    def __getitem__(self, index):
        if index == 0:
            return self._records[self._index][0]
        if index == 1:
            return self._records[self._index][1]
        raise IndexError(index)

    def header_timestamp_nanoseconds(self):
        return self._records.header_timestamp_nanoseconds(self._index)


class _IndexedRecords(list):
    def header_timestamp_nanoseconds(self, index):
        return self[index].header_timestamp_nanoseconds()


class _HeaderTimestamp:
    def __init__(self, nanoseconds):
        self._nanoseconds = nanoseconds

    @property
    def secs(self):
        return divmod(self._nanoseconds, 1000000000)[0]

    @property
    def nsecs(self):
        return divmod(self._nanoseconds, 1000000000)[1]

    def to_sec(self):
        return self._nanoseconds * 1e-9


def _cdr_header_timestamp_nanoseconds(header):
    """Extract Header.stamp from the fixed prefix of a ROS 2 CDR message."""
    encapsulation = bytes(header[:4])
    if len(encapsulation) < 4:
        raise ValueError("Truncated CDR encapsulation header")

    representation = encapsulation[:2]
    if representation in (b"\x00\x01", b"\x00\x03", b"\x00\x07"):
        byte_order = "<"
    elif representation in (b"\x00\x00", b"\x00\x02", b"\x00\x06"):
        byte_order = ">"
    else:
        raise ValueError("Unsupported CDR representation: {}".format(representation.hex()))

    sec, nanosec = struct.unpack_from(byte_order + "iI", header, 4)
    return sec * 1000000000 + nanosec

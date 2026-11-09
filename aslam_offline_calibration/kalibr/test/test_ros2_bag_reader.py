import importlib.util
from pathlib import Path
import tempfile
import unittest
from unittest import mock

import rosbag2_py
from rclpy.serialization import serialize_message
from sensor_msgs.msg import Image

_reader_path = (Path(__file__).resolve().parents[1] / "python" /
                "kalibr_common" / "BagReader.py")
_spec = importlib.util.spec_from_file_location("kalibr_bag_reader", _reader_path)
_reader_module = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_reader_module)
BagReader = _reader_module.BagReader
message_type = _reader_module.message_type
stamp_nanoseconds = _reader_module.stamp_nanoseconds


class Rosbag2ReaderTest(unittest.TestCase):
    def test_reads_topic_messages_and_header_timestamps(self):
        with tempfile.TemporaryDirectory(prefix="kalibr_ros2_bag_test_") as directory:
            bag_path = directory + "/recording"
            writer = rosbag2_py.SequentialWriter()
            writer.open(
                rosbag2_py.StorageOptions(uri=bag_path, storage_id="sqlite3"),
                rosbag2_py.ConverterOptions(
                    input_serialization_format="cdr",
                    output_serialization_format="cdr"))
            writer.create_topic(rosbag2_py.TopicMetadata(
                name="/left/image_raw",
                type="sensor_msgs/msg/Image",
                serialization_format="cdr"))

            for header_seconds, bag_seconds in ((3, 4), (1, 5), (2, 6)):
                message = Image()
                message.header.stamp.sec = header_seconds
                message.header.stamp.nanosec = 123
                writer.write(
                    "/left/image_raw", serialize_message(message),
                    bag_seconds * 1000000000)
            del writer

            reader = BagReader(bag_path)
            try:
                import rclpy.serialization
                with mock.patch(
                        "rclpy.serialization.deserialize_message",
                        wraps=rclpy.serialization.deserialize_message) as deserialize:
                    records = reader.records("/left/image_raw")
                    self.assertEqual(len(records), 3)
                    self.assertEqual(records.header_timestamp_nanoseconds(0), 3000000123)
                    self.assertEqual(deserialize.call_count, 0)

                    first, bag_stamp = records[0]
                    self.assertEqual(deserialize.call_count, 1)

                self.assertEqual(message_type(first), "sensor_msgs/Image")
                self.assertEqual(stamp_nanoseconds(first.header.stamp), 3000000123)
                self.assertEqual(bag_stamp.to_sec(), 4.0)
                self.assertEqual(
                    [stamp_nanoseconds(records[index][0].header.stamp)
                     for index in range(len(records))],
                    [3000000123, 1000000123, 2000000123])
            finally:
                reader.close()


if __name__ == "__main__":
    unittest.main()

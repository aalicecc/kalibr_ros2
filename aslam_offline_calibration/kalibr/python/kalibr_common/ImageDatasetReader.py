import cv_bridge
import cv2
from kalibr_common.BagReader import BagReader, message_type, stamp_nanoseconds, stamp_seconds
import os
import numpy as np
import pylab as pl
import aslam_cv as acv
import sm


class BagImageDatasetReaderIterator(object):
  def __init__(self, dataset, indices=None):
    self.dataset = dataset
    if indices is None:
      self.indices = np.arange(dataset.numImages())
    else:
      self.indices = indices
    self.iter = self.indices.__iter__()

  def __iter__(self):
    return self

  def next(self):
    # required for python 2.x compatibility
    idx = next(self.iter)
    return self.dataset.getImage(idx)

  def __next__(self):
    idx = next(self.iter)
    return self.dataset.getImage(idx)


class BagImageDatasetReader(object):
  def __init__(self, bagfile, imagetopic, bag_from_to=None, perform_synchronization=False, bag_freq=None):
    self.bagfile = bagfile
    self.topic = imagetopic
    self.perform_synchronization = perform_synchronization
    self.bag = BagReader(bagfile)
    self.uncompress = None
    if imagetopic is None:
      raise RuntimeError(
          "Please pass in a topic name referring to the image stream in the bag file\n{0}".format(self.bag))

    self.CVB = cv_bridge.CvBridge()
    # Get the message indices
    self.records = self.bag.records(imagetopic)
    if len(self.records) == 0:
      raise RuntimeError("Could not find topic {0} in {1}.".format(imagetopic, self.bagfile))
    self.indices = np.arange(len(self.records))

    # sort the indices by header.stamp
    self.indices = self.sortByTime(self.indices)

    # go through the bag and remove the indices outside the timespan [bag_start_time, bag_end_time]
    if bag_from_to:
      self.indices = self.truncateIndicesFromTime(self.indices, bag_from_to)

    # go through and remove indices not at the correct frequency
    if bag_freq:
      self.indices = self.truncateIndicesFromFreq(self.indices, bag_freq)

  # sort the ros messegaes by the header time not message time
  def sortByTime(self, indices):
    self.timestamp_corrector = sm.DoubleTimestampCorrector()
    timestamps = list()
    for idx in indices:
      timestamp = self.records.header_timestamp_nanoseconds(idx)
      timestamps.append(timestamp)
      if self.perform_synchronization:
        data, stamp = self.records[idx]
        self.timestamp_corrector.correctTimestamp(stamp_seconds(data.header.stamp),
                                                  stamp_seconds(stamp))

    sorted_tuples = sorted(zip(timestamps, indices))
    sorted_indices = [tuple_value[1] for tuple_value in sorted_tuples]
    return sorted_indices

  def truncateIndicesFromTime(self, indices, bag_from_to):
    # get the timestamps
    timestamps = [(idx, self.records.header_timestamp_nanoseconds(idx) * 1e-9)
                  for idx in indices]

    bagstart = min(timestamp for _, timestamp in timestamps)
    baglength = max(timestamp for _, timestamp in timestamps) - bagstart

    # some value checking
    if bag_from_to[0] >= bag_from_to[1]:
      raise RuntimeError("Bag start time must be bigger than end time.".format(bag_from_to[0]))
    if bag_from_to[0] < 0.0:
      sm.logWarn("Bag start time of {0} s is smaller 0".format(bag_from_to[0]))
    if bag_from_to[1] > baglength:
      sm.logWarn("Bag end time of {0} s is bigger than the total length of {1} s".format(
          bag_from_to[1], baglength))

    # find the valid timestamps
    valid_indices = []
    for idx, timestamp in timestamps:
      if timestamp >= (bagstart + bag_from_to[0]) and timestamp <= (bagstart + bag_from_to[1]):
        valid_indices.append(idx)
    sm.logWarn(
        "BagImageDatasetReader: truncated {0} / {1} images (from-to).".format(len(indices) - len(valid_indices), len(indices)))
    return valid_indices

  def truncateIndicesFromFreq(self, indices, freq):

    # some value checking
    if freq < 0.0:
      raise RuntimeError("Frequency {0} Hz is smaller 0".format(freq))

    # find the valid timestamps
    timestamp_last = -1
    valid_indices = []
    for idx in indices:
      timestamp = self.records.header_timestamp_nanoseconds(idx) * 1e-9
      if timestamp_last < 0.0:
        timestamp_last = timestamp
        valid_indices.append(idx)
        continue
      if (timestamp - timestamp_last) >= 1.0 / freq:
        timestamp_last = timestamp
        valid_indices.append(idx)
    sm.logWarn(
      "BagImageDatasetReader: truncated {0} / {1} images (frequency)".format(len(indices) - len(valid_indices), len(indices)))
    return valid_indices

  def __iter__(self):
    # Reset the bag reading
    return self.readDataset()

  def readDataset(self):
    return BagImageDatasetReaderIterator(self, self.indices)

  def readDatasetShuffle(self):
    indices = self.indices
    np.random.shuffle(indices)
    return BagImageDatasetReaderIterator(self, indices)

  def numImages(self):
    return len(self.indices)

  def getImage(self, idx):
    data, stamp = self.records[idx]
    if self.perform_synchronization:
      timestamp = acv.Time(self.timestamp_corrector.getLocalTime(
          stamp_seconds(data.header.stamp)))
    else:
      sec, nsec = divmod(stamp_nanoseconds(data.header.stamp), 1000000000)
      timestamp = acv.Time(sec, nsec)
    data_type = message_type(data)
    if data_type == 'mv_cameras/ImageSnappyMsg':
      if self.uncompress is None:
        from snappy import uncompress
        self.uncompress = uncompress
      img_data = np.reshape(self.uncompress(np.fromstring(
          data.data, dtype='uint8')), (data.height, data.width), order="C")
    elif data_type == 'sensor_msgs/CompressedImage':
      # compressed images only have either mono or BGR normally (png and jpeg)
      # https://github.com/ros-perception/vision_opencv/blob/906d326c146bd1c6fbccc4cd1268253890ac6e1c/cv_bridge/src/cv_bridge.cpp#L480-L506
      img_data = np.array(self.CVB.compressed_imgmsg_to_cv2(data))
      if len(img_data.shape) > 2 and img_data.shape[2] == 3:
        img_data = cv2.cvtColor(img_data, cv2.COLOR_BGR2GRAY)
    elif data_type == 'sensor_msgs/Image':
      if data.encoding == "16UC1" or data.encoding == "mono16":
        image_16u = np.array(self.CVB.imgmsg_to_cv2(data))
        img_data = (image_16u / 256).astype("uint8")
      elif data.encoding == "8UC1" or data.encoding == "mono8":
        img_data = np.array(self.CVB.imgmsg_to_cv2(data))
      elif data.encoding == "8UC3" or data.encoding == "bgr8":
        img_data = np.array(self.CVB.imgmsg_to_cv2(data))
        img_data = cv2.cvtColor(img_data, cv2.COLOR_BGR2GRAY)
      elif data.encoding == "rgb8":
        img_data = np.array(self.CVB.imgmsg_to_cv2(data))
        img_data = cv2.cvtColor(img_data, cv2.COLOR_RGB2GRAY)
      elif data.encoding == "8UC4" or data.encoding == "bgra8":
        img_data = np.array(self.CVB.imgmsg_to_cv2(data))
        img_data = cv2.cvtColor(img_data, cv2.COLOR_BGRA2GRAY)
      # bayes encodings conversions from
      # https://github.com/ros-perception/image_pipeline/blob/6caf51bd4484ae846cd8a199f7a6a4b060c6373a/image_proc/src/libimage_proc/processor.cpp#L70
      elif data.encoding == "bayer_rggb8":
        img_data = np.array(self.CVB.imgmsg_to_cv2(data))
        img_data = cv2.cvtColor(img_data, cv2.COLOR_BAYER_BG2GRAY)
      elif data.encoding == "bayer_bggr8":
        img_data = np.array(self.CVB.imgmsg_to_cv2(data))
        img_data = cv2.cvtColor(img_data, cv2.COLOR_BAYER_RG2GRAY)
      elif data.encoding == "bayer_gbrg8":
        img_data = np.array(self.CVB.imgmsg_to_cv2(data))
        img_data = cv2.cvtColor(img_data, cv2.COLOR_BAYER_GR2GRAY)
      elif data.encoding == "bayer_grbg8":
        img_data = np.array(self.CVB.imgmsg_to_cv2(data))
        img_data = cv2.cvtColor(img_data, cv2.COLOR_BAYER_GB2GRAY)
      else:
        raise RuntimeError(
            "Unsupported Image Encoding: '{}'\nSupported are: "
            "16UC1 / mono16, 8UC1 / mono8, 8UC3 / rgb8 / bgr8, 8UC4 / bgra8, "
            "bayer_rggb8, bayer_bggr8, bayer_gbrg8, bayer_grbg8".format(data.encoding))
    else:
      raise RuntimeError(
        "Unsupported Image Type: '{}'\nSupported are: "
        "mv_cameras/ImageSnappyMsg, sensor_msgs/CompressedImage, sensor_msgs/Image".format(data_type))
    return (timestamp, img_data)

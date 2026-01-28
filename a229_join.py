import argparse
import subprocess
import tempfile
import sys
import os
from datetime import datetime
import nvtk_mp42gpx
from enum import Enum
from collections import namedtuple

class CameraDirection(Enum):
    FRONT = "front"
    REAR = "rear"

class VideoFile:
    def __init__(self, path):
        self.folder = os.path.dirname(path)
        self.filename = os.path.basename(path)
        
        self.date = datetime.strptime(self.filename[:16], '%Y_%m%d_%H%M%S')
        self.number = self.filename[17:-5]
        self.direction = CameraDirection.FRONT
        if self.filename[-5] == 'R':
            self.direction = CameraDirection.REAR

        self.gpx = []

    def str_date(self):
        return str(self.date)

    def __str__(self):
        return self.mp4file + self.str_date() + (' gps ' + str(len(self.gpx)) if len(self.gpx) > 0 else '')

    def read_gps(self):
        if not self.gpx:
            self.gpx = nvtk_mp42gpx.extract_gpx(self.mp4file)
        return self.gpx

VideoPair = namedtuple('VideoPair', ['front', 'rear'])

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('input', help='Input dir', action="store")
    parser.add_argument('out', help='Output dir', action="store")
    args = parser.parse_args()

    front_files = []
    rear_files = []
    for root, dirs, files in os.walk(args.input):
        for file in files:
            full_path = os.path.join(root, file)
            if file.lower().endswith('.mp4'):
                vid = VideoFile(full_path)
                if vid.direction == CameraDirection.REAR:
                    rear_files.append(vid)
                else:
                    front_files.append(vid)
    front_files.sort(key=lambda v: v.date)
    rear_files.sort(key=lambda v: v.date)
    pairs = []
    while len(front_files) > 0 and len(rear_files) > 0:
        if abs((front_files[0].date - rear_files[0].date).total_seconds()) <= 10:
            pairs.append(VideoPair(front_files.pop(0), rear_files.pop(0)))
        elif front_files[0].date < rear_files[0].date:
            print(f"No rear match for front: {front_files[0].filename}")
            pairs.append(VideoPair(front_files.pop(0), None))
        else:
            print(f"No front match for rear: {rear_files[0].filename}")
            pairs.append(VideoPair(None, rear_files.pop(0)))

if __name__ == '__main__':
    main()

# v = VideoFile("/home/gavin/Datasets/viofo/Movie/2026_0118_144124_000001F.MP4")
# # v = VideoFile("/home/gavin/Datasets/viofo/Movie/2026_0118_144124_000002R.MP4")

# print(v.date)
# print(v.number)
# print(v.direction)
import argparse
import subprocess
import tempfile
import sys
import os
from datetime import datetime, timedelta
import nvtk_mp42gpx
from enum import Enum
from collections import namedtuple
from typing import Optional

class CameraDirection(Enum):
    FRONT = "front"
    REAR = "rear"

class VideoFile:
    def __init__(self, path):
        self.folder = os.path.dirname(path)
        self.filename = os.path.basename(path)
        self.path = path
        
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

    def get_duration(self):
        result = subprocess.run(["ffprobe", "-v", "error", "-show_entries",
                             "format=duration", "-of",
                             "default=noprint_wrappers=1:nokey=1", self.path],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT)
        return float(result.stdout)


VideoPair = namedtuple('VideoPair', ['front', 'rear'])

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('input', help='Input dir', action="store")
    parser.add_argument('out', help='Output dir', action="store")
    args = parser.parse_args()

    # create video pairs
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
    pairs: list[VideoPair] = []
    while len(front_files) > 0 and len(rear_files) > 0:
        if abs((front_files[0].date - rear_files[0].date).total_seconds()) <= 10:
            pairs.append(VideoPair(front_files.pop(0), rear_files.pop(0)))
        elif front_files[0].date < rear_files[0].date:
            pairs.append(VideoPair(front_files.pop(0), None))
        else:
            pairs.append(VideoPair(None, rear_files.pop(0)))

    # group based on time
    groups = [[]]
    for pair in pairs:
        if groups[-1] == []:
            groups[-1].append(pair)
        else:
            date = None
            if pair.front is None:
                date = pair.rear.date
            elif pair.rear is None:
                date = pair.front.date
            else:
                date = min(pair.front.date, pair.rear.date)

            prev_date = None
            if groups[-1][-1].front is None:
                prev_date = groups[-1][-1].rear.date
            elif groups[-1][-1].rear is None:
                prev_date = groups[-1][-1].front.date
            else:
                prev_date = max(groups[-1][-1].front.date, groups[-1][-1].rear.date)

            if abs((date - prev_date).total_seconds()) <= 70:
                groups[-1].append(pair)
            else:
                groups.append([])
                groups[-1].append(pair)

    # get group durations
    # for i, group in enumerate(groups):
    #     if not group:
    #         continue
    #     first_pair = group[0]
    #     last_pair = group[-1]

    #     # Get the earliest date in the first pair
    #     if first_pair.front and first_pair.rear:
    #         start_time = min(first_pair.front.date, first_pair.rear.date)
    #     elif first_pair.front:
    #         start_time = first_pair.front.date
    #     else:
    #         start_time = first_pair.rear.date
        
    #     # Get the latest date + duration in the last pair
    #     if last_pair.front and last_pair.rear:
    #         # Use the file that ends latest
    #         front_end = last_pair.front.date
    #         front_end += timedelta(seconds=last_pair.front.get_duration())
    #         rear_end = last_pair.rear.date
    #         rear_end += timedelta(seconds=last_pair.rear.get_duration())
    #         end_time = max(front_end, rear_end)
    #     elif last_pair.front:
    #         end_time = last_pair.front.date
    #         end_time += timedelta(seconds=last_pair.front.get_duration())
    #     else:
    #         end_time = last_pair.rear.date
    #         end_time += timedelta(seconds=last_pair.rear.get_duration())
    #     print(f"Group {i+1}: {start_time.strftime('%Y-%m-%d %I:%M:%S %p')} - {end_time.strftime('%Y-%m-%d %I:%M:%S %p')} (interval: {end_time - start_time})")

    # Splice together all front and rear videos in each group
    for i, group in enumerate(groups):
        if not group:
            continue

        # Prepare lists of front and rear video paths
        front_paths = [pair.front.path for pair in group if pair.front]
        rear_paths = [pair.rear.path for pair in group if pair.rear]

        # Only join if there are videos
        # Get start and end time for naming
        first_pair = group[0]
        last_pair = group[-1]
        if first_pair.front and first_pair.rear:
            start_time = min(first_pair.front.date, first_pair.rear.date)
        elif first_pair.front:
            start_time = first_pair.front.date
        else:
            start_time = first_pair.rear.date

        if last_pair.front and last_pair.rear:
            front_end = last_pair.front.date + timedelta(seconds=last_pair.front.get_duration())
            rear_end = last_pair.rear.date + timedelta(seconds=last_pair.rear.get_duration())
            end_time = max(front_end, rear_end)
        elif last_pair.front:
            end_time = last_pair.front.date + timedelta(seconds=last_pair.front.get_duration())
        else:
            end_time = last_pair.rear.date + timedelta(seconds=last_pair.rear.get_duration())
        
        start_str = start_time.strftime('%Y-%m-%d %I:%M:%S %p')
        end_str = end_time.strftime('%I:%M:%S %p')

        if front_paths:
            front_list_file = os.path.join(tempfile.gettempdir(), f"front_list_{i}.txt")
            with open(front_list_file, "w") as f:
                for path in front_paths:
                    f.write(f"file '{path}'\n")
            front_out = os.path.join(args.out, f"{start_str}-{end_str}_front.mp4")
            subprocess.run([
                "ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", front_list_file,
                "-c", "copy", front_out
            ])
            print(f"Front videos for group {i+1} joined to {front_out}")

        if rear_paths:
            rear_list_file = os.path.join(tempfile.gettempdir(), f"rear_list_{i}.txt")
            with open(rear_list_file, "w") as f:
                for path in rear_paths:
                    f.write(f"file '{path}'\n")
            rear_out = os.path.join(args.out, f"{start_str}-{end_str}_rear.mp4")
            subprocess.run([
                "ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", rear_list_file,
                "-c", "copy", rear_out
            ])
            print(f"Rear videos for group {i+1} joined to {rear_out}")

if __name__ == '__main__':
    main()

# v = VideoFile("/home/gavin/Datasets/viofo/Movie/2026_0118_144124_000001F.MP4")
# # v = VideoFile("/home/gavin/Datasets/viofo/Movie/2026_0118_144124_000002R.MP4")

# print(v.date)
# print(v.number)
# print(v.direction)
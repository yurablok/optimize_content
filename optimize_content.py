# optimize_content
# Optimize size of videos and images by converting to webm and webp,
# with optional resizing and simple 60 FPS frame interpolation.
#
# Author: Yurii Blok
# License: Public Domain / Unlicense
# https://github.com/yurablok/optimize_content
# History:
# v0.1    2025-09-12    First release.

import random
import os, sys
import subprocess

files = []
argInput: bool = False
argResize: bool = False
arg60Fps: bool = False
argWithWebMP: bool = False
for arg in sys.argv[1:]:
    if argInput:
        files.append(arg)
        argInput = False
    elif arg == "-i":
        argInput = True
    elif arg == "-r":
        argResize = True
    elif arg == "-60":
        arg60Fps = True
    elif arg == "-w":
        argWithWebMP = True
    else:
        print(f"\033[91mUnknown arg: {arg}\033[0m")
        exit(1)

output_dir = "converted/"
os.makedirs(output_dir, exist_ok=True)

video_formats = [ ".mp4", ".m4v", ".mov", ".mkv", ".mpeg", ".wmv" ]
if argWithWebMP:
    video_formats.append(".webm")
animated_formats = [ ".gif" ]
images_formats = [ ".jpg", ".jpeg", ".png", ".bmp", ".avif" ]
if argWithWebMP:
    images_formats.append(".webp")

if len(files) == 0:
    files = [
        f for f in os.listdir(".")
            if f.lower().endswith((*video_formats, *animated_formats, *images_formats))
    ]
failed = []

ffmpeg2pass = "ffmpeg2pass-" + str(random.randint(100000000, 999999999))

for file in files:
    file_name, file_ext = os.path.splitext(os.path.split(file)[1])
    file_ext = file_ext.lower()

    try:
        stat_info = os.stat(file)
        original_times = (stat_info.st_atime, stat_info.st_mtime)

        if file_ext in video_formats:
            output_file = output_dir + file_name + ".webm"
            vf = ""
            if argResize:
                try:
                    cmd = [
                        "ffprobe", "-v", "error",
                        "-select_streams", "v:0",
                        "-show_entries", "stream=width,height,duration",
                        "-of", "csv", file
                    ]
                    result = subprocess.run(
                        cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
                    # ['stream', '1280', '720', '16536.905583\n']
                    # ['program', 'stream', '1280', '720', '16536.905583\n\nstream', '1280', '720', '16536.905583\n']
                    result = result.stdout.split(",")
                    width = int(result[-3])
                    height = int(result[-2])
                    duration_s = float(result[-1])
                    print(f"width={width} height={height}")
                    if width > height:
                        max_width = 1280
                        max_height = 720
                        if width > max_width and height > max_height:
                            new_width = max_width
                            new_height = int(height * max_width / width)
                            vf += f",scale={new_width}:{new_height}"
                    else:
                        max_height = 1280
                        if height > max_height:
                            new_width = int(width * max_height / height)
                            new_height = max_height
                            vf += f",scale={new_width}:{new_height}"
                except Exception as ex:
                    print(f"\033[93mffprobe: {ex} {result}\033[0m")
            if arg60Fps:
                # nlmeans, unsharp
                vf += ",mpdecimate=frac=0.25"
                vf += ",minterpolate='mi_mode=mci:mc_mode=aobmc:me_mode=bidir:fps=60'"
            if len(vf) > 0:
                vf = [ "-vf", vf.strip(",") ]
                if arg60Fps:
                    vf += [ "-r", "60" ]
            else:
                vf = []
            print(f"\033[93mAnalyzing video {file} to {ffmpeg2pass}-0.log...\033[0m")
            cmd = [ # first pass
                "ffmpeg",
                "-y", "-v", "quiet",
                "-stats",
                "-i", file,
                "-pass", "1", "-passlogfile", ffmpeg2pass,
                "-an", # no audio
                "-map_metadata", "-1", # skip metadata
                "-map_chapters", "-1", # skip chapters
                "-c:v", "libvpx-vp9", "-crf", "36", "-b:v", "0",
                "-f", "webm",
                "-row-mt", "1",
                "NUL" if os.name == "nt" else "/dev/null"
            ]
            subprocess.run(cmd, check=True)
            print(f"\033[93mConverting video {file} to {output_file}...\033[0m")
            cmd = [ # second pass
                "ffmpeg",
                "-y", "-v", "quiet",
                "-stats",
                "-i", file,
                "-pass", "2", "-passlogfile", ffmpeg2pass,
                *vf,
                "-c:a", "libopus",
                #"-c:v", "libaom-av1", "-cpu-used", "8", "-crf", "34", "-b:v", "0",
                #"-c:v", "librav1e", "-rav1e-params", "speed=10:tiles=2",
                #"-c:v", "libsvtav1", "-preset", "4", "-crf", "34",
                "-c:v", "libvpx-vp9", "-crf", "36", "-b:v", "0", "-g", "256",
                "-row-mt", "1", #"-threads", "32",
                "-map_metadata", "0",
                output_file
            ]
            subprocess.run(cmd, check=True)

        elif file_ext in animated_formats:
            output_file = output_dir + file_name + ".webp"
            cmd = [
                "gif2webp",
                file,
                "-mixed",
                "-min_size",
                "-o", output_file,
                "-v",
                "-mt"
            ]
            print(f"\033[93mConverting animated {file} to {output_file}...\033[0m")
            subprocess.run(cmd, check=True)

        else:
            output_file = output_dir + file_name + ".webp"
            resize_args = []
            try:
                if not argResize:
                    raise
                from PIL import Image
                with Image.open(file) as img:
                    width, height = img.size
                    # 2560x1440
                    # 1920x3413
                    if width > height:
                        max_width = 2560
                        max_height = 1440
                        if width > max_width and height > max_height:
                            new_width = max_width
                            new_height = int(height * max_width / width)
                            resize_args = ["-resize", str(new_width), str(new_height)]
                    else:
                        max_width = 1920
                        if width > max_width:
                            new_width = max_width
                            new_height = int(height * max_width / width)
                            resize_args = ["-resize", str(new_width), str(new_height)]
            except:
                pass
            cmd = [
                "cwebp",
                #NOTE: Use no-wic version on Windows!
                "-metadata", "all",
                "-q", "88",
                "-sharp_yuv",
                *resize_args,
                file,
                "-o", output_file,
                "-mt"
            ]

            print(f"\033[93mConverting image {file} to {output_file}...\033[0m")
            subprocess.run(cmd, check=True)

            output_size_b = os.path.getsize(output_file)
            if stat_info.st_size * 1.2 < output_size_b:
                print(f"\033[93mToo big ({int(output_size_b * 100 / stat_info.st_size)} %), lossless converting {file} to {output_file}.temp...\033[0m")
                cmd = [
                    "cwebp",
                    "-metadata", "all",
                    "-lossless",
                    *resize_args,
                    file,
                    "-o", output_file + ".temp",
                    "-mt"
                ]
                subprocess.run(cmd, check=True)
                output_temp_size_b = os.path.getsize(output_file + ".temp")
                if output_size_b < output_temp_size_b:
                    print(f"\033[93mLossing variant is smaller\033[0m")
                    os.remove(output_file + ".temp")
                else:
                    print(f"\033[93mLossless variant is smaller\033[0m")
                    os.remove(output_file)
                    os.rename(output_file + ".temp", output_file)

        os.utime(output_file, original_times)
    except Exception as ex:
        failed.append(file)
        print(f"\033[91m{file}: {ex}\033[0m")

for ext in ["-0.log", "-0.log.mbtree"]:
    try:
        os.remove(ffmpeg2pass + ext)
    except FileNotFoundError:
        pass

print("\033[92mConversion complete.\033[0m")
if len(failed) > 0:
    print(f"\033[91mFailed: {failed}\033[0m")

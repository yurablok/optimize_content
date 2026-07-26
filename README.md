# optimize_content

Optimize size of videos and images by converting to `webm` and `webp`, with optional resizing and simple 60 FPS frame interpolation.

## Dependencies

- `Python 3`. `Pillow` for image resizing
- `ffmpeg` + `ffprobe`
- `cwebp` + `gif2webp` (parts of libwebp, no-wic)

## Parameters

- `-h`: Print the help message.
- `-i <path>`: Specify input file(s) or directory(ies). Can be repeated.
  Directories are traversed recursively for supported files.
  If omitted, processes all supported files recursively in the current directory.
- `-o <path>`: Specify output directory. If omitted, uses `converted/`.
- `-l`: Only list matched found files.
- `-v`: Verbose mode. Show ffmpeg output during conversion.
- `-m`: Modification mode. Show each file before processing with tkinter GUI preview for crop/rotate/resize. Press Escape or close the window to proceed to the next file.
- `-r`: Enable resizing (videos and images). Uses predefined maximum dimensions depending on orientation:
  - Horizontal video: `1280 x 720`
  - Vertical video: `___ x 1280`
  - Horizontal image: `2560 x 1440`
  - Vertical image: `1920 x ___`
- `-rv`: Enable resizing for videos only (same dimensions as `-r`).
- `-60`: Enable 60 FPS conversion for videos and animated images using motion interpolation.
- `-m4v`, `-mkv`, `-mov`, `-mp4`, `-mpeg`, `-webm`, `-wmv`: Exclude unwanted video formats.
- `-h264`, `-hevc`, `-vp8`, `-vp9`, `-av1`, `-mpeg2video`, `-mpeg4`, `-vc1`, `-wmv3`, `-theora`, `-mjpeg`, `-prores`, `-dnxhd`, `-cineform`, `-dvvideo`: Exclude videos by codec.
- `-gif`: Exclude animated GIF format.
- `-avif`, `-bmp`, `-jpeg`, `-jpg`, `-png`, `-webp`: Exclude unwanted image formats.
- `+ex`: Copy excluded (by format or codec) files to output directory instead of skipping them.
- `+gif`, `+mp4`, etc.: Include ONLY files with this format (excludes all others).
- `+h264`, `+hevc`, etc.: Include ONLY videos with this codec.

## Comparison of video codecs

| Codec | HD bitrate | UHD bitrate | HDR                              | Hardware dec/enc |
| ----- | :--------: | :---------: | -------------------------------- | ---------------- |
| AVC   |      1     |      1      | Not standardized                 | Since 2004/2007  |
| HEVC  |  0.6~0.75  |   0.5~0.65  | HDR10, HDR10+, Dolby Vision, HLG | Since 2015/2016  |
| VP9   |  0.65~0.85 |  0.55~0.75  | Limited, PQ/HLG                  | Since 2016/Intel |
| AV1   |  0.55~0.75 |  0.45~0.65  | HDR10, HDR10+, Dolby Vision, HLG | Since 2020/2022  |
| VVC   |   0.4~0.6  |  0.35~0.5   | HDR10, HDR10+, Dolby Vision, HLG | Since 2024/2026+ |

VP9: Easy to achieve pixel-precision quality, but limited HDR support (`--enable-vp9-highbitdepth`), libvpx-vp9 is less optimized than libsvtav1.

AV1: To achieve pixel-precision quality, it is needed to disable ~4 of 7 filters/functions, and to tune ~3 parameters, that, in result, reduces its efficiency.

## Comparison of image formats

| Format    | Compression | HDR   | Lossy | Lossless | Animation | Support     |
| --------- | ----------- | ----- | ----- | -------- | --------- | ----------- |
| WebP      | `High`      | No    | `Yes` | `Yes`    | `Yes`     | `Wide`      |
| JPEG XL   | `Very High` | `Yes` | `Yes` | `Yes`    | `Yes`     | Limited     |
| JPEG      | Medium      | No    | `Yes` | No       | No        | `Universal` |
| AVIF      | `Very High` | `Yes` | `Yes` | `Yes`    | `Yes`     | Average     |
| HEIC/HEIF | `Very High` | `Yes` | `Yes` | `Yes`    | `Yes`     | Average     |
| PNG       | Low         | No    | No    | `Yes`    | No        | `Universal` |
| GIF       | Very Low    | No    | 8-bit | No       | `Yes`     | `Universal` |
| TIFF      | Low         | `Yes` | `Yes` | `Yes`    | No        | Limited     |
| OpenEXR   | Low         | `Yes` | `Yes` | `Yes`    | No        | Limited     |

## TODO

- JPEG XL
- HDR
```
ffmpeg -i input.avif -pix_fmt yuv420p10le -colorspace bt2020 -color_primaries bt2020 -color_trc smpte2084 output.webp

ffmpeg -i input.gif -c:v libjxl -effort 7 -distance 0 output.jxl
```

# sort_content

Interactive image/animation comparator for sorting content. Shows two files side by side, user picks one via click or arrow key. Sorting uses binary insertion with O(n log n) comparisons. Progress is saved for resume.

## Dependencies

- `Python 3`. `Pillow` for image processing
- `ffmpeg` + `ffprobe` for video/animation loading

## Parameters

- `-h`: Print the help message.
- `-i <path>`: Specify input file(s) or directory(ies). Can be repeated. Directories are traversed recursively for supported files. If omitted, processes all supported image/animation files recursively in the current directory.
- `-sl <path>`: Create symlinks of sorted results in the specified folder. Format: "1.filename.ext", "2.filename.ext", etc.
- `-o <filename>`: Save sorted file list (text, one path per line) to the given file. If not specified, the list is not saved.
- `-ch <filename>`: Choices cache file for resume sorting (default: sorting_choices.txt). Previous choices are recorded and loaded automatically.
- `-gv`: Open grid view of sorted results after completion. Shows all sorted images in a grid layout.
- `-gif`, `-jpg`, `-jpeg`, `-png`, `-bmp`, `-avif`, `-webp`: Exclude specific image/animation formats from processing.

## Features

- **Binary insertion sort**: O(n log n) comparisons for efficient sorting
- **Progress persistence**: Choices are saved to file, allowing resume after interruption
- **Side-by-side comparison**: GUI shows two files at a time for easy comparison
- **Keyboard controls**: Left/Right arrow keys to choose, Escape to quit
- **Grid view**: Post-sort visualization of all sorted files

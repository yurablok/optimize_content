# optimize_content
# Optimize size of videos and images by converting to webm and webp,
# with optional resizing and simple 60 FPS frame interpolation.
#
# Author: Yurii Blok
# License: Public Domain / Unlicense
# https://github.com/yurablok/optimize_content
# History:
# v0.4    2026-10-07    Added collage mode.
# v0.3    2026-07-26    Added codec-based filtering (-h264, -hevc, etc.) and include filters (+mp4, +h264).
#                       Added recursive directory traversal, verbose mode (-v), copy excluded (+ex).
#                       Added skip-if-already-converted logic, colored progress with file counters.
#                       Added animated→webm via ffmpeg when modifications or -60 are used.
#                       WIP: tkinter GUI preview for crop/rotate/resize before conversion (-m).
# v0.2    2025-12-14    Added arguments to ignore unwanted formats.
#                       Changed video codec from VP9 to AV1.
# v0.1    2025-09-12    First release.

import random
import os, sys
import subprocess
import shutil
import threading
import tkinter as tk
from PIL import Image, ImageTk, ImageOps
from math import gcd, sqrt, ceil

G, Y, C, R, W, D, E = "\033[32m", "\033[33m", "\033[36m", "\033[31m", "\033[97m", "\033[90m", "\033[0m"

# GUI theme colors
BG = "#1e1e1e"
PANEL = "#2a2a2a"
ENTRY = "#3c3c3c"
BTN = "#555555"
BTN_ACT = "#666666"
FG = "#ffffff"
FG_DIM = "#cccccc"
FG_DIMMER = "#888888"
ERR = "#ff4444"
BLUE = "#1f6feb"
BLUE_ACT = "#388bfd"
GREEN = "#238636"
GREEN_ACT = "#2ea043"

video_formats = { "mp4", "m4v", "mov", "mkv", "mpeg", "wmv", "webm", "ts" }
video_codecs = { "h264", "hevc", "vp8", "vp9", "av1", "mpeg2video", "mpeg4", "vc1", "wmv3", "theora", "mjpeg", "prores", "dnxhd", "cineform", "dvvideo" }
animated_formats = { "gif" }
image_formats = { "jpg", "jpeg", "png", "bmp", "avif", "webp" }
include_formats = set()
include_codecs = set()
excluded_formats = set()
all_formats = { *video_formats, *animated_formats, *image_formats }
all_codecs = { *video_codecs }

files = []
sources = []
argInput: bool = False
argOutput: bool = False
argOutputStr: str = ""
argResize: bool = False
argResizeVideo: bool = False
arg60Fps: bool = False
argListOnly: bool = False
argModification: bool = False
argVerbose: bool = False
argCopyExcluded: bool = False
argTestM: bool = False
argCollage: bool = False
argHelp = len(sys.argv) < 2

HELP_TEXT = f"""{G}Batch video and image format converter. {C}v0.4{E}
{W}Converts to webm and webp with optional resizing, 60 FPS interpolation,
codec/format filtering, and interactive preview before conversion.{E}
- `{Y}-h{E}`: Print the help message.
- `{Y}-i{E} {C}<path>{E}`: Specify input file(s) or directory(ies). Can be repeated.
        Directories are traversed recursively for supported files.
        If omitted, processes all supported files recursively in the
        current directory.
- `{Y}-o{E} {C}<path>{E}`: Specify output directory. If omitted, uses {D}converted/{E}.
- `{Y}-l{E}`: Only list matched found files.
- `{Y}-v{E}`: Verbose mode. Show ffmpeg output during conversion.
- `{Y}-m{E}`: Modification mode. Show each file before processing. Press Escape
        or close the window to proceed to the next file.
- `{Y}-r{E}`: Enable resizing (videos and images). Uses predefined maximum
        dimensions depending on orientation:
  - Horizontal video: {C}1280 x 720{E}
  - Vertical video: {C}___ x 1280{E}
  - Horizontal image: {C}2560 x 1440{E}
  - Vertical image: {C}1920 x ___{E}
- `{Y}-rv{E}`: Enable resizing for videos only (same dimensions as {Y}-r{E}).
- `{Y}-60{E}`: Enable 60 FPS conversion for videos and animated images using
        motion interpolation.
- `{Y}-co{E}`: Collage mode. Layout all input images in a 2D grid and tile them
        evenly across horizontal and vertical space (no resizing of sources),
        then save as webp. Falls back to proportional scaling when canvas
        exceeds 16383px in either dimension.
- `{Y}-m4v{E}`, `{Y}-mkv{E}`, `{Y}-mov{E}`, `{Y}-mp4{E}`, `{Y}-mpeg{E}`, `{Y}-webm{E}`, `{Y}-wmv{E}`: Exclude unwanted video format.
- `{Y}-h264{E}`, `{Y}-hevc{E}`, `{Y}-vp8{E}`, `{Y}-vp9{E}`, `{Y}-av1{E}`, `{Y}-mpeg2video{E}`, `{Y}-mpeg4{E}`,
  `{Y}-vc1{E}`, `{Y}-wmv3{E}`, `{Y}-theora{E}`, `{Y}-mjpeg{E}`, `{Y}-prores{E}`, `{Y}-dnxhd{E}`,
  `{Y}-cineform{E}`, `{Y}-dvvideo{E}`: Exclude videos by codec.
- `{Y}-gif{E}`: Exclude unwanted animated format.
- `{Y}-avif{E}`, `{Y}-bmp{E}`, `{Y}-jpeg{E}`, `{Y}-jpg{E}`, `{Y}-png{E}`, `{Y}-webp{E}`: Exclude unwanted image format.
- `{Y}+gif{E}`, `{Y}+mp4{E}`, etc.: Include ONLY files with this format (excludes all others).
- `{Y}+h264{E}`, `{Y}+hevc{E}`, etc.: Include ONLY videos with this codec.
- `{Y}+ex{E}`: Copy excluded (by format or codec) files to output instead of skipping."""

for arg in sys.argv[1:]:
    if argInput:
        files.append(arg)
        sources.append(arg if os.path.isdir(arg) else os.path.dirname(arg) or ".")
        argInput = False
    elif argOutput:
        if not arg.endswith('/'):
            print(f"{R}Output path must end with '/'{E}")
            exit(1)
        argOutputStr = arg
        argOutput = False
    elif arg == "-i":
        argInput = True
    elif arg == "-o":
        if len(argOutputStr) > 0:
            print(f"{R}There can be only one argument -o{E}")
            exit(1)
        argOutput = True
    elif arg == "-r":
        argResize = True
    elif arg == "-rv":
        argResizeVideo = True
    elif arg == "-60":
        arg60Fps = True
    elif arg == "-l":
        argListOnly = True
    elif arg == "-m":
        argModification = True
    elif arg == "-v":
        argVerbose = True
    elif arg == "+ex":
        argCopyExcluded = True
    elif arg.startswith("-") and arg[1:].lower() in video_formats:
        excluded_formats.add(arg[1:].lower())
        video_formats.remove(arg[1:].lower())
    elif arg.startswith("-") and arg[1:].lower() in animated_formats:
        excluded_formats.add(arg[1:].lower())
        animated_formats.remove(arg[1:].lower())
    elif arg.startswith("-") and arg[1:].lower() in image_formats:
        excluded_formats.add(arg[1:].lower())
        image_formats.remove(arg[1:].lower())
    elif arg.startswith("-") and arg[1:].lower() in video_codecs:
        video_codecs.remove(arg[1:].lower())
    elif arg.startswith("+") and len(arg) > 1:
        fmt = arg[1:].lower()
        if fmt in all_formats:
            include_formats.add(fmt)
        elif fmt in all_codecs:
            include_codecs.add(fmt)
        else:
            print(f"{R}Unknown format/codec for + filter: {arg}{E}")
            exit(1)
    elif arg == "--test-m":
        argTestM = True
    elif arg == "-co":
        argCollage = True
    elif arg == "-h":
        argHelp = True
    else:
        print(f"{R}Unknown argument: {arg}{E}")
        exit(1)
if argHelp:
    print(HELP_TEXT)
    exit(0)
if argOutput is True:
    print(f"{R}Argument -o requires a path{E}")
    exit(1)

supported_formats = { *video_formats, *animated_formats, *image_formats, *excluded_formats }

if include_formats:
    video_formats &= include_formats
    animated_formats &= include_formats
    image_formats &= include_formats
    supported_formats = { *video_formats, *animated_formats, *image_formats, *excluded_formats }

expanded = []
expanded_sources = []
for i, path in enumerate(files):
    if os.path.isdir(path):
        for root, dirs, filenames in os.walk(path):
            for f in filenames:
                if os.path.splitext(f)[1][1:].lower() in supported_formats:
                    expanded.append(os.path.join(root, f))
                    expanded_sources.append(sources[i])
    else:
        expanded.append(path)
        expanded_sources.append(sources[i])
files = expanded
sources = expanded_sources

output_dir = argOutputStr if len(argOutputStr) > 0 else "converted/"
if not output_dir.endswith("/"):
    output_dir += "/"
os.makedirs(output_dir, exist_ok=True)

if len(files) == 0:
    files = []
    sources = []
    for root, dirs, filenames in os.walk("."):
        for f in filenames:
            if os.path.splitext(f)[1][1:].lower() in supported_formats:
                files.append(os.path.join(root, f))
                sources.append(".")
failed = []

CORNER_WIDTH = 2


from dataclasses import dataclass
from typing import Optional, Tuple


@dataclass
class PreviewState:
    """Result of compute_preview_state — pure math, no side effects.

    Crop corners pass through 3 stages:
      Stage 1 (raw):      cl, ct, cr, cb — user-specified crop values
      Stage 2 (image):    crop_box — bounding box in original image pixel coordinates
                           (accounts for rotation, with corner_width padding)
      Stage 3 (preview):  crop_box_canvas — crop_box scaled by ratio, relative
                           to preview image top-left (image-local coords)

    Image dimension pipeline:
      crop_w/h  →  src_w/h  →  fit_w/h  →  img_w/h
      (crop)      (+resize)    (fit canvas) (+pct)

    Canvas position:
      img_cx, img_cy — center (= canvas center, image drawn here)
    """
    cl: int           # stage 1: raw crop left
    ct: int           # stage 1: raw crop top
    cr: int           # stage 1: raw crop right
    cb: int           # stage 1: raw crop bottom
    angle: int        # rotation angle (0, 90, 180, 270)
    crop_w: int       # width after crop+rotate (before resize)
    crop_h: int       # height after crop+rotate (before resize)
    src_w: int        # width after crop+rotate+resize (final source)
    src_h: int        # height after crop+rotate+resize (final source)
    ar_w: int         # aspect ratio numerator (src_w / gcd)
    ar_h: int         # aspect ratio denominator (src_h / gcd)
    fit_w: int        # width fitted to canvas (src * fit_ratio)
    fit_h: int        # height fitted to canvas (src * fit_ratio)
    img_w: int        # preview width on canvas (from crop_box_canvas or fit)
    img_h: int        # preview height on canvas (from crop_box_canvas or fit)
    ratio: float      # final scale ratio (preview / source)
    crop_box: Optional[Tuple[int, int, int, int]]              # stage 2: (x1, y1, x2, y2) in image space
    crop_box_canvas: Optional[Tuple[float, float, float, float]]  # stage 3: (x1, y1, x2, y2) relative to image
    img_cx: float     # preview image center X on canvas
    img_cy: float     # preview image center Y on canvas


@dataclass
class Crop:
    left: int
    top: int
    width: int
    height: int


@dataclass
class Rotate:
    angle: int


@dataclass
class Resize:
    width: int
    height: int


Modification = Crop | Rotate | Resize


def compute_preview_state(orig_w, orig_h, cl, ct, cr, cb, angle, rw, rh, avail_w, avail_h, pct, canvas_w, canvas_h, corner_width=CORNER_WIDTH) -> PreviewState:
    """Pure math: compute all preview state from image size and modification params."""
    # 1. Validate crop
    if cr <= cl or cb <= ct:
        cr, cb = orig_w, orig_h

    # 2. Compute dimensions after crop
    cw, ch = cr - cl, cb - ct
    if angle in (90, 270):
        crop_w, crop_h = ch, cw
    else:
        crop_w, crop_h = cw, ch

    # 3. Resize
    src_w, src_h = crop_w, crop_h
    if rw >= 1 and rh >= 1 and (rw != src_w or rh != src_h):
        src_w, src_h = rw, rh

    # 4. Preview scaling
    if avail_w < 1 or avail_h < 1:
        avail_w, avail_h = 1, 1
    fit_ratio = min(avail_w / src_w, avail_h / src_h)
    fit_w = max(int(src_w * fit_ratio), 1)
    fit_h = max(int(src_h * fit_ratio), 1)
    pct = max(1, pct)
    ratio = fit_ratio * pct / 100
    img_w = max(int(src_w * ratio), 1)
    img_h = max(int(src_h * ratio), 1)

    # 5. Stage 2: crop bounding box in rotated image local coordinates
    crop_box = None
    if cw > 0 and ch > 0:
        if angle == 90:
            # crop maps to (orig_h-cb, cl) → (orig_h-ct, cr) in rotated space
            bx, by, bw, bh = orig_h - cb, cl, cb - ct, cr - cl
        elif angle == 180:
            bx, by, bw, bh = orig_w - cr, orig_h - cb, cw, ch
        elif angle == 270:
            bx, by, bw, bh = ct, orig_w - cr, cb - ct, cr - cl
        else:
            bx, by, bw, bh = cl, ct, cw, ch
        hw = corner_width // 2
        crop_box = (bx - hw, by - hw, bx + bw + hw, by + bh + hw)

    # 6. Stage 3: crop box on canvas (relative to preview image top-left)
    crop_box_canvas = None
    if crop_box is not None:
        x1, y1, x2, y2 = crop_box
        # crop_box is in rotated-local coords; preview starts at crop origin (bx, by)
        crop_box_canvas = (
            (x1 - bx) * ratio, (y1 - by) * ratio,
            (x2 - bx) * ratio, (y2 - by) * ratio,
        )

    # 7. Image display on canvas — sized to crop_box_canvas, centered
    if crop_box_canvas is not None:
        img_w = max(int(crop_box_canvas[2] - crop_box_canvas[0]), 1)
        img_h = max(int(crop_box_canvas[3] - crop_box_canvas[1]), 1)
    else:
        img_w, img_h = fit_w, fit_h
    img_cx = canvas_w / 2
    img_cy = canvas_h / 2

    # 8. Aspect ratio
    g = gcd(src_w, src_h)
    ar_w, ar_h = src_w // g, src_h // g

    return PreviewState(
        cl=cl, ct=ct, cr=cr, cb=cb,
        angle=angle,
        crop_w=crop_w, crop_h=crop_h,
        src_w=src_w, src_h=src_h,
        ar_w=ar_w, ar_h=ar_h,
        fit_w=fit_w, fit_h=fit_h,
        img_w=img_w, img_h=img_h, ratio=ratio,
        crop_box=crop_box,
        crop_box_canvas=crop_box_canvas,
        img_cx=img_cx, img_cy=img_cy,
    )


def apply_preview_state(img, st: PreviewState):
    """Apply crop, rotate, resize to a PIL image using PreviewState."""
    if st.cl != 0 or st.ct != 0 or st.cr != img.width or st.cb != img.height:
        img = img.crop((st.cl, st.ct, st.cr, st.cb))
    if st.angle != 0:
        img = img.rotate(-st.angle, expand=True)
    if st.src_w != img.width or st.src_h != img.height:
        img = img.resize((st.src_w, st.src_h), Image.NEAREST)
    return img


def _make_section(parent, title, with_reset=False):
    """Create a section header with optional Reset button."""
    hdr = tk.Frame(parent, bg=PANEL)
    hdr.pack(fill=tk.X, padx=8, pady=(10, 2))
    tk.Label(hdr, text=title, bg=PANEL, fg=FG, font=("Segoe UI", 10, "bold")).pack(side=tk.LEFT)
    reset_btn = None
    if with_reset:
        reset_btn = tk.Button(hdr, text="Reset", bg=BTN, fg=FG, activebackground=BTN_ACT,
                              relief=tk.FLAT, cursor="hand2", state=tk.DISABLED)
        reset_btn.pack(side=tk.RIGHT)
    return hdr, reset_btn

def _make_entry(parent, label, var, width=5, padx=0):
    """Create a labeled Entry widget."""
    tk.Label(parent, text=label, bg=PANEL, fg=FG_DIM).pack(side=tk.LEFT)
    e = tk.Entry(parent, textvariable=var, width=width, bg=ENTRY, fg=FG, insertbackground=FG)
    e.pack(side=tk.LEFT, padx=padx)
    return e

def _bind_input(widgets, callback):
    """Bind KeyRelease/FocusOut/ButtonRelease-1/FocusIn to a list of widgets."""
    for w in widgets:
        for event in ("<KeyRelease>", "<FocusOut>", "<ButtonRelease-1>"):
            w.bind(event, callback)
        w.bind("<FocusIn>", lambda e: w.configure(fg=FG))

def preview_file(path, ext):
    root = tk.Tk()
    root.title(os.path.basename(path))
    root.configure(bg=BG)
    root.minsize(800, 500)
    root.state("zoomed")

    # Left: image preview
    left = tk.Frame(root, bg=BG)
    left.pack(side=tk.LEFT, expand=True, fill=tk.BOTH)
    canvas = tk.Canvas(left, bg=BG, highlightthickness=0)
    canvas.pack(expand=True, fill=tk.BOTH)

    # Right: controls
    right = tk.Frame(root, bg=PANEL, width=300)
    right.pack(side=tk.RIGHT, fill=tk.Y, padx=(2, 0))
    right.pack_propagate(False)

    ctrl_canvas = tk.Canvas(right, bg=PANEL, highlightthickness=0)
    scrollbar = tk.Scrollbar(right, command=ctrl_canvas.yview)
    ctrl = tk.Frame(ctrl_canvas, bg=PANEL)
    _ctrl_win = ctrl_canvas.create_window(0, 0, window=ctrl, anchor="nw")
    def _center_ctrl(ch):
        ctrl.update_idletasks()
        h = ctrl.winfo_height()
        y = max(0, (ch - h) // 2) if h > 0 and ch > h else 0
        ctrl_canvas.configure(scrollregion=(0, 0, ctrl.winfo_width(), max(ch, h + y)))
        ctrl_canvas.coords(_ctrl_win, 0, y)
    ctrl_canvas.bind("<Configure>", lambda e: _center_ctrl(e.height))
    ctrl_canvas.configure(yscrollcommand=scrollbar.set)
    scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
    ctrl_canvas.pack(side=tk.LEFT, expand=True, fill=tk.BOTH)

    def _bind_scroll(entry, step=1, min_val=0, callback=None):
        def _on_wheel(e):
            try:
                v = int(entry.get())
            except ValueError:
                v = 0
            v = v + step * (1 if e.delta > 0 else -1)
            if min_val is not None:
                v = max(min_val, v)
            entry.delete(0, tk.END)
            entry.insert(0, str(v))
            entry.configure(fg=FG)
            if callback:
                callback()
        entry.bind("<MouseWheel>", _on_wheel)

    # ── Preview size ──
    tk.Label(ctrl, text="Preview", bg=PANEL, fg=FG, font=("Segoe UI", 10, "bold")).pack(anchor="w", padx=8, pady=(10, 2))
    pf = tk.Frame(ctrl, bg=PANEL)
    pf.pack(fill=tk.X, padx=8)
    preview_pct = tk.StringVar(value="80")
    tk.Label(pf, text="Size:", bg=PANEL, fg=FG_DIM).pack(side=tk.LEFT)
    preview_entry = tk.Entry(pf, textvariable=preview_pct, width=4, bg=ENTRY, fg=FG, insertbackground=FG)
    preview_entry.pack(side=tk.LEFT, padx=(0, 2))
    tk.Label(pf, text="%", bg=PANEL, fg=FG_DIM).pack(side=tk.LEFT)
    preview_pct.trace_add("write", lambda *a: _schedule_preview())
    _bind_scroll(preview_entry, step=5, min_val=1)
    left.bind("<Configure>", lambda e: _schedule_preview())

    photo_ref = [None]
    is_video = ext in video_formats
    img_orig = [None]
    video_frames = [0]
    video_fps = [30.0]
    frame_cache = {}
    _video_dims = [0, 0]

    updating = [False]
    preview_scheduled = [False]
    def _schedule_preview():
        if not preview_scheduled[0]:
            preview_scheduled[0] = True
            root.after_idle(_run_preview)
    def _run_preview():
        preview_scheduled[0] = False
        if img_orig[0] is not None:
            _update_preview()
        else:
            canvas.delete("all")
            canvas.create_text(canvas.winfo_width() // 2, canvas.winfo_height() // 2,
                               text="Failed to load image", fill=ERR, font=("Segoe UI", 12))
    def _update_preview():
        if updating[0]:
            return
        if img_orig[0] is None:
            return
        updating[0] = True
        try:
            if is_video:
                frame_num = frame_num_var.get()
                cached = frame_cache.get(frame_num)
                img = cached.copy() if cached else img_orig[0].copy()
                if frame_lbl:
                    frame_lbl.configure(text=f"{frame_num}/{video_frames[0] - 1}")
            else:
                img = img_orig[0].copy()
            # Compute all preview state via shared pure function
            try:
                cl_ui = int(crop_l_var.get())
                ct_ui = int(crop_t_var.get())
                cr_ui = int(crop_r_var.get())
                cb_ui = int(crop_b_var.get())
            except ValueError:
                cl_ui, ct_ui, cr_ui, cb_ui = 0, 0, img.width, img.height
            try:
                rw_ui = int(resize_w.get())
                rh_ui = int(resize_h.get())
            except ValueError:
                rw_ui, rh_ui = img.width, img.height
            avail_w = left.winfo_width() - 20
            avail_h = left.winfo_height() - 20
            if avail_w < 10 or avail_h < 10:
                avail_w, avail_h = root.winfo_screenwidth() - 350, root.winfo_screenheight() - 100
            st = compute_preview_state(
                img_orig[0].width, img_orig[0].height,
                cl_ui, ct_ui, cr_ui, cb_ui,
                int(rotation.get()), rw_ui, rh_ui,
                avail_w, avail_h, max(1, int(preview_pct.get())),
                canvas.winfo_width(), canvas.winfo_height(),
            )
            # Apply crop + rotate + resize to PIL image
            img = apply_preview_state(img, st)
            # Auto-sync resize with crop if user didn't set it manually
            if not resize_user_set[0]:
                resize_w.delete(0, tk.END)
                resize_w.insert(0, str(st.crop_w))
                resize_h.delete(0, tk.END)
                resize_h.insert(0, str(st.crop_h))
            # Update UI fields
            resize_ar.configure(text=f"({st.ar_w}:{st.ar_h})")
            crop_l_var.set(str(st.cl))
            crop_t_var.set(str(st.ct))
            crop_r_var.set(str(st.cr))
            crop_b_var.set(str(st.cb))
            # Scale to preview size
            img = img.resize((st.img_w, st.img_h), Image.NEAREST)
            photo_ref[0] = ImageTk.PhotoImage(img)
            canvas.delete("all")
            canvas.create_image(st.img_cx, st.img_cy, image=photo_ref[0], anchor="center")
            # Draw crop on canvas (crop_box_canvas is in image-local coords)
            if st.crop_box_canvas:
                ox = st.img_cx - st.img_w / 2
                oy = st.img_cy - st.img_h / 2
                cx1, cy1, cx2, cy2 = st.crop_box_canvas
                dx, dy = cx1 + ox, cy1 + oy
                dw, dh = (cx2 - cx1), (cy2 - cy1)
                r = min(20, dw // 4, dh // 4)
                # Corners
                for cx, cy in [(dx, dy), (dx+dw, dy), (dx, dy+dh), (dx+dw, dy+dh)]:
                    sx = 1 if cx == dx else -1
                    sy = 1 if cy == dy else -1
                    canvas.create_line(cx, cy, cx + sx*r, cy, fill="red", width=CORNER_WIDTH)
                    canvas.create_line(cx, cy, cx, cy + sy*r, fill="red", width=CORNER_WIDTH)
                # Edge midpoints
                mr = r // 2
                mx, my = dx + dw / 2, dy + dh / 2
                canvas.create_line(mx - mr, dy, mx + mr, dy, fill="red", width=CORNER_WIDTH)
                canvas.create_line(mx - mr, dy + dh, mx + mr, dy + dh, fill="red", width=CORNER_WIDTH)
                canvas.create_line(dx, my - mr, dx, my + mr, fill="red", width=CORNER_WIDTH)
                canvas.create_line(dx + dw, my - mr, dx + dw, my + mr, fill="red", width=CORNER_WIDTH)
        except Exception as ex:
            canvas.delete("all")
            canvas.create_text(canvas.winfo_width() // 2, canvas.winfo_height() // 2,
                               text=str(ex), fill=ERR, font=("Segoe UI", 12))
        finally:
            updating[0] = False

    _applied = None
    _saved_crop = [0, 0, 0, 0]
    _saved_resize = [0, 0]
    _saved_rotate = [0]
    def _save_values():
        try:
            _saved_crop[0] = int(crop_l_var.get())
            _saved_crop[1] = int(crop_t_var.get())
            _saved_crop[2] = int(crop_r_var.get())
            _saved_crop[3] = int(crop_b_var.get())
        except ValueError:
            pass
        try:
            _saved_resize[0] = int(resize_w.get())
            _saved_resize[1] = int(resize_h.get())
        except ValueError:
            pass
        try:
            _saved_rotate[0] = int(rotation.get())
        except ValueError:
            pass
    def apply_and_close():
        nonlocal _applied
        _save_values()
        _applied = "apply"
        root.destroy()
    def convert_and_close():
        nonlocal _applied
        _applied = "convert"
        root.destroy()
    def skip_and_close():
        root.destroy()

    root.protocol("WM_DELETE_WINDOW", skip_and_close)
    root.bind("<Escape>", lambda e: skip_and_close())

    # ── Crop ──
    crop_dirty = [False]
    crop_user_set = [False]
    crop_set = [False]
    _, crop_reset = _make_section(ctrl, "Crop", with_reset=True)
    cf1 = tk.Frame(ctrl, bg=PANEL)
    cf1.pack(fill=tk.X, padx=8)
    crop_l_var = tk.StringVar(value="0")
    crop_t_var = tk.StringVar(value="0")
    crop_l = _make_entry(cf1, "L:", crop_l_var, padx=(0, 6))
    crop_t = _make_entry(cf1, "T:", crop_t_var)
    cf2 = tk.Frame(ctrl, bg=PANEL)
    cf2.pack(fill=tk.X, padx=8, pady=(4, 0))
    crop_r_var = tk.StringVar(value="0")
    crop_b_var = tk.StringVar(value="0")
    crop_r = _make_entry(cf2, "R:", crop_r_var, padx=(0, 6))
    crop_b = _make_entry(cf2, "B:", crop_b_var)
    def _on_crop_input(e=None):
        crop_dirty[0] = True
        crop_reset.configure(state=tk.NORMAL)
        _schedule_preview()
    def _on_crop_wh_input(widget):
        def handler(e=None):
            crop_user_set[0] = True
            _on_crop_input()
        widget.bind("<KeyRelease>", handler)
    def _reset_crop():
        crop_l_var.set("0")
        crop_t_var.set("0")
        crop_r_var.set(str(img_orig[0].width))
        crop_b_var.set(str(img_orig[0].height))
        crop_set[0] = True
        crop_user_set[0] = False
        crop_dirty[0] = False
        crop_reset.configure(state=tk.DISABLED)
        _schedule_preview()
    crop_reset.configure(command=_reset_crop)
    _bind_scroll(crop_l, min_val=None, callback=_on_crop_input)
    _bind_scroll(crop_t, min_val=None, callback=_on_crop_input)
    _bind_scroll(crop_r, callback=_on_crop_input)
    _bind_scroll(crop_b, callback=_on_crop_input)
    _bind_input([crop_l, crop_t, crop_r, crop_b], _on_crop_input)
    _on_crop_wh_input(crop_r)
    _on_crop_wh_input(crop_b)

    # ── Resize ──
    resize_dirty = [False]
    resize_user_set = [False]
    _, resize_reset = _make_section(ctrl, "Resize", with_reset=True)
    rf = tk.Frame(ctrl, bg=PANEL)
    rf.pack(fill=tk.X, padx=8)
    tk.Label(rf, text="W:", bg=PANEL, fg=FG_DIM).pack(side=tk.LEFT)
    resize_w = tk.Entry(rf, width=6, bg=ENTRY, fg=FG, insertbackground=FG)
    resize_w.pack(side=tk.LEFT, padx=(0, 8))
    tk.Label(rf, text="H:", bg=PANEL, fg=FG_DIM).pack(side=tk.LEFT)
    resize_h = tk.Entry(rf, width=6, bg=ENTRY, fg=FG, insertbackground=FG)
    resize_h.pack(side=tk.LEFT)
    resize_ar = tk.Label(rf, text="", bg=PANEL, fg=BTN_ACT, font=("Segoe UI", 9))
    resize_ar.pack(side=tk.LEFT, padx=(6, 0))
    def _on_resize_input(e=None):
        resize_user_set[0] = True
        resize_dirty[0] = True
        resize_reset.configure(state=tk.NORMAL)
        _schedule_preview()
    def _reset_resize():
        angle = int(rotation.get())
        w, h = (img_orig[0].height, img_orig[0].width) if angle in (90, 270) else (img_orig[0].width, img_orig[0].height)
        resize_w.delete(0, tk.END)
        resize_w.insert(0, str(w))
        resize_h.delete(0, tk.END)
        resize_h.insert(0, str(h))
        resize_dirty[0] = False
        resize_user_set[0] = False
        resize_reset.configure(state=tk.DISABLED)
        _schedule_preview()
    resize_reset.configure(command=_reset_resize)
    _bind_scroll(resize_w, callback=_on_resize_input)
    _bind_scroll(resize_h, callback=_on_resize_input)
    _bind_input([resize_w, resize_h], _on_resize_input)

    # ── Rotate ──
    rotate_dirty = [False]
    _, rotate_reset = _make_section(ctrl, "Rotate", with_reset=True)
    rf2 = tk.Frame(ctrl, bg=PANEL)
    rf2.pack(fill=tk.X, padx=8)
    rotation = tk.StringVar(value="0")
    prev_angle = [0]
    def _swap_resize():
        try:
            rw = int(resize_w.get())
            rh = int(resize_h.get())
        except ValueError:
            return
        resize_w.delete(0, tk.END)
        resize_w.insert(0, str(rh))
        resize_h.delete(0, tk.END)
        resize_h.insert(0, str(rw))
    def _on_rotate_input(*a):
        angle = int(rotation.get())
        was_ortho = prev_angle[0] in (90, 270)
        is_ortho = angle in (90, 270)
        if was_ortho != is_ortho:
            _swap_resize()
        prev_angle[0] = angle
        if angle != 0:
            rotate_dirty[0] = True
            rotate_reset.configure(state=tk.NORMAL)
        else:
            rotate_dirty[0] = False
            rotate_reset.configure(state=tk.DISABLED)
        _schedule_preview()
    def _reset_rotate():
        rotation.set("0")
        prev_angle[0] = 0
        rotate_dirty[0] = False
        rotate_reset.configure(state=tk.DISABLED)
        _schedule_preview()
    rotate_reset.configure(command=_reset_rotate)
    rotation.trace_add("write", _on_rotate_input)
    for val in ["0", "90", "180", "270"]:
        tk.Radiobutton(rf2, text=val + "°", variable=rotation, value=val, bg=PANEL, fg=FG_DIM, selectcolor=ENTRY, activebackground=PANEL).pack(side=tk.LEFT)

    # ── Frame selector (video only) ──
    frame_num_var = tk.IntVar(value=0)
    frame_slider = None
    frame_lbl = None
    def _on_frame_change(*a):
        if not is_video or img_orig[0] is None:
            return
        frame_num = frame_num_var.get()
        if frame_num in frame_cache:
            _schedule_preview()
            return
        canvas.delete("all")
        canvas.create_text(canvas.winfo_width() // 2, canvas.winfo_height() // 2,
                           text="Loading frame...", fill=FG_DIMMER, font=("Segoe UI", 12))
        root.update()
        def _load_video_frame():
            img = _extract_frame(frame_num)
            if img is not None:
                root.after(0, _schedule_preview)
        t = threading.Thread(target=_load_video_frame, daemon=True)
        t.start()
    if is_video:
        _make_section(ctrl, "Frame")
        frame_f = tk.Frame(ctrl, bg=PANEL)
        frame_f.pack(fill=tk.X, padx=8)
        frame_slider = tk.Scale(frame_f, from_=0, to=0, orient=tk.HORIZONTAL,
                                variable=frame_num_var, bg=PANEL, fg=FG_DIM,
                                troughcolor=ENTRY, highlightthickness=0,
                                sliderlength=15, showvalue=False,
                                command=lambda v: root.after(1, _on_frame_change))
        frame_slider.pack(side=tk.LEFT, expand=True, fill=tk.X)
        def _on_frame_wheel(e):
            if video_frames[0] <= 0:
                return
            step = 1 if e.delta > 0 else -1
            v = max(0, min(video_frames[0] - 1, frame_num_var.get() + step))
            frame_slider.set(v)
        frame_slider.bind("<MouseWheel>", _on_frame_wheel)

        frame_lbl = tk.Label(frame_f, text="0/0", bg=PANEL, fg=FG_DIMMER, width=10)
        frame_lbl.pack(side=tk.LEFT, padx=(4, 0))

    # ── Action buttons ──
    bf = tk.Frame(ctrl, bg=PANEL)
    bf.pack(fill=tk.X, padx=8, pady=(10, 8))
    tk.Button(bf, text="Skip", command=skip_and_close, bg=BTN, fg=FG, activebackground=BTN_ACT, relief=tk.FLAT, cursor="hand2").pack(side=tk.LEFT, expand=True, fill=tk.X, padx=(0, 4))
    tk.Button(bf, text="Convert", command=convert_and_close, bg=BLUE, fg=FG, activebackground=BLUE_ACT, relief=tk.FLAT, cursor="hand2").pack(side=tk.LEFT, expand=True, fill=tk.X, padx=(0, 4))
    tk.Button(bf, text="Modify", command=apply_and_close, bg=GREEN, fg=FG, activebackground=GREEN_ACT, relief=tk.FLAT, cursor="hand2").pack(side=tk.LEFT, expand=True, fill=tk.X)

    # ── State for video frame extraction ──
    def _get_video_dimensions():
        if _video_dims[0] == 0:
            try:
                r = subprocess.run(
                    ["ffprobe", "-v", "error", "-select_streams", "v:0",
                     "-show_entries", "stream=width,height",
                     "-of", "csv=p=0", path],
                    stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=5)
                parts = r.stdout.strip().split(",")
                _video_dims[0], _video_dims[1] = int(parts[0]), int(parts[1])
            except Exception:
                _video_dims[0], _video_dims[1] = 640, 480
        return _video_dims[0], _video_dims[1]

    def _extract_frame(frame_num):
        if frame_num in frame_cache:
            return frame_cache[frame_num]
        try:
            timestamp = frame_num / video_fps[0]
            r = subprocess.run(
                ["ffmpeg", "-v", "error", "-ss", str(timestamp), "-i", path,
                 "-vframes", "1", "-f", "rawvideo", "-pix_fmt", "rgb24", "-"],
                stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=10)
            if r.returncode == 0 and len(r.stdout) > 0:
                w, h = _get_video_dimensions()
                img = Image.frombytes("RGB", (w, h), r.stdout[:w * h * 3])
                frame_cache[frame_num] = img
                return img
        except Exception:
            pass
        return None

    # ── Load image ──
    try:
        if is_video:
            r = subprocess.run(
                ["ffprobe", "-v", "error", "-select_streams", "v:0",
                 "-show_entries", "stream=width,height,r_frame_rate",
                 "-of", "csv=p=0", path],
                stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=5)
            parts = r.stdout.strip().split(",")
            w, h = int(parts[0]), int(parts[1])
            _video_dims[0], _video_dims[1] = w, h
            if len(parts) >= 3:
                fps_str = parts[2]
                if "/" in fps_str:
                    sp = fps_str.split("/")
                    if len(sp) == 2 and sp[0].isdigit() and sp[1].isdigit():
                        video_fps[0] = float(sp[0]) / float(sp[1]) if float(sp[1]) > 0 else 30.0
            # Get frame count: nb_frames first, else duration*fps
            r2 = subprocess.run(
                ["ffprobe", "-v", "error", "-select_streams", "v:0",
                 "-show_entries", "stream=nb_frames",
                 "-of", "csv=p=0", path],
                stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=5)
            nb = r2.stdout.strip()
            if nb.isdigit():
                video_frames[0] = int(nb)
            else:
                try:
                    r3 = subprocess.run(
                        ["ffprobe", "-v", "error",
                         "-show_entries", "format=duration",
                         "-of", "csv=p=0", path],
                        stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=5)
                    dur = float(r3.stdout.strip())
                    if dur > 0:
                        video_frames[0] = max(1, int(dur * video_fps[0]))
                except (ValueError, subprocess.TimeoutExpired):
                    video_frames[0] = 0
            if video_frames[0] > 0 and frame_slider:
                frame_slider.configure(to=video_frames[0] - 1)
                frame_num_var.set(0)
            if frame_lbl:
                frame_lbl.configure(text=f"0/{video_frames[0] - 1}")
            img_orig[0] = _extract_frame(0)
            if img_orig[0] is None:
                r = subprocess.run(
                    ["ffmpeg", "-v", "error", "-i", path,
                     "-vframes", "1", "-f", "rawvideo", "-pix_fmt", "rgb24", "-"],
                    stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=5)
                img_orig[0] = Image.frombytes("RGB", (w, h), r.stdout)
        else:
            with Image.open(path) as im:
                img_orig[0] = ImageOps.exif_transpose(im).copy()
        # Initialize resize fields with original dimensions
        resize_w.delete(0, tk.END)
        resize_w.insert(0, str(img_orig[0].width))
        resize_h.delete(0, tk.END)
        resize_h.insert(0, str(img_orig[0].height))
        _update_preview()
    except Exception as ex:
        canvas.delete("all")
        canvas.create_text(canvas.winfo_width() // 2, canvas.winfo_height() // 2,
                           text=str(ex), fill=ERR, font=("Segoe UI", 12))

    root.mainloop()

    if _applied is None:
        return None

    if _applied == "convert":
        return []

    # Collect only modified parameters
    modifications = []
    if crop_dirty[0]:
        cl, ct, cr, cb = _saved_crop
        if cr > cl and cb > ct:
            modifications.append(Crop(left=cl, top=ct, width=cr - cl, height=cb - ct))
    if resize_dirty[0]:
        rw, rh = _saved_resize
        if rw >= 1 and rh >= 1:
            modifications.append(Resize(width=rw, height=rh))
    if rotate_dirty[0]:
        angle = _saved_rotate[0]
        if angle != 0:
            modifications.append(Rotate(angle=angle))

    return modifications

def build_modification_filters(modifications: list[Modification]):
    filters = []
    has_geometry_change = False
    for m in modifications:
        if isinstance(m, Crop):
            filters.append(f"crop={m.width}:{m.height}:{m.left}:{m.top}")
            has_geometry_change = True
        elif isinstance(m, Rotate):
            if m.angle == 90:
                filters.append("transpose=1")
            elif m.angle == 180:
                filters.append("transpose=1,transpose=1")
            elif m.angle == 270:
                filters.append("transpose=2")
        elif isinstance(m, Resize):
            filters.append(f"scale={m.width}:{m.height}")
            has_geometry_change = True
    #if has_geometry_change and w > 0 and h > 0:
    #    filters.append(f"setdar={m.width}/{m.height}")
    return filters

def apply_image_modifications(path, modifications: list[Modification]):
    src = Image.open(path)
    try:
        img = src.copy()
    finally:
        src.close()
    for m in modifications:
        if isinstance(m, Crop):
            img = img.crop((m.left, m.top, m.left + m.width, m.top + m.height))
    for m in modifications:
        if isinstance(m, Rotate):
            img = img.rotate(-m.angle, expand=True)
    for m in modifications:
        if isinstance(m, Resize):
            img = img.resize((m.width, m.height), Image.NEAREST)
    img.save(path)
    img.close()

if argTestM:
    import unittest

    def _s(ow: int, oh: int, cl: int, ct: int, cr: int, cb: int, a: int = 0,
            rw: int = None, rh: int = None, aw: int = 1920, ah: int = 1080, p: int = 100,
            cw_canvas: int = None, ch_canvas: int = None):
        """Shorthand for compute_preview_state with sensible defaults."""
        cw, ch = cr - cl, cb - ct
        if a in (90, 270):
            cw, ch = ch, cw
        if rw is None:
            rw = cw
        if rh is None:
            rh = ch
        if cw_canvas is None:
            cw_canvas = aw
        if ch_canvas is None:
            ch_canvas = ah
        return compute_preview_state(ow, oh, cl, ct, cr, cb, a, rw, rh, aw, ah, p, cw_canvas, ch_canvas)

    class TestComputeCropClamp(unittest.TestCase):
        def test_no_crop(self):
            st = _s(8, 4, 0, 0, 8, 4)
            self.assertEqual((st.cl, st.ct, st.cr, st.cb), (0, 0, 8, 4))
            self.assertEqual((st.src_w, st.src_h), (8, 4))
            self.assertEqual(st.crop_box, (-1, -1, 9, 5))

        def test_crop_left_inc(self):
            st = _s(8, 4, 1, 0, 8, 4)
            self.assertEqual((st.cl, st.ct, st.cr, st.cb), (1, 0, 8, 4))
            self.assertEqual((st.src_w, st.src_h), (7, 4))
            self.assertEqual(st.crop_box, (0, -1, 9, 5))

        def test_crop_box_with_90_rotation(self):
            st = _s(1000, 800, 100, 50, 500, 400, a=90)
            # Rotated crop area: (orig_h-cb, cl, orig_h-ct, cr) = (400, 100, 750, 500)
            # With hw=1: (399, 99, 751, 501)
            self.assertEqual(st.crop_box, (399, 99, 751, 501))
            # crop_box_canvas should map crop origin to (0,0)
            cx1, cy1, cx2, cy2 = st.crop_box_canvas
            self.assertAlmostEqual(cx1, -1 * st.ratio, delta=1)
            self.assertAlmostEqual(cy1, -1 * st.ratio, delta=1)

        def test_crop_box_with_180_rotation(self):
            st = _s(1000, 800, 100, 50, 500, 400, a=180)
            # 180°: (orig_w-cr, orig_h-cb, orig_w-cl, orig_h-ct) = (500, 400, 900, 750)
            # With hw=1: (499, 399, 901, 751)
            self.assertEqual(st.crop_box, (499, 399, 901, 751))

        def test_crop_box_with_270_rotation(self):
            st = _s(1000, 800, 100, 50, 500, 400, a=270)
            # 270°: (ct, orig_w-cr, cb, orig_w-cl) = (50, 500, 400, 900)
            # With hw=1: (49, 499, 401, 901)
            self.assertEqual(st.crop_box, (49, 499, 401, 901))

    print(f"{G}Running Crop/Resize unit tests...{E}")
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    for cls in [TestComputeCropClamp]:
        suite.addTests(loader.loadTestsFromTestCase(cls))
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    if result.wasSuccessful():
        print(f"{G}All tests passed.{E}")
    else:
        print(f"{R}Some tests failed.{E}")
    exit(0 if result.wasSuccessful() else 1)

if argCollage:
    img_files = []
    for f in files:
        ext = os.path.splitext(f)[1][1:].lower()
        if ext in image_formats:
            img_files.append(f)
    # Remove any existing collage.webp to avoid recursive references
    img_files = [f for f in img_files if not str(os.path.basename(f)).startswith("collage")]
    if img_files:
        images = []
        for f in img_files:
            with Image.open(f) as im:
                im = ImageOps.exif_transpose(im).copy()
                if im.mode != "RGB":
                    im = im.convert("RGB")
                images.append(im)
            print(f"{Y}Loaded {f}: {im.width}x{im.height}{E}")
        n = len(images)
        print(f"{Y}Total images: {n}{E}")
        # Randomized square packing — infinite search, Ctrl+C saves best.
        print(f"{Y}Using randomized layout (Ctrl+C to stop, saves best so far){E}")
        indexed = list(enumerate(images))
        indexed.sort(key=lambda ix: ix[1].width * ix[1].height, reverse=True)
        imgs = [im for _, im in indexed]

        total_area = sum(im.width * im.height for im in imgs)
        canvas_area = int(total_area * 1.21)
        side = int(ceil(sqrt(canvas_area)))
        canvas_w = side
        canvas_h = side
        print(f"{Y}Canvas: {canvas_w}x{canvas_h}, total_area={total_area}, canvas_area={canvas_area}{E}")

        random.seed()
        best_n = 0
        best_layout = []
        best_fill = 0
        attempt = 0

        try:
            while True:
                layout = []
                occupied = []
                placed = 0
                for im in imgs:
                    w, h = im.width, im.height
                    pos = None
                    for trial in range(1000):
                        px = random.randint(0, max(0, canvas_w - w))
                        py = random.randint(0, max(0, canvas_h - h))
                        ok = True
                        for ox, oy, ow, oh in occupied:
                            if not (px + w <= ox or px >= ox + ow or py + h <= oy or py >= oy + oh):
                                ok = False
                                break
                        if ok:
                            pos = (px, py)
                            break
                    if pos:
                        layout.append((im, pos[0], pos[1]))
                        occupied.append((pos[0], pos[1], w, h))
                        placed += 1
                    else:
                        break

                attempt += 1
                occ = sum(w * h for _, _, w, h in occupied)
                if occupied:
                    bx, by = min(p[0] for p in occupied), min(p[1] for p in occupied)
                    bxe, bye = max(p[0]+p[2] for p in occupied), max(p[1]+p[3] for p in occupied)
                    bfill = int(occ * 100 // max(1, (bxe-bx)*(bye-by)))
                else:
                    bfill = 0

                if placed > best_n or (placed == best_n and bfill > best_fill):
                    best_n = placed
                    best_fill = bfill
                    best_layout = layout[:]
                    print(f"{Y}Attempt {attempt}: {placed}/{n}, fill={bfill}%{E}")
                    if placed == n:
                        print(f"{G}ALL {n} images placed — stopping{E}")
                        break

                if attempt % 100 == 0:
                    print(f"{Y}[{attempt}] Best: {best_n}/{n}, fill={best_fill}%{E}")

        except (KeyboardInterrupt, EOFError):
            if best_n > 0:
                print(f"{G}\nStopped after {attempt} attempts. Best: {best_n}/{n} placed, fill={best_fill}%{E}")
            else:
                print(f"{R}\nNo placement succeeded after {attempt} attempts.{E}")

        # Build collage
        collage = Image.new("RGB", (canvas_w, canvas_h), (0, 0, 0))
        for im, cx, cy in best_layout:
            collage.paste(im, (cx, cy))
        if collage.width > 16383 or collage.height > 16383:
            ratio = min(16383 / collage.width, 16383 / collage.height)
            new_w = max(int(collage.width * ratio), 1)
            new_h = max(int(collage.height * ratio), 1)
            print(f"{Y}Collage rescaled: {collage.width}x{collage.height} -> {new_w}x{new_h}{E}")
            collage = collage.resize((new_w, new_h), Image.Resampling.BICUBIC)
        output_file = output_dir + "collage.webp"
        if os.path.exists(output_file) and os.path.getsize(output_file) > 0:
            print(f"{Y}Skipped collage (already exists: {output_file}){E}")
        else:
            if os.path.dirname(output_file):
                os.makedirs(os.path.dirname(output_file), exist_ok=True)
            collage.save(output_file, format="WEBP", quality=88, method=6)
            collage.close()
            print(f"{Y}Created collage: {output_file}{E}")
    else:
        print(f"{Y}No image files for collage{E}")
    exit(0)

ffmpeg2pass = "ffmpeg2pass-" + str(random.randint(100000000, 999999999))
total = len(files)

for i, file in enumerate(files):
    if argListOnly:
        print(file)
        continue
    result = []
    if argModification:
        result = preview_file(file, os.path.splitext(file)[1][1:].lower())
        if result is None:
            print(f"{Y}[{i+1}/{total}] Skipped {file}{E}")
            continue

    source = sources[i]
    rel_path = os.path.relpath(file, source) if source else os.path.relpath(file)
    file_name, file_ext = os.path.splitext(rel_path)
    file_ext = file_ext[1:].lower()

    try:
        stat_info = os.stat(file)
        original_times = (stat_info.st_atime, stat_info.st_mtime)

        if file_ext in excluded_formats:
            if argCopyExcluded:
                output_file = output_dir + file_name + "." + file_ext
                if os.path.exists(output_file) and os.path.getsize(output_file) > 0:
                    print(f"{Y}[{i+1}/{total}] Skipped {file} (already exists: {output_file}){E}")
                    continue
                if os.path.dirname(output_file):
                    os.makedirs(os.path.dirname(output_file), exist_ok=True)
                shutil.copy2(file, output_file)
                print(f"{Y}[{i+1}/{total}] Copied {file} to {output_file} (excluded format: {file_ext}){E}")
            else:
                print(f"{Y}[{i+1}/{total}] Skipped {file} (excluded format: {file_ext}){E}")
            continue

        if file_ext in video_formats:
            try:
                cmd = [
                    "ffprobe", "-v", "error",
                    "-select_streams", "v:0",
                    "-show_entries", "stream=codec_name",
                    "-of", "csv=p=0", file
                ]
                proc = subprocess.run(
                    cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
                codec = proc.stdout.strip().split()[0].strip(",.").lower()
                if include_codecs and codec not in include_codecs:
                    print(f"{Y}[{i+1}/{total}] Skipped {file} (codec {codec} not in +{include_codecs}){E}")
                    continue
                if codec not in video_codecs:
                    if codec in all_codecs:
                        if argCopyExcluded:
                            output_file = output_dir + file_name + "." + file_ext
                            if os.path.exists(output_file) and os.path.getsize(output_file) > 0:
                                print(f"{Y}[{i+1}/{total}] Skipped {file} (already exists: {output_file}){E}")
                                continue
                            if os.path.dirname(output_file):
                                os.makedirs(os.path.dirname(output_file), exist_ok=True)
                            shutil.copy2(file, output_file)
                            print(f"{Y}[{i+1}/{total}] Copied {file} to {output_file} (excluded codec: {codec}){E}")
                        else:
                            print(f"{Y}[{i+1}/{total}] Skipped {file} (excluded codec: {codec}){E}")
                    else:
                        failed.append(file)
                        print(f"{R}[{i+1}/{total}] Failed {file}: unknown codec: {codec}{E}")
                    continue
            except Exception as ex:
                failed.append(file)
                print(f"{R}[{i+1}/{total}] Failed {file}: ffprobe {ex}{E}")
                continue
            output_file = output_dir + file_name + ".webm" # ".mkv"
            if os.path.exists(output_file) and os.path.getsize(output_file) > 0:
                print(f"{Y}[{i+1}/{total}] Skipped {file} (already exists: {output_file}){E}")
                continue
            if os.path.dirname(output_file):
                os.makedirs(os.path.dirname(output_file), exist_ok=True)
            vf = ""
            if result:
                mod_filters = build_modification_filters(result)
                if mod_filters:
                    vf += "," + ",".join(mod_filters)
            if argResize or argResizeVideo:
                try:
                    cmd = [
                        "ffprobe", "-v", "error",
                        "-select_streams", "v:0",
                        "-show_entries", "stream=width,height,duration",
                        "-of", "csv", file
                    ]
                    proc = subprocess.run(
                        cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
                    # ['stream', '1280', '720', '16536.905583\n']
                    # ['stream', '1920', '1080', 'N/A\n']
                    # ['program', 'stream', '1280', '720', '16536.905583\n\nstream', '1280', '720', '16536.905583\n']
                    result = proc.stdout.split(",")
                    width = int(result[-3])
                    height = int(result[-2])
                    #duration_s = float(result[-1])
                    print(f"{W}[{i+1}/{total}] width={width} height={height}{E}")
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
                    print(f"{Y}[{i+1}/{total}] ffprobe: {ex} {result}{E}")
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
            #print(f"\033[93mAnalyzing video {file} to {ffmpeg2pass}-0.log...\033[0m")
            #cmd = [ # first pass
            #    "ffmpeg",
            #    "-y", #"-v", "quiet",
            #    "-stats",
            #    "-i", file,
            #    #"-x265-params", "pass=1",
            #    "-pass", "1", "-passlogfile", ffmpeg2pass,
            #    "-an", # no audio
            #    "-map_metadata", "-1", # skip metadata
            #    "-map_chapters", "-1", # skip chapters
            #    #"-c:v", "libsvtav1", "-preset", "4", "-crf", "34",
            #    #"-c:v", "libx265", #"-crf", "28",
            #    "-c:v", "libvpx-vp9", "-crf", "36", "-b:v", "0",
            #    "-f", "null",
            #    #"-f", "webm",
            #    #"-row-mt", "1",
            #    "NUL" if os.name == "nt" else "/dev/null"
            #]
            #subprocess.run(cmd, check=True)
            print(f"{Y}[{i+1}/{total}] Converting video {file} to {output_file}...{E}")
            cmd = [ # second pass
                "ffmpeg",
                "-y",
                *(["-v", "quiet"] if not argVerbose else []),
                "-stats",
                "-i", file,
                #"-x265-params", "pass=2",
                #"-pass", "2", "-passlogfile", ffmpeg2pass,
                *vf,
                "-c:a", "libopus",
                #"-c:v", "libaom-av1", "-cpu-used", "8", "-crf", "34", "-b:v", "0",
                #"-c:v", "librav1e", "-rav1e-params", "speed=10:tiles=2",
                #"-pix_fmt", "yuv420p10le",
                #"-c:v", "libsvtav1", "-preset", "4", "-crf", "35", "-svtav1-params",
                #    "tune=1" # Visual quality tuning, modes: 0=VQ|VMAF, 1=PSNR, 2=SSIM
                #    ":tile-columns=0" # Auto tile columns
                #    ":tile-rows=0" # Auto tile rows
                #    #":keyint=2s" # 30s
                #    #":lookahead=120"
                #    #":aq-mode=2" # Variance‑based adaptive quantization
                #    ":film-grain=0" # Disable film grain synthesis
                #    #":film-grain-denoise=0"
                #    ":enable-qm=0" # Quantization Matrices. Can improve texture retention
                #    ":qm-min=0:qm-max=0" # Forces a specific QM strength, 0=off, 15=max
                #    #":lambda-scale-factors=512,512" # Aggressive; biases rate‑distortion decisions
                #    ":enable-dlf=1" # Deblocking Loop Filter
                #    ":enable-tpl-la=1" # Temporal Dependency Modeling + Lookahead
                #    ":enable-cdef=0" # Constrained Directional Enhancement Filter
                #    ":enable-restoration=0" # Loop Restoration Filter
                #    ":enable-tf=1" # Temporal Filter
                #    ":irefresh-type=2" # 0 - Closed GOP, 1 - Open GOP, 2 - Rolling intra refresh
                #    ":scd=1" # Enable scene‑cut detection
                #    ":scm=2" # More aggressive scene‑cut logic
                #    ,
                # "-profile:v", "2",
                # "-pix_fmt", "yuv420p10le",
                "-c:v", "libvpx-vp9", "-crf", "38", "-b:v", "0", # "-g", "128",
                #"-c:v", "libvvenc", "-crf", "28", "-preset", "medium",
                #"-c:v", "libx265", "-crf", "22", "-tag:v", "hvc1", # 28
                "-row-mt", "1", #"-threads", "32",
                "-map_metadata", "0",
                output_file
            ]
            subprocess.run(cmd, check=True)

        elif file_ext in animated_formats:
            output_webm = output_dir + file_name + ".webm"
            output_webp = output_dir + file_name + ".webp"
            if (os.path.exists(output_webm) and os.path.getsize(output_webm) > 0) or \
               (os.path.exists(output_webp) and os.path.getsize(output_webp) > 0):
                existing = output_webm if os.path.exists(output_webm) and os.path.getsize(output_webm) > 0 else output_webp
                print(f"{Y}[{i+1}/{total}] Skipped {file} (already exists: {existing}){E}")
                continue
            use_ffmpeg = bool(result) or arg60Fps
            if use_ffmpeg:
                output_file = output_webm
                if os.path.dirname(output_file):
                    os.makedirs(os.path.dirname(output_file), exist_ok=True)
                vf_parts = []
                if result:
                    mod_filters = build_modification_filters(result)
                    if mod_filters:
                        vf_parts.extend(mod_filters)
                if arg60Fps:
                    vf_parts.append("minterpolate='mi_mode=mci:mc_mode=aobmc:me_mode=bidir:fps=60'")
                cmd = [
                    "ffmpeg", "-y", "-stats",
                    *(["-v", "quiet"] if not argVerbose else []),
                    "-i", file,
                ]
                if vf_parts:
                    cmd += ["-vf", ",".join(vf_parts)]
                if arg60Fps:
                    cmd += ["-r", "60"]
                cmd += [
                    "-pix_fmt", "yuv420p",
                    "-c:v", "libvpx-vp9", "-crf", "38", "-b:v", "0",
                    "-row-mt", "1",
                    output_file,
                ]
                print(f"{Y}[{i+1}/{total}] Converting animated {file} to {output_file} (video)...{E}")
            else:
                output_file = output_webp
                if os.path.dirname(output_file):
                    os.makedirs(os.path.dirname(output_file), exist_ok=True)
                cmd = [
                    "gif2webp",
                    file,
                    "-mixed",
                    "-min_size",
                    "-o", output_file,
                    "-v",
                    "-mt"
                ]
                print(f"{Y}[{i+1}/{total}] Converting animated {file} to {output_file}...{E}")
            subprocess.run(cmd, check=True)

        else:
            if result:
                apply_image_modifications(file, result)
            output_file = output_dir + file_name + ".webp"
            if os.path.exists(output_file) and os.path.getsize(output_file) > 0:
                print(f"{Y}[{i+1}/{total}] Skipped {file} (already exists: {output_file}){E}")
                continue
            if os.path.dirname(output_file):
                os.makedirs(os.path.dirname(output_file), exist_ok=True)
            resize_args = []
            if argResize:
                try:
                    with Image.open(file) as img:
                        width, height = img.size
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
                except Exception:
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
                #"ffmpeg",
                #"-y", #"-v", "quiet",
                #"-stats",
                #"-i", file,
                ##"-vf", "scale=200:100",
                #"-c:v", "libwebp",
                #"-quality", "88",
                ##"-map_metadata", "0",
                ##"-metadata:s:v", "copy",
                #output_file,
            ]

            print(f"{Y}[{i+1}/{total}] Converting image {file} to {output_file}...{E}")
            subprocess.run(cmd, check=True)

            output_size_b = os.path.getsize(output_file)
            if stat_info.st_size * 1.2 < output_size_b:
                print(f"{Y}[{i+1}/{total}] Too big ({int(output_size_b * 100 / stat_info.st_size)} %), lossless converting {file} to {output_file}.temp...{E}")
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
                    print(f"{Y}[{i+1}/{total}] Lossing variant is smaller{E}")
                    os.remove(output_file + ".temp")
                else:
                    print(f"{Y}[{i+1}/{total}] Lossless variant is smaller{E}")
                    os.remove(output_file)
                    os.rename(output_file + ".temp", output_file)

        os.utime(output_file, original_times)
    except Exception as ex:
        failed.append(file)
        print(f"{R}[{i+1}/{total}] {file}: {ex}{E}")

#for ext in ["-0.log", "-0.log.mbtree"]:
#    try:
#        print("try to remove: " + ffmpeg2pass + ext)
#        os.remove(ffmpeg2pass + ext)
#        print("removed: " + ffmpeg2pass + ext)
#    except FileNotFoundError:
#        pass

print(f"{G}Conversion complete.{E}")
if len(failed) > 0:
    print(f"{R}Failed: {failed}{E}")

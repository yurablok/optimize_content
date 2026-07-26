# sort_content
# Interactive image/animation comparator for sorting content.
# Binary insertion sort with O(n log n) comparisons.
# Progress saved to txt files for resume.
#
# Author: Yurii Blok
# License: Public Domain / Unlicense
# https://github.com/yurablok/optimize_content
# History:
# v0.1    2026-07-26    First release. Interactive side-by-side image/animation comparator.
#                       Binary insertion sort, choices cache for resume, symlink output,
#                       grid view, animation playback, recursive directory traversal.

import os, sys, threading
from dataclasses import dataclass, field
import tkinter as tk
from PIL import Image, ImageTk, ImageOps

G, Y, C, R, W, D, E = "\033[32m", "\033[33m", "\033[36m", "\033[31m", "\033[97m", "\033[90m", "\033[0m"

# GUI theme colors
BG = "#1e1e1e"
FG_DIM = "#666666"
FG_LOAD = "#888888"
FG_TEXT = "#cccccc"

def _resize_image(pil_img, max_w, max_h):
    """Resize a PIL image to fit within max_w x max_h, return PhotoImage."""
    w, h = pil_img.size
    ratio = min(max_w / w, max_h / h)
    return ImageTk.PhotoImage(pil_img.resize((max(int(w * ratio), 1), max(int(h * ratio), 1)), Image.NEAREST))

@dataclass
class AnimData:
    kind: str = "anim"
    frames: list = field(default_factory=list)
    delays: list = field(default_factory=list)
    total: int = 0
    cur: int = 0
    orig: list = field(default_factory=list)
    size_version: int = 0

animated_formats = { "gif" }
image_formats = { "jpg", "jpeg", "png", "bmp", "avif", "webp" }
MAX_LOAD_THREADS = 20

files = []
sources = []

argInput: bool = False

argSymlink: bool = False
strSymlink: str = ""

argGridView: bool = False

argOutput: bool = False
strOutput: str = ""

argChoices: bool = False
strChoices: str = ""
defChoices = "sorting_choices.txt"

for arg in sys.argv[1:]:
    if argInput:
        files.append(arg)
        sources.append(arg if os.path.isdir(arg) else os.path.dirname(arg) or ".")
        argInput = False
    elif argSymlink:
        strSymlink = arg
        argSymlink = False
    elif argOutput:
        strOutput = arg
        argOutput = False
    elif argChoices:
        strChoices = arg
        argChoices = False
    elif arg == "-i":
        argInput = True
    elif arg == "-sl":
        argSymlink = True
    elif arg == "-o":
        argOutput = True
    elif arg == "-ch":
        argChoices = True
    elif arg == "-gv":
        argGridView = True
    elif arg.startswith("-") and arg[1:].lower() in animated_formats:
        animated_formats.remove(arg[1:].lower())
    elif arg.startswith("-") and arg[1:].lower() in image_formats:
        image_formats.remove(arg[1:].lower())
    elif arg == "-h":
        print(f"""{G}Interactive image/animation comparator for sorting content. {C}v0.1{E}
{W}Shows two files side by side, user picks one via click or arrow key.
Sorting uses binary insertion with O(n log n) comparisons.
Progress is saved for resume.{E}
- `{Y}-h{E}`: Print the help message.
- `{Y}-i{E} {C}<path>{E}`: Specify input file(s) or directory(ies). Can be repeated.
        Directories are traversed recursively for supported files.
        If omitted, processes all supported files recursively in the
        current directory.
- `{Y}-{list(animated_formats)}{E}`: Exclude unwanted animated format.
- `{Y}-{list(image_formats)}{E}`: Exclude unwanted image format.
- `{Y}-sl{E} {C}<path>{E}`: Create symlinks of sorted results in the specified folder.
        Format: "{G}1.filename.ext{E}", "{G}2.filename.ext{E}", etc.
- `{Y}-o{E} {C}<filename>{E}`: Save sorted file list (text, one path per line) to the given file.
        If not specified, the list is not saved.
- `{Y}-ch{E} {C}<filename>{E}`: Choices cache file (default: {D}{defChoices}{E}).
- `{Y}-gv{E}`: Open grid view of sorted results after completion.""")
        exit(0)
    else:
        print(f"{R}Unknown argument: {arg}{E}")
        exit(1)

supported_formats = { *animated_formats, *image_formats }

expanded = []
src_map = {}
for i, path in enumerate(files):
    src = os.path.abspath(path) if os.path.isdir(path) else os.path.abspath(os.path.dirname(path) or ".")
    if os.path.isdir(path):
        for root, dirs, filenames in os.walk(path):
            for f in filenames:
                if os.path.splitext(f)[1][1:].lower() in supported_formats:
                    full = os.path.join(root, f)
                    if os.path.islink(full):
                        continue
                    rel = os.path.relpath(full, src)
                    expanded.append(rel)
                    src_map[rel] = src
    else:
        if not os.path.islink(path):
            rel = os.path.relpath(os.path.abspath(path), src)
            expanded.append(rel)
            src_map[rel] = src
files = expanded
sources = src_map

if len(files) == 0:
    src = os.path.abspath(".")
    for root, dirs, filenames in os.walk("."):
        for f in filenames:
            if os.path.splitext(f)[1][1:].lower() in supported_formats:
                full = os.path.join(root, f)
                if os.path.islink(full):
                    continue
                rel = os.path.relpath(full, src)
                files.append(rel)
                sources[rel] = src

# Deduplicate while preserving order
seen = set()
unique_files = []
for f in files:
    norm = os.path.normpath(f)
    if norm not in seen:
        seen.add(norm)
        unique_files.append(f)
files = unique_files
strOutput = os.path.join(sources[files[0]], strOutput) if strOutput else ""
strChoices = os.path.join(sources[files[0]], strChoices if strChoices else defChoices)

if len(files) < 2:
    print(f"{R}Need at least 2 files, found {len(files)}{E}")
    exit(1)

# ─── Choices cache ───────────────────────────────────────────────────────────

def _norm(p):
    return os.path.normpath(p).replace("\\", "/")

def _load_choices():
    cache = {}
    if not os.path.exists(strChoices):
        return cache
    try:
        with open(strChoices, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                parts = line.split(" | ")
                if len(parts) == 3:
                    result, a, b = parts
                    result = "L" if result == "L" else "R"
                    a, b = _norm(a), _norm(b)
                    key = (a, b) if a <= b else (b, a)
                    cache[key] = result
    except Exception:
        pass
    return cache

def _to_relative(p):
    p = _norm(p)
    if not os.path.isabs(p):
        return p
    for src in sorted(set(sources.values()), key=len, reverse=True):
        try:
            return os.path.relpath(p, src).replace("\\", "/")
        except ValueError:
            continue
    return os.path.basename(p)

def _record_choice(a, b, result, cache):
    a, b = _norm(a), _norm(b)
    key = (a, b) if a <= b else (b, a)
    cache[key] = result
    try:
        with open(strChoices, "a", encoding="utf-8") as f:
            f.write(f"{result} | {_to_relative(a)} | {_to_relative(b)}\n")
    except Exception:
        pass

def _lookup(a, b, cache):
    a, b = _norm(a), _norm(b)
    key = (a, b) if a <= b else (b, a)
    if key in cache:
        return cache[key]
    # Try resolving absolute paths to relative
    for prefix in sorted(set(sources.values()), key=len, reverse=True):
        rel_a = os.path.relpath(a, prefix).replace("\\", "/") if os.path.isabs(a) else a
        rel_b = os.path.relpath(b, prefix).replace("\\", "/") if os.path.isabs(b) else b
        key2 = (rel_a, rel_b) if rel_a <= rel_b else (rel_b, rel_a)
        if key2 in cache:
            return cache[key2]
    return None

def _save_result(sorted_items):
    if not strOutput:
        return
    try:
        with open(strOutput, "w", encoding="utf-8") as f:
            for i, item in enumerate(sorted_items, 1):
                f.write(f"{item}\n")
    except Exception:
        pass

def _save_choices(cache):
    try:
        with open(strChoices, "w", encoding="utf-8") as f:
            for (ka, kb), v in cache.items():
                f.write(f"{v} | {_to_relative(ka)} | {_to_relative(kb)}\n")
    except Exception:
        pass

def _create_symlinks(sorted_items):
    if not strSymlink:
        return
    try:
        os.makedirs(strSymlink, exist_ok=True)
        for i, item in enumerate(sorted_items, 1):
            src = os.path.join(sources.get(item, "."), item)
            name = os.path.basename(item)
            link_name = f"{i}.{name}"
            link_path = os.path.join(strSymlink, link_name)
            if os.path.exists(link_path) or os.path.islink(link_path):
                os.remove(link_path)
            os.symlink(os.path.abspath(src), link_path)
    except Exception as e:
        print(f"{R}Symlink error: {e}{E}")
        exit(1)

def _show_grid_view(sorted_items):
    if not argGridView:
        return
    try:
        gv = tk.Tk()
        gv.title("Grid View")
        gv.configure(bg=BG)
        gv.state("zoomed")

        cell_w, cell_h = 200, 220
        pad = 8

        canvas = tk.Canvas(gv, bg=BG, highlightthickness=0)
        scrollbar = tk.Scrollbar(gv, orient=tk.VERTICAL, command=canvas.yview)
        scroll_frame = tk.Frame(canvas, bg=BG)

        scroll_frame.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=scroll_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)

        canvas.pack(side=tk.LEFT, expand=True, fill=tk.BOTH)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        def _on_mousewheel(e):
            canvas.yview_scroll(int(-1 * (e.delta / 120)), "units")
        canvas.bind_all("<MouseWheel>", _on_mousewheel)

        photos = []
        img_labels = []
        cell_frames = []
        load_results = [None] * len(sorted_items)

        # Build grid with placeholders
        for i, item in enumerate(sorted_items):
            cell = tk.Frame(scroll_frame, bg=BG, width=cell_w, height=cell_h)
            cell.grid_propagate(False)

            img_label = tk.Label(cell, bg=BG, text="...", fg=FG_DIM)
            img_label.pack(expand=True, fill=tk.BOTH)
            img_labels.append(img_label)

            name = os.path.basename(item)
            tk.Label(cell, text=f"{i + 1}. {name}", bg=BG, fg=FG_TEXT,
                     font=("Segoe UI", 9), wraplength=cell_w - 10, anchor="n").pack(fill=tk.X)

            photos.append(None)
            cell_frames.append(cell)

        # Layout cells in grid
        _cur_cols = [0]
        def _layout():
            w = canvas.winfo_width()
            new_cols = max(1, (w - 20) // (cell_w + pad))
            if new_cols == _cur_cols[0]:
                return
            _cur_cols[0] = new_cols
            for i, cell in enumerate(cell_frames):
                row, col = divmod(i, new_cols)
                cell.grid(row=row, column=col, padx=pad // 2, pady=pad // 2)

        # Show window immediately
        gv.update()
        _layout()

        _resize_id = [None]
        def _on_resize(e):
            if _resize_id[0] is not None:
                gv.after_cancel(_resize_id[0])
            _resize_id[0] = gv.after(100, _layout)
        gv.bind("<Configure>", _on_resize)

        # Load images in background threads
        sem = threading.Semaphore(MAX_LOAD_THREADS)
        def _load_one(idx, path):
            sem.acquire()
            try:
                with Image.open(path) as im:
                    thumb = ImageOps.exif_transpose(im).copy()
                load_results[idx] = thumb
            except Exception:
                load_results[idx] = False
            finally:
                sem.release()

        threads = []
        for i, item in enumerate(sorted_items):
            full = os.path.join(sources.get(item, "."), item)
            t = threading.Thread(target=_load_one, args=(i, full), daemon=True)
            t.start()
            threads.append(t)

        # Poll for completion (track remaining indices)
        pending = set(range(len(sorted_items)))
        def _poll():
            done = [i for i in pending if not threads[i].is_alive()]
            for i in done:
                pending.discard(i)
                result = load_results[i]
                if result is not None and result is not False:
                    photos[i] = _resize_image(result, cell_w - 10, cell_h - 40)
                    img_labels[i].configure(image=photos[i], text="")
                else:
                    img_labels[i].configure(text="[error]", fg=FG_DIM)
            if pending:
                gv.after(50, _poll)

        gv.after(100, _poll)
        gv.mainloop()
    except Exception as e:
        print(f"{Y}Grid view error: {e}{E}")

# ─── Binary insertion sort ───────────────────────────────────────────────────

def sort_next(sorted_list, pending, cache):
    """Return next pair (left, right) to compare, or None if done.
    Binary search is resolved from cache where possible."""
    if not pending:
        return None
    item = pending.pop(0)
    if not sorted_list:
        sorted_list.append(item)
        _save_result(sorted_list)
        return sort_next(sorted_list, pending, cache)
    lo, hi = 0, len(sorted_list)
    while lo < hi:
        mid = (lo + hi) // 2
        cached = _lookup(item, sorted_list[mid], cache)
        if cached == "L":
            hi = mid
        elif cached == "R":
            lo = mid + 1
        else:
            pending.insert(0, item)
            return item, sorted_list[mid]
    sorted_list.insert(lo, item)
    _save_result(sorted_list)
    return sort_next(sorted_list, pending, cache)

# ─── UI ──────────────────────────────────────────────────────────────────────

class Comparer:
    def _create_side(self, side_char):
        panel = tk.Frame(self.frame, bg=BG)
        panel.pack(side=tk.LEFT if side_char == "L" else tk.RIGHT, expand=True, fill=tk.BOTH, padx=4, pady=4)
        panel.pack_propagate(False)
        label = tk.Label(panel, bg=BG, cursor="hand2")
        label.pack(expand=True, fill=tk.BOTH)
        label.bind("<Button-1>", lambda e, s=side_char: self.pick(s))
        loading = tk.Label(panel, text="Loading...", bg=BG, fg=FG_LOAD, font=("Segoe UI", 16))
        return panel, label, loading

    def __init__(self):
        self.cache = _load_choices()
        _save_choices(self.cache)
        self.sorted_list = []
        self.pending = list(files)

        self.root = tk.Tk()
        self.root.title("sort_content")
        self.root.configure(bg=BG)
        self.root.minsize(640, 360)
        self.root.state("zoomed")
        self.root.bind("<Left>", lambda e: self.pick("L"))
        self.root.bind("<Right>", lambda e: self.pick("R"))
        self.root.bind("<Escape>", lambda e: self._quit())
        self.root.protocol("WM_DELETE_WINDOW", self._quit)

        self.frame = tk.Frame(self.root, bg=BG)
        self.frame.pack(expand=True, fill=tk.BOTH)

        self._sides = {}
        for s in ("L", "R"):
            panel, label, loading = self._create_side(s)
            self._sides[s] = {"panel": panel, "label": label, "loading": loading}

        self._closing = False
        self._load_gen = 0
        self._resize_pending = False
        self._last_size = (0, 0)
        self._last_size_done = (0, 0)
        self._resizing = False
        self._cached_size = (100, 100)
        self._size_version = 0
        self.frame.bind("<Configure>", self._on_resize)
        self.root.after(50, self._init_show)

    def _init_show(self):
        self.root.update()
        self._cached_size = self._get_size()
        self._last_size = (self.frame.winfo_width(), self.frame.winfo_height())
        self.show_pair()

    def _finalize(self):
        if self.sorted_list:
            _save_result(self.sorted_list)
            _create_symlinks(self.sorted_list)
        self.root.destroy()
        _show_grid_view(self.sorted_list)
        os._exit(0)

    def _quit(self):
        self._closing = True
        self.stop_animations()
        self._finalize()

    def _get_size(self):
        w = self.frame.winfo_width()
        h = self.frame.winfo_height()
        return max(w // 2 - 8, 100), max(h - 8, 100)

    def _full_path(self, rel):
        src = sources.get(rel, ".")
        return os.path.join(src, rel)

    def _on_resize(self, event):
        if self._closing:
            return
        fw = self.frame.winfo_width()
        fh = self.frame.winfo_height()
        size = (fw, fh)
        if size == self._last_size:
            return
        self._last_size = size
        if not self._resize_pending:
            self._resize_pending = True
            self.root.after_idle(self._do_resize)

    def _do_resize(self):
        self._resize_pending = False
        if self._closing or self._resizing:
            return
        self._resizing = True
        try:
            size = (self.frame.winfo_width(), self.frame.winfo_height())
            if size == self._last_size_done:
                return
            self._last_size_done = size
            max_w, max_h = self._get_size()
            self._cached_size = (max_w, max_h)
            self._size_version += 1
            for s in ("L", "R"):
                ad = self._sides[s].get("anim")
                if not ad or ad.kind != "static":
                    continue
                if ad.orig:
                    photo = _resize_image(ad.orig[0], max_w, max_h)
                    ad.frames = [photo]
                    ad.size_version = self._size_version
                    self._sides[s]["label"].configure(image=photo)
        finally:
            self._resizing = False

    def stop_animations(self):
        try:
            for s in ("L", "R"):
                aid = self._sides[s].get("after_id")
                if aid is not None:
                    self.root.after_cancel(aid)
                    self._sides[s]["after_id"] = None
        except tk.TclError:
            pass

    def _load_frames(self, path, max_w, max_h, result):
        try:
            im = Image.open(path)
            is_animated = getattr(im, "is_animated", False)
            if is_animated:
                frames = []
                delays = []
                for idx in range(getattr(im, "n_frames", 1)):
                    im.seek(idx)
                    frame = ImageOps.exif_transpose(im).copy().convert("RGB")
                    frames.append(frame)
                    delays.append(im.info.get("duration", 20))
                    if idx == 0:
                        result["first_img"] = frame
                result["pil_frames"] = frames
                result["delays"] = delays
                result["total"] = len(frames)
            else:
                img = ImageOps.exif_transpose(im).copy().convert("RGB")
                result["first_img"] = img
                result["pil_frames"] = [img]
                result["delays"] = [0]
                result["total"] = 1
            im.close()
        except Exception as ex:
            print(f"{Y}Failed to load {path}: {ex}{E}")
            result["error"] = True

    def load_image(self, path, max_w, max_h, side):
        anim = AnimData(size_version=self._size_version)
        result = {}
        t = threading.Thread(target=self._load_frames, args=(path, max_w, max_h, result), daemon=True)
        t.start()
        self._sides[side]["loading"].place(relx=0.5, rely=0.5, anchor="center")
        self._poll_ready(side, anim, result, t, self._load_gen)
        return anim

    def _poll_ready(self, side, anim, result, thread, gen):
        if self._closing or gen != self._load_gen:
            return
        max_w, max_h = self._cached_size
        if "first_img" in result and not anim.frames:
            photo0 = _resize_image(result["first_img"], max_w, max_h)
            anim.frames = [photo0]
            self._sides[side]["label"].configure(image=photo0)
        if thread.is_alive():
            self.root.after(50, self._poll_ready, side, anim, result, thread, gen)
            return
        self._sides[side]["loading"].place_forget()
        if "error" in result:
            anim.kind = "error"
            return
        if gen != self._load_gen:
            return
        pil_frames = result["pil_frames"]
        anim.frames = [anim.frames[0]] + [None] * (len(pil_frames) - 1)
        anim.delays = result["delays"]
        anim.total = result["total"]
        anim.orig = pil_frames
        if result["total"] <= 1:
            anim.kind = "static"

    def animate(self, label, anim, side):
        if self._closing:
            return
        if anim.kind == "error":
            return
        max_w, max_h = self._cached_size
        if anim.size_version != self._size_version:
            if anim.kind == "static":
                if anim.frames and isinstance(anim.frames[0], ImageTk.PhotoImage):
                    if anim.orig:
                        anim.frames[0] = anim.orig[0]
            else:
                for i in range(len(anim.frames)):
                    anim.frames[i] = None
            anim.size_version = self._size_version
        if anim.kind == "static":
            if anim.frames:
                f = anim.frames[0]
                if isinstance(f, Image.Image):
                    anim.frames[0] = _resize_image(f, max_w, max_h)
                label.configure(image=anim.frames[0])
            return
        if not anim.frames or anim.total == 0:
            after_id = self.root.after(50, self.animate, label, anim, side)
            self._sides[side]["after_id"] = after_id
            return
        next_idx = (anim.cur + 1) % anim.total
        if anim.frames[next_idx] is None and anim.orig and next_idx < len(anim.orig):
            anim.frames[next_idx] = _resize_image(anim.orig[next_idx], max_w, max_h)
        elif isinstance(anim.frames[next_idx], Image.Image):
            anim.frames[next_idx] = _resize_image(anim.frames[next_idx], max_w, max_h)
        label.configure(image=anim.frames[next_idx])
        anim.cur = next_idx
        after_next = (next_idx + 1) % anim.total
        if anim.orig and after_next < len(anim.orig) and anim.frames[after_next] is None:
            def _precompute(idx=after_next):
                if len(anim.frames) > idx and anim.frames[idx] is None and anim.orig and idx < len(anim.orig):
                    anim.frames[idx] = _resize_image(anim.orig[idx], max_w, max_h)
            self.root.after_idle(_precompute)
        after_id = self.root.after(anim.delays[anim.cur], self.animate, label, anim, side)
        self._sides[side]["after_id"] = after_id

    def show_pair(self):
        self.stop_animations()
        for s in ("L", "R"):
            self._sides[s]["loading"].place_forget()
        self._load_gen += 1
        self.root.update_idletasks()
        self.frame.update_idletasks()
        max_w, max_h = self._get_size()
        self._cached_size = (max_w, max_h)

        pair = sort_next(self.sorted_list, self.pending, self.cache)
        if pair is None:
            print(f"\n{G}Sorting complete! {len(self.sorted_list)} files sorted.{E}")
            if strOutput:
                print(f"{G}File list saved to {C}{strOutput}{E}\n")
            for i, item in enumerate(self.sorted_list, 1):
                print(f"  {G}{i}.{E} {W}{item}{E}")
            self._finalize()

        left_path, right_path = pair
        self._sides["L"]["path"] = left_path
        self._sides["R"]["path"] = right_path
        left_data = self.load_image(self._full_path(left_path), max_w, max_h, "L")
        right_data = self.load_image(self._full_path(right_path), max_w, max_h, "R")
        if left_data.kind == "error" or right_data.kind == "error":
            self.show_pair()
            return
        self._sides["L"]["anim"] = left_data
        self._sides["R"]["anim"] = right_data
        self.animate(self._sides["L"]["label"], left_data, "L")
        self.animate(self._sides["R"]["label"], right_data, "R")
        n = len(self.sorted_list) + len(self.pending) + 1
        done = len(self.sorted_list)
        self.root.title(f"{left_path}  vs  {right_path}  ({done}/{n})")

    def pick(self, side):
        self.stop_animations()
        left_path = self._sides["L"]["path"]
        right_path = self._sides["R"]["path"]
        chosen = left_path if side == "L" else right_path
        print(f"{G}Chosen: {Y}{side}{E} — {W}{chosen}{E}")
        _record_choice(left_path, right_path, side, self.cache)
        self.show_pair()

    def run(self):
        self.root.mainloop()

Comparer().run()

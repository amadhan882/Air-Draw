import os
import sys

os.environ["GLOG_minloglevel"] = "2"
os.environ["TF_CPP_MIN_LOG_LEVEL"] = "3"

import cv2
import mediapipe as mp
from mediapipe.tasks.python import vision
from mediapipe.tasks import python
import pygame
import math
import logging
import random
import hashlib
import tempfile
import time
import json
import urllib.request
from collections import OrderedDict, deque
import datetime

# ================= CONFIG =================
MODEL_URL = "https://storage.googleapis.com/mediapipe-models/hand_landmarker/hand_landmarker/float16/1/hand_landmarker.task"
MODEL_PATH = "hand_landmarker.task"

WINDOW_WIDTH, WINDOW_HEIGHT = 1280, 720
FPS = 120
PROCESS_W, PROCESS_H = 640, 360

DRAW_MODES = ["CONTINUOUS", "PINCH"]
MAX_STROKES = 300
MAX_PTS = 600
MIN_MOVE = 1.5
MAX_JUMP = 250

PINCH_ON = 0.042
PINCH_OFF = 0.062

BRUSH_SIZES = [
    ("XS", 2, 2),
    ("S", 4, 6),
    ("M", 8, 11),
    ("L", 14, 18),
]

BRUSH_COLORS = [
    ("Green", (0, 255, 80)),
    ("Cyan", (0, 210, 255)),
    ("Pink", (255, 50, 190)),
    ("Gold", (255, 200, 10)),
    ("White", (240, 240, 240)),
    ("Red", (255, 55, 30)),
    ("Orange", (255, 140, 0)),
    ("Purple", (180, 0, 255)),
    ("Sky", (80, 180, 255)),
    ("Lime", (180, 255, 0)),
]

BRUSH_STYLES = [
    "NORMAL",
    "CHALK",
    "HEART",
    "STAR",
    "SQUARE",
    "DIAMOND",
    "TRIANGLE",
    "CROSS",
    "HEXAGON",
    "PENTAGON",
    "BUBBLE",
    "DOTS",
    "OUTLINE",
    "SPARKLE",
    "CLOUD",
    "LEAF",
    "FLOWER",
    "RAINDROP",
]

PANEL_W = 220
PANEL_X = WINDOW_WIDTH - PANEL_W
DWELL_SEC = 0.7

PANEL_BOTTOM_RESERVE = 90
PANEL_SCROLL_SPEED = 20

SYMMETRY_MODES = ["NONE", "VERTICAL", "HORIZONTAL", "QUAD"]

GLOW_ENABLED_DEFAULT = True
SHAPE_CACHE_MAX = 512
CHALK_CACHE_MAX = 256
MODEL_DOWNLOAD_TIMEOUT_SEC = 30
MODEL_DOWNLOAD_RETRIES = 3
MODEL_SHA256 = os.getenv("AIR_DRAW_MODEL_SHA256", "").strip().lower()
SETTINGS_PATH = os.getenv("AIR_DRAW_SETTINGS_PATH", "air_draw_settings.json")
DIAGNOSTICS_DIR = os.getenv("AIR_DRAW_DIAGNOSTICS_DIR", ".")


logging.basicConfig(
    level=getattr(logging, os.getenv("AIR_DRAW_LOG_LEVEL", "INFO").upper(), logging.INFO),
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger("air_draw")


# ================= DOWNLOAD =================
def download_model():
    if os.path.exists(MODEL_PATH):
        logger.info("Using cached model at %s", MODEL_PATH)
        return

    logger.info("Downloading MediaPipe hand model…")
    opener = urllib.request.build_opener()
    opener.addheaders = [("User-Agent", "AirDraw/1.0")]
    urllib.request.install_opener(opener)

    last_exc = None
    for attempt in range(1, MODEL_DOWNLOAD_RETRIES + 1):
        tmp_path = None
        try:
            with tempfile.NamedTemporaryFile(delete=False, suffix=".task") as tmp:
                tmp_path = tmp.name
            with urllib.request.urlopen(MODEL_URL, timeout=MODEL_DOWNLOAD_TIMEOUT_SEC) as src, open(tmp_path, "wb") as dst:
                dst.write(src.read())

            if MODEL_SHA256:
                hasher = hashlib.sha256()
                with open(tmp_path, "rb") as fp:
                    for chunk in iter(lambda: fp.read(8192), b""):
                        hasher.update(chunk)
                got = hasher.hexdigest().lower()
                if got != MODEL_SHA256:
                    raise RuntimeError(f"SHA256 mismatch for model. expected={MODEL_SHA256} got={got}")

            os.replace(tmp_path, MODEL_PATH)
            logger.info("Model downloaded successfully to %s", MODEL_PATH)
            return
        except Exception as exc:
            last_exc = exc
            logger.warning("Model download attempt %d/%d failed: %s", attempt, MODEL_DOWNLOAD_RETRIES, exc)
            if tmp_path and os.path.exists(tmp_path):
                os.unlink(tmp_path)
            time.sleep(min(5, attempt))

    raise RuntimeError(f"Unable to download model after {MODEL_DOWNLOAD_RETRIES} attempts") from last_exc


def _clamp_index(value, upper):
    if upper <= 0:
        return 0
    return max(0, min(int(value), upper - 1))


def load_settings():
    defaults = {
        "brush_size_idx": 1,
        "brush_color_idx": 0,
        "brush_style_idx": 0,
        "draw_mode_idx": 1,
        "sym_mode_idx": 0,
        "glow_enabled": GLOW_ENABLED_DEFAULT,
    }
    if not os.path.exists(SETTINGS_PATH):
        return defaults

    try:
        with open(SETTINGS_PATH, "r", encoding="utf-8") as fp:
            data = json.load(fp)
        defaults.update(data if isinstance(data, dict) else {})
    except Exception as exc:
        logger.warning("Failed to load settings from %s: %s", SETTINGS_PATH, exc)
    return defaults


def save_settings(settings):
    try:
        with open(SETTINGS_PATH, "w", encoding="utf-8") as fp:
            json.dump(settings, fp, indent=2, sort_keys=True)
    except Exception as exc:
        logger.warning("Failed to save settings to %s: %s", SETTINGS_PATH, exc)


def export_diagnostics(payload):
    ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    path = os.path.join(DIAGNOSTICS_DIR, f"air_draw_diag_{ts}.json")
    with open(path, "w", encoding="utf-8") as fp:
        json.dump(payload, fp, indent=2, sort_keys=True)
    return path


# ================= UTIL =================
def to_screen(lm):
    return int(lm.x * WINDOW_WIDTH), int(lm.y * WINDOW_HEIGHT)


def detect_pinch(landmarks, prev_state):
    d = math.hypot(landmarks[4].x - landmarks[8].x, landmarks[4].y - landmarks[8].y)
    return d < (PINCH_OFF if prev_state else PINCH_ON)


def detect_spread(landmarks):
    """Returns 0.0–1.0 based on index–pinky tip spread."""
    d = math.hypot(landmarks[8].x - landmarks[20].x, landmarks[8].y - landmarks[20].y)
    return max(0.0, min(1.0, d / 0.35))


def export_canvas(canvas_surf):
    ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    path = f"handpainter_{ts}.png"
    export = pygame.Surface((WINDOW_WIDTH, WINDOW_HEIGHT))
    export.fill((15, 15, 20))
    export.blit(canvas_surf, (0, 0))
    pygame.image.save(export, path)
    return path


def draw_glow_line(surface, color, p1, p2, r):
    """Draws a soft glow bloom around a line using alpha surfaces."""
    for _layer, alpha, extra in [(3, 25, 6), (2, 50, 3), (1, 120, 1)]:
        glow_col = (*color, alpha)
        w = max(1, (r + extra) * 2)
        glow_surf = pygame.Surface((WINDOW_WIDTH, WINDOW_HEIGHT), pygame.SRCALPHA)
        pygame.draw.line(glow_surf, glow_col, p1, p2, w)
        surface.blit(glow_surf, (0, 0))


def mirror_points(pos, sym_mode):
    """Returns list of (mirrored) positions to draw at for given symmetry."""
    x, y = pos
    cx, cy = WINDOW_WIDTH // 2, WINDOW_HEIGHT // 2
    pts = [pos]
    if sym_mode == "VERTICAL":
        pts.append((2 * cx - x, y))
    elif sym_mode == "HORIZONTAL":
        pts.append((x, 2 * cy - y))
    elif sym_mode == "QUAD":
        pts += [(2 * cx - x, y), (x, 2 * cy - y), (2 * cx - x, 2 * cy - y)]
    return pts


# ================= CACHES =================
_shape_cache = OrderedDict()


def get_shape_stamp(style, r, color):
    key = (style, r, color)
    if key in _shape_cache:
        _shape_cache.move_to_end(key)
        return _shape_cache[key]

    size = int(r * 3) + 4
    surf = pygame.Surface((size, size), pygame.SRCALPHA)
    cx, cy = size // 2, size // 2

    if style == "HEART":
        points = []
        for t in range(0, 360, 10):
            rad = math.radians(t)
            x = 16 * (math.sin(rad) ** 3)
            y = (
                13 * math.cos(rad)
                - 5 * math.cos(2 * rad)
                - 2 * math.cos(3 * rad)
                - math.cos(4 * rad)
            )
            scale = max(1, r) / 16.0
            points.append((cx + x * scale, cy - y * scale))
        if len(points) > 2:
            pygame.draw.polygon(surf, color, points)
    elif style == "STAR":
        points = []
        for i in range(10):
            angle = i * math.pi / 5 - math.pi / 2
            radius = r if i % 2 == 0 else r / 2
            points.append((cx + radius * math.cos(angle), cy + radius * math.sin(angle)))
        if len(points) > 2:
            pygame.draw.polygon(surf, color, points)
    elif style == "SQUARE":
        pygame.draw.rect(surf, color, (cx - r, cy - r, r * 2, r * 2))
    elif style == "DIAMOND":
        points = [(cx, cy - r), (cx + r, cy), (cx, cy + r), (cx - r, cy)]
        pygame.draw.polygon(surf, color, points)
    elif style == "TRIANGLE":
        points = [
            (cx, cy - r),
            (cx + r * math.cos(math.pi / 6), cy + r * math.sin(math.pi / 6)),
            (cx - r * math.cos(math.pi / 6), cy + r * math.sin(math.pi / 6)),
        ]
        pygame.draw.polygon(surf, color, points)
    elif style == "CROSS":
        pygame.draw.rect(surf, color, (cx - r, cy - max(1, r // 3), r * 2, max(1, r * 2 // 3)))
        pygame.draw.rect(surf, color, (cx - max(1, r // 3), cy - r, max(1, r * 2 // 3), r * 2))
    elif style == "HEXAGON":
        points = []
        for i in range(6):
            angle = i * math.pi / 3
            points.append((cx + r * math.cos(angle), cy + r * math.sin(angle)))
        if len(points) > 2:
            pygame.draw.polygon(surf, color, points)
    elif style == "PENTAGON":
        points = []
        for i in range(5):
            angle = i * math.pi * 2 / 5 - math.pi / 2
            points.append((cx + r * math.cos(angle), cy + r * math.sin(angle)))
        if len(points) > 2:
            pygame.draw.polygon(surf, color, points)
    elif style == "BUBBLE":
        pygame.draw.circle(surf, color, (cx, cy), r, max(1, r // 3))
        pygame.draw.circle(surf, (255, 255, 255, 150), (cx - r // 3, cy - r // 3), max(1, r // 4))
    elif style == "DOTS":
        pygame.draw.circle(surf, color, (cx - r // 2, cy - r // 2), max(1, r // 3))
        pygame.draw.circle(surf, color, (cx + r // 2, cy + r // 2), max(1, r // 3))
    elif style == "OUTLINE":
        pygame.draw.circle(surf, color, (cx, cy), r, max(1, r // 4))
    elif style == "SPARKLE":
        pygame.draw.line(surf, color, (cx, cy - r), (cx, cy + r), max(1, r // 4))
        pygame.draw.line(surf, color, (cx - r, cy), (cx + r, cy), max(1, r // 4))
    elif style == "CLOUD":
        pygame.draw.circle(surf, color, (cx, cy), r // 2)
        pygame.draw.circle(surf, color, (cx - r // 2, cy), max(1, r // 3))
        pygame.draw.circle(surf, color, (cx + r // 2, cy), max(1, r // 3))
        pygame.draw.circle(surf, color, (cx, cy - r // 3), r // 2)
    elif style == "LEAF":
        points = [(cx, cy - r), (cx + r // 2, cy), (cx, cy + r), (cx - r // 2, cy)]
        pygame.draw.polygon(surf, color, points)
    elif style == "FLOWER":
        for i in range(5):
            angle = i * math.pi * 2 / 5
            px = cx + (r // 2) * math.cos(angle)
            py = cy + (r // 2) * math.sin(angle)
            pygame.draw.circle(surf, color, (int(px), int(py)), max(1, r // 2))
        pygame.draw.circle(surf, (255, 255, 0), (cx, cy), max(1, r // 3))
    elif style == "RAINDROP":
        points = [(cx, cy - r), (cx + r // 2, cy + r // 2), (cx - r // 2, cy + r // 2)]
        pygame.draw.polygon(surf, color, points)
        pygame.draw.circle(surf, color, (cx, cy + r // 2), max(1, r // 2))

    _shape_cache[key] = (surf, cx)
    _shape_cache.move_to_end(key)
    while len(_shape_cache) > SHAPE_CACHE_MAX:
        _shape_cache.popitem(last=False)
    return surf, cx


_chalk_cache = OrderedDict()


def get_chalk_dot(color, a):
    a = (a // 20) * 20
    key = (color, a)
    if key in _chalk_cache:
        _chalk_cache.move_to_end(key)
        return _chalk_cache[key]
    cs = pygame.Surface((3, 3), pygame.SRCALPHA)
    pygame.draw.circle(cs, (*color, a), (1, 1), 1)
    _chalk_cache[key] = cs
    _chalk_cache.move_to_end(key)
    while len(_chalk_cache) > CHALK_CACHE_MAX:
        _chalk_cache.popitem(last=False)
    return cs


# ================= SMOOTH TRACKER =================
class SmoothTracker:
    """Weighted exponential moving average with velocity cap."""

    def __init__(self, alpha=0.45, buf=6):
        self.alpha = alpha
        self.pos = None
        self.buf = deque(maxlen=buf)

    def update(self, raw):
        self.buf.append(raw)
        avg_x = sum(p[0] for p in self.buf) / len(self.buf)
        avg_y = sum(p[1] for p in self.buf) / len(self.buf)
        if self.pos is None:
            self.pos = (avg_x, avg_y)
        else:
            a = self.alpha
            self.pos = (self.pos[0] * (1 - a) + avg_x * a, self.pos[1] * (1 - a) + avg_y * a)
        return self.pos

    def reset(self):
        self.pos = None
        self.buf.clear()


# ================= HAND DRAWER =================
class HandDrawer:
    def __init__(self):
        self.strokes = deque(maxlen=MAX_STROKES)
        self.current = None
        self.was_drawing = False
        self.last_pos = None
        self.last_pinch = False
        self.frames_unseen = 0
        self.frames_not_drawing = 0
        self.just_started = False
        self.warmup = 0
        self.tracker = SmoothTracker()
        self.drawn_pts_len = 0
        self.prev_wrist = None
        self.swipe_vel_buffer = deque(maxlen=5)

    def update_swipe(self, wrist_pos):
        if self.prev_wrist:
            dx = wrist_pos[0] - self.prev_wrist[0]
            dy = wrist_pos[1] - self.prev_wrist[1]
            self.swipe_vel_buffer.append((dx, dy))
        self.prev_wrist = wrist_pos

        if len(self.swipe_vel_buffer) == 5:
            avg_dx = sum(v[0] for v in self.swipe_vel_buffer) / 5
            avg_dy = sum(v[1] for v in self.swipe_vel_buffer) / 5
            speed = math.hypot(avg_dx, avg_dy)

            if speed > 40:
                self.swipe_vel_buffer.clear()
                if avg_dy < -25 and abs(avg_dy) > abs(avg_dx):
                    return "UP"
                elif avg_dx < -25 and abs(avg_dx) > abs(avg_dy):
                    return "LEFT"
        return None

    def reset(self):
        self.strokes.clear()
        self.current = None
        self.was_drawing = False
        self.last_pos = None
        self.last_pinch = False
        self.frames_unseen = 0
        self.frames_not_drawing = 0
        self.tracker.reset()
        self.drawn_pts_len = 0
        self.prev_wrist = None
        self.swipe_vel_buffer.clear()

    def undo(self):
        if self.strokes:
            self.strokes.pop()

    def on_lost(self):
        self.frames_unseen += 1
        if self.frames_unseen > 10:
            if self.was_drawing and self.current and len(self.current["pts"]) >= 2:
                self.strokes.append(self.current)
            self.current = None
            self.was_drawing = False
            self.last_pos = None
            self.last_pinch = False
            self.frames_not_drawing = 0
            self.tracker.reset()
            self.drawn_pts_len = 0
            self.prev_wrist = None
            self.swipe_vel_buffer.clear()

    def update(self, raw_pos, drawing, brush_size, brush_color, brush_style, brush_alpha=255, sym_mode="NONE"):
        self.frames_unseen = 0
        pos = self.tracker.update(raw_pos)

        if not drawing:
            self.frames_not_drawing += 1
            if self.frames_not_drawing > 8:
                if self.was_drawing and self.current and len(self.current["pts"]) >= 2:
                    self.strokes.append(self.current)
                self.current = None
                self.was_drawing = False
                self.last_pos = None
                self.just_started = True
                self.warmup = 0
                self.drawn_pts_len = 0
            return

        self.frames_not_drawing = 0

        if not self.was_drawing:
            self.was_drawing = True
            self.current = {
                "pts": [],
                "size": brush_size,
                "color": brush_color,
                "style": brush_style,
                "alpha": brush_alpha,
                "sym": sym_mode,
            }
            self.last_pos = pos
            self.just_started = True
            self.warmup = 0
            self.drawn_pts_len = 0
            return

        if self.just_started:
            self.warmup += 1
            self.last_pos = pos
            if self.warmup >= 3:
                self.just_started = False
            return

        if self.last_pos is None:
            self.last_pos = pos
            return

        dx = pos[0] - self.last_pos[0]
        dy = pos[1] - self.last_pos[1]
        dist = math.hypot(dx, dy)

        if dist > MAX_JUMP:
            return
        if dist < MIN_MOVE:
            return

        if self.current and len(self.current["pts"]) < MAX_PTS:
            self.current["pts"].append(pos)
        self.last_pos = pos

    def draw_incremental(self, surface, glow_enabled=False):
        if not self.current:
            return
        pts = self.current["pts"]
        n = len(pts)
        if n < 2 or self.drawn_pts_len >= n:
            return

        start_idx = max(1, self.drawn_pts_len)
        for k in range(start_idx, n):
            self._render_segment(surface, self.current, k, glow_enabled)

        self.drawn_pts_len = n

    def redraw_all(self, surface, glow_enabled=False):
        for stroke in self.strokes:
            stroke["dist_rem"] = 0.0
            for k in range(1, len(stroke["pts"])):
                self._render_segment(surface, stroke, k, glow_enabled)
        if self.current:
            self.current["dist_rem"] = 0.0
            for k in range(1, len(self.current["pts"])):
                self._render_segment(surface, self.current, k, glow_enabled)
            self.drawn_pts_len = len(self.current["pts"])

    @staticmethod
    def _render_segment(surface, stroke, k, glow_enabled=False):
        pts = stroke["pts"]
        r = stroke["size"]
        color = stroke["color"]
        style = stroke["style"]
        alpha = stroke.get("alpha", 255)
        sym = stroke.get("sym", "NONE")

        p1, p2 = pts[k - 1], pts[k]

        pairs = [(p1, p2)]
        if sym != "NONE":
            mps1 = mirror_points(p1, sym)
            mps2 = mirror_points(p2, sym)
            pairs = list(zip(mps1, mps2))

        for mp1, mp2 in pairs:
            HandDrawer._draw_pair(surface, mp1, mp2, r, color, style, alpha, glow_enabled)

    @staticmethod
    def _draw_pair(surface, p1, p2, r, color, style, alpha=255, glow_enabled=False):
        dx = p2[0] - p1[0]
        dy = p2[1] - p1[1]
        dist = math.hypot(dx, dy)
        if dist == 0:
            return

        spd_r = max(max(1, r - 2), min(r, int(r * (1 + 6 / max(1, dist)))))

        if style == "ERASER":
            erase_surf = pygame.Surface((WINDOW_WIDTH, WINDOW_HEIGHT), pygame.SRCALPHA)
            er = spd_r * 3
            pygame.draw.line(erase_surf, (0, 0, 0, 0), p1, p2, er * 2)
            pygame.draw.circle(erase_surf, (0, 0, 0, 0), p1, er)
            pygame.draw.circle(erase_surf, (0, 0, 0, 0), p2, er)
            surface.blit(erase_surf, (0, 0), special_flags=pygame.BLEND_RGBA_MIN)
            return

        draw_color = (*color[:3], alpha) if alpha < 255 else color

        if style == "NORMAL":
            out_col = tuple(max(0, c // 4) for c in color[:3])
            mid_col = tuple(c // 2 for c in color[:3])

            if glow_enabled and alpha > 180:
                draw_glow_line(surface, color[:3], p1, p2, spd_r)

            pygame.draw.line(surface, out_col, p1, p2, (spd_r + 2) * 2)
            pygame.draw.line(surface, mid_col, p1, p2, spd_r * 2)
            pygame.draw.line(surface, draw_color, p1, p2, max(1, spd_r - 1) * 2)

            pygame.draw.circle(surface, out_col, p1, spd_r + 2)
            pygame.draw.circle(surface, mid_col, p1, spd_r)
            pygame.draw.circle(surface, draw_color, p1, max(1, spd_r - 1))

            pygame.draw.circle(surface, out_col, p2, spd_r + 2)
            pygame.draw.circle(surface, mid_col, p2, spd_r)
            pygame.draw.circle(surface, draw_color, p2, max(1, spd_r - 1))

        elif style == "CHALK":
            steps = max(1, int(dist / 3))

            for i in range(steps):
                t = i / steps
                x = int(p1[0] + dx * t)
                y = int(p1[1] + dy * t)
                for _ in range(max(2, spd_r)):
                    ox = random.randint(-spd_r, spd_r)
                    oy = random.randint(-spd_r, spd_r)
                    if ox * ox + oy * oy <= spd_r * spd_r:
                        a = random.randint(80, min(200, alpha))
                        cs = get_chalk_dot(color[:3], a)
                        surface.blit(cs, (x + ox - 1, y + oy - 1))
        else:
            spacing = max(14, spd_r * 2.2)
            steps = int(dist / spacing)

            for i in range(steps):
                t = max(0.0, min(1.0, (i * spacing) / dist))
                x = int(p1[0] + dx * t)
                y = int(p1[1] + dy * t)
                stamp, cx = get_shape_stamp(style, spd_r, color[:3])
                if alpha < 255:
                    stamp = stamp.copy()
                    stamp.set_alpha(alpha)
                surface.blit(stamp, (x - cx, y - cx))


# ================= UI PANEL =================
class Button:
    def __init__(self, rect, label, action, color=(60, 60, 70), text_color=(220, 220, 220)):
        self.rect = pygame.Rect(rect)
        self.label = label
        self.action = action
        self.bg_color = color
        self.text_color = text_color
        self.selected = False
        self.dwell = 0.0
        self.hovering = False
        self.last_pinch = False

    def update_state(self, finger_pos, is_pinching, dt):
        """Returns True if button was just triggered."""
        inside = self.rect.collidepoint(finger_pos) if finger_pos else False
        triggered = False

        if inside:
            if not self.hovering:
                self.hovering = True
                self.dwell = 0.0
            self.dwell += dt
            if self.dwell >= DWELL_SEC:
                self.dwell = 0.0
                triggered = True

            if is_pinching and not getattr(self, "last_pinch", False):
                triggered = True
                self.dwell = 0.0
        else:
            self.hovering = False
            self.dwell = 0.0

        self.last_pinch = is_pinching
        return triggered

    def draw(self, surface, font):
        bg = (100, 100, 120) if self.selected else self.bg_color
        if self.hovering:
            bg = tuple(min(255, c + 40) for c in bg)
        pygame.draw.rect(surface, bg, self.rect, border_radius=6)

        if self.hovering and self.dwell > 0:
            cx, cy = self.rect.centerx, self.rect.centery
            arc_r = min(self.rect.width, self.rect.height) // 2 - 2
            frac = self.dwell / DWELL_SEC
            end_a = -math.pi / 2 + frac * 2 * math.pi
            pygame.draw.arc(surface, (255, 220, 80), (cx - arc_r, cy - arc_r, arc_r * 2, arc_r * 2), -math.pi / 2, end_a, 3)

        if self.selected:
            pygame.draw.rect(surface, (255, 220, 80), self.rect, 2, border_radius=6)

        if not hasattr(self, "_txt_cache") or self._txt_cache[0] != self.label:
            self._txt_cache = (self.label, font.render(self.label, True, self.text_color))
        txt = self._txt_cache[1]
        surface.blit(txt, txt.get_rect(center=self.rect.center))


class ColorButton(Button):
    def __init__(self, rect, color_rgb, action):
        super().__init__(rect, "", action, color=color_rgb, text_color=(0, 0, 0))
        self.swatch = color_rgb

    def draw(self, surface, font):
        pygame.draw.rect(surface, self.swatch, self.rect, border_radius=5)
        if self.hovering and self.dwell > 0:
            cx, cy = self.rect.centerx, self.rect.centery
            r = min(self.rect.width, self.rect.height) // 2 - 2
            frac = self.dwell / DWELL_SEC
            pygame.draw.arc(surface, (255, 255, 255), (cx - r, cy - r, r * 2, r * 2), -math.pi / 2, -math.pi / 2 + frac * 2 * math.pi, 3)
        if self.selected:
            pygame.draw.rect(surface, (255, 255, 255), self.rect, 3, border_radius=5)
        else:
            pygame.draw.rect(surface, (100, 100, 100), self.rect, 1, border_radius=5)


# ================= SKELETON =================
_prev_sk = {}


def draw_skeleton(surface, landmarks, label, color=(0, 200, 255)):
    global _prev_sk
    pts = [to_screen(lm) for lm in landmarks]
    if label not in _prev_sk:
        _prev_sk[label] = pts
    smooth = []
    for i, p in enumerate(pts):
        pr = _prev_sk[label][i]
        smooth.append((int(pr[0] * 0.65 + p[0] * 0.35), int(pr[1] * 0.65 + p[1] * 0.35)))
    _prev_sk[label] = smooth
    conns = [
        (0, 1),
        (1, 2),
        (2, 3),
        (3, 4),
        (5, 6),
        (6, 7),
        (7, 8),
        (9, 10),
        (10, 11),
        (11, 12),
        (13, 14),
        (14, 15),
        (15, 16),
        (17, 18),
        (18, 19),
        (19, 20),
        (0, 5),
        (5, 9),
        (9, 13),
        (13, 17),
        (0, 17),
    ]
    for a, b in conns:
        pygame.draw.line(surface, color, smooth[a], smooth[b], 1)
    for p in smooth:
        pygame.draw.circle(surface, (255, 255, 255), p, 2)


# ================= CAMERA THREAD =================
import threading


class CameraThread:
    def __init__(self, src=0):
        self.cap = cv2.VideoCapture(src)
        self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, WINDOW_WIDTH)
        self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, WINDOW_HEIGHT)
        self.cap.set(cv2.CAP_PROP_FPS, 60)

        options = vision.HandLandmarkerOptions(
            base_options=python.BaseOptions(model_asset_path=MODEL_PATH),
            running_mode=vision.RunningMode.VIDEO,
            num_hands=2,
            min_hand_detection_confidence=0.65,
            min_hand_presence_confidence=0.55,
            min_tracking_confidence=0.55,
        )
        self.detector = vision.HandLandmarker.create_from_options(options)

        self.running = True
        self.ret = False
        self.frame = None
        self.result = None
        self.frame_count = 0
        self.lock = threading.Lock()

        self.thread = threading.Thread(target=self._run, daemon=True)
        self.thread.start()

    def _run(self):
        while self.running:
            ret, frame = self.cap.read()
            if not ret:
                continue

            frame = cv2.flip(frame, 1)
            self.frame_count += 1
            small = cv2.resize(frame, (PROCESS_W, PROCESS_H))
            rgb_s = cv2.cvtColor(small, cv2.COLOR_BGR2RGB)
            mp_img = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb_s)
            res = self.detector.detect_for_video(mp_img, self.frame_count)

            with self.lock:
                self.ret = ret
                self.frame = frame
                self.result = res

    def get_data(self):
        with self.lock:
            return self.ret, self.frame, self.result, self.frame_count

    def stop(self):
        self.running = False
        if self.thread.is_alive():
            self.thread.join()
        self.cap.release()
        if hasattr(self, "detector") and self.detector:
            self.detector.close()


# ================= MAIN =================
def main():
    download_model()
    settings = load_settings()

    cam_thread = CameraThread(0)

    pygame.init()
    screen = pygame.display.set_mode((WINDOW_WIDTH, WINDOW_HEIGHT))
    pygame.display.set_caption("✏️  Hand Painter v2")
    clock = pygame.time.Clock()
    font_sm = pygame.font.SysFont("Consolas", 14)
    font_hd = pygame.font.SysFont("Consolas", 16, bold=True)
    font_ti = pygame.font.SysFont("Consolas", 12)

    canvas = pygame.Surface((WINDOW_WIDTH, WINDOW_HEIGHT), pygame.SRCALPHA)

    drawers = {"Left": HandDrawer(), "Right": HandDrawer()}

    brush_size_idx = _clamp_index(settings.get("brush_size_idx", 1), len(BRUSH_SIZES))
    brush_color_idx = _clamp_index(settings.get("brush_color_idx", 0), len(BRUSH_COLORS))
    brush_style_idx = _clamp_index(settings.get("brush_style_idx", 0), len(BRUSH_STYLES) + 1)
    draw_mode_idx = _clamp_index(settings.get("draw_mode_idx", 1), len(DRAW_MODES))
    sym_mode_idx = _clamp_index(settings.get("sym_mode_idx", 0), len(SYMMETRY_MODES))
    glow_enabled = bool(settings.get("glow_enabled", GLOW_ENABLED_DEFAULT))
    show_hud = True
    settings_dirty = False
    session_start = time.time()
    last_diag = ""
    brush_alpha = 255
    export_msg = ""
    export_timer = 0.0

    all_styles = BRUSH_STYLES + ["ERASER"]

    def get_brush():
        _, r, _ = BRUSH_SIZES[brush_size_idx]
        _, col = BRUSH_COLORS[brush_color_idx]
        style = all_styles[brush_style_idx]
        return r, col, style

    def current_settings():
        return {
            "brush_size_idx": brush_size_idx,
            "brush_color_idx": brush_color_idx,
            "brush_style_idx": brush_style_idx,
            "draw_mode_idx": draw_mode_idx,
            "sym_mode_idx": sym_mode_idx,
            "glow_enabled": glow_enabled,
        }

    px_off = 8
    px = PANEL_X + px_off
    bh = 26
    bw = PANEL_W - px_off * 2
    gap = 5
    sec_h = 14
    y = sec_h + 2

    buttons = []
    panel_scroll = 0

    def make_btn(label, action, color=(55, 55, 68), full_width=True, bx_offset=0, bw_override=None):
        nonlocal y
        width = bw_override if bw_override else bw
        b = Button((px + bx_offset, y, width, bh), label, action, color=color)
        buttons.append(b)
        if full_width:
            y += bh + gap
        return b

    section_labels = []

    def sec(text):
        nonlocal y
        section_labels.append((text, y))
        y += sec_h + 2

    sec("MODE  /  SYMMETRY  /  GLOW")

    mode_btn_ref = []

    def toggle_mode():
        nonlocal draw_mode_idx, settings_dirty
        draw_mode_idx = (draw_mode_idx + 1) % len(DRAW_MODES)
        mode_btn_ref[0].label = f"MODE:{DRAW_MODES[draw_mode_idx]}"
        settings_dirty = True

    sym_btn_ref = []

    def toggle_sym():
        nonlocal sym_mode_idx, settings_dirty
        sym_mode_idx = (sym_mode_idx + 1) % len(SYMMETRY_MODES)
        sym_btn_ref[0].label = f"SYM:{SYMMETRY_MODES[sym_mode_idx]}"
        settings_dirty = True

    glow_btn_ref = []

    def toggle_glow():
        nonlocal glow_enabled, settings_dirty
        glow_enabled = not glow_enabled
        glow_btn_ref[0].label = f"GLOW:{'ON' if glow_enabled else 'OFF'}"
        settings_dirty = True

    half_w = (bw - gap) // 2
    mb = make_btn(f"MODE:{DRAW_MODES[draw_mode_idx]}", toggle_mode, (40, 60, 80), full_width=False, bw_override=half_w)
    sb2 = make_btn(
        f"SYM:{SYMMETRY_MODES[sym_mode_idx]}",
        toggle_sym,
        (40, 70, 60),
        full_width=False,
        bx_offset=half_w + gap,
        bw_override=half_w,
    )
    mode_btn_ref.append(mb)
    sym_btn_ref.append(sb2)
    y += bh + gap

    gb = make_btn(f"GLOW:{'ON' if glow_enabled else 'OFF'}", toggle_glow, (60, 40, 80))
    glow_btn_ref.append(gb)

    sec("BRUSH SIZE")
    size_btns = []
    bw_each = (bw - gap * (len(BRUSH_SIZES) - 1)) // len(BRUSH_SIZES)
    for si, (lbl, _r, _o) in enumerate(BRUSH_SIZES):

        def _size_action(i=si):
            nonlocal brush_size_idx, settings_dirty
            brush_size_idx = i
            for k, sb in enumerate(size_btns):
                sb.selected = k == i
            settings_dirty = True

        bx = px + si * (bw_each + gap)
        b = Button((bx, y, bw_each, bh), lbl, _size_action)
        b.selected = si == brush_size_idx
        buttons.append(b)
        size_btns.append(b)
    y += bh + gap

    sec("COLOR")
    color_btns = []
    color_cols = 5
    sw = (bw - gap * (color_cols - 1)) // color_cols
    for ci, (_name, col) in enumerate(BRUSH_COLORS):

        def _col_action(i=ci):
            nonlocal brush_color_idx, settings_dirty
            brush_color_idx = i
            for k, cb in enumerate(color_btns):
                cb.selected = k == i
            settings_dirty = True

        crow = ci // color_cols
        cc = ci % color_cols
        b = ColorButton((px + cc * (sw + gap), y + crow * (sw + gap), sw, sw), col, _col_action)
        b.selected = ci == brush_color_idx
        buttons.append(b)
        color_btns.append(b)
    color_rows = (len(BRUSH_COLORS) - 1) // color_cols + 1
    y += color_rows * (sw + gap)

    sec("STYLE")
    style_btns = []
    style_cols = 2
    sbw = (bw - gap * (style_cols - 1)) // style_cols
    for sti, sty in enumerate(all_styles):

        def _sty_action(i=sti):
            nonlocal brush_style_idx, settings_dirty
            brush_style_idx = i
            for k, stb in enumerate(style_btns):
                stb.selected = k == i
            settings_dirty = True

        row = sti // style_cols
        col = sti % style_cols
        bx = px + col * (sbw + gap)
        by = y + row * (bh + gap)
        btn_col = (80, 40, 40) if sty == "ERASER" else (55, 55, 68)
        b = Button((bx, by, sbw, bh), sty, _sty_action, color=btn_col)
        b.selected = sti == brush_style_idx
        buttons.append(b)
        style_btns.append(b)
    y += ((len(all_styles) - 1) // style_cols + 1) * (bh + gap)

    sec("ACTIONS")
    full_redraw = False

    def do_undo():
        nonlocal full_redraw
        for d in drawers.values():
            d.undo()
        full_redraw = True

    def do_clear():
        nonlocal full_redraw
        canvas.fill((0, 0, 0, 0))
        for d in drawers.values():
            d.reset()
        full_redraw = True

    def do_export():
        nonlocal export_msg, export_timer
        path = export_canvas(canvas)
        export_msg = f"Saved: {path}"
        export_timer = 3.0

    act_w = (bw - gap * 2) // 3
    undo_b = Button((px, y, act_w, bh), "UNDO[Z]", do_undo, (70, 50, 50))
    clr_b = Button((px + act_w + gap, y, act_w, bh), "CLR[C]", do_clear, (90, 30, 30))
    exp_b = Button((px + (act_w + gap) * 2, y, act_w, bh), "EXP[E]", do_export, (30, 80, 60))
    buttons += [undo_b, clr_b, exp_b]
    y += bh + gap

    virtual_h = y + 10
    scroll_area_h = WINDOW_HEIGHT - PANEL_BOTTOM_RESERVE
    max_scroll = max(0, virtual_h - scroll_area_h)

    panel_surf = pygame.Surface((PANEL_W, WINDOW_HEIGHT), pygame.SRCALPHA)

    ui_bg = pygame.Surface((PANEL_W, WINDOW_HEIGHT), pygame.SRCALPHA)
    ui_bg.fill((20, 20, 30, 210))
    pygame.draw.line(ui_bg, (80, 80, 100, 200), (0, 0), (0, WINDOW_HEIGHT), 2)

    dark_overlay = pygame.Surface((WINDOW_WIDTH, WINDOW_HEIGHT))
    dark_overlay.set_alpha(120)
    dark_overlay.fill((0, 0, 0))

    _label_cache = {}

    last_frame_count = -1
    finger_tip = None
    cursor_pinch = False
    hand_in_panel = False

    running = True
    while running:
        dt = min(clock.tick(FPS) / 1000.0, 0.05)

        if export_timer > 0:
            export_timer -= dt

        for e in pygame.event.get():
            if e.type == pygame.QUIT:
                if settings_dirty:
                    save_settings(current_settings())
                running = False
            if e.type == pygame.KEYDOWN:
                if e.key == pygame.K_c:
                    do_clear()
                if e.key == pygame.K_z:
                    do_undo()
                if e.key == pygame.K_e:
                    do_export()
                if e.key == pygame.K_g:
                    toggle_glow()
                if e.key == pygame.K_x:
                    toggle_sym()
                if e.key == pygame.K_s:
                    draw_mode_idx = (draw_mode_idx + 1) % len(DRAW_MODES)
                    mode_btn_ref[0].label = f"MODE:{DRAW_MODES[draw_mode_idx]}"
                    settings_dirty = True
                if e.key == pygame.K_LEFTBRACKET:
                    brush_size_idx = max(0, brush_size_idx - 1)
                    for k, sb in enumerate(size_btns):
                        sb.selected = k == brush_size_idx
                    settings_dirty = True
                if e.key == pygame.K_RIGHTBRACKET:
                    brush_size_idx = min(len(BRUSH_SIZES) - 1, brush_size_idx + 1)
                    for k, sb in enumerate(size_btns):
                        sb.selected = k == brush_size_idx
                    settings_dirty = True
                if e.key == pygame.K_h:
                    show_hud = not show_hud
                if e.key == pygame.K_F5:
                    save_settings(current_settings())
                    settings_dirty = False
                    export_msg = f"Settings saved: {SETTINGS_PATH}"
                    export_timer = 2.5
                if e.key == pygame.K_F9:
                    diag_payload = {
                        "uptime_sec": round(time.time() - session_start, 2),
                        "fps": round(clock.get_fps(), 2),
                        "cache": {"shape": len(_shape_cache), "chalk": len(_chalk_cache)},
                        "strokes": {label: len(d.strokes) for label, d in drawers.items()},
                        "mode": DRAW_MODES[draw_mode_idx],
                        "symmetry": SYMMETRY_MODES[sym_mode_idx],
                        "glow_enabled": glow_enabled,
                        "settings_path": SETTINGS_PATH,
                    }
                    try:
                        last_diag = export_diagnostics(diag_payload)
                        export_msg = f"Diagnostics: {last_diag}"
                    except Exception as exc:
                        export_msg = f"Diag export failed: {exc}"
                    export_timer = 3.0
            if e.type == pygame.MOUSEWHEEL:
                if pygame.mouse.get_pos()[0] >= PANEL_X:
                    panel_scroll = max(0, min(max_scroll, panel_scroll - e.y * PANEL_SCROLL_SPEED))
            if e.type == pygame.MOUSEBUTTONDOWN and e.button == 1:
                if not getattr(sys.modules[__name__], "_ui_hidden", False):
                    mx, my = e.pos
                    if mx >= PANEL_X and my < WINDOW_HEIGHT - PANEL_BOTTOM_RESERVE:
                        scrolled_pos = (mx, my + panel_scroll)
                        for btn in buttons:
                            if btn.rect.collidepoint(scrolled_pos):
                                btn.action()
                    elif mx >= PANEL_X:
                        for btn in buttons:
                            if btn.rect.collidepoint(e.pos):
                                btn.action()

        ret, frame, result, frame_count = cam_thread.get_data()
        if not ret or frame is None:
            continue

        is_new_frame = frame_count != last_frame_count
        last_frame_count = frame_count

        landmarks_all = result.hand_landmarks if result else []
        handedness = result.handedness if result else []

        mode = DRAW_MODES[draw_mode_idx]
        br, bcol, bsty = get_brush()
        sym_mode = SYMMETRY_MODES[sym_mode_idx]

        if is_new_frame:
            seen_labels = set()
            new_finger_tip = None
            new_cursor_pinch = False
            hand_in_panel = False

            for i, lms in enumerate(landmarks_all):
                if i >= len(handedness):
                    continue
                label = handedness[i][0].category_name
                score = handedness[i][0].score
                if score < 0.55:
                    continue

                seen_labels.add(label)
                drawer = drawers[label]
                drawer.frames_unseen = 0

                tip = to_screen(lms[8])
                wrist = to_screen(lms[0])
                pinch = detect_pinch(lms, drawer.last_pinch)
                drawer.last_pinch = pinch

                spread = detect_spread(lms)
                brush_alpha = int(60 + spread * 195)

                if tip[0] >= PANEL_X:
                    hand_in_panel = True
                    new_finger_tip = tip
                    new_cursor_pinch = pinch
                elif new_finger_tip is None:
                    new_finger_tip = tip
                    new_cursor_pinch = pinch

                drawing = pinch if mode == "PINCH" else True

                if tip[0] >= PANEL_X:
                    drawing = False

                if not pinch:
                    swipe_dir = drawer.update_swipe(wrist)
                    if swipe_dir == "UP":
                        do_clear()
                        drawing = False
                    elif swipe_dir == "LEFT":
                        do_undo()
                        drawing = False
                else:
                    drawer.prev_wrist = None
                    drawer.swipe_vel_buffer.clear()

                drawer.update(tip, drawing, br, bcol, bsty, brush_alpha, sym_mode)

            finger_tip = new_finger_tip
            cursor_pinch = new_cursor_pinch
            for label, drawer in drawers.items():
                if label not in seen_labels:
                    drawer.on_lost()

        any_drawing = False
        for d in drawers.values():
            if d.current is not None or d.was_drawing:
                any_drawing = True
                break

        ui_hidden = any_drawing and not hand_in_panel
        setattr(sys.modules[__name__], "_ui_hidden", ui_hidden)

        if not ui_hidden:
            scrolled_finger = None
            if finger_tip:
                scrolled_finger = (finger_tip[0], finger_tip[1] + panel_scroll)
            for btn in buttons:
                if btn.update_state(scrolled_finger, cursor_pinch, dt):
                    btn.action()
        else:
            for btn in buttons:
                btn.hovering = False
                btn.dwell = 0.0
                btn.last_pinch = False

        if full_redraw:
            canvas.fill((0, 0, 0, 0))
            for d in drawers.values():
                d.redraw_all(canvas, glow_enabled)
            full_redraw = False
        else:
            for d in drawers.values():
                d.draw_incremental(canvas, glow_enabled)

        if landmarks_all:
            screen.fill((10, 10, 14))
        else:
            rgb_full = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            cam_surf = pygame.image.frombuffer(rgb_full.tobytes(), (WINDOW_WIDTH, WINDOW_HEIGHT), "RGB")
            screen.blit(cam_surf, (0, 0))
            screen.blit(dark_overlay, (0, 0))

        screen.blit(canvas, (0, 0))

        if sym_mode != "NONE" and not ui_hidden:
            cx, cy = WINDOW_WIDTH // 2, WINDOW_HEIGHT // 2
            guide_col = (60, 60, 80)
            if sym_mode in ("VERTICAL", "QUAD"):
                pygame.draw.line(screen, guide_col, (cx, 0), (cx, WINDOW_HEIGHT), 1)
            if sym_mode in ("HORIZONTAL", "QUAD"):
                pygame.draw.line(screen, guide_col, (0, cy), (PANEL_X, cy), 1)

        sk_colors = {"Left": (0, 220, 255), "Right": (220, 0, 255)}
        for i, lm in enumerate(landmarks_all):
            if i < len(handedness):
                label = handedness[i][0].category_name
                draw_skeleton(screen, lm, label, sk_colors.get(label, (255, 255, 255)))

        ui_hidden = getattr(sys.modules[__name__], "_ui_hidden", False)
        if not ui_hidden:
            if finger_tip and finger_tip[0] >= PANEL_X:
                pygame.draw.circle(screen, (255, 220, 80), finger_tip, 10, 2)
                pygame.draw.circle(screen, (255, 255, 255), finger_tip, 3)

            panel_surf.fill((0, 0, 0, 0))
            panel_surf.blit(ui_bg, (0, 0))

            scroll_area_h = WINDOW_HEIGHT - PANEL_BOTTOM_RESERVE
            scroll_clip = pygame.Rect(0, 0, PANEL_W, scroll_area_h)
            panel_surf.set_clip(scroll_clip)

            for sec_text, sec_wy in section_labels:
                ly = sec_wy - panel_scroll
                if -sec_h <= ly < scroll_area_h:
                    if sec_text not in _label_cache:
                        _label_cache[sec_text] = font_ti.render(sec_text, True, (160, 160, 190))
                    panel_surf.blit(_label_cache[sec_text], (px_off, ly))

            for btn in buttons:
                local_x = btn.rect.x - PANEL_X
                local_y = btn.rect.y - panel_scroll
                if local_y + btn.rect.height < 0 or local_y >= scroll_area_h:
                    continue
                orig_rect = btn.rect
                btn.rect = pygame.Rect(local_x, local_y, btn.rect.width, btn.rect.height)
                btn.draw(panel_surf, font_sm)
                btn.rect = orig_rect

            if max_scroll > 0:
                bar_total = scroll_area_h
                bar_h = max(20, int(bar_total * scroll_area_h / virtual_h))
                bar_y = int((panel_scroll / max_scroll) * (bar_total - bar_h))
                pygame.draw.rect(panel_surf, (60, 60, 80), (PANEL_W - 5, 0, 4, scroll_area_h), border_radius=2)
                pygame.draw.rect(panel_surf, (140, 140, 180), (PANEL_W - 5, bar_y, 4, bar_h), border_radius=2)

            panel_surf.set_clip(None)

            sep_y = WINDOW_HEIGHT - PANEL_BOTTOM_RESERVE
            pygame.draw.line(panel_surf, (70, 70, 100), (0, sep_y), (PANEL_W, sep_y), 1)

            opa_label = "OPACITY"
            if opa_label not in _label_cache:
                _label_cache[opa_label] = font_ti.render("OPACITY (spread fingers)", True, (160, 160, 190))
            panel_surf.blit(_label_cache[opa_label], (px_off, sep_y + 5))
            bar_y2 = sep_y + 20
            bar_w2 = int(bw * (brush_alpha / 255))
            pygame.draw.rect(panel_surf, (40, 40, 60), (px_off, bar_y2, bw, 8), border_radius=3)
            pygame.draw.rect(panel_surf, (140, 160, 255), (px_off, bar_y2, bar_w2, 8), border_radius=3)

            _, pr, _ = BRUSH_SIZES[brush_size_idx]
            _, pcol = BRUSH_COLORS[brush_color_idx]
            prev_cx = PANEL_W // 2
            prev_cy = sep_y + 55
            pygame.draw.circle(panel_surf, (35, 35, 55), (prev_cx, prev_cy), pr + 5)
            preview_col = (*pcol[:3], brush_alpha)
            pygame.draw.circle(panel_surf, preview_col, (prev_cx, prev_cy), pr)
            if "PREVIEW" not in _label_cache:
                _label_cache["PREVIEW"] = font_ti.render("PREVIEW", True, (160, 160, 190))
            panel_surf.blit(
                _label_cache["PREVIEW"],
                (prev_cx - _label_cache["PREVIEW"].get_width() // 2, sep_y + 33),
            )

            screen.blit(panel_surf, (PANEL_X, 0))

            if show_hud:
                fps = int(clock.get_fps())
                sn = BRUSH_SIZES[brush_size_idx][0]
                hud = font_hd.render(
                    f"FPS:{fps}  |  {mode}  |  Size:{sn}"
                    f"  |  Style:{all_styles[brush_style_idx]}"
                    f"  |  Sym:{SYMMETRY_MODES[sym_mode_idx]}"
                    f"  |  Glow:{'ON' if glow_enabled else 'OFF'}"
                    f"  |  [E]Export [G]Glow [X]Sym [Z]Undo [C]Clear [S]Mode [F5]Save [F9]Diag [H]HUD",
                    True,
                    (200, 200, 200),
                )
                pygame.draw.rect(screen, (0, 0, 0, 160), (0, 0, hud.get_width() + 20, 26))
                screen.blit(hud, (10, 5))

        if export_timer > 0 and export_msg:
            msg_surf = font_hd.render(export_msg, True, (80, 255, 140))
            mx = WINDOW_WIDTH // 2 - msg_surf.get_width() // 2
            pygame.draw.rect(screen, (10, 30, 20, 200), (mx - 10, WINDOW_HEIGHT - 50, msg_surf.get_width() + 20, 34))
            screen.blit(msg_surf, (mx, WINDOW_HEIGHT - 44))

        pygame.display.flip()

    cam_thread.stop()
    if settings_dirty:
        save_settings(current_settings())
    pygame.quit()


if __name__ == "__main__":
    main()

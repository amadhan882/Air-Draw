# Air-Draw v.1.0.0

![Python](https://img.shields.io/badge/Python-3.8%2B-blue?style=flat-square&logo=python&logoColor=white)
![MediaPipe](https://img.shields.io/badge/MediaPipe-Hand%20Landmarker-orange?style=flat-square)
![Pygame](https://img.shields.io/badge/Pygame-2.x-green?style=flat-square)
![OpenCV](https://img.shields.io/badge/OpenCV-4.x-red?style=flat-square&logo=opencv&logoColor=white)
![License](https://img.shields.io/badge/License-MIT-lightgrey?style=flat-square)
![Platform](https://img.shields.io/badge/Platform-Windows%20%7C%20macOS%20%7C%20Linux-informational?style=flat-square)
![Author](https://img.shields.io/badge/Author-Madhan%20Alagarsamy-blueviolet?style=flat-square&logo=github)

A real-time, camera-based hand-tracking drawing application built with MediaPipe, OpenCV, and Pygame. Draw on a virtual canvas using nothing but your hands — no stylus, no mouse, no touch screen required.

---

## Table of Contents

- [Overview](#overview)
- [Features](#features)
- [Requirements](#requirements)
- [Installation](#installation)
- [Usage](#usage)
- [Controls](#controls)
- [Brush System](#brush-system)
- [Gesture Reference](#gesture-reference)
- [Architecture](#architecture)
- [Configuration](#configuration)
- [Known Limitations](#known-limitations)
- [Author](#author)
- [License](#license)

---

## Overview

Hand Painter uses the MediaPipe Hand Landmarker model to track 21 landmarks on each detected hand in real time. Finger positions are mapped to canvas coordinates, enabling freehand drawing through either a continuous-trace mode or a pinch-to-draw mode. The application runs entirely locally — no cloud inference, no network dependency beyond the initial model download.

---

## Features

- **Dual-hand support** — left and right hands tracked independently with separate drawing states
- **18 brush styles** — Normal, Chalk, Heart, Star, Square, Diamond, Triangle, Cross, Hexagon, Pentagon, Bubble, Dots, Outline, Sparkle, Cloud, Leaf, Flower, Raindrop, plus a dedicated Eraser
- **10-color palette** — Green, Cyan, Pink, Gold, White, Red, Orange, Purple, Sky, Lime
- **4 brush sizes** — XS / S / M / L
- **Symmetry modes** — None, Vertical, Horizontal, Quad (mirror drawing across axes)
- **Glow / bloom effect** — soft luminance bloom layered under normal strokes
- **Opacity control** — finger spread distance maps to stroke alpha (60–255)
- **Pinch or continuous draw mode** — toggle between pinch-to-activate and always-on tracing
- **Undo and clear** — per-stroke undo stack (up to 300 strokes) and full canvas clear
- **PNG export** — saves canvas with a dark background to a timestamped file
- **Swipe gestures** — swipe up to clear, swipe left to undo (open-hand gestures)
- **Scrollable UI panel** — all controls accessible via finger hover dwell or pinch-click
- **Threaded camera capture** — camera runs in a background thread to maintain high render FPS
- **Smooth tracking** — weighted exponential moving average with velocity-cap filtering

---

## Requirements

| Dependency | Minimum Version | Tested Version |
|---|---|---|
| Python | 3.8 or later | 3.13.5 |
| mediapipe | 0.10.x | 0.10.33 |
| opencv-python | 4.x | 4.13.0.92 |
| pygame | 2.x | 2.6.1 |

A webcam capable of at least 720p is recommended. The application internally processes frames at 640x360 for hand detection and renders at 1280x720.

### Tested Environment

This project has been verified on the following setup:

| Property | Value |
|---|---|
| OS | Windows 11 |
| Python | 3.13.5 |
| mediapipe | 0.10.33 |
| opencv-python | 4.13.0.92 |
| pygame | 2.6.1 |

> **Note:** mediapipe 0.10.33 automatically installs `opencv-contrib-python` as a dependency. If you already have `opencv-python` installed, both can coexist without conflict.

---

## Installation

**1. Clone the repository**

```bash
git clone https://github.com/amadhan82/Air-Draw.git
cd Air-Draw
```

**2. Create and activate a virtual environment (recommended)**

```bash
python -m venv venv

# Windows
venv\Scripts\activate

# macOS / Linux
source venv/bin/activate
```

**3. Install dependencies**

```bash
pip install mediapipe opencv-python pygame
```

**4. Run the application**

```bash
python hand_painter.py
```

On first launch, the MediaPipe hand landmark model (`hand_landmarker.task`, ~29 MB) is downloaded automatically from Google's model storage and saved alongside the script. Subsequent launches use the cached file.

---

## Usage

1. Position yourself so your hand(s) are visible to the webcam within the frame.
2. The right panel displays all brush controls. Hover your index finger over a button for approximately 0.7 seconds to activate it, or perform a pinch gesture while hovering.
3. Keep your hand in the left portion of the screen (away from the panel) to draw.
4. The panel auto-hides while you are actively drawing and your hand is not near it.

---

## Controls

### Keyboard Shortcuts

| Key | Action |
|---|---|
| `Z` | Undo last stroke |
| `C` | Clear canvas |
| `E` | Export canvas to PNG |
| `G` | Toggle glow effect |
| `X` | Cycle symmetry mode |
| `S` | Toggle draw mode (Continuous / Pinch) |
| `[` | Decrease brush size |
| `]` | Increase brush size |

---

## Brush System

### Sizes

| Label | Draw Radius |
|---|---|
| XS | 2 px |
| S | 4 px |
| M | 8 px |
| L | 14 px |

### Styles

Styles are stamped along the stroke path at regular intervals. Shape stamps are cached by `(style, radius, color)` to avoid redundant surface allocation.

- **NORMAL** — anti-aliased multi-layer line with optional glow bloom
- **CHALK** — randomized particle scatter simulating chalk texture
- **ERASER** — alpha-channel eraser using `BLEND_RGBA_MIN` composite
- **Shape styles** (HEART, STAR, SQUARE, DIAMOND, TRIANGLE, CROSS, HEXAGON, PENTAGON, BUBBLE, DOTS, OUTLINE, SPARKLE, CLOUD, LEAF, FLOWER, RAINDROP) — pre-rendered polygon/circle stamp blitted along the path

### Symmetry Modes

| Mode | Behaviour |
|---|---|
| NONE | Normal single-line drawing |
| VERTICAL | Mirrors strokes across the vertical centre axis |
| HORIZONTAL | Mirrors strokes across the horizontal centre axis |
| QUAD | Mirrors across both axes simultaneously (4 copies) |

Guide lines are drawn on-screen when a symmetry mode is active.

### Opacity

Spread your fingers apart (measure between index tip and pinky tip) to increase opacity. A closed-finger pose produces approximately 60 alpha; a fully open hand produces 255. The current opacity is visualised by the bar at the bottom of the panel and the preview circle.

---

## Gesture Reference

| Gesture | Action |
|---|---|
| Index fingertip position | Cursor / draw position |
| Pinch (thumb + index) | Draw (in Pinch mode) / activate UI button |
| Finger hover over button (0.7 s) | Activate UI button |
| Open-hand swipe up | Clear canvas |
| Open-hand swipe left | Undo last stroke |
| Finger spread width | Controls stroke opacity |

Swipe detection uses a 5-frame velocity buffer on the wrist landmark. A swipe is registered when average speed exceeds 40 px/frame with a dominant directional component greater than 25 px/frame.

---

## Architecture

```
hand_painter.py
├── CameraThread          — Background thread: capture, resize, MediaPipe inference
├── SmoothTracker         — Exponential moving average + circular buffer for finger smoothing
├── HandDrawer            — Stroke state machine, incremental and full redraw, swipe detection
│   └── _render_segment   — Per-segment renderer dispatching to shape/chalk/normal paths
├── Button / ColorButton  — UI widget with dwell timer, pinch-click, and selection state
├── Shape cache           — LRU-style dict keyed on (style, radius, color)
├── Chalk cache           — Per-(color, alpha) dot surface
└── main()                — Event loop, camera data polling, canvas compositing, UI layout
```

**Rendering pipeline per frame:**

1. Camera thread produces the latest frame and MediaPipe result under a lock.
2. Main thread reads landmark data, updates each `HandDrawer`, and appends new points.
3. `draw_incremental` renders only newly added stroke segments onto the persistent `canvas` surface.
4. On undo or clear, `redraw_all` repaints the entire canvas from the stroke deque.
5. The camera image (or solid background when hands are detected), canvas, symmetry guides, skeleton overlay, and UI panel are composited onto the screen surface in order.

---

## Configuration

All tunable constants are declared at the top of `hand_painter.py` under the `CONFIG` block.

| Constant | Default | Description |
|---|---|---|
| `WINDOW_WIDTH` / `WINDOW_HEIGHT` | 1280 / 720 | Render resolution |
| `PROCESS_W` / `PROCESS_H` | 640 / 360 | Hand detection resolution |
| `FPS` | 120 | Target frame rate cap |
| `MAX_STROKES` | 300 | Maximum strokes retained in undo history |
| `MAX_PTS` | 600 | Maximum points per stroke |
| `MIN_MOVE` | 1.5 px | Minimum cursor movement to append a point |
| `MAX_JUMP` | 250 px | Maximum inter-frame jump before the point is discarded |
| `PINCH_ON` | 0.042 | Normalised distance threshold to enter pinch state |
| `PINCH_OFF` | 0.062 | Normalised distance threshold to exit pinch state |
| `DWELL_SEC` | 0.7 s | Hover duration required to trigger a UI button |
| `PANEL_W` | 220 px | Width of the right-side control panel |
| `GLOW_ENABLED_DEFAULT` | True | Initial glow state on launch |
| `SHAPE_CACHE_MAX` / `CHALK_CACHE_MAX` | 512 / 256 | Upper bounds for runtime shape/chalk caches |
| `MODEL_DOWNLOAD_TIMEOUT_SEC` | 30 | Timeout used per model download attempt |
| `MODEL_DOWNLOAD_RETRIES` | 3 | Retry count for model download failures |

---

### Environment Overrides

You can override selected production settings via environment variables:

- `AIR_DRAW_LOG_LEVEL` — logging level (`DEBUG`, `INFO`, `WARNING`, ...)
- `AIR_DRAW_MODEL_SHA256` — expected SHA-256 hash of `hand_landmarker.task` for integrity validation

---

## Known Limitations

- Detection confidence degrades under poor lighting or against backgrounds with skin-tone colours.
- Chalk style uses `random.randint` per segment step; at large brush sizes and high speed this can cause brief CPU spikes.
- Shape/chalk cache limits are now bounded, but very high limits may still increase memory usage.
- Swipe gestures may misfire if the drawing hand moves quickly across the canvas near the panel boundary.
- Export saves at the render resolution (1280x720) regardless of display DPI.

---

## Author

- Developed by **Madhan Alagarsamy**
- Security Researcher
- GitHub: [https://github.com/amadhan82](https://github.com/amadhan82)

---

## License

- This project is released under the MIT License. See [LICENSE](LICENSE) for details.
- MediaPipe is developed by Google and is subject to the [Apache 2.0 License](https://github.com/google-ai-edge/mediapipe/blob/master/LICENSE).

# Air-Draw Hand Painter

[![Python](https://img.shields.io/badge/Python-Required-blue)](https://www.python.org/)
[![MediaPipe](https://img.shields.io/badge/MediaPipe-Hands-success)](https://ai.google.dev/edge/mediapipe)
[![Pygame](https://img.shields.io/badge/Pygame-Rendering-success)](https://www.pygame.org/)
[![OpenCV](https://img.shields.io/badge/OpenCV-Camera-success)](https://opencv.org/)

A single-file hand-tracking drawing app built with MediaPipe, OpenCV, and Pygame.

This README only documents behavior that is present in `hand_painter.py`.

## What the code does

- Opens a webcam feed and mirrors frames horizontally.
- Runs MediaPipe `HandLandmarker` in `VIDEO` mode on a background thread.
- Tracks up to 2 hands and uses handedness labels (`Left`, `Right`) to manage separate stroke state.
- Draws to a transparent Pygame canvas layered over a dimmed camera/background view.
- Supports drawing in two modes:
  - `CONTINUOUS`
  - `PINCH`

## Confirmed feature set from code

### Brush system

- Sizes: `XS`, `S`, `M`, `L`
- Colors: 10 presets (`Green`, `Cyan`, `Pink`, `Gold`, `White`, `Red`, `Orange`, `Purple`, `Sky`, `Lime`)
- Styles:
  - `NORMAL`
  - `CHALK`
  - `HEART`, `STAR`, `SQUARE`, `DIAMOND`, `TRIANGLE`, `CROSS`, `HEXAGON`, `PENTAGON`, `BUBBLE`, `DOTS`, `OUTLINE`, `SPARKLE`, `CLOUD`, `LEAF`, `FLOWER`, `RAINDROP`
  - `ERASER` (added at runtime)

### Interaction and gestures

- Pinch detection between thumb tip (`4`) and index tip (`8`) with hysteresis thresholds.
- Finger spread (index tip `8` to pinky tip `20`) controls brush alpha in the range `60..255`.
- Swipe gestures while hand is open:
  - Up swipe: clear
  - Left swipe: undo

### Symmetry and effects

- Symmetry modes:
  - `NONE`
  - `VERTICAL`
  - `HORIZONTAL`
  - `QUAD`
- Optional glow effect toggle (`GLOW:ON/OFF`).

### UI panel behavior

- Right-side panel with sections:
  - Mode / Symmetry / Glow
  - Brush size
  - Color
  - Style
  - Actions (`UNDO`, `CLR`, `EXP`)
- Panel supports:
  - Hover dwell activation
  - Pinch-click activation
  - Mouse wheel scroll in panel area
  - Mouse click activation
- Panel is automatically hidden while drawing outside the panel area.

### Export

- Export action saves a PNG with timestamp format:
  - `handpainter_YYYYMMDD_HHMMSS.png`
- Exported image is composited on a dark background `(15, 15, 20)` before saving.

## Keyboard controls (from code)

- `C` clear canvas
- `Z` undo last stroke
- `E` export PNG
- `G` toggle glow
- `X` cycle symmetry mode
- `S` cycle draw mode
- `[` decrease brush size
- `]` increase brush size

## Requirements

The script imports and uses:

- `opencv-python` (`cv2`)
- `mediapipe`
- `pygame`

It also uses Python standard library modules:

- `os`, `sys`, `math`, `datetime`, `threading`, `urllib.request`, `collections.deque`

## Setup

1. Create and activate a virtual environment.
2. Install required packages:

```bash
pip install opencv-python mediapipe pygame
```

3. Run:

```bash
python hand_painter.py
```

On first run, the script downloads the hand landmarker model to:

- `hand_landmarker.task`

## File layout

```text
.
├── hand_painter.py
└── README.md
```

## Notes

- The current implementation is monolithic in one Python file.
- No automated test suite is included in this repository.
- This repository currently does not include a `LICENSE` file.

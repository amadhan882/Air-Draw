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


## Table of Contents

- [Overview](#overview)
- [Feature Highlights](#feature-highlights)
- [Architecture](#architecture)
- [Project Structure](#project-structure)
- [Requirements](#requirements)
- [Installation](#installation)
- [Quick Start](#quick-start)
- [Controls](#controls)
- [Brush and Rendering System](#brush-and-rendering-system)
- [Performance Notes](#performance-notes)
- [Configuration Reference](#configuration-reference)
- [Export and Output](#export-and-output)
- [Troubleshooting](#troubleshooting)
- [Security and Privacy](#security-and-privacy)
- [Roadmap](#roadmap)
- [Contributing](#contributing)
- [License](#license)

## Overview

This project captures live webcam frames, detects hand landmarks with MediaPipe, then converts recognized hand gestures into drawing actions on a transparent canvas in Pygame.

Core interaction concepts:

- Draw continuously or only while pinching.
- Select colors, brush sizes, and style stamps from an on-screen panel.
- Toggle symmetry and glow effects for stylized artwork.
- Use hover dwell or pinch-click in air to activate UI controls.
- Save generated art as timestamped PNG files.

## Feature Highlights

### Input and Tracking

- Real-time hand tracking using `vision.HandLandmarker`.
- Two-hand support with handedness awareness.
- Smoothing pipeline (`SmoothTracker`) to reduce cursor jitter.
- Pinch detection hysteresis (`PINCH_ON` / `PINCH_OFF`) for stability.
- Swipe gesture shortcuts:
  - Swipe up: clear canvas
  - Swipe left: undo

### Drawing and Effects

- Drawing modes:
  - `CONTINUOUS`
  - `PINCH`
- Brush sizes: `XS`, `S`, `M`, `L`.
- Expanded color palette.
- Rich style set including shape stamps and eraser mode.
- Symmetry modes: `NONE`, `VERTICAL`, `HORIZONTAL`, `QUAD`.
- Optional glow effect for bright strokes.
- Opacity linked to finger spread.

### User Interface

- Scrollable control panel with sections for:
  - Mode / symmetry / glow
  - Brush size
  - Color swatches
  - Style selection
  - Actions (undo, clear, export)
- Air interaction support:
  - Hover dwell activation
  - Pinch-to-click activation
- Keyboard shortcuts for fast operation.

## Architecture

High-level runtime flow:

1. `download_model()` ensures the hand landmarker model exists locally.
2. `CameraThread` continuously captures camera frames and runs MediaPipe inference in the background.
3. Main Pygame loop:
   - Consumes latest frame + hand landmarks.
   - Converts landmarks to pointer positions and gesture states.
   - Updates per-hand `HandDrawer` state.
   - Renders incremental stroke updates to the canvas.
   - Draws UI panel and live HUD.

Primary components:

- `CameraThread`: non-blocking acquisition + inference.
- `SmoothTracker`: weighted moving average smoothing.
- `HandDrawer`: gesture-to-stroke state machine and rendering pipeline.
- `Button` / `ColorButton`: panel interaction primitives.

## Project Structure

```text
.
├── hand_painter.py   # Main application entry point and all runtime logic
└── README.md         # Project documentation
```

## Requirements

- Python 3.9 or newer
- Webcam (USB or integrated)
- Operating system with graphics support for Pygame

Python packages:

- `opencv-python`
- `mediapipe`
- `pygame`

## Installation

1. Clone the repository:

```bash
git clone https://github.com/amadhan882/Air-Draw.git
cd Air-Draw
```

2. Create and activate a virtual environment:

```bash
python -m venv .venv
source .venv/bin/activate
```

3. Install dependencies:

```bash
pip install --upgrade pip
pip install opencv-python mediapipe pygame
```

## Quick Start

Run the application:

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
On first launch, the MediaPipe hand landmarker model is downloaded automatically and stored as:

```text
hand_landmarker.task
```

## Controls

### Keyboard Shortcuts

- `C`: clear canvas
- `Z`: undo last stroke
- `E`: export canvas as PNG
- `G`: toggle glow
- `X`: cycle symmetry mode
- `S`: cycle draw mode
- `[` / `]`: decrease / increase brush size
- Window close button: exit application

### Air UI Interaction

- Move index fingertip over panel controls.
- Trigger control via either:
  - Dwell (hover for configured delay), or
  - Pinch click while hovering.

## Brush and Rendering System

The renderer supports two broad categories:

1. Line-based rendering:
   - `NORMAL`: multi-pass edge/mid/core stroke layering
   - `CHALK`: randomized textured dots for grain

2. Stamp-based rendering:
   - Shape stamps such as heart, star, diamond, triangle, hexagon, pentagon, cloud, leaf, flower, and raindrop
   - Cached in `_shape_cache` for reuse and reduced draw overhead

Additional behavior:

- Eraser mode removes pixels from the alpha canvas.
- Glow mode composites translucent bloom layers around bright strokes.
- Symmetry mode mirrors stroke segments based on the selected axis mode.

## Performance Notes

- Inference runs on resized frames (`PROCESS_W`, `PROCESS_H`) to balance speed and quality.
- Rendering is incremental by default; full redraw only occurs when required (undo/clear).
- Frequently reused visual assets are cached:
  - Shape stamps in `_shape_cache`
  - Chalk dots in `_chalk_cache`
  - UI text labels in `_label_cache`

## Configuration Reference

You can tune behavior by editing constants near the top of `hand_painter.py`:

- Window and frame settings:
  - `WINDOW_WIDTH`, `WINDOW_HEIGHT`, `FPS`
  - `PROCESS_W`, `PROCESS_H`
- Gesture thresholds:
  - `PINCH_ON`, `PINCH_OFF`
  - `MIN_MOVE`, `MAX_JUMP`
- UI timing and layout:
  - `DWELL_SEC`
  - `PANEL_W`, `PANEL_BOTTOM_RESERVE`, `PANEL_SCROLL_SPEED`
- Feature toggles:
  - `GLOW_ENABLED_DEFAULT`

## Export and Output

- Export action writes a timestamped PNG named:

```text
handpainter_YYYYMMDD_HHMMSS.png
```

- Exported images are generated on a dark background for good visual contrast outside the app.

## Troubleshooting

### Camera not detected

- Confirm no other application is locking the webcam.
- Try reconnecting camera hardware.
- On Linux, validate permissions for video devices.

### Low FPS or lag

- Reduce processing resolution (`PROCESS_W`, `PROCESS_H`).
- Disable glow to reduce overdraw cost.
- Close other GPU/CPU intensive applications.

### Hand tracking unstable

- Improve front lighting and reduce background clutter.
- Keep hand centered and within camera field of view.
- Raise confidence thresholds only if needed after testing.

### Dependency install issues

- Ensure `pip` is up to date.
- Use a clean virtual environment.
- Verify Python version compatibility with installed package releases.

## Security and Privacy

- The application processes camera frames locally.
- No telemetry or remote frame upload is implemented in this codebase.
- The model file is downloaded from Google Cloud Storage on first run.

## Roadmap

Potential future improvements:

- Modularize code into multiple files (`ui`, `render`, `tracking`, `config`).
- Add configuration file support (YAML or TOML).
- Add unit tests for gesture logic and geometry utilities.
- Add packaging metadata and CLI launch options.
- Add recording or time-lapse export.

## Contributing

1. Fork the project and create a feature branch.
2. Make your changes with clear commit messages.
3. Run static checks and local validation.
4. Open a pull request with a concise problem/solution summary.

## License

This repository is available under the MIT License.

If you intend to use a different license, replace this section and add a dedicated `LICENSE` file.

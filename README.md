# Intel RealSense + ArUco Marker Pose Estimation

Detect ArUco markers in real-time from an Intel RealSense camera stream,
estimate each marker's 6-DoF pose (rotation + translation), and overlay
3D axes directly on the video.

```
┌──────────────────────────────────────┐
│  [RGB video]                         │
│                                      │
│      ┌───────┐    ┌───────┐          │
│      │ ArUco │    │ ArUco │          │
│      │  #3   │───►│  #7   │          │
│      └───────┘    └───────┘          │
│         ↑ X,Y,Z axes                 │
└──────────────────────────────────────┘
```

---

## Table of Contents

1. [Prerequisites](#1-prerequisites)
2. [Step 1 — Install Librealsense SDK](#step-1--install-librealsense-sdk)
3. [Step 2 — Install Python Dependencies](#step-2--install-python-dependencies)
4. [Step 3 — Print ArUco Markers](#step-3--print-aruco-markers)
5. [Step 4 — Run the Application](#step-4--run-the-application)
6. [CLI Reference](#cli-reference)
7. [Camera Calibration (Optional but Recommended)](#camera-calibration-optional-but-recommended)
8. [Troubleshooting](#troubleshooting)
9. [How It Works](#how-it-works)

---

## 1. Prerequisites

| Item | Required |
|------|----------|
| Intel RealSense camera (D415, D435, D435i, D455, etc.) | Yes |
| Python ≥ 3.8 | Yes |
| Ubuntu / Debian Linux (or WSL2 on Windows) | Recommended |
| USB 3.0 port | Yes (RealSense needs it) |

---

## Step 1 — Install Librealsense SDK

The **pyrealsense2** Python bindings depend on the native
Librealsense2 C++ library. Install it first.

### Option A — Pre-built Ubuntu/Debian package (easiest)

```bash
# Add the official Intel RealSense APT repository
sudo apt-key adv --keyserver keyserver.ubuntu.com --recv-key C8B3A55A6F3EFCDE
sudo add-apt-repository "deb https://librealsense.intel.com/RelDeb_utils/jammy ./"
sudo apt update
sudo apt install librealsense2-dkms librealsense2-utils

# Verify the camera is detected
realsense-viewer
```

Press **Ctrl+Q** to close the viewer once you confirm video is displayed.

### Option B — Build from source (for latest features)

```bash
sudo apt install git cmake pkg-config libusb-1.0-0-dev libgtk-3-dev \
                 libglfw3-dev libgl1-mesa-dev libglu1-mesa-dev \
                 pkg-config libudev-dev

git clone https://github.com/IntelRealSense/librealsense.git
cd librealsense
mkdir build && cd build
cmake .. -DBUILD_EXAMPLES=true
make -j$(nproc)
sudo make install
cd ../..
rm -rf librealsense
```

### Option C — Windows (WSL2 or native)

**WSL2:** Follow Option A inside WSL2. Plug the camera into the USB and use
`usbipd` to pass it through.

**Native Windows:** Download the installer from
https://github.com/IntelRealSense/librealsense/releases and run it.
Then use the Anaconda prompt or add `C:\Program Files\Intel RealSense SDK 2.0\python\wrapper\your_python_version` to your `PATH`.

---

## Step 2 — Install Python Dependencies

```bash
# Create a virtual environment (recommended)
python3 -m venv venv
source venv/bin/activate     # Linux / macOS
# venv\Scripts\activate      # Windows

# Install packages
pip install -r requirements.txt
```

### What gets installed

| Package | Purpose |
|---------|---------|
| `opencv-python` | Computer vision — ArUco detection, drawing, image I/O |
| `pyrealsense2`  | Python bindings for Intel RealSense cameras |
| `numpy`         | Numerical arrays (camera matrices, transforms) |

### Verify the installation

```bash
# Python imports should not raise errors
python3 -c "import cv2; print('OpenCV', cv2.__version__)"
python3 -c "import pyrealsense2 as rs; print('pyrealsense2 OK')"
```

### Common installation errors

| Error | Fix |
|-------|-----|
| `No module named pyrealsense2` | Re-run `pip install pyrealsense2` |
| `librealsense2.so: cannot open shared object file` | Run `sudo ldconfig` or `export LD_LIBRARY_PATH=/usr/local/lib:$LD_LIBRARY_PATH` |
| `USB permission denied` | Run `sudo usermod -aG users $USER` then **reboot** |

---

## Step 3 — Print ArUco Markers

You need physical ArUco markers to detect. Here's how to generate them:

### Quick one-liner (generates a 5-marker PDF)

```bash
python3 - <<'PY'
import cv2
import numpy as np
import os

dictionary = cv2.aruco.getPredefinedDictionary(cv2.aruco.DICT_6X6_250)
marker_size_px = 400
output_dir = "markers"
os.makedirs(output_dir, exist_ok=True)

for marker_id in range(5):
    img = dictionary.generateImageMarker(marker_id, marker_size_px)
    path = os.path.join(output_dir, f"marker_{marker_id}.png")
    cv2.imwrite(path, img)
    print(f"  Saved {path}")

print("\nPrint these PNGs on A4 paper (keep the original size = 100% / no scaling).")
print("Measure the square side length and pass it as --marker-size (in metres).")
PY
```

**Important:** Print at **100% scale** (no "fit to page"). Measure the
printed square side with a ruler and pass that value (in metres) to
`--marker-size`.

### Online generator

https://chev.me/arucogen/ — paste marker IDs, choose dictionary `6x6_250`,
set size, and download the PDF.

---

## Step 4 — Run the Application

### Basic usage

```bash
python3 aruco_realsense.py
```

This starts the RealSense RGB camera, detects ArUco markers (`6x6_250`
dictionary, 5 cm square size by default), and draws:

- **Green outlines** around each detected marker
- **RGB 3D axes** (red=X, green=Y, blue=Z) showing the marker's pose
- **Marker ID** and **translation vector** as text labels

### Custom marker size

If your printed markers are 10 cm (0.1 m):

```bash
python3 aruco_realsense.py --marker-size 0.1
```

### Different dictionary

```bash
python3 aruco_realsense.py --dictionary 4x4_100
```

### With custom camera calibration

```bash
python3 aruco_realsense.py --calib-file camera_calibration.npz
```

### Keyboard shortcuts

| Key | Action |
|-----|--------|
| `q` / `ESC` | Quit |
| `f` | Toggle fullscreen |
| `s` | Save screenshot to `screenshot_YYYYMMDD_HHMMSS_NNN.png` |

---

## CLI Reference

```
usage: aruco_realsense.py [-h]
                          [--dictionary {4x4_50,4x4_100,...,7x7_1000}]
                          [--marker-size SIZE]
                          [--width WIDTH]
                          [--height HEIGHT]
                          [--fps FPS]
                          [--calib-file FILE]
                          [--depth]

options:
  -h, --help            Show this help message
  --dictionary DICT     ArUco dictionary (default: 6x6_250)
  --marker-size SIZE    Physical marker square side in metres (default: 0.05)
  --width WIDTH         RGB stream width (default: 640)
  --height HEIGHT       RGB stream height (default: 480)
  --fps FPS             Capture FPS (default: 30)
  --calib-file FILE     Path to calibration .npz file
  --depth               Enable depth-colour overlay
```

---

## Camera Calibration (Optional but Recommended)

The RealSense SDK provides factory-calibrated intrinsics, but a custom
calibration improves pose accuracy, especially with lens distortion.

### Quick calibration script

```bash
python3 - <<'PY'
"""
Quick camera calibration using RealSense + a chessboard.
Hold a chessboard (9x6 inner corners) in front of the camera and
capture frames by pressing SPACE. Press Q when done (need 10+ frames).
"""
import cv2
import numpy as np
import pyrealsense2 as rs

# Chessboard parameters — adjust to your board
BOARD_W, BOARD_H = 9, 6          # inner corners (not squares)
SQUARE_SIZE = 0.025              # metres (25 mm squares)

obj_pts = np.zeros((BOARD_W * BOARD_H, 3), np.float32)
obj_pts[:, :2] = np.mgrid[0:BOARD_W, 0:BOARD_H].T.reshape(-1, 2)
obj_pts *= SQUARE_SIZE

obj_points, img_points = [], []

pipeline = rs.pipeline()
cfg = rs.config()
cfg.enable_stream(rs.stream.color, 640, 480, rs.format.bgr8, 30)
pipeline.start(cfg)

win = "Calibration — SPACE to capture, Q to finish"
cv2.namedWindow(win)

count = 0
while count < 15:
    frames = pipeline.wait_for_frames()
    frame = np.asanyarray(frames.get_color_frame().data)
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

    ret, corners = cv2.findChessboardCornersSB(gray, (BOARD_W, BOARD_H))
    if ret:
        cv2.cornerSubPix(gray, corners, (11,11), (-1,-1),
                         (cv2.TERM_CRITERIA_EPS+cv2.TERM_CRITERIA_MAX_ITER, 30, 0.01))
        cv2.drawChessboardCorners(frame, (BOARD_W, BOARD_H), corners, ret)
        cv2.putText(frame, "Press SPACE to capture", (10, 30),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0,255,0), 2)

    cv2.putText(frame, f"Captured: {count}/15", (10, frame.shape[0]-10),
                cv2.FONT_HERSHEY_SIMPLEX, 0.6, (200,200,200), 1)
    cv2.imshow(win, frame)

    key = cv2.waitKey(1) & 0xFF
    if key == ord(" "):
        obj_points.append(obj_pts)
        img_points.append(corners)
        count += 1
        print(f"[+] Frame {count} captured")
    elif key in (ord("q"), 27):
        break

pipeline.stop()
cv2.destroyAllWindows()

if count >= 10:
    ret, mtx, dist, rvecs, tvecs = cv2.calibrateCamera(
        obj_points, img_points, gray.shape[::-1], None, None)
    print(f"\nCalibration OK (re-projection error: {ret:.4f})")
    np.savez("camera_calibration.npz",
             cameraMatrix=mtx, distCoeffs=dist)
    print("Saved: camera_calibration.npz")
    print("\nUse:  python3 aruco_realsense.py --calib-file camera_calibration.npz")
else:
    print(f"[!] Need at least 10 frames (captured {count})")
PY
```

---

## Troubleshooting

### "Cannot open device / RealSense not detected"

```bash
# Check USB connection
lsusb | grep -i intel

# Check kernel module
lsmod | grep uvcvideo

# Add udev rule (allows non-root access)
echo 'SUBSYSTEM=="usb", ATTR{idVendor}=="8086", MODE="0666"' | \
    sudo tee /etc/udev/rules.d/99-realsense-libusb.rules
sudo udevadm control --reload-rules && sudo udevadm trigger
```

### "ModuleNotFoundError: No module named pyrealsense2"

```bash
pip install --force-reinstall pyrealsense2
```

### "cv2.aruco is not found"

Make sure you're using `opencv-python` (not `opencv-contrib-python` —
ArUco is included in the main package since 4.x):

```bash
pip uninstall opencv-contrib-python   # if installed
pip install opencv-python>=4.8.0
```

### Markers not detected

1. **Check dictionary:** Make sure `--dictionary` matches what you printed.
2. **Check lighting:** Avoid glare/reflections on the printed marker.
3. **Check distance:** Hold the marker 20–80 cm from the camera.
4. **Check marker size:** `--marker-size` only affects pose scale, not
   detection. Use `--width 1280 --height 720` for better resolution.

### Pose axes look wrong / jittery

1. **Calibrate your camera** (see section above).
2. **Verify marker size** — measure the printed square with a ruler.
3. **Increase resolution:** `--width 1280 --height 720`.

---

## How It Works

```
┌─────────────┐     ┌──────────────┐     ┌──────────────────┐
│  RealSense  │────►│  BGR Frame   │────►│  cv2.aruco.      │
│  Camera     │     │  (640x480)   │     │  detectMarkers() │
└─────────────┘     └──────────────┘     └────────┬─────────┘
                                                   │
                                          corners + ids
                                                   │
                                          ┌────────▼─────────┐
                                          │ estimatePose     │
                                          │   Markers()      │
                                          └────────┬─────────┘
                                                   │
                                          rvecs + tvecs
                                                   │
                                          ┌────────▼─────────┐
                                          │ drawDetected     │
                                          │   Markers()      │
                                          │   drawAxes()     │
                                          └────────┬─────────┘
                                                   │
                                          ┌────────▼─────────┐
                                          │  Annotated Frame │
                                          │  → imshow()      │
                                          └──────────────────┘
```

1. **Capture:** `pyrealsense2` streams BGR frames from the RGB sensor.
2. **Detect:** `cv2.aruco.detectMarkers()` finds marker corners and IDs
   in the grayscale frame.
3. **Pose:** `cv2.aruco.estimatePoseMarkers()` uses PnP to solve for
   each marker's rotation (`rvec`) and translation (`tvec`) relative
   to the camera.
4. **Draw:** Green outlines + RGB axes (X=red, Y=green, Z=blue) are
   overlaid on the frame.

---

## File Structure

```
aruco_realsense/
├── aruco_realsense.py    # Main application
├── requirements.txt      # Python dependencies
└── README.md             # This file
```

---

## License

MIT — feel free to modify and reuse.

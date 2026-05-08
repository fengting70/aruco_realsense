#!/usr/bin/env python3
"""
Intel RealSense + ArUco Marker Detection & Pose Estimation
============================================================
Detects ArUco markers in a RealSense RGB stream, estimates their
6-DoF poses (rotation + translation), and draws 3D axes on each marker.

Usage:
    python aruco_realsense.py [--dictionary DICT] [--marker-size SIZE]
    python aruco_realsense.py --help

Keyboard:
    q / ESC   Quit
    d         Toggle depth-colormap overlay
    f         Toggle fullscreen
    s         Save screenshot
"""

import argparse
import cv2
import numpy as np
import pyrealsense2 as rs
import os
import sys
from datetime import datetime

# ------------------------------------------------------------------
# ArUco dictionary presets (name -> OpenCV constant)
# ------------------------------------------------------------------
DICT_MAP = {
    "4x4_50":     cv2.aruco.DICT_4X4_50,
    "4x4_100":    cv2.aruco.DICT_4X4_100,
    "4x4_250":    cv2.aruco.DICT_4X4_250,
    "4x4_1000":   cv2.aruco.DICT_4X4_1000,
    "5x5_50":     cv2.aruco.DICT_5X5_50,
    "5x5_100":    cv2.aruco.DICT_5X5_100,
    "5x5_250":    cv2.aruco.DICT_5X5_250,
    "5x5_1000":   cv2.aruco.DICT_5X5_1000,
    "6x6_50":     cv2.aruco.DICT_6X6_50,
    "6x6_100":    cv2.aruco.DICT_6X6_100,
    "6x6_250":    cv2.aruco.DICT_6X6_250,
    "6x6_1000":   cv2.aruco.DICT_6X6_1000,
    "7x7_50":     cv2.aruco.DICT_7X7_50,
    "7x7_100":    cv2.aruco.DICT_7X7_100,
    "7x7_250":    cv2.aruco.DICT_7X7_250,
    "7x7_1000":   cv2.aruco.DICT_7X7_1000,
}


def build_parser():
    """Build CLI argument parser."""
    parser = argparse.ArgumentParser(
        description="RealSense ArUco marker detection + pose estimation")
    parser.add_argument(
        "--dictionary", type=str, default="6x6_250",
        choices=list(DICT_MAP.keys()),
        help="ArUco dictionary (default: 6x6_250)")
    parser.add_argument(
        "--marker-size", type=float, default=0.05,
        help="Physical marker square side in metres (default: 0.05 = 5 cm)")
    parser.add_argument(
        "--width", type=int, default=640,
        help="RGB stream width (default: 640)")
    parser.add_argument(
        "--height", type=int, default=480,
        help="RGB stream height (default: 480)")
    parser.add_argument(
        "--fps", type=int, default=30,
        help="Capture FPS (default: 30)")
    parser.add_argument(
        "--calib-file", type=str, default=None,
        help="Path to camera calibration .npz file (cameraMatrix + distCoeffs). "
             "If omitted, intrinsics are read live from the RealSense sensor.")
    return parser


# ------------------------------------------------------------------
# Camera intrinsics helpers
# ------------------------------------------------------------------

def intrinsics_from_realsense(stream_profile):
    """Extract camera matrix & distortion from a RealSense video stream profile."""
    intr = stream_profile.as_video_stream_profile().get_intrinsics()
    camera_matrix = np.array([
        [intr.fx,  0.0, intr.ppx],
        [ 0.0, intr.fy, intr.ppy],
        [ 0.0,  0.0,     1.0],
    ], dtype=np.float32)
    # RealSense provides distortion coeffs as a list
    dist_coeffs = np.array(intr.coeffs, dtype=np.float32).reshape(1, -1)
    return camera_matrix, dist_coeffs


def intrinsics_from_calib_file(path):
    """Load camera matrix + distortion from an OpenCV calibration .npz."""
    data = np.load(path)
    return data["cameraMatrix"].astype(np.float32), data["distCoeffs"].astype(np.float32)


# ------------------------------------------------------------------
# ArUco detection helpers
# ------------------------------------------------------------------

def my_estimatePoseSingleMarkers(corners, marker_size, mtx, distortion):
    '''
    This will estimate the rvec and tvec for each of the marker corners detected by:
       corners, ids, rejectedImgPoints = detector.detectMarkers(image)
    corners - is an array of detected corners for each detected marker in the image
    marker_size - is the size of the detected markers
    mtx - is the camera matrix
    distortion - is the camera distortion matrix
    RETURN list of rvecs, tvecs, and trash (so that it corresponds to the old estimatePoseSingleMarkers())
    '''
    marker_points = np.array([[-marker_size / 2, marker_size / 2, 0],
                              [marker_size / 2, marker_size / 2, 0],
                              [marker_size / 2, -marker_size / 2, 0],
                              [-marker_size / 2, -marker_size / 2, 0]], dtype=np.float32)
    trash = []
    rvecs = []
    tvecs = []
    
    for c in corners:
        nada, R, t = cv2.solvePnP(marker_points, c, mtx, distortion, False, cv2.SOLVEPNP_IPPE_SQUARE)
        rvecs.append(R)
        tvecs.append(t)
        trash.append(nada)
    return rvecs, tvecs, trash

def detect_and_estimate(frame, dictionary, detector_params, marker_size,
                        camera_matrix, dist_coeffs):
    """
    Detect ArUco markers in a BGR frame and estimate their 6-DoF pose.

    Returns
    -------
    corners : list of detected corners (or None)
    ids     : marker IDs (or None)
    rvecs   : per-marker rotation vectors (list)
    tvecs   : per-marker translation vectors (list)
    """
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    aruco_detector =  cv2.aruco.ArucoDetector(dictionary, detector_params)
    corners, ids, _ = aruco_detector.detectMarkers(gray)

    # Estimate pose for every detected marker
    rvecs, tvecs, _objpts = None, None, []
    if ids is not None and len(ids) > 0:
        rvecs, tvecs, _objpts = my_estimatePoseSingleMarkers(
            corners, marker_size, camera_matrix, dist_coeffs)

    return corners, ids, rvecs, tvecs


def draw_markers_and_axes(frame, corners, ids, rvecs, tvecs, marker_size, camera_matrix, dist_coeffs):
    """
    Draw marker outlines, IDs, and 3D pose axes on the frame.

    Each axis: X=red, Y=green, Z=blue (OpenGL convention).
    """
    if ids is None or len(ids) == 0:
        return frame

    cv2.aruco.drawDetectedMarkers(frame, corners, ids, borderColor=(0, 255, 0))

    for i, mid in enumerate(ids.flatten()):
        cv2.drawFrameAxes(
            frame, camera_matrix,dist_coeffs, rvecs[i], tvecs[i], marker_size * 1.0)

        # Label with marker ID at the top-left corner
        pt = tuple(corners[i][0][0].astype(int))
        cv2.putText(frame, f"#{mid}",
                    (pt[0] - 5, pt[1] - 10),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 255), 2)

        # Translation info below the marker
        tx, ty, tz = tvecs[i].ravel()
        info = f"t=({tx:.2f},{ty:.2f},{tz:.2f})"
        cv2.putText(frame, info,
                    (pt[0], pt[1] + 20),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.4, (255, 255, 0), 1)

    return frame


# ------------------------------------------------------------------
# Main
# ------------------------------------------------------------------

def main():
    parser = build_parser()
    args = parser.parse_args()

    # ---- dictionary ----
    dictionary = cv2.aruco.getPredefinedDictionary(DICT_MAP[args.dictionary])
    detector_params = cv2.aruco.DetectorParameters()
    detector_params.cornerRefinementMethod = cv2.aruco.CORNER_REFINE_SUBPIX

    print(f"[Config] Dictionary : {args.dictionary}")
    print(f"[Config] Marker size: {args.marker_size} m")
    print(f"[Config] Resolution : {args.width}x{args.height} @ {args.fps} fps")

    # ---- RealSense pipeline ----
    pipeline = rs.pipeline()
    cfg = rs.config()
    cfg.enable_stream(rs.stream.color, args.width, args.height,
                      rs.format.bgr8, args.fps)
    cfg.enable_stream(rs.stream.depth, args.width, args.height,
                      rs.format.z16, args.fps)

    try:
        profile = pipeline.start(cfg)
    except RuntimeError as e:
        print(f"[ERROR] Cannot start RealSense pipeline: {e}")
        print("        Make sure a RealSense camera is connected and "
              "librealsense2 is installed.")
        sys.exit(1)

    # Grab intrinsics from the actual device
    frames = pipeline.wait_for_frames()
    color_profile = frames.get_color_frame().profile
    camera_matrix, dist_coeffs = intrinsics_from_realsense(color_profile)
    print(f"[Camera] FX={camera_matrix[0,0]:.1f}  FY={camera_matrix[1,1]:.1f}  "
          f"PP=({camera_matrix[0,2]:.1f}, {camera_matrix[1,2]:.1f})")

    # Or override with a calibration file
    if args.calib_file:
        camera_matrix, dist_coeffs = intrinsics_from_calib_file(args.calib_file)
        print(f"[Camera] Loaded calibration from {args.calib_file}")

    # Align depth frame to color frame (see align-depth2color.py)
    align = rs.align(rs.stream.color)

    # ---- UI window ----
    win_name = "RealSense — ArUco Pose Estimation"
    cv2.namedWindow(win_name, cv2.WINDOW_AUTOSIZE)

    prev_time = cv2.getTickCount()
    frame_count = 0
    screenshot_idx = 0
    depth_overlay = False

    # Mouse tracking state
    mouse_x, mouse_y = -1, -1
    mouse_callback_set = False

    print("[INFO]  Press 'q' or ESC to quit  |  's' to save screenshot")
    print("       Press 'f' to toggle fullscreen")
    print("       Press 'd' to toggle depth overlay")
    print("=" * 60)

    try:
        while True:
            frames = pipeline.wait_for_frames()
            # Align depth frame to color frame
            aligned_frames = align.process(frames)
            color_frame = aligned_frames.get_color_frame()
            if not color_frame:
                continue

            frame = np.asanyarray(color_frame.data)

            # Get aligned depth frame if overlay is on
            depth_image = None
            if depth_overlay:
                aligned_depth_frame = aligned_frames.get_depth_frame()
                if aligned_depth_frame:
                    depth_image = np.asanyarray(aligned_depth_frame.get_data())

            # ---- detect & pose ----
            corners, ids, rvecs, tvecs = detect_and_estimate(
                frame, dictionary, detector_params,
                args.marker_size, camera_matrix, dist_coeffs)

            # ---- draw ----
            draw_markers_and_axes(frame, corners, ids, rvecs, tvecs,
                                  args.marker_size, camera_matrix, dist_coeffs)

            # FPS counter
            frame_count += 1
            elapsed = (cv2.getTickCount() - prev_time) / cv2.getTickFrequency()
            fps = frame_count / elapsed if elapsed > 0 else 0
            status = f"FPS: {fps:.1f}"
            if ids is not None and len(ids) > 0:
                status += f"  |  Markers: {', '.join(map(str, ids.flatten()))}"
            else:
                status += "  |  No markers"
            
            if depth_overlay and depth_image is not None:
                status += "  |  Depth overlay: ON"
            else:
                status += "  |  Depth overlay: OFF"

            cv2.putText(frame, status, (10, 30),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)

            # ---- display ----
            display = frame
            if depth_overlay and depth_image is not None:
                # Blend depth colormap onto color frame (see align-depth2color.py)
                depth_colormap = cv2.applyColorMap(
                    cv2.convertScaleAbs(depth_image, alpha=0.03),
                    cv2.COLORMAP_JET)
                display = cv2.addWeighted(frame, 0.30, depth_colormap, 0.70, 0)

            cv2.imshow(win_name, display)

            # Set mouse callback after window is created (avoids NULL handler error)
            if not mouse_callback_set:
                def on_mouse(event, x, y, flags, param):
                    nonlocal mouse_x, mouse_y
                    mouse_x, mouse_y = x, y
                cv2.setMouseCallback(win_name, on_mouse)
                mouse_callback_set = True

            # ---- mouse cursor info (second HUD line) ----
            if 0 <= mouse_y < display.shape[0] and 0 <= mouse_x < display.shape[1]:
                cursor_info = f"({mouse_x},{mouse_y})"
                if depth_overlay and depth_image is not None:
                    depth_mm = int(depth_image[mouse_y, mouse_x])
                    cursor_info += f"  |  Depth={depth_mm}mm"
                cv2.putText(display, cursor_info, (10, 55),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 1)

            key = cv2.waitKey(1) & 0xFF
            if key in (ord("q"), 27):
                break
            elif key == ord("f"):
                if cv2.getWindowProperty(win_name, cv2.WND_PROP_FULLSCREEN) \
                        == cv2.WINDOW_FULLSCREEN:
                    cv2.setWindowProperty(win_name, cv2.WND_PROP_FULLSCREEN,
                                          cv2.WINDOW_NORMAL)
                else:
                    cv2.setWindowProperty(win_name, cv2.WND_PROP_FULLSCREEN,
                                          cv2.WINDOW_FULLSCREEN)
            elif key == ord("d"):
                depth_overlay = not depth_overlay
                # print(f"[INFO] Depth overlay: {'ON' if depth_overlay else 'OFF'}")
            elif key == ord("s"):
                screenshot_idx += 1
                ts = datetime.now().strftime("%Y%m%d_%H%M%S")
                path = f"screenshot_{ts}_{screenshot_idx:03d}.png"
                cv2.imwrite(path, display)
                print(f"[+] Saved {path}")

    except KeyboardInterrupt:
        print("\n[INFO] Interrupted.")
    finally:
        pipeline.stop()
        cv2.destroyAllWindows()
        print("[INFO] Done.")


if __name__ == "__main__":
    main()

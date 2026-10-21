"""Generate the printable ArUco marker used for vision scale calibration."""

import argparse
from pathlib import Path

import cv2


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--id", type=int, default=23)
    parser.add_argument("--pixels", type=int, default=900)
    parser.add_argument("--out", default="aruco_marker_5cm.png")
    args = parser.parse_args()

    dictionary = cv2.aruco.getPredefinedDictionary(cv2.aruco.DICT_4X4_50)
    marker = cv2.aruco.generateImageMarker(dictionary, args.id, args.pixels)
    border = max(32, args.pixels // 10)
    marker = cv2.copyMakeBorder(marker, border, border, border, border, cv2.BORDER_CONSTANT, value=255)

    out = Path(args.out)
    ok = cv2.imwrite(str(out), marker)
    if not ok:
        raise SystemExit(f"Could not write {out}")
    print(f"Wrote {out}. Print it so the black marker square is exactly 5 cm wide.")


if __name__ == "__main__":
    main()

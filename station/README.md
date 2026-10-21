# Reweave scanning station

A permanent scanning station: a Raspberry Pi with a camera mounted over the cutting table. A worker spreads offcuts on the table and presses a button. The station takes a full-resolution photo, sends it to the Reweave backend, and the server sorts the pieces into bins and lists every bin on the marketplace as a lot. No phone or laptop is needed.

```
button press ─▶ station.py ─▶ camera still (12 MP)
                     │
                     └─▶ POST /api/vision/scan  ─▶ scan pipeline ─▶ one lot per bin
                                                   (pinned to the station's location)
```

Results are printed to the station log (bin letter, material, pieces, weight, price, and where to put each piece), and the status light shows whether the scan worked.

## Hardware

| Part | Notes |
|---|---|
| Raspberry Pi 4 or 5 | 2 GB+ RAM. The Pi only captures and uploads; all vision runs on the backend |
| Raspberry Pi Camera Module 3 | The 12 MP autofocus model. Use the **Wide** variant if the camera is mounted under ~80 cm above the table |
| Overhead mount | A boom arm or ceiling bracket holding the camera level, pointing straight down |
| Momentary push button | Any normally-open button; wired to a GPIO pin and ground |
| LED + 330 Ω resistor | Optional status light |
| Diffuse lighting | LED panels on both sides of the table. Avoid hard shadows and direct sunlight |
| Printed scale marker | 5 cm ArUco marker from `GET /api/vision/aruco-marker`, printed at exactly 5 cm and taped flat in a corner of the table |

### Wiring

Pin numbers are BCM (the `GPIOxx` names), with physical header pins in brackets.

| Part | Connect |
|---|---|
| Button | one leg to GPIO17 [pin 11], the other to GND [pin 9] (the internal pull-up is used, so no resistor is needed) |
| Status LED | GPIO27 [pin 13] → 330 Ω resistor → LED long leg; LED short leg → GND [pin 14] |

Status light: **blinking** while a scan is running, **solid for 4 s** when the lots are listed, **fast blinking** when the scan failed.

### Placement

- Mount the camera so the whole working area fits in frame with a small margin, with the scale marker visible in a corner.
- Use a plain, matte surface that contrasts with the fabric. Busy patterns or a glossy table confuse segmentation.
- Lay pieces flat and keep them from overlapping. Overlapping pieces merge into one.

## Install

On Raspberry Pi OS (Bookworm or later), which already includes `picamera2` and `gpiozero`:

```bash
sudo apt update && sudo apt install -y python3-picamera2 python3-gpiozero git
rpicam-hello --timeout 5000          # confirm the camera works

git clone <your-repo-url> ~/reweave
cd ~/reweave/station
python3 -m venv --system-site-packages .venv   # system packages give access to picamera2
.venv/bin/pip install -r requirements.txt
```

## Configure

```bash
cp station.env.example station.env
nano station.env
```

| Variable | Purpose |
|---|---|
| `REWEAVE_API_URL` | Backend base URL, reachable from the Pi |
| `REWEAVE_EMAIL`, `REWEAVE_PASSWORD` | A **factory** (or admin) account. The station signs in on start and again when its token expires |
| `STATION_LAT`, `STATION_LNG` | The station's location, used to pin its lots on the buyer map |
| `BUTTON_GPIO` | Button pin (default 17). If empty, the station reads Enter from the terminal instead |
| `STATUS_LED_GPIO` | Status light pin. Leave empty for no light |
| `CAPTURE_DIR`, `KEEP_CAPTURES` | Where photos are saved, and how many to keep (default 20) |
| `CAPTURE_WIDTH`, `CAPTURE_HEIGHT` | Still resolution (default 4608×2592, the Camera Module 3 maximum) |
| `USE_DEPLOYMENT` | Use the backend's always-warm segmentation deployment when one is configured |
| `REQUEST_TIMEOUT_S` | How long to wait for a scan (default 240 s) |

## Test

```bash
.venv/bin/python station.py --env-file station.env --once
```

This takes one photo straight away, scans it, prints the bins, and exits. To test without a camera, for example on a laptop, upload an existing photo:

```bash
.venv/bin/python station.py --env-file station.env --file table.jpg
```

Each scan lists real lots. Clear test scans afterwards from the factory portal ("Reset inventory") or the admin inventory page.

## Run as a service

The service starts the station at boot, waits for button presses, and restarts it if it stops.

```bash
sudo cp station.env /etc/reweave-station.env
sudo chmod 600 /etc/reweave-station.env       # it contains the account password
```

Edit `reweave-station.service` so that `User=` is your Pi username and the paths point to your clone, then:

```bash
sudo cp reweave-station.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now reweave-station
journalctl -u reweave-station -f              # watch scans as they happen
```

## Troubleshooting

| Symptom | Fix |
|---|---|
| `Photo rejected: No fabric pieces remained…` | Check lighting and table contrast, and spread the pieces out |
| Weights look wrong | Make sure the marker is visible, flat, and printed at exactly 5 cm. The log warns when it falls back to an estimated scale |
| `Could not sign in…` at boot | The network wasn't ready yet; the service retries every 10 s |
| `… is a buyer account` | Use a factory or admin login |
| First scan of the day is slow | The segmentation model is cold-starting. The station requests a warm-up on start, and configuring `REPLICATE_DEPLOYMENT` on the backend removes the delay |
| Failed scans | The photo stays in `CAPTURE_DIR`. Rescan it with `--file` once the cause is fixed |

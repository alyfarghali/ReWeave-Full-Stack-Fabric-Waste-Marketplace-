"""Reweave scanning station for a Raspberry Pi with a camera mounted over the cutting table.

Each press of the station button (or Enter, when run interactively) takes a
full-resolution still, uploads it to POST /api/vision/scan, and prints the sort
bins the pipeline assigned. Every bin is listed on the marketplace as a lot by
the server, pinned to the station's configured location.

    python station.py                 # run forever, scanning on each trigger
    python station.py --once          # one scan, then exit
    python station.py --file scan.jpg # upload an existing photo (no camera needed)

Configuration comes from environment variables (see station.env.example);
``--env-file`` loads them from a file for manual runs.
"""

from __future__ import annotations

import argparse
import logging
import os
import sys
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

import requests

log = logging.getLogger("reweave.station")


# -- configuration ------------------------------------------------------------------


def _env(name: str, default: str = "") -> str:
    return os.environ.get(name, default).strip()


def _optional_float(name: str) -> float | None:
    value = _env(name)
    return float(value) if value else None


def _optional_int(name: str, default: str = "") -> int | None:
    value = _env(name, default)
    return int(value) if value else None


@dataclass(frozen=True)
class Config:
    api_url: str
    email: str
    password: str
    station_lat: float | None
    station_lng: float | None
    button_gpio: int | None
    status_led_gpio: int | None
    capture_dir: Path
    keep_captures: int
    capture_size: tuple[int, int]
    use_deployment: bool
    request_timeout_s: int

    @classmethod
    def from_env(cls) -> "Config":
        return cls(
            api_url=_env("REWEAVE_API_URL", "http://localhost:8000").rstrip("/"),
            email=_env("REWEAVE_EMAIL"),
            password=_env("REWEAVE_PASSWORD"),
            station_lat=_optional_float("STATION_LAT"),
            station_lng=_optional_float("STATION_LNG"),
            button_gpio=_optional_int("BUTTON_GPIO", "17"),
            status_led_gpio=_optional_int("STATUS_LED_GPIO"),
            capture_dir=Path(_env("CAPTURE_DIR", "~/reweave-station/captures")).expanduser(),
            keep_captures=int(_env("KEEP_CAPTURES", "20")),
            capture_size=(int(_env("CAPTURE_WIDTH", "4608")), int(_env("CAPTURE_HEIGHT", "2592"))),
            use_deployment=_env("USE_DEPLOYMENT", "true").lower() in {"1", "true", "yes", "on"},
            request_timeout_s=int(_env("REQUEST_TIMEOUT_S", "240")),
        )

    def validate(self) -> None:
        missing = [name for name, value in (("REWEAVE_EMAIL", self.email), ("REWEAVE_PASSWORD", self.password)) if not value]
        if missing:
            raise SystemExit(f"Missing configuration: {', '.join(missing)} (see station.env.example)")


def load_env_file(path: Path) -> None:
    """Minimal KEY=VALUE loader; existing environment variables win."""
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


# -- backend API --------------------------------------------------------------------


class ScanRejected(Exception):
    """The server could not use the photo (blurry, nothing found, segmentation failed)."""


class ApiClient:
    RETRY_DELAYS_S = (5, 15, 45)
    # Gateway and availability errors are worth retrying. A 500 means the
    # pipeline itself failed, and rerunning it would repeat paid AI calls.
    RETRYABLE_STATUS = {502, 503, 504}

    def __init__(self, config: Config):
        self.config = config
        self.session = requests.Session()
        self.token: str | None = None

    def login(self) -> None:
        response = self.session.post(
            f"{self.config.api_url}/api/auth/login",
            json={"email": self.config.email, "password": self.config.password},
            timeout=30,
        )
        if response.status_code == 401:
            raise SystemExit("Login failed: check REWEAVE_EMAIL and REWEAVE_PASSWORD")
        response.raise_for_status()
        body = response.json()
        if body.get("role") not in {"factory", "admin"}:
            raise SystemExit(f"{self.config.email} is a {body.get('role')} account; the station needs a factory login")
        self.token = body["access_token"]
        log.info("Signed in as %s", body.get("name") or self.config.email)

    def warmup(self) -> None:
        """Boot the segmentation model ahead of the first scan. Best effort."""
        try:
            self._authorized_post("/api/vision/warmup", timeout=15)
        except requests.RequestException:
            pass

    def scan(self, photo: Path) -> dict:
        """Upload a photo and return the listing result, retrying transient failures."""
        for attempt, delay in enumerate((0, *self.RETRY_DELAYS_S)):
            if delay:
                log.warning("Retrying in %ss (attempt %d)", delay, attempt + 1)
                time.sleep(delay)
            try:
                response = self._upload(photo)
            except requests.RequestException as exc:
                log.warning("Could not reach %s: %s", self.config.api_url, exc)
                continue
            if response.status_code == 400:
                raise ScanRejected(_detail(response))
            if response.status_code in self.RETRYABLE_STATUS:
                log.warning("Server unavailable (%s)", response.status_code)
                continue
            if not response.ok:
                raise RuntimeError(f"Server error {response.status_code}: {_detail(response)}")
            return response.json()
        raise ConnectionError("Scan failed after retries; the photo is kept in the capture folder")

    def _upload(self, photo: Path) -> requests.Response:
        data = {"use_deployment": str(self.config.use_deployment).lower()}
        if self.config.station_lat is not None and self.config.station_lng is not None:
            data.update(origin_lat=str(self.config.station_lat), origin_lng=str(self.config.station_lng))

        with photo.open("rb") as image:
            return self._authorized_post(
                "/api/vision/scan",
                files={"image": (photo.name, image, "image/jpeg")},
                data=data,
                timeout=self.config.request_timeout_s,
            )

    def _authorized_post(self, path: str, **kwargs) -> requests.Response:
        if not self.token:
            self.login()
        response = self.session.post(f"{self.config.api_url}{path}", headers=self._auth(), **kwargs)
        if response.status_code == 401:  # token expired: sign in again once
            self.login()
            for value in (kwargs.get("files") or {}).values():
                value[1].seek(0)
            response = self.session.post(f"{self.config.api_url}{path}", headers=self._auth(), **kwargs)
        return response

    def _auth(self) -> dict:
        return {"Authorization": f"Bearer {self.token}"}


def _detail(response: requests.Response) -> str:
    try:
        return str(response.json().get("detail") or response.text)
    except ValueError:
        return response.text[:300]


# -- hardware -----------------------------------------------------------------------


class Camera:
    """Raspberry Pi camera via picamera2 (preinstalled on Raspberry Pi OS)."""

    def __init__(self, size: tuple[int, int]):
        try:
            from picamera2 import Picamera2
        except ImportError as exc:
            raise SystemExit(
                "picamera2 is not available. On Raspberry Pi OS: sudo apt install python3-picamera2, "
                "and create the venv with --system-site-packages."
            ) from exc
        self.camera = Picamera2()
        self.camera.configure(self.camera.create_still_configuration(main={"size": size}))
        self.camera.start()
        time.sleep(2)  # let exposure and white balance settle
        self.has_autofocus = "AfMode" in self.camera.camera_controls

    def capture(self, path: Path) -> Path:
        if self.has_autofocus:
            self.camera.autofocus_cycle()
        self.camera.capture_file(str(path))
        return path

    def close(self) -> None:
        self.camera.stop()


class StatusLight:
    """Optional LED: blinking while scanning, solid on success, fast blink on error."""

    def __init__(self, gpio: int | None):
        self.led = None
        if gpio is None:
            return
        try:
            from gpiozero import LED

            self.led = LED(gpio)
        except Exception as exc:  # noqa: BLE001 -- the station still works without a light
            log.warning("Status LED on GPIO %s unavailable: %s", gpio, exc)

    def busy(self) -> None:
        if self.led:
            self.led.blink(on_time=0.5, off_time=0.5)

    def ok(self) -> None:
        if self.led:
            self.led.blink(on_time=4, off_time=0, n=1)

    def error(self) -> None:
        if self.led:
            self.led.blink(on_time=0.1, off_time=0.1, n=20)


class Trigger:
    """Waits for the station button, falling back to Enter in an interactive terminal."""

    def __init__(self, gpio: int | None):
        self.button = None
        if gpio is not None:
            try:
                from gpiozero import Button

                self.button = Button(gpio, bounce_time=0.1)
                log.info("Press the button on GPIO %s to scan", gpio)
                return
            except Exception as exc:  # noqa: BLE001
                log.warning("Button on GPIO %s unavailable: %s", gpio, exc)
        if not sys.stdin.isatty():
            raise SystemExit("No button available and no terminal to read Enter from; set BUTTON_GPIO")
        log.info("Press Enter to scan (Ctrl+C to quit)")

    def wait(self) -> None:
        if self.button:
            self.button.wait_for_press()
            self.button.wait_for_release()
        else:
            input()


# -- station ------------------------------------------------------------------------


class Station:
    def __init__(self, config: Config, api: ApiClient, light: StatusLight):
        self.config = config
        self.api = api
        self.light = light

    def scan_photo(self, photo: Path) -> bool:
        log.info("Scanning %s ...", photo.name)
        self.light.busy()
        try:
            result = self.api.scan(photo)
        except ScanRejected as exc:
            self.light.error()
            log.error("Photo rejected: %s. Check the marker is visible and pieces are spread out, then rescan.", exc)
            return False
        except Exception as exc:  # noqa: BLE001 -- keep the station alive for the next scan
            self.light.error()
            log.error("Scan failed: %s", exc)
            return False
        self.light.ok()
        report(result)
        return True

    def capture_path(self) -> Path:
        self.config.capture_dir.mkdir(parents=True, exist_ok=True)
        return self.config.capture_dir / f"scan_{datetime.now():%Y%m%d_%H%M%S}.jpg"

    def prune_captures(self) -> None:
        captures = sorted(self.config.capture_dir.glob("scan_*.jpg"))
        for old in captures[: max(0, len(captures) - self.config.keep_captures)]:
            old.unlink(missing_ok=True)


def report(result: dict) -> None:
    bins = result.get("bins") or []
    log.info("Listed %d bin%s from scan #%s:", len(bins), "" if len(bins) == 1 else "s", result.get("scan_run_id"))
    for item in bins:
        log.info(
            "  Bin %s  %-28s %3d pcs  %6.2f kg  $%7.2f  lot #%s",
            item["sort_group_id"],
            item["name"][:28],
            item["piece_count"],
            item["weight_kg"],
            item["price_usd"],
            item["lot_id"],
        )
        if item.get("sort_instruction"):
            log.info("         %s", item["sort_instruction"])
    log.info(
        "Diverted %.2f kg: %.2f kg CO2e and %.0f L of water saved",
        result.get("total_weight_kg", 0),
        result.get("total_carbon_saved_kg", 0),
        result.get("total_water_saved_l", 0),
    )
    for warning in result.get("warnings") or []:
        log.warning("  %s", warning)


def main() -> None:
    parser = argparse.ArgumentParser(description="Reweave Raspberry Pi scanning station")
    parser.add_argument("--env-file", type=Path, help="load configuration from a KEY=VALUE file")
    parser.add_argument("--once", action="store_true", help="take one scan, then exit")
    parser.add_argument("--file", type=Path, help="upload an existing photo instead of using the camera")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)-7s %(message)s", datefmt="%H:%M:%S")
    if args.env_file:
        load_env_file(args.env_file)
    config = Config.from_env()
    config.validate()

    api = ApiClient(config)
    try:
        api.login()
    except requests.RequestException as exc:
        # Usually the network isn't up yet at boot; the service restarts us.
        log.error("Could not sign in to %s: %s", config.api_url, exc)
        sys.exit(1)
    station = Station(config, api, StatusLight(config.status_led_gpio))

    if args.file:
        sys.exit(0 if station.scan_photo(args.file) else 1)

    api.warmup()
    camera = Camera(config.capture_size)
    trigger = None if args.once else Trigger(config.button_gpio)
    try:
        while True:
            if trigger:
                trigger.wait()
            photo = camera.capture(station.capture_path())
            ok = station.scan_photo(photo)
            station.prune_captures()
            if args.once:
                sys.exit(0 if ok else 1)
    except KeyboardInterrupt:
        log.info("Stopping")
    finally:
        camera.close()


if __name__ == "__main__":
    main()

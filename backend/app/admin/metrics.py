"""The admin operations dashboard: P&L, inventory, impact, and scan history.

``AdminMetricsReport`` takes a snapshot of every lot and scan run and builds
each dashboard section from it.
"""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from ..core.config import get_settings
from ..marketplace.models import Lot, LotStatus, ScanRun
from ..marketplace.piece_images import PieceImages

ESTIMATED_COST_FACTOR = 0.28
DIVERSION_TARGET_KG = 5.0
RECENT_RUN_LIMIT = 8
LOTS_PER_RUN = 10

# Dashboard-specific equivalence factors (these differ slightly from
# ImpactFactors; kept as-is so dashboard numbers don't shift).
CAR_MILES_PER_KG_CO2 = 2.48
PHONE_CHARGES_PER_KG_CO2 = 122
LITERS_PER_SHOWER = 65
LITERS_PER_BOTTLE = 0.5
KWH_PER_KG_DIVERTED = 15


def round_small(value: float, small_digits: int = 3, normal_digits: int = 1) -> float:
    """Keep more precision for sub-1 values so tiny scans don't show 0."""
    value = float(value or 0)
    if abs(value) < 1:
        return round(value, small_digits)
    return round(value, normal_digits)


def short_fabric(value: str) -> str:
    return (value or "Unspecified").split("/")[0].replace(" Blend", "").strip() or "Unspecified"


def run_label(created_at: datetime) -> str:
    base = created_at if created_at.tzinfo else created_at.replace(tzinfo=timezone.utc)
    local = base.astimezone(ZoneInfo(get_settings().display_timezone))
    hour12 = local.hour % 12 or 12
    ampm = "AM" if local.hour < 12 else "PM"
    return f"{local.strftime('%b')} {local.day}, {hour12}:{local.strftime('%M')} {ampm}"


def lot_row(lot: Lot) -> dict:
    return {
        "id": lot.id,
        "name": lot.name,
        "fabric_type": lot.fabric_type,
        "composition": lot.composition,
        "color_name": lot.color_name,
        "color_hex": lot.color_hex,
        "piece_count": lot.piece_count or 0,
        "weight_kg": round_small(lot.weight_kg, normal_digits=2),
        "price_usd": round(lot.price_usd or 0, 2),
        "current_price_usd": round(lot.current_price_usd, 2),
        "carbon_saved_kg": round_small(lot.carbon_saved_kg, normal_digits=2),
        "water_saved_l": round(lot.water_saved_l or 0, 1),
        "status": lot.status,
        "claimed_by": lot.claimed_by,
        "days_listed": lot.days_listed,
        "price_decay_pct": lot.price_decay_pct,
        "scan_run_id": lot.scan_run_id,
        "thumbnail": PieceImages.thumbnail(lot.piece_images),
        "created_at": lot.created_at.isoformat(),
    }


class LotTotals:
    """Sums over a set of lots."""

    def __init__(self, lots: list[Lot]):
        self.lots = lots

    @property
    def weight_kg(self) -> float:
        return sum(lot.weight_kg or 0 for lot in self.lots)

    @property
    def pieces(self) -> int:
        return sum(lot.piece_count or 0 for lot in self.lots)

    @property
    def carbon_kg(self) -> float:
        return sum(lot.carbon_saved_kg or 0 for lot in self.lots)

    @property
    def water_l(self) -> float:
        return sum(lot.water_saved_l or 0 for lot in self.lots)

    @property
    def current_value(self) -> float:
        return sum(lot.current_price_usd for lot in self.lots)

    @property
    def base_value(self) -> float:
        return sum(lot.price_usd or 0 for lot in self.lots)

    def status_counts(self) -> dict:
        return {
            status: sum(1 for lot in self.lots if lot.status == status)
            for status in (LotStatus.AVAILABLE, LotStatus.CLAIMED, LotStatus.UNLISTED)
        }


class AdminMetricsReport:
    def __init__(self, lots: list[Lot], scan_runs: list[ScanRun]):
        """``lots`` and ``scan_runs`` must both be ordered newest first."""
        self.lots = lots
        self.scan_runs = scan_runs
        self.claimed = [lot for lot in lots if lot.status == LotStatus.CLAIMED]
        self.available = [lot for lot in lots if lot.status == LotStatus.AVAILABLE]
        self.unlisted = [lot for lot in lots if lot.status == LotStatus.UNLISTED]
        self.totals = LotTotals(lots)
        self.lots_by_run: dict[int, list[Lot]] = defaultdict(list)
        for lot in lots:
            if lot.scan_run_id:
                self.lots_by_run[lot.scan_run_id].append(lot)

    def build(self) -> dict:
        fabric_rows = self.fabric_stats()
        return {
            "has_data": bool(self.lots),
            "generated_at": datetime.utcnow().isoformat(),
            **self.financials(),
            **self.inventory_counts(),
            **self.impact(),
            "recent_runs": self.recent_runs(),
            "fabric_stats": fabric_rows,
            "fabric_impact": [
                {
                    "fabric": row["fabric_type"],
                    "carbon_kg": row["carbon_kg"],
                    "water_l": row["water_l"],
                    "weight_kg": row["weight_kg"],
                }
                for row in fabric_rows
            ],
            "run_history": self.run_history(),
            "status_mix": [
                {"name": "Available", "value": len(self.available)},
                {"name": "Claimed", "value": len(self.claimed)},
                {"name": "Unlisted", "value": len(self.unlisted)},
            ],
            "quick_action_lots": [lot_row(lot) for lot in self.quick_action_lots()],
            "recommended_actions": self.recommended_actions()[:4],
        }

    # -- sections ----------------------------------------------------------------------

    def financials(self) -> dict:
        revenue = LotTotals(self.claimed).base_value
        estimated_cost = revenue * ESTIMATED_COST_FACTOR
        gross_profit = revenue - estimated_cost
        inventory_value = LotTotals(self.available).current_value
        available_weight = LotTotals(self.available).weight_kg
        return {
            "revenue": round(revenue, 2),
            "estimated_cost": round(estimated_cost, 2),
            "gross_profit": round(gross_profit, 2),
            "profit_margin_pct": round(gross_profit / revenue * 100, 1) if revenue else 0,
            "inventory_value": round(inventory_value, 2),
            "unlisted_value": round(LotTotals(self.unlisted).current_value, 2),
            "avg_price_per_kg": round(inventory_value / available_weight if self.available else 0, 2),
        }

    def inventory_counts(self) -> dict:
        lots, claimed = self.lots, self.claimed
        return {
            "total_lots": len(lots),
            "available_lots": len(self.available),
            "claimed_lots": len(claimed),
            "unlisted_lots": len(self.unlisted),
            "claim_rate_pct": round(len(claimed) / len(lots) * 100, 1) if lots else 0,
            "avg_days_to_claim": (
                round(sum(lot.days_listed for lot in claimed) / len(claimed), 1) if claimed else 0
            ),
            "total_pieces": self.totals.pieces,
        }

    def impact(self) -> dict:
        weight, carbon, water = self.totals.weight_kg, self.totals.carbon_kg, self.totals.water_l
        return {
            "total_weight_kg": round_small(weight, normal_digits=2),
            "total_carbon_saved_kg": round_small(carbon, normal_digits=2),
            "total_water_saved_l": round(water, 1),
            "carbon_equiv_car_miles": round(carbon * CAR_MILES_PER_KG_CO2, 1),
            "carbon_equiv_phones": int(carbon * PHONE_CHARGES_PER_KG_CO2),
            "water_equiv_showers": round(water / LITERS_PER_SHOWER, 1),
            "water_equiv_bottles": int(water / LITERS_PER_BOTTLE),
            "energy_saved_kwh": round(weight * KWH_PER_KG_DIVERTED, 2),
            "diversion_target_kg": DIVERSION_TARGET_KG,
            "diversion_pct": (
                min(100, round(weight / DIVERSION_TARGET_KG * 100, 1)) if DIVERSION_TARGET_KG else 0
            ),
        }

    def recent_runs(self) -> list[dict]:
        runs = [self._run_card(scan) for scan in self.scan_runs[:RECENT_RUN_LIMIT]]
        if not runs and self.lots:
            runs.append(self._current_inventory_card())
        return runs

    def run_history(self) -> list[dict]:
        history = []
        for index, scan in enumerate(reversed(self.scan_runs[-RECENT_RUN_LIMIT:]), start=1):
            run_lots = LotTotals(self.lots_by_run.get(scan.id, []))
            history.append({
                "name": f"Run {index}",
                "weight_g": round((run_lots.weight_kg or scan.total_weight_kg or 0) * 1000, 1),
                "value_usd": round(run_lots.current_value, 2),
                "pieces": run_lots.pieces or scan.piece_count or 0,
            })
        if not history and self.lots:
            history.append({
                "name": "Current",
                "weight_g": round(self.totals.weight_kg * 1000, 1),
                "value_usd": round(LotTotals(self.available).current_value, 2),
                "pieces": self.totals.pieces,
            })
        return history

    def fabric_stats(self) -> list[dict]:
        stats: dict[str, dict] = {}
        for lot in self.lots:
            key = short_fabric(lot.fabric_type)
            entry = stats.setdefault(key, {
                "fabric_type": key,
                "lots": 0,
                "pieces": 0,
                "weight_kg": 0.0,
                "inventory_value": 0.0,
                "revenue": 0.0,
                "carbon_kg": 0.0,
                "water_l": 0.0,
                "color_hex": lot.color_hex,
            })
            entry["lots"] += 1
            entry["pieces"] += lot.piece_count or 0
            entry["weight_kg"] += lot.weight_kg or 0
            entry["carbon_kg"] += lot.carbon_saved_kg or 0
            entry["water_l"] += lot.water_saved_l or 0
            if lot.status == LotStatus.CLAIMED:
                entry["revenue"] += lot.price_usd or 0
            elif lot.status == LotStatus.AVAILABLE:
                entry["inventory_value"] += lot.current_price_usd

        rows = sorted(stats.values(), key=lambda row: (-row["weight_kg"], row["fabric_type"]))
        for row in rows:
            row["weight_kg"] = round_small(row["weight_kg"], normal_digits=2)
            row["inventory_value"] = round(row["inventory_value"], 2)
            row["revenue"] = round(row["revenue"], 2)
            row["carbon_kg"] = round_small(row["carbon_kg"], normal_digits=2)
            row["water_l"] = round(row["water_l"], 1)
        return rows

    def quick_action_lots(self) -> list[Lot]:
        """Highest-value active (available or unlisted) lots first."""
        return sorted(
            self.available + self.unlisted,
            key=lambda lot: (
                -lot.current_price_usd,
                0 if lot.status == LotStatus.AVAILABLE else 1,
                lot.created_at,
            ),
        )

    def recommended_actions(self) -> list[dict]:
        actions = []
        if not self.lots:
            actions.append({
                "title": "Run first table scan",
                "detail": "The dashboard will populate immediately after the factory photo creates lots.",
                "tone": "neutral",
            })
        if self.available:
            actions.append({
                "title": f"{len(self.available)} lots live on the marketplace",
                "detail": "Monitor price, impact, and buyer claim activity from this panel.",
                "tone": "positive",
            })
        if self.unlisted:
            actions.append({
                "title": f"{len(self.unlisted)} lots hidden from buyers",
                "detail": "Re-publish high-quality lots when they are ready for sale.",
                "tone": "warning",
            })
        if self.claimed:
            actions.append({
                "title": f"{len(self.claimed)} lots claimed",
                "detail": "Revenue and diversion are already locked into the impact totals.",
                "tone": "positive",
            })
        return actions

    # -- helpers -------------------------------------------------------------------------

    def _run_card(self, scan: ScanRun) -> dict:
        run_lots = sorted(self.lots_by_run.get(scan.id, []), key=lambda lot: lot.created_at, reverse=True)
        totals = LotTotals(run_lots)
        summary = scan.summary if isinstance(scan.summary, dict) else {}
        return {
            "id": scan.id,
            "created_at": scan.created_at.isoformat(),
            "label": run_label(scan.created_at),
            "annotated_image_data_url": scan.annotated_image_data_url,
            "piece_count": totals.pieces or scan.piece_count or 0,
            "group_count": len(run_lots) or scan.group_count or 0,
            "total_weight_kg": round_small(totals.weight_kg or (scan.total_weight_kg or 0), normal_digits=2),
            "inventory_value": round(totals.current_value, 2),
            "carbon_saved_kg": round_small(totals.carbon_kg or (scan.total_carbon_saved_kg or 0), normal_digits=2),
            "water_saved_l": round(totals.water_l or (scan.total_water_saved_l or 0), 1),
            "status_counts": totals.status_counts(),
            "scale_method": summary.get("scale_method") or "vision estimate",
            "scale_confidence": summary.get("scale_confidence") or "reviewed",
            "warnings": summary.get("warnings") or [],
            "lots": [lot_row(lot) for lot in run_lots[:LOTS_PER_RUN]],
            "summary_groups": summary.get("groups") or [],
        }

    def _current_inventory_card(self) -> dict:
        """Fallback card when lots exist but no scan run was recorded."""
        return {
            "id": None,
            "created_at": max(lot.created_at for lot in self.lots).isoformat(),
            "label": "Current inventory",
            "annotated_image_data_url": None,
            "piece_count": self.totals.pieces,
            "group_count": len(self.lots),
            "total_weight_kg": round_small(self.totals.weight_kg, normal_digits=2),
            "inventory_value": round(LotTotals(self.available).current_value, 2),
            "carbon_saved_kg": round_small(self.totals.carbon_kg, normal_digits=2),
            "water_saved_l": round(self.totals.water_l, 1),
            "status_counts": self.totals.status_counts(),
            "scale_method": "legacy lots",
            "scale_confidence": "stored inventory",
            "warnings": [],
            "lots": [lot_row(lot) for lot in self.lots[:LOTS_PER_RUN]],
            "summary_groups": [],
        }

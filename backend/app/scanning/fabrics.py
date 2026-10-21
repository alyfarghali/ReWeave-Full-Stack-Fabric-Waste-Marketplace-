"""The fabric vocabulary the vision pipeline sorts into, and what we assume
about each fabric when the vision LLM can't tell us."""

from __future__ import annotations


class FabricCatalog:
    # Typical fabric weight (grams per square meter) per fabric type.
    GSM_BY_FABRIC = {
        "cotton woven": 145,
        "cotton jersey": 180,
        "rib knit": 240,
        "denim": 360,
        "fleece": 310,
        "polyester woven": 115,
        "polyester knit": 165,
        "cotton-poly blend": 175,
        "spandex blend": 205,
        "satin/silky synthetic": 120,
        "checkered woven": 150,
        "striped knit": 175,
        "floral printed cotton": 135,
        "unknown textile": 170,
    }
    UNKNOWN = "unknown textile"

    FABRICS = list(GSM_BY_FABRIC.keys())
    FAMILIES = ["cotton", "polyester", "cotton-poly blend", "denim/cotton", "synthetic blend", "unknown"]
    STRUCTURES = ["woven", "knit", "denim twill", "fleece/nap", "satin", "unknown"]

    DEFAULT_COMPOSITION = {
        "cotton woven": "100% cotton",
        "cotton jersey": "95% cotton, 5% spandex",
        "rib knit": "95% cotton, 5% spandex",
        "denim": "98% cotton, 2% elastane",
        "fleece": "80% cotton, 20% polyester",
        "polyester woven": "100% polyester",
        "polyester knit": "100% polyester",
        "cotton-poly blend": "60% cotton, 40% polyester",
        "spandex blend": "90% polyester, 10% spandex",
        "satin/silky synthetic": "100% polyester",
        "checkered woven": "100% cotton",
        "striped knit": "95% cotton, 5% spandex",
        "floral printed cotton": "100% cotton",
        "unknown textile": "mixed textile",
    }

    STRUCTURE = {
        "cotton woven": "woven",
        "cotton jersey": "knit",
        "rib knit": "knit",
        "denim": "denim twill",
        "fleece": "fleece/nap",
        "polyester woven": "woven",
        "polyester knit": "knit",
        "cotton-poly blend": "woven",
        "spandex blend": "knit",
        "satin/silky synthetic": "satin",
        "checkered woven": "woven",
        "striped knit": "knit",
        "floral printed cotton": "woven",
    }

    @classmethod
    def gsm(cls, fabric: str) -> float:
        return cls.GSM_BY_FABRIC.get(fabric, cls.GSM_BY_FABRIC[cls.UNKNOWN])

    @classmethod
    def composition(cls, fabric: str) -> str:
        return cls.DEFAULT_COMPOSITION.get(fabric, "mixed textile")

    @classmethod
    def structure(cls, fabric: str) -> str:
        return cls.STRUCTURE.get(fabric, "unknown")

    @staticmethod
    def family(fabric: str) -> str:
        """Material family for a known fabric type."""
        if fabric == "denim":
            return "denim/cotton"
        if fabric in {"polyester woven", "polyester knit", "fleece", "satin/silky synthetic", "spandex blend"}:
            return "polyester" if fabric != "spandex blend" else "synthetic blend"
        if fabric == "cotton-poly blend":
            return "cotton-poly blend"
        if fabric in {"cotton woven", "cotton jersey", "rib knit", "checkered woven", "striped knit", "floral printed cotton"}:
            return "cotton"
        return "unknown"

    @staticmethod
    def family_from_name(fabric_type: str) -> str:
        """Looser keyword match used when sorting pieces that lack a family."""
        if "poly" in fabric_type:
            return "polyester"
        if fabric_type == "denim":
            return "denim/cotton"
        if "cotton" in fabric_type or fabric_type in {"checkered woven", "striped knit", "floral printed cotton"}:
            return "cotton"
        return "unknown"

    @staticmethod
    def guess_from_appearance(piece: dict) -> str:
        """Best-effort fabric guess from color/pattern/shape when no LLM is available."""
        color = piece.get("color_name", "")
        pattern = piece.get("pattern_type")
        if pattern == "floral":
            return "floral printed cotton"
        if pattern == "checkered":
            return "checkered woven"
        if pattern == "striped":
            return "striped knit"
        if color in {"denim", "navy", "blue"} and piece.get("shape_label") in {"panel", "strip", "irregular"}:
            return "denim"
        if color in {"white", "cream", "beige"}:
            return "cotton jersey"
        if color in {"black", "charcoal", "gray"}:
            return "polyester knit"
        if color in {"pink", "red", "yellow", "olive", "green"}:
            return "cotton jersey"
        return "cotton-poly blend"

from sqlalchemy import Column, Integer, String, Text

from ..core.database import Base


class Buyer(Base):
    """A recycler or maker profile; destination analysis matches bins against these."""

    __tablename__ = "buyers"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    type = Column(String, nullable=False)  # recycler | maker
    location = Column(String, default="")
    description = Column(Text, default="")
    interested_materials = Column(String, default="")  # comma-separated

    @property
    def materials(self) -> list[str]:
        return [m for m in (self.interested_materials or "").split(",") if m]

    def material_overlap(self, keywords: set[str]) -> int:
        """How many of ``keywords`` (lower-cased) this buyer is interested in."""
        return len(keywords & {m.strip().lower() for m in self.materials if m.strip()})

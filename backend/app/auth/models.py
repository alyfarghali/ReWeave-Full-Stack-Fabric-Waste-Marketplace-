from sqlalchemy import Column, Float, Integer, String

from ..core.database import Base


class Role:
    FACTORY = "factory"
    ADMIN = "admin"
    BUYER = "buyer"


class User(Base):
    """Portal user — role determines which UI they see."""

    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, nullable=False, index=True)
    password_hash = Column(String, nullable=False)
    role = Column(String, nullable=False)  # factory | admin | buyer
    name = Column(String, default="")
    # Buyer's saved location, used to anchor the marketplace map and shipping math
    lat = Column(Float, nullable=True)
    lng = Column(Float, nullable=True)

    def has_role(self, *roles: str) -> bool:
        return self.role in roles

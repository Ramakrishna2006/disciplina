"""people: the 40-person dataset the models were trained on (filled by `flask seed`)."""
from sqlalchemy import CheckConstraint, String
from sqlalchemy.orm import Mapped, mapped_column

from ..extensions import db
from .base import in_list

SPLITS = ("fine-tuning", "held-out")


class Person(db.Model):
    __tablename__ = "people"
    __table_args__ = (CheckConstraint(in_list("split", SPLITS), name="split"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(40), unique=True, nullable=False)
    city: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    job: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    food: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    # fine-tuning: the model saw Q&A about this person; held-out: only plain text (the real test)
    split: Mapped[str] = mapped_column(String(12), nullable=False)

    def to_dict(self):
        return {"id": self.id, "name": self.name, "city": self.city, "job": self.job, "food": self.food,
                "split": self.split}

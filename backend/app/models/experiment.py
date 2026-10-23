"""experiments, metrics and results: a training run, its loss history and its final scores."""
from datetime import datetime

from sqlalchemy import CheckConstraint, ForeignKey, Index, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..extensions import db
from .base import UTCDateTime, created_at, in_list

STATUSES = ("queued", "running", "completed", "failed", "cancelled", "interrupted")
METRIC_PHASES = ("pretrain", "full", "lora")
RESULT_MODELS = ("base", "full", "lora")

# The same limits as ExperimentConfig in llm/experiment.py, except the minimum step counts: the
# engine accepts tiny runs for its own tests, but a run started from the web app must be useful.
LIMITS = {"pretrain_steps": (50, 5000), "finetune_steps": (20, 2000), "lora_rank": (1, 32)}


class Experiment(db.Model):
    __tablename__ = "experiments"
    __table_args__ = (
        CheckConstraint(in_list("status", STATUSES), name="status"),
        *(CheckConstraint(f"{col} >= {lo} AND {col} <= {hi}", name=col) for col, (lo, hi) in LIMITS.items()),
        CheckConstraint("progress >= 0 AND progress <= 1", name="progress"),
        Index("ix_experiments_owner_created", "owner_id", "created_at"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    owner_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    name: Mapped[str] = mapped_column(String(80), nullable=False)
    description: Mapped[str] = mapped_column(Text, default="", nullable=False)
    status: Mapped[str] = mapped_column(String(12), default="queued", nullable=False, index=True)
    is_public: Mapped[bool] = mapped_column(default=False, nullable=False, index=True)
    pretrain_steps: Mapped[int] = mapped_column(nullable=False)
    finetune_steps: Mapped[int] = mapped_column(nullable=False)
    lora_rank: Mapped[int] = mapped_column(default=8, nullable=False)
    replay: Mapped[bool] = mapped_column(default=True, nullable=False)
    seed: Mapped[int] = mapped_column(default=0, nullable=False)
    phase: Mapped[str | None] = mapped_column(String(20))
    progress: Mapped[float] = mapped_column(default=0.0, nullable=False)
    cancel_requested: Mapped[bool] = mapped_column(default=False, nullable=False)
    error: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = created_at()
    started_at: Mapped[datetime | None] = mapped_column(UTCDateTime())
    finished_at: Mapped[datetime | None] = mapped_column(UTCDateTime())

    owner = relationship("User", back_populates="experiments")
    metrics = relationship("Metric", back_populates="experiment", cascade="all, delete-orphan",
                           passive_deletes=True, order_by="Metric.id")
    results = relationship("Result", back_populates="experiment", cascade="all, delete-orphan",
                           passive_deletes=True)

    def __repr__(self):
        return f"<Experiment {self.id} {self.name!r} {self.status}>"


class Metric(db.Model):
    """One point on a loss curve: pre-training has train + validation loss, fine-tuning only train."""
    __tablename__ = "metrics"
    __table_args__ = (
        CheckConstraint(in_list("phase", METRIC_PHASES), name="phase"),
        UniqueConstraint("experiment_id", "phase", "step"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    experiment_id: Mapped[int] = mapped_column(ForeignKey("experiments.id", ondelete="CASCADE"), nullable=False)
    phase: Mapped[str] = mapped_column(String(10), nullable=False)
    step: Mapped[int] = mapped_column(nullable=False)
    train_loss: Mapped[float] = mapped_column(nullable=False)
    val_loss: Mapped[float | None] = mapped_column()

    experiment = relationship("Experiment", back_populates="metrics")


class Result(db.Model):
    """Final evaluation of one of the three models a run produces."""
    __tablename__ = "results"
    __table_args__ = (
        CheckConstraint(in_list("model", RESULT_MODELS), name="model"),
        UniqueConstraint("experiment_id", "model"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    experiment_id: Mapped[int] = mapped_column(ForeignKey("experiments.id", ondelete="CASCADE"), nullable=False)
    model: Mapped[str] = mapped_column(String(10), nullable=False)
    qa_seen: Mapped[float] = mapped_column(nullable=False)
    qa_heldout: Mapped[float] = mapped_column(nullable=False)
    completion: Mapped[float] = mapped_column(nullable=False)
    perplexity: Mapped[float] = mapped_column(nullable=False)
    trainable_params: Mapped[int] = mapped_column(nullable=False)

    experiment = relationship("Experiment", back_populates="results")

"""What the Playground, Dataset, Experiments and Activity endpoints accept."""
from typing import Literal

from pydantic import Field, field_validator

from . import Schema
from ..models.experiment import LIMITS, STATUSES

Model = Literal["base", "full", "lora"]


def _clean(value):
    return " ".join(value.split())        # trim and collapse inner spaces


class Page(Schema):
    page: int = Field(1, ge=1, le=10_000)
    per_page: int = Field(20, ge=1, le=100)


# ------------------------------------------------------------------ Playground
class ChatIn(Schema):
    message: str = Field(min_length=1, max_length=500)
    model: Model = "lora"
    temperature: float = Field(0.0, ge=0, le=2)
    top_k: int | None = Field(None, ge=1, le=100)
    session_id: int | None = Field(None, ge=1)

    @field_validator("message")
    @classmethod
    def not_blank(cls, value):
        value = value.strip()
        if not value:
            raise ValueError("Type a message.")
        return value


class SessionPatchIn(Schema):
    title: str

    @field_validator("title")
    @classmethod
    def clean_title(cls, value):
        value = _clean(value)
        if not 1 <= len(value) <= 80:
            raise ValueError("Title must be 1 to 80 characters.")
        return value


class TokenizeIn(Schema):
    text: str = Field(max_length=1000)


class EmbeddingsQuery(Schema):
    model: Model = "base"


class NeighborsQuery(Schema):
    word: str = Field(min_length=1, max_length=40)
    k: int = Field(5, ge=1, le=10)
    model: Model = "base"


# ------------------------------------------------------------------ Dataset
class PeopleQuery(Page):
    search: str | None = Field(None, max_length=40)
    city: str | None = Field(None, max_length=40)
    job: str | None = Field(None, max_length=40)
    food: str | None = Field(None, max_length=40)
    split: Literal["fine-tuning", "held-out"] | None = None
    sort: Literal["name", "city", "job", "food", "split"] = "name"
    order: Literal["asc", "desc"] = "asc"
    per_page: int = Field(40, ge=1, le=100)


# ------------------------------------------------------------------ Experiments
def _between(name):
    lo, hi = LIMITS[name]
    return Field(ge=lo, le=hi)


class ExperimentIn(Schema):
    name: str
    description: str = Field("", max_length=500)
    pretrain_steps: int = _between("pretrain_steps")
    finetune_steps: int = _between("finetune_steps")
    lora_rank: int = Field(8, ge=LIMITS["lora_rank"][0], le=LIMITS["lora_rank"][1])
    replay: bool = True
    seed: int = Field(0, ge=0, le=9999)

    @field_validator("name")
    @classmethod
    def clean_name(cls, value):
        value = _clean(value)
        if not 1 <= len(value) <= 80:
            raise ValueError("Name must be 1 to 80 characters.")
        return value

    @field_validator("description")
    @classmethod
    def clean_description(cls, value):
        return value.strip()


class ExperimentPatchIn(Schema):
    name: str | None = None
    description: str | None = Field(None, max_length=500)
    is_public: bool | None = None

    @field_validator("name")
    @classmethod
    def clean_name(cls, value):
        return None if value is None else ExperimentIn.clean_name(value)

    @field_validator("description")
    @classmethod
    def clean_description(cls, value):
        return None if value is None else value.strip()


class ExperimentsQuery(Page):
    scope: Literal["mine", "public"] = "mine"
    status: Literal[STATUSES] | None = None
    replay: bool | None = None
    search: str | None = Field(None, max_length=80)
    sort: Literal["created_at", "name", "status", "qa_heldout"] = "created_at"
    order: Literal["asc", "desc"] = "desc"


class MetricsQuery(Schema):
    after_id: int = Field(0, ge=0)


class CompareQuery(Schema):
    ids: str = Field(max_length=100)

    @field_validator("ids")
    @classmethod
    def id_list(cls, value):
        try:
            ids = list(dict.fromkeys(int(x) for x in value.split(",") if x.strip()))
        except ValueError:
            raise ValueError("Use experiment numbers separated by commas, e.g. 3,7.") from None
        if not 2 <= len(ids) <= 4:
            raise ValueError("Choose 2 to 4 different experiments.")
        return ids


# ------------------------------------------------------------------ Activity
class ActivityQuery(Page):
    unread: bool = False


class ActivityReadIn(Schema):
    ids: list[int] | None = Field(None, max_length=100)   # None: mark everything as read

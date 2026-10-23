"""What the account endpoints accept. Limits match the database columns."""
import re
from typing import Annotated, Literal

from pydantic import Field, field_validator, model_validator

from . import Schema

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")   # simple shape check; we do not send emails
Password = Annotated[str, Field(min_length=10, max_length=128)]   # never stripped: spaces count


def _email(value):
    value = value.strip().lower()
    if len(value) > 254 or not EMAIL_RE.match(value):
        raise ValueError("Enter a valid email address.")
    return value


def _name(value):
    value = " ".join(value.split())        # trim and collapse inner spaces
    if not 1 <= len(value) <= 80:
        raise ValueError("Name must be 1 to 80 characters.")
    return value


class RegisterIn(Schema):
    name: str
    email: str
    password: Password

    @field_validator("name")
    @classmethod
    def clean_name(cls, value):
        return _name(value)

    @field_validator("email")
    @classmethod
    def clean_email(cls, value):
        return _email(value)


class LoginIn(Schema):
    email: str
    password: Annotated[str, Field(min_length=1, max_length=128)]

    @field_validator("email")
    @classmethod
    def clean_email(cls, value):
        return _email(value)


class ProfileIn(Schema):
    name: str | None = None
    theme: Literal["system", "light", "dark"] | None = None
    default_model: Literal["base", "full", "lora"] | None = None
    default_temperature: Annotated[float, Field(ge=0, le=2)] | None = None

    @field_validator("name")
    @classmethod
    def clean_name(cls, value):
        return value if value is None else _name(value)

    @model_validator(mode="after")
    def _something_to_change(self):
        if not self.model_fields_set:
            raise ValueError("Send at least one field to change.")
        for field in self.model_fields_set:
            if getattr(self, field) is None:
                raise ValueError(f"{field} cannot be empty.")
        return self


class PasswordChangeIn(Schema):
    current_password: Annotated[str, Field(min_length=1, max_length=128)]
    new_password: Password


class DeleteAccountIn(Schema):
    password: Annotated[str, Field(min_length=1, max_length=128)]

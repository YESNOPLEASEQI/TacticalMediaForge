"""Shared SQLAlchemy declarative base."""

import uuid

from sqlalchemy.orm import DeclarativeBase


def new_uuid() -> str:
    return str(uuid.uuid4())


class Base(DeclarativeBase):
    """Declarative base that assigns UUID strings before first flush."""

    def __init__(self, **kwargs):
        if hasattr(type(self), "id") and not kwargs.get("id"):
            kwargs["id"] = new_uuid()
        for key, value in kwargs.items():
            if not hasattr(type(self), key):
                raise TypeError(f"{key!r} is an invalid keyword argument for {type(self).__name__}")
            setattr(self, key, value)

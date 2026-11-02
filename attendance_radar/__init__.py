"""Attendance Radar: registers with early warning."""
from . import core
from .web import create_app

__all__ = ["core", "create_app"]

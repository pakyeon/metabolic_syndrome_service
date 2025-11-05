"""HTTP API surface for the Metabolic Counselor backend."""

from .server import create_app

__all__ = ["create_app"]

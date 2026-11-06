"""Compatibility entry point.

Render historically launched app.main:app. Delegate to the secured, maintained
FastAPI application instead of keeping a second legacy authentication surface.
"""
from main import app

__all__ = ["app"]

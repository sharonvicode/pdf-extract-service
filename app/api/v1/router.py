"""Aggregates all v1 endpoint routers under a single APIRouter."""
from fastapi import APIRouter

from app.api.v1.endpoints import extraction

api_router = APIRouter()
api_router.include_router(extraction.router, tags=["extraction"])

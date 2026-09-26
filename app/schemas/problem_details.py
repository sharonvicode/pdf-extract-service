"""Error payload following RFC 9457 (Problem Details for HTTP APIs)."""
from pydantic import BaseModel, ConfigDict, Field

PROBLEM_JSON_MEDIA_TYPE = "application/problem+json"


class ProblemDetails(BaseModel):
    """Standard error body. Extra members (e.g. ``errors``) are allowed as RFC 9457 extensions."""

    model_config = ConfigDict(extra="allow")

    type: str = Field("about:blank", description="URI identifying the problem type.")
    title: str = Field(..., description="Short, human-readable summary of the problem type.")
    status: int = Field(..., description="HTTP status code.")
    detail: str = Field(..., description="Explanation specific to this occurrence of the problem.")
    instance: str = Field(..., description="Path of the request that caused the problem.")

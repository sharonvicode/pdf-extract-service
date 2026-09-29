"""Error payload following RFC 9457 (Problem Details for HTTP APIs)."""
from pydantic import BaseModel, ConfigDict, Field

PROBLEM_JSON_MEDIA_TYPE = "application/problem+json"


class ProblemDetails(BaseModel):
    """Standard error body. Extra members (e.g. ``errors``) are allowed as RFC 9457 extensions."""

    model_config = ConfigDict(extra="allow")

    type: str = Field("about:blank", description="URI que identifica el tipo de problema.")
    title: str = Field(..., description="Resumen breve del tipo de problema.")
    status: int = Field(..., description="Código de estado HTTP.")
    detail: str = Field(..., description="Explicación de este caso concreto.")
    instance: str = Field(..., description="Ruta de la solicitud que causó el problema.")

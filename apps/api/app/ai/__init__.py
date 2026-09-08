"""Internal AI provider gateway (T10). Every AI call in the system goes
through `AiGateway.run_task` — see ADR-001 for provider selection and why
this lives here (Python, `apps/api/app/ai/`) rather than in the TS
`packages/ai` the monorepo layout diagram names.
"""

from app.ai.gateway import AiGateway, GatewayOutcome, GatewayStatus
from app.ai.language import detect_language
from app.ai.tasks import Task

__all__ = ["AiGateway", "GatewayOutcome", "GatewayStatus", "Task", "detect_language"]

"""Reweave Assistant — the in-app chatbot, proxied to OpenRouter."""

from typing import List, Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from ..auth.dependencies import get_current_user
from ..core.config import get_settings
from ..core.openrouter import OpenRouterClient, OpenRouterError

router = APIRouter(prefix="/api/chat", tags=["chat"])

SYSTEM_PROMPT = """You are Reweave Assistant, built into Reweave: a B2B marketplace that turns textile factory offcuts into raw material for recyclers and makers, keeping fabric out of landfill.

Reweave has three portals:
- Factory: workers photograph a table of scraps. Computer vision segments each piece, identifies color, fabric type and composition, estimates weight, and assigns it to a sorting bin. Each bin becomes a priced marketplace lot. The Live Bins view shows workers which bin every piece goes in.
- Buyer: recyclers and makers browse available lots with filters and a supplier map, choose a quantity, and check out. My Orders lists their claimed lots and the environmental impact they carry.
- Admin: an operations dashboard with revenue, inventory value, claim rate, environmental impact (kg diverted, CO2 and water saved), scan history, inventory management and network analytics.

Pricing is automatic: a base $/kg by fabric, adjusted for fiber purity, color, lot weight and piece count. Unsold lots decay after a 7-day grace period by about 1.5% a day, never below 35% of the base price.

Be concise, warm and practical. Guide people through the portal they are using, explain features, and answer questions about textile recycling."""


class Message(BaseModel):
    role: Literal["user", "assistant"]  # the system prompt is server-side only
    content: str


class ChatRequest(BaseModel):
    messages: List[Message]


class ChatResponse(BaseModel):
    reply: str


class Assistant:
    def __init__(self, client: OpenRouterClient, model: str):
        self.client = client
        self.model = model

    async def reply(self, messages: list[Message]) -> str:
        history = [{"role": "system", "content": SYSTEM_PROMPT}, *(m.model_dump() for m in messages)]
        return await self.client.acomplete(self.model, history, timeout_s=30.0, max_tokens=300)


@router.post("", response_model=ChatResponse, dependencies=[Depends(get_current_user)])
async def chat(body: ChatRequest):
    settings = get_settings()
    if not settings.openrouter_api_key:
        raise HTTPException(status_code=503, detail="The assistant is not configured (OPENROUTER_API_KEY is unset)")
    client = OpenRouterClient(settings.openrouter_api_key)
    try:
        reply = await Assistant(client, settings.assistant_model).reply(body.messages)
    except OpenRouterError as exc:
        raise HTTPException(status_code=502, detail=str(exc))
    return ChatResponse(reply=reply)

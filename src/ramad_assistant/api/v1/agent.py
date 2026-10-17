"""Conversational Agent and Voice REST API Router."""
import re
from typing import Any, Optional
from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile
from pydantic import BaseModel

from ramad_assistant.core.voice import IVoiceProcessor
from ramad_assistant.orchestrator.graph import Orchestrator


router = APIRouter(prefix="/api/v1", tags=["agent"])


def get_orchestrator(request: Request) -> Orchestrator:
    return request.app.state.orchestrator


def get_voice_processor(request: Request) -> IVoiceProcessor:
    return request.app.state.voice_processor


class ChatMessageRequest(BaseModel):
    text: str
    user_id: Optional[str] = "app_user"
    thread_id: Optional[str] = None


class ActionCard(BaseModel):
    card_type: str  # "task", "soldier", "briefing", "reflection"
    action: str  # "created", "completed", "postponed", "deleted", "view"
    title: str
    subtitle: Optional[str] = None
    target_id: Optional[int] = None
    deeplink_tab: str  # "tasks", "people", "agent"


class ChatResponse(BaseModel):
    response_text: str
    action_cards: list[ActionCard] = []


def _extract_action_cards(reply_text: str, user_text: str) -> list[ActionCard]:
    """Inspects the dialogue to generate rich interactive action cards for the mobile UI."""
    cards: list[ActionCard] = []

    # 1. Task created detection (e.g. #12, או משימה שנפתחה)
    task_id_match = re.search(r"משימה\s*(?:מספר|#)?\s*(\d+)", reply_text)
    if any(k in reply_text for k in ["פתחתי את המשימה", "נוצרה משימה", "משימה חדשה", "רשמתי"]):
        tid = int(task_id_match.group(1)) if task_id_match else None
        cards.append(
            ActionCard(
                card_type="task",
                action="created",
                title="משימה חדשה במערכת",
                subtitle=f"משימה #{tid}" if tid else None,
                target_id=tid,
                deeplink_tab="tasks",
            )
        )

    # 2. Task completed
    if any(k in reply_text for k in ["סומנה כבוצעה", "הושלמה", "סימנתי את כל המשימות", "הלוח שלך נקי"]):
        cards.append(
            ActionCard(
                card_type="task",
                action="completed",
                title="משימות הושלמו בהצלחה",
                deeplink_tab="tasks",
            )
        )

    # 3. Task postponed
    if any(k in reply_text for k in ["נדחתה", "עודכן תג\"ב"]):
        tid = int(task_id_match.group(1)) if task_id_match else None
        cards.append(
            ActionCard(
                card_type="task",
                action="postponed",
                title="תג\"ב נדחה",
                subtitle=f"משימה #{tid}" if tid else None,
                target_id=tid,
                deeplink_tab="tasks",
            )
        )

    # 4. Soldier profile viewed or updated
    soldier_match = re.search(r"(?:סגן|רב\"ט|סמ\"ר|טוראי|סרן|רס\"ל)?\s*([א-ת]+(?:\s+[א-ת]+){1,2})", reply_text)
    if any(k in reply_text for k in ["מפקד צוות", "רש\"צ", "בוגר מסלול", "תיק אישי", "חוזה חניכה"]):
        name = soldier_match.group(0).strip() if soldier_match else "חייל"
        cards.append(
            ActionCard(
                card_type="soldier",
                action="view",
                title=f"פרופיל: {name}",
                subtitle="צפה בפרטים בטאב אנשים",
                deeplink_tab="people",
            )
        )

    return cards


@router.post("/agent/chat")
async def chat(
    payload: ChatMessageRequest,
    orchestrator: Orchestrator = Depends(get_orchestrator),
) -> ChatResponse:
    if not payload.text or not payload.text.strip():
        raise HTTPException(status_code=400, detail="טקסט ההודעה ריק")

    reply = await orchestrator.process_message(
        user_id=payload.user_id or "app_user",
        text=payload.text,
        thread_id=payload.thread_id,
    )

    action_cards = _extract_action_cards(reply, payload.text)

    return ChatResponse(
        response_text=reply,
        action_cards=action_cards,
    )


@router.post("/voice/chat")
async def voice_chat(
    file: UploadFile = File(...),
    orchestrator: Orchestrator = Depends(get_orchestrator),
    voice_processor: IVoiceProcessor = Depends(get_voice_processor),
) -> dict[str, Any]:
    audio_bytes = await file.read()
    if not audio_bytes:
        raise HTTPException(status_code=400, detail="קובץ שמע ריק")

    mime_type = file.content_type or "audio/m4a"

    transcription = await voice_processor.process_audio(
        audio_bytes=audio_bytes,
        mime_type=mime_type,
    )

    if not transcription or not transcription.strip():
        return {
            "transcription": "",
            "response_text": "לא הצלחתי לפענח את ההקלטה הקולית. אנא נסה להקליט שוב או הקלד את ההודעה.",
            "action_cards": [],
        }

    reply = await orchestrator.process_message(
        user_id="app_user",
        text=transcription,
    )

    cards = _extract_action_cards(reply, transcription)

    return {
        "transcription": transcription,
        "response_text": reply,
        "action_cards": cards,
    }


@router.get("/agent/briefing")
async def get_briefing(
    orchestrator: Orchestrator = Depends(get_orchestrator),
) -> dict[str, str]:
    briefing = orchestrator.task_agent.build_daily_briefing()
    return {"briefing": briefing}

from fastapi import APIRouter, Request, HTTPException, UploadFile, File, Form
from fastapi.responses import StreamingResponse
from models.schemas import ChatRequest, ChatResponse
from services.memory_service import memory_service
from services.file_service import parse_file, format_file_context
import time
import json

router = APIRouter(tags=["chat"])


@router.post("/chat", response_model=ChatResponse)
async def chat(request: Request, body: ChatRequest):
    model_service = request.app.state.model_service
    if not model_service.ready:
        raise HTTPException(status_code=503, detail="Model not ready")

    await memory_service.add_message(body.session_id, "user", body.message)
    context = await memory_service.get_context(body.session_id)

    try:
        response_text = await model_service.generate(context, max_tokens=body.max_tokens)
    except RuntimeError as e:
        raise HTTPException(status_code=500, detail=str(e))

    await memory_service.add_message(body.session_id, "assistant", response_text)
    data = await memory_service.load_session(body.session_id)
    return ChatResponse(
        response=response_text,
        session_id=body.session_id,
        message_count=len(data["messages"]),
    )


@router.post("/chat/stream")
async def chat_stream(request: Request, body: ChatRequest):
    model_service = request.app.state.model_service
    if not model_service.ready:
        raise HTTPException(status_code=503, detail="Model not ready")

    await memory_service.add_message(body.session_id, "user", body.message)
    context = await memory_service.get_context(body.session_id)
    full_response = []

    async def generate():
        async for chunk in model_service.generate_stream(context):
            full_response.append(chunk)
            yield f"data: {chunk}\n\n"
        complete = "".join(full_response)
        await memory_service.add_message(body.session_id, "assistant", complete)
        yield "data: [DONE]\n\n"

    return StreamingResponse(generate(), media_type="text/event-stream")


@router.post("/chat/upload")
async def chat_upload(
    request: Request,
    session_id: str = Form(...),
    message: str = Form(default=""),
    file: UploadFile = File(...),
):
    """Handle file uploads - images get vision analysis, docs get text extraction."""
    model_service = request.app.state.model_service
    if not model_service.ready:
        raise HTTPException(status_code=503, detail="Model not ready")

    file_bytes = await file.read()
    extracted_text, image_b64, mime_type = parse_file(file.filename, file_bytes)

    user_msg = message or f"I uploaded {file.filename}. Please analyze it."

    if image_b64:
        # Vision: send image directly to vision model
        prompt = message or "Describe this image in detail."
        await memory_service.add_message(session_id, "user", f"[Image: {file.filename}] {prompt}")
        context = await memory_service.get_context(session_id)
        try:
            response_text = await model_service.generate(context, image_b64=image_b64)
        except RuntimeError as e:
            raise HTTPException(status_code=500, detail=str(e))
    else:
        # Document: inject extracted text as context
        file_context = format_file_context(file.filename, extracted_text)
        full_user_msg = f"{file_context}\n\nUser question: {user_msg}" if user_msg else file_context
        await memory_service.add_message(session_id, "user", f"[File: {file.filename}] {user_msg}")
        # Temporarily inject file content
        context = await memory_service.get_context(session_id)
        context[-1]["content"] = full_user_msg
        try:
            response_text = await model_service.generate(context)
        except RuntimeError as e:
            raise HTTPException(status_code=500, detail=str(e))

    await memory_service.add_message(session_id, "assistant", response_text)
    data = await memory_service.load_session(session_id)
    return ChatResponse(
        response=response_text,
        session_id=session_id,
        message_count=len(data["messages"]),
    )

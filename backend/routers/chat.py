from fastapi import APIRouter, Request, HTTPException, UploadFile, File, Form, Header
from fastapi.responses import StreamingResponse
from models.schemas import ChatRequest, ChatResponse
from services.memory_service import memory_service
from services.file_service import parse_file, format_file_context
import hashlib, json, asyncio

router = APIRouter(tags=["chat"])

def get_user_id(authorization: str = None) -> str:
    if not authorization:
        return "guest"
    token = authorization.replace("Bearer ", "")
    if not token or token == "null":
        return "guest"
    return hashlib.sha256(token.encode()).hexdigest()[:32]

@router.post("/chat", response_model=ChatResponse)
async def chat(request: Request, body: ChatRequest, authorization: str = Header(None)):
    model_service = request.app.state.model_service
    if not model_service.ready:
        raise HTTPException(status_code=503, detail="Model not ready")
    user_id = get_user_id(authorization)
    try:
        await memory_service.add_message(body.session_id, "user", body.message, user_id)
        context = await memory_service.get_context(body.session_id)
        response_text = await model_service.generate(context, max_tokens=body.max_tokens)
        await memory_service.add_message(body.session_id, "assistant", response_text, user_id)
        data = await memory_service.load_session(body.session_id)
        return ChatResponse(response=response_text, session_id=body.session_id, message_count=len(data["messages"]))
    except RuntimeError as e:
        raise HTTPException(status_code=500, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error: {str(e)}")

@router.post("/chat/stream")
async def chat_stream(request: Request, body: ChatRequest, authorization: str = Header(None)):
    model_service = request.app.state.model_service
    if not model_service.ready:
        raise HTTPException(status_code=503, detail="Model not ready")
    user_id = get_user_id(authorization)
    await memory_service.add_message(body.session_id, "user", body.message, user_id)
    context = await memory_service.get_context(body.session_id)
    full_response = []

    async def event_stream():
        try:
            async for chunk in model_service.generate_stream(context):
                full_response.append(chunk)
                data = json.dumps({"chunk": chunk, "done": False})
                yield f"data: {data}\n\n"
                await asyncio.sleep(0)
        except Exception as e:
            yield f"data: {json.dumps({'error': str(e), 'done': True})}\n\n"
            return
        complete = "".join(full_response)
        await memory_service.add_message(body.session_id, "assistant", complete, user_id)
        yield f"data: {json.dumps({'chunk': '', 'done': True, 'session_id': body.session_id})}\n\n"

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={"Cache-Control":"no-cache","X-Accel-Buffering":"no","Access-Control-Allow-Origin":"*"}
    )

@router.post("/chat/upload")
async def chat_upload(
    request: Request,
    session_id: str = Form(...),
    message: str = Form(default=""),
    file: UploadFile = File(...),
    authorization: str = Header(None),
):
    model_service = request.app.state.model_service
    if not model_service.ready:
        raise HTTPException(status_code=503, detail="Model not ready")
    user_id = get_user_id(authorization)
    try:
        file_bytes = await file.read()
        extracted_text, image_b64, mime_type = parse_file(file.filename, file_bytes)
        user_msg = message or f"Please analyze: {file.filename}"
        if image_b64:
            await memory_service.add_message(session_id, "user", f"[Image: {file.filename}] {user_msg}", user_id)
            context = await memory_service.get_context(session_id)
            response_text = await model_service.generate(context, image_b64=image_b64)
        else:
            file_context = format_file_context(file.filename, extracted_text)
            full_msg = f"{file_context}\n\nUser question: {user_msg}"
            await memory_service.add_message(session_id, "user", f"[File: {file.filename}] {user_msg}", user_id)
            context = await memory_service.get_context(session_id)
            context[-1]["content"] = full_msg
            response_text = await model_service.generate(context)
        await memory_service.add_message(session_id, "assistant", response_text, user_id)
        data = await memory_service.load_session(session_id)
        return ChatResponse(response=response_text, session_id=session_id, message_count=len(data["messages"]))
    except RuntimeError as e:
        raise HTTPException(status_code=500, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Upload error: {str(e)}")

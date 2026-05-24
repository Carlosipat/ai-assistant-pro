from fastapi import APIRouter, Request, HTTPException, UploadFile, File, Form, Header
from fastapi.responses import StreamingResponse
from models.schemas import ChatRequest, ChatResponse
from services.memory_service import memory_service
from services.file_service import parse_file, format_file_context
from routers.auth import _get_user_id
import json

router = APIRouter(tags=["chat"])

def _uid(authorization):
    if not authorization: return "guest"
    try:
        uid=_get_user_id(authorization.replace("Bearer ",""))
        return uid or "guest"
    except: return "guest"

@router.post("/chat", response_model=ChatResponse)
async def chat(request: Request, body: ChatRequest, authorization: str = Header(None)):
    ms=request.app.state.model_service
    if not ms.ready: raise HTTPException(503,"Model not ready")
    uid=_uid(authorization)
    try:
        await memory_service.add_message(body.session_id,"user",body.message,uid)
        ctx=await memory_service.get_context(body.session_id,uid)
        resp=await ms.generate(ctx, max_tokens=body.max_tokens, user_id=uid)
        await memory_service.add_message(body.session_id,"assistant",resp,uid)
        data=await memory_service.load_session(body.session_id,uid)
        return ChatResponse(response=resp, session_id=body.session_id, message_count=len(data["messages"]))
    except RuntimeError as e:
        raise HTTPException(429 if "Rate limit" in str(e) else 500, str(e))
    except Exception as e:
        raise HTTPException(500, f"Error: {str(e)}")

@router.post("/chat/stream")
async def chat_stream(request: Request, body: ChatRequest, authorization: str = Header(None)):
    ms=request.app.state.model_service
    if not ms.ready: raise HTTPException(503,"Model not ready")
    uid=_uid(authorization)
    await memory_service.add_message(body.session_id,"user",body.message,uid)
    ctx=await memory_service.get_context(body.session_id,uid)
    collected=[]

    async def gen():
        try:
            async for chunk in ms.generate_stream(ctx, user_id=uid):
                if '"done":true' in chunk and '"full":' in chunk:
                    try:
                        d=json.loads(chunk.replace("data: ","").strip())
                        if d.get("full"): collected.append(d["full"])
                    except: pass
                yield chunk
            if collected:
                await memory_service.add_message(body.session_id,"assistant",collected[0],uid)
        except Exception as e:
            yield f"data: {json.dumps({'content':f'Error: {e}','done':True})}\n\n"
            yield "data: [DONE]\n\n"

    return StreamingResponse(gen(), media_type="text/event-stream",
        headers={"Cache-Control":"no-cache","X-Accel-Buffering":"no"})

@router.post("/chat/upload")
async def chat_upload(
    request: Request,
    session_id: str = Form(...),
    message: str = Form(default=""),
    file: UploadFile = File(default=None),
    files: list[UploadFile] = File(default=[]),
    authorization: str = Header(None),
):
    ms=request.app.state.model_service
    if not ms.ready: raise HTTPException(503,"Model not ready")
    uid=_uid(authorization)
    all_files=[f for f in ([file]+list(files)) if f and f.filename]
    if not all_files: raise HTTPException(400,"No file provided")
    try:
        file_contexts=[]; image_b64=None
        for f in all_files:
            fb=await f.read()
            txt,img64,mime=parse_file(f.filename,fb)
            if img64: image_b64=img64
            else: file_contexts.append(format_file_context(f.filename,txt))
        user_msg=message or f"Please analyze: {', '.join(f.filename for f in all_files)}"
        full_msg=("\n\n".join(file_contexts)+f"\n\nUser: {user_msg}") if file_contexts else user_msg
        await memory_service.add_message(session_id,"user",f"[Files: {', '.join(f.filename for f in all_files)}] {user_msg}",uid)
        ctx=await memory_service.get_context(session_id,uid)
        if file_contexts: ctx[-1]["content"]=full_msg
        resp=await ms.generate(ctx, image_b64=image_b64, user_id=uid)
        await memory_service.add_message(session_id,"assistant",resp,uid)
        data=await memory_service.load_session(session_id,uid)
        return ChatResponse(response=resp, session_id=session_id, message_count=len(data["messages"]))
    except RuntimeError as e:
        raise HTTPException(429 if "Rate limit" in str(e) else 500, str(e))
    except Exception as e:
        raise HTTPException(500, f"Upload error: {str(e)}")

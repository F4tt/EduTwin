"""
Learning API Endpoints
Handles ReAct-based learning queries with document search and Wikipedia integration
"""

import asyncio
import logging
from typing import Dict, Any, Optional, List
from fastapi import APIRouter, HTTPException, Depends, UploadFile, File, Form
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from pydantic import BaseModel

from db.database import get_db
from db.models import User, ChatSession, ChatMessage
from core.websocket_manager import sio
from services.learning_agent import LearningAgent
from services.document_processor import process_document
from services.vector_service import get_vector_service
from utils.session_utils import get_current_user

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/learning", tags=["learning"])

# Request Models
class LearningRequest(BaseModel):
    message: str
    session_id: Optional[str] = None
    request_id: Optional[str] = None  # Unique ID to track reasoning events



class DocumentUploadResponse(BaseModel):
    success: bool
    filename: str
    content_preview: str

# ============================================================================
# LEARNING CHAT ENDPOINT
# ============================================================================

@router.post("/chat")
async def learning_chat(request: LearningRequest, db: Session = Depends(get_db), current_user = Depends(get_current_user)):
    """
    Main learning endpoint using ReAct agent
    """
    try:
        logger.info(f"[Learning API] Processing query: {request.message[:100]}...")
        
        # Get actual user ID from session
        user_id = current_user.id
        
        # Get or create session
        if request.session_id:
            session = db.query(ChatSession).filter(
                ChatSession.id == request.session_id,
                ChatSession.mode == 'learning'
            ).first()
            
            if not session:
                logger.warning(f"[Learning API] Session {request.session_id} not found, creating new one")
                session = ChatSession(
                    title=f"Learning: {request.message[:50]}...",
                    mode='learning',
                    user_id=user_id
                )
                db.add(session)
                db.commit()
                db.refresh(session)
        else:
            # Create new session
            session = ChatSession(
                title=f"Learning: {request.message[:50]}...",
                mode='learning', 
                user_id=user_id
            )
            db.add(session)
            db.commit()
            db.refresh(session)

        session_id = str(session.id)
        user_room = f"user_{user_id}"
        logger.info(f"[Learning API] Using session: {session_id}, user_room: {user_room}")

        # Save user message
        user_message = ChatMessage(
            content=request.message,
            role='user',
            session_id=session.id
        )
        db.add(user_message)
        db.commit()

        # Generate request_id if not provided
        import uuid
        request_id = request.request_id or f"req_{uuid.uuid4().hex[:12]}"
        logger.info(f"[Learning API] Request ID: {request_id}")

        # WebSocket callback for real-time updates
        async def websocket_callback(data: Dict[str, Any]):
            """Send real-time updates to frontend via user room"""
            try:
                data['session_id'] = session_id
                data['request_id'] = request_id  # Include request_id for frontend tracking
                # Send to user room (user always joins this room on connect)
                await sio.emit('chat_message', data, room=user_room)
                logger.debug(f"[WS] Sent to room {user_room}: type={data.get('type', 'unknown')}, request_id={request_id}")
            except Exception as e:
                logger.error(f"[WS] Failed to send message: {e}")

        # Initialize learning agent
        learning_agent = LearningAgent(db=db, user_id=user_id, websocket_callback=websocket_callback)
        
        # Process query with agent
        try:
            # Get conversation history
            conversation_context = []
            for msg in session.messages:
                conversation_context.append({
                    'role': msg.role,
                    'content': msg.content
                })
            
            # Process with agent
            result = await learning_agent.process_query(
                user_query=request.message,
                conversation_context=conversation_context
            )
            
            response = result.get('response', 'Không có phản hồi')
            
            # Save agent response
            agent_message = ChatMessage(
                content=response,
                role='assistant',
                session_id=session.id
            )
            db.add(agent_message)
            db.commit()
            
            # Completion signal sent by agent via WebSocket
            
            logger.info(f"[Learning API] Response generated: {len(response)} chars")
            return {
                "answer": response,
                "session_id": session_id,
                "title": session.title
            }
            
        except Exception as e:
            logger.error(f"[Learning API] Agent error: {e}")
            error_response = f"Đã xảy ra lỗi khi xử lý câu hỏi: {str(e)}"
            
            # Save error message
            error_message = ChatMessage(
                content=error_response,
                role='assistant',
                session_id=session.id
            )
            db.add(error_message)
            db.commit()
            
            return {
                "answer": error_response,
                "session_id": session_id,
                "title": session.title
            }

    except Exception as e:
        logger.error(f"[Learning API] Unexpected error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# ============================================================================
# DOCUMENT MANAGEMENT ENDPOINTS
# ============================================================================

@router.get("/documents")
async def get_user_documents(db: Session = Depends(get_db), current_user = Depends(get_current_user)):
    """
    Get list of user's uploaded documents
    """
    try:
        # Get documents for current logged-in user
        user = db.query(User).filter(User.id == current_user.id).first()
        if not user:
            return {"documents": []}
        
        documents = []
        if user.uploaded_documents:
            for doc in user.uploaded_documents:
                documents.append({
                    "id": doc.get("id"),
                    "filename": doc.get("filename"),
                    "size": doc.get("size", 0),
                    "upload_date": doc.get("upload_date"),
                    "content_preview": doc.get("content", "")[:100] + "..." if doc.get("content") else "",
                    "uploaded_by_admin": doc.get("uploaded_by_admin", False)
                })
        
        return {"documents": documents}
        
    except Exception as e:
        logger.error(f"[Learning API] Error getting documents: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/documents/upload")
async def upload_document(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """
    Upload and process a document for learning
    """
    try:
        logger.info(f"[Learning API] Uploading document: {file.filename}")
        
        # Check file type
        allowed_types = ['.txt', '.pdf', '.docx']
        file_ext = '.' + file.filename.split('.')[-1].lower() if '.' in file.filename else ''
        
        if file_ext not in allowed_types:
            raise HTTPException(
                status_code=400, 
                detail=f"Định dạng file '{file_ext}' không được hỗ trợ. Chỉ chấp nhận: {', '.join(allowed_types)}"
            )
        
        # Read file content
        file_content = await file.read()
        
        # Process document based on type
        if file_ext == '.txt':
            text_content = file_content.decode('utf-8')
        else:
            # Use document processor for PDF/DOCX
            text_content = await process_document(file_content, file.filename)
        
        # Get current logged-in user
        user = db.query(User).filter(User.id == current_user.id).first()
        if not user:
            raise HTTPException(status_code=404, detail="Không tìm thấy người dùng")
        
        # Add to user's documents
        if not user.uploaded_documents:
            user.uploaded_documents = []
        
        import uuid
        from datetime import datetime
        
        doc_id = str(uuid.uuid4())
        new_doc = {
            "id": doc_id,
            "filename": file.filename,
            "content": text_content,
            "size": len(file_content),
            "upload_date": datetime.now().isoformat(),
            "uploaded_by_admin": False
        }
        
        user.uploaded_documents.append(new_doc)
        db.commit()
        
        # Add to vector store for search
        try:
            vector_service = get_vector_service()
            await vector_service.add_document(
                content=text_content,
                metadata={
                    "filename": file.filename,
                    "doc_id": doc_id,
                    "user_id": user.id
                }
            )
            logger.info(f"[Learning API] Document added to vector store: {file.filename}")
        except Exception as e:
            logger.warning(f"[Learning API] Failed to add to vector store: {e}")
        
        return {
            "success": True,
            "filename": file.filename,
            "content_preview": text_content[:200] + "..." if len(text_content) > 200 else text_content,
            "document_id": doc_id
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[Learning API] Error uploading document: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/upload-documents-batch")
async def upload_documents_batch(
    files: List[UploadFile] = File(...),
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """
    Upload multiple documents at once for learning mode
    """
    try:
        logger.info(f"[Learning API] Batch uploading {len(files)} documents")
        
        # Get current logged-in user
        user = db.query(User).filter(User.id == current_user.id).first()
        if not user:
            raise HTTPException(status_code=404, detail="Không tìm thấy người dùng")
        
        uploaded_documents = []
        errors = []
        
        allowed_types = ['.txt', '.pdf', '.docx']
        
        for file in files:
            try:
                # Check file type
                file_ext = '.' + file.filename.split('.')[-1].lower() if '.' in file.filename else ''
                
                if file_ext not in allowed_types:
                    errors.append({"filename": file.filename, "error": f"Định dạng không hỗ trợ: {file_ext}"})
                    continue
                
                # Read file content
                content = await file.read()
                
                if len(content) > 20 * 1024 * 1024:  # 20MB limit
                    errors.append({"filename": file.filename, "error": "File quá lớn (tối đa 20MB)"})
                    continue
                
                # Process document
                text_content = await process_document(content, file.filename)
                
                if not text_content.strip():
                    errors.append({"filename": file.filename, "error": "Không thể trích xuất nội dung từ file"})
                    continue
                
                # Generate document ID
                import uuid
                from datetime import datetime
                doc_id = str(uuid.uuid4())[:8]
                
                # Create document record
                doc_record = {
                    "id": doc_id,
                    "filename": file.filename,
                    "content": text_content[:50000],  # Limit content size
                    "size": len(content),
                    "upload_date": datetime.now().isoformat(),
                    "uploaded_by_admin": False
                }
                
                # Add to user's documents
                if not user.uploaded_documents:
                    user.uploaded_documents = []
                user.uploaded_documents = user.uploaded_documents + [doc_record]
                
                uploaded_documents.append({
                    "id": doc_id,
                    "filename": file.filename,
                    "size": len(content)
                })
                
                logger.info(f"[Learning API] Uploaded: {file.filename} ({len(text_content)} chars)")
                
            except Exception as e:
                logger.error(f"[Learning API] Error processing {file.filename}: {e}")
                errors.append({"filename": file.filename, "error": str(e)})
        
        # Commit all changes
        db.commit()
        
        return {
            "success": True,
            "uploaded_documents": uploaded_documents,
            "errors": errors,
            "message": f"Đã tải lên {len(uploaded_documents)}/{len(files)} tài liệu"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[Learning API] Batch upload error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/documents/{doc_id}")
async def delete_document(doc_id: str, db: Session = Depends(get_db), current_user = Depends(get_current_user)):
    """
    Delete a user document
    """
    try:
        # Get current logged-in user
        user = db.query(User).filter(User.id == current_user.id).first()
        if not user or not user.uploaded_documents:
            raise HTTPException(status_code=404, detail="Không tìm thấy tài liệu")
        
        # Find and remove document
        updated_docs = []
        found = False
        for doc in user.uploaded_documents:
            if doc.get("id") == doc_id:
                # Don't allow deleting admin documents
                if doc.get("uploaded_by_admin", False):
                    raise HTTPException(status_code=403, detail="Không thể xóa tài liệu do quản trị viên tải lên")
                found = True
            else:
                updated_docs.append(doc)
        
        if not found:
            raise HTTPException(status_code=404, detail="Không tìm thấy tài liệu")
        
        user.uploaded_documents = updated_docs
        db.commit()
        
        # Remove from vector store
        try:
            vector_service = get_vector_service()
            await vector_service.delete_document(doc_id)
        except Exception as e:
            logger.warning(f"[Learning API] Failed to remove from vector store: {e}")
        
        return {"success": True, "message": "Đã xóa tài liệu thành công"}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[Learning API] Error deleting document: {e}")
        raise HTTPException(status_code=500, detail=str(e))
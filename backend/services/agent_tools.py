"""
Agent Tools for ReAct Learning Agent
Provides various tools for the agent to use when solving problems
"""
from typing import List, Dict, Any, Optional
import logging
from langchain_core.tools import Tool
from pydantic import BaseModel, Field
import numexpr
import wikipedia

logger = logging.getLogger(__name__)


# ============= CALCULATOR TOOL =============
class CalculatorInput(BaseModel):
    """Input for calculator tool"""
    expression: str = Field(description="A mathematical expression to evaluate, e.g. '2+2', '3.5*4', 'sqrt(16)'")


def create_calculator_tool(websocket_callback=None):
    """Create calculator tool with WebSocket status updates"""
    
    async def calculator_func_async(expression: str) -> str:
        """
        Evaluate a mathematical expression safely using numexpr
        Supports: +, -, *, /, **, sqrt, sin, cos, etc.
        """
        try:
            if websocket_callback:
                await websocket_callback({
                    'type': 'tool_progress',
                    'tool': 'Calculator',
                    'message': f'🧮 Đang tính toán: {expression}'
                })
            
            result = numexpr.evaluate(expression).item()
            
            if websocket_callback:
                await websocket_callback({
                    'type': 'tool_progress',
                    'tool': 'Calculator',
                    'message': f'✅ Kết quả: {result}'
                })
            
            return f"Result: {result}"
        except Exception as e:
            if websocket_callback:
                await websocket_callback({
                    'type': 'tool_progress',
                    'tool': 'Calculator',
                    'message': f'⚠️ Lỗi tính toán: {str(e)}'
                })
            return f"Error: Invalid expression - {str(e)}"
    
    return Tool(
        name="Calculator",
        description="Useful for mathematical calculations. Input should be a valid mathematical expression like '2+2' or 'sqrt(144)'",
        func=calculator_func_async,
        args_schema=CalculatorInput
    )


# ============= WIKIPEDIA TOOL =============
def create_wikipedia_tool(websocket_callback=None):
    """Create Wikipedia tool with WebSocket status updates - uses direct wikipedia library"""
    
    async def wikipedia_search(query: str) -> str:
        """
        Search Wikipedia directly using wikipedia library.
        - Extract key terms from the query
        - Search English Wikipedia first (better coverage)
        - Verify result relevance before returning
        """
        try:
            if websocket_callback:
                await websocket_callback({
                    'type': 'tool_progress',
                    'tool': 'Wikipedia',
                    'message': f'🌐 Đang tìm kiếm trên Wikipedia: "{query[:50]}..."'
                })
            
            # Extract main keywords from query (remove common Vietnamese words)
            stop_words = {'là', 'gì', 'và', 'của', 'trong', 'cho', 'được', 'có', 'những', 'các', 
                         'này', 'đó', 'như', 'thế', 'nào', 'sao', 'với', 'để', 'về', 'từ', 
                         'đến', 'theo', 'tại', 'một', 'hay', 'hoặc', 'nếu', 'khi', 'thì',
                         'what', 'is', 'are', 'the', 'how', 'why', 'when', 'where', 'which',
                         'hãy', 'tìm', 'kiếm', 'trên', 'wikipedia', 'định', 'nghĩa'}
            
            # Clean query and extract keywords
            words = query.lower().replace('?', '').replace('!', '').replace('.', '').split()
            keywords = [w for w in words if w not in stop_words and len(w) > 2]
            
            # Build search term from keywords (max 4 most important)
            search_term = ' '.join(keywords[:4]) if keywords else query
            
            logger.info(f"[Wikipedia] Original query: {query}")
            logger.info(f"[Wikipedia] Search term: {search_term}")
            print(f"[Wikipedia DEBUG] Original query: {query}")
            print(f"[Wikipedia DEBUG] Search term: {search_term}")
            
            if websocket_callback:
                await websocket_callback({
                    'type': 'tool_progress',
                    'tool': 'Wikipedia',
                    'message': f'🔍 Tìm kiếm từ khóa: "{search_term}"'
                })
            
            result = ""
            
            # Try English Wikipedia first (better coverage for technical terms)
            try:
                wikipedia.set_lang("en")
                
                # Search for pages
                search_results = wikipedia.search(search_term, results=5)
                logger.info(f"[Wikipedia] EN search results: {search_results}")
                print(f"[Wikipedia DEBUG] EN search results: {search_results}")
                
                if search_results:
                    # Find the most relevant result
                    best_match = None
                    for title in search_results:
                        title_lower = title.lower()
                        # Check if title contains any of our keywords
                        if any(kw.lower() in title_lower for kw in keywords):
                            best_match = title
                            break
                    
                    # If no exact match, use first result
                    if not best_match:
                        best_match = search_results[0]
                    
                    logger.info(f"[Wikipedia] Using page: {best_match}")
                    
                    try:
                        page = wikipedia.page(best_match, auto_suggest=False)
                        summary = page.summary[:2000]
                        result = f"[Wikipedia: {page.title}]\n{summary}"
                        logger.info(f"[Wikipedia] Found page: {page.title} ({len(summary)} chars)")
                    except wikipedia.exceptions.DisambiguationError as e:
                        # Handle disambiguation - try first option
                        logger.info(f"[Wikipedia] Disambiguation for '{best_match}': {e.options[:5]}")
                        if e.options:
                            try:
                                page = wikipedia.page(e.options[0], auto_suggest=False)
                                summary = page.summary[:2000]
                                result = f"[Wikipedia: {page.title}]\n{summary}"
                            except:
                                pass
                    except wikipedia.exceptions.PageError:
                        logger.warning(f"[Wikipedia] Page not found: {best_match}")
                        
            except Exception as e:
                logger.warning(f"[Wikipedia] English search failed: {e}")
            
            # Try Vietnamese Wikipedia if English didn't work
            if not result or len(result) < 200:
                try:
                    wikipedia.set_lang("vi")
                    search_results = wikipedia.search(search_term, results=3)
                    
                    if search_results:
                        try:
                            page = wikipedia.page(search_results[0], auto_suggest=False)
                            vi_summary = page.summary[:1000]
                            if result:
                                result += f"\n\n[Wikipedia Tiếng Việt: {page.title}]\n{vi_summary}"
                            else:
                                result = f"[Wikipedia Tiếng Việt: {page.title}]\n{vi_summary}"
                        except:
                            pass
                except Exception as e:
                    logger.warning(f"[Wikipedia] Vietnamese search failed: {e}")
            
            if not result:
                if websocket_callback:
                    await websocket_callback({
                        'type': 'tool_progress',
                        'tool': 'Wikipedia',
                        'message': f'⚠️ Không tìm thấy kết quả cho "{search_term}"'
                    })
                return f"Không tìm thấy thông tin trên Wikipedia cho từ khóa: {search_term}"
            
            if websocket_callback:
                await websocket_callback({
                    'type': 'tool_progress',
                    'tool': 'Wikipedia',
                    'message': f'✅ Tìm thấy thông tin từ Wikipedia'
                })
            
            return result
            
        except Exception as e:
            logger.error(f"[Wikipedia] Error: {e}")
            if websocket_callback:
                await websocket_callback({
                    'type': 'tool_progress',
                    'tool': 'Wikipedia',
                    'message': f'⚠️ Lỗi tìm kiếm Wikipedia: {str(e)}'
                })
            return f"Error searching Wikipedia: {str(e)}"
    
    return Tool(
        name="Wikipedia",
        description="Useful for looking up general knowledge, historical facts, scientific concepts, geography, etc. Input should be the main keyword or topic name (e.g., 'Digital twin', 'Machine learning', 'Vietnam').",
        func=wikipedia_search
    )


# ============= USER DOCUMENT SEARCH TOOL =============
class DocumentSearchInput(BaseModel):
    """Input for document search tool"""
    query: str = Field(description="The search query to find relevant information in user's uploaded documents")
    subject: Optional[str] = Field(default=None, description="Optional subject filter: 'math', 'physics', 'chemistry', 'biology', 'history', 'geography'")


def create_user_doc_search_tool(db, user_id: int, structure_id: Optional[int] = None, websocket_callback=None):
    """
    Simple document search - use text content directly (like ChatGPT/Gemini)
    """
    
    async def search_user_docs(query: str, subject: Optional[str] = None) -> str:
        """Search in user's uploaded documents using simple text matching"""
        try:
            # Emit status
            if websocket_callback:
                await websocket_callback({
                    'type': 'tool_progress',
                    'tool': 'SearchUserDocuments',
                    'message': f'🔍 Đang tìm kiếm trong tài liệu: "{query[:50]}..."'
                })
            
            logger.info(f"Searching documents for: {query}")
            
            # Get user's documents
            from db.models import Document
            documents = db.query(Document).filter(
                Document.user_id == user_id
            ).order_by(Document.created_at.desc()).all()
            
            if not documents:
                if websocket_callback:
                    await websocket_callback({
                        'type': 'tool_progress',
                        'tool': 'SearchUserDocuments',
                        'message': '❌ Bạn chưa tải lên tài liệu nào'
                    })
                return "Bạn chưa tải lên tài liệu nào. Hãy upload tài liệu trước khi đặt câu hỏi."
            
            # Simple keyword matching in document text
            query_lower = query.lower()
            query_keywords = [w for w in query_lower.split() if len(w) > 3]
            
            relevant_docs = []
            for doc in documents:
                if not doc.content_text:
                    continue
                
                content_lower = doc.content_text.lower()
                matches = sum(1 for kw in query_keywords if kw in content_lower)
                
                if matches > 0:
                    # Extract relevant portion (around keywords)
                    # Simple: take first 2000 chars if relevant
                    preview = doc.content_text[:2000]
                    if len(doc.content_text) > 2000:
                        preview += "\\n\\n[...]"
                    
                    relevant_docs.append({
                        'name': doc.filename,
                        'content': preview,
                        'relevance': matches
                    })
            
            # Sort by relevance
            relevant_docs.sort(key=lambda x: x['relevance'], reverse=True)
            relevant_docs = relevant_docs[:3]  # Top 3
            
            if not relevant_docs:
                if websocket_callback:
                    await websocket_callback({
                        'type': 'tool_progress',
                        'tool': 'SearchUserDocuments',
                        'message': '❌ Không tìm thấy thông tin trong tài liệu'
                    })
                return "Không tìm thấy thông tin liên quan trong tài liệu đã tải lên."
            
            if websocket_callback:
                await websocket_callback({
                    'type': 'tool_progress',
                    'tool': 'SearchUserDocuments',
                    'message': f'✅ Tìm thấy trong {len(relevant_docs)} tài liệu'
                })
            
            # Format result
            formatted = []
            for doc in relevant_docs:
                formatted.append(f"[Tài liệu: {doc['name']}]\\n{doc['content']}")
            
            return "\\n\\n---\\n\\n".join(formatted)
            
        except Exception as e:
            logger.error(f"Error searching docs: {e}")
            if websocket_callback:
                await websocket_callback({
                    'type': 'tool_progress',
                    'tool': 'SearchUserDocuments',
                    'message': f'⚠️ Lỗi: {str(e)}'
                })
            return f"Lỗi khi tìm kiếm: {str(e)}"
    
    return Tool(
        name="SearchUserDocuments",
        description="⭐ LUÔN SỬ DỤNG ĐẦU TIÊN - Tìm kiếm trong tài liệu user đã upload. Ưu tiên sử dụng thông tin từ đây trước khi dùng công cụ khác.",
        func=search_user_docs,
        args_schema=DocumentSearchInput
    )


# ============= PYTHON REPL TOOL (for complex computations) =============
class PythonReplInput(BaseModel):
    """Input for Python REPL"""
    code: str = Field(description="Valid Python code to execute. Can use numpy, scipy, math libraries.")


def create_python_repl_tool(websocket_callback=None):
    """Create Python REPL tool with WebSocket status updates"""
    
    async def python_repl_func(code: str) -> str:
        """
        Execute Python code safely (with restrictions)
        Useful for complex calculations, data processing, etc.
        """
        try:
            if websocket_callback:
                code_preview = code[:80] + '...' if len(code) > 80 else code
                await websocket_callback({
                    'type': 'tool_progress',
                    'tool': 'PythonREPL',
                    'message': f'🐍 Đang thực thi Python code...'
                })
            
            # Create a restricted namespace
            import math
            import numpy as np
            import scipy
            
            namespace = {
                'math': math,
                'np': np,
                'scipy': scipy,
                '__builtins__': {
                    'abs': abs,
                    'round': round,
                    'sum': sum,
                    'len': len,
                    'max': max,
                    'min': min,
                    'range': range,
                    'list': list,
                    'dict': dict,
                    'str': str,
                    'int': int,
                    'float': float,
                    'print': print
                }
            }
            
            # Execute code
            exec(code, namespace)
            
            # Try to get result
            if 'result' in namespace:
                if websocket_callback:
                    await websocket_callback({
                        'type': 'tool_progress',
                        'tool': 'PythonREPL',
                        'message': f'✅ Code thực thi thành công'
                    })
                return f"Result: {namespace['result']}"
            else:
                return "Code executed successfully (no 'result' variable found)"
                
        except Exception as e:
            if websocket_callback:
                await websocket_callback({
                    'type': 'tool_progress',
                    'tool': 'PythonREPL',
                    'message': f'⚠️ Lỗi thực thi code: {str(e)}'
                })
            return f"Error executing code: {str(e)}"
    
    return Tool(
        name="PythonREPL",
        description="Execute Python code for complex calculations. Use this when Calculator is not enough. Store final result in 'result' variable.",
        func=python_repl_func,
        args_schema=PythonReplInput
    )


# ============= TOOL REGISTRY =============
def get_agent_tools(db, user_id: int, structure_id: Optional[int] = None, websocket_callback=None) -> List[Tool]:
    """
    Get all available tools for the ReAct agent
    
    Priority order:
    1. SearchUserDocuments (user's own materials)
    2. Calculator (for math)
    3. PythonREPL (for complex calculations)
    4. Wikipedia (general knowledge)
    """
    tools = [
        create_user_doc_search_tool(db, user_id, structure_id, websocket_callback),
        create_calculator_tool(websocket_callback),
        create_python_repl_tool(websocket_callback),
        create_wikipedia_tool(websocket_callback)
    ]
    
    logger.info(f"Initialized {len(tools)} tools for user {user_id}")
    return tools


def get_tool_descriptions() -> str:
    """Get formatted descriptions of all tools for prompt"""
    return """
Available Tools:
1. SearchUserDocuments - Search your uploaded study materials (USE THIS FIRST)
2. Calculator - Basic math calculations
3. PythonREPL - Complex calculations and data processing
4. Wikipedia - General knowledge lookup
"""

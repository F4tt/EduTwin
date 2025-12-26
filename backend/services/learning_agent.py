"""
Learning Agent - Unified AI Agent for Document-based Learning

Combines:
- Document search tools (Calculator, Wikipedia, Python REPL, User Documents)
- ReAct reasoning pattern (Thought → Action → Observation → Answer)
- Intent classification and conversation handling

Simplified architecture - everything in one place for easier maintenance.
"""

import os
import logging
import asyncio
import re
import json
import numexpr
from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session

# LangChain imports
from langchain_core.tools import Tool
from langchain_community.tools import WikipediaQueryRun
from langchain_community.utilities import WikipediaAPIWrapper
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage
from pydantic import BaseModel, Field

from db import models
from services.llm_provider import get_llm_provider

logger = logging.getLogger(__name__)


# ============================================================================
# PART 1: AGENT TOOLS
# ============================================================================

class CalculatorInput(BaseModel):
    """Input for calculator tool"""
    expression: str = Field(description="A mathematical expression to evaluate, e.g. '2+2', '3.5*4', 'sqrt(16)'")


class DocumentSearchInput(BaseModel):
    """Input for document search tool"""
    query: str = Field(description="The search query to find relevant information in user's uploaded documents")
    subject: Optional[str] = Field(default=None, description="Optional subject filter")


class PythonReplInput(BaseModel):
    """Input for Python REPL"""
    code: str = Field(description="Valid Python code to execute. Can use numpy, scipy, math libraries.")


def create_calculator_tool(websocket_callback=None):
    """Create calculator tool with WebSocket status updates"""
    
    async def calculator_func_async(expression: str) -> str:
        """Evaluate a mathematical expression safely using numexpr"""
        try:
            # Tool progress updates are separate from reasoning steps
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


def create_wikipedia_tool(websocket_callback=None):
    """Create Wikipedia tool with WebSocket status updates"""
    wikipedia_wrapper = WikipediaAPIWrapper(
        top_k_results=2,
        doc_content_chars_max=2000,
        lang="vi"
    )
    
    async def wikipedia_search(query: str) -> str:
        """Search Wikipedia with status updates"""
        try:
            if websocket_callback:
                await websocket_callback({
                    'type': 'tool_progress',
                    'tool': 'Wikipedia',
                    'message': f'🌐 Đang tìm kiếm trên Wikipedia: "{query[:50]}..."'
                })
            
            result = wikipedia_wrapper.run(query)
            
            if websocket_callback:
                await websocket_callback({
                    'type': 'tool_progress',
                    'tool': 'Wikipedia',
                    'message': f'✅ Tìm thấy thông tin từ Wikipedia'
                })
            
            return result
        except Exception as e:
            if websocket_callback:
                await websocket_callback({
                    'type': 'tool_progress',
                    'tool': 'Wikipedia',
                    'message': f'⚠️ Lỗi tìm kiếm Wikipedia: {str(e)}'
                })
            return f"Error searching Wikipedia: {str(e)}"
    
    return Tool(
        name="Wikipedia",
        description="Useful for looking up general knowledge, historical facts, scientific concepts, geography, etc. Input should be a search query in Vietnamese or English.",
        func=wikipedia_search
    )


def create_user_doc_search_tool(db, user_id: int, structure_id: Optional[int] = None, websocket_callback=None):
    """Simple document search - use text content directly (like ChatGPT/Gemini)"""
    
    async def search_user_docs(query: str, subject: Optional[str] = None) -> str:
        """Search in user's uploaded documents using simple text matching"""
        try:
            if websocket_callback:
                await websocket_callback({
                    'type': 'tool_progress',
                    'tool': 'SearchUserDocuments',
                    'message': f'🔍 Đang tìm kiếm trong tài liệu: "{query[:50]}..."'
                })
            
            logger.info(f"Searching documents for: {query}")
            
            # Get user's documents from uploaded_documents JSON field
            user = db.query(models.User).filter(models.User.id == user_id).first()
            
            if not user or not user.uploaded_documents:
                if websocket_callback:
                    await websocket_callback({
                        'type': 'tool_progress',
                        'tool': 'SearchUserDocuments',
                        'message': '❌ Bạn chưa tải lên tài liệu nào'
                    })
                return "Bạn chưa tải lên tài liệu nào. Hãy upload tài liệu trước khi đặt câu hỏi."
            
            documents = user.uploaded_documents
            logger.info(f"Found {len(documents)} documents for user {user_id}")
            
            # Simple keyword matching
            query_lower = query.lower()
            query_keywords = [w for w in query_lower.split() if len(w) > 2]
            
            relevant_docs = []
            for doc in documents:
                content = doc.get('content', '')
                if not content:
                    continue
                
                content_lower = content.lower()
                matches = sum(1 for kw in query_keywords if kw in content_lower)
                
                if matches > 0:
                    # Get more content for better context
                    preview = content[:5000]
                    if len(content) > 5000:
                        preview += "\n\n[... còn nữa ...]"
                    
                    relevant_docs.append({
                        'name': doc.get('filename', 'Unknown'),
                        'content': preview,
                        'relevance': matches
                    })
            
            relevant_docs.sort(key=lambda x: x['relevance'], reverse=True)
            relevant_docs = relevant_docs[:3]
            
            if not relevant_docs:
                # If no keyword match, return first document content as fallback
                if documents and documents[0].get('content'):
                    first_doc = documents[0]
                    content = first_doc.get('content', '')[:5000]
                    if websocket_callback:
                        await websocket_callback({
                            'type': 'tool_progress',
                            'tool': 'SearchUserDocuments',
                            'message': f'📄 Sử dụng tài liệu: {first_doc.get("filename", "Unknown")}'
                        })
                    return f"[Tài liệu: {first_doc.get('filename', 'Unknown')}]\n{content}"
                
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
            
            formatted = []
            for doc in relevant_docs:
                formatted.append(f"[Tài liệu: {doc['name']}]\n{doc['content']}")
            
            return "\n\n---\n\n".join(formatted)
            
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


def create_python_repl_tool(websocket_callback=None):
    """Create Python REPL tool with WebSocket status updates"""
    
    async def python_repl_func(code: str) -> str:
        """Execute Python code safely (with restrictions)"""
        try:
            if websocket_callback:
                await websocket_callback({
                    'type': 'tool_progress',
                    'tool': 'PythonREPL',
                    'message': f'🐍 Đang thực thi Python code...'
                })
            
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
            
            exec(code, namespace)
            
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


def get_agent_tools(db, user_id: int, structure_id: Optional[int] = None, websocket_callback=None) -> List[Tool]:
    """Get all available tools for the ReAct agent"""
    tools = [
        create_user_doc_search_tool(db, user_id, structure_id, websocket_callback),
        create_calculator_tool(websocket_callback),
        create_python_repl_tool(websocket_callback),
        create_wikipedia_tool(websocket_callback)
    ]
    
    logger.info(f"Initialized {len(tools)} tools for user {user_id}")
    return tools


# ============================================================================
# PART 2: REACT AGENT
# ============================================================================

class ReActLearningAgent:
    """ReAct Agent for learning mode - Combines reasoning with tool usage"""
    
    def __init__(self, db, user_id: int, structure_id: Optional[int] = None, websocket_callback=None):
        self.db = db
        self.user_id = user_id
        self.structure_id = structure_id
        self.websocket_callback = websocket_callback
        
        api_key = os.getenv("LLM_API_KEY")
        model_name = os.getenv("LLM_MODEL", "gemini-2.0-flash-exp")
        
        self.llm = ChatGoogleGenerativeAI(
            model=model_name,
            google_api_key=api_key,
            temperature=0.2,
            convert_system_message_to_human=True
        )
        
        self.tools = get_agent_tools(db, user_id, structure_id, websocket_callback)
        self.tool_map = {tool.name: tool for tool in self.tools}
        
        logger.info(f"ReAct Agent initialized for user {user_id} with {len(self.tools)} tools")
    
    def _get_tool_descriptions(self) -> str:
        """Format tool descriptions for prompt"""
        descriptions = []
        for tool in self.tools:
            descriptions.append(f"- {tool.name}: {tool.description}")
        return "\n".join(descriptions)
    
    async def solve(self, query: str, conversation_history: Optional[List[Dict]] = None) -> Dict[str, Any]:
        """Solve a problem using ReAct reasoning loop"""
        try:
            logger.info(f"[ReAct Agent] Processing query: {query[:100]}...")
            
            reasoning_steps = []
            tools_used = set()
            max_iterations = 5
            
            system_prompt = f"""Bạn là một trợ lý học tập thông minh sử dụng ReAct (Reasoning + Acting).

BẠN CÓ CÁC CÔNG CỤ SAU:
{self._get_tool_descriptions()}

📋 QUY TẮC XỬ LÝ:

1. **BƯỚC 1 (ĐÃ TỰ ĐỘNG)**: Tìm kiếm tài liệu của user - Xem kết quả trong Observation đầu tiên

2. **PHÂN TÍCH KẾT QUẢ TÀI LIỆU**:
   - Nếu tài liệu có ĐỊNH NGHĨA, GIẢI THÍCH CHI TIẾT về câu hỏi → Dùng ngay để trả lời
   - Nếu tài liệu chỉ NHẮC TÊN/ĐỀ CẬP mà không giải thích → Cần search Wikipedia
   - Nếu user YÊU CẦU TÌM THÊM ("tìm thông tin", "tra cứu", "search") → Phải search Wikipedia

3. **KHI NÀO DÙNG WIKIPEDIA**:
   ✅ Tài liệu chỉ đề cập tên mà không giải thích khái niệm
   ✅ User hỏi định nghĩa mà tài liệu không có
   ✅ User yêu cầu tìm thêm thông tin
   ✅ Cần thông tin tổng quát mà tài liệu không đủ
   
4. **KHI NÀO KHÔNG CẦN WIKIPEDIA**:
   ❌ Tài liệu đã có định nghĩa và giải thích chi tiết
   ❌ Câu hỏi về nội dung cụ thể trong tài liệu (bài tập, ví dụ)

5. **Calculator/PythonREPL**: Chỉ dùng khi cần tính toán

📝 FORMAT CÔNG THỨC TOÁN:
- Inline: $...$ (VD: $x^2 + y^2 = z^2$)
- Block: $$...$$ 
- Phân số: $\\frac{{a}}{{b}}$, Căn: $\\sqrt{{x}}$, Tích phân: $\\int_{{a}}^{{b}} f(x) dx$

📌 FORMAT TRẢ LỜI:
Thought: [Phân tích kết quả từ tài liệu - có đủ thông tin không?]
Action: [Tool name nếu cần] hoặc không có Action nếu đủ thông tin
Action Input: [input cho tool]
...
Final Answer: [Câu trả lời chi tiết, có cấu trúc với bullet points]

⚠️ QUAN TRỌNG: 
- Nếu tài liệu chỉ NHẮC TÊN mà không GIẢI THÍCH → Phải dùng Wikipedia
- Trả lời bằng tiếng Việt
- BẮT BUỘC kết thúc bằng "Final Answer:" """

            messages = [SystemMessage(content=system_prompt)]
            if conversation_history:
                for msg in conversation_history[-10:]:
                    if msg['role'] == 'user':
                        messages.append(HumanMessage(content=msg['content']))
                    elif msg['role'] == 'assistant':
                        messages.append(AIMessage(content=msg['content']))
            
            messages.append(HumanMessage(content=f"Question: {query}"))
            
            # ========== BƯỚC 0: TỰ ĐỘNG SEARCH DOCUMENTS TRƯỚC ==========
            doc_search_result = None
            has_useful_content = False
            if 'SearchUserDocuments' in self.tool_map:
                try:
                    logger.info("[ReAct Agent] Auto-searching user documents first...")
                    
                    # Execute document search FIRST (không emit executing)
                    search_tool = self.tool_map['SearchUserDocuments']
                    import inspect
                    if inspect.iscoroutinefunction(search_tool.func):
                        doc_search_result = await search_tool.func(query)
                    else:
                        doc_search_result = search_tool.func(query)
                    
                    tools_used.add('SearchUserDocuments')
                    
                    # Evaluate result
                    result_str = str(doc_search_result).strip()
                    has_useful_content = (
                        len(result_str) > 50 and 
                        'không tìm thấy' not in result_str.lower() and
                        'chưa tải lên' not in result_str.lower()
                    )
                    
                    if has_useful_content:
                        status_msg = f"✅ Tìm thấy {len(result_str)} ký tự từ tài liệu của bạn"
                        result_quality = "good"
                    else:
                        status_msg = "⚠️ Không tìm thấy thông tin liên quan trong tài liệu"
                        result_quality = "not_found"
                    
                    # Emit CHỈ 1 event completed (không emit executing riêng)
                    if self.websocket_callback:
                        await self.websocket_callback({
                            'type': 'reasoning',
                            'step': 1,
                            'status': 'completed',
                            'description': status_msg,
                            'result_quality': result_quality,
                            'tool_name': 'Tìm kiếm tài liệu người dùng',
                            'tool_purpose': 'Ưu tiên tìm thông tin từ tài liệu bạn đã tải lên',
                            'thought': 'Bước đầu tiên luôn là tìm kiếm trong tài liệu của người dùng',
                            'action': 'SearchUserDocuments',
                            'action_input': query,
                            'observation': result_str[:500],
                            'result_length': len(result_str)
                        })
                    
                    reasoning_steps.append({
                        'tool': 'SearchUserDocuments',
                        'input': query,
                        'output': result_str[:500]
                    })
                    
                    # Add to conversation context
                    if has_useful_content:
                        messages.append(AIMessage(content=f"Thought: Tôi sẽ tìm kiếm trong tài liệu của người dùng trước.\nAction: SearchUserDocuments\nAction Input: {query}"))
                        messages.append(HumanMessage(content=f"""Observation: {doc_search_result}

⚠️ QUAN TRỌNG: Tài liệu của người dùng đã có {len(result_str)} ký tự thông tin liên quan!
Dựa trên thông tin này, hãy tổng hợp câu trả lời CHẤT LƯỢNG CAO cho user:
- Giải thích rõ ràng, dễ hiểu
- Có cấu trúc (bullet points nếu cần)
- Dùng công thức LaTeX nếu có toán học: $...$
- Trích dẫn nguồn từ tài liệu khi phù hợp

Hãy đưa ra Final Answer ngay."""))
                    
                    logger.info(f"[ReAct Agent] Document search result: {result_quality} ({len(result_str)} chars)")
                    
                except Exception as e:
                    logger.error(f"[ReAct Agent] Error in auto document search: {e}")
            
            # ========== TIẾP TỤC ReAct LOOP - LLM sẽ synthesize response ==========
            start_step = 2 if doc_search_result else 1
            for iteration in range(max_iterations):
                logger.info(f"[ReAct Agent] Iteration {iteration + 1}/{max_iterations}")
                
                response = await self.llm.ainvoke(messages)
                response_content = response.content
                
                if isinstance(response_content, list):
                    response_text = '\n\n'.join(str(item) for item in response_content)
                else:
                    response_text = str(response_content)
                
                logger.info(f"[ReAct Agent] LLM Response: {response_text[:200]}...")
                
                # Extract Thought
                thought_match = re.search(r'Thought:\s*(.+?)(?:\n|Action:|Final Answer:|$)', response_text, re.DOTALL)
                thought = thought_match.group(1).strip() if thought_match else ""
                
                # Check for Action FIRST (higher priority than Final Answer)
                action_match = re.search(r'Action:\s*(\w+)', response_text)
                
                # Only treat as Final Answer if NO Action present
                if "Final Answer:" in response_text and not action_match:
                    answer = response_text.split("Final Answer:")[-1].strip()
                    logger.info(f"[ReAct Agent] Final answer reached (no action)")
                    
                    # Send agent_complete with full answer
                    if self.websocket_callback:
                        await self.websocket_callback({
                            'type': 'agent_complete',
                            'status': 'completed',
                            'final_answer': answer
                        })
                    
                    return {
                        'answer': answer,
                        'reasoning_steps': reasoning_steps,
                        'tools_used': list(tools_used),
                        'success': True
                    }
                
                # Extract Action and Action Input
                action_match = re.search(r'Action:\s*(\w+)', response_text)
                input_match = re.search(r'Action Input:\s*(.+?)(?:\n|$)', response_text, re.DOTALL)
                
                if not action_match or not input_match:
                    logger.warning("[ReAct Agent] LLM didn't follow ReAct format")
                    
                    # Clean response
                    clean_response = response_text
                    if "Thought:" in clean_response:
                        parts = clean_response.split("Thought:")
                        if len(parts) > 1:
                            clean_response = parts[-1].strip()
                    
                    clean_response = re.sub(r'(📚\s*)+', '', clean_response).strip()
                    
                    # Send agent_complete
                    if self.websocket_callback:
                        await self.websocket_callback({
                            'type': 'agent_complete',
                            'status': 'completed',
                            'final_answer': clean_response
                        })
                    
                    return {
                        'answer': clean_response,
                        'reasoning_steps': reasoning_steps,
                        'tools_used': list(tools_used),
                        'success': True
                    }
                
                action_name = action_match.group(1).strip()
                action_input = input_match.group(1).strip()
                
                # Tool descriptions for UI display
                tool_descriptions = {
                    'SearchUserDocuments': {
                        'name': 'Tìm kiếm tài liệu người dùng',
                        'purpose': 'Tìm kiếm thông tin trong các tài liệu đã tải lên của bạn',
                        'action': 'Đang tìm kiếm'
                    },
                    'Wikipedia': {
                        'name': 'Tra cứu Wikipedia', 
                        'purpose': 'Tra cứu kiến thức tổng quát trên Wikipedia',
                        'action': 'Đang tra cứu'
                    },
                    'Calculator': {
                        'name': 'Máy tính',
                        'purpose': 'Thực hiện các phép tính toán học',
                        'action': 'Đang tính toán'
                    },
                    'PythonREPL': {
                        'name': 'Python REPL',
                        'purpose': 'Chạy code Python để xử lý dữ liệu phức tạp',
                        'action': 'Đang chạy code'
                    }
                }
                
                tool_info = tool_descriptions.get(action_name, {
                    'name': action_name,
                    'purpose': f'Sử dụng công cụ {action_name}',
                    'action': 'Đang xử lý'
                })
                
                # Execute tool FIRST, then emit completed (không emit executing riêng)
                if action_name in self.tool_map:
                    tool = self.tool_map[action_name]
                    logger.info(f"[ReAct Agent] Executing tool: {action_name}")
                    
                    try:
                        import inspect
                        if inspect.iscoroutinefunction(tool.func):
                            observation = await tool.func(action_input)
                        else:
                            observation = tool.func(action_input)
                        tools_used.add(action_name)
                        
                        # Emit CHỈ 1 event completed (sau khi tool xong)
                        if self.websocket_callback:
                            obs_str = str(observation).strip()
                            result_preview = obs_str[:200]
                            
                            # Phân loại kết quả chi tiết
                            if not obs_str or len(obs_str) < 10:
                                status_msg = "❌ Không tìm thấy thông tin phù hợp"
                                result_quality = "empty"
                            elif "không tìm thấy" in obs_str.lower() or "no results" in obs_str.lower():
                                status_msg = "⚠️ Tìm kiếm không có kết quả"
                                result_quality = "not_found"
                            elif len(obs_str) > 100:
                                status_msg = f"✅ Tìm thấy {len(obs_str)} ký tự thông tin"
                                result_quality = "good"
                            else:
                                status_msg = "✅ Có kết quả"
                                result_quality = "partial"
                            
                            await self.websocket_callback({
                                'type': 'reasoning',
                                'step': start_step + iteration,
                                'status': 'completed',
                                'description': status_msg,
                                'result_quality': result_quality,
                                'thought': thought,
                                'action': action_name,
                                'action_input': action_input[:300],
                                'observation': obs_str[:500],
                                'result_preview': result_preview,
                                'result_length': len(obs_str)
                            })
                        
                        reasoning_steps.append({
                            'tool': action_name,
                            'input': action_input,
                            'output': str(observation)[:500]
                        })
                        
                        messages.append(AIMessage(content=response_text))
                        messages.append(HumanMessage(content=f"Observation: {observation}"))
                        
                    except Exception as e:
                        logger.error(f"[ReAct Agent] Tool execution error: {e}")
                        
                        # Emit reasoning step FAILED
                        if self.websocket_callback:
                            await self.websocket_callback({
                                'type': 'reasoning',
                                'step': start_step + iteration,
                                'status': 'failed',
                                'description': f"Lỗi: {str(e)[:100]}",
                                'thought': thought,
                                'action': action_name,
                                'action_input': action_input[:200],
                                'error': str(e)
                            })
                        
                        messages.append(AIMessage(content=response_text))
                        messages.append(HumanMessage(content=f"Observation: Lỗi khi thực thi tool: {str(e)}"))
                else:
                    logger.warning(f"[ReAct Agent] Unknown tool: {action_name}")
                    
                    # Emit reasoning step FAILED
                    if self.websocket_callback:
                        await self.websocket_callback({
                            'type': 'reasoning',
                            'step': start_step + iteration,
                            'status': 'failed',
                            'description': f"Công cụ '{action_name}' không tồn tại",
                            'thought': thought,
                            'action': action_name,
                            'action_input': action_input[:200]
                        })
                    
                    messages.append(AIMessage(content=response_text))
                    messages.append(HumanMessage(content=f"Observation: Công cụ '{action_name}' không tồn tại. Các công cụ khả dụng: {list(self.tool_map.keys())}"))
            
            logger.warning("[ReAct Agent] Max iterations reached")
            return {
                'answer': "Xin lỗi, tôi cần nhiều thời gian hơn để giải quyết vấn đề này. Bạn có thể thử đơn giản hóa câu hỏi không?",
                'reasoning_steps': reasoning_steps,
                'tools_used': list(tools_used),
                'success': False
            }
            
        except Exception as e:
            logger.error(f"[ReAct Agent] Error: {e}", exc_info=True)
            return {
                'answer': f"Xin lỗi, đã có lỗi khi xử lý: {str(e)}",
                'reasoning_steps': [],
                'tools_used': [],
                'success': False,
                'error': str(e)
            }


# ============================================================================
# PART 3: LEARNING AGENT (HIGH-LEVEL ORCHESTRATOR)
# ============================================================================

class LearningAgent:
    """AI Agent for learning mode - Orchestrates ReAct agent and handles conversation"""
    
    def __init__(self, db: Session, user_id: int, websocket_callback=None):
        self.db = db
        self.user_id = user_id
        self.websocket_callback = websocket_callback
        self.llm_provider = get_llm_provider()
        self.conversation_history = []
        self.structure_id = self._get_active_structure_id()
    
    def _get_active_structure_id(self) -> Optional[int]:
        """Get the currently active teaching structure"""
        structure = self.db.query(models.CustomTeachingStructure).filter(
            models.CustomTeachingStructure.is_active == True
        ).first()
        return structure.id if structure else None
    
    async def process_query(self, user_query: str, conversation_context: List[Dict[str, str]] = None) -> Dict:
        """Process a learning query - main entry point"""
        
        intent = await self._classify_intent(user_query)
        logger.info(f"[Learning Agent] Intent classified: {intent}")
        
        if intent['type'] == 'casual_chat':
            response = await self._generate_casual_response(user_query, conversation_context)
            return {
                'response': response,
                'context_used': '',
                'needs_clarification': False
            }
        
        elif intent['type'] == 'greeting':
            return {
                'response': 'Xin chào! Tôi là trợ lý học tập của bạn. Bạn có thể hỏi tôi về bất kỳ nội dung nào trong tài liệu đã tải lên, hoặc gửi bài tập cần giải. Tôi luôn sẵn sàng hỗ trợ bạn! 😊',
                'context_used': '',
                'needs_clarification': False
            }
        
        elif intent['type'] in ['study_question', 'problem_solving']:
            needs_tools = intent.get('needs_tools', False)
            
            if needs_tools or intent['type'] == 'problem_solving':
                logger.info(f"[Learning Agent] Using ReAct agent")
                result = await solve_with_react_agent(
                    db=self.db,
                    user_id=self.user_id,
                    query=user_query,
                    conversation_history=conversation_context,
                    structure_id=self.structure_id,
                    websocket_callback=self.websocket_callback
                )
                
                if result['success']:
                    return {
                        'response': result['answer'],
                        'context_used': '',
                        'needs_clarification': False,
                        'reasoning_steps': result.get('reasoning_steps', [])
                    }
            
            # Fallback to general response
            response = await self._generate_general_response(user_query, conversation_context)
            return {
                'response': response,
                'context_used': '',
                'needs_clarification': False
            }
        
        else:
            response = await self._generate_general_response(user_query, conversation_context)
            return {
                'response': response,
                'context_used': '',
                'needs_clarification': False
            }
    
    async def _classify_intent(self, user_query: str) -> Dict:
        """Use LLM to classify user intent"""
        classification_prompt = f"""Phân tích câu hỏi/tin nhắn của người dùng và xác định ý định.

Câu hỏi: "{user_query}"

Hãy phân loại vào MỘT trong các loại sau:
1. greeting - Lời chào hỏi
2. casual_chat - Trò chuyện thông thường
3. study_question - Câu hỏi về kiến thức
4. problem_solving - Bài tập cần giải

Đánh giá:
- needs_tools: Có cần công cụ tính toán/search không? (true/false)

Trả lời bằng JSON: {{"type": "loại", "needs_tools": true/false}}"""

        try:
            messages = [{"role": "user", "content": classification_prompt}]
            response = await self.llm_provider.chat(
                messages=messages, 
                temperature=0.1
            )
            
            if response:
                content = self._extract_text_from_llm(response)
                try:
                    json_start = content.find('{')
                    json_end = content.rfind('}') + 1
                    if json_start >= 0 and json_end > json_start:
                        json_str = content[json_start:json_end]
                        intent = json.loads(json_str)
                        return intent
                except:
                    pass
            
            return self._fallback_intent_classification(user_query)
            
        except Exception as e:
            logger.error(f"Error in intent classification: {e}")
            return self._fallback_intent_classification(user_query)
    
    def _fallback_intent_classification(self, query: str) -> Dict:
        """Fallback heuristic classification"""
        query_lower = query.lower().strip()
        
        greeting_words = ['xin chào', 'chào', 'hello', 'hi', 'hey']
        if any(word in query_lower for word in greeting_words) and len(query_lower.split()) <= 5:
            return {'type': 'greeting', 'needs_tools': False}
        
        casual_patterns = ['bạn là ai', 'bạn tên gì', 'cảm ơn']
        if any(pattern in query_lower for pattern in casual_patterns):
            return {'type': 'casual_chat', 'needs_tools': False}
        
        study_words = ['giải', 'bài tập', 'tính', 'tìm', 'chứng minh']
        if any(word in query_lower for word in study_words):
            return {'type': 'problem_solving', 'needs_tools': True}
        
        return {'type': 'study_question', 'needs_tools': True}
    
    async def _generate_casual_response(self, query: str, conversation_context: Optional[List[Dict[str, str]]] = None) -> str:
        """Generate natural response for casual chat"""
        system_prompt = """Bạn là trợ lý học tập thân thiện. Trả lời ngắn gọn (2-3 câu)."""
        
        try:
            messages = [{"role": "system", "content": system_prompt}]
            if conversation_context:
                messages.extend(conversation_context[-4:])
            messages.append({"role": "user", "content": query})
            
            response = await self.llm_provider.chat(
                messages=messages, 
                temperature=0.7
            )
            
            if response:
                return self._extract_text_from_llm(response)
            
            return "Tôi hiểu rồi! Bạn có câu hỏi gì về học tập không?"
            
        except Exception as e:
            logger.error(f"Error generating casual response: {e}")
            return "Tôi ở đây để giúp bạn học tập. Bạn có câu hỏi gì không?"
    
    async def _generate_general_response(self, query: str, conversation_context: Optional[List[Dict[str, str]]] = None) -> str:
        """Generate response for general knowledge questions"""
        system_prompt = """Bạn là trợ lý học tập. Trả lời câu hỏi dựa trên kiến thức chung.

FORMAT CÔNG THỨC TOÁN HỌC:
- Công thức inline: $...$ (VD: $x^2 + y^2 = z^2$)
- Công thức block: $$...$$ (VD: $$\\int_a^b f(x) dx$$)
- Phân số: $\\frac{a}{b}$, Căn: $\\sqrt{x}$, Lũy thừa: $x^n$
- LUÔN wrap công thức trong $ hoặc $$"""
        
        try:
            messages = [{"role": "system", "content": system_prompt}]
            if conversation_context:
                messages.extend(conversation_context[-4:])
            messages.append({"role": "user", "content": query})
            
            response = await self.llm_provider.chat(
                messages=messages, 
                temperature=0.5
            )
            
            if response:
                return self._extract_text_from_llm(response)
            
            return "Tôi cần thêm thông tin để trả lời câu hỏi này chính xác hơn."
            
        except Exception as e:
            logger.error(f"Error generating general response: {e}")
            return "Xin lỗi, tôi gặp khó khăn khi xử lý câu hỏi này."
    
    def _extract_text_from_llm(self, response: dict) -> str:
        """Extract text content from LLM response"""
        # Gemini format
        candidates = response.get("candidates")
        if isinstance(candidates, list) and candidates:
            cand0 = candidates[0]
            if isinstance(cand0, dict):
                content = cand0.get("content")
                if isinstance(content, dict):
                    parts = content.get("parts")
                    if isinstance(parts, list) and parts:
                        text = parts[0].get("text")
                        if text:
                            return text.strip()
        
        # OpenAI format
        choices = response.get("choices")
        if isinstance(choices, list) and choices:
            msg = choices[0].get("message")
            if isinstance(msg, dict):
                content = msg.get("content")
                if content:
                    return content.strip()
        
        # Fallback
        if isinstance(response, str):
            return response.strip()
        
        return str(response)


# ============================================================================
# PART 4: PUBLIC API
# ============================================================================

async def generate_learning_response(
    db: Session,
    user_id: int,
    user_query: str,
    conversation_history: List[Dict[str, str]] = None,
    websocket_callback=None
) -> Dict:
    """
    Main entry point for generating learning mode responses
    
    Args:
        db: Database session
        user_id: User ID
        user_query: User's question
        conversation_history: Previous conversation context
        websocket_callback: Optional callback for streaming
    
    Returns:
        Dictionary with response and metadata
    """
    agent = LearningAgent(db, user_id, websocket_callback)
    result = await agent.process_query(user_query, conversation_history)
    return result


async def solve_with_react_agent(
    db,
    user_id: int,
    query: str,
    conversation_history: Optional[List[Dict]] = None,
    structure_id: Optional[int] = None,
    websocket_callback=None
) -> Dict[str, Any]:
    """Convenience function to create and use ReAct agent"""
    agent = ReActLearningAgent(db, user_id, structure_id, websocket_callback)
    result = await agent.solve(query, conversation_history)
    return result

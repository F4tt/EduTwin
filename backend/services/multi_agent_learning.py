"""
Multi-Agent Learning System - Leader-Worker Architecture

Architecture:
┌─────────────────────────────────────────────────────────────┐
│                      LEADER AGENT                            │
│  - Receives user question                                    │
│  - Analyzes and plans                                        │
│  - Delegates tasks to Worker                                 │
│  - Evaluates Worker results                                  │
│  - Decides: continue/retry/finalize                          │
│  - Synthesizes final answer                                  │
└─────────────────────────────────────────────────────────────┘
                            ↑↓
┌─────────────────────────────────────────────────────────────┐
│                      WORKER AGENT                            │
│  - Receives tasks from Leader                                │
│  - Uses tools (Document Search, Wikipedia, Calculator, etc.) │
│  - Returns results to Leader                                 │
│  - No decision-making, just execution                        │
└─────────────────────────────────────────────────────────────┘

Flow:
1. User Question → Leader
2. Leader analyzes → Creates task for Worker
3. Worker executes tools → Returns observation
4. Leader evaluates observation → Decides next step
5. If more info needed → Back to step 2
6. If enough info → Leader synthesizes final answer
"""

import os
import re
import json
import logging
import asyncio
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field
from enum import Enum
from sqlalchemy.orm import Session

from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage

from db import models
from services.llm_provider import get_llm_provider

logger = logging.getLogger(__name__)


# ============================================================================
# DATA CLASSES
# ============================================================================

class TaskType(Enum):
    """Types of tasks Leader can delegate to Worker"""
    SEARCH_DOCUMENTS = "search_documents"
    SEARCH_WIKIPEDIA = "search_wikipedia"
    CALCULATE = "calculate"
    EXECUTE_CODE = "execute_code"
    NO_ACTION = "no_action"  # Leader has enough info


@dataclass
class LeaderDecision:
    """Leader's decision after evaluating Worker's result"""
    action: str  # "delegate", "retry", "finalize"
    task_type: Optional[TaskType] = None
    task_input: Optional[str] = None
    reasoning: str = ""
    final_answer: Optional[str] = None
    confidence: float = 0.0


@dataclass 
class WorkerResult:
    """Result from Worker's tool execution"""
    success: bool
    tool_used: str
    input_query: str
    output: str
    execution_time: float = 0.0
    error: Optional[str] = None


@dataclass
class AgentState:
    """State shared between Leader and Worker"""
    user_query: str
    conversation_history: List[Dict] = field(default_factory=list)
    worker_results: List[WorkerResult] = field(default_factory=list)
    reasoning_steps: List[Dict] = field(default_factory=list)
    iteration: int = 0
    max_iterations: int = 5


# ============================================================================
# WORKER AGENT
# ============================================================================

class WorkerAgent:
    """
    Worker Agent - Tool Executor
    
    Responsibilities:
    - Execute specific tools as directed by Leader
    - Return raw results without interpretation
    - Report success/failure honestly
    
    NO decision-making - just execution!
    """
    
    def __init__(self, db: Session, user_id: int, websocket_callback=None):
        self.db = db
        self.user_id = user_id
        self.websocket_callback = websocket_callback
        self._setup_tools()
    
    def _setup_tools(self):
        """Initialize available tools"""
        import numexpr
        self.numexpr = numexpr
    
    async def _emit_progress(self, tool: str, message: str, status: str = "executing"):
        """Emit progress update via WebSocket"""
        if self.websocket_callback:
            await self.websocket_callback({
                'type': 'worker_progress',
                'tool': tool,
                'message': message,
                'status': status
            })
    
    async def execute_task(self, task_type: TaskType, task_input: str) -> WorkerResult:
        """Execute a task and return result"""
        import time
        start_time = time.time()
        
        logger.info(f"[Worker] Executing task: {task_type.value} with input: {task_input[:100]}...")
        
        try:
            if task_type == TaskType.SEARCH_DOCUMENTS:
                result = await self._search_documents(task_input)
            elif task_type == TaskType.SEARCH_WIKIPEDIA:
                result = await self._search_wikipedia(task_input)
            elif task_type == TaskType.CALCULATE:
                result = await self._calculate(task_input)
            elif task_type == TaskType.EXECUTE_CODE:
                result = await self._execute_python(task_input)
            else:
                result = WorkerResult(
                    success=False,
                    tool_used="none",
                    input_query=task_input,
                    output="",
                    error="Unknown task type"
                )
            
            result.execution_time = time.time() - start_time
            return result
            
        except Exception as e:
            logger.error(f"[Worker] Task execution error: {e}")
            return WorkerResult(
                success=False,
                tool_used=task_type.value,
                input_query=task_input,
                output="",
                execution_time=time.time() - start_time,
                error=str(e)
            )
    
    async def _search_documents(self, query: str) -> WorkerResult:
        """Search in user's uploaded documents"""
        await self._emit_progress("SearchDocuments", f"🔍 Đang tìm trong tài liệu: \"{query[:50]}...\"")
        
        try:
            user = self.db.query(models.User).filter(models.User.id == self.user_id).first()
            
            if not user or not user.uploaded_documents:
                await self._emit_progress("SearchDocuments", "❌ Không có tài liệu", "failed")
                return WorkerResult(
                    success=False,
                    tool_used="SearchDocuments",
                    input_query=query,
                    output="Bạn chưa tải lên tài liệu nào.",
                    error="No documents"
                )
            
            documents = user.uploaded_documents
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
                # Fallback: return first document
                if documents and documents[0].get('content'):
                    first_doc = documents[0]
                    content = first_doc.get('content', '')[:5000]
                    await self._emit_progress("SearchDocuments", f"📄 Sử dụng tài liệu: {first_doc.get('filename')}", "completed")
                    return WorkerResult(
                        success=True,
                        tool_used="SearchDocuments",
                        input_query=query,
                        output=f"[Tài liệu: {first_doc.get('filename', 'Unknown')}]\n{content}"
                    )
                
                await self._emit_progress("SearchDocuments", "❌ Không tìm thấy thông tin phù hợp", "failed")
                return WorkerResult(
                    success=False,
                    tool_used="SearchDocuments",
                    input_query=query,
                    output="Không tìm thấy thông tin liên quan trong tài liệu.",
                    error="No relevant content"
                )
            
            formatted = []
            for doc in relevant_docs:
                formatted.append(f"[Tài liệu: {doc['name']}]\n{doc['content']}")
            
            result_text = "\n\n---\n\n".join(formatted)
            await self._emit_progress("SearchDocuments", f"✅ Tìm thấy trong {len(relevant_docs)} tài liệu", "completed")
            
            return WorkerResult(
                success=True,
                tool_used="SearchDocuments",
                input_query=query,
                output=result_text
            )
            
        except Exception as e:
            logger.error(f"[Worker] Document search error: {e}")
            await self._emit_progress("SearchDocuments", f"⚠️ Lỗi: {str(e)}", "failed")
            return WorkerResult(
                success=False,
                tool_used="SearchDocuments",
                input_query=query,
                output="",
                error=str(e)
            )
    
    async def _search_wikipedia(self, query: str) -> WorkerResult:
        """Search Wikipedia for information"""
        await self._emit_progress("Wikipedia", f"🌐 Đang tra cứu Wikipedia: \"{query[:50]}...\"")
        
        try:
            import wikipedia
            
            # Extract keywords
            stop_words = {'là', 'gì', 'và', 'của', 'trong', 'cho', 'được', 'có', 'những', 'các',
                         'này', 'đó', 'như', 'thế', 'nào', 'sao', 'với', 'để', 'về', 'từ',
                         'hãy', 'tìm', 'kiếm', 'trên', 'wikipedia', 'định', 'nghĩa'}
            
            words = query.lower().replace('?', '').replace('!', '').replace('.', '').split()
            keywords = [w for w in words if w not in stop_words and len(w) > 2]
            search_term = ' '.join(keywords[:4]) if keywords else query
            
            # Try English Wikipedia first
            wikipedia.set_lang("en")
            search_results = wikipedia.search(search_term, results=5)
            
            if search_results:
                best_match = search_results[0]
                for title in search_results:
                    if any(kw.lower() in title.lower() for kw in keywords):
                        best_match = title
                        break
                
                try:
                    page = wikipedia.page(best_match, auto_suggest=False)
                    summary = page.summary[:2000]
                    result = f"[Wikipedia: {page.title}]\n{summary}"
                    
                    await self._emit_progress("Wikipedia", f"✅ Tìm thấy: {page.title}", "completed")
                    return WorkerResult(
                        success=True,
                        tool_used="Wikipedia",
                        input_query=query,
                        output=result
                    )
                except wikipedia.exceptions.DisambiguationError as e:
                    if e.options:
                        try:
                            page = wikipedia.page(e.options[0], auto_suggest=False)
                            summary = page.summary[:2000]
                            result = f"[Wikipedia: {page.title}]\n{summary}"
                            
                            await self._emit_progress("Wikipedia", f"✅ Tìm thấy: {page.title}", "completed")
                            return WorkerResult(
                                success=True,
                                tool_used="Wikipedia",
                                input_query=query,
                                output=result
                            )
                        except:
                            pass
            
            # Try Vietnamese Wikipedia
            wikipedia.set_lang("vi")
            search_results = wikipedia.search(search_term, results=3)
            
            if search_results:
                try:
                    page = wikipedia.page(search_results[0], auto_suggest=False)
                    summary = page.summary[:2000]
                    result = f"[Wikipedia VI: {page.title}]\n{summary}"
                    
                    await self._emit_progress("Wikipedia", f"✅ Tìm thấy (VI): {page.title}", "completed")
                    return WorkerResult(
                        success=True,
                        tool_used="Wikipedia",
                        input_query=query,
                        output=result
                    )
                except:
                    pass
            
            await self._emit_progress("Wikipedia", "❌ Không tìm thấy thông tin", "failed")
            return WorkerResult(
                success=False,
                tool_used="Wikipedia",
                input_query=query,
                output="Không tìm thấy thông tin trên Wikipedia.",
                error="No results found"
            )
            
        except Exception as e:
            logger.error(f"[Worker] Wikipedia search error: {e}")
            await self._emit_progress("Wikipedia", f"⚠️ Lỗi: {str(e)}", "failed")
            return WorkerResult(
                success=False,
                tool_used="Wikipedia",
                input_query=query,
                output="",
                error=str(e)
            )
    
    async def _calculate(self, expression: str) -> WorkerResult:
        """Evaluate mathematical expression"""
        await self._emit_progress("Calculator", f"🧮 Đang tính: {expression}")
        
        try:
            result = self.numexpr.evaluate(expression).item()
            
            await self._emit_progress("Calculator", f"✅ Kết quả: {result}", "completed")
            return WorkerResult(
                success=True,
                tool_used="Calculator",
                input_query=expression,
                output=f"Kết quả: {result}"
            )
        except Exception as e:
            await self._emit_progress("Calculator", f"⚠️ Lỗi: {str(e)}", "failed")
            return WorkerResult(
                success=False,
                tool_used="Calculator",
                input_query=expression,
                output="",
                error=str(e)
            )
    
    async def _execute_python(self, code: str) -> WorkerResult:
        """Execute Python code safely"""
        await self._emit_progress("PythonREPL", "🐍 Đang chạy code Python...")
        
        try:
            import math
            import numpy as np
            
            namespace = {
                'math': math,
                'np': np,
                '__builtins__': {
                    'abs': abs, 'round': round, 'sum': sum, 'len': len,
                    'max': max, 'min': min, 'range': range, 'list': list,
                    'dict': dict, 'str': str, 'int': int, 'float': float, 'print': print
                }
            }
            
            exec(code, namespace)
            
            if 'result' in namespace:
                await self._emit_progress("PythonREPL", "✅ Code thực thi thành công", "completed")
                return WorkerResult(
                    success=True,
                    tool_used="PythonREPL",
                    input_query=code,
                    output=f"Kết quả: {namespace['result']}"
                )
            else:
                return WorkerResult(
                    success=True,
                    tool_used="PythonREPL",
                    input_query=code,
                    output="Code executed (no 'result' variable)"
                )
                
        except Exception as e:
            await self._emit_progress("PythonREPL", f"⚠️ Lỗi: {str(e)}", "failed")
            return WorkerResult(
                success=False,
                tool_used="PythonREPL",
                input_query=code,
                output="",
                error=str(e)
            )


# ============================================================================
# LEADER AGENT
# ============================================================================

class LeaderAgent:
    """
    Leader Agent - Decision Maker & Orchestrator
    
    Responsibilities:
    - Analyze user question
    - Plan what information is needed
    - Delegate tasks to Worker
    - Evaluate Worker's results
    - Decide next action: more search, retry, or finalize
    - Synthesize final answer
    
    Key principle: THINKING before acting, EVALUATING after receiving
    """
    
    def __init__(self, websocket_callback=None):
        self.websocket_callback = websocket_callback
        
        api_key = os.getenv("LLM_API_KEY")
        model_name = os.getenv("LLM_MODEL", "gemini-2.0-flash-exp")
        
        self.llm = ChatGoogleGenerativeAI(
            model=model_name,
            google_api_key=api_key,
            temperature=0.3,
            convert_system_message_to_human=True
        )
    
    async def _emit_reasoning(self, step: int, phase: str, content: Dict):
        """Emit reasoning step via WebSocket"""
        if self.websocket_callback:
            await self.websocket_callback({
                'type': 'leader_reasoning',
                'step': step,
                'phase': phase,  # "analyzing", "planning", "evaluating", "synthesizing"
                **content
            })
    
    async def analyze_and_plan(self, state: AgentState) -> LeaderDecision:
        """
        Phase 1: Analyze user question and plan first action
        
        Returns decision on what Worker should do
        """
        logger.info(f"[Leader] Analyzing query: {state.user_query[:100]}...")
        
        await self._emit_reasoning(1, "analyzing", {
            'status': 'thinking',
            'description': '🧠 Đang phân tích câu hỏi...'
        })
        
        analyze_prompt = f"""Bạn là LEADER AGENT - chuyên phân tích và lập kế hoạch.

CÂU HỎI CỦA USER:
"{state.user_query}"

NHIỆM VỤ: Phân tích câu hỏi và quyết định cần làm gì TRƯỚC TIÊN.

CÁC CÔNG CỤ CÓ SẴN:
1. search_documents - Tìm trong tài liệu user đã upload (ƯU TIÊN DÙNG TRƯỚC)
2. search_wikipedia - Tra cứu kiến thức chung trên Wikipedia
3. calculate - Tính toán biểu thức toán học
4. execute_code - Chạy code Python

NGUYÊN TẮC:
- LUÔN bắt đầu bằng search_documents để tìm trong tài liệu của user
- Chỉ dùng wikipedia khi tài liệu không có thông tin cần thiết
- Nếu câu hỏi đơn giản (chào hỏi, cảm ơn) → trả lời trực tiếp

TRẢ LỜI BẰNG JSON:
{{
    "reasoning": "Giải thích ngắn gọn tại sao chọn hành động này",
    "action": "delegate" hoặc "answer_directly",
    "task_type": "search_documents" / "search_wikipedia" / "calculate" / "execute_code" / null,
    "task_input": "query hoặc expression cho Worker",
    "direct_answer": "câu trả lời nếu answer_directly"
}}"""

        try:
            response = await self.llm.ainvoke([HumanMessage(content=analyze_prompt)])
            response_text = self._extract_response_text(response)
            
            decision = self._parse_decision(response_text, phase="analyze")
            
            await self._emit_reasoning(1, "analyzing", {
                'status': 'completed',
                'description': f'✅ {decision.reasoning[:100]}...' if len(decision.reasoning) > 100 else f'✅ {decision.reasoning}',
                'decision': decision.action,
                'task_type': decision.task_type.value if decision.task_type else None
            })
            
            return decision
            
        except Exception as e:
            logger.error(f"[Leader] Analysis error: {e}")
            # Default: search documents first
            return LeaderDecision(
                action="delegate",
                task_type=TaskType.SEARCH_DOCUMENTS,
                task_input=state.user_query,
                reasoning="Mặc định tìm trong tài liệu trước"
            )
    
    async def evaluate_result(self, state: AgentState, worker_result: WorkerResult) -> LeaderDecision:
        """
        Phase 2: Evaluate Worker's result and decide next action
        
        Options:
        - "delegate": Need more info → assign new task to Worker
        - "retry": Worker failed → retry with different approach
        - "finalize": Have enough info → synthesize answer
        """
        logger.info(f"[Leader] Evaluating result from {worker_result.tool_used}")
        
        step_num = state.iteration + 2
        await self._emit_reasoning(step_num, "evaluating", {
            'status': 'thinking',
            'description': f'🔍 Đang đánh giá kết quả từ {worker_result.tool_used}...'
        })
        
        # Build context from previous results
        results_summary = []
        for i, result in enumerate(state.worker_results):
            results_summary.append(f"""
Kết quả {i+1} ({result.tool_used}):
- Thành công: {result.success}
- Output: {result.output[:500]}...
""")
        
        evaluate_prompt = f"""Bạn là LEADER AGENT - chuyên đánh giá kết quả.

CÂU HỎI GỐC:
"{state.user_query}"

KẾT QUẢ TỪ WORKER:
Tool: {worker_result.tool_used}
Thành công: {worker_result.success}
Output: {worker_result.output[:2000]}

CÁC KẾT QUẢ TRƯỚC ĐÓ:
{chr(10).join(results_summary) if results_summary else "Chưa có"}

NHIỆM VỤ: Đánh giá kết quả và quyết định bước tiếp theo.

ĐÁNH GIÁ:
1. Kết quả có trả lời được câu hỏi của user không?
2. Thông tin có đủ chi tiết và chính xác không?
3. Có cần tìm thêm thông tin từ nguồn khác không?

CÁC LỰA CHỌN:
- "finalize": Đã đủ thông tin → tổng hợp câu trả lời
- "delegate": Cần thêm thông tin → giao task mới cho Worker
- "retry": Kết quả không tốt → thử cách khác

TRẢ LỜI BẰNG JSON:
{{
    "evaluation": "Đánh giá chi tiết kết quả",
    "is_sufficient": true/false,
    "action": "finalize" / "delegate" / "retry",
    "task_type": "search_documents" / "search_wikipedia" / "calculate" / null,
    "task_input": "query mới nếu cần tìm thêm",
    "confidence": 0.0-1.0
}}"""

        try:
            response = await self.llm.ainvoke([HumanMessage(content=evaluate_prompt)])
            response_text = self._extract_response_text(response)
            
            decision = self._parse_decision(response_text, phase="evaluate")
            
            if decision.action == "finalize":
                await self._emit_reasoning(step_num, "evaluating", {
                    'status': 'completed',
                    'description': f'✅ Đã đủ thông tin để trả lời (độ tin cậy: {decision.confidence:.0%})',
                    'decision': 'finalize'
                })
            else:
                await self._emit_reasoning(step_num, "evaluating", {
                    'status': 'completed',
                    'description': f'📋 Cần thêm thông tin: {decision.reasoning[:80]}...',
                    'decision': decision.action,
                    'next_task': decision.task_type.value if decision.task_type else None
                })
            
            return decision
            
        except Exception as e:
            logger.error(f"[Leader] Evaluation error: {e}")
            # Default: finalize with what we have
            return LeaderDecision(
                action="finalize",
                reasoning="Sử dụng thông tin hiện có để trả lời",
                confidence=0.5
            )
    
    async def synthesize_answer(self, state: AgentState) -> str:
        """
        Phase 3: Synthesize final answer from all collected information
        """
        logger.info(f"[Leader] Synthesizing final answer...")
        
        await self._emit_reasoning(state.iteration + 3, "synthesizing", {
            'status': 'thinking',
            'description': '📝 Đang tổng hợp câu trả lời...'
        })
        
        # Collect all observations
        all_observations = []
        for result in state.worker_results:
            if result.success:
                all_observations.append(f"[{result.tool_used}]\n{result.output}")
        
        synthesize_prompt = f"""Bạn là LEADER AGENT - chuyên tổng hợp câu trả lời.

CÂU HỎI CỦA USER:
"{state.user_query}"

THÔNG TIN ĐÃ THU THẬP:
{chr(10).join(all_observations) if all_observations else "Không có thông tin cụ thể"}

NHIỆM VỤ: Tổng hợp câu trả lời CHẤT LƯỢNG CAO cho user.

YÊU CẦU:
1. Trả lời trực tiếp vào câu hỏi
2. Sử dụng thông tin từ tài liệu/Wikipedia đã tìm được
3. Có cấu trúc rõ ràng (bullet points nếu cần)
4. Giải thích dễ hiểu, phù hợp với học sinh
5. Công thức toán học: dùng LaTeX ($...$ cho inline, $$...$$ cho block)
6. Trích dẫn nguồn khi phù hợp

KHÔNG được:
- Nói "dựa vào thông tin" hoặc "theo tài liệu" quá nhiều
- Lặp lại câu hỏi
- Trả lời chung chung không có nội dung

Hãy viết câu trả lời bằng tiếng Việt:"""

        try:
            response = await self.llm.ainvoke([HumanMessage(content=synthesize_prompt)])
            answer = self._extract_response_text(response)
            
            # Clean up answer
            answer = answer.strip()
            if answer.startswith('"') and answer.endswith('"'):
                answer = answer[1:-1]
            
            await self._emit_reasoning(state.iteration + 3, "synthesizing", {
                'status': 'completed',
                'description': '✅ Đã hoàn thành câu trả lời'
            })
            
            return answer
            
        except Exception as e:
            logger.error(f"[Leader] Synthesis error: {e}")
            return "Xin lỗi, tôi gặp khó khăn khi tổng hợp câu trả lời. Vui lòng thử lại."
    
    def _extract_response_text(self, response) -> str:
        """Extract text from LLM response"""
        if hasattr(response, 'content'):
            content = response.content
            if isinstance(content, list):
                return '\n'.join(str(item) for item in content)
            return str(content)
        return str(response)
    
    def _parse_decision(self, response_text: str, phase: str) -> LeaderDecision:
        """Parse JSON decision from LLM response"""
        try:
            # Find JSON in response
            json_match = re.search(r'\{[^{}]*\}', response_text, re.DOTALL)
            if json_match:
                data = json.loads(json_match.group())
                
                # Map task type string to enum
                task_type = None
                task_type_str = data.get('task_type')
                if task_type_str:
                    task_type_map = {
                        'search_documents': TaskType.SEARCH_DOCUMENTS,
                        'search_wikipedia': TaskType.SEARCH_WIKIPEDIA,
                        'calculate': TaskType.CALCULATE,
                        'execute_code': TaskType.EXECUTE_CODE
                    }
                    task_type = task_type_map.get(task_type_str)
                
                return LeaderDecision(
                    action=data.get('action', 'delegate'),
                    task_type=task_type,
                    task_input=data.get('task_input', data.get('direct_answer', '')),
                    reasoning=data.get('reasoning', data.get('evaluation', '')),
                    final_answer=data.get('direct_answer'),
                    confidence=float(data.get('confidence', 0.7))
                )
        except Exception as e:
            logger.warning(f"[Leader] Failed to parse decision JSON: {e}")
        
        # Fallback
        return LeaderDecision(
            action="delegate",
            task_type=TaskType.SEARCH_DOCUMENTS,
            task_input="",
            reasoning="Fallback decision"
        )


# ============================================================================
# ORCHESTRATOR - COORDINATES LEADER AND WORKER
# ============================================================================

class MultiAgentOrchestrator:
    """
    Orchestrator - Coordinates Leader and Worker agents
    
    Main loop:
    1. Leader analyzes question → creates task
    2. Worker executes task → returns result
    3. Leader evaluates result → decides next step
    4. Repeat until Leader says "finalize"
    5. Leader synthesizes final answer
    """
    
    def __init__(self, db: Session, user_id: int, websocket_callback=None):
        self.db = db
        self.user_id = user_id
        self.websocket_callback = websocket_callback
        
        self.leader = LeaderAgent(websocket_callback)
        self.worker = WorkerAgent(db, user_id, websocket_callback)
    
    async def process_query(
        self,
        user_query: str,
        conversation_history: List[Dict] = None
    ) -> Dict[str, Any]:
        """
        Main entry point - process user query using Leader-Worker pattern
        """
        logger.info(f"[Orchestrator] Processing: {user_query[:100]}...")
        
        # Initialize state
        state = AgentState(
            user_query=user_query,
            conversation_history=conversation_history or []
        )
        
        try:
            # Step 1: Leader analyzes and plans
            decision = await self.leader.analyze_and_plan(state)
            
            # Handle direct answer (greeting, simple questions)
            if decision.action == "answer_directly" and decision.final_answer:
                logger.info("[Orchestrator] Leader answered directly")
                
                if self.websocket_callback:
                    await self.websocket_callback({
                        'type': 'agent_complete',
                        'status': 'completed',
                        'final_answer': decision.final_answer
                    })
                
                return {
                    'response': decision.final_answer,
                    'success': True,
                    'reasoning_steps': [],
                    'tools_used': []
                }
            
            # Main loop: Leader delegates → Worker executes → Leader evaluates
            tools_used = set()
            
            while state.iteration < state.max_iterations:
                state.iteration += 1
                logger.info(f"[Orchestrator] Iteration {state.iteration}/{state.max_iterations}")
                
                # Worker executes task
                if decision.task_type and decision.task_input:
                    worker_result = await self.worker.execute_task(
                        decision.task_type,
                        decision.task_input or user_query
                    )
                    
                    state.worker_results.append(worker_result)
                    tools_used.add(worker_result.tool_used)
                    
                    state.reasoning_steps.append({
                        'iteration': state.iteration,
                        'tool': worker_result.tool_used,
                        'input': worker_result.input_query[:200],
                        'success': worker_result.success,
                        'output_preview': worker_result.output[:300]
                    })
                    
                    # Leader evaluates result
                    decision = await self.leader.evaluate_result(state, worker_result)
                
                # Check if Leader says we're done
                if decision.action == "finalize":
                    break
                
                # If no valid task, break to prevent infinite loop
                if not decision.task_type:
                    logger.warning("[Orchestrator] No task type, breaking loop")
                    break
            
            # Leader synthesizes final answer
            final_answer = await self.leader.synthesize_answer(state)
            
            # Emit completion
            if self.websocket_callback:
                await self.websocket_callback({
                    'type': 'agent_complete',
                    'status': 'completed',
                    'final_answer': final_answer
                })
            
            return {
                'response': final_answer,
                'success': True,
                'reasoning_steps': state.reasoning_steps,
                'tools_used': list(tools_used),
                'iterations': state.iteration
            }
            
        except Exception as e:
            logger.error(f"[Orchestrator] Error: {e}", exc_info=True)
            
            error_msg = f"Xin lỗi, đã có lỗi xảy ra: {str(e)}"
            
            if self.websocket_callback:
                await self.websocket_callback({
                    'type': 'agent_complete',
                    'status': 'error',
                    'final_answer': error_msg
                })
            
            return {
                'response': error_msg,
                'success': False,
                'error': str(e),
                'reasoning_steps': state.reasoning_steps,
                'tools_used': []
            }


# ============================================================================
# PUBLIC API
# ============================================================================

async def process_with_multi_agent(
    db: Session,
    user_id: int,
    query: str,
    conversation_history: List[Dict] = None,
    websocket_callback=None
) -> Dict[str, Any]:
    """
    Process a learning query using Multi-Agent (Leader-Worker) architecture
    
    Args:
        db: Database session
        user_id: User ID
        query: User's question
        conversation_history: Previous messages
        websocket_callback: Callback for real-time updates
    
    Returns:
        Dict with 'response', 'success', 'reasoning_steps', 'tools_used'
    """
    orchestrator = MultiAgentOrchestrator(db, user_id, websocket_callback)
    return await orchestrator.process_query(query, conversation_history)

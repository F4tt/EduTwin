import React, { useState, useEffect, useRef } from 'react';
import { Send, Plus, MessageSquare, Trash2, ChevronLeft, ChevronRight, Upload, FileText, Square } from 'lucide-react';
import axiosClient from '../api/axiosClient';
import { useAuth } from '../context/AuthContext';
import { useWebSocket } from '../context/WebSocketContext';
import ReasoningDisplay from '../components/ReasoningDisplay';
import MarkdownWithMath from '../components/MarkdownWithMath';

const Learning = () => {
    const { user } = useAuth();
    const { connected, chatMessages, isTyping, joinChatSession, leaveChatSession, clearChatMessages } = useWebSocket();

    const [sessions, setSessions] = useState([]);
    const [currentSessionId, setCurrentSessionId] = useState(null);
    const [messages, setMessages] = useState([]);
    const [input, setInput] = useState('');
    const [loading, setLoading] = useState(false);
    const [collapsed, setCollapsed] = useState(() => {
        try {
            return localStorage.getItem('learning_sidebar_collapsed') === 'true';
        } catch (e) {
            return false;
        }
    });

    const [documents, setDocuments] = useState([]);
    const [uploadingDoc, setUploadingDoc] = useState(false);
    const [showDocumentPanel, setShowDocumentPanel] = useState(false);
    const [abortController, setAbortController] = useState(null);

    // Reasoning steps from agent
    const [reasoningSteps, setReasoningSteps] = useState([]);
    const [isAgentProcessing, setIsAgentProcessing] = useState(false);
    const [isReasoningCompleted, setIsReasoningCompleted] = useState(false);

    // Use ref to track latest reasoning steps for saving with messages
    const reasoningStepsRef = useRef([]);

    // Track current request ID for filtering WebSocket events
    const currentRequestIdRef = useRef(null);

    const messagesEndRef = useRef(null);
    const fileInputRef = useRef(null);

    // Cleanup on unmount to prevent crashes when switching pages
    useEffect(() => {
        return () => {
            // Clear reasoning steps and agent processing state
            setReasoningSteps([]);
            setIsAgentProcessing(false);
            setLoading(false);
        };
    }, []);

    useEffect(() => {
        fetchSessions();
        fetchDocuments();
    }, []);

    // Sync reasoning steps with ref for use in async handlers
    useEffect(() => {
        reasoningStepsRef.current = reasoningSteps;
    }, [reasoningSteps]);

    const fetchSessions = async () => {
        try {
            const res = await axiosClient.get('/chatbot/sessions', {
                params: { mode: 'learning' }
            });
            setSessions(res.data);
            if (res.data.length > 0 && !currentSessionId) {
                setCurrentSessionId(res.data[0].id);
            }
        } catch (e) {
            console.error(e);
        }
    };

    const fetchDocuments = async () => {
        try {
            const res = await axiosClient.get('/learning/documents');
            setDocuments(res.data.documents || []);
        } catch (e) {
            console.error('Failed to fetch documents:', e);
        }
    };

    useEffect(() => {
        if (currentSessionId) {
            fetchMessages(currentSessionId);

            // FIX: Clear reasoning from previous session when switching sessions
            setReasoningSteps([]);
            setIsAgentProcessing(false);
            setIsReasoningCompleted(false);
            currentRequestIdRef.current = null;  // Clear request tracking

            if (!String(currentSessionId).startsWith('draft')) {
                joinChatSession(currentSessionId);
            }

            clearChatMessages();
        }

        return () => {
            if (currentSessionId && !String(currentSessionId).startsWith('draft')) {
                leaveChatSession(currentSessionId);
            }
        };
    }, [currentSessionId, joinChatSession, leaveChatSession, clearChatMessages]);

    // Single useEffect to handle ALL chatMessages events
    useEffect(() => {
        if (chatMessages.length === 0) return;

        const latestMessage = chatMessages[chatMessages.length - 1];
        const isReasoningOrAgentEvent = ['reasoning', 'tool_progress', 'agent_complete', 'self_reflection'].includes(latestMessage.type);

        // CRITICAL FIX: Use request_id for filtering reasoning events
        // This is more reliable than session_id because:
        // 1. request_id is set BEFORE HTTP request starts
        // 2. No race condition with session creation
        if (isReasoningOrAgentEvent) {
            const eventRequestId = latestMessage.request_id;
            const currentRequestId = currentRequestIdRef.current;

            // Only process if we have an active request
            if (!currentRequestId) {
                console.log('[Learning] Ignoring reasoning event - no active request');
                return;
            }

            // If event has request_id, it must match current request
            if (eventRequestId && eventRequestId !== currentRequestId) {
                console.log('[Learning] Ignoring event from different request:', eventRequestId, 'current:', currentRequestId);
                return;
            }

            console.log('[Learning] Processing reasoning event for request:', currentRequestId);
        } else {
            // For non-reasoning events (chat messages), use session filter
            const isDraftSession = String(currentSessionId).startsWith('draft');
            const isMatchingSession = String(latestMessage.session_id) === String(currentSessionId);
            if (!isDraftSession && !isMatchingSession) return;
        }

        // Handle tool_progress - update current step's progress
        if (latestMessage.type === 'tool_progress') {
            setReasoningSteps(prev => {
                if (prev.length === 0) return prev;
                const lastStep = prev[prev.length - 1];
                const progressMessages = lastStep.progressMessages || [];
                return [
                    ...prev.slice(0, -1),
                    {
                        ...lastStep,
                        progressMessages: [...progressMessages, latestMessage.message]
                    }
                ];
            });
            return;
        }

        // Handle reasoning event - UPDATE hoặc ADD step
        if (latestMessage.type === 'reasoning' && latestMessage.step !== undefined) {
            setIsAgentProcessing(true);

            setReasoningSteps(prev => {
                const stepIndex = latestMessage.step - 1;
                const newSteps = [...prev];

                // Ensure array is large enough
                while (newSteps.length <= stepIndex) {
                    newSteps.push({ step: newSteps.length + 1, status: 'pending' });
                }

                // MERGE all data from this event into the step
                const existingStep = newSteps[stepIndex] || {};
                newSteps[stepIndex] = {
                    ...existingStep,
                    step: latestMessage.step,
                    status: latestMessage.status || existingStep.status || 'pending',
                    description: latestMessage.description || existingStep.description,
                    tool_name: latestMessage.tool_name || existingStep.tool_name,
                    tool_purpose: latestMessage.tool_purpose || existingStep.tool_purpose,
                    thought: latestMessage.thought || existingStep.thought,
                    action: latestMessage.action || existingStep.action,
                    action_input: latestMessage.action_input || existingStep.action_input,
                    observation: latestMessage.observation || existingStep.observation,
                    result_preview: latestMessage.result_preview || existingStep.result_preview,
                    result_length: latestMessage.result_length || existingStep.result_length,
                    result_quality: latestMessage.result_quality || existingStep.result_quality,
                    error: latestMessage.error || existingStep.error
                };

                return newSteps;
            });
            return;
        }

        // Handle agent_complete
        if (latestMessage.type === 'agent_complete') {
            console.log('[Learning] agent_complete received');
            setIsAgentProcessing(false);
            setIsReasoningCompleted(true);
            return;
        }
    }, [chatMessages, currentSessionId]);

    useEffect(() => {
        scrollToBottom();
    }, [messages, loading, reasoningSteps]);

    const scrollToBottom = () => {
        messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
    };

    const handleDeleteSession = async (sessionId) => {
        if (!window.confirm('Bạn có chắc muốn xóa phiên này?')) return;
        try {
            await axiosClient.delete(`/chatbot/sessions/${sessionId}`);
            setSessions(prev => prev.filter(s => s.id !== sessionId));
            if (currentSessionId === sessionId) {
                const remaining = sessions.filter(s => s.id !== sessionId);
                if (remaining.length > 0) {
                    setCurrentSessionId(remaining[0].id);
                    fetchMessages(remaining[0].id);
                } else {
                    const draftId = `draft-${Date.now()}`;
                    const newSession = { id: draftId, title: 'Phiên học tập mới' };
                    setSessions([newSession]);
                    setCurrentSessionId(draftId);
                    setMessages([]);
                }
            }
        } catch (e) {
            alert('❌ Không thể xóa phiên. Vui lòng thử lại sau.');
        }
    };

    const fetchMessages = async (sessionId) => {
        if (String(sessionId).startsWith('draft')) {
            setMessages([]);
            return;
        }
        try {
            const res = await axiosClient.get(`/chatbot/sessions/${sessionId}/messages`);
            setMessages(res.data.messages || []);
        } catch (e) {
            console.error(e);
        }
    };

    const createNewSession = async () => {
        try {
            const res = await axiosClient.post('/chatbot/sessions', {
                title: 'Phiên học tập mới',
                mode: 'learning'
            });
            const newSession = {
                id: res.data.id,
                title: res.data.title || 'Phiên học tập mới',
                mode: 'learning'
            };

            setSessions([newSession, ...sessions]);
            setCurrentSessionId(newSession.id);
            fetchMessages(newSession.id);
        } catch (e) {
            console.error('Failed to create session:', e);
            const draftId = `draft-${Date.now()}`;
            const newSession = {
                id: draftId,
                title: 'Phiên học tập mới',
                mode: 'learning'
            };
            setSessions([newSession, ...sessions]);
            setCurrentSessionId(draftId);
            setMessages([]);
        }
    };

    const toggleCollapsed = () => {
        const next = !collapsed;
        setCollapsed(next);
        try { localStorage.setItem('learning_sidebar_collapsed', next ? 'true' : 'false'); } catch (e) { }
    };

    const handleSend = async () => {
        if (!input.trim()) return;

        const userMsg = { role: 'user', content: input };
        setMessages(prev => [...prev, userMsg]);
        setInput('');
        setLoading(true);

        // Clear previous reasoning steps when starting new question
        setReasoningSteps([]);
        setIsAgentProcessing(true);
        setIsReasoningCompleted(false);

        // Store AbortController for cancellation
        const controller = new AbortController();
        setAbortController(controller);

        // Generate request_id for tracking - CRITICAL for WebSocket filtering
        const requestId = `learning_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
        currentRequestIdRef.current = requestId;  // Set BEFORE making request
        console.log('[Learning] Starting request:', requestId);

        try {
            const payload = {
                message: userMsg.content,
                request_id: requestId
            };
            if (currentSessionId && !String(currentSessionId).startsWith('draft')) {
                payload.session_id = String(currentSessionId);
            }

            const res = await axiosClient.post('/learning/chat', payload, {
                timeout: 120000,
            });
            const data = res.data;

            const botMsg = {
                role: 'assistant',
                content: data.answer || data.response || '(Không có phản hồi)',
                reasoningSteps: [...reasoningStepsRef.current]
            };
            setMessages(prev => [...prev, botMsg]);

            // Agent finished - mark reasoning as completed but DON'T clear steps yet
            setIsAgentProcessing(false);
            setIsReasoningCompleted(true);

            if (data.session_id && String(currentSessionId).startsWith('draft')) {
                const realId = data.session_id;
                setSessions(prev => prev.map(s => s.id === currentSessionId ? { ...s, id: realId, title: data.title || s.title } : s));
                setCurrentSessionId(realId);
            }

            fetchSessions();

        } catch (e) {
            if (e.name === 'CanceledError' || e.name === 'AbortError') {
                // Request was cancelled
                setMessages(prev => [...prev, {
                    role: 'assistant',
                    content: '⚠️ Yêu cầu đã bị hủy bởi người dùng.',
                    cancelled: true
                }]);
            } else {
                setMessages(prev => [...prev, { role: 'assistant', content: '❌ Không thể kết nối đến máy chủ. Vui lòng kiểm tra kết nối mạng và thử lại.' }]);
            }
            setIsAgentProcessing(false);
            setIsReasoningCompleted(true);
            // Clear request_id on error so we don't get stuck
            currentRequestIdRef.current = null;
        } finally {
            setLoading(false);
            setAbortController(null);
            // Note: Don't clear currentRequestIdRef on success - it helps filter late-arriving events
        }
    };

    const handleFileUpload = async (event) => {
        const files = Array.from(event.target.files);
        if (!files || files.length === 0) return;

        const allowedTypes = ['.txt', '.docx', '.pdf'];
        const maxFileSize = 20 * 1024 * 1024; // 20MB per file

        // Validate all files first
        for (const file of files) {
            const fileExt = file.name.substring(file.name.lastIndexOf('.')).toLowerCase();
            if (!allowedTypes.includes(fileExt)) {
                alert(`⚠️ File "${file.name}" không được hỗ trợ.\n\nVui lòng chọn file dạng: .txt, .docx hoặc .pdf`);
                return;
            }

            if (file.size > maxFileSize) {
                alert(`⚠️ File "${file.name}" quá lớn.\n\nKích thước tối đa cho phép là 20MB.`);
                return;
            }
        }

        // Calculate total size
        const totalSize = files.reduce((sum, file) => sum + file.size, 0);
        const totalSizeMB = (totalSize / (1024 * 1024)).toFixed(2);

        const confirmMsg = `Bạn muốn tải lên ${files.length} file (tổng ${totalSizeMB}MB)?`;
        if (!window.confirm(confirmMsg)) {
            return;
        }

        setUploadingDoc(true);

        try {
            console.log(`⏳ Đang xử lý ${files.length} file (${totalSizeMB}MB)... Vui lòng đợi.`);

            const formData = new FormData();
            files.forEach(file => {
                formData.append('files', file);
            });

            const res = await axiosClient.post('/learning/upload-documents-batch', formData, {
                headers: {
                    'Content-Type': 'multipart/form-data'
                },
                timeout: 300000 // 5 minutes for large files
            });

            const successCount = res.data.uploaded_documents?.length || 0;
            alert(`Đã tải lên thành công ${successCount}/${files.length} file!\n\nTài liệu đã sẵn sàng để sử dụng trong trò chuyện học tập.`);
            fetchDocuments();

        } catch (e) {
            console.error('Upload error:', e);
            if (e.code === 'ECONNABORTED' || e.message.includes('timeout')) {
                alert('⚠️ Upload timeout!\n\nFile quá lớn hoặc mất quá nhiều thời gian xử lý.\n\nGợi ý:\n• Chia nhỏ file thành nhiều phần\n• Chỉ upload file dưới 10MB mỗi lần\n• Kiểm tra kết nối mạng');
            } else {
                const errorMsg = e.response?.data?.detail || e.message;
                alert('❌ Không thể tải tài liệu lên. Vui lòng thử lại sau.');
            }
        } finally {
            setUploadingDoc(false);
            if (fileInputRef.current) {
                fileInputRef.current.value = '';
            }
        }
    };

    const handleDeleteDocument = async (docId) => {
        if (!window.confirm('Bạn có chắc muốn xóa tài liệu này?')) return;

        try {
            await axiosClient.delete(`/learning/documents/${docId}`);
            alert('✅ Đã xóa tài liệu thành công!');
            fetchDocuments();
        } catch (e) {
            alert('❌ Không thể xóa tài liệu. Vui lòng thử lại sau.');
        }
    };

    return (
        <div className="container chat-container" style={{
            background: 'linear-gradient(135deg, #f0f9ff 0%, #e0f2fe 100%)'
        }}>
            {collapsed && (
                <div style={{ width: '48px', display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0 }}>
                    <button
                        onClick={toggleCollapsed}
                        title="Mở sidebar"
                        className="btn"
                        style={{
                            width: '40px',
                            height: '40px',
                            borderRadius: '50%',
                            border: '1px solid var(--border-color)',
                            background: 'var(--bg-surface)',
                            color: 'var(--text-secondary)',
                            padding: 0,
                            boxShadow: 'var(--shadow-md)',
                        }}
                    >
                        <ChevronRight size={20} />
                    </button>
                </div>
            )}

            {!collapsed && (
                <div className="chat-sidebar">
                    <button
                        onClick={toggleCollapsed}
                        title="Thu nhỏ sidebar"
                        className="btn"
                        style={{
                            position: 'absolute',
                            top: '50%',
                            right: '-20px',
                            transform: 'translateY(-50%)',
                            width: '40px',
                            height: '40px',
                            borderRadius: '50%',
                            border: '1px solid var(--border-color)',
                            background: 'var(--bg-surface)',
                            color: 'var(--text-secondary)',
                            padding: 0,
                            boxShadow: 'var(--shadow-md)',
                            zIndex: 40,
                        }}
                    >
                        <ChevronLeft size={20} />
                    </button>

                    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '1.5rem' }}>
                        <h3 style={{
                            margin: 0,
                            fontSize: '1.1rem',
                            fontWeight: '700',
                            color: 'var(--text-primary)'
                        }}>
                            Lịch sử học tập
                        </h3>
                    </div>

                    <button
                        className="btn btn-primary"
                        onClick={createNewSession}
                        style={{
                            marginBottom: '1rem',
                            width: '100%',
                            justifyContent: 'center'
                        }}
                    >
                        <Plus size={18} /> <span style={{ marginLeft: '0.5rem' }}>Phiên học tập mới</span>
                    </button>

                    <div style={{
                        marginBottom: '1rem',
                        padding: '0.75rem',
                        background: 'white',
                        borderRadius: '8px',
                        border: '1px solid var(--border-color)'
                    }}>
                        <div style={{
                            display: 'flex',
                            alignItems: 'center',
                            justifyContent: 'space-between',
                            marginBottom: '0.5rem'
                        }}>
                            <span style={{ fontSize: '0.9rem', fontWeight: '600' }}>
                                📚 Tài liệu ({documents.length})
                            </span>
                            <button
                                className="btn btn-sm"
                                onClick={() => setShowDocumentPanel(!showDocumentPanel)}
                                style={{ padding: '0.25rem 0.5rem', fontSize: '0.8rem' }}
                            >
                                {showDocumentPanel ? 'Ẩn' : 'Xem'}
                            </button>
                        </div>

                        <input
                            type="file"
                            ref={fileInputRef}
                            onChange={handleFileUpload}
                            accept=".txt,.docx,.pdf"
                            multiple
                            style={{ display: 'none' }}
                        />

                        <button
                            className="btn btn-outline"
                            onClick={() => fileInputRef.current?.click()}
                            disabled={uploadingDoc}
                            style={{
                                width: '100%',
                                fontSize: '0.85rem',
                                padding: '0.5rem',
                                justifyContent: 'center'
                            }}
                        >
                            <Upload size={16} />
                            <span style={{ marginLeft: '0.5rem' }}>
                                {uploadingDoc ? 'Đang tải...' : 'Tải tài liệu lên'}
                            </span>
                        </button>

                        {showDocumentPanel && (
                            <div style={{
                                marginTop: '0.75rem',
                                maxHeight: '150px',
                                overflowY: 'auto'
                            }}>
                                {documents.length === 0 ? (
                                    <p style={{
                                        fontSize: '0.8rem',
                                        color: 'var(--text-tertiary)',
                                        textAlign: 'center',
                                        margin: '0.5rem 0'
                                    }}>
                                        Chưa có tài liệu
                                    </p>
                                ) : (
                                    documents.map(doc => (
                                        <div
                                            key={doc.id}
                                            style={{
                                                padding: '0.4rem',
                                                marginBottom: '0.4rem',
                                                background: 'var(--bg-secondary)',
                                                borderRadius: '4px',
                                                fontSize: '0.8rem'
                                            }}
                                        >
                                            <div style={{
                                                display: 'flex',
                                                alignItems: 'center',
                                                justifyContent: 'space-between',
                                            }}>
                                                <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', flex: 1, overflow: 'hidden' }}>
                                                    <FileText size={14} />
                                                    <span style={{
                                                        overflow: 'hidden',
                                                        textOverflow: 'ellipsis',
                                                        whiteSpace: 'nowrap'
                                                    }}>
                                                        {doc.filename}
                                                    </span>
                                                    {doc.uploaded_by_admin && (
                                                        <span style={{
                                                            fontSize: '0.7rem',
                                                            background: '#3b82f6',
                                                            color: 'white',
                                                            padding: '0.1rem 0.3rem',
                                                            borderRadius: '3px'
                                                        }}>Admin</span>
                                                    )}
                                                </div>
                                                {!doc.uploaded_by_admin && (
                                                    <button
                                                        onClick={() => handleDeleteDocument(doc.id)}
                                                        style={{
                                                            background: 'transparent',
                                                            border: 'none',
                                                            color: 'var(--danger-color)',
                                                            cursor: 'pointer',
                                                            padding: '0.2rem'
                                                        }}
                                                    >
                                                        <Trash2 size={14} />
                                                    </button>
                                                )}
                                            </div>
                                        </div>
                                    ))
                                )}
                            </div>
                        )}
                    </div>

                    <div style={{
                        flex: 1,
                        overflowY: 'auto',
                        display: 'flex',
                        flexDirection: 'column',
                        gap: '0.5rem',
                        paddingRight: '0.5rem'
                    }}>
                        {sessions.map(sess => (
                            <div
                                key={sess.id}
                                className={`session-item ${currentSessionId === sess.id ? 'active' : ''}`}
                                onClick={() => setCurrentSessionId(sess.id)}
                            >
                                <div style={{
                                    display: 'flex',
                                    alignItems: 'center',
                                    gap: '0.75rem',
                                    flex: 1,
                                    overflow: 'hidden'
                                }}>
                                    <MessageSquare size={18} style={{ flexShrink: 0, opacity: currentSessionId === sess.id ? 1 : 0.7 }} />
                                    <span style={{
                                        whiteSpace: 'nowrap',
                                        overflow: 'hidden',
                                        textOverflow: 'ellipsis',
                                        fontSize: '0.9rem',
                                        fontWeight: currentSessionId === sess.id ? '600' : '500'
                                    }}>
                                        {sess.title || 'Phiên học tập mới'}
                                    </span>
                                </div>

                                {!String(sess.id).startsWith('draft') && (
                                    <button
                                        onClick={(e) => { e.stopPropagation(); handleDeleteSession(sess.id); }}
                                        className="delete-btn btn-ghost"
                                        title="Xóa phiên"
                                        style={{
                                            padding: '4px',
                                            borderRadius: '4px',
                                            display: 'flex',
                                            alignItems: 'center',
                                            justifyContent: 'center',
                                            opacity: currentSessionId === sess.id ? 1 : 0,
                                            transition: 'all 0.2s ease'
                                        }}
                                    >
                                        <Trash2 size={16} />
                                    </button>
                                )}
                            </div>
                        ))}
                    </div>
                </div>
            )}

            <div className="chat-main">
                <div className="chat-header" style={{
                    background: 'linear-gradient(135deg, #e8f5e9 0%, #f1f8f4 100%)'
                }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
                        <div className="chat-header-avatar">
                            <span>📚</span>
                        </div>
                        <div>
                            <h3 style={{ margin: 0, fontSize: '1rem', fontWeight: '600', color: 'var(--text-primary)' }}>
                                Trợ lý học tập EduTwin
                            </h3>
                            <p style={{
                                margin: 0,
                                fontSize: '0.8rem',
                                color: 'var(--text-tertiary)',
                                marginTop: '0.2rem'
                            }}>
                                Giải bài tập dựa trên tài liệu
                            </p>
                        </div>
                    </div>
                </div>

                <div className="chat-messages">
                    {messages.length === 0 && (
                        <div style={{
                            display: 'flex',
                            flexDirection: 'column',
                            alignItems: 'center',
                            justifyContent: 'center',
                            height: '100%',
                            color: 'var(--text-tertiary)',
                            textAlign: 'center',
                            padding: '2rem'
                        }}>
                            <div style={{ fontSize: '3rem', marginBottom: '1rem', opacity: 0.5 }}>📚</div>
                            <h3 style={{ fontSize: '1.2rem', fontWeight: '600', marginBottom: '0.5rem', color: 'var(--text-secondary)' }}>Bắt đầu học tập mới</h3>
                            <p style={{ maxWidth: '400px' }}>Tải tài liệu lên và hỏi tôi về nội dung bài học, bài tập hoặc kiến thức liên quan.</p>
                        </div>
                    )}

                    {messages.map((msg, idx) => {
                        // Check if this is the last assistant message and we have reasoning steps
                        const isLastAssistantMsg = msg.role === 'assistant' &&
                            idx === messages.length - 1 &&
                            reasoningSteps.length > 0;

                        // If this is the last assistant message with reasoning, show reasoning before it
                        if (isLastAssistantMsg) {
                            return (
                                <div key={idx}>
                                    {/* Show reasoning steps BEFORE final response */}
                                    <ReasoningDisplay
                                        steps={reasoningSteps}
                                        isProcessing={isAgentProcessing}
                                        isCompleted={isReasoningCompleted}
                                    />

                                    {/* Final response */}
                                    <div style={{
                                        display: 'flex',
                                        justifyContent: 'flex-start',
                                        alignItems: 'flex-end',
                                        gap: '0.75rem'
                                    }}>
                                        <div style={{
                                            width: '28px',
                                            height: '28px',
                                            borderRadius: '50%',
                                            background: 'linear-gradient(135deg, #34d399 0%, #10b981 100%)',
                                            display: 'flex',
                                            alignItems: 'center',
                                            justifyContent: 'center',
                                            fontSize: '0.9rem',
                                            flexShrink: 0
                                        }}>📚</div>
                                        <div className={`chat-message ${msg.role}`}>
                                            <div className="markdown-content">
                                                <MarkdownWithMath content={msg.content} />
                                            </div>
                                        </div>
                                    </div>
                                </div>
                            );
                        }

                        // Normal message rendering
                        return (
                            <div key={idx}>
                                {/* Show reasoning steps saved with this message */}
                                {msg.role === 'assistant' && msg.reasoningSteps && msg.reasoningSteps.length > 0 && (
                                    <ReasoningDisplay
                                        steps={msg.reasoningSteps}
                                        isProcessing={false}
                                        isCompleted={true}
                                        defaultCollapsed={true}
                                    />
                                )}
                                <div style={{
                                    display: 'flex',
                                    justifyContent: msg.role === 'user' ? 'flex-end' : 'flex-start',
                                    alignItems: 'flex-end',
                                    gap: '0.75rem'
                                }}>
                                    {msg.role === 'assistant' && (
                                        <div style={{
                                            width: '28px',
                                            height: '28px',
                                            borderRadius: '50%',
                                            background: 'linear-gradient(135deg, #34d399 0%, #10b981 100%)',
                                            display: 'flex',
                                            alignItems: 'center',
                                            justifyContent: 'center',
                                            fontSize: '0.9rem',
                                            flexShrink: 0
                                        }}>📚</div>
                                    )}

                                    <div className={`chat-message ${msg.role}`}>
                                        <div className="markdown-content">
                                            <MarkdownWithMath content={msg.content} />
                                        </div>
                                    </div>
                                </div>
                            </div>
                        );
                    })}

                    {/* Show reasoning steps ONLY while processing (before response arrives) */}
                    {/* Once response is in messages, reasoning is shown with the message above */}
                    {reasoningSteps.length > 0 && isAgentProcessing && (
                        <ReasoningDisplay
                            steps={reasoningSteps}
                            isProcessing={isAgentProcessing}
                            isCompleted={isReasoningCompleted}
                        />
                    )}

                    {isTyping && !loading && (
                        <div className="animate-fade-in" style={{
                            display: 'flex',
                            justifyContent: 'flex-start',
                            alignItems: 'flex-end',
                            gap: '0.75rem'
                        }}>
                            <div style={{
                                width: '28px',
                                height: '28px',
                                borderRadius: '50%',
                                background: 'linear-gradient(135deg, #34d399 0%, #10b981 100%)',
                                display: 'flex',
                                alignItems: 'center',
                                justifyContent: 'center',
                                fontSize: '0.9rem',
                                flexShrink: 0
                            }}>📚</div>
                            <div style={{
                                background: 'white',
                                padding: '1rem',
                                borderRadius: '1rem',
                                borderTopLeftRadius: '4px',
                                border: '1px solid var(--border-color)',
                                boxShadow: 'var(--shadow-sm)'
                            }}>
                                <div style={{ display: 'flex', gap: '4px' }}>
                                    <span className="dot-animate" style={{ animationDelay: '0s', width: '8px', height: '8px', background: 'var(--text-tertiary)', borderRadius: '50%' }}></span>
                                    <span className="dot-animate" style={{ animationDelay: '0.2s', width: '8px', height: '8px', background: 'var(--text-tertiary)', borderRadius: '50%' }}></span>
                                    <span className="dot-animate" style={{ animationDelay: '0.4s', width: '8px', height: '8px', background: 'var(--text-tertiary)', borderRadius: '50%' }}></span>
                                </div>
                            </div>
                        </div>
                    )}

                    {loading && (
                        <div style={{ display: 'flex', justifyContent: 'flex-start', alignItems: 'flex-end', gap: '0.75rem' }}>
                            <div style={{
                                width: '28px',
                                height: '28px',
                                borderRadius: '50%',
                                background: 'linear-gradient(135deg, #34d399 0%, #10b981 100%)',
                                display: 'flex',
                                alignItems: 'center',
                                justifyContent: 'center',
                                fontSize: '0.9rem',
                                flexShrink: 0
                            }}>📚</div>
                            <div style={{
                                background: 'white',
                                padding: '1rem',
                                borderRadius: '1rem',
                                borderTopLeftRadius: '4px',
                                border: '1px solid var(--border-color)',
                                boxShadow: 'var(--shadow-sm)'
                            }}>
                                <div style={{ display: 'flex', gap: '4px' }}>
                                    <span className="dot-animate" style={{ animationDelay: '0s', width: '8px', height: '8px', background: 'var(--text-tertiary)', borderRadius: '50%' }}></span>
                                    <span className="dot-animate" style={{ animationDelay: '0.2s', width: '8px', height: '8px', background: 'var(--text-tertiary)', borderRadius: '50%' }}></span>
                                    <span className="dot-animate" style={{ animationDelay: '0.4s', width: '8px', height: '8px', background: 'var(--text-tertiary)', borderRadius: '50%' }}></span>
                                </div>
                            </div>
                        </div>
                    )}

                    <div ref={messagesEndRef} />
                </div>

                <div className="chat-input-area">
                    <div style={{
                        display: 'flex',
                        gap: '0.75rem',
                        alignItems: 'center',
                        width: '100%'
                    }}>
                        <input
                            className="input-field"
                            placeholder="Gửi câu hỏi hoặc bài tập..."
                            value={input}
                            onChange={(e) => setInput(e.target.value)}
                            onKeyDown={(e) => e.key === 'Enter' && !loading && input.trim() && handleSend()}
                            disabled={loading}
                            style={{ margin: 0, boxShadow: 'var(--shadow-sm)', flex: 1 }}
                        />
                        <button
                            className="btn btn-primary"
                            onClick={handleSend}
                            disabled={loading || !input.trim()}
                            title="Gửi tin nhắn (Enter)"
                            style={{
                                width: '48px',
                                height: '48px',
                                padding: 0,
                                borderRadius: '12px',
                                display: 'flex',
                                alignItems: 'center',
                                justifyContent: 'center',
                                flexShrink: 0,
                                opacity: loading ? 0.6 : 1
                            }}
                        >
                            <Send size={20} />
                        </button>
                    </div>
                </div>
            </div>
        </div>
    );
};

export default Learning;

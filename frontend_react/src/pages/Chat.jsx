import React, { useState, useEffect, useRef } from 'react';
import { createPortal } from 'react-dom';
import { Send, Plus, MessageSquare, Trash2, ChevronLeft, ChevronRight, Square } from 'lucide-react';
import axiosClient from '../api/axiosClient';
import { useAuth } from '../context/AuthContext';
import { useWebSocket } from '../context/WebSocketContext';
import PreferenceVisualizer from '../components/PreferenceVisualizer';
import MarkdownWithMath from '../components/MarkdownWithMath';

const Chat = () => {
    const { user } = useAuth();
    const { connected, chatMessages, isTyping, joinChatSession, leaveChatSession, clearChatMessages } = useWebSocket();

    const [sessions, setSessions] = useState([]);
    const [currentSessionId, setCurrentSessionId] = useState(null);
    const [messages, setMessages] = useState([]);
    const [input, setInput] = useState('');
    const [loading, setLoading] = useState(false);
    const [preferenceCount, setPreferenceCount] = useState(0);
    const [collapsed, setCollapsed] = useState(() => {
        try {
            return localStorage.getItem('chat_sidebar_collapsed') === 'true';
        } catch (e) {
            return false;
        }
    });

    const messagesEndRef = useRef(null);
    const abortControllerRef = useRef(null);
    const cancelledRequestRef = useRef(false);
    const currentRequestIdRef = useRef(null);
    const [headerPortalTarget, setHeaderPortalTarget] = useState(null);

    // Generate unique request ID
    const generateRequestId = () => {
        return `req_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
    };

    useEffect(() => {
        const target = document.getElementById('header-portal');
        if (target) {
            setHeaderPortalTarget(target);
        }
    }, []);

    useEffect(() => {
        fetchSessions();
        fetchPreferenceCount();
    }, []);

    const fetchPreferenceCount = async () => {
        try {
            const res = await axiosClient.get('/user/preferences');
            const learned = res.data.learned || [];
            setPreferenceCount(Array.isArray(learned) ? learned.length : 0);
        } catch (e) {
            console.error('Failed to fetch preference count:', e);
        }
    };

    const fetchSessions = async () => {
        try {
            const res = await axiosClient.get('/chatbot/sessions', {
                params: { mode: 'chat' }
            });
            setSessions(res.data);
            if (res.data.length > 0 && !currentSessionId) {
                setCurrentSessionId(res.data[0].id);
            }
        } catch (e) {
            console.error(e);
        }
    };

    useEffect(() => {
        if (currentSessionId) {
            fetchMessages(currentSessionId);

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

    useEffect(() => {
        if (chatMessages.length > 0) {
            const latestMessage = chatMessages[chatMessages.length - 1];
            console.log('[Chat] WebSocket message received:', {
                session_id: latestMessage.session_id,
                currentSessionId,
                mode: latestMessage.mode,
                message: latestMessage.message?.substring(0, 50),
                cancelled: cancelledRequestRef.current
            });

            // Ignore WebSocket messages if request was cancelled
            if (cancelledRequestRef.current) {
                console.log('[Chat] Ignoring WebSocket message - request was cancelled');
                return;
            }

            if ((latestMessage.session_id === currentSessionId || latestMessage.session_id === String(currentSessionId)) && latestMessage.mode === 'chat') {
                const newMsg = {
                    role: latestMessage.role || 'assistant',
                    content: latestMessage.message
                };
                setMessages(prev => {
                    const isDuplicate = prev.some(m =>
                        m.content === newMsg.content &&
                        m.role === newMsg.role &&
                        prev.indexOf(m) >= prev.length - 2
                    );
                    console.log('[Chat] isDuplicate:', isDuplicate, 'current count:', prev.length);
                    if (isDuplicate) return prev;
                    return [...prev, newMsg];
                });
            }
        }
    }, [chatMessages, currentSessionId]);

    useEffect(() => {
        scrollToBottom();
    }, [messages, loading]);

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
                    const newSession = { id: draftId, title: 'Phiên mới' };
                    setSessions([newSession]);
                    setCurrentSessionId(draftId);
                    setMessages([]);
                }
            }
        } catch (e) {
            alert('Lỗi xóa phiên: ' + (e.message || e));
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
                title: 'Phiên mới',
                mode: 'chat'
            });
            const newSession = {
                id: res.data.id,
                title: res.data.title || 'Phiên mới',
                mode: 'chat'
            };

            setSessions([newSession, ...sessions]);
            setCurrentSessionId(newSession.id);
            fetchMessages(newSession.id);
        } catch (e) {
            console.error('Failed to create session:', e);
            const draftId = `draft-${Date.now()}`;
            const newSession = {
                id: draftId,
                title: 'Phiên mới',
                mode: 'chat'
            };
            setSessions([newSession, ...sessions]);
            setCurrentSessionId(draftId);
            setMessages([]);
        }
    };

    const toggleCollapsed = () => {
        const next = !collapsed;
        setCollapsed(next);
        try { localStorage.setItem('chat_sidebar_collapsed', next ? 'true' : 'false'); } catch (e) { }
    };

    const handleSend = async () => {
        if (!input.trim()) return;

        const userMsg = { role: 'user', content: input };
        setMessages(prev => [...prev, userMsg]);
        setInput('');
        setLoading(true);

        // Reset cancelled flag and create new AbortController for this request
        cancelledRequestRef.current = false;
        abortControllerRef.current = new AbortController();

        // Generate unique request ID for cancel support
        const requestId = generateRequestId();
        currentRequestIdRef.current = requestId;

        try {
            const payload = {
                message: userMsg.content,
                request_id: requestId,
            };
            if (currentSessionId && !String(currentSessionId).startsWith('draft')) {
                payload.session_id = String(currentSessionId);
            }

            const res = await axiosClient.post('/chatbot', payload, {
                timeout: 120000,
                signal: abortControllerRef.current.signal,
            });
            const data = res.data;

            // If request was cancelled on backend, don't show response
            if (data.cancelled) {
                return;
            }

            const botMsg = {
                role: 'assistant',
                content: data.answer || data.response || '(Không có phản hồi)'
            };
            setMessages(prev => [...prev, botMsg]);

            if (data.session_id && String(currentSessionId).startsWith('draft')) {
                const realId = data.session_id;
                setSessions(prev => prev.map(s => s.id === currentSessionId ? { ...s, id: realId, title: data.title || s.title } : s));
                setCurrentSessionId(realId);
            }

            fetchSessions();
            fetchPreferenceCount();

        } catch (e) {
            // Don't show error message if request was cancelled
            if (e.name === 'CanceledError' || e.code === 'ERR_CANCELED') {
                setMessages(prev => [...prev, { role: 'assistant', content: '⏹️ Đã hủy yêu cầu.' }]);
            } else {
                setMessages(prev => [...prev, { role: 'assistant', content: 'Lỗi kết nối: ' + e.message }]);
            }
        } finally {
            setLoading(false);
            abortControllerRef.current = null;
            currentRequestIdRef.current = null;
        }
    };

    const handleCancel = async () => {
        if (abortControllerRef.current) {
            cancelledRequestRef.current = true;

            // Notify backend to cancel the request (so it won't save to DB)
            const requestId = currentRequestIdRef.current;
            if (requestId) {
                try {
                    await axiosClient.post('/chatbot/cancel', { request_id: requestId });
                    console.log('[Chat] Cancel request sent to backend:', requestId);
                } catch (err) {
                    console.warn('[Chat] Failed to send cancel to backend:', err);
                }
            }

            abortControllerRef.current.abort();
        }
    };



    return (
        <div className="container chat-container">
            {headerPortalTarget && createPortal(
                <PreferenceVisualizer preferenceCount={preferenceCount} />,
                headerPortalTarget
            )}

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
                            Lịch sử chat
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
                        <Plus size={18} /> <span style={{ marginLeft: '0.5rem' }}>Cuộc trò chuyện mới</span>
                    </button>

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
                                        {sess.title || 'Phiên chat mới'}
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
                    background: 'linear-gradient(135deg, #e3f2fd 0%, #f1f8fd 100%)'
                }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
                        <div className="chat-header-avatar">
                            <span>🤖</span>
                        </div>
                        <div>
                            <h3 style={{ margin: 0, fontSize: '1rem', fontWeight: '600', color: 'var(--text-primary)' }}>
                                Trợ lý ảo EduTwin
                            </h3>
                            <p style={{
                                margin: 0,
                                fontSize: '0.8rem',
                                color: 'var(--text-tertiary)',
                                marginTop: '0.2rem'
                            }}>
                                Trò chuyện và phân tích
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
                            <div style={{ fontSize: '3rem', marginBottom: '1rem', opacity: 0.5 }}>💬</div>
                            <h3 style={{ fontSize: '1.2rem', fontWeight: '600', marginBottom: '0.5rem', color: 'var(--text-secondary)' }}>Bắt đầu cuộc trò chuyện mới</h3>
                            <p style={{ maxWidth: '400px' }}>Hãy hỏi tôi về điểm số, xu hướng học tập hoặc lời khuyên để cải thiện kết quả của bạn.</p>
                        </div>
                    )}

                    {messages.map((msg, idx) => (
                        <div
                            key={idx}
                            style={{
                                display: 'flex',
                                justifyContent: msg.role === 'user' ? 'flex-end' : 'flex-start',
                                alignItems: 'flex-end',
                                gap: '0.75rem'
                            }}
                        >
                            {msg.role === 'assistant' && (
                                <div style={{
                                    width: '28px',
                                    height: '28px',
                                    borderRadius: '50%',
                                    background: 'var(--primary-light)',
                                    display: 'flex',
                                    alignItems: 'center',
                                    justifyContent: 'center',
                                    fontSize: '0.9rem',
                                    flexShrink: 0
                                }}>🤖</div>
                            )}

                            <div className={`chat-message ${msg.role}`}>
                                <div className="markdown-content">
                                    <MarkdownWithMath content={msg.content} />
                                </div>
                            </div>
                        </div>
                    ))}

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
                                background: 'var(--primary-light)',
                                display: 'flex',
                                alignItems: 'center',
                                justifyContent: 'center',
                                fontSize: '0.9rem',
                                flexShrink: 0
                            }}>🤖</div>
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
                                background: 'var(--primary-light)',
                                display: 'flex',
                                alignItems: 'center',
                                justifyContent: 'center',
                                fontSize: '0.9rem',
                                flexShrink: 0
                            }}>🤖</div>
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
                            placeholder="Nhập câu hỏi của bạn..."
                            value={input}
                            onChange={(e) => setInput(e.target.value)}
                            onKeyDown={(e) => {
                                if (e.key === 'Enter') {
                                    if (loading) {
                                        handleCancel();
                                    } else {
                                        handleSend();
                                    }
                                }
                            }}
                            disabled={false}
                            style={{ margin: 0, boxShadow: 'var(--shadow-sm)', flex: 1 }}
                        />
                        <button
                            className={`btn ${loading ? 'btn-danger' : 'btn-primary'}`}
                            onClick={loading ? handleCancel : handleSend}
                            disabled={!loading && !input.trim()}
                            title={loading ? 'Hủy yêu cầu (Enter)' : 'Gửi tin nhắn (Enter)'}
                            style={{
                                width: '48px',
                                height: '48px',
                                padding: 0,
                                borderRadius: '12px',
                                display: 'flex',
                                alignItems: 'center',
                                justifyContent: 'center',
                                flexShrink: 0,
                                transition: 'all 0.2s ease'
                            }}
                        >
                            {loading ? <Square size={20} /> : <Send size={20} />}
                        </button>
                    </div>
                </div>
            </div>
        </div>
    );
};

export default Chat;

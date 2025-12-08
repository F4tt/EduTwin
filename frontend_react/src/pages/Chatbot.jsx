import React, { useState, useEffect, useRef } from 'react';
import { createPortal } from 'react-dom';
import { Send, Plus, MessageSquare, Trash2, Check, X, ChevronLeft, ChevronRight } from 'lucide-react';
import ReactMarkdown from 'react-markdown';
import axiosClient from '../api/axiosClient';
import { useAuth } from '../context/AuthContext';
import { useWebSocket } from '../context/WebSocketContext';
import PreferenceVisualizer from '../components/PreferenceVisualizer';

const Chatbot = () => {
    const { user } = useAuth();
    const { connected, chatMessages, isTyping, joinChatSession, leaveChatSession, clearChatMessages } = useWebSocket();
    const [sessions, setSessions] = useState([]);
    const [currentSessionId, setCurrentSessionId] = useState(null);
    const [messages, setMessages] = useState([]);
    const [input, setInput] = useState('');
    const [loading, setLoading] = useState(false);
    const [pendingScore, setPendingScore] = useState(null);
    const [preferenceCount, setPreferenceCount] = useState(0);
    const [collapsed, setCollapsed] = useState(() => {
        try {
            return localStorage.getItem('chat_sidebar_collapsed') === 'true';
        } catch (e) {
            return false;
        }
    });
    const messagesEndRef = useRef(null);
    const [headerPortalTarget, setHeaderPortalTarget] = useState(null);

    useEffect(() => {
        // Find the portal target in Layout
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

    useEffect(() => {
        if (currentSessionId) {
            fetchMessages(currentSessionId);

            // Join WebSocket room for this chat session
            if (!String(currentSessionId).startsWith('draft')) {
                joinChatSession(currentSessionId);
            }

            // Clear previous messages from WebSocket
            clearChatMessages();
        }

        // Cleanup: leave room when session changes
        return () => {
            if (currentSessionId && !String(currentSessionId).startsWith('draft')) {
                leaveChatSession(currentSessionId);
            }
        };
    }, [currentSessionId, joinChatSession, leaveChatSession, clearChatMessages]);

    // Listen for WebSocket chat messages
    useEffect(() => {
        if (chatMessages.length > 0) {
            const latestMessage = chatMessages[chatMessages.length - 1];
            // Only add if it's for current session
            if (latestMessage.session_id === currentSessionId || latestMessage.session_id === String(currentSessionId)) {
                const newMsg = {
                    role: latestMessage.role || 'assistant',
                    content: latestMessage.message
                };
                // Avoid duplicates by checking if message already exists
                setMessages(prev => {
                    const isDuplicate = prev.some(m =>
                        m.content === newMsg.content &&
                        m.role === newMsg.role &&
                        prev.indexOf(m) >= prev.length - 2 // Check last 2 messages
                    );
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

    const fetchSessions = async () => {
        try {
            const res = await axiosClient.get('/chatbot/sessions');
            setSessions(res.data);
            if (res.data.length > 0 && !currentSessionId) {
                setCurrentSessionId(res.data[0].id);
            }
        } catch (e) {
            console.error(e);
        }
    };

    const handleDeleteSession = async (sessionId) => {
        if (!window.confirm('Bạn có chắc muốn xóa phiên này?')) return;
        try {
            await axiosClient.delete(`/chatbot/sessions/${sessionId}`);
            setSessions(prev => prev.filter(s => s.id !== sessionId));
            // if deleted current session, fallback to first persisted or create a draft
            if (currentSessionId === sessionId) {
                const remaining = sessions.filter(s => s.id !== sessionId);
                if (remaining.length > 0) {
                    setCurrentSessionId(remaining[0].id);
                    fetchMessages(remaining[0].id);
                } else {
                    // create a local draft
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
            // Call backend to create session with initial greeting
            const res = await axiosClient.post('/chatbot/sessions', { title: 'Phiên mới' });
            const newSession = { id: res.data.id, title: res.data.title || 'Phiên mới' };

            // Add to sessions list and set as current
            setSessions([newSession, ...sessions]);
            setCurrentSessionId(newSession.id);

            // Fetch messages to get the initial greeting
            fetchMessages(newSession.id);
        } catch (e) {
            console.error('Failed to create session:', e);
            // Fallback to draft session on error
            const draftId = `draft-${Date.now()}`;
            const newSession = { id: draftId, title: 'Phiên mới' };
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
        setPendingScore(null);

        try {
            const payload = { message: userMsg.content };
            if (user) payload.client_user_id = user.user_id;
            if (currentSessionId && !String(currentSessionId).startsWith('draft')) {
                payload.session_id = currentSessionId;
            }

            // Use regular endpoint (faster than streaming for now)
            const res = await axiosClient.post('/chatbot', payload, {
                timeout: 120000, // 120 seconds - allow enough time for LLM response
            });
            const data = res.data;

            const botMsg = {
                role: 'assistant',
                content: data.answer || data.response || '(Không có phản hồi)'
            };
            setMessages(prev => [...prev, botMsg]);

            // Handle side effects
            if (data.pending_score_update) {
                setPendingScore(data.pending_score_update);
            }

            // If session was draft, update ID
            if (data.session_id && String(currentSessionId).startsWith('draft')) {
                const realId = data.session_id;
                setSessions(prev => prev.map(s => s.id === currentSessionId ? { ...s, id: realId, title: data.title || s.title } : s));
                setCurrentSessionId(realId);
            }

            // Refresh sessions to get updated titles if any
            fetchSessions();

            // Refresh preference count (backend learns after every 5 messages)
            fetchPreferenceCount();

        } catch (e) {
            setMessages(prev => [...prev, { role: 'assistant', content: 'Lỗi kết nối: ' + e.message }]);
        } finally {
            setLoading(false);
        }
    };

    const handleConfirmScore = async () => {
        if (!pendingScore) return;
        try {
            await axiosClient.post('/chatbot/confirm-update', {
                update_id: pendingScore.id
            });
            setPendingScore(null);
            // Add system message
            setMessages(prev => [...prev, { role: 'assistant', content: '✅ Đã cập nhật điểm thành công!' }]);

            // Trigger refresh in StudyUpdate page
            const { emitStudyScoresUpdated } = await import('../utils/eventBus');
            emitStudyScoresUpdated({ source: 'chatbot' });
        } catch (e) {
            alert('Lỗi cập nhật: ' + e.message);
        }
    };

    return (
        <div className="container chat-container">
            {/* Render PreferenceVisualizer in the Header Portal */}
            {headerPortalTarget && createPortal(
                <PreferenceVisualizer preferenceCount={preferenceCount} />,
                headerPortalTarget
            )}

            {/* Expand Button (Visible when sidebar is collapsed) */}
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

            {/* Sessions Sidebar */}
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
                                            opacity: currentSessionId === sess.id ? 1 : 0, // Show only on hover or active
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

            {/* Chat Area */}
            <div className="chat-main">
                {/* Header */}
                <div className="chat-header">
                    <div className="chat-header-avatar">
                        <span>🤖</span>
                    </div>
                    <div>
                        <h3 style={{ margin: 0, fontSize: '1rem', fontWeight: '600', color: 'var(--text-primary)' }}>Trợ lý ảo EduTwin</h3>
                    </div>
                </div>

                {/* Messages */}
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
                                    <ReactMarkdown>{msg.content}</ReactMarkdown>
                                </div>
                            </div>
                        </div>
                    ))}

                    {/* Typing Indicator from WebSocket */}
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

                    {/* Pending Score Update Card */}
                    {pendingScore && (
                        <div className="animate-fade-in pending-score-card">
                            <h4 className="pending-score-title">
                                ⚠️ Phát hiện thay đổi điểm số
                            </h4>
                            <p className="pending-score-text">
                                Môn <b>{pendingScore.subject}</b> học kỳ <b>{pendingScore.semester}</b> lớp <b>{pendingScore.grade_level}</b>: <span style={{ textDecoration: 'line-through', opacity: 0.7 }}>{pendingScore.old_score || '?'}</span> → <b style={{ color: '#059669' }}>{pendingScore.new_score}</b>
                            </p>
                            <div style={{ display: 'flex', gap: '1rem' }}>
                                <button className="btn btn-primary" style={{ padding: '0.5rem 1rem', fontSize: '0.9rem', background: '#059669', borderColor: '#059669' }} onClick={handleConfirmScore}>
                                    <Check size={16} /> Xác nhận
                                </button>
                                <button className="btn btn-outline" style={{ padding: '0.5rem 1rem', fontSize: '0.9rem', color: '#dc2626', borderColor: '#dc2626' }} onClick={() => setPendingScore(null)}>
                                    <X size={16} /> Bỏ qua
                                </button>
                            </div>
                        </div>
                    )}

                    <div ref={messagesEndRef} />
                </div>

                {/* Input Area */}
                <div className="chat-input-area">
                    <input
                        className="input-field"
                        placeholder="Nhập câu hỏi của bạn..."
                        value={input}
                        onChange={(e) => setInput(e.target.value)}
                        onKeyDown={(e) => e.key === 'Enter' && handleSend()}
                        disabled={loading}
                        style={{ margin: 0, boxShadow: 'var(--shadow-sm)' }}
                    />
                    <button
                        className="btn btn-primary"
                        onClick={handleSend}
                        disabled={loading || !input.trim()}
                        style={{
                            width: '48px',
                            height: '48px',
                            padding: 0,
                            borderRadius: '12px',
                            display: 'flex',
                            alignItems: 'center',
                            justifyContent: 'center',
                            flexShrink: 0
                        }}
                    >
                        <Send size={20} />
                    </button>
                </div>
            </div>
        </div>
    );
};

export default Chatbot;

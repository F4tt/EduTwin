import React, { useState, useEffect, useRef } from 'react';
import { Send, Plus, MessageSquare, Trash2, Check, X, ChevronLeft, ChevronRight } from 'lucide-react';
import ReactMarkdown from 'react-markdown';
import axiosClient from '../api/axiosClient';
import { useAuth } from '../context/AuthContext';

const Chatbot = () => {
    const { user } = useAuth();
    const [sessions, setSessions] = useState([]);
    const [currentSessionId, setCurrentSessionId] = useState(null);
    const [messages, setMessages] = useState([]);
    const [input, setInput] = useState('');
    const [loading, setLoading] = useState(false);
    const [pendingScore, setPendingScore] = useState(null);
    const [collapsed, setCollapsed] = useState(() => {
        try {
            return localStorage.getItem('chat_sidebar_collapsed') === 'true';
        } catch (e) {
            return false;
        }
    });
    const messagesEndRef = useRef(null);

    useEffect(() => {
        fetchSessions();
    }, []);

    useEffect(() => {
        if (currentSessionId) {
            fetchMessages(currentSessionId);
        }
    }, [currentSessionId]);

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

    const createNewSession = () => {
        const draftId = `draft-${Date.now()}`;
        const newSession = { id: draftId, title: 'Phiên mới' };
        setSessions([newSession, ...sessions]);
        setCurrentSessionId(draftId);
        setMessages([]);
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
                timeout: 60000,
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
        <div style={{ display: 'flex', height: 'calc(100vh - 4rem)', gap: '1.5rem', position: 'relative' }}>
            {/* Expand Button (Visible when sidebar is collapsed) */}
            {collapsed && (
                <button
                    onClick={toggleCollapsed}
                    title="Mở sidebar"
                    style={{
                        position: 'absolute',
                        left: '12px',
                        top: '50%',
                        transform: 'translateY(-50%)',
                        width: '36px',
                        height: '36px',
                        borderRadius: '50%',
                        border: '1px solid #e0e0e0',
                        background: '#fff',
                        color: '#555',
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'center',
                        cursor: 'pointer',
                        boxShadow: '0 2px 8px rgba(0,0,0,0.1)',
                        zIndex: 100,
                        transition: 'all 0.2s ease'
                    }}
                    onMouseEnter={(e) => {
                        e.currentTarget.style.background = '#f5f5f5';
                        e.currentTarget.style.transform = 'translateY(-50%) scale(1.1)';
                    }}
                    onMouseLeave={(e) => {
                        e.currentTarget.style.background = '#fff';
                        e.currentTarget.style.transform = 'translateY(-50%) scale(1)';
                    }}
                >
                    <ChevronRight size={20} />
                </button>
            )}


            {/* Sessions Sidebar */}
            {!collapsed && (
                <div className="card" style={{
                    width: '300px',
                    display: 'flex',
                    flexDirection: 'column',
                    padding: '1.5rem',
                    position: 'relative',
                    boxShadow: '0 4px 12px rgba(0,0,0,0.08)'
                }}>
                    <button
                        onClick={toggleCollapsed}
                        title="Thu nhỏ sidebar"
                        style={{
                            position: 'absolute',
                            top: '50%',
                            right: '-18px', // Half of 36px width
                            transform: 'translateY(-50%)',
                            width: '36px',
                            height: '36px',
                            borderRadius: '50%',
                            border: '1px solid #e0e0e0',
                            background: '#fff',
                            color: '#555',
                            display: 'flex',
                            alignItems: 'center',
                            justifyContent: 'center',
                            cursor: 'pointer',
                            boxShadow: '0 2px 8px rgba(0,0,0,0.1)',
                            zIndex: 40,
                            transition: 'all 0.2s ease'
                        }}
                        onMouseEnter={(e) => {
                            e.currentTarget.style.background = '#f5f5f5';
                            e.currentTarget.style.transform = 'translateY(-50%) scale(1.1)';
                        }}
                        onMouseLeave={(e) => {
                            e.currentTarget.style.background = '#fff';
                            e.currentTarget.style.transform = 'translateY(-50%) scale(1)';
                        }}
                    >
                        <ChevronLeft size={20} />
                    </button>

                    <h3 style={{
                        margin: '0 0 1.25rem 0',
                        fontSize: '1.1rem',
                        fontWeight: '600',
                        color: '#333'
                    }}>
                        Lịch sử trò chuyện
                    </h3>

                    <button
                        className="btn btn-primary"
                        onClick={createNewSession}
                        style={{
                            marginBottom: '1.25rem',
                            padding: '0.75rem 1rem',
                            fontSize: '0.95rem',
                            fontWeight: '500'
                        }}
                    >
                        <Plus size={18} /> <span style={{ marginLeft: '0.5rem' }}>Tạo phiên mới</span>
                    </button>

                    <div style={{
                        flex: 1,
                        overflowY: 'auto',
                        display: 'flex',
                        flexDirection: 'column',
                        gap: '0.75rem',
                        width: '100%',
                        paddingRight: '0.25rem'
                    }}>
                        {sessions.map(sess => (
                            <div key={sess.id} style={{
                                display: 'flex',
                                gap: '0.5rem',
                                alignItems: 'stretch',
                                width: '100%'
                            }}>
                                <div
                                    onClick={() => setCurrentSessionId(sess.id)}
                                    title={sess.title || 'Phiên chat'}
                                    style={{
                                        padding: '0.875rem 1rem',
                                        borderRadius: '10px',
                                        cursor: 'pointer',
                                        background: currentSessionId === sess.id ? '#fee2e2' : '#f9fafb',
                                        color: currentSessionId === sess.id ? '#d32f2f' : '#555',
                                        display: 'flex',
                                        alignItems: 'center',
                                        gap: '0.75rem',
                                        fontSize: '0.9rem',
                                        fontWeight: currentSessionId === sess.id ? '600' : '400',
                                        flex: 1,
                                        border: currentSessionId === sess.id ? '2px solid #d32f2f' : '2px solid transparent',
                                        transition: 'all 0.2s ease'
                                    }}
                                    onMouseEnter={(e) => {
                                        if (currentSessionId !== sess.id) {
                                            e.currentTarget.style.background = '#f3f4f6';
                                            e.currentTarget.style.borderColor = '#e5e7eb';
                                        }
                                    }}
                                    onMouseLeave={(e) => {
                                        if (currentSessionId !== sess.id) {
                                            e.currentTarget.style.background = '#f9fafb';
                                            e.currentTarget.style.borderColor = 'transparent';
                                        }
                                    }}
                                >
                                    <MessageSquare size={18} style={{ flexShrink: 0 }} />
                                    <span style={{
                                        whiteSpace: 'nowrap',
                                        overflow: 'hidden',
                                        textOverflow: 'ellipsis',
                                        lineHeight: '1.4'
                                    }}>
                                        {sess.title || 'Phiên chat'}
                                    </span>
                                </div>
                                {/* delete button */}
                                {!String(sess.id).startsWith('draft') && (
                                    <button
                                        onClick={() => handleDeleteSession(sess.id)}
                                        title="Xóa phiên"
                                        style={{
                                            border: 'none',
                                            background: '#fee2e2',
                                            color: '#c62828',
                                            cursor: 'pointer',
                                            borderRadius: '10px',
                                            padding: '0.5rem',
                                            display: 'flex',
                                            alignItems: 'center',
                                            justifyContent: 'center',
                                            transition: 'all 0.2s ease',
                                            width: '40px'
                                        }}
                                        onMouseEnter={(e) => {
                                            e.currentTarget.style.background = '#fecaca';
                                        }}
                                        onMouseLeave={(e) => {
                                            e.currentTarget.style.background = '#fee2e2';
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
            <div className="card" style={{ flex: 1, display: 'flex', flexDirection: 'column', padding: '0', overflow: 'hidden', position: 'relative' }}>
                {/* Expand button when sidebar is collapsed */}


                {/* Header */}
                <div style={{ padding: '1rem', borderBottom: '1px solid #eee', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                    <div style={{ width: '10px', height: '10px', borderRadius: '50%', background: '#2ecc71' }}></div>
                    <span style={{ fontWeight: '600' }}>Trợ lý ảo EduTwin</span>
                </div>

                {/* Messages */}
                <div style={{ flex: 1, overflowY: 'auto', padding: '1.5rem', display: 'flex', flexDirection: 'column', gap: '1.5rem' }}>
                    {messages.map((msg, idx) => (
                        <div
                            key={idx}
                            style={{
                                display: 'flex',
                                justifyContent: msg.role === 'user' ? 'flex-end' : 'flex-start'
                            }}
                        >
                            <div style={{
                                maxWidth: '70%',
                                padding: '1rem',
                                borderRadius: '12px',
                                background: msg.role === 'user' ? '#d32f2f' : '#f1f2f6',
                                color: msg.role === 'user' ? 'white' : '#333',
                                boxShadow: '0 2px 4px rgba(0,0,0,0.05)',
                                borderTopRightRadius: msg.role === 'user' ? '2px' : '12px',
                                borderTopLeftRadius: msg.role === 'assistant' ? '2px' : '12px'
                            }}>
                                <ReactMarkdown>{msg.content}</ReactMarkdown>
                            </div>
                        </div>
                    ))}

                    {loading && (
                        <div style={{ display: 'flex', justifyContent: 'flex-start' }}>
                            <div style={{ background: '#f1f2f6', padding: '1rem', borderRadius: '12px', borderTopLeftRadius: '2px' }}>
                                <div style={{ display: 'flex', gap: '4px' }}>
                                    <span className="dot-animate" style={{ animationDelay: '0s' }}>•</span>
                                    <span className="dot-animate" style={{ animationDelay: '0.2s' }}>•</span>
                                    <span className="dot-animate" style={{ animationDelay: '0.4s' }}>•</span>
                                </div>
                            </div>
                        </div>
                    )}

                    {/* Pending Score Update Card */}
                    {pendingScore && (
                        <div style={{ margin: '0 auto', maxWidth: '80%', background: '#fff0f3', border: '1px solid #ffcdd2', borderRadius: '8px', padding: '1rem' }}>
                            <h4 style={{ color: '#c62828', marginBottom: '0.5rem', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                                ⚠️ Phát hiện thay đổi điểm số
                            </h4>
                            <p style={{ marginBottom: '0.5rem' }}>
                                Môn <b>{pendingScore.subject}</b> học kỳ <b>{pendingScore.semester}</b> lớp <b>{pendingScore.grade_level}</b>: {pendingScore.old_score || '?'} → <b>{pendingScore.new_score}</b>
                            </p>
                            <div style={{ display: 'flex', gap: '1rem' }}>
                                <button className="btn btn-primary" style={{ padding: '0.5rem 1rem', fontSize: '0.9rem' }} onClick={handleConfirmScore}>
                                    <Check size={16} /> Xác nhận
                                </button>
                                <button className="btn btn-outline" style={{ padding: '0.5rem 1rem', fontSize: '0.9rem' }} onClick={() => setPendingScore(null)}>
                                    <X size={16} /> Bỏ qua
                                </button>
                            </div>
                        </div>
                    )}

                    <div ref={messagesEndRef} />
                </div>

                {/* Input Area */}
                <div style={{ padding: '1rem', borderTop: '1px solid #eee', background: '#fff' }}>
                    <div style={{ display: 'flex', gap: '1rem' }}>
                        <input
                            className="input-field"
                            placeholder="Nhập câu hỏi của bạn..."
                            value={input}
                            onChange={(e) => setInput(e.target.value)}
                            onKeyDown={(e) => e.key === 'Enter' && handleSend()}
                            disabled={loading}
                        />
                        <button
                            className="btn btn-primary"
                            onClick={handleSend}
                            disabled={loading || !input.trim()}
                            style={{ width: '50px', padding: 0 }}
                        >
                            <Send size={20} />
                        </button>
                    </div>
                </div>
            </div>

            <style>{`
        .dot-animate {
          animation: blink 1.4s infinite both;
          font-size: 1.5rem;
          line-height: 1rem;
        }
        @keyframes blink {
          0% { opacity: 0.2; }
          20% { opacity: 1; }
          100% { opacity: 0.2; }
        }
      `}</style>
        </div>
    );
};

export default Chatbot;

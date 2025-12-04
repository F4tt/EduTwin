import React, { createContext, useContext, useEffect, useState, useCallback, useRef } from 'react';
import { io } from 'socket.io-client';
import { useAuth } from './AuthContext';

const WebSocketContext = createContext(null);

export const useWebSocket = () => {
    const context = useContext(WebSocketContext);
    if (!context) {
        throw new Error('useWebSocket must be used within a WebSocketProvider');
    }
    return context;
};

export const WebSocketProvider = ({ children }) => {
    const { user } = useAuth();
    const [socket, setSocket] = useState(null);
    const [connected, setConnected] = useState(false);
    const [chatMessages, setChatMessages] = useState([]);
    const [studyUpdates, setStudyUpdates] = useState([]);
    const [predictions, setPredictions] = useState([]);
    const [isTyping, setIsTyping] = useState(false);
    
    const socketRef = useRef(null);
    const reconnectTimeoutRef = useRef(null);
    const reconnectAttemptsRef = useRef(0);
    const maxReconnectAttempts = 5;
    
    // Connect to WebSocket server
    useEffect(() => {
        if (!user) {
            // Disconnect if user logs out
            if (socketRef.current) {
                socketRef.current.disconnect();
                socketRef.current = null;
                setSocket(null);
                setConnected(false);
            }
            return;
        }
        
        // Connect to WebSocket
        const wsUrl = import.meta.env.VITE_WS_URL || 'http://localhost:8000';
        
        const newSocket = io(wsUrl, {
            path: '/socket.io',
            transports: ['websocket', 'polling'],
            auth: {
                user_id: user.id
            },
            reconnection: true,
            reconnectionDelay: 1000,
            reconnectionDelayMax: 5000,
            reconnectionAttempts: maxReconnectAttempts
        });
        
        socketRef.current = newSocket;
        setSocket(newSocket);
        
        // Connection event handlers
        newSocket.on('connect', () => {
            console.log('WebSocket connected');
            setConnected(true);
            reconnectAttemptsRef.current = 0;
            
            // Authenticate after connection
            newSocket.emit('authenticate', { user_id: user.id });
        });
        
        newSocket.on('disconnect', (reason) => {
            console.log('WebSocket disconnected:', reason);
            setConnected(false);
        });
        
        newSocket.on('connect_error', (error) => {
            console.error('WebSocket connection error:', error);
            setConnected(false);
        });
        
        newSocket.on('authenticated', (data) => {
            console.log('WebSocket authenticated:', data);
        });
        
        newSocket.on('connected', (data) => {
            console.log('WebSocket connection confirmed:', data);
        });
        
        // Chat events
        newSocket.on('chat_message', (data) => {
            console.log('Received chat message:', data);
            setChatMessages(prev => [...prev, data]);
        });
        
        newSocket.on('chat_typing', (data) => {
            console.log('Typing indicator:', data);
            setIsTyping(data.is_typing);
        });
        
        // Study update events
        newSocket.on('study_update', (data) => {
            console.log('Received study update:', data);
            setStudyUpdates(prev => [...prev, data]);
        });
        
        newSocket.on('prediction_update', (data) => {
            console.log('Received prediction update:', data);
            setPredictions(data.predictions || []);
        });
        
        // Error handling
        newSocket.on('error', (error) => {
            console.error('WebSocket error:', error);
        });
        
        // Ping/pong for connection health
        const pingInterval = setInterval(() => {
            if (newSocket.connected) {
                newSocket.emit('ping');
            }
        }, 30000); // Every 30 seconds
        
        newSocket.on('pong', (data) => {
            console.log('Pong received:', data);
        });
        
        // Cleanup
        return () => {
            clearInterval(pingInterval);
            if (reconnectTimeoutRef.current) {
                clearTimeout(reconnectTimeoutRef.current);
            }
            newSocket.disconnect();
        };
    }, [user]);
    
    // Join chat session room
    const joinChatSession = useCallback((chatSessionId) => {
        if (socketRef.current && socketRef.current.connected) {
            console.log('Joining chat session:', chatSessionId);
            socketRef.current.emit('join_chat_session', { chat_session_id: chatSessionId });
        }
    }, []);
    
    // Leave chat session room
    const leaveChatSession = useCallback((chatSessionId) => {
        if (socketRef.current && socketRef.current.connected) {
            console.log('Leaving chat session:', chatSessionId);
            socketRef.current.emit('leave_chat_session', { chat_session_id: chatSessionId });
        }
    }, []);
    
    // Send custom event
    const emit = useCallback((event, data) => {
        if (socketRef.current && socketRef.current.connected) {
            socketRef.current.emit(event, data);
        } else {
            console.warn('Socket not connected. Cannot emit:', event);
        }
    }, []);
    
    // Subscribe to custom event
    const on = useCallback((event, callback) => {
        if (socketRef.current) {
            socketRef.current.on(event, callback);
            // Return unsubscribe function
            return () => {
                if (socketRef.current) {
                    socketRef.current.off(event, callback);
                }
            };
        }
        return () => {};
    }, []);
    
    // Clear chat messages
    const clearChatMessages = useCallback(() => {
        setChatMessages([]);
    }, []);
    
    const value = {
        socket,
        connected,
        chatMessages,
        studyUpdates,
        predictions,
        isTyping,
        joinChatSession,
        leaveChatSession,
        emit,
        on,
        clearChatMessages
    };
    
    return (
        <WebSocketContext.Provider value={value}>
            {children}
        </WebSocketContext.Provider>
    );
};

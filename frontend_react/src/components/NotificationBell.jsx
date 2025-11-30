import React, { useState, useRef, useEffect } from 'react';
import { Bell, X, Check } from 'lucide-react';
import { useWebSocket } from '../context/WebSocketContext';
import './NotificationBell.css';

const NotificationBell = () => {
    const { notifications, unreadCount, markNotificationRead, clearNotifications } = useWebSocket();
    const [isOpen, setIsOpen] = useState(false);
    const dropdownRef = useRef(null);

    // Close dropdown when clicking outside
    useEffect(() => {
        const handleClickOutside = (event) => {
            if (dropdownRef.current && !dropdownRef.current.contains(event.target)) {
                setIsOpen(false);
            }
        };

        if (isOpen) {
            document.addEventListener('mousedown', handleClickOutside);
        }

        return () => {
            document.removeEventListener('mousedown', handleClickOutside);
        };
    }, [isOpen]);

    const handleNotificationClick = (notification) => {
        markNotificationRead(notification.id);
        // Handle different notification types
        if (notification.type === 'confirmation') {
            // Navigate to appropriate page or show confirmation dialog
            console.log('Confirmation notification:', notification);
        }
    };

    const getNotificationIcon = (type) => {
        switch (type) {
            case 'confirmation':
                return '❓';
            case 'success':
                return '✅';
            case 'warning':
                return '⚠️';
            case 'error':
                return '❌';
            default:
                return '📢';
        }
    };

    const formatTimestamp = (timestamp) => {
        const date = new Date(timestamp);
        const now = new Date();
        const diff = Math.floor((now - date) / 1000); // seconds

        if (diff < 60) return 'Vừa xong';
        if (diff < 3600) return `${Math.floor(diff / 60)} phút trước`;
        if (diff < 86400) return `${Math.floor(diff / 3600)} giờ trước`;
        return `${Math.floor(diff / 86400)} ngày trước`;
    };

    return (
        <div className="notification-bell" ref={dropdownRef}>
            <button
                className="notification-btn"
                onClick={() => setIsOpen(!isOpen)}
                aria-label="Thông báo"
            >
                <Bell size={20} />
                {unreadCount > 0 && (
                    <span className="notification-badge">
                        {unreadCount > 9 ? '9+' : unreadCount}
                    </span>
                )}
            </button>

            {isOpen && (
                <div className="notification-dropdown">
                    <div className="notification-header">
                        <h3>Thông báo</h3>
                        {notifications.length > 0 && (
                            <button
                                className="clear-btn"
                                onClick={clearNotifications}
                                title="Xóa tất cả"
                            >
                                <X size={16} />
                            </button>
                        )}
                    </div>

                    <div className="notification-list">
                        {notifications.length === 0 ? (
                            <div className="notification-empty">
                                <Bell size={32} style={{ opacity: 0.3 }} />
                                <p>Không có thông báo mới</p>
                            </div>
                        ) : (
                            notifications.slice().reverse().map((notification) => (
                                <div
                                    key={notification.id}
                                    className={`notification-item ${notification.read ? 'read' : 'unread'}`}
                                    onClick={() => handleNotificationClick(notification)}
                                >
                                    <div className="notification-icon">
                                        {getNotificationIcon(notification.type)}
                                    </div>
                                    <div className="notification-content">
                                        <div className="notification-message">
                                            {notification.message || notification.data?.message || 'Thông báo mới'}
                                        </div>
                                        <div className="notification-time">
                                            {formatTimestamp(notification.timestamp)}
                                        </div>
                                    </div>
                                    {!notification.read && (
                                        <div className="notification-unread-dot"></div>
                                    )}
                                </div>
                            ))
                        )}
                    </div>

                    {notifications.length > 0 && (
                        <div className="notification-footer">
                            <button
                                className="mark-all-read-btn"
                                onClick={() => {
                                    notifications.forEach(n => {
                                        if (!n.read) markNotificationRead(n.id);
                                    });
                                }}
                            >
                                <Check size={14} />
                                <span>Đánh dấu tất cả đã đọc</span>
                            </button>
                        </div>
                    )}
                </div>
            )}
        </div>
    );
};

export default NotificationBell;

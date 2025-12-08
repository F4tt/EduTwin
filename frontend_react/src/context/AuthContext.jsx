import React, { createContext, useState, useContext, useEffect } from 'react';
import axiosClient from '../api/axiosClient';

const AuthContext = createContext(null);

export const AuthProvider = ({ children }) => {
    const [user, setUser] = useState(null);
    const [loading, setLoading] = useState(true);

    useEffect(() => {
        // On mount, try to restore user from localStorage first for instant UI,
        // then validate with backend
        const init = async () => {
            // Step 1: Immediately restore from localStorage for instant UI
            const storedUser = localStorage.getItem('user');
            if (storedUser) {
                try {
                    const parsedUser = JSON.parse(storedUser);
                    if (parsedUser && parsedUser.user_id) {
                        setUser(parsedUser);
                    }
                } catch (e) {
                    console.error('Failed to parse stored user:', e);
                    localStorage.removeItem('user');
                }
            }

            // Step 2: Validate session with backend
            try {
                const res = await axiosClient.get('/auth/me');
                // backend returns { user: {...}, message: "..." }
                const userFromRes = res.data.user || null;
                if (userFromRes && Object.keys(userFromRes).length > 0 && userFromRes.user_id) {
                    // Session is valid, update user state
                    setUser(userFromRes);
                    localStorage.setItem('user', JSON.stringify(userFromRes));
                } else if (!storedUser) {
                    // No valid session and no stored user
                    setUser(null);
                }
                // If we have storedUser but got empty response, keep storedUser (graceful degradation)
            } catch (e) {
                // Session validation failed
                if (e.response?.status === 401) {
                    // Session expired or invalid - clear everything
                    console.log('[Auth] Session expired or invalid, clearing user state');
                    setUser(null);
                    localStorage.removeItem('user');
                } else {
                    // Network error or backend unavailable - keep localStorage user
                    console.log('[Auth] Backend unavailable, using cached user');
                    // storedUser already loaded above, keep it
                }
            } finally {
                setLoading(false);
            }
        };
        init();
    }, []);

    const login = async (username, password) => {
        try {
            const res = await axiosClient.post('/auth/login', { username, password });
            if (res.data && res.data.user) {
                const userData = res.data.user;
                // ensure profile fields are preserved
                const merged = { ...userData, ...(res.data.profile || {}) };
                setUser(merged);
                localStorage.setItem('user', JSON.stringify(merged));
                return { success: true, user: userData };
            }
            return { success: false, message: 'Đăng nhập thất bại. Vui lòng thử lại.' };
        } catch (error) {
            // Convert backend error to user-friendly Vietnamese message
            let message = 'Đã xảy ra lỗi khi đăng nhập. Vui lòng thử lại.';

            if (error.response) {
                const status = error.response.status;
                const detail = error.response.data?.detail || '';

                if (status === 401 || detail.includes('Invalid') || detail.includes('incorrect')) {
                    message = 'Tài khoản hoặc mật khẩu không đúng. Vui lòng kiểm tra lại.';
                } else if (status === 404) {
                    message = 'Tài khoản không tồn tại.';
                } else if (status >= 500) {
                    message = 'Máy chủ đang bận. Vui lòng thử lại sau.';
                } else if (detail.includes('network') || error.message.includes('network')) {
                    message = 'Lỗi kết nối mạng. Vui lòng kiểm tra kết nối internet.';
                }
            } else if (error.message.includes('timeout')) {
                message = 'Kết nối quá chậm. Vui lòng thử lại.';
            } else if (error.message.includes('Network Error')) {
                message = 'Không thể kết nối đến máy chủ. Vui lòng kiểm tra kết nối internet.';
            }

            return { success: false, message };
        }
    };

    const register = async (data) => {
        try {
            await axiosClient.post('/auth/register', data);
            return { success: true };
        } catch (error) {
            // Convert backend error to user-friendly Vietnamese message
            let message = 'Đã xảy ra lỗi khi đăng ký. Vui lòng thử lại.';

            if (error.response) {
                const status = error.response.status;
                const detail = error.response.data?.detail || '';

                if (status === 409 || detail.includes('already exists') || detail.includes('đã tồn tại')) {
                    message = 'Tên đăng nhập đã tồn tại. Vui lòng chọn tên khác.';
                } else if (status === 400) {
                    if (detail.includes('password')) {
                        message = 'Mật khẩu không hợp lệ. Vui lòng nhập mật khẩu mạnh hơn.';
                    } else if (detail.includes('username')) {
                        message = 'Tên đăng nhập không hợp lệ. Chỉ dùng chữ cái, số và dấu gạch dưới.';
                    } else {
                        message = 'Thông tin đăng ký không hợp lệ. Vui lòng kiểm tra lại.';
                    }
                } else if (status >= 500) {
                    message = 'Máy chủ đang bận. Vui lòng thử lại sau.';
                }
            } else if (error.message.includes('timeout')) {
                message = 'Kết nối quá chậm. Vui lòng thử lại.';
            } else if (error.message.includes('Network Error')) {
                message = 'Không thể kết nối đến máy chủ. Vui lòng kiểm tra kết nối internet.';
            }

            return { success: false, message };
        }
    };

    const logout = async () => {
        // Clear AI insights cache for this user before logout
        const username = user?.username;
        if (username && typeof window !== 'undefined' && window.localStorage) {
            try {
                // Clear DataViz AI comments
                const aiCacheKey = `dataviz_ai_comments_${username}`;
                window.localStorage.removeItem(aiCacheKey);

                // NOTE: Learning Goals AI strategy is NOT cleared on logout
                // to preserve strategy even when user logs out
            } catch (e) {
                console.error('Failed to clear AI cache on logout:', e);
            }
        }

        // Cleanup empty chat sessions before logout
        try {
            await axiosClient.delete('/chatbot/cleanup-empty-sessions');
        } catch (e) {
            console.error('Failed to cleanup empty sessions:', e);
        }

        setUser(null);
        localStorage.removeItem('user');
        // inform backend
        try {
            axiosClient.post('/auth/logout');
        } catch (e) {
            // ignore
        }
    };

    const updateProfile = async (data) => {
        try {
            // Optimistic update
            const updatedUser = { ...user, ...data };
            setUser(updatedUser);
            localStorage.setItem('user', JSON.stringify(updatedUser));
            // Call API to persist profile change
            const res = await axiosClient.post('/auth/profile', data);
            // Fetch latest user data from backend to ensure sync
            try {
                const meRes = await axiosClient.get('/auth/me');
                const freshUser = meRes.data.user || updatedUser;
                setUser(freshUser);
                localStorage.setItem('user', JSON.stringify(freshUser));
            } catch (e) {
                // If refresh fails, keep the optimistic update
                console.error('Could not refresh user data after profile update:', e);
            }
        } catch (e) {
            console.error(e);
        }
    }

    return (
        <AuthContext.Provider value={{ user, login, register, logout, updateProfile, loading }}>
            {children}
        </AuthContext.Provider>
    );
};

export const useAuth = () => useContext(AuthContext);

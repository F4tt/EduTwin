import React, { createContext, useState, useContext, useEffect } from 'react';
import axiosClient from '../api/axiosClient';

const AuthContext = createContext(null);

export const AuthProvider = ({ children }) => {
    const [user, setUser] = useState(null);
    const [loading, setLoading] = useState(true);

    useEffect(() => {
        // On mount, try to fetch current authenticated user/profile from backend
        const init = async () => {
            try {
                const res = await axiosClient.get('/auth/me');
                // backend returns { user: {...}, message: "..." }
                const userFromRes = res.data.user || null;
                if (userFromRes && Object.keys(userFromRes).length > 0) {
                    setUser(userFromRes);
                    localStorage.setItem('user', JSON.stringify(userFromRes));
                } else {
                    // fallback to stored user
                    const storedUser = localStorage.getItem('user');
                    if (storedUser) setUser(JSON.parse(storedUser));
                }
            } catch (e) {
                // no active session or endpoint unavailable
                const storedUser = localStorage.getItem('user');
                if (storedUser) setUser(JSON.parse(storedUser));
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
                // ensure profile fields and is_first_login are preserved
                const merged = { ...userData, ...(res.data.profile || {}) };
                setUser(merged);
                localStorage.setItem('user', JSON.stringify(merged));
                return { success: true, user: userData };
            }
            return { success: false, message: 'Login failed' };
        } catch (error) {
            return { success: false, message: error.response?.data?.detail || 'Login error' };
        }
    };

    const register = async (data) => {
        try {
            await axiosClient.post('/auth/register', data);
            return { success: true };
        } catch (error) {
            return { success: false, message: error.response?.data?.detail || 'Register error' };
        }
    };

    const logout = () => {
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

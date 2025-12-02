import React, { useEffect } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { motion } from 'framer-motion';
import { useAuth } from '../context/AuthContext';

const LoginChoice = () => {
    const { user, loading } = useAuth();
    const navigate = useNavigate();

    // Redirect if already logged in
    useEffect(() => {
        if (!loading && user) {
            if (user.user_type === 'institution') {
                navigate('/institution/dashboard');
            } else {
                navigate('/chat');
            }
        }
    }, [user, loading, navigate]);

    return (
        <div style={{ 
            display: 'flex', 
            flexDirection: 'column',
            alignItems: 'center', 
            justifyContent: 'center', 
            minHeight: '100vh', 
            background: 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)',
            padding: '2rem'
        }}>
            <motion.div
                initial={{ opacity: 0, y: -20 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ duration: 0.8 }}
                style={{ textAlign: 'center', marginBottom: '3rem', color: 'white' }}
            >
                <h1 style={{ fontSize: '4rem', fontWeight: '800', marginBottom: '1rem', letterSpacing: '-1px' }}>
                    EduTwin
                </h1>
                <p style={{ fontSize: '1.5rem', opacity: 0.9 }}>
                    Chọn loại tài khoản để đăng nhập
                </p>
            </motion.div>

            <div style={{ 
                display: 'grid', 
                gridTemplateColumns: 'repeat(auto-fit, minmax(300px, 1fr))',
                gap: '2rem',
                maxWidth: '900px',
                width: '100%'
            }}>
                {/* Student Card */}
                <motion.div
                    initial={{ opacity: 0, x: -50 }}
                    animate={{ opacity: 1, x: 0 }}
                    transition={{ duration: 0.6, delay: 0.2 }}
                    whileHover={{ scale: 1.05, boxShadow: '0 20px 40px rgba(0,0,0,0.3)' }}
                    style={{
                        background: 'white',
                        borderRadius: '20px',
                        padding: '3rem 2rem',
                        textAlign: 'center',
                        boxShadow: '0 10px 30px rgba(0,0,0,0.2)',
                        cursor: 'pointer',
                        transition: 'all 0.3s ease'
                    }}
                >
                    <div style={{ fontSize: '4rem', marginBottom: '1.5rem' }}>🎓</div>
                    <h2 style={{ fontSize: '1.8rem', fontWeight: '700', color: 'var(--primary-color)', marginBottom: '1rem' }}>
                        Học sinh
                    </h2>
                    <p style={{ fontSize: '1.05rem', color: 'var(--text-secondary)', marginBottom: '2rem', lineHeight: '1.6' }}>
                        Truy cập trợ lý học tập thông minh, theo dõi điểm số và nhận hỗ trợ cá nhân hóa
                    </p>
                    <Link 
                        to="/login/student"
                        className="btn btn-primary"
                        style={{ 
                            width: '100%', 
                            padding: '1rem', 
                            fontSize: '1.1rem',
                            textDecoration: 'none',
                            display: 'inline-block'
                        }}
                    >
                        Đăng nhập với tư cách Học sinh
                    </Link>
                </motion.div>

                {/* Institution Card */}
                <motion.div
                    initial={{ opacity: 0, x: 50 }}
                    animate={{ opacity: 1, x: 0 }}
                    transition={{ duration: 0.6, delay: 0.4 }}
                    whileHover={{ scale: 1.05, boxShadow: '0 20px 40px rgba(0,0,0,0.3)' }}
                    style={{
                        background: 'white',
                        borderRadius: '20px',
                        padding: '3rem 2rem',
                        textAlign: 'center',
                        boxShadow: '0 10px 30px rgba(0,0,0,0.2)',
                        cursor: 'pointer',
                        transition: 'all 0.3s ease'
                    }}
                >
                    <div style={{ fontSize: '4rem', marginBottom: '1.5rem' }}>🏫</div>
                    <h2 style={{ fontSize: '1.8rem', fontWeight: '700', color: '#10b981', marginBottom: '1rem' }}>
                        Cơ sở Giáo dục
                    </h2>
                    <p style={{ fontSize: '1.05rem', color: 'var(--text-secondary)', marginBottom: '2rem', lineHeight: '1.6' }}>
                        Quản lý học sinh, phân tích dữ liệu học tập và theo dõi tiến độ của cơ sở giáo dục
                    </p>
                    <Link 
                        to="/login/institution"
                        className="btn"
                        style={{ 
                            width: '100%', 
                            padding: '1rem', 
                            fontSize: '1.1rem',
                            background: '#10b981',
                            color: 'white',
                            border: 'none',
                            textDecoration: 'none',
                            display: 'inline-block'
                        }}
                    >
                        Đăng nhập với tư cách Cơ sở GD
                    </Link>
                </motion.div>
            </div>

            <motion.div
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                transition={{ duration: 0.8, delay: 0.6 }}
                style={{ marginTop: '3rem', color: 'white', textAlign: 'center' }}
            >
                <p style={{ fontSize: '0.95rem', opacity: 0.8 }}>
                    © 2025 EduTwin - Nền tảng học tập thông minh
                </p>
            </motion.div>
        </div>
    );
};

export default LoginChoice;

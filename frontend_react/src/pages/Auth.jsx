import React, { useState } from 'react';
import { useAuth } from '../context/AuthContext';
import { useNavigate } from 'react-router-dom';
import { motion } from 'framer-motion';
import { isValidUsername, isValidName } from '../utils/validation';
import { useIsMobile } from '../hooks/useIsMobile';

const Auth = () => {
    const [isLogin, setIsLogin] = useState(true);
    const [formData, setFormData] = useState({
        username: '', password: '', confirmPassword: '', firstName: '', lastName: ''
    });
    const [error, setError] = useState('');
    const { login, register } = useAuth();
    const navigate = useNavigate();
    const isMobile = useIsMobile();

    const handleChange = (e) => {
        setFormData({ ...formData, [e.target.name]: e.target.value });
    };

    const handleSubmit = async (e) => {
        e.preventDefault();
        setError('');

        if (isLogin) {
            const res = await login(formData.username, formData.password);
            if (res.success) {
                navigate('/chat');
            } else {
                setError(res.message);
            }
        } else {
            // Validation
            if (!isValidName(formData.firstName) || !isValidName(formData.lastName)) {
                setError('Họ/Tên chỉ được chứa chữ cái và khoảng trắng.');
                return;
            }
            if (!isValidUsername(formData.username)) {
                setError('Tên đăng nhập chỉ được dùng chữ cái/số tiếng Anh (kèm "_" hoặc "-")');
                return;
            }
            if (formData.password !== formData.confirmPassword) {
                setError('Mật khẩu không khớp');
                return;
            }

            const res = await register({
                username: formData.username,
                password: formData.password,
                first_name: formData.firstName,
                last_name: formData.lastName
            });
            if (res.success) {
                setIsLogin(true);
                setError('');
                alert('Đăng ký thành công! Vui lòng đăng nhập.');
            } else {
                setError(res.message);
            }
        }
    };

    return (
        <div style={{ display: 'flex', height: '100vh', width: '100vw', overflow: 'hidden', background: 'var(--bg-body)' }}>
            {/* Left Side - Image/Brand (Hidden on mobile) */}
            {!isMobile && (
                <div style={{
                    flex: 1,
                    background: 'linear-gradient(135deg, var(--primary-color) 0%, var(--primary-hover) 100%)',
                    display: 'flex',
                    flexDirection: 'column',
                    justifyContent: 'center',
                    alignItems: 'center',
                    color: 'white',
                    padding: '2rem',
                    position: 'relative'
                }}>
                    <div style={{ position: 'absolute', top: 0, left: 0, width: '100%', height: '100%', opacity: 0.1, backgroundImage: 'url("https://www.transparenttextures.com/patterns/cubes.png")' }}></div>
                    <motion.div
                        initial={{ opacity: 0, y: 20 }}
                        animate={{ opacity: 1, y: 0 }}
                        transition={{ duration: 0.8 }}
                        style={{ zIndex: 1, textAlign: 'center' }}
                    >
                        <h1 style={{ fontSize: '4rem', fontWeight: '800', marginBottom: '1rem', letterSpacing: '-1px' }}>EduTwin</h1>
                        <p style={{ fontSize: '1.5rem', opacity: 0.9, fontWeight: '300' }}>Trợ lý học tập thông minh của bạn</p>
                    </motion.div>
                </div>
            )}

            {/* Right Side - Form */}
            <div style={{ flex: 1, display: 'flex', alignItems: 'center', justifyContent: 'center', background: 'var(--bg-surface)', padding: isMobile ? '1rem' : 0 }}>
                <div style={{ width: '100%', maxWidth: isMobile ? '100%' : '450px', padding: isMobile ? '1.5rem' : '3rem' }}>
                    {/* Mobile: Show brand header */}
                    {isMobile && (
                        <div style={{ textAlign: 'center', marginBottom: '2rem' }}>
                            <h1 style={{ fontSize: '2rem', fontWeight: '800', color: 'var(--primary-color)', marginBottom: '0.5rem' }}>EduTwin</h1>
                            <p style={{ fontSize: '0.95rem', color: 'var(--text-secondary)' }}>Trợ lý học tập thông minh</p>
                        </div>
                    )}
                    <div style={{ marginBottom: isMobile ? '1.5rem' : '2.5rem' }}>
                        <h2 style={{ fontSize: isMobile ? '1.5rem' : '2rem', fontWeight: '700', marginBottom: '0.5rem', color: 'var(--text-primary)' }}>
                            {isLogin ? 'Chào mừng trở lại!' : 'Tạo tài khoản mới'}
                        </h2>
                        <p style={{ color: 'var(--text-secondary)', fontSize: isMobile ? '0.95rem' : '1.05rem' }}>
                            {isLogin ? 'Vui lòng đăng nhập để tiếp tục.' : 'Bắt đầu hành trình học tập của bạn.'}
                        </p>
                    </div>

                    {error && (
                        <div style={{
                            background: '#fef2f2',
                            color: 'var(--danger-color)',
                            padding: '1rem',
                            borderRadius: 'var(--radius-md)',
                            marginBottom: '1.5rem',
                            fontSize: '0.95rem',
                            border: '1px solid #fecaca',
                            display: 'flex',
                            alignItems: 'center',
                            gap: '0.5rem'
                        }}>
                            ⚠️ {error}
                        </div>
                    )}

                    <form onSubmit={handleSubmit}>
                        {!isLogin && (
                            <div style={{ display: 'flex', gap: '1rem' }}>
                                <div style={{ marginBottom: '1.25rem', flex: 1 }}>
                                    <label className="label">Họ</label>
                                    <input className="input-field" name="lastName" placeholder="Nguyễn" onChange={handleChange} required />
                                </div>
                                <div style={{ marginBottom: '1.25rem', flex: 1 }}>
                                    <label className="label">Tên</label>
                                    <input className="input-field" name="firstName" placeholder="Văn A" onChange={handleChange} required />
                                </div>
                            </div>
                        )}

                        <div style={{ marginBottom: '1.25rem' }}>
                            <label className="label">Tên đăng nhập</label>
                            <input className="input-field" name="username" placeholder="username" onChange={handleChange} required />
                        </div>

                        <div style={{ marginBottom: '1.25rem' }}>
                            <label className="label">Mật khẩu</label>
                            <input className="input-field" type="password" name="password" placeholder="••••••••" onChange={handleChange} required />
                        </div>

                        {!isLogin && (
                            <div style={{ marginBottom: '2rem' }}>
                                <label className="label">Nhập lại mật khẩu</label>
                                <input className="input-field" type="password" name="confirmPassword" placeholder="••••••••" onChange={handleChange} required />
                            </div>
                        )}

                        <button type="submit" className="btn btn-primary" style={{ width: '100%', padding: '0.875rem', fontSize: '1rem' }}>
                            {isLogin ? 'Đăng nhập' : 'Đăng ký'}
                        </button>
                    </form>

                    <div style={{ marginTop: '2rem', textAlign: 'center', fontSize: '0.95rem', color: 'var(--text-secondary)' }}>
                        {isLogin ? 'Chưa có tài khoản? ' : 'Đã có tài khoản? '}
                        <button
                            onClick={() => {
                                setIsLogin(!isLogin);
                                setError('');
                                setFormData({
                                    username: '', password: '', confirmPassword: '', firstName: '', lastName: ''
                                });
                            }}
                            style={{
                                background: 'none',
                                border: 'none',
                                color: 'var(--primary-color)',
                                fontWeight: '600',
                                cursor: 'pointer',
                                padding: 0,
                                marginLeft: '0.25rem'
                            }}
                        >
                            {isLogin ? 'Đăng ký ngay' : 'Đăng nhập'}
                        </button>
                    </div>
                </div>
            </div>
        </div>
    );
};

export default Auth;

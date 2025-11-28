import React, { useState } from 'react';
import { useAuth } from '../context/AuthContext';
import { useNavigate } from 'react-router-dom';
import { motion } from 'framer-motion';
import { isValidUsername, isValidName } from '../utils/validation';

const Auth = () => {
    const [isLogin, setIsLogin] = useState(true);
    const [formData, setFormData] = useState({
        username: '', password: '', confirmPassword: '', firstName: '', lastName: ''
    });
    const [error, setError] = useState('');
    const { login, register } = useAuth();
    const navigate = useNavigate();

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
        <div style={{ display: 'flex', height: '100vh', width: '100vw', overflow: 'hidden' }}>
            {/* Left Side - Image/Brand */}
            <div style={{
                flex: 1,
                background: 'linear-gradient(135deg, #d32f2f 0%, #b71c1c 100%)',
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
                    <h1 style={{ fontSize: '4rem', fontWeight: '800', marginBottom: '1rem' }}>EduTwin</h1>
                    <p style={{ fontSize: '1.5rem', opacity: 0.9 }}>Trợ lý học tập thông minh của bạn</p>
                </motion.div>
            </div>

            {/* Right Side - Form */}
            <div style={{ flex: 1, display: 'flex', alignItems: 'center', justifyContent: 'center', background: '#fff' }}>
                <div style={{ width: '100%', maxWidth: '400px', padding: '2rem' }}>
                    <h2 style={{ fontSize: '2rem', fontWeight: '700', marginBottom: '0.5rem', color: '#333' }}>
                        {isLogin ? 'Chào mừng trở lại!' : 'Tạo tài khoản mới'}
                    </h2>
                    <p style={{ color: '#666', marginBottom: '2rem' }}>
                        {isLogin ? 'Vui lòng đăng nhập để tiếp tục.' : 'Bắt đầu hành trình học tập của bạn.'}
                    </p>

                    {error && (
                        <div style={{ background: '#ffebee', color: '#c62828', padding: '0.75rem', borderRadius: '8px', marginBottom: '1rem', fontSize: '0.9rem' }}>
                            {error}
                        </div>
                    )}

                    <form onSubmit={handleSubmit}>
                        {!isLogin && (
                            <div style={{ display: 'flex', gap: '1rem' }}>
                                <div style={{ marginBottom: '1rem', flex: 1 }}>
                                    <label className="label">Họ</label>
                                    <input className="input-field" name="lastName" placeholder="Nguyễn" onChange={handleChange} required />
                                </div>
                                <div style={{ marginBottom: '1rem', flex: 1 }}>
                                    <label className="label">Tên</label>
                                    <input className="input-field" name="firstName" placeholder="Văn A" onChange={handleChange} required />
                                </div>
                            </div>
                        )}

                        <div style={{ marginBottom: '1rem' }}>
                            <label className="label">Tên đăng nhập</label>
                            <input className="input-field" name="username" placeholder="username" onChange={handleChange} required />
                        </div>

                        <div style={{ marginBottom: '1rem' }}>
                            <label className="label">Mật khẩu</label>
                            <input className="input-field" type="password" name="password" placeholder="••••••••" onChange={handleChange} required />
                        </div>

                        {!isLogin && (
                            <div style={{ marginBottom: '1.5rem' }}>
                                <label className="label">Nhập lại mật khẩu</label>
                                <input className="input-field" type="password" name="confirmPassword" placeholder="••••••••" onChange={handleChange} required />
                            </div>
                        )}

                        <button type="submit" className="btn btn-primary" style={{ width: '100%', marginTop: '1rem' }}>
                            {isLogin ? 'Đăng nhập' : 'Đăng ký'}
                        </button>
                    </form>

                    <div style={{ marginTop: '1.5rem', textAlign: 'center', fontSize: '0.9rem', color: '#666' }}>
                        {isLogin ? 'Chưa có tài khoản? ' : 'Đã có tài khoản? '}
                        <button
                            onClick={() => {
                                setIsLogin(!isLogin);
                                setError('');
                                setFormData({
                                    username: '', password: '', confirmPassword: '', firstName: '', lastName: ''
                                });
                            }}
                            style={{ background: 'none', border: 'none', color: '#d32f2f', fontWeight: '600', textDecoration: 'underline' }}
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

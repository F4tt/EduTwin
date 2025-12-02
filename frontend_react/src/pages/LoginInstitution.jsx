import React, { useState, useEffect } from 'react';
import { useAuth } from '../context/AuthContext';
import { useNavigate, Link } from 'react-router-dom';
import { motion } from 'framer-motion';
import { isValidUsername } from '../utils/validation';

const LoginInstitution = () => {
    const [isLogin, setIsLogin] = useState(true);
    const [formData, setFormData] = useState({
        institutionName: '',
        institutionType: '',
        username: '',
        password: '',
        confirmPassword: ''
    });
    const [error, setError] = useState('');
    const { loginInstitution, registerInstitution, user, loading } = useAuth();
    const navigate = useNavigate();
    
    // Redirect if already logged in (wait for auth loading to finish)
    useEffect(() => {
        if (!loading && user) {
            if (user.user_type === 'institution') {
                navigate('/institution/dashboard');
            } else {
                navigate('/chat');
            }
        }
    }, [user, loading, navigate]);

    const handleChange = (e) => {
        setFormData({ ...formData, [e.target.name]: e.target.value });
    };

    const handleSubmit = async (e) => {
        e.preventDefault();
        setError('');

        if (isLogin) {
            const res = await loginInstitution(formData.username, formData.password);
            if (res.success) {
                navigate('/institution/dashboard');
            } else {
                setError(res.message);
            }
        } else {
            // Validation
            if (!isValidUsername(formData.username)) {
                setError('Tên đăng nhập chỉ được dùng chữ cái/số tiếng Anh (kèm "_" hoặc "-")');
                return;
            }
            if (formData.password !== formData.confirmPassword) {
                setError('Mật khẩu không khớp');
                return;
            }
            if (formData.institutionName.trim().length < 3) {
                setError('Tên cơ sở giáo dục phải có ít nhất 3 ký tự');
                return;
            }

            const res = await registerInstitution({
                institution_name: formData.institutionName,
                institution_type: formData.institutionType || null,
                username: formData.username,
                password: formData.password
            });
            if (res.success) {
                setIsLogin(true);
                setError('');
                alert('Đăng ký thành công! Vui lòng đăng nhập.');
                setFormData({
                    institutionName: '',
                    institutionType: '',
                    username: '',
                    password: '',
                    confirmPassword: '',
                    email: '',
                    phone: '',
                    address: '',
                    contactPerson: ''
                });
            } else {
                setError(res.message);
            }
        }
    };

    return (
        <div style={{ display: 'flex', height: '100vh', width: '100vw', overflow: 'hidden', background: 'var(--bg-body)' }}>
            {/* Left Side - Image/Brand */}
            <div style={{
                flex: 1,
                background: 'linear-gradient(135deg, #10b981 0%, #059669 100%)',
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
                    <p style={{ fontSize: '1.5rem', opacity: 0.9, fontWeight: '300' }}>Nền tảng quản lý học tập thông minh</p>
                    <p style={{ fontSize: '1.2rem', opacity: 0.8, marginTop: '1rem' }}>Dành cho Cơ sở Giáo dục</p>
                </motion.div>
            </div>

            {/* Right Side - Form */}
            <div style={{ flex: 1, display: 'flex', alignItems: 'center', justifyContent: 'center', background: 'var(--bg-surface)', overflowY: 'auto', padding: '2rem 0' }}>
                <div style={{ width: '100%', maxWidth: '500px', padding: '2rem 3rem' }}>
                    <div style={{ marginBottom: '2.5rem' }}>
                        <h2 style={{ fontSize: '2rem', fontWeight: '700', marginBottom: '0.5rem', color: 'var(--text-primary)' }}>
                            {isLogin ? 'Đăng nhập Cơ sở Giáo dục' : 'Đăng ký Cơ sở Giáo dục'}
                        </h2>
                        <p style={{ color: 'var(--text-secondary)', fontSize: '1.05rem' }}>
                            {isLogin ? 'Vui lòng đăng nhập để quản lý.' : 'Đăng ký tài khoản cho cơ sở giáo dục của bạn.'}
                        </p>
                        <div style={{ marginTop: '1rem' }}>
                            <Link to="/login/student" style={{ color: '#10b981', fontSize: '0.9rem', textDecoration: 'none' }}>
                                ← Bạn là học sinh? Đăng nhập tại đây
                            </Link>
                        </div>
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
                            <>
                                <div style={{ marginBottom: '1.25rem' }}>
                                    <label className="label">Tên cơ sở giáo dục *</label>
                                    <input 
                                        className="input-field" 
                                        name="institutionName" 
                                        placeholder="VD: Trường THPT Lê Quý Đôn" 
                                        value={formData.institutionName}
                                        onChange={handleChange} 
                                        required 
                                    />
                                </div>

                                <div style={{ marginBottom: '1.25rem' }}>
                                    <label className="label">Loại hình</label>
                                    <select 
                                        className="input-field" 
                                        name="institutionType"
                                        value={formData.institutionType}
                                        onChange={handleChange}
                                    >
                                        <option value="">-- Chọn loại hình --</option>
                                        <option value="high_school">Trường THPT</option>
                                        <option value="university">Đại học</option>
                                        <option value="training_center">Trung tâm đào tạo</option>
                                        <option value="other">Khác</option>
                                    </select>
                                </div>
                            </>
                        )}

                        <div style={{ marginBottom: '1.25rem' }}>
                            <label className="label">Tên đăng nhập *</label>
                            <input 
                                className="input-field" 
                                name="username" 
                                placeholder="username"
                                value={formData.username}
                                onChange={handleChange} 
                                required 
                            />
                        </div>

                        <div style={{ marginBottom: '1.25rem' }}>
                            <label className="label">Mật khẩu *</label>
                            <input 
                                className="input-field" 
                                type="password" 
                                name="password" 
                                placeholder="••••••••"
                                value={formData.password}
                                onChange={handleChange} 
                                required 
                            />
                        </div>

                        {!isLogin && (
                            <div style={{ marginBottom: '2rem' }}>
                                <label className="label">Nhập lại mật khẩu *</label>
                                <input 
                                    className="input-field" 
                                    type="password" 
                                    name="confirmPassword" 
                                    placeholder="••••••••"
                                    value={formData.confirmPassword}
                                    onChange={handleChange} 
                                    required 
                                />
                            </div>
                        )}

                        <button type="submit" className="btn btn-primary" style={{ width: '100%', padding: '0.875rem', fontSize: '1rem', background: '#10b981' }}>
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
                                    institutionName: '',
                                    institutionType: '',
                                    username: '',
                                    password: '',
                                    confirmPassword: ''
                                });
                            }}
                            style={{
                                background: 'none',
                                border: 'none',
                                color: '#10b981',
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

export default LoginInstitution;

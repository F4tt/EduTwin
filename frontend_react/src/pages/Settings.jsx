import React, { useState, useEffect } from 'react';
import { useAuth } from '../context/AuthContext';
import axiosClient from '../api/axiosClient';
import { validateProfileFields } from '../utils/validation';
import { Save, Sparkles } from 'lucide-react';

const Settings = () => {
    const { user, updateProfile } = useAuth();
    const [formData, setFormData] = useState({
        email: user?.email || '',
        phone: user?.phone || '',
        address: user?.address || '',
        age: user?.age || ''
    });
    const [message, setMessage] = useState('');
    const [error, setError] = useState('');

    // Change password state
    const [pwdForm, setPwdForm] = useState({ current_password: '', new_password: '', confirm_password: '' });
    const [pwdMsg, setPwdMsg] = useState('');

    // Learned personalization state
    const [learnedPrefs, setLearnedPrefs] = useState([]);

    useEffect(() => {
        fetchLearnedPreferences();
    }, []);

    const fetchLearnedPreferences = async () => {
        try {
            const res = await axiosClient.get('/user/learned-personalization');
            const prefs = res.data.learned_preferences || [];
            console.log('[Settings] Learned preferences:', prefs);
            setLearnedPrefs(Array.isArray(prefs) ? prefs : []);
        } catch (e) {
            console.error('Failed to fetch learned preferences:', e);
            setLearnedPrefs([]);
        }
    };

    const handleChange = (e) => {
        setFormData({ ...formData, [e.target.name]: e.target.value });
    };

    const handleSave = async () => {
        setMessage('');
        setError('');

        const { isValid, error: valError } = validateProfileFields(formData.email, formData.phone, formData.age);
        if (!isValid) {
            setError(valError);
            return;
        }

        try {
            await axiosClient.post('/auth/profile', formData);
            updateProfile(formData);
            setMessage('Đã lưu thông tin thành công!');
            setTimeout(() => setMessage(''), 3000);
        } catch (e) {
            setError('Lỗi: ' + (e.response?.data?.detail || e.message));
        }
    };

    const handlePwdChange = (e) => setPwdForm({ ...pwdForm, [e.target.name]: e.target.value });

    const handleChangePassword = async () => {
        setPwdMsg('');
        if (!pwdForm.current_password || !pwdForm.new_password || !pwdForm.confirm_password) {
            setPwdMsg('Vui lòng điền đầy đủ các trường.');
            return;
        }
        if (pwdForm.new_password !== pwdForm.confirm_password) {
            setPwdMsg('Mật khẩu mới và nhập lại không khớp.');
            return;
        }
        // Basic ascii validation (as in Streamlit)
        const isAscii = (s) => /^[\x00-\x7F]*$/.test(s);
        if (!isAscii(pwdForm.current_password) || !isAscii(pwdForm.new_password)) {
            setPwdMsg('Mật khẩu chỉ được chứa ký tự ASCII.');
            return;
        }

        try {
            const res = await axiosClient.post('/auth/change-password', {
                current_password: pwdForm.current_password,
                new_password: pwdForm.new_password
            });
            setPwdMsg('Đã đổi mật khẩu thành công.');
            setPwdForm({ current_password: '', new_password: '', confirm_password: '' });
            setTimeout(() => setPwdMsg(''), 4000);
        } catch (e) {
            setPwdMsg('Lỗi: ' + (e.response?.data?.detail || e.message));
        }
    };

    return (
        <div style={{ maxWidth: '700px', margin: '0 auto' }}>

            <div className="card" style={{ marginBottom: '2rem' }}>
                <h3 style={{ marginBottom: '1.5rem', fontSize: '1.2rem', fontWeight: '600' }}>Thông tin cá nhân</h3>

                {message && (
                    <div style={{ padding: '0.75rem', background: '#e8f5e9', color: '#2e7d32', borderRadius: '6px', marginBottom: '1rem' }}>
                        {message}
                    </div>
                )}
                {error && (
                    <div style={{ padding: '0.75rem', background: '#ffebee', color: '#c62828', borderRadius: '6px', marginBottom: '1rem' }}>
                        {error}
                    </div>
                )}

                <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
                    <div>
                        <label className="label">Họ tên</label>
                        <input className="input-field" value={user?.name || user?.full_name || ''} disabled style={{ background: '#f5f5f5' }} />
                    </div>
                    <div>
                        <label className="label">Email</label>
                        <input className="input-field" name="email" value={formData.email} onChange={handleChange} />
                    </div>
                    <div>
                        <label className="label">Số điện thoại</label>
                        <input className="input-field" name="phone" value={formData.phone} onChange={handleChange} />
                    </div>
                    <div>
                        <label className="label">Địa chỉ</label>
                        <input className="input-field" name="address" value={formData.address} onChange={handleChange} />
                    </div>
                    <div>
                        <label className="label">Tuổi</label>
                        <input className="input-field" name="age" value={formData.age} onChange={handleChange} />
                    </div>

                    <button className="btn btn-primary" onClick={handleSave} style={{ marginTop: '1rem', alignSelf: 'flex-start' }}>
                        <Save size={18} /> Lưu thay đổi
                    </button>
                </div>
            </div>

            <div className="card" style={{ marginBottom: '2rem' }}>
                <h3 style={{ marginBottom: '1rem', fontSize: '1.1rem', fontWeight: '600' }}>Đổi mật khẩu</h3>
                {pwdMsg && (
                    <div style={{ padding: '0.6rem', marginBottom: '0.8rem', borderRadius: '6px', background: pwdMsg.startsWith('Lỗi') ? '#ffebee' : '#e8f5e9', color: pwdMsg.startsWith('Lỗi') ? '#c62828' : '#2e7d32' }}>{pwdMsg}</div>
                )}
                <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
                    <input className="input-field" name="current_password" type="password" placeholder="Mật khẩu hiện tại" value={pwdForm.current_password} onChange={handlePwdChange} />
                    <input className="input-field" name="new_password" type="password" placeholder="Mật khẩu mới" value={pwdForm.new_password} onChange={handlePwdChange} />
                    <input className="input-field" name="confirm_password" type="password" placeholder="Nhập lại mật khẩu mới" value={pwdForm.confirm_password} onChange={handlePwdChange} />
                    <div style={{ display: 'flex', gap: '0.5rem' }}>
                        <button className="btn btn-primary" onClick={handleChangePassword}>Đổi mật khẩu</button>
                    </div>
                </div>
            </div>

            {/* Learned Personalization Section */}
            <div className="card" style={{ marginBottom: '2rem' }}>
                <h3 style={{ marginBottom: '1rem', fontSize: '1.1rem', fontWeight: '600', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                    <Sparkles size={20} color="#d32f2f" />
                    Cá nhân hóa tự động
                </h3>
                
                {learnedPrefs.length > 0 ? (
                    <>
                        <p style={{ fontSize: '0.9rem', color: '#666', marginBottom: '1rem' }}>
                            Chatbot đã tự động học phong cách sử dụng của bạn từ các cuộc trò chuyện:
                        </p>
                        <ul style={{ listStyle: 'none', padding: 0, display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
                            {learnedPrefs.map((pref, idx) => (
                                <li 
                                    key={idx} 
                                    style={{ 
                                        padding: '0.75rem', 
                                        background: '#f5f5f5', 
                                        borderRadius: '6px',
                                        borderLeft: '3px solid #d32f2f',
                                        fontSize: '0.95rem'
                                    }}
                                >
                                    {pref}
                                </li>
                            ))}
                        </ul>
                        <p style={{ fontSize: '0.85rem', color: '#888', marginTop: '1rem', fontStyle: 'italic' }}>
                            💡 Các cá nhân hóa này được cập nhật tự động sau mỗi 5 tin nhắn để chatbot phục vụ bạn tốt hơn.
                        </p>
                    </>
                ) : (
                    <div style={{ 
                        padding: '2rem', 
                        background: '#f9f9f9', 
                        borderRadius: '8px',
                        textAlign: 'center',
                        border: '2px dashed #e0e0e0'
                    }}>
                        
                        <p style={{ fontSize: '0.95rem', color: '#666', marginBottom: '0.5rem' }}>
                            Chưa có dữ liệu cá nhân hóa
                        </p>
                        <p style={{ fontSize: '0.85rem', color: '#999' }}>
                            Chatbot sẽ tự động học phong cách của bạn sau mỗi 5 tin nhắn trò chuyện. 
                            Hãy bắt đầu chat để hệ thống hiểu bạn hơn! 💬
                        </p>
                    </div>
                )}
            </div>
        </div>
    );
};

export default Settings;

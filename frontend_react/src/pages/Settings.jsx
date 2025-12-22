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
            const res = await axiosClient.get('/user/preferences');
            const learned = res.data.learned || {};
            console.log('[Settings] Learned preferences:', learned);

            // Handle both formats: dict (new) and array (legacy)
            if (typeof learned === 'object' && !Array.isArray(learned)) {
                // New format: { category: [items] }
                const categoryNames = {
                    learning_style: '📚 Phong cách học',
                    personality: '🧠 Tính cách',
                    emotions: '💭 Cảm xúc',
                    habits: '⏰ Thói quen',
                    schedule: '📅 Lịch trình',
                    interests: '⭐ Sở thích',
                    goals: '🎯 Mục tiêu',
                    challenges: '💪 Thách thức',
                    communication_style: '💬 Giao tiếp'
                };

                const flatList = [];
                for (const [category, items] of Object.entries(learned)) {
                    if (Array.isArray(items)) {
                        const categoryLabel = categoryNames[category] || category;
                        items.forEach(item => {
                            flatList.push(`${categoryLabel}: ${item}`);
                        });
                    }
                }
                setLearnedPrefs(flatList);
            } else if (Array.isArray(learned)) {
                // Legacy format: flat array
                setLearnedPrefs(learned);
            } else {
                setLearnedPrefs([]);
            }
        } catch (e) {
            console.error('Failed to fetch learned preferences:', e);
            setLearnedPrefs([]);
        }
    };

    const handleChange = (e) => {
        setFormData({ ...formData, [e.target.name]: e.target.value });
    };

    // Kiểm tra xem một field có thay đổi chưa lưu không
    const isFieldChanged = (fieldName) => {
        return formData[fieldName] !== (user?.[fieldName] || '');
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
        <div style={{ maxWidth: '700px', margin: '0 auto', paddingBottom: '3rem' }}>

            <div className="card" style={{ marginBottom: '2rem' }}>
                <h3 style={{ marginBottom: '1.5rem', fontSize: '1.25rem', fontWeight: '600', color: 'var(--text-primary)' }}>Thông tin cá nhân</h3>

                {message && (
                    <div style={{
                        padding: '1rem',
                        background: '#f0fdf4',
                        color: '#166534',
                        borderRadius: 'var(--radius-md)',
                        marginBottom: '1.5rem',
                        border: '1px solid #bbf7d0',
                        display: 'flex',
                        alignItems: 'center',
                        gap: '0.5rem'
                    }}>
                        <Sparkles size={18} />
                        {message}
                    </div>
                )}
                {error && (
                    <div style={{
                        padding: '1rem',
                        background: '#fef2f2',
                        color: 'var(--danger-color)',
                        borderRadius: 'var(--radius-md)',
                        marginBottom: '1.5rem',
                        border: '1px solid #fecaca'
                    }}>
                        {error}
                    </div>
                )}

                <div className="grid" style={{ gap: '1.5rem' }}>
                    <div>
                        <label className="label">Họ tên</label>
                        <input className="input-field" value={
                            user?.last_name && user?.first_name
                                ? `${user.last_name} ${user.first_name}`
                                : user?.name || user?.full_name || ''
                        } disabled style={{ background: 'var(--bg-body)', color: 'var(--text-secondary)', cursor: 'not-allowed' }} />
                    </div>
                    <div>
                        <label className="label">Email</label>
                        <input
                            className="input-field"
                            name="email"
                            value={formData.email}
                            onChange={handleChange}
                            style={{
                                borderColor: isFieldChanged('email') ? '#dc2626' : 'var(--border-color)',
                                borderWidth: isFieldChanged('email') ? '2px' : '1px',
                                backgroundColor: isFieldChanged('email') ? '#fef2f2' : 'transparent',
                                boxShadow: isFieldChanged('email') ? '0 0 0 3px rgba(220, 38, 38, 0.1)' : 'none'
                            }}
                        />
                    </div>
                    <div>
                        <label className="label">Số điện thoại</label>
                        <input
                            className="input-field"
                            name="phone"
                            value={formData.phone}
                            onChange={handleChange}
                            style={{
                                borderColor: isFieldChanged('phone') ? '#dc2626' : 'var(--border-color)',
                                borderWidth: isFieldChanged('phone') ? '2px' : '1px',
                                backgroundColor: isFieldChanged('phone') ? '#fef2f2' : 'transparent',
                                boxShadow: isFieldChanged('phone') ? '0 0 0 3px rgba(220, 38, 38, 0.1)' : 'none'
                            }}
                        />
                    </div>
                    <div>
                        <label className="label">Địa chỉ</label>
                        <input
                            className="input-field"
                            name="address"
                            value={formData.address}
                            onChange={handleChange}
                            style={{
                                borderColor: isFieldChanged('address') ? '#dc2626' : 'var(--border-color)',
                                borderWidth: isFieldChanged('address') ? '2px' : '1px',
                                backgroundColor: isFieldChanged('address') ? '#fef2f2' : 'transparent',
                                boxShadow: isFieldChanged('address') ? '0 0 0 3px rgba(220, 38, 38, 0.1)' : 'none'
                            }}
                        />
                    </div>
                    <div>
                        <label className="label">Tuổi</label>
                        <input
                            className="input-field"
                            name="age"
                            value={formData.age}
                            onChange={handleChange}
                            style={{
                                borderColor: isFieldChanged('age') ? '#dc2626' : 'var(--border-color)',
                                borderWidth: isFieldChanged('age') ? '2px' : '1px',
                                backgroundColor: isFieldChanged('age') ? '#fef2f2' : 'transparent',
                                boxShadow: isFieldChanged('age') ? '0 0 0 3px rgba(220, 38, 38, 0.1)' : 'none'
                            }}
                        />
                    </div>

                    <div style={{ paddingTop: '0.5rem' }}>
                        <button className="btn btn-primary" onClick={handleSave}>
                            <Save size={18} /> Lưu thay đổi
                        </button>
                    </div>
                </div>
            </div>

            <div className="card" style={{ marginBottom: '2rem' }}>
                <h3 style={{ marginBottom: '1.5rem', fontSize: '1.25rem', fontWeight: '600', color: 'var(--text-primary)' }}>Đổi mật khẩu</h3>
                {pwdMsg && (
                    <div style={{
                        padding: '1rem',
                        marginBottom: '1.5rem',
                        borderRadius: 'var(--radius-md)',
                        background: pwdMsg.startsWith('Lỗi') ? '#fef2f2' : '#f0fdf4',
                        color: pwdMsg.startsWith('Lỗi') ? 'var(--danger-color)' : '#166534',
                        border: `1px solid ${pwdMsg.startsWith('Lỗi') ? '#fecaca' : '#bbf7d0'}`
                    }}>
                        {pwdMsg}
                    </div>
                )}
                <div className="grid" style={{ gap: '1.25rem' }}>
                    <div>
                        <label className="label">Mật khẩu hiện tại</label>
                        <input className="input-field" name="current_password" type="password" placeholder="••••••••" value={pwdForm.current_password} onChange={handlePwdChange} />
                    </div>
                    <div>
                        <label className="label">Mật khẩu mới</label>
                        <input className="input-field" name="new_password" type="password" placeholder="••••••••" value={pwdForm.new_password} onChange={handlePwdChange} />
                    </div>
                    <div>
                        <label className="label">Nhập lại mật khẩu mới</label>
                        <input className="input-field" name="confirm_password" type="password" placeholder="••••••••" value={pwdForm.confirm_password} onChange={handlePwdChange} />
                    </div>
                    <div style={{ paddingTop: '0.5rem' }}>
                        <button className="btn btn-primary" onClick={handleChangePassword}>Đổi mật khẩu</button>
                    </div>
                </div>
            </div>

            {/* Learned Personalization Section */}
            <div className="card">
                <h3 style={{ marginBottom: '1.5rem', fontSize: '1.25rem', fontWeight: '600', display: 'flex', alignItems: 'center', gap: '0.75rem', color: 'var(--text-primary)' }}>
                    <Sparkles size={24} className="text-primary" style={{ color: 'var(--primary-color)' }} />
                    Cá nhân hóa tự động
                </h3>

                {learnedPrefs.length > 0 ? (
                    <>
                        <p style={{ fontSize: '1rem', color: 'var(--text-secondary)', marginBottom: '1.25rem' }}>
                            Chatbot đã tự động học phong cách sử dụng của bạn từ các cuộc trò chuyện:
                        </p>
                        <ul style={{ listStyle: 'none', padding: 0, display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
                            {learnedPrefs.map((pref, idx) => (
                                <li
                                    key={idx}
                                    style={{
                                        padding: '1rem',
                                        background: 'var(--bg-body)',
                                        borderRadius: 'var(--radius-md)',
                                        borderLeft: '4px solid var(--primary-color)',
                                        fontSize: '0.95rem',
                                        color: 'var(--text-primary)',
                                        boxShadow: 'var(--shadow-sm)'
                                    }}
                                >
                                    {pref}
                                </li>
                            ))}
                        </ul>
                        <p style={{ fontSize: '0.875rem', color: 'var(--text-tertiary)', marginTop: '1.5rem', fontStyle: 'italic', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                            <Sparkles size={14} />
                            Các cá nhân hóa này được cập nhật tự động để twin phục vụ bạn tốt hơn.
                        </p>
                    </>
                ) : (
                    <div style={{
                        padding: '3rem',
                        background: 'var(--bg-body)',
                        borderRadius: 'var(--radius-lg)',
                        textAlign: 'center',
                        border: '2px dashed var(--border-color)',
                        display: 'flex',
                        flexDirection: 'column',
                        alignItems: 'center',
                        gap: '1rem'
                    }}>
                        <div style={{
                            width: '60px',
                            height: '60px',
                            borderRadius: '50%',
                            background: 'var(--bg-surface)',
                            display: 'flex',
                            alignItems: 'center',
                            justifyContent: 'center',
                            boxShadow: 'var(--shadow-md)'
                        }}>
                            <Sparkles size={30} style={{ color: 'var(--text-tertiary)' }} />
                        </div>
                        <div>
                            <p style={{ fontSize: '1.1rem', color: 'var(--text-secondary)', marginBottom: '0.5rem', fontWeight: '600' }}>
                                Chưa có dữ liệu cá nhân hóa
                            </p>
                            <p style={{ fontSize: '0.95rem', color: 'var(--text-tertiary)', maxWidth: '400px', margin: '0 auto' }}>
                                Chatbot sẽ tự động học phong cách của bạn sau mỗi 3 tin nhắn trò chuyện.
                                Hãy bắt đầu chat để hệ thống hiểu bạn hơn!
                            </p>
                        </div>
                    </div>
                )}
            </div>
        </div>
    );
};

export default Settings;

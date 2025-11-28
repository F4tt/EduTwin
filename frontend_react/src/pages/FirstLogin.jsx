import React, { useEffect, useState, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import { motion, AnimatePresence } from 'framer-motion';
import { AlertCircle } from 'lucide-react';
import axiosClient from '../api/axiosClient';
import { validateProfileFields, validateScore } from '../utils/validation';
import { useAuth } from '../context/AuthContext';

const SUBJECTS = [
    { id: 'Toan', label: 'Toán' },
    { id: 'Ngu van', label: 'Ngữ văn' },
    { id: 'Tieng Anh', label: 'Tiếng Anh' },
    { id: 'Vat ly', label: 'Vật lý' },
    { id: 'Hoa hoc', label: 'Hóa học' },
    { id: 'Sinh hoc', label: 'Sinh học' },
    { id: 'Lich su', label: 'Lịch sử' },
    { id: 'Dia ly', label: 'Địa lý' },
    { id: 'Giao duc cong dan', label: 'GDCD' },
];

const GRADES = ['10', '11', '12'];
const SEMESTERS = ['1', '2'];

const FirstLogin = () => {
    const { user, updateProfile } = useAuth();
    const navigate = useNavigate();
    const errorRef = useRef(null);

    const [step, setStep] = useState(1);
    const [profileData, setProfileData] = useState({ email: '', phone: '', address: '', age: '' });
    const [scoreInputs, setScoreInputs] = useState({});
    const [inputErrors, setInputErrors] = useState({});
    const [currentGrade, setCurrentGrade] = useState('');
    const [loadingScores, setLoadingScores] = useState(false);
    const [error, setError] = useState('');

    useEffect(() => {
        // preload profile fields from user if present
        if (user) {
            setProfileData({
                email: user.email || '',
                phone: user.phone || '',
                address: user.address || '',
                age: user.age || ''
            });
            if (user.current_grade) setCurrentGrade(user.current_grade);
        }
    }, [user]);

    useEffect(() => {
        fetchScores();
    }, []);

    const fetchScores = async () => {
        setLoadingScores(true);
        try {
            const res = await axiosClient.get('/study/scores');
            const scores = res.data.scores || [];
            // initialize scoreInputs with actual or predicted values (but keep empty string for None)
            const initial = {};
            scores.forEach(it => {
                const key = `${it.subject}_${it.grade_level}_${it.semester}`;
                if (it.actual !== null && it.actual !== undefined) initial[key] = String(it.actual);
                else if (it.predicted !== null && it.predicted !== undefined) initial[key] = '';
            });
            setScoreInputs(initial);
        } catch (e) {
            console.error('Fetch scores failed', e);
        } finally {
            setLoadingScores(false);
        }
    };

    const handleProfileChange = (e) => {
        setProfileData({ ...profileData, [e.target.name]: e.target.value });
    };

    const handleStep1Submit = async (skip = false) => {
        if (!skip) {
            const { isValid, error: err } = validateProfileFields(profileData.email, profileData.phone, profileData.age);
            if (!isValid) {
                setError(err);
                return;
            }
            try {
                await axiosClient.post('/auth/profile', profileData);
                updateProfile(profileData);
            } catch (e) {
                setError('Lỗi lưu thông tin: ' + (e.response?.data?.detail || e.message));
                return;
            }
        }
        setError('');
        setStep(2);
    };

    const handleScoreChange = (subjectId, grade, semester, value) => {
        const key = `${subjectId}_${grade}_${semester}`;
        setScoreInputs(prev => ({ ...prev, [key]: value }));
        const err = validateScore(value);
        if (err) setInputErrors(prev => ({ ...prev, [key]: err }));
        else {
            const copy = { ...inputErrors };
            delete copy[key];
            setInputErrors(copy);
        }
    };

    const handleStep2Submit = async () => {
        setError('');
        if (!currentGrade) {
            setError('Vui lòng chọn học kỳ hiện tại.');
            return;
        }
        if (Object.keys(inputErrors).length > 0) {
            setError('Vui lòng sửa các lỗi nhập liệu màu đỏ.');
            return;
        }

        const updates = [];
        let hasError = false;

        GRADES.forEach(grade => {
            SEMESTERS.forEach(sem => {
                SUBJECTS.forEach(subj => {
                    const key = `${subj.id}_${grade}_${sem}`;
                    const rawVal = scoreInputs[key];
                    if (rawVal && String(rawVal).trim() !== '') {
                        const val = parseFloat(String(rawVal).replace(',', '.'));
                        if (isNaN(val) || val < 0 || val > 10) {
                            hasError = true;
                            setInputErrors(prev => ({ ...prev, [key]: 'Lỗi' }));
                            return;
                        }
                        updates.push({ subject: subj.id, grade_level: grade, semester: sem, score: val });
                    }
                });
            });
        });

        if (hasError) {
            setError('Có lỗi nhập liệu. Vui lòng kiểm tra lại.');
            return;
        }

        try {
            await axiosClient.post('/auth/profile', { current_grade: currentGrade });
            updateProfile({ current_grade: currentGrade });

            if (updates.length > 0) {
                await axiosClient.post('/study/scores/bulk', { scores: updates });
            }

            await axiosClient.post('/auth/complete-first-time');
            updateProfile({ is_first_login: false });

            navigate('/chat');
        } catch (e) {
            setError('Lỗi khi lưu dữ liệu: ' + (e.response?.data?.detail || e.message));
        }
    };

    const gradeOptions = [
        { value: '1_10', label: 'Học kỳ 1 - Lớp 10' },
        { value: '2_10', label: 'Học kỳ 2 - Lớp 10' },
        { value: '1_11', label: 'Học kỳ 1 - Lớp 11' },
        { value: '2_11', label: 'Học kỳ 2 - Lớp 11' },
        { value: '1_12', label: 'Học kỳ 1 - Lớp 12' },
        { value: '2_12', label: 'Học kỳ 2 - Lớp 12' },
    ];

    const isInputDisabled = (grade, semester) => {
        if (!currentGrade) return false;
        const [curSem, curGrade] = currentGrade.split('_').map(Number);
        const tg = parseInt(grade, 10);
        const ts = parseInt(semester, 10);
        if (tg > curGrade) return true;
        if (tg === curGrade && ts > curSem) return true;
        return false;
    };

    return (
        <div style={{ minHeight: '100vh', background: '#f8f9fa', padding: '2rem', display: 'flex', justifyContent: 'center', alignItems: 'center' }}>
            <div className="card" style={{ width: '100%', maxWidth: '900px', padding: '2.5rem', maxHeight: '90vh', overflowY: 'auto' }}>

                {/* Progress Bar */}
                <div style={{ marginBottom: '2rem' }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '0.5rem', color: '#666', fontSize: '0.9rem' }}>
                        <span>Thông tin cá nhân</span>
                        <span>Kết quả học tập</span>
                    </div>
                    <div style={{ height: '6px', background: '#eee', borderRadius: '3px', overflow: 'hidden' }}>
                        <motion.div
                            initial={{ width: '0%' }}
                            animate={{ width: step === 1 ? '50%' : '100%' }}
                            style={{ height: '100%', background: '#d32f2f' }}
                        />
                    </div>
                </div>

                <AnimatePresence mode='wait'>
                    {step === 1 && (
                        <motion.div key="step1" initial={{ opacity: 0, x: -20 }} animate={{ opacity: 1, x: 0 }} exit={{ opacity: 0, x: 20 }}>
                            <h2 style={{ fontSize: '1.75rem', fontWeight: '700', marginBottom: '0.5rem' }}>👋 Chào mừng đến với EduTwin</h2>
                            <p style={{ color: '#666', marginBottom: '2rem' }}>Hãy cập nhật thông tin để chúng tôi hỗ trợ bạn tốt hơn.</p>

                            {error && (
                                <div ref={errorRef} style={{ color: '#c62828', marginBottom: '1rem', background: '#ffebee', padding: '0.75rem', borderRadius: '6px', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                                    <AlertCircle size={18} /> {error}
                                </div>
                            )}

                            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1.5rem' }}>
                                <div>
                                    <label className="label">Email</label>
                                    <input className="input-field" name="email" value={profileData.email} onChange={handleProfileChange} placeholder="VD: example@email.com" />
                                </div>
                                <div>
                                    <label className="label">Số điện thoại</label>
                                    <input className="input-field" name="phone" value={profileData.phone} onChange={handleProfileChange} placeholder="VD: 0912 345 678" />
                                </div>
                                <div>
                                    <label className="label">Địa chỉ</label>
                                    <input className="input-field" name="address" value={profileData.address} onChange={handleProfileChange} placeholder="VD: Hà Nội" />
                                </div>
                                <div>
                                    <label className="label">Tuổi</label>
                                    <input className="input-field" name="age" value={profileData.age} onChange={handleProfileChange} placeholder="VD: 16" />
                                </div>
                            </div>

                            <div style={{ display: 'flex', justifyContent: 'space-between', marginTop: '2rem' }}>
                                <button className="btn btn-outline" onClick={() => handleStep1Submit(true)}>Bỏ qua</button>
                                <button className="btn btn-primary" onClick={() => handleStep1Submit(false)}>Lưu và Tiếp tục</button>
                            </div>
                        </motion.div>
                    )}

                    {step === 2 && (
                        <motion.div key="step2" initial={{ opacity: 0, x: -20 }} animate={{ opacity: 1, x: 0 }} exit={{ opacity: 0, x: 20 }}>
                            <h2 style={{ fontSize: '1.75rem', fontWeight: '700', marginBottom: '0.5rem' }}>📚 Kết quả học tập</h2>
                            <p style={{ color: '#666', marginBottom: '2rem' }}>Nhập điểm số các môn học (nếu có).</p>

                            {error && (
                                <div ref={errorRef} style={{ color: '#c62828', marginBottom: '1rem', background: '#ffebee', padding: '0.75rem', borderRadius: '6px', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                                    <AlertCircle size={18} /> {error}
                                </div>
                            )}

                            <div style={{ marginBottom: '2rem', background: '#e3f2fd', padding: '1rem', borderRadius: '8px' }}>
                                <label className="label" style={{ color: '#1565c0' }}>Học kỳ hiện tại của bạn <span style={{ color: 'red' }}>*</span></label>
                                <select className="input-field" value={currentGrade} onChange={(e) => setCurrentGrade(e.target.value)} style={{ borderColor: '#2196f3' }}>
                                    <option value="">-- Chọn học kỳ --</option>
                                    {gradeOptions.map(opt => (<option key={opt.value} value={opt.value}>{opt.label}</option>))}
                                </select>
                                <p style={{ fontSize: '0.85rem', color: '#555', marginTop: '0.5rem' }}>* Các ô nhập điểm cho học kỳ tương lai sẽ bị khóa.</p>
                            </div>

                            {loadingScores ? (
                                <div>Đang tải dữ liệu...</div>
                            ) : (
                                <div style={{ maxHeight: '500px', overflowY: 'auto', paddingRight: '0.5rem' }}>
                                    {GRADES.map(grade => (
                                        <div key={grade} style={{ marginBottom: '2rem', border: '1px solid #eee', borderRadius: '8px', padding: '1rem' }}>
                                            <h3 style={{ fontSize: '1.2rem', fontWeight: '700', marginBottom: '1rem', color: '#d32f2f', borderBottom: '2px solid #fce4ec', paddingBottom: '0.5rem' }}>Lớp {grade}</h3>
                                            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '2rem' }}>
                                                {SEMESTERS.map(sem => {
                                                    const disabled = isInputDisabled(grade, sem);
                                                    return (
                                                        <div key={sem} style={{ opacity: disabled ? 0.5 : 1 }}>
                                                            <h4 style={{ fontSize: '1rem', fontWeight: '600', marginBottom: '0.75rem', color: '#555' }}>Học kỳ {sem} {disabled && '(Chưa học)'}</h4>
                                                            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(100px, 1fr))', gap: '0.75rem' }}>
                                                                {SUBJECTS.map(subj => {
                                                                    const key = `${subj.id}_${grade}_${sem}`;
                                                                    const hasError = !!inputErrors[key];
                                                                    return (
                                                                        <div key={key}>
                                                                            <label style={{ fontSize: '0.8rem', display: 'block', marginBottom: '0.2rem', color: hasError ? '#c62828' : '#444' }}>{subj.label}</label>
                                                                            <div style={{ position: 'relative' }}>
                                                                                <input
                                                                                    className="input-field"
                                                                                    style={{ padding: '0.4rem', fontSize: '0.9rem', borderColor: hasError ? '#c62828' : '#e0e0e0', background: hasError ? '#ffebee' : 'white' }}
                                                                                    placeholder="VD: 8.5"
                                                                                    value={scoreInputs[key] || ''}
                                                                                    onChange={(e) => handleScoreChange(subj.id, grade, sem, e.target.value)}
                                                                                    disabled={disabled}
                                                                                />
                                                                                {hasError && (<div style={{ position: 'absolute', right: 0, top: '100%', fontSize: '0.7rem', color: '#c62828', zIndex: 10 }}>{inputErrors[key]}</div>)}
                                                                            </div>
                                                                        </div>
                                                                    );
                                                                })}
                                                            </div>
                                                        </div>
                                                    );
                                                })}
                                            </div>
                                        </div>
                                    ))}
                                </div>
                            )}

                            <div style={{ display: 'flex', justifyContent: 'space-between', marginTop: '2rem', paddingTop: '1rem', borderTop: '1px solid #eee' }}>
                                <button className="btn btn-outline" onClick={() => setStep(1)}>Quay lại</button>
                                <button className="btn btn-primary" onClick={handleStep2Submit} disabled={!currentGrade}>Hoàn tất và Lưu</button>
                            </div>
                        </motion.div>
                    )}
                </AnimatePresence>
            </div>
        </div>
    );
};

export default FirstLogin;

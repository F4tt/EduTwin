import React, { useEffect, useState, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import { motion, AnimatePresence } from 'framer-motion';
import { AlertCircle, Download, Upload, FileText } from 'lucide-react';
import * as XLSX from 'xlsx';
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
    const [uploadFile, setUploadFile] = useState(null);
    const [uploading, setUploading] = useState(false);

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

    const handleDownloadTemplate = () => {
        const columns = [];
        SUBJECTS.forEach(subj => {
            GRADES.forEach(grade => {
                SEMESTERS.forEach(sem => {
                    columns.push(`${subj.id}_${grade}_${sem}`);
                });
            });
        });

        // Create Excel file using HTML table
        let excelContent = '<html xmlns:o="urn:schemas-microsoft-com:office:office" xmlns:x="urn:schemas-microsoft-com:office:excel" xmlns="http://www.w3.org/TR/REC-html40">';
        excelContent += '<head><meta charset="utf-8"/></head><body><table>';
        
        // Header row
        excelContent += '<tr>';
        columns.forEach(col => {
            excelContent += `<th>${col}</th>`;
        });
        excelContent += '</tr>';
        
        // One empty sample row
        excelContent += '<tr>';
        columns.forEach(() => {
            excelContent += '<td></td>';
        });
        excelContent += '</tr>';
        
        excelContent += '</table></body></html>';

        const blob = new Blob([excelContent], { type: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet' });
        const link = document.createElement('a');
        const url = URL.createObjectURL(blob);
        link.setAttribute('href', url);
        link.setAttribute('download', 'my_scores_template.xlsx');
        link.style.visibility = 'hidden';
        document.body.appendChild(link);
        link.click();
        document.body.removeChild(link);
    };

    const handleFileUpload = async () => {
        if (!uploadFile) {
            setError('Vui lòng chọn file trước.');
            return;
        }
        if (!currentGrade) {
            setError('Vui lòng chọn học kỳ hiện tại trước khi tải lên.');
            return;
        }

        setUploading(true);
        setError('');

        try {
            // Use FormData to send Excel file to backend
            const formData = new FormData();
            formData.append('file', uploadFile);
            formData.append('current_grade', currentGrade);

            const res = await axiosClient.post('/study/scores/import-excel', formData, {
                headers: { 'Content-Type': 'multipart/form-data' }
            });

            const imported = res.data.imported_scores || [];
            const newInputs = { ...scoreInputs };
            const newErrors = { ...inputErrors };

            imported.forEach(score => {
                const key = `${score.subject}_${score.grade_level}_${score.semester}`;
                const value = String(score.score);
                const err = validateScore(value);
                if (err) {
                    newErrors[key] = err;
                } else {
                    newInputs[key] = value;
                    delete newErrors[key];
                }
            });

            setScoreInputs(newInputs);
            setInputErrors(newErrors);
            setUploadFile(null);
            setError('');
            alert('Đã import điểm từ file thành công!');
        } catch (e) {
            setError('Lỗi đọc file: ' + e.message);
        } finally {
            setUploading(false);
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
        <div style={{ minHeight: '100vh', background: 'var(--bg-body)', padding: '2rem', display: 'flex', justifyContent: 'center', alignItems: 'center' }}>
            <div className="card" style={{ width: '100%', maxWidth: '900px', padding: '2.5rem', maxHeight: '90vh', overflowY: 'auto' }}>

                {/* Progress Bar */}
                <div style={{ marginBottom: '2.5rem' }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '0.75rem', color: 'var(--text-secondary)', fontSize: '0.95rem', fontWeight: '500' }}>
                        <span>Thông tin cá nhân</span>
                        <span>Kết quả học tập</span>
                    </div>
                    <div style={{ height: '8px', background: 'var(--border-color)', borderRadius: '4px', overflow: 'hidden' }}>
                        <motion.div
                            initial={{ width: '0%' }}
                            animate={{ width: step === 1 ? '50%' : '100%' }}
                            style={{ height: '100%', background: 'var(--primary-color)' }}
                        />
                    </div>
                </div>

                <AnimatePresence mode='wait'>
                    {step === 1 && (
                        <motion.div key="step1" initial={{ opacity: 0, x: -20 }} animate={{ opacity: 1, x: 0 }} exit={{ opacity: 0, x: 20 }}>
                            <h2 style={{ fontSize: '1.75rem', fontWeight: '700', marginBottom: '0.5rem', color: 'var(--text-primary)' }}>👋 Chào mừng đến với EduTwin</h2>
                            <p style={{ color: 'var(--text-secondary)', marginBottom: '2rem' }}>Hãy cập nhật thông tin để chúng tôi hỗ trợ bạn tốt hơn.</p>

                            {error && (
                                <div ref={errorRef} style={{
                                    color: 'var(--danger-color)',
                                    marginBottom: '1.5rem',
                                    background: '#fef2f2',
                                    padding: '1rem',
                                    borderRadius: 'var(--radius-md)',
                                    display: 'flex',
                                    alignItems: 'center',
                                    gap: '0.5rem',
                                    border: '1px solid #fecaca'
                                }}>
                                    <AlertCircle size={18} /> {error}
                                </div>
                            )}

                            <div className="grid" style={{ gridTemplateColumns: '1fr 1fr', gap: '1.5rem' }}>
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

                            <div style={{ display: 'flex', justifyContent: 'space-between', marginTop: '2.5rem' }}>
                                <button className="btn btn-outline" onClick={() => handleStep1Submit(true)}>Bỏ qua</button>
                                <button className="btn btn-primary" onClick={() => handleStep1Submit(false)}>Lưu và Tiếp tục</button>
                            </div>
                        </motion.div>
                    )}

                    {step === 2 && (
                        <motion.div key="step2" initial={{ opacity: 0, x: -20 }} animate={{ opacity: 1, x: 0 }} exit={{ opacity: 0, x: 20 }}>
                            <h2 style={{ fontSize: '1.75rem', fontWeight: '700', marginBottom: '0.5rem', color: 'var(--text-primary)' }}>📚 Kết quả học tập</h2>
                            <p style={{ color: 'var(--text-secondary)', marginBottom: '2rem' }}>Nhập điểm số các môn học (nếu có).</p>

                            {error && (
                                <div ref={errorRef} style={{
                                    color: 'var(--danger-color)',
                                    marginBottom: '1.5rem',
                                    background: '#fef2f2',
                                    padding: '1rem',
                                    borderRadius: 'var(--radius-md)',
                                    display: 'flex',
                                    alignItems: 'center',
                                    gap: '0.5rem',
                                    border: '1px solid #fecaca'
                                }}>
                                    <AlertCircle size={18} /> {error}
                                </div>
                            )}

                            <div style={{ marginBottom: '2rem', background: 'var(--primary-light)', padding: '1.5rem', borderRadius: 'var(--radius-md)' }}>
                                <label className="label" style={{ color: 'var(--primary-color)', fontWeight: '600' }}>Học kỳ hiện tại của bạn <span style={{ color: 'var(--danger-color)' }}>*</span></label>
                                <select className="input-field" value={currentGrade} onChange={(e) => setCurrentGrade(e.target.value)} style={{ borderColor: 'var(--primary-color)' }}>
                                    <option value="">-- Chọn học kỳ --</option>
                                    {gradeOptions.map(opt => (<option key={opt.value} value={opt.value}>{opt.label}</option>))}
                                </select>
                                <p style={{ fontSize: '0.85rem', color: 'var(--text-secondary)', marginTop: '0.5rem' }}>* Các ô nhập điểm cho học kỳ tương lai sẽ bị khóa.</p>
                            </div>

                            <div style={{
                                marginBottom: '2rem',
                                borderRadius: 'var(--radius-md)',
                                background: 'white',
                                border: '1px solid var(--border-color)',
                                boxShadow: '0 1px 3px rgba(0, 0, 0, 0.1)',
                                overflow: 'hidden'
                            }}>
                                <div style={{
                                    padding: '1.25rem 1.5rem',
                                    borderBottom: '1px solid var(--border-color)',
                                    display: 'flex',
                                    justifyContent: 'space-between',
                                    alignItems: 'center',
                                    background: 'var(--bg-surface)'
                                }}>
                                    <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
                                        <div style={{
                                            background: 'var(--primary-light)',
                                            color: 'var(--primary-color)',
                                            padding: '0.5rem',
                                            borderRadius: '8px',
                                            display: 'flex',
                                            alignItems: 'center',
                                            justifyContent: 'center'
                                        }}>
                                            <Upload size={20} />
                                        </div>
                                        <div>
                                            <h4 style={{ fontSize: '1rem', fontWeight: '600', margin: 0, color: 'var(--text-primary)' }}>Tải lên file điểm</h4>
                                            <p style={{ fontSize: '0.85rem', color: 'var(--text-secondary)', margin: 0 }}>Nhập nhanh điểm số từ file mẫu</p>
                                        </div>
                                    </div>
                                    <button
                                        onClick={handleDownloadTemplate}
                                        className="btn btn-ghost"
                                        style={{ fontSize: '0.85rem', gap: '0.5rem', color: 'var(--primary-color)', fontWeight: '500' }}
                                    >
                                        <Download size={16} /> Tải xuống file định dạng mẫu
                                    </button>
                                </div>

                                <div style={{ padding: '2rem' }}>
                                    {!uploadFile ? (
                                        <>
                                            <input
                                                type="file"
                                                accept=".xlsx,.xls"
                                                onChange={(e) => setUploadFile(e.target.files[0])}
                                                style={{ display: 'none' }}
                                                id="score-upload-input"
                                            />
                                            <label
                                                htmlFor="score-upload-input"
                                                style={{
                                                    display: 'flex',
                                                    flexDirection: 'column',
                                                    alignItems: 'center',
                                                    justifyContent: 'center',
                                                    padding: '2.5rem',
                                                    border: '2px dashed var(--border-color)',
                                                    borderRadius: 'var(--radius-lg)',
                                                    cursor: 'pointer',
                                                    transition: 'all 0.2s',
                                                    background: 'var(--bg-body)',
                                                    gap: '1rem'
                                                }}
                                                onMouseOver={(e) => {
                                                    e.currentTarget.style.borderColor = 'var(--primary-color)';
                                                    e.currentTarget.style.background = 'var(--primary-light)';
                                                }}
                                                onMouseOut={(e) => {
                                                    e.currentTarget.style.borderColor = 'var(--border-color)';
                                                    e.currentTarget.style.background = 'var(--bg-body)';
                                                }}
                                            >
                                                <div style={{
                                                    background: 'white',
                                                    padding: '1rem',
                                                    borderRadius: '50%',
                                                    boxShadow: '0 2px 4px rgba(0,0,0,0.05)',
                                                    color: 'var(--text-secondary)'
                                                }}>
                                                    <Upload size={24} />
                                                </div>
                                                <div style={{ textAlign: 'center' }}>
                                                    <span style={{ display: 'block', fontSize: '1rem', fontWeight: '600', color: 'var(--text-primary)', marginBottom: '0.25rem' }}>
                                                        Click để tải file lên
                                                    </span>
                                                    <span style={{ fontSize: '0.85rem', color: 'var(--text-tertiary)' }}>
                                                        Hỗ trợ định dạng Excel (.xlsx, .xls)
                                                    </span>
                                                </div>
                                            </label>
                                        </>
                                    ) : (
                                        <div style={{
                                            padding: '1.5rem',
                                            border: '1px solid var(--primary-color)',
                                            borderRadius: 'var(--radius-lg)',
                                            background: 'var(--primary-light)',
                                            display: 'flex',
                                            flexDirection: 'column',
                                            alignItems: 'center',
                                            animation: 'fadeIn 0.3s ease'
                                        }}>
                                            <div style={{
                                                background: 'var(--primary-color)',
                                                color: 'white',
                                                width: '48px',
                                                height: '48px',
                                                borderRadius: '12px',
                                                display: 'flex',
                                                alignItems: 'center',
                                                justifyContent: 'center',
                                                marginBottom: '1rem',
                                                boxShadow: '0 4px 6px -1px rgba(var(--primary-rgb), 0.3)'
                                            }}>
                                                <FileText size={24} />
                                            </div>
                                            <h4 style={{ margin: '0 0 0.25rem 0', color: 'var(--text-primary)', fontWeight: '600' }}>{uploadFile.name}</h4>
                                            <p style={{ margin: '0 0 1.5rem 0', color: 'var(--text-secondary)', fontSize: '0.85rem' }}>
                                                {(uploadFile.size / 1024).toFixed(1)} KB
                                            </p>
                                            <div style={{ display: 'flex', gap: '0.75rem' }}>
                                                <button
                                                    onClick={() => setUploadFile(null)}
                                                    className="btn"
                                                    style={{
                                                        background: 'white',
                                                        border: '1px solid var(--border-color)',
                                                        color: 'var(--text-secondary)',
                                                        padding: '0.5rem 1rem'
                                                    }}
                                                >
                                                    Hủy bỏ
                                                </button>
                                                <button
                                                    onClick={handleFileUpload}
                                                    disabled={uploading || !currentGrade}
                                                    className="btn btn-primary"
                                                    style={{ padding: '0.5rem 1.5rem' }}
                                                >
                                                    {uploading ? 'Đang xử lý...' : 'Áp dụng ngay'}
                                                </button>
                                            </div>
                                        </div>
                                    )}
                                </div>
                            </div>

                            {loadingScores ? (
                                <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', color: 'var(--primary-color)' }}>
                                    <span className="spinner"></span> Đang tải dữ liệu...
                                </div>
                            ) : (
                                <div style={{ maxHeight: '500px', overflowY: 'auto', paddingRight: '0.5rem' }}>
                                    {GRADES.map(grade => (
                                        <div key={grade} style={{ marginBottom: '2rem', border: '1px solid var(--border-color)', borderRadius: 'var(--radius-lg)', padding: '1.5rem' }}>
                                            <h3 style={{ fontSize: '1.2rem', fontWeight: '700', marginBottom: '1.5rem', color: 'var(--primary-color)', borderBottom: '1px solid var(--border-color)', paddingBottom: '0.75rem' }}>Lớp {grade}</h3>
                                            <div className="grid" style={{ gridTemplateColumns: '1fr 1fr', gap: '2rem' }}>
                                                {SEMESTERS.map(sem => {
                                                    const disabled = isInputDisabled(grade, sem);
                                                    return (
                                                        <div key={sem} style={{ opacity: disabled ? 0.5 : 1 }}>
                                                            <h4 style={{ fontSize: '1rem', fontWeight: '600', marginBottom: '1rem', color: 'var(--text-secondary)' }}>Học kỳ {sem} {disabled && '(Chưa học)'}</h4>
                                                            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(100px, 1fr))', gap: '1rem' }}>
                                                                {SUBJECTS.map(subj => {
                                                                    const key = `${subj.id}_${grade}_${sem}`;
                                                                    const hasError = !!inputErrors[key];
                                                                    return (
                                                                        <div key={key}>
                                                                            <label style={{ fontSize: '0.85rem', display: 'block', marginBottom: '0.25rem', color: hasError ? 'var(--danger-color)' : 'var(--text-secondary)' }}>{subj.label}</label>
                                                                            <div style={{ position: 'relative' }}>
                                                                                <input
                                                                                    className="input-field"
                                                                                    style={{
                                                                                        padding: '0.5rem',
                                                                                        fontSize: '0.95rem',
                                                                                        borderColor: hasError ? 'var(--danger-color)' : 'var(--border-color)',
                                                                                        background: hasError ? '#fef2f2' : 'var(--bg-surface)'
                                                                                    }}
                                                                                    placeholder="-"
                                                                                    value={scoreInputs[key] || ''}
                                                                                    onChange={(e) => handleScoreChange(subj.id, grade, sem, e.target.value)}
                                                                                    disabled={disabled}
                                                                                />
                                                                                {hasError && (<div style={{ position: 'absolute', right: 0, top: '100%', fontSize: '0.75rem', color: 'var(--danger-color)', zIndex: 10 }}>{inputErrors[key]}</div>)}
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

                            <div style={{ display: 'flex', justifyContent: 'space-between', marginTop: '2rem', paddingTop: '1.5rem', borderTop: '1px solid var(--border-color)' }}>
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

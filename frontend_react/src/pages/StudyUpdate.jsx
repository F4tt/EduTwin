import React, { useState, useEffect, useCallback, useRef } from 'react';
import axiosClient from '../api/axiosClient';
import { Save, Trash2 } from 'lucide-react';
import { useAuth } from '../context/AuthContext';
import {
    emitStudyScoresUpdated,
    emitMlPipelineProcessing,
    emitMlPipelineCompleted,
    REFRESH_DATA_EVENTS,
    ML_PIPELINE_PROCESSING_EVENT,
    ML_PIPELINE_COMPLETED_EVENT,
} from '../utils/eventBus';

const StudyUpdate = () => {
    const { user, updateProfile } = useAuth();
    const [scores, setScores] = useState([]);
    const [loading, setLoading] = useState(true);
    const [inputs, setInputs] = useState({});
    const [message, setMessage] = useState({ type: '', text: '' });
    const [pipelineBanner, setPipelineBanner] = useState({ type: '', text: '' });
    const pipelineTimeoutRef = useRef(null);
    const [currentGrade, setCurrentGrade] = useState(user?.current_grade || '');
    const skipNextRefreshRef = useRef(false);

    useEffect(() => {
        // sync current grade when auth profile changes
        setCurrentGrade(user?.current_grade || '');
    }, [user]);

    const applySnapshot = useCallback((payload) => {
        console.log('[StudyUpdate] applySnapshot called with:', payload);
        if (!payload || !Array.isArray(payload.scores)) {
            console.warn('[StudyUpdate] Invalid snapshot payload');
            return;
        }

        const data = payload.scores;
        console.log(`[StudyUpdate] Applying ${data.length} score records`);
        setScores(data);

        if (Object.prototype.hasOwnProperty.call(payload, 'current_grade')) {
            setCurrentGrade(payload.current_grade || '');
        }

        const initialInputs = {};
        data.forEach(item => {
            initialInputs[item.key] = item.actual !== null ? item.actual : '';
        });
        setInputs(initialInputs);
        console.log('[StudyUpdate] Snapshot applied successfully');
    }, []);

    const fetchScores = useCallback(async (silent = false) => {
        try {
            if (!silent) {
                setLoading(true);
            }
            const res = await axiosClient.get('/study/scores');
            applySnapshot(res.data);
        } catch (e) {
            console.error(e);
        } finally {
            if (!silent) {
                setLoading(false);
            }
        }
    }, [applySnapshot]);

    useEffect(() => {
        fetchScores();
    }, [fetchScores]);

    useEffect(() => {
        const handler = () => {
            if (skipNextRefreshRef.current) {
                console.log('[StudyUpdate] Skipping refresh - snapshot was just applied');
                skipNextRefreshRef.current = false;
                return;
            }
            fetchScores(true);
        };
        REFRESH_DATA_EVENTS.forEach(evt => window.addEventListener(evt, handler));
        return () => {
            REFRESH_DATA_EVENTS.forEach(evt => window.removeEventListener(evt, handler));
        };
    }, [fetchScores]);

    useEffect(() => {
        const handleProcessing = (event) => {
            if (pipelineTimeoutRef.current) {
                clearTimeout(pipelineTimeoutRef.current);
            }
            const detail = event?.detail || {};
            setPipelineBanner({
                type: 'info',
                text: detail.message || 'Pipeline đang cập nhật dữ liệu...'
            });
        };
        const handleCompleted = (event) => {
            if (pipelineTimeoutRef.current) {
                clearTimeout(pipelineTimeoutRef.current);
            }
            const detail = event?.detail || {};
            if (detail.error) {
                setPipelineBanner({ type: 'error', text: detail.error });
            } else {
                const stats = detail.stats || detail.pipeline || {};
                const processed = stats.processed_users ? ` (${stats.processed_users} người dùng)` : '';
                setPipelineBanner({
                    type: 'success',
                    text: detail.message || `Pipeline đã hoàn tất${processed}.`
                });
            }
            pipelineTimeoutRef.current = setTimeout(() => {
                setPipelineBanner({ type: '', text: '' });
            }, 4000);
        };
        window.addEventListener(ML_PIPELINE_PROCESSING_EVENT, handleProcessing);
        window.addEventListener(ML_PIPELINE_COMPLETED_EVENT, handleCompleted);
        return () => {
            window.removeEventListener(ML_PIPELINE_PROCESSING_EVENT, handleProcessing);
            window.removeEventListener(ML_PIPELINE_COMPLETED_EVENT, handleCompleted);
            if (pipelineTimeoutRef.current) {
                clearTimeout(pipelineTimeoutRef.current);
            }
        };
    }, []);

    const notifyScoresUpdated = () => {
        emitStudyScoresUpdated();
    };

    const handleChange = (key, value) => {
        setInputs(prev => ({ ...prev, [key]: value }));
    };

    const handleSaveGrade = async () => {
        if (!currentGrade) {
            setMessage({ type: 'error', text: 'Vui lòng chọn học kỳ hiện tại.' });
            return;
        }
        try {
            await axiosClient.post('/auth/profile', { current_grade: currentGrade });
            updateProfile({ current_grade: currentGrade });
            setMessage({ type: 'success', text: 'Đã lưu học kỳ hiện tại!' });
            setTimeout(() => setMessage({ type: '', text: '' }), 3000);
            await fetchScores(); // Refresh scores
            notifyScoresUpdated();
        } catch (e) {
            setMessage({ type: 'error', text: 'Lỗi lưu học kỳ: ' + e.message });
        }
    };

    const slotIndexForToken = (token) => {
        if (!token) return null;
        try {
            const parts = String(token).split('_');
            if (parts.length !== 2) return null;
            const sem = parts[0];
            const gr = parts[1];
            const ordered = [];
            ['10', '11', '12'].forEach(g => {
                ['1', '2'].forEach(s => ordered.push({ g, s }));
            });
            for (let i = 0; i < ordered.length; i++) {
                if (ordered[i].g === gr && ordered[i].s === sem) return i;
            }
        } catch {
            return null;
        }
        return null;
    };

    const activeIdx = slotIndexForToken(currentGrade);

    const handleSave = async () => {
        setMessage({ type: '', text: '' });
        const updates = [];
        let hasError = false;
        scores.forEach(item => {
            const rawVal = String(inputs[item.key] || '').trim();
            // determine rec_idx for this record
            let recIdx = null;
            try {
                const ordered = [];
                ['10', '11', '12'].forEach(g => ['1', '2'].forEach(s => ordered.push({ g, s })));
                for (let i = 0; i < ordered.length; i++) {
                    if (ordered[i].g === item.grade_level && ordered[i].s === item.semester) { recIdx = i; break; }
                }
            } catch { recIdx = null; }

            // skip inputs for future slots beyond activeIdx
            if (activeIdx !== null && recIdx !== null && activeIdx !== undefined && recIdx > activeIdx) {
                return;
            }

            if (rawVal) {
                const val = parseFloat(rawVal.replace(',', '.'));
                if (isNaN(val) || val < 0 || val > 10) {
                    hasError = true;
                    return;
                }
                // Only update if changed or new
                if (val !== item.actual) {
                    updates.push({ subject: item.subject, grade_level: item.grade_level, semester: item.semester, score: val });
                }
            }
        });

        if (hasError) {
            setMessage({ type: 'error', text: 'Điểm số phải từ 0-10.' });
            return;
        }

        if (updates.length === 0) {
            setMessage({ type: 'info', text: 'Không có thay đổi nào.' });
            return;
        }

        try {
            emitMlPipelineProcessing({ message: 'Đang đồng bộ pipeline với điểm mới của bạn...' });
            let responseData = null;
            if (updates.length > 0) {
                const res = await axiosClient.post('/study/scores/bulk', { scores: updates });
                responseData = res?.data;
                console.log('[StudyUpdate] Bulk save response:', responseData);
            }
            setMessage({ type: 'success', text: 'Đã lưu thành công!' });

            if (responseData?.scores_snapshot) {
                console.log('[StudyUpdate] Applying snapshot from bulk response');
                skipNextRefreshRef.current = true;
                applySnapshot(responseData.scores_snapshot);
                // Emit completion AFTER applying snapshot to avoid race condition
                emitMlPipelineCompleted({ message: 'Pipeline đã cập nhật lại dự đoán.' });
                // Don't call notifyScoresUpdated() - snapshot already applied, no need to trigger refetch
            } else {
                console.log('[StudyUpdate] No snapshot, fetching scores');
                await fetchScores();
                emitMlPipelineCompleted({ message: 'Pipeline đã cập nhật lại dự đoán.' });
                notifyScoresUpdated();
            }
        } catch (e) {
            setMessage({ type: 'error', text: 'Lỗi lưu dữ liệu: ' + e.message });
            emitMlPipelineCompleted({ error: e?.response?.data?.detail || e.message || 'Pipeline gặp lỗi khi đồng bộ.' });
        }
    };

    const handleDelete = async (item) => {
        if (!window.confirm(`Xóa điểm môn ${item.subject}?`)) return;
        try {
            await axiosClient.post('/study/scores/delete', {
                scores: [
                    {
                        subject: item.subject,
                        grade_level: item.grade_level,
                        semester: item.semester,
                    }
                ]
            });
            // Optimistic update
            setInputs(prev => ({ ...prev, [item.key]: '' }));
            await fetchScores();
            notifyScoresUpdated();
        } catch (e) {
            alert('Lỗi xóa: ' + e.message);
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

    if (loading) return <div style={{ display: 'flex', justifyContent: 'center', padding: '2rem', color: 'var(--text-secondary)' }}><span className="spinner"></span></div>;

    return (
        <div className="container" style={{ maxWidth: '1000px', paddingBottom: '3rem' }}>

            {/* Current Semester Selector */}
            <div className="card" style={{ marginBottom: '2rem', background: 'var(--primary-light)', border: '1px solid var(--primary-color)' }}>
                <h3 style={{ fontSize: '1.1rem', fontWeight: '600', marginBottom: '1rem', color: 'var(--primary-color)' }}>
                    🎓 Học kỳ hiện tại của bạn
                </h3>
                <div style={{ display: 'flex', gap: '1rem', alignItems: 'center' }}>
                    <select
                        className="input-field"
                        value={currentGrade}
                        onChange={(e) => setCurrentGrade(e.target.value)}
                        style={{ flex: 1, borderColor: 'var(--primary-color)' }}
                    >
                        <option value="">-- Chọn học kỳ --</option>
                        {gradeOptions.map(opt => (
                            <option key={opt.value} value={opt.value}>{opt.label}</option>
                        ))}
                    </select>
                    <button className="btn btn-primary" onClick={handleSaveGrade} style={{ whiteSpace: 'nowrap' }}>
                        <Save size={16} /> Lưu học kỳ
                    </button>
                </div>
                <p style={{ fontSize: '0.85rem', color: 'var(--text-secondary)', marginTop: '0.75rem', marginBottom: 0 }}>
                    💡 Học kỳ hiện tại giúp hệ thống lọc điểm và dự đoán chính xác hơn.
                </p>
            </div>

            <div className="card">
                {/* Legend: actual vs predicted */}
                <div style={{ display: 'flex', gap: '1.5rem', marginBottom: '1.5rem', alignItems: 'center', paddingBottom: '1rem', borderBottom: '1px solid var(--border-color)' }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                        <div style={{ width: '12px', height: '12px', background: 'var(--text-primary)', borderRadius: '3px' }} />
                        <div style={{ fontSize: '0.9rem', color: 'var(--text-primary)', fontWeight: '500' }}>Thực tế</div>
                    </div>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                        <div style={{ width: '12px', height: '12px', background: 'var(--text-tertiary)', borderRadius: '3px' }} />
                        <div style={{ fontSize: '0.9rem', color: 'var(--text-secondary)', fontWeight: '500' }}>Dự đoán (KNN)</div>
                    </div>
                </div>

                {['10', '11', '12'].map(grade => (
                    <div key={grade} style={{ marginBottom: '2.5rem' }}>
                        <h3 style={{
                            fontSize: '1.25rem',
                            fontWeight: '700',
                            color: 'var(--primary-color)',
                            borderBottom: '1px solid var(--border-color)',
                            paddingBottom: '0.75rem',
                            marginBottom: '1.5rem'
                        }}>
                            Lớp {grade}
                        </h3>

                        <div className="grid" style={{ gridTemplateColumns: 'repeat(auto-fit, minmax(350px, 1fr))', gap: '2rem' }}>
                            {['1', '2'].map(sem => {
                                const semScores = scores.filter(s => s.grade_level === grade && s.semester === sem);
                                if (semScores.length === 0) return null;

                                return (
                                    <div key={sem}>
                                        <h4 style={{ fontWeight: '600', marginBottom: '1rem', color: 'var(--text-secondary)' }}>Học kỳ {sem}</h4>
                                        <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
                                            {semScores.map(item => {
                                                // compute recIdx for this item
                                                let recIdx = null;
                                                const ordered = [];
                                                ['10', '11', '12'].forEach(g => ['1', '2'].forEach(s => ordered.push({ g, s })));
                                                for (let i = 0; i < ordered.length; i++) {
                                                    if (ordered[i].g === item.grade_level && ordered[i].s === item.semester) { recIdx = i; break; }
                                                }
                                                const disabledInput = (activeIdx !== null && recIdx !== null && recIdx > activeIdx);
                                                return (
                                                    <div key={item.key} style={{ display: 'flex', alignItems: 'center', gap: '1rem', opacity: disabledInput ? 0.6 : 1 }}>
                                                        <label style={{ width: '140px', fontSize: '0.9rem', color: 'var(--text-primary)' }}>{item.subject_display || item.subject}</label>
                                                        <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                                                            <input
                                                                className="input-field"
                                                                style={{ padding: '0.4rem 0.75rem', width: '90px', textAlign: 'center' }}
                                                                value={inputs[item.key] || ''}
                                                                placeholder={item.predicted ? `${item.predicted}` : '-'}
                                                                onChange={(e) => handleChange(item.key, e.target.value)}
                                                                disabled={disabledInput}
                                                            />
                                                            {/* If there is no actual score but there is a predicted score, show a badge */}
                                                            {item.actual == null && item.predicted != null && (
                                                                <div style={{ fontSize: '0.75rem', color: 'var(--text-secondary)', padding: '2px 8px', borderRadius: '12px', background: 'var(--secondary-light)', border: '1px solid var(--border-color)' }}>
                                                                    Dự đoán
                                                                </div>
                                                            )}
                                                        </div>
                                                        {item.actual !== null && (
                                                            <button
                                                                onClick={() => handleDelete(item)}
                                                                className="btn btn-ghost"
                                                                style={{ padding: '0.4rem', color: 'var(--text-tertiary)' }}
                                                                title="Xóa điểm này"
                                                            >
                                                                <Trash2 size={16} />
                                                            </button>
                                                        )}
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
                {/* Save button moved to bottom */}
                <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem', marginTop: '2rem', paddingTop: '1.5rem', borderTop: '1px solid var(--border-color)' }}>
                    <div style={{ display: 'flex', justifyContent: 'flex-end' }}>
                        <button className="btn btn-primary" onClick={handleSave}>
                            <Save size={18} /> Lưu điểm số
                        </button>
                    </div>
                    {pipelineBanner.text && (
                        <div style={{
                            padding: '1rem',
                            borderRadius: 'var(--radius-md)',
                            background: pipelineBanner.type === 'error' ? '#fef2f2' : pipelineBanner.type === 'success' ? '#f0fdf4' : '#fefce8',
                            color: pipelineBanner.type === 'error' ? 'var(--danger-color)' : pipelineBanner.type === 'success' ? '#166534' : '#854d0e',
                            border: `1px solid ${pipelineBanner.type === 'error' ? '#fecaca' : pipelineBanner.type === 'success' ? '#bbf7d0' : '#fef08a'}`
                        }}>
                            {pipelineBanner.text}
                        </div>
                    )}
                    {message.text && (
                        <div style={{
                            padding: '1rem',
                            borderRadius: 'var(--radius-md)',
                            background: message.type === 'error' ? '#fef2f2' : message.type === 'success' ? '#f0fdf4' : 'var(--primary-light)',
                            color: message.type === 'error' ? 'var(--danger-color)' : message.type === 'success' ? '#166534' : 'var(--primary-color)',
                            border: `1px solid ${message.type === 'error' ? '#fecaca' : message.type === 'success' ? '#bbf7d0' : 'var(--primary-light)'}`
                        }}>
                            {message.text}
                        </div>
                    )}
                </div>
            </div>
        </div>
    );
};

export default StudyUpdate;

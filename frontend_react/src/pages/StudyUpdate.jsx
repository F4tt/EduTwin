import React, { useState, useEffect, useCallback, useRef, useMemo } from 'react';
import * as XLSX from 'xlsx';
import axiosClient from '../api/axiosClient';
import { Save, Trash2, Download, Upload, FileText, X } from 'lucide-react';
import { useAuth } from '../context/AuthContext';
import { getScaleMin, getScaleMax, getScaleStep, isValidScore, formatScore } from '../utils/scaleUtils';
import { translateError, formatPipelineError } from '../utils/errorMessages';
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
    const [currentGrade, setCurrentGrade] = useState('');
    const [savedCurrentGrade, setSavedCurrentGrade] = useState(''); // Saved value from DB
    const skipNextRefreshRef = useRef(false);
    const [uploadFile, setUploadFile] = useState(null);
    const [uploading, setUploading] = useState(false);

    // Active structure state
    const [activeStructure, setActiveStructure] = useState(null);
    const [loadingStructure, setLoadingStructure] = useState(true);

    // Fetch active structure
    const fetchActiveStructure = useCallback(async () => {
        try {
            setLoadingStructure(true);
            console.log('[StudyUpdate] Fetching active structure...');
            const res = await axiosClient.get('/custom-model/get-active-structure');
            console.log('[StudyUpdate] Active structure response:', res.data);

            if (res.data.has_structure) {
                const structureData = {
                    id: res.data.structure_id,
                    name: res.data.structure_name,
                    timePoints: res.data.time_point_labels || [],
                    subjects: res.data.subject_labels || [],
                    scaleType: res.data.scale_type || '0-10'
                };
                console.log('[StudyUpdate] Setting activeStructure:', structureData);
                setActiveStructure(structureData);

                // Fetch current_timepoint for this structure
                try {
                    const timepointRes = await axiosClient.get(`/user/current-timepoint/${structureData.id}`);
                    const currentTimepoint = timepointRes.data.current_timepoint;
                    if (currentTimepoint && structureData.timePoints.includes(currentTimepoint)) {
                        console.log('[StudyUpdate] Setting currentGrade from structure preference:', currentTimepoint);
                        setCurrentGrade(currentTimepoint);
                        setSavedCurrentGrade(currentTimepoint);
                    } else {
                        console.log('[StudyUpdate] No valid current_timepoint for this structure');
                        setCurrentGrade('');
                        setSavedCurrentGrade('');
                    }
                } catch (timepointErr) {
                    console.error('[StudyUpdate] Error fetching current timepoint:', timepointErr);
                    setCurrentGrade('');
                    setSavedCurrentGrade('');
                }
            } else {
                console.log('[StudyUpdate] No active structure found');
                setActiveStructure(null);
                setCurrentGrade('');
                setSavedCurrentGrade('');
            }
        } catch (e) {
            console.error('[StudyUpdate] Error fetching active structure:', e);
            setActiveStructure(null);
        } finally {
            setLoadingStructure(false);
        }
    }, []);

    useEffect(() => {
        fetchActiveStructure();
    }, [fetchActiveStructure]);

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
            const newGrade = payload.current_grade || '';
            setCurrentGrade(newGrade);
            setSavedCurrentGrade(newGrade); // Also update saved value
            console.log('[StudyUpdate] Updated currentGrade to:', newGrade);
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

            console.log('[fetchScores] Starting fetch, activeStructure:', activeStructure?.id);

            // Wait for structure to load first
            if (loadingStructure) {
                console.log('[fetchScores] Waiting for structure to load...');
                return;
            }

            // If no active structure, don't fetch - UI will show empty state
            if (!activeStructure?.id) {
                console.log('[fetchScores] No active structure, skipping fetch');
                setScores([]);
                setInputs({});
                if (!silent) {
                    setLoading(false);
                }
                return;
            }

            // Use custom structure API
            console.log('[fetchScores] Loading scores for structure:', activeStructure.id);
            const res = await axiosClient.get(`/custom-model/user-scores/${activeStructure.id}`);
            const scoreData = res.data.scores || {};

            console.log('[fetchScores] Received score data:', scoreData);
            console.log('[fetchScores] Number of entries:', Object.keys(scoreData).length);

            // Transform to scores array format: [{key, subject, actual, predicted, ...}]
            const transformedScores = [];
            activeStructure.subjects.forEach(subject => {
                activeStructure.timePoints.forEach(timePoint => {
                    const key = `${subject}_${timePoint}`;
                    const scoreInfo = scoreData[key] || {};
                    transformedScores.push({
                        key,
                        subject,
                        subject_display: subject,
                        time_point: timePoint,
                        actual: scoreInfo.actual_score !== undefined && scoreInfo.actual_score !== null ? scoreInfo.actual_score : null,
                        predicted: scoreInfo.predicted_score !== undefined && scoreInfo.predicted_score !== null ? scoreInfo.predicted_score : null,
                    });
                });
            });

            console.log('[fetchScores] Transformed scores:', transformedScores.filter(s => s.actual !== null || s.predicted !== null));

            setScores(transformedScores);

            // Initialize inputs with actual values
            const initialInputs = {};
            transformedScores.forEach(item => {
                if (item.actual !== null && item.actual !== undefined) {
                    initialInputs[item.key] = String(item.actual);
                }
            });
            console.log('[fetchScores] Setting inputs with', Object.keys(initialInputs).length, 'actual scores');
            setInputs(initialInputs);
        } catch (e) {
            console.error('[fetchScores] Error:', e);
        } finally {
            if (!silent) {
                setLoading(false);
            }
        }
    }, [activeStructure, loadingStructure]);

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
                setPipelineBanner({ type: 'error', text: formatPipelineError(detail.error) });
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

    // Kiểm tra xem một input có phải giá trị chưa lưu không
    const isUnsavedInput = (key, currentValue) => {
        const score = scores.find(s => s.key === key);
        if (!score) return false;

        const inputVal = String(currentValue || '').trim();
        if (!inputVal) return false;

        const parsedVal = parseFloat(inputVal.replace(',', '.'));
        if (isNaN(parsedVal)) return false;

        return parsedVal !== score.actual;
    };

    const handleSaveGrade = async () => {
        if (!currentGrade) {
            setMessage({ type: 'error', text: activeStructure ? 'Vui lòng chọn mốc thời gian hiện tại.' : 'Vui lòng chọn học kỳ hiện tại.' });
            return;
        }

        try {
            // Check if currentGrade is changing backwards (to earlier timepoint)
            const isMovingBackwards = savedCurrentGrade && currentGrade !== savedCurrentGrade;

            if (isMovingBackwards && activeStructure) {
                const currentIndex = activeStructure.timePoints.indexOf(currentGrade);
                const savedIndex = activeStructure.timePoints.indexOf(savedCurrentGrade);

                if (currentIndex !== -1 && savedIndex !== -1 && currentIndex < savedIndex) {
                    console.log('[StudyUpdate] Moving backwards from', savedCurrentGrade, 'to', currentGrade);
                    console.log('[StudyUpdate] Will clear actual scores after index', currentIndex);

                    // Get timepoints after current
                    const futureTimePoints = activeStructure.timePoints.slice(currentIndex + 1);
                    console.log('[StudyUpdate] Future timepoints to clear:', futureTimePoints);

                    // Clear actual scores for future timepoints
                    const clearUpdates = {};
                    activeStructure.subjects.forEach(subject => {
                        futureTimePoints.forEach(tp => {
                            const key = `${subject}_${tp}`;
                            clearUpdates[key] = null; // Set to null to clear
                        });
                    });

                    console.log('[StudyUpdate] Clearing scores for', Object.keys(clearUpdates).length, 'entries');

                    // Send clear request
                    await axiosClient.post('/custom-model/user-scores', {
                        structure_id: activeStructure.id,
                        scores: clearUpdates
                    });
                    console.log('[StudyUpdate] Scores cleared successfully');
                }
            }

            // Save currentGrade to structure preferences
            if (activeStructure?.id) {
                await axiosClient.post('/user/current-timepoint', {
                    structure_id: activeStructure.id,
                    current_timepoint: currentGrade
                });
                console.log('[StudyUpdate] Saved current_timepoint:', currentGrade);
            }
            setSavedCurrentGrade(currentGrade); // Update saved value

            // Trigger ML pipeline if we have the structure
            if (activeStructure?.id) {
                console.log('[StudyUpdate] Triggering ML pipeline for structure', activeStructure.id);
                emitMlPipelineProcessing();
                setPipelineBanner({ type: 'info', text: '⚙️ Đang chạy pipeline ML để dự đoán điểm...' });

                try {
                    await axiosClient.post(`/custom-model/trigger-pipeline/${activeStructure.id}`);
                    console.log('[StudyUpdate] ML pipeline completed');
                    setPipelineBanner({ type: 'success', text: '✓ Pipeline ML hoàn thành! Đã dự đoán các điểm tương lai.' });
                    emitMlPipelineCompleted();

                    // Auto-hide success message
                    if (pipelineTimeoutRef.current) {
                        clearTimeout(pipelineTimeoutRef.current);
                    }
                    pipelineTimeoutRef.current = setTimeout(() => {
                        setPipelineBanner({ type: '', text: '' });
                    }, 5000);
                } catch (pipelineErr) {
                    console.error('[StudyUpdate] Pipeline error:', pipelineErr);
                    setPipelineBanner({ type: 'error', text: '⚠️ ' + formatPipelineError(pipelineErr.response?.data?.detail || pipelineErr.message) });
                }
            }

            setMessage({ type: 'success', text: 'Đã lưu mốc thời gian hiện tại!' });
            setTimeout(() => setMessage({ type: '', text: '' }), 3000);
            await fetchScores(); // Refresh scores
            notifyScoresUpdated();
        } catch (e) {
            console.error('[StudyUpdate] Error in handleSaveGrade:', e);
            setMessage({ type: 'error', text: translateError(e.response?.data?.detail || e.message) });
        }
    };

    const handleSave = async () => {
        setMessage({ type: '', text: '' });

        // Custom structure save logic
        const updates = {};
        let hasError = false;
        let hasChanges = false;

        const scaleMin = getScaleMin(activeStructure?.scaleType || '0-10');
        const scaleMax = getScaleMax(activeStructure?.scaleType || '0-10');

        scores.forEach(item => {
            const rawVal = String(inputs[item.key] || '').trim();

            // Skip if empty
            if (!rawVal) return;

            const val = parseFloat(rawVal.replace(',', '.'));
            if (isNaN(val) || !isValidScore(val, activeStructure?.scaleType || '0-10')) {
                hasError = true;
                return;
            }

            // Only update if changed
            if (val !== item.actual) {
                updates[item.key] = val;
                hasChanges = true;
            }
        });

        if (hasError) {
            setMessage({ type: 'error', text: `Điểm số phải từ ${scaleMin} đến ${scaleMax}.` });
            return;
        }

        if (!hasChanges) {
            setMessage({ type: 'info', text: 'Không có thay đổi nào.' });
            return;
        }

        try {
            emitMlPipelineProcessing({ message: 'Đang đồng bộ pipeline với điểm mới của bạn...' });

            console.log('[handleSave] Sending updates:', updates);
            console.log('[handleSave] Keys:', Object.keys(updates));

            const res = await axiosClient.post('/custom-model/user-scores', {
                structure_id: activeStructure.id,
                scores: updates
            });

            console.log('[handleSave] Save response:', res.data);

            setMessage({ type: 'success', text: res.data.message || 'Đã lưu thành công!' });

            // Refresh scores to get predictions
            console.log('[handleSave] Fetching updated scores...');
            await fetchScores();
            console.log('[handleSave] Scores refreshed');

            emitMlPipelineCompleted({ message: 'Pipeline đã cập nhật lại dự đoán.' });
            notifyScoresUpdated();
        } catch (e) {
            console.error('[handleSave] Error:', e);
            setMessage({ type: 'error', text: translateError(e.response?.data?.detail || e.message) });
            emitMlPipelineCompleted({ error: translateError(e?.response?.data?.detail || e.message || 'Hệ thống gặp lỗi khi đồng bộ.') });
        }
    };

    const handleDelete = async (item) => {
        if (!window.confirm(`Xóa điểm môn ${item.subject}?`)) return;
        try {
            // Delete by setting score to empty string
            await axiosClient.post('/custom-model/user-scores', {
                structure_id: activeStructure.id,
                scores: { [item.key]: "" }
            });
            // Optimistic update
            setInputs(prev => ({ ...prev, [item.key]: '' }));
            await fetchScores();
            notifyScoresUpdated();
        } catch (e) {
            alert('❌ Không thể xóa. Vui lòng thử lại sau.');
        }
    };

    const handleDownloadTemplate = () => {
        // Custom structure: matrix format (subjects as rows, timepoints as columns)
        const headers = ['Môn học', ...activeStructure.timePoints];
        const rows = activeStructure.subjects.map(subject => {
            const row = [subject];
            activeStructure.timePoints.forEach(timePoint => {
                const key = `${subject}_${timePoint}`;
                row.push(inputs[key] || '');
            });
            return row;
        });

        const ws = XLSX.utils.aoa_to_sheet([headers, ...rows]);
        const wb = XLSX.utils.book_new();
        XLSX.utils.book_append_sheet(wb, ws, 'Scores');
        XLSX.writeFile(wb, `${activeStructure.name}_scores.xlsx`);
    };

    const handleFileUpload = async () => {
        if (!uploadFile) {
            setMessage({ type: 'error', text: 'Vui lòng chọn file trước.' });
            return;
        }

        setUploading(true);
        setMessage({ type: '', text: '' });

        try {
            // Parse matrix format
            const data = await uploadFile.arrayBuffer();
            const workbook = XLSX.read(data, { type: 'array' });
            const sheetName = workbook.SheetNames[0];
            const worksheet = workbook.Sheets[sheetName];
            const jsonData = XLSX.utils.sheet_to_json(worksheet, { header: 1 });

            if (jsonData.length < 2) {
                setMessage({ type: 'error', text: 'File không có dữ liệu.' });
                setUploading(false);
                return;
            }

            const headers = jsonData[0];
            const newInputs = { ...inputs }; // Keep existing inputs
            let updated = 0;

            // Determine which timepoints are enabled based on saved current grade
            const savedTimePointIdx = activeStructure.timePoints.indexOf(savedCurrentGrade);

            // Parse rows (skip header)
            for (let i = 1; i < jsonData.length; i++) {
                const row = jsonData[i];
                const subject = row[0];

                if (!subject) continue;

                // Parse each timepoint column
                for (let j = 1; j < headers.length; j++) {
                    const timePoint = headers[j];
                    const tpIdx = activeStructure.timePoints.indexOf(timePoint);

                    // Skip disabled timepoints (beyond saved current grade)
                    if (savedTimePointIdx >= 0 && tpIdx > savedTimePointIdx) {
                        continue;
                    }

                    const scoreValue = row[j];

                    if (scoreValue !== undefined && scoreValue !== null && scoreValue !== '') {
                        const key = `${subject}_${timePoint}`;
                        const parsedScore = parseFloat(String(scoreValue).replace(',', '.'));
                        if (!isNaN(parsedScore)) {
                            newInputs[key] = String(parsedScore);
                            updated++;
                        }
                    }
                }
            }

            if (updated === 0) {
                setMessage({ type: 'error', text: 'Không tìm thấy điểm hợp lệ trong file.' });
                setUploading(false);
                return;
            }

            // Update inputs state to show in UI (NOT saved to backend yet)
            setInputs(newInputs);
            setUploadFile(null);
            setMessage({ type: 'success', text: `Đã tải lên ${updated} điểm từ file. Nhấn "Lưu điểm số" để cập nhật.` });
        } catch (e) {
            console.error('[Upload Error]', e);
            setMessage({ type: 'error', text: translateError(e.response?.data?.detail || e.message) });
        } finally {
            setUploading(false);
        }
    };

    // Show loading spinner while fetching structure or data
    if (loading || loadingStructure) {
        return <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', flexDirection: 'column', padding: '2rem', color: 'var(--text-secondary)' }}>
            <span className="spinner"></span>
            <p style={{ marginTop: '1rem' }}>Đang tải dữ liệu...</p>
        </div>;
    }

    // Show message if no active structure
    if (!activeStructure) {
        return (
            <div className="container" style={{ maxWidth: '1000px', paddingBottom: '3rem' }}>
                <div className="card" style={{
                    padding: '3rem 2rem',
                    textAlign: 'center',
                    background: 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)',
                    color: 'white',
                    borderRadius: '12px'
                }}>
                    <h2 style={{ fontSize: '1.5rem', fontWeight: '600', marginBottom: '1rem', color: 'white' }}>
                        Chưa thiết lập cấu trúc học tập
                    </h2>
                    <p style={{ fontSize: '1rem', opacity: 0.95, maxWidth: '600px', margin: '0 auto', lineHeight: 1.6 }}>
                        Vui lòng tạo và kích hoạt một cấu trúc học tập tùy chỉnh để xem trực quan hóa dữ liệu.
                    </p>
                </div>
            </div>
        );
    }

    const gradeOptions = activeStructure.timePoints.map(tp => ({ value: tp, label: tp }));

    return (
        <div className="container" style={{ maxWidth: '1000px', paddingBottom: '3rem' }}>

            {/* Current Semester Selector */}
            <div className="card" style={{ marginBottom: '2rem', background: 'var(--primary-light)', border: '1px solid var(--primary-color)' }}>
                <h3 style={{ fontSize: '1.1rem', fontWeight: '600', marginBottom: '1rem', color: 'var(--primary-color)' }}>
                    🎓 Mốc thời gian hiện tại
                </h3>
                <div style={{ display: 'flex', gap: '1rem', alignItems: 'center' }}>
                    <select
                        className="input-field"
                        value={currentGrade}
                        onChange={(e) => setCurrentGrade(e.target.value)}
                        style={{ flex: 1, borderColor: 'var(--primary-color)' }}
                    >
                        <option value="">-- Chọn mốc thời gian --</option>
                        {gradeOptions.map(opt => (
                            <option key={opt.value} value={opt.value}>{opt.label}</option>
                        ))}
                    </select>
                    <button className="btn btn-primary" onClick={handleSaveGrade} style={{ whiteSpace: 'nowrap' }}>
                        <Save size={16} /> Lưu mốc thời gian
                    </button>
                </div>
                <p style={{ fontSize: '0.85rem', color: 'var(--text-secondary)', marginTop: '0.75rem', marginBottom: 0 }}>
                    💡 Mốc thời gian hiện tại giúp hệ thống lọc điểm và dự đoán chính xác hơn.
                </p>
            </div>

            {/* Upload Section */}
            <div className="card" style={{
                marginBottom: '2rem',
                border: '1px solid var(--border-color)',
                overflow: 'hidden',
                padding: 0,
                opacity: !savedCurrentGrade ? 0.5 : 1,
                pointerEvents: !savedCurrentGrade ? 'none' : 'auto'
            }}>
                {!savedCurrentGrade && (
                    <div style={{
                        position: 'absolute',
                        top: 0,
                        left: 0,
                        right: 0,
                        bottom: 0,
                        background: 'rgba(255, 255, 255, 0.7)',
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'center',
                        zIndex: 10,
                        borderRadius: 'var(--radius-md)'
                    }}>
                        <div style={{
                            background: 'white',
                            padding: '1.5rem 2rem',
                            borderRadius: 'var(--radius-md)',
                            boxShadow: '0 4px 6px -1px rgba(0, 0, 0, 0.1)',
                            textAlign: 'center',
                            border: '2px solid var(--primary-color)'
                        }}>
                            <p style={{ margin: 0, fontWeight: '600', color: 'var(--primary-color)' }}>
                                ⚠️ Vui lòng chọn và lưu mốc thời gian trước
                            </p>
                        </div>
                    </div>
                )}
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
                            <h3 style={{ fontSize: '1rem', fontWeight: '600', margin: 0, color: 'var(--text-primary)' }}>Tải lên file để cập nhật điểm</h3>
                            <p style={{ fontSize: '0.85rem', color: 'var(--text-secondary)', margin: 0 }}>Cập nhật điểm nhanh chóng từ file Excel (xlsx, xls)</p>
                        </div>
                    </div>
                    <button
                        onClick={handleDownloadTemplate}
                        className="btn btn-ghost"
                        style={{ fontSize: '0.85rem', gap: '0.5rem', color: 'var(--primary-color)', fontWeight: '500' }}
                        title="Tải file mẫu chứa dữ liệu hiện tại"
                    >
                        <Download size={16} /> Tải xuống dữ liệu hiện tại
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
                                id="score-upload-input-update"
                            />
                            <label
                                htmlFor="score-upload-input-update"
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
                                        Hỗ trợ định dạng .xlsx/.xls
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
                                    disabled={uploading || (!currentGrade && !activeStructure)}
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

            <div className="card" style={{
                position: 'relative',
                opacity: !savedCurrentGrade ? 0.5 : 1,
                pointerEvents: !savedCurrentGrade ? 'none' : 'auto'
            }}>
                {!savedCurrentGrade && (
                    <div style={{
                        position: 'absolute',
                        top: 0,
                        left: 0,
                        right: 0,
                        bottom: 0,
                        background: 'rgba(255, 255, 255, 0.7)',
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'center',
                        zIndex: 10,
                        borderRadius: 'var(--radius-md)'
                    }}>
                        <div style={{
                            background: 'white',
                            padding: '1.5rem 2rem',
                            borderRadius: 'var(--radius-md)',
                            boxShadow: '0 4px 6px -1px rgba(0, 0, 0, 0.1)',
                            textAlign: 'center',
                            border: '2px solid var(--primary-color)'
                        }}>
                            <p style={{ margin: 0, fontWeight: '600', color: 'var(--primary-color)' }}>
                                ⚠️ Vui lòng chọn và lưu mốc thời gian trước
                            </p>
                        </div>
                    </div>
                )}
                {/* Legend: actual vs predicted */}
                <div style={{ display: 'flex', gap: '1.5rem', marginBottom: '1.5rem', alignItems: 'center', paddingBottom: '1rem', borderBottom: '1px solid var(--border-color)' }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                        <div style={{ width: '12px', height: '12px', background: 'var(--text-primary)', borderRadius: '3px' }} />
                        <div style={{ fontSize: '0.9rem', color: 'var(--text-primary)', fontWeight: '500' }}>Thực tế</div>
                    </div>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                        <div style={{ width: '12px', height: '12px', background: 'var(--text-tertiary)', borderRadius: '3px' }} />
                        <div style={{ fontSize: '0.9rem', color: 'var(--text-secondary)', fontWeight: '500' }}>Dự đoán</div>
                    </div>
                </div>

                {loadingStructure ? (
                    <div style={{ textAlign: 'center', padding: '3rem', color: 'var(--text-secondary)' }}>
                        Đang tải cấu trúc...
                    </div>
                ) : !activeStructure ? (
                    <div style={{ textAlign: 'center', padding: '3rem' }}>
                        <p style={{ fontSize: '1.1rem', color: 'var(--text-secondary)', marginBottom: '0.5rem' }}>
                            Chưa có cấu trúc học tập nào được kích hoạt
                        </p>
                        <p style={{ fontSize: '0.9rem', color: 'var(--text-tertiary)' }}>
                            Vui lòng liên hệ quản trị viên để kích hoạt cấu trúc học tập
                        </p>
                    </div>
                ) : (
                    <>
                        {/* Compact Table Layout */}
                        <div style={{ overflowX: 'auto' }}>
                            <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.9rem' }}>
                                <thead>
                                    <tr style={{ borderBottom: '2px solid var(--border-color)' }}>
                                        <th style={{ padding: '0.75rem', textAlign: 'left', fontWeight: '600', color: 'var(--text-primary)', position: 'sticky', left: 0, background: 'var(--bg-surface)', zIndex: 1 }}>Môn học</th>
                                        {activeStructure.timePoints.map((timePoint) => (
                                            <th key={timePoint} style={{ padding: '0.75rem', textAlign: 'center', fontWeight: '600', color: 'var(--primary-color)', minWidth: '100px' }}>
                                                {timePoint}
                                            </th>
                                        ))}
                                        <th style={{ padding: '0.75rem', width: '60px' }}></th>
                                    </tr>
                                </thead>
                                <tbody>
                                    {activeStructure.subjects.map((subject) => {
                                        const savedTimePointIdx = activeStructure.timePoints.indexOf(savedCurrentGrade);

                                        return (
                                            <tr key={subject} style={{ borderBottom: '1px solid var(--border-color)' }}>
                                                <td style={{ padding: '0.5rem 0.75rem', fontWeight: '500', color: 'var(--text-primary)', position: 'sticky', left: 0, background: 'var(--bg-surface)', zIndex: 1 }}>
                                                    {subject}
                                                </td>
                                                {activeStructure.timePoints.map((timePoint, tpIdx) => {
                                                    const key = `${subject}_${timePoint}`;
                                                    const scoreItem = scores.find(s => s.key === key);
                                                    const disabledInput = savedTimePointIdx >= 0 && tpIdx > savedTimePointIdx;
                                                    const hasActual = scoreItem?.actual !== null && scoreItem?.actual !== undefined;
                                                    const hasPredicted = scoreItem?.predicted !== null && scoreItem?.predicted !== undefined;
                                                    const scaleType = activeStructure?.scaleType || '0-10';

                                                    return (
                                                        <td key={timePoint} style={{ padding: '0.5rem', textAlign: 'center' }}>
                                                            <div style={{ position: 'relative', display: 'inline-block' }}>
                                                                <input
                                                                    type="number"
                                                                    step={getScaleStep(scaleType)}
                                                                    min={getScaleMin(scaleType)}
                                                                    max={getScaleMax(scaleType)}
                                                                    className="input-field"
                                                                    style={{
                                                                        padding: '0.4rem 0.5rem',
                                                                        width: '70px',
                                                                        textAlign: 'center',
                                                                        fontSize: '0.9rem',
                                                                        borderColor: isUnsavedInput(key, inputs[key]) ? '#dc2626' : 'var(--border-color)',
                                                                        borderWidth: isUnsavedInput(key, inputs[key]) ? '2px' : '1px',
                                                                        backgroundColor: isUnsavedInput(key, inputs[key]) ? '#fef2f2' : 'transparent',
                                                                        color: hasActual || inputs[key] ? '#16a34a' : 'var(--text-tertiary)',
                                                                        fontWeight: hasActual || inputs[key] ? '600' : '400',
                                                                        opacity: disabledInput ? 0.5 : 1,
                                                                        cursor: disabledInput ? 'not-allowed' : 'text'
                                                                    }}
                                                                    value={inputs[key] || ''}
                                                                    placeholder={hasPredicted ? formatScore(scoreItem.predicted, scaleType) : ''}
                                                                    onChange={(e) => handleChange(key, e.target.value)}
                                                                    disabled={disabledInput}
                                                                    title={hasActual ? `Điểm thực tế: ${formatScore(scoreItem.actual, scaleType)}` : hasPredicted ? `Dự đoán: ${formatScore(scoreItem.predicted, scaleType)}` : ''}
                                                                />
                                                                {!hasActual && hasPredicted && !inputs[key] && (
                                                                    <div style={{
                                                                        position: 'absolute',
                                                                        top: '-8px',
                                                                        right: '-8px',
                                                                        fontSize: '0.65rem',
                                                                        color: '#6b7280',
                                                                        background: '#f3f4f6',
                                                                        padding: '2px 5px',
                                                                        borderRadius: '8px',
                                                                        border: '1px solid #e5e7eb',
                                                                        whiteSpace: 'nowrap'
                                                                    }}>
                                                                        AI
                                                                    </div>
                                                                )}
                                                            </div>
                                                        </td>
                                                    );
                                                })}
                                                <td style={{ padding: '0.5rem', textAlign: 'center' }}>
                                                    {/* Show delete if has actual score in any timepoint */}
                                                    {activeStructure.timePoints.some(tp => {
                                                        const k = `${subject}_${tp}`;
                                                        const item = scores.find(s => s.key === k);
                                                        return item?.actual !== null;
                                                    }) && (
                                                            <button
                                                                onClick={async () => {
                                                                    if (window.confirm(`Xóa tất cả điểm môn ${subject}?`)) {
                                                                        const deleteKeys = {};
                                                                        activeStructure.timePoints.forEach(tp => {
                                                                            const k = `${subject}_${tp}`;
                                                                            const item = scores.find(s => s.key === k);
                                                                            if (item?.actual !== null) {
                                                                                deleteKeys[k] = "";
                                                                            }
                                                                        });

                                                                        if (Object.keys(deleteKeys).length > 0) {
                                                                            try {
                                                                                await axiosClient.post('/custom-model/user-scores', {
                                                                                    structure_id: activeStructure.id,
                                                                                    scores: deleteKeys
                                                                                });
                                                                                await fetchScores();
                                                                                notifyScoresUpdated();
                                                                            } catch (e) {
                                                                                alert('❌ Không thể xóa. Vui lòng thử lại sau.');
                                                                            }
                                                                        }
                                                                    }
                                                                }}
                                                                className="btn btn-ghost"
                                                                style={{ padding: '0.3rem', color: 'var(--text-tertiary)', fontSize: '0.85rem' }}
                                                                title="Xóa tất cả điểm môn này"
                                                            >
                                                                <Trash2 size={14} />
                                                            </button>
                                                        )}
                                                </td>
                                            </tr>
                                        );
                                    })}
                                </tbody>
                            </table>
                        </div>
                    </>
                )}
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

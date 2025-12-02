import React, { useState, useEffect, useRef } from 'react';
import { useAuth } from '../context/AuthContext';
import axiosClient from '../api/axiosClient';
import { Upload, RefreshCw, AlertCircle, Brain, Database, Clock, FileText, Zap, CheckCircle, Settings, Lightbulb, Save, Power } from 'lucide-react';
import { motion } from 'framer-motion';

const InstitutionAdminTools = () => {
    const { user } = useAuth();
    const [file, setFile] = useState(null);
    const [uploading, setUploading] = useState(false);
    const [message, setMessage] = useState({ type: '', text: '' });
    const [summary, setSummary] = useState(null);

    // Model evaluation state
    const [evaluating, setEvaluating] = useState(false);
    const [evaluationResults, setEvaluationResults] = useState(null);
    const [evaluationMessage, setEvaluationMessage] = useState('');

    // Model parameters state
    const [parameters, setParameters] = useState({ knn_n: 15, kr_bandwidth: 1.25, lwlr_tau: 3.0 });
    const [loadingParams, setLoadingParams] = useState(false);
    const [savingParams, setSavingParams] = useState(false);
    const [paramMessage, setParamMessage] = useState('');

    // ML Model selection state
    const [modelStatus, setModelStatus] = useState(null);
    const [selectedModel, setSelectedModel] = useState('');
    const [modelMsg, setModelMsg] = useState('');
    const [loadingModels, setLoadingModels] = useState(false);

    // Dataset status state
    const [datasetStatus, setDatasetStatus] = useState(null);
    const [loadingDataset, setLoadingDataset] = useState(false);

    // Teaching structure state
    const [numTimePoints, setNumTimePoints] = useState('');
    const [numSubjects, setNumSubjects] = useState('');
    const [structureConfirmed, setStructureConfirmed] = useState(false);
    const [timePointLabels, setTimePointLabels] = useState([]);
    const [subjectLabels, setSubjectLabels] = useState([]);
    const [savingStructure, setSavingStructure] = useState(false);
    const [structureMessage, setStructureMessage] = useState('');

    // Pipeline toggle state
    const [pipelineEnabled, setPipelineEnabled] = useState(true);
    const [togglingPipeline, setTogglingPipeline] = useState(false);

    // Pipeline status banner
    const [pipelineBanner, setPipelineBanner] = useState({ type: '', text: '' });
    const pipelineTimeoutRef = useRef(null);

    const clearPipelineTimer = () => {
        if (pipelineTimeoutRef.current) {
            clearTimeout(pipelineTimeoutRef.current);
            pipelineTimeoutRef.current = null;
        }
    };

    const notifyPipelineProcessing = (detail = {}) => {
        clearPipelineTimer();
        const text = detail.message || 'Đang cập nhật pipeline...';
        setPipelineBanner({ type: 'info', text });
    };

    const notifyPipelineCompleted = (detail = {}) => {
        clearPipelineTimer();
        if (detail.error) {
            const errorText = detail.error;
            setPipelineBanner({ type: 'error', text: errorText });
        } else {
            const stats = detail.stats || detail.pipeline || {};
            const processed = stats.processed_users ? ` (${stats.processed_users} người dùng)` : '';
            const successText = detail.message || `Pipeline đã hoàn tất${processed}.`;
            setPipelineBanner({ type: 'success', text: successText });
        }
        pipelineTimeoutRef.current = setTimeout(() => setPipelineBanner({ type: '', text: '' }), 5000);
    };

    useEffect(() => {
        return () => clearPipelineTimer();
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, []);

    // Fetch model status and dataset status on mount
    useEffect(() => {
        fetchModelStatus();
        fetchDatasetStatus();
        fetchModelParameters();
        fetchTeachingStructure();
        fetchPipelineStatus();
    }, []);

    const fetchModelStatus = async () => {
        setLoadingModels(true);
        try {
            const res = await axiosClient.get('/developer/model-status');
            setModelStatus(res.data);
            setSelectedModel(res.data.active_model);
        } catch (e) {
            console.error('Error fetching model status:', e);
            setModelMsg('Lỗi: ' + (e.response?.data?.detail || e.message));
            setModelStatus({ error: e.response?.data?.detail || e.message || 'Không thể tải trạng thái mô hình' });
        } finally {
            setLoadingModels(false);
        }
    };

    const fetchDatasetStatus = async () => {
        setLoadingDataset(true);
        try {
            const res = await axiosClient.get('/developer/dataset-status');
            setDatasetStatus(res.data);
        } catch (e) {
            console.error('Error fetching dataset status:', e);
            setDatasetStatus({ error: e.response?.data?.detail || e.message || 'Không thể tải trạng thái dataset' });
        } finally {
            setLoadingDataset(false);
        }
    };

    const fetchModelParameters = async () => {
        setLoadingParams(true);
        try {
            const res = await axiosClient.get('/developer/model-parameters');
            setParameters(res.data);
        } catch (e) {
            console.error('Error fetching model parameters:', e);
        } finally {
            setLoadingParams(false);
        }
    };

    const handleSaveParameters = async () => {
        setSavingParams(true);
        setParamMessage('');
        notifyPipelineProcessing({ reason: 'model-parameters', message: 'Đang áp dụng thông số mới và cập nhật pipeline...' });

        try {
            const res = await axiosClient.post('/developer/model-parameters', parameters);
            setParamMessage('✓ ' + (res.data.message || 'Đã cập nhật thông số thành công'));
            setTimeout(() => setParamMessage(''), 3000);
            if (res.data.ml_version) {
                notifyPipelineCompleted({
                    reason: 'model-parameters',
                    message: res.data.note || 'Thông số đã cập nhật. Dự đoán sẽ được làm mới khi user truy cập dữ liệu.'
                });
            } else if (res.data.pipeline_status === 'running_in_background') {
                notifyPipelineCompleted({
                    reason: 'model-parameters',
                    message: res.data.note || 'Pipeline đang chạy background, dự đoán sẽ được cập nhật trong giây lát.'
                });
            } else if (res.data.pipeline) {
                notifyPipelineCompleted({ reason: 'model-parameters', stats: res.data.pipeline, message: 'Pipeline đã cập nhật theo thông số mới.' });
            }
        } catch (e) {
            const errorMsg = e.response?.data?.detail || e.message || 'Lỗi không xác định';
            setParamMessage('Lỗi: ' + errorMsg);
            notifyPipelineCompleted({ reason: 'model-parameters', error: 'Pipeline lỗi: ' + errorMsg });
        } finally {
            setSavingParams(false);
        }
    };

    const handleSelectModel = async (modelName) => {
        setModelMsg('');
        notifyPipelineProcessing({ reason: 'model-selection', message: 'Đang chuyển mô hình và chạy lại pipeline...' });
        try {
            const res = await axiosClient.post('/developer/select-model', { model: modelName });
            setSelectedModel(modelName);
            setModelMsg('✓ ' + (res.data.message || 'Đã cập nhật mô hình dự đoán.'));
            setTimeout(() => setModelMsg(''), 3000);
            if (res.data.ml_version) {
                notifyPipelineCompleted({
                    reason: 'model-selection',
                    message: res.data.note || 'Mô hình đã chuyển. Dự đoán sẽ được làm mới khi user truy cập dữ liệu.'
                });
            } else if (res.data.pipeline_status === 'running_in_background') {
                notifyPipelineCompleted({
                    reason: 'model-selection',
                    message: res.data.note || 'Pipeline đang chạy background, dự đoán sẽ được cập nhật trong giây lát.'
                });
            } else if (res.data.pipeline) {
                notifyPipelineCompleted({ reason: 'model-selection', stats: res.data.pipeline, message: 'Pipeline đã áp dụng mô hình mới.' });
            }
            await fetchModelStatus();
        } catch (e) {
            console.error('Model selection error:', e);
            const errorMsg = e.response?.data?.detail || e.message || 'Lỗi không xác định';
            setModelMsg('Lỗi: ' + errorMsg);
            notifyPipelineCompleted({ reason: 'model-selection', error: 'Lỗi khi chọn mô hình: ' + errorMsg });
        }
    };

    const handleFileChange = (e) => {
        const selectedFile = e.target.files[0];
        if (selectedFile) {
            const ext = selectedFile.name.split('.').pop().toLowerCase();
            if (ext !== 'xlsx' && ext !== 'xls' && ext !== 'csv') {
                setMessage({ type: 'error', text: 'Chỉ chấp nhận file Excel (.xlsx, .xls) hoặc CSV (.csv)' });
                return;
            }
            setFile(selectedFile);
            setMessage({ type: '', text: '' });
        }
    };

    const handleUpload = async () => {
        if (!file) {
            setMessage({ type: 'error', text: 'Vui lòng chọn file trước khi tải lên.' });
            return;
        }

        setUploading(true);
        setMessage({ type: '', text: '' });
        setSummary(null);
        notifyPipelineProcessing({ reason: 'dataset-import', message: 'Đang tải lên tập dữ liệu và cập nhật pipeline...' });

        const formData = new FormData();
        formData.append('file', file);

        try {
            const res = await axiosClient.post('/developer/import-excel', formData, {
                headers: { 'Content-Type': 'multipart/form-data' },
                timeout: 90000
            });
            setSummary(res.data.summary || {});
            setFile(null);
            notifyPipelineCompleted({ reason: 'dataset-import', stats: res.data.pipeline, message: 'Pipeline đã đồng bộ dataset mới.' });
            await fetchDatasetStatus();
        } catch (e) {
            setMessage({ type: 'error', text: 'Lỗi import: ' + (e.response?.data?.detail || e.message) });
            notifyPipelineCompleted({ reason: 'dataset-import', error: 'Pipeline lỗi: ' + (e.response?.data?.detail || e.message) });
        } finally {
            setUploading(false);
        }
    };

    const handleEvaluateModels = async () => {
        setEvaluating(true);
        setEvaluationMessage('');
        setEvaluationResults(null);

        try {
            const res = await axiosClient.post('/developer/evaluate-models', {}, { timeout: 120000 });
            setEvaluationResults(res.data);
            if (res.data.error) {
                setEvaluationMessage('Cảnh báo: ' + res.data.error);
            } else {
                setEvaluationMessage('✓ Đánh giá mô hình hoàn tất!');
            }
        } catch (e) {
            setEvaluationMessage('Lỗi: ' + (e.response?.data?.detail || e.message));
        } finally {
            setEvaluating(false);
        }
    };

    const fetchTeachingStructure = async () => {
        try {
            const res = await axiosClient.get('/developer/teaching-structure');
            if (res.data.has_structure) {
                setNumTimePoints(res.data.num_time_points.toString());
                setNumSubjects(res.data.num_subjects.toString());
                setTimePointLabels(res.data.time_point_labels);
                setSubjectLabels(res.data.subject_labels);
                setStructureConfirmed(true);
            }
        } catch (e) {
            console.error('Error fetching teaching structure:', e);
        }
    };

    const handleSaveStructure = async () => {
        if (timePointLabels.some(l => !l.trim()) || subjectLabels.some(l => !l.trim())) {
            alert('Vui lòng nhập tên cho tất cả mốc thời gian và môn học');
            return;
        }

        setSavingStructure(true);
        setStructureMessage('');

        try {
            const res = await axiosClient.post('/developer/teaching-structure', {
                num_time_points: parseInt(numTimePoints),
                num_subjects: parseInt(numSubjects),
                time_point_labels: timePointLabels,
                subject_labels: subjectLabels
            });
            setStructureMessage('✓ ' + res.data.message);
            setTimeout(() => setStructureMessage(''), 3000);
        } catch (e) {
            setStructureMessage('Lỗi: ' + (e.response?.data?.detail || e.message));
        } finally {
            setSavingStructure(false);
        }
    };

    const fetchPipelineStatus = async () => {
        try {
            const res = await axiosClient.get('/developer/pipeline-status');
            setPipelineEnabled(res.data.pipeline_enabled);
        } catch (e) {
            console.error('Error fetching pipeline status:', e);
        }
    };

    const handleTogglePipeline = async () => {
        setTogglingPipeline(true);
        try {
            const res = await axiosClient.post('/developer/pipeline-toggle', {
                enabled: !pipelineEnabled
            });
            setPipelineEnabled(res.data.pipeline_enabled);
            setStructureMessage('✓ ' + res.data.message);
            setTimeout(() => setStructureMessage(''), 3000);
        } catch (e) {
            setStructureMessage('Lỗi: ' + (e.response?.data?.detail || e.message));
        } finally {
            setTogglingPipeline(false);
        }
    };

    const handleConfirmStructure = () => {
        const numTP = parseInt(numTimePoints);
        const numSub = parseInt(numSubjects);
        
        if (isNaN(numTP) || numTP < 1) {
            alert('Vui lòng nhập số lượng mốc thời gian lớn hơn 0');
            return;
        }
        
        if (isNaN(numSub) || numSub < 1) {
            alert('Vui lòng nhập số lượng môn học lớn hơn 0');
            return;
        }
        
        // Update time point labels
        setTimePointLabels(prevLabels => {
            const newLabels = [...prevLabels];
            if (numTP > prevLabels.length) {
                for (let i = prevLabels.length; i < numTP; i++) {
                    newLabels.push('');
                }
            } else if (numTP < prevLabels.length) {
                return newLabels.slice(0, numTP);
            }
            return newLabels;
        });
        
        // Update subject labels
        setSubjectLabels(prevLabels => {
            const newLabels = [...prevLabels];
            if (numSub > prevLabels.length) {
                for (let i = prevLabels.length; i < numSub; i++) {
                    newLabels.push('');
                }
            } else if (numSub < prevLabels.length) {
                return newLabels.slice(0, numSub);
            }
            return newLabels;
        });
        
        setStructureConfirmed(true);
    };

    const handleDownloadTemplate = () => {
        // Tạo CSV content
        const headers = ['STT', 'name'];
        timePointLabels.forEach(timePoint => {
            subjectLabels.forEach(subject => {
                headers.push(`${subject}_${timePoint}`);
            });
        });

        // Tạo CSV string
        let csvContent = headers.join(',') + '\n';
        
        // Thêm 3 dòng mẫu
        for (let i = 1; i <= 3; i++) {
            const row = [i, `Học sinh ${i}`];
            for (let j = 0; j < timePointLabels.length * subjectLabels.length; j++) {
                row.push('');
            }
            csvContent += row.join(',') + '\n';
        }

        // Download file
        const blob = new Blob(['\uFEFF' + csvContent], { type: 'text/csv;charset=utf-8;' });
        const link = document.createElement('a');
        const url = URL.createObjectURL(blob);
        link.setAttribute('href', url);
        link.setAttribute('download', 'teaching_structure_template.csv');
        link.style.visibility = 'hidden';
        document.body.appendChild(link);
        link.click();
        document.body.removeChild(link);
    };

    return (
        <div style={{ padding: '2rem', maxWidth: '1400px', margin: '0 auto' }}>
            <motion.div
                initial={{ opacity: 0, y: 20 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ duration: 0.3 }}
            >
                <h1 style={{ fontSize: '2rem', fontWeight: '700', marginBottom: '0.5rem', color: 'var(--text-primary)' }}>
                    Công cụ Quản trị
                </h1>
                <p style={{ fontSize: '1rem', color: 'var(--text-secondary)', marginBottom: '2rem' }}>
                    Quản lý mô hình ML, dataset và thông số dự đoán cho cơ sở giáo dục của bạn.
                </p>

                {message.text && (
                    <div style={{
                        padding: '1rem',
                        borderRadius: 'var(--radius-md)',
                        marginBottom: '1.5rem',
                        background: message.type === 'error' ? '#fef2f2' : message.type === 'success' ? '#f0fdf4' : 'var(--primary-light)',
                        color: message.type === 'error' ? 'var(--danger-color)' : message.type === 'success' ? '#166534' : 'var(--primary-color)',
                        border: `1px solid ${message.type === 'error' ? '#fecaca' : message.type === 'success' ? '#bbf7d0' : 'var(--primary-light)'}`,
                        display: 'flex',
                        alignItems: 'center',
                        gap: '0.75rem'
                    }}>
                        {message.type === 'error' ? <AlertCircle size={20} /> : <Zap size={20} />}
                        {message.text}
                    </div>
                )}

                {pipelineBanner.text && (
                    <div style={{
                        padding: '1rem',
                        borderRadius: 'var(--radius-md)',
                        marginBottom: '1.5rem',
                        background: pipelineBanner.type === 'error' ? '#fef2f2' : pipelineBanner.type === 'success' ? '#f0fdf4' : '#fefce8',
                        color: pipelineBanner.type === 'error' ? 'var(--danger-color)' : pipelineBanner.type === 'success' ? '#166534' : '#854d0e',
                        border: `1px solid ${pipelineBanner.type === 'error' ? '#fecaca' : pipelineBanner.type === 'success' ? '#bbf7d0' : '#fef08a'}`,
                        display: 'flex',
                        alignItems: 'center',
                        gap: '0.75rem'
                    }}>
                        <RefreshCw size={20} className={pipelineBanner.type === 'info' ? 'spin' : ''} />
                        {pipelineBanner.text}
                    </div>
                )}

                {/* Teaching Structure Setup Section - Must be completed first */}
                <div style={{ background: 'var(--bg-surface)', padding: '2rem', borderRadius: 'var(--radius-lg)', marginBottom: '2rem', border: '1px solid var(--border-color)' }}>
                    <h3 style={{ fontSize: '1.25rem', fontWeight: '600', marginBottom: '1rem', display: 'flex', alignItems: 'center', gap: '0.75rem', color: 'var(--text-primary)' }}>
                        <Settings size={24} style={{ color: '#3b82f6' }} />
                        Thiết lập cấu trúc giảng dạy
                    </h3>

                    <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '2rem', marginBottom: '2rem' }}>
                        {/* Left Column - Inputs */}
                        <div>
                            <div style={{ marginBottom: '1.5rem' }}>
                                <label style={{ display: 'block', marginBottom: '0.5rem', fontWeight: '500', color: 'var(--text-primary)' }}>
                                    Số lượng mốc thời gian: {parseInt(numTimePoints) || 0}
                                </label>
                                <input
                                    type="number"
                                    min="1"
                                    value={numTimePoints}
                                    onChange={(e) => setNumTimePoints(e.target.value)}
                                    placeholder="Nhập số lượng"
                                    className="input-field"
                                    style={{ width: '100%', padding: '0.75rem', borderRadius: 'var(--radius-md)', border: '1px solid var(--border-color)' }}
                                />
                            </div>

                            <div style={{ marginBottom: '1.5rem' }}>
                                <label style={{ display: 'block', marginBottom: '0.5rem', fontWeight: '500', color: 'var(--text-primary)' }}>
                                    Số lượng môn học: {parseInt(numSubjects) || 0}
                                </label>
                                <input
                                    type="number"
                                    min="1"
                                    value={numSubjects}
                                    onChange={(e) => setNumSubjects(e.target.value)}
                                    placeholder="Nhập số lượng"
                                    className="input-field"
                                    style={{ width: '100%', padding: '0.75rem', borderRadius: 'var(--radius-md)', border: '1px solid var(--border-color)' }}
                                />
                            </div>

                            <button
                                onClick={handleConfirmStructure}
                                className="button-primary"
                                style={{ 
                                    width: '100%',
                                    padding: '0.875rem', 
                                    borderRadius: 'var(--radius-md)', 
                                    background: '#3b82f6', 
                                    color: 'white', 
                                    border: 'none', 
                                    cursor: 'pointer',
                                    fontWeight: '500',
                                    fontSize: '1rem'
                                }}
                            >
                                xác nhận
                            </button>

                            {structureConfirmed && (
                                <div style={{ marginTop: '1.5rem' }}>
                                    <label style={{ display: 'block', marginBottom: '0.75rem', fontWeight: '500', color: 'var(--text-primary)' }}>
                                        Cấu trúc tập dữ liệu yêu cầu:
                                    </label>
                                    <div style={{ 
                                        background: 'var(--bg-body)', 
                                        padding: '1rem', 
                                        borderRadius: 'var(--radius-md)', 
                                        border: '1px solid var(--border-color)'
                                    }}>
                                        <p style={{ fontSize: '0.9rem', color: 'var(--text-secondary)', marginBottom: '0.5rem' }}>
                                            <strong>Tổng số cột điểm:</strong> {timePointLabels.length * subjectLabels.length} cột
                                        </p>
                                        <p style={{ fontSize: '0.85rem', color: 'var(--text-tertiary)' }}>
                                            = {timePointLabels.length} mốc thời gian × {subjectLabels.length} môn học
                                        </p>
                                    </div>
                                </div>
                            )}
                        </div>

                        {/* Right Column - Instructions */}
                        <div style={{ 
                            background: '#dbeafe', 
                            padding: '1.5rem', 
                            borderRadius: 'var(--radius-md)',
                            position: 'relative'
                        }}>
                            
                            <div style={{ marginBottom: '1rem' }}>
                                <p style={{ fontWeight: '600', color: '#1e40af', marginBottom: '0.75rem' }}>
                                    Ví dụ 1: giảm sát điểm số học sinh THPT với mốc thời gian là 3 năm học với điểm số 9 môn:
                                </p>
                                <p style={{ fontSize: '0.9rem', color: '#1e40af', lineHeight: '1.7' }}>
                                    số lượng mốc thời gian là 3 (Lớp 10, Lớp 11, Lớp 12). số lượng môn học 9.
                                </p>
                            </div>
                            <div>
                                <p style={{ fontWeight: '600', color: '#1e40af', marginBottom: '0.75rem' }}>
                                    Ví dụ 2: giảm sát điểm số học viên luyện thi TOEIC với mốc thời gian là 4 khóa học với điểm số của 4 kỹ năng:
                                </p>
                                <p style={{ fontSize: '0.9rem', color: '#1e40af', lineHeight: '1.7' }}>
                                    số lượng mốc thời gian 4, số lượng môn học 4 kỹ năng (Reading, Listening, Speaking, Writing).
                                </p>
                            </div>
                            <div style={{ 
                                marginTop: '1.5rem', 
                                padding: '1rem', 
                                background: 'white', 
                                borderRadius: 'var(--radius-md)',
                                fontSize: '0.85rem',
                                color: '#374151'
                            }}>
                                <p style={{ fontWeight: '500', marginBottom: '0.5rem' }}>💡 Lưu ý:</p>
                                <p style={{ lineHeight: '1.6' }}>
                                    Tên các môn học và mốc thời gian nhập thủ công. Nhập mốc thời gian tăng dần từ trái sang phải.
                                </p>
                            </div>
                        </div>
                    </div>

                    {/* Input fields for labels */}
                    {structureConfirmed && (
                        <div style={{ marginBottom: '2rem' }}>
                            <h4 style={{ fontSize: '1.1rem', fontWeight: '600', marginBottom: '1rem', color: 'var(--text-primary)' }}>
                                Nhập tên các mốc thời gian:
                            </h4>
                            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(200px, 1fr))', gap: '1rem' }}>
                                {timePointLabels.map((label, idx) => (
                                    <input
                                        key={idx}
                                        type="text"
                                        value={label}
                                        onChange={(e) => {
                                            const newLabels = [...timePointLabels];
                                            newLabels[idx] = e.target.value;
                                            setTimePointLabels(newLabels);
                                        }}
                                        placeholder={`Mốc ${idx + 1}`}
                                        className="input-field"
                                        style={{ padding: '0.75rem', borderRadius: 'var(--radius-md)', border: '1px solid var(--border-color)' }}
                                    />
                                ))}
                            </div>
                        </div>
                    )}

                    {structureConfirmed && (
                        <div style={{ marginBottom: '2rem' }}>
                            <h4 style={{ fontSize: '1.1rem', fontWeight: '600', marginBottom: '1rem', color: 'var(--text-primary)' }}>
                                Nhập tên các môn học:
                            </h4>
                            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(200px, 1fr))', gap: '1rem' }}>
                                {subjectLabels.map((label, idx) => (
                                    <input
                                        key={idx}
                                        type="text"
                                        value={label}
                                        onChange={(e) => {
                                            const newLabels = [...subjectLabels];
                                            newLabels[idx] = e.target.value;
                                            setSubjectLabels(newLabels);
                                        }}
                                        placeholder={`Môn ${idx + 1}`}
                                        className="input-field"
                                        style={{ padding: '0.75rem', borderRadius: 'var(--radius-md)', border: '1px solid var(--border-color)' }}
                                    />
                                ))}
                            </div>
                        </div>
                    )}

                    {structureMessage && (
                        <div style={{
                            padding: '1rem',
                            borderRadius: 'var(--radius-md)',
                            marginTop: '1rem',
                            background: structureMessage.startsWith('Lỗi') ? '#fef2f2' : '#f0fdf4',
                            color: structureMessage.startsWith('Lỗi') ? 'var(--danger-color)' : '#166534',
                            border: `1px solid ${structureMessage.startsWith('Lỗi') ? '#fecaca' : '#bbf7d0'}`,
                            textAlign: 'center'
                        }}>
                            {structureMessage}
                        </div>
                    )}

                    {structureConfirmed && (
                        <div style={{ display: 'flex', justifyContent: 'center', gap: '1rem', paddingTop: '1rem', borderTop: '1px solid var(--border-color)' }}>
                            <button
                                onClick={handleDownloadTemplate}
                                disabled={timePointLabels.some(l => !l.trim()) || subjectLabels.some(l => !l.trim())}
                                className="button-secondary"
                                style={{ 
                                    padding: '1rem 2rem', 
                                    borderRadius: 'var(--radius-md)', 
                                    background: (timePointLabels.some(l => !l.trim()) || subjectLabels.some(l => !l.trim())) ? '#9ca3af' : '#10b981', 
                                    color: 'white', 
                                    border: 'none', 
                                    cursor: (timePointLabels.some(l => !l.trim()) || subjectLabels.some(l => !l.trim())) ? 'not-allowed' : 'pointer',
                                    fontWeight: '600',
                                    fontSize: '1rem',
                                    boxShadow: (timePointLabels.some(l => !l.trim()) || subjectLabels.some(l => !l.trim())) ? 'none' : '0 4px 6px rgba(16, 185, 129, 0.2)',
                                    transition: 'all 0.2s',
                                    opacity: (timePointLabels.some(l => !l.trim()) || subjectLabels.some(l => !l.trim())) ? 0.6 : 1,
                                    display: 'flex',
                                    alignItems: 'center',
                                    gap: '0.5rem'
                                }}
                                onMouseOver={(e) => {
                                    if (!(timePointLabels.some(l => !l.trim()) || subjectLabels.some(l => !l.trim()))) {
                                        e.target.style.background = '#059669';
                                    }
                                }}
                                onMouseOut={(e) => {
                                    if (!(timePointLabels.some(l => !l.trim()) || subjectLabels.some(l => !l.trim()))) {
                                        e.target.style.background = '#10b981';
                                    }
                                }}
                            >
                                <FileText size={18} />
                                Tải tập dữ liệu mẫu
                            </button>
                            <button
                                onClick={handleSaveStructure}
                                disabled={timePointLabels.some(l => !l.trim()) || subjectLabels.some(l => !l.trim()) || savingStructure}
                                className="button-primary"
                                style={{ 
                                    padding: '1rem 2rem', 
                                    borderRadius: 'var(--radius-md)', 
                                    background: (timePointLabels.some(l => !l.trim()) || subjectLabels.some(l => !l.trim()) || savingStructure) ? '#9ca3af' : '#3b82f6', 
                                    color: 'white', 
                                    border: 'none', 
                                    cursor: (timePointLabels.some(l => !l.trim()) || subjectLabels.some(l => !l.trim()) || savingStructure) ? 'not-allowed' : 'pointer',
                                    fontWeight: '600',
                                    fontSize: '1rem',
                                    boxShadow: (timePointLabels.some(l => !l.trim()) || subjectLabels.some(l => !l.trim()) || savingStructure) ? 'none' : '0 4px 6px rgba(59, 130, 246, 0.2)',
                                    transition: 'all 0.2s',
                                    opacity: (timePointLabels.some(l => !l.trim()) || subjectLabels.some(l => !l.trim()) || savingStructure) ? 0.6 : 1,
                                    display: 'flex',
                                    alignItems: 'center',
                                    gap: '0.5rem'
                                }}
                                onMouseOver={(e) => {
                                    if (!(timePointLabels.some(l => !l.trim()) || subjectLabels.some(l => !l.trim()) || savingStructure)) {
                                        e.currentTarget.style.background = '#2563eb';
                                    }
                                }}
                                onMouseOut={(e) => {
                                    if (!(timePointLabels.some(l => !l.trim()) || subjectLabels.some(l => !l.trim()) || savingStructure)) {
                                        e.currentTarget.style.background = '#3b82f6';
                                    }
                                }}
                            >
                                <Save size={18} />
                                {savingStructure ? 'Đang lưu...' : 'Lưu cấu trúc'}
                            </button>
                            <button
                                onClick={handleTogglePipeline}
                                disabled={togglingPipeline}
                                className="button-toggle"
                                style={{ 
                                    padding: '1rem 2rem', 
                                    borderRadius: 'var(--radius-md)', 
                                    background: togglingPipeline ? '#9ca3af' : (pipelineEnabled ? '#f59e0b' : '#6b7280'),
                                    color: 'white', 
                                    border: 'none', 
                                    cursor: togglingPipeline ? 'not-allowed' : 'pointer',
                                    fontWeight: '600',
                                    fontSize: '1rem',
                                    boxShadow: togglingPipeline ? 'none' : `0 4px 6px ${pipelineEnabled ? 'rgba(245, 158, 11, 0.2)' : 'rgba(107, 114, 128, 0.2)'}`,
                                    transition: 'all 0.2s',
                                    opacity: togglingPipeline ? 0.6 : 1,
                                    display: 'flex',
                                    alignItems: 'center',
                                    gap: '0.5rem'
                                }}
                                onMouseOver={(e) => {
                                    if (!togglingPipeline) {
                                        e.currentTarget.style.background = pipelineEnabled ? '#d97706' : '#4b5563';
                                    }
                                }}
                                onMouseOut={(e) => {
                                    if (!togglingPipeline) {
                                        e.currentTarget.style.background = pipelineEnabled ? '#f59e0b' : '#6b7280';
                                    }
                                }}
                            >
                                <Power size={18} />
                                {togglingPipeline ? 'Đang xử lý...' : (pipelineEnabled ? 'Tắt Pipeline' : 'Bật Pipeline')}
                            </button>
                                onClick={() => {
                                    alert('Cấu trúc giảng dạy đã được lưu!');
                                }}
                                disabled={timePointLabels.some(l => !l.trim()) || subjectLabels.some(l => !l.trim())}
                                className="button-primary"
                                style={{ 
                                    padding: '1rem 2rem', 
                                    borderRadius: 'var(--radius-md)', 
                                    background: (timePointLabels.some(l => !l.trim()) || subjectLabels.some(l => !l.trim())) ? '#9ca3af' : '#3b82f6', 
                                    color: 'white', 
                                    border: 'none', 
                                    cursor: (timePointLabels.some(l => !l.trim()) || subjectLabels.some(l => !l.trim())) ? 'not-allowed' : 'pointer',
                                    fontWeight: '600',
                                    fontSize: '1rem',
                                    boxShadow: (timePointLabels.some(l => !l.trim()) || subjectLabels.some(l => !l.trim())) ? 'none' : '0 4px 6px rgba(59, 130, 246, 0.2)',
                                    transition: 'all 0.2s',
                                    opacity: (timePointLabels.some(l => !l.trim()) || subjectLabels.some(l => !l.trim())) ? 0.6 : 1,
                                    display: 'flex',
                                    alignItems: 'center',
                                    gap: '0.5rem'
                                }}
                                onMouseOver={(e) => {
                                    if (!(timePointLabels.some(l => !l.trim()) || subjectLabels.some(l => !l.trim()))) {
                                        e.currentTarget.style.background = '#2563eb';
                                    }
                                }}
                                onMouseOut={(e) => {
                                    if (!(timePointLabels.some(l => !l.trim()) || subjectLabels.some(l => !l.trim()))) {
                                        e.currentTarget.style.background = '#3b82f6';
                                    }
                                }}
                            >
                                <Save size={18} />
                                Lưu cấu trúc
                            </button>
                        </div>
                    )}
                </div>

                {/* Dataset Status Section */}
                <div style={{ background: 'var(--bg-surface)', padding: '2rem', borderRadius: 'var(--radius-lg)', marginBottom: '2rem', border: '1px solid var(--border-color)' }}>
                    <h3 style={{ fontSize: '1.25rem', fontWeight: '600', marginBottom: '1.25rem', display: 'flex', alignItems: 'center', gap: '0.75rem', color: 'var(--text-primary)' }}>
                        <Database size={24} style={{ color: '#10b981' }} />
                        Trạng Thái Bộ Dữ Liệu Tham Chiếu
                    </h3>
                    {loadingDataset ? (
                        <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', color: 'var(--text-secondary)' }}>
                            <span className="spinner"></span> Đang tải...
                        </div>
                    ) : datasetStatus ? (
                        datasetStatus.error ? (
                            <div style={{
                                padding: '1rem',
                                background: '#fef2f2',
                                borderRadius: 'var(--radius-md)',
                                color: 'var(--danger-color)',
                                border: '1px solid #fecaca',
                                display: 'flex',
                                alignItems: 'center',
                                gap: '0.5rem'
                            }}>
                                <AlertCircle size={18} />
                                {datasetStatus.error}
                            </div>
                        ) : (
                        <div style={{ display: 'flex', flexDirection: 'column', gap: '1.5rem' }}>
                            <div style={{
                                padding: '1.5rem',
                                background: datasetStatus.has_dataset ? '#f0fdf4' : '#fff7ed',
                                borderRadius: 'var(--radius-md)',
                                border: `1px solid ${datasetStatus.has_dataset ? '#bbf7d0' : '#fed7aa'}`
                            }}>
                                <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem', marginBottom: '1rem' }}>
                                    <strong style={{ fontSize: '1.1rem', color: datasetStatus.has_dataset ? '#166534' : '#9a3412' }}>
                                        {datasetStatus.has_dataset ? '✓ Đã có bộ dữ liệu' : '⚠ Chưa có bộ dữ liệu'}
                                    </strong>
                                </div>
                                <div className="grid" style={{ gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: '1.5rem' }}>
                                    <div>
                                        <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginBottom: '0.5rem' }}>
                                            <FileText size={16} style={{ color: 'var(--text-tertiary)' }} />
                                            <span style={{ fontSize: '0.9rem', color: 'var(--text-secondary)' }}>Số mẫu tham chiếu:</span>
                                        </div>
                                        <strong style={{ fontSize: '1.5rem', color: 'var(--text-primary)' }}>
                                            {datasetStatus.sample_count.toLocaleString('vi-VN')}
                                        </strong>
                                    </div>
                                    <div>
                                        <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginBottom: '0.5rem' }}>
                                            <Database size={16} style={{ color: 'var(--text-tertiary)' }} />
                                            <span style={{ fontSize: '0.9rem', color: 'var(--text-secondary)' }}>Kích thước (ước tính):</span>
                                        </div>
                                        <strong style={{ fontSize: '1.5rem', color: 'var(--text-primary)' }}>
                                            {datasetStatus.size_mb} MB
                                        </strong>
                                    </div>
                                </div>
                            </div>

                            {datasetStatus.last_import && (
                                <div style={{
                                    padding: '1.25rem',
                                    background: 'var(--bg-body)',
                                    borderRadius: 'var(--radius-md)',
                                    border: '1px solid var(--border-color)'
                                }}>
                                    <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginBottom: '1rem' }}>
                                        <Clock size={18} style={{ color: 'var(--text-tertiary)' }} />
                                        <strong style={{ fontSize: '1rem', color: 'var(--text-secondary)' }}>Lần tải lên gần nhất:</strong>
                                    </div>
                                    <div style={{ fontSize: '0.95rem', color: 'var(--text-primary)', lineHeight: '1.8' }}>
                                        <div><span style={{ color: 'var(--text-secondary)' }}>File:</span> <strong>{datasetStatus.last_import.filename}</strong></div>
                                        <div><span style={{ color: 'var(--text-secondary)' }}>Thời gian:</span> {new Date(datasetStatus.last_import.created_at).toLocaleString('vi-VN')}</div>
                                        <div><span style={{ color: 'var(--text-secondary)' }}>Đã tải lên:</span> {datasetStatus.last_import.imported_rows.toLocaleString('vi-VN')} / {datasetStatus.last_import.total_rows.toLocaleString('vi-VN')} dòng</div>
                                        {datasetStatus.last_import.skipped_rows > 0 && (
                                            <div style={{ color: 'var(--warning-color)', marginTop: '0.5rem' }}>
                                                <strong>⚠ Đã bỏ qua:</strong> {datasetStatus.last_import.skipped_rows.toLocaleString('vi-VN')} dòng
                                            </div>
                                        )}
                                    </div>
                                </div>
                            )}

                            {!datasetStatus.has_dataset && (
                                <div style={{
                                    padding: '1rem',
                                    background: '#fff7ed',
                                    borderRadius: 'var(--radius-md)',
                                    color: '#9a3412',
                                    fontSize: '0.95rem',
                                    border: '1px solid #fed7aa',
                                    display: 'flex',
                                    alignItems: 'center',
                                    gap: '0.5rem'
                                }}>
                                    <AlertCircle size={18} />
                                    Chưa có bộ dữ liệu tham chiếu. Vui lòng tải lên tập dữ liệu để sử dụng tính năng dự đoán.
                                </div>
                            )}
                        </div>
                        )
                    ) : (
                        <p style={{ color: 'var(--danger-color)' }}>Không thể tải trạng thái dataset.</p>
                    )}
                </div>

                {/* Import Excel Section - Disabled until teaching structure is confirmed */}
                <div style={{ 
                    background: 'var(--bg-surface)', 
                    padding: '2rem', 
                    borderRadius: 'var(--radius-lg)', 
                    marginBottom: '2rem', 
                    border: '1px solid var(--border-color)',
                    opacity: structureConfirmed && timePointLabels.every(l => l.trim()) && subjectLabels.every(l => l.trim()) ? 1 : 0.6,
                    position: 'relative'
                }}>
                    {(!structureConfirmed || timePointLabels.some(l => !l.trim()) || subjectLabels.some(l => !l.trim())) && (
                        <div style={{
                            position: 'absolute',
                            top: 0,
                            left: 0,
                            right: 0,
                            bottom: 0,
                            background: 'rgba(255, 255, 255, 0.8)',
                            borderRadius: 'var(--radius-lg)',
                            display: 'flex',
                            alignItems: 'center',
                            justifyContent: 'center',
                            zIndex: 10
                        }}>
                            <div style={{
                                background: '#fff7ed',
                                padding: '1.5rem 2rem',
                                borderRadius: 'var(--radius-md)',
                                border: '2px solid #fed7aa',
                                maxWidth: '500px',
                                textAlign: 'center'
                            }}>
                                <AlertCircle size={32} style={{ color: '#9a3412', marginBottom: '1rem' }} />
                                <p style={{ color: '#9a3412', fontWeight: '600', fontSize: '1.1rem', marginBottom: '0.5rem' }}>
                                    Vui lòng hoàn tất thiết lập cấu trúc giảng dạy
                                </p>
                                <p style={{ color: '#9a3412', fontSize: '0.95rem' }}>
                                    Bạn cần xác nhận số lượng mốc thời gian, môn học và nhập đầy đủ tên cho tất cả các mốc/môn trước khi tải lên dữ liệu tham chiếu.
                                </p>
                            </div>
                        </div>
                    )}
                    <h3 style={{ fontSize: '1.25rem', fontWeight: '600', marginBottom: '1rem', display: 'flex', alignItems: 'center', gap: '0.75rem', color: 'var(--text-primary)' }}>
                        <Upload size={24} style={{ color: '#10b981' }} />
                        Tải Lên Tập Dữ Liệu Tham Chiếu
                    </h3>
                    <p style={{ fontSize: '0.95rem', color: 'var(--text-secondary)', marginBottom: '1.5rem' }}>
                        Tải lên tập dữ liệu tham chiếu với cấu trúc giống với tập dữ liệu mẫu được cung cấp
                    </p>

                    <div style={{ marginBottom: '1.5rem' }}>
                        <input
                            type="file"
                            accept=".xlsx,.xls,.csv"
                            onChange={handleFileChange}
                            disabled={!structureConfirmed || timePointLabels.some(l => !l.trim()) || subjectLabels.some(l => !l.trim())}
                            className="input-field"
                            style={{
                                padding: '1rem',
                                border: '2px dashed var(--border-color)',
                                borderRadius: 'var(--radius-md)',
                                width: '100%',
                                cursor: (structureConfirmed && timePointLabels.every(l => l.trim()) && subjectLabels.every(l => l.trim())) ? 'pointer' : 'not-allowed',
                                background: 'var(--bg-body)'
                            }}
                        />
                        {file && (
                            <p style={{ marginTop: '0.75rem', fontSize: '0.95rem', color: '#10b981', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                                <FileText size={16} />
                                Đã chọn: <strong>{file.name}</strong>
                            </p>
                        )}
                    </div>

                    <button
                        className="btn"
                        onClick={handleUpload}
                        disabled={!file || uploading || !structureConfirmed || timePointLabels.some(l => !l.trim()) || subjectLabels.some(l => !l.trim())}
                        style={{
                            background: (!file || uploading || !structureConfirmed || timePointLabels.some(l => !l.trim()) || subjectLabels.some(l => !l.trim())) ? '#9ca3af' : '#10b981',
                            color: 'white',
                            display: 'flex',
                            alignItems: 'center',
                            gap: '0.5rem',
                            cursor: (!file || uploading || !structureConfirmed || timePointLabels.some(l => !l.trim()) || subjectLabels.some(l => !l.trim())) ? 'not-allowed' : 'pointer',
                            opacity: (!file || uploading || !structureConfirmed || timePointLabels.some(l => !l.trim()) || subjectLabels.some(l => !l.trim())) ? 0.6 : 1
                        }}
                    >
                        {uploading ? <RefreshCw size={18} className="spin" /> : <Upload size={18} />}
                        {uploading ? 'Đang tải lên...' : 'Tải lên tập dữ liệu'}
                    </button>

                    {summary && (
                        <div style={{ marginTop: '1.5rem', padding: '1.25rem', background: 'var(--bg-body)', borderRadius: 'var(--radius-md)', border: '1px solid var(--border-color)' }}>
                            <h4 style={{ fontSize: '1rem', fontWeight: '600', marginBottom: '1rem', color: 'var(--text-primary)' }}>📊 Kết quả tải lên:</h4>
                            <ul style={{ margin: 0, paddingLeft: '1.5rem', fontSize: '0.95rem', color: 'var(--text-secondary)', display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
                                <li>Tổng số dòng hợp lệ: <strong>{summary.total_rows || 0}</strong></li>
                                <li>Số mẫu tham chiếu: <strong>{summary.reference_samples || 0}</strong></li>
                                {summary.cleared_existing && <li style={{ color: 'var(--warning-color)' }}>⚠ Đã thay thế dữ liệu cũ</li>}
                            </ul>
                        </div>
                    )}
                </div>

                {/* Model Parameters Section */}
                <div style={{ background: 'var(--bg-surface)', padding: '2rem', borderRadius: 'var(--radius-lg)', marginBottom: '2rem', border: '1px solid var(--border-color)', borderLeft: '4px solid var(--warning-color)' }}>
                    <h3 style={{ fontSize: '1.25rem', fontWeight: '600', marginBottom: '0.5rem', display: 'flex', alignItems: 'center', gap: '0.75rem', color: 'var(--text-primary)' }}>
                        <Settings size={24} style={{ color: 'var(--warning-color)' }} />
                        Cấu Hình Thông Số Mô Hình ML
                    </h3>
                    <p style={{ fontSize: '0.95rem', color: 'var(--text-secondary)', marginBottom: '1.5rem' }}>
                        Tùy chỉnh các thông số cho các mô hình KNN, Kernel Regression, và LWLR.
                    </p>

                    {paramMessage && (
                        <div style={{
                            padding: '1rem',
                            borderRadius: 'var(--radius-md)',
                            marginBottom: '1.5rem',
                            background: paramMessage.startsWith('Lỗi') ? '#fef2f2' : '#f0fdf4',
                            color: paramMessage.startsWith('Lỗi') ? 'var(--danger-color)' : '#166534',
                            border: `1px solid ${paramMessage.startsWith('Lỗi') ? '#fecaca' : '#bbf7d0'}`
                        }}>
                            {paramMessage}
                        </div>
                    )}

                    {loadingParams ? (
                        <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', color: 'var(--text-secondary)' }}>
                            <span className="spinner"></span> Đang tải thông số...
                        </div>
                    ) : (
                        <div>
                            {/* KNN Parameter */}
                            <div style={{
                                marginBottom: '1.25rem',
                                padding: '1.25rem',
                                background: 'var(--bg-body)',
                                borderRadius: 'var(--radius-md)',
                                border: '1px solid var(--border-color)'
                            }}>
                                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.75rem' }}>
                                    <div>
                                        <strong style={{ display: 'block', fontSize: '1rem', marginBottom: '0.25rem', color: 'var(--text-primary)' }}>KNN - Số lân cận (n)</strong>
                                        <p style={{ fontSize: '0.9rem', color: 'var(--text-secondary)', margin: 0 }}>Số mẫu tham chiếu gần nhất. Phạm vi: 1-100</p>
                                    </div>
                                    <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                                        <input
                                            type="number"
                                            min="1"
                                            max="100"
                                            value={parameters.knn_n}
                                            onChange={(e) => setParameters({ ...parameters, knn_n: parseInt(e.target.value) || 15 })}
                                            className="input-field"
                                            style={{ width: '100px', textAlign: 'center' }}
                                        />
                                    </div>
                                </div>
                                <div style={{ fontSize: '0.85rem', color: 'var(--warning-color)', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                                    <Lightbulb size={14} /> Giá trị mặc định: 15
                                </div>
                            </div>

                            {/* Kernel Regression Parameter */}
                            <div style={{
                                marginBottom: '1.25rem',
                                padding: '1.25rem',
                                background: 'var(--bg-body)',
                                borderRadius: 'var(--radius-md)',
                                border: '1px solid var(--border-color)'
                            }}>
                                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.75rem' }}>
                                    <div>
                                        <strong style={{ display: 'block', fontSize: '1rem', marginBottom: '0.25rem', color: 'var(--text-primary)' }}>Kernel Regression - Bandwidth (σ)</strong>
                                        <p style={{ fontSize: '0.9rem', color: 'var(--text-secondary)', margin: 0 }}>Bề rộng hạt nhân Gaussian. Phạm vi: 0.1-10.0</p>
                                    </div>
                                    <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                                        <input
                                            type="number"
                                            min="0.1"
                                            max="10"
                                            step="0.05"
                                            value={parameters.kr_bandwidth}
                                            onChange={(e) => setParameters({ ...parameters, kr_bandwidth: parseFloat(e.target.value) || 1.25 })}
                                            className="input-field"
                                            style={{ width: '100px', textAlign: 'center' }}
                                        />
                                    </div>
                                </div>
                                <div style={{ fontSize: '0.85rem', color: 'var(--warning-color)', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                                    <Lightbulb size={14} /> Giá trị mặc định: 1.25
                                </div>
                            </div>

                            {/* LWLR Parameter */}
                            <div style={{
                                marginBottom: '1.5rem',
                                padding: '1.25rem',
                                background: 'var(--bg-body)',
                                borderRadius: 'var(--radius-md)',
                                border: '1px solid var(--border-color)'
                            }}>
                                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.75rem' }}>
                                    <div>
                                        <strong style={{ display: 'block', fontSize: '1rem', marginBottom: '0.25rem', color: 'var(--text-primary)' }}>LWLR - Tham số cửa sổ (τ)</strong>
                                        <p style={{ fontSize: '0.9rem', color: 'var(--text-secondary)', margin: 0 }}>Điều khiển kích thước cửa sổ bộ lọc. Phạm vi: 0.5-10.0</p>
                                    </div>
                                    <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                                        <input
                                            type="number"
                                            min="0.5"
                                            max="10"
                                            step="0.1"
                                            value={parameters.lwlr_tau}
                                            onChange={(e) => setParameters({ ...parameters, lwlr_tau: parseFloat(e.target.value) || 3.0 })}
                                            className="input-field"
                                            style={{ width: '100px', textAlign: 'center' }}
                                        />
                                    </div>
                                </div>
                                <div style={{ fontSize: '0.85rem', color: 'var(--warning-color)', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                                    <Lightbulb size={14} /> Giá trị mặc định: 3.0
                                </div>
                            </div>

                            <button
                                className="btn"
                                onClick={handleSaveParameters}
                                disabled={savingParams}
                                style={{
                                    background: '#10b981',
                                    color: 'white',
                                    display: 'flex',
                                    alignItems: 'center',
                                    gap: '0.5rem'
                                }}
                            >
                                <Save size={18} />
                                {savingParams ? 'Đang lưu...' : 'Lưu Thông Số'}
                            </button>
                        </div>
                    )}
                </div>

                {/* Model Evaluation Section */}
                <div style={{ background: 'var(--bg-surface)', padding: '2rem', borderRadius: 'var(--radius-lg)', marginBottom: '2rem', border: '1px solid var(--border-color)', borderLeft: '4px solid var(--accent-color)' }}>
                    <h3 style={{ fontSize: '1.25rem', fontWeight: '600', marginBottom: '0.5rem', display: 'flex', alignItems: 'center', gap: '0.75rem', color: 'var(--text-primary)' }}>
                        <Zap size={24} style={{ color: 'var(--accent-color)' }} />
                        Đánh Giá Mô Hình ML
                    </h3>
                    <p style={{ fontSize: '0.95rem', color: 'var(--text-secondary)', marginBottom: '1.5rem' }}>
                        Đánh giá và so sánh 3 mô hình (KNN, Kernel Regression, LWLR) trên dataset của bạn.
                    </p>

                    <button
                        className="btn"
                        onClick={handleEvaluateModels}
                        disabled={evaluating || !datasetStatus?.has_dataset}
                        style={{
                            background: '#10b981',
                            color: 'white',
                            display: 'flex',
                            alignItems: 'center',
                            gap: '0.5rem'
                        }}
                    >
                        <Zap size={18} className={evaluating ? 'spin' : ''} />
                        {evaluating ? 'Đang đánh giá...' : 'Đánh Giá Mô Hình'}
                    </button>

                    {evaluationMessage && (
                        <div style={{
                            padding: '1rem',
                            borderRadius: 'var(--radius-md)',
                            marginTop: '1.5rem',
                            background: evaluationMessage.startsWith('Lỗi') ? '#fef2f2' : '#f0fdf4',
                            color: evaluationMessage.startsWith('Lỗi') ? 'var(--danger-color)' : '#166534',
                            border: `1px solid ${evaluationMessage.startsWith('Lỗi') ? '#fecaca' : '#bbf7d0'}`
                        }}>
                            {evaluationMessage}
                        </div>
                    )}

                    {evaluationResults && !evaluationResults.error && (
                        <div style={{ marginTop: '2rem' }}>
                            {evaluationResults.recommendation && (
                                <div style={{
                                    padding: '1.5rem',
                                    background: 'var(--bg-surface)',
                                    border: '2px solid #10b981',
                                    borderRadius: 'var(--radius-md)',
                                    marginBottom: '2rem',
                                    boxShadow: 'var(--shadow-sm)'
                                }}>
                                    <div style={{ fontSize: '1rem', color: 'var(--text-secondary)', marginBottom: '0.5rem' }}>
                                        <strong>🎯 Mô hình được đề xuất:</strong>
                                    </div>
                                    <div style={{ fontSize: '1.25rem', fontWeight: '700', color: '#10b981' }}>
                                        {evaluationResults.recommendation}
                                    </div>
                                    <div style={{ fontSize: '0.95rem', color: 'var(--text-secondary)', marginTop: '0.5rem' }}>
                                        Độ chính xác: <strong>{evaluationResults.best_accuracy}%</strong>
                                    </div>
                                </div>
                            )}
                        </div>
                    )}
                </div>

                {/* ML Model Selection Section */}
                <div style={{ background: 'var(--bg-surface)', padding: '2rem', borderRadius: 'var(--radius-lg)', border: '1px solid var(--border-color)' }}>
                    <h3 style={{ fontSize: '1.25rem', fontWeight: '600', marginBottom: '1rem', display: 'flex', alignItems: 'center', gap: '0.75rem', color: 'var(--text-primary)' }}>
                        <Brain size={24} style={{ color: '#10b981' }} />
                        Thiết Lập Mô Hình
                    </h3>
                    <p style={{ fontSize: '0.95rem', color: 'var(--text-secondary)', marginBottom: '1.5rem' }}>
                        Chọn mô hình học máy để dự đoán điểm số cho học sinh:
                    </p>

                    {modelMsg && (
                        <div style={{
                            padding: '1rem',
                            borderRadius: 'var(--radius-md)',
                            marginBottom: '1.5rem',
                            background: modelMsg.startsWith('Lỗi') ? '#fef2f2' : '#f0fdf4',
                            color: modelMsg.startsWith('Lỗi') ? 'var(--danger-color)' : '#166534',
                            border: `1px solid ${modelMsg.startsWith('Lỗi') ? '#fecaca' : '#bbf7d0'}`
                        }}>
                            {modelMsg}
                        </div>
                    )}

                    {loadingModels ? (
                        <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', color: 'var(--text-secondary)' }}>
                            <span className="spinner"></span> Đang tải...
                        </div>
                    ) : modelStatus ? (
                        modelStatus.error ? (
                            <div style={{
                                padding: '1rem',
                                background: '#fef2f2',
                                borderRadius: 'var(--radius-md)',
                                color: 'var(--danger-color)',
                                border: '1px solid #fecaca',
                                display: 'flex',
                                alignItems: 'center',
                                gap: '0.5rem'
                            }}>
                                <AlertCircle size={18} />
                                {modelStatus.error}
                            </div>
                        ) : modelStatus.available_models ? (
                        <div className="grid" style={{ gridTemplateColumns: 'repeat(auto-fit, minmax(250px, 1fr))', gap: '1rem' }}>
                            {modelStatus.available_models.map((model) => (
                                <div
                                    key={model}
                                    style={{
                                        display: 'flex',
                                        alignItems: 'flex-start',
                                        gap: '1rem',
                                        padding: '1.25rem',
                                        background: selectedModel === model ? 'var(--bg-surface)' : 'var(--bg-body)',
                                        borderRadius: 'var(--radius-md)',
                                        border: '2px solid ' + (selectedModel === model ? '#10b981' : 'var(--border-color)'),
                                        cursor: 'pointer',
                                        transition: 'all 0.2s',
                                        position: 'relative'
                                    }}
                                    onClick={() => handleSelectModel(model)}
                                >
                                    <input
                                        type="radio"
                                        name="ml-model"
                                        value={model}
                                        checked={selectedModel === model}
                                        onChange={() => handleSelectModel(model)}
                                        style={{ marginTop: '0.25rem', cursor: 'pointer' }}
                                    />
                                    <div style={{ flex: 1 }}>
                                        <strong style={{ fontSize: '1rem', display: 'block', marginBottom: '0.5rem', color: 'var(--text-primary)' }}>
                                            {model === 'knn' ? 'KNN' : model === 'kernel_regression' ? 'Kernel Regression' : 'LWLR'}
                                        </strong>
                                        {modelStatus.descriptions && modelStatus.descriptions[model] && (
                                            <p style={{ fontSize: '0.85rem', color: 'var(--text-secondary)', margin: 0, lineHeight: '1.5' }}>
                                                {modelStatus.descriptions[model]}
                                            </p>
                                        )}
                                    </div>
                                    {selectedModel === model && (
                                        <div style={{
                                            position: 'absolute',
                                            top: '0.75rem',
                                            right: '0.75rem',
                                            color: '#10b981'
                                        }}>
                                            <CheckCircle size={18} />
                                        </div>
                                    )}
                                </div>
                            ))}
                        </div>
                        ) : (
                            <p style={{ color: 'var(--danger-color)' }}>Không có mô hình khả dụng.</p>
                        )
                    ) : (
                        <p style={{ color: 'var(--danger-color)' }}>Không thể tải trạng thái mô hình.</p>
                    )}
                </div>
            </motion.div>
        </div>
    );
};

export default InstitutionAdminTools;

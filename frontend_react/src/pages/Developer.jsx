import React, { useState, useEffect, useRef } from 'react';
import { useAuth } from '../context/AuthContext';
import axiosClient from '../api/axiosClient';
import { Upload, RefreshCw, AlertCircle, Brain, Database, Clock, FileText, Zap, CheckCircle, Settings, Lightbulb, Save } from 'lucide-react';
import {
    emitMlModelChanged,
    emitMlParametersChanged,
    emitReferenceDatasetChanged,
    emitMlPipelineProcessing,
    emitMlPipelineCompleted,
} from '../utils/eventBus';

const Developer = () => {
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
        emitMlPipelineProcessing({ ...detail, message: text });
    };

    const notifyPipelineCompleted = (detail = {}) => {
        clearPipelineTimer();
        if (detail.error) {
            const errorText = detail.error;
            setPipelineBanner({ type: 'error', text: errorText });
            emitMlPipelineCompleted({ ...detail, message: errorText });
        } else {
            const stats = detail.stats || detail.pipeline || {};
            const processed = stats.processed_users ? ` (${stats.processed_users} người dùng)` : '';
            const successText = detail.message || `Pipeline đã hoàn tất${processed}.`;
            setPipelineBanner({ type: 'success', text: successText });
            emitMlPipelineCompleted({ ...detail, stats, message: successText });
        }
        pipelineTimeoutRef.current = setTimeout(() => setPipelineBanner({ type: '', text: '' }), 5000);
    };

    useEffect(() => {
        return () => clearPipelineTimer();
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, []);

    // Check permissions
    if (!user || (user.role !== 'developer' && user.role !== 'admin')) {
        return (
            <div className="container" style={{ maxWidth: '600px', padding: '4rem 2rem' }}>
                <div className="card" style={{ textAlign: 'center', padding: '3rem' }}>
                    <div style={{ display: 'inline-flex', padding: '1rem', borderRadius: '50%', background: '#fef2f2', marginBottom: '1.5rem' }}>
                        <AlertCircle size={48} style={{ color: 'var(--danger-color)' }} />
                    </div>
                    <h2 style={{ color: 'var(--danger-color)', marginBottom: '1rem', fontSize: '1.5rem' }}>Truy cập bị từ chối</h2>
                    <p style={{ color: 'var(--text-secondary)' }}>Bạn không có quyền truy cập vào trang này.</p>
                </div>
            </div>
        );
    }

    // Fetch model status and dataset status on mount
    useEffect(() => {
        fetchModelStatus();
        fetchDatasetStatus();
        fetchModelParameters();
    }, []);

    const fetchModelStatus = async () => {
        setLoadingModels(true);
        try {
            const res = await axiosClient.get('/developer/model-status');
            setModelStatus(res.data);
            setSelectedModel(res.data.active_model);
        } catch (e) {
            setModelMsg('Lỗi: ' + (e.response?.data?.detail || e.message));
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
            console.log('Saving parameters:', parameters);
            const res = await axiosClient.post('/developer/model-parameters', parameters);
            console.log('Save response:', res.data);
            setParamMessage('✓ ' + (res.data.message || 'Đã cập nhật thông số thành công'));
            emitMlParametersChanged({ parameters: { ...parameters } });
            setTimeout(() => setParamMessage(''), 3000);
            // Backend uses lazy evaluation - predictions updated when user accesses data
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
            console.error('Full error object:', e);
            console.error('Error response:', e.response);
            const errorMsg = e.response?.data?.detail || e.message || 'Lỗi không xác định';
            setParamMessage('Lỗi: ' + errorMsg);
            console.error('Error saving parameters:', e);
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
            emitMlModelChanged({ model: modelName });
            setTimeout(() => setModelMsg(''), 3000);
            // Backend uses lazy evaluation - predictions updated when user accesses data
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
            const errorMsg = e.response?.data?.detail || e.message || 'Lỗi không xác định';
            setModelMsg('Lỗi: ' + errorMsg);
            console.error('Error selecting model:', e);
            notifyPipelineCompleted({ reason: 'model-selection', error: 'Pipeline lỗi: ' + errorMsg });
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
            setMessage({ type: 'success', text: 'Tải lên thành công!' });
            setFile(null);
            notifyPipelineCompleted({ reason: 'dataset-import', stats: res.data.pipeline, message: 'Pipeline đã đồng bộ dataset mới.' });
            emitReferenceDatasetChanged({ summary: res.data.summary || {} });
            // Refresh dataset status after import
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

    return (
        <div className="container" style={{ maxWidth: '1000px', paddingBottom: '3rem' }}>

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

            {/* Dataset Status Section */}
            <div className="card" style={{ marginBottom: '2rem' }}>
                <h3 style={{ fontSize: '1.25rem', fontWeight: '600', marginBottom: '1.25rem', display: 'flex', alignItems: 'center', gap: '0.75rem', color: 'var(--text-primary)' }}>
                    <Database size={24} style={{ color: 'var(--primary-color)' }} />
                    Trạng Thái Bộ Dữ Liệu Tham Chiếu
                </h3>
                {loadingDataset ? (
                    <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', color: 'var(--text-secondary)' }}>
                        <span className="spinner"></span> Đang tải...
                    </div>
                ) : datasetStatus ? (
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
                ) : (
                    <p style={{ color: 'var(--danger-color)' }}>Không thể tải trạng thái dataset.</p>
                )}
            </div>

            {/* Import Excel Section */}
            <div className="card" style={{ marginBottom: '2rem' }}>
                <h3 style={{ fontSize: '1.25rem', fontWeight: '600', marginBottom: '1rem', display: 'flex', alignItems: 'center', gap: '0.75rem', color: 'var(--text-primary)' }}>
                    <Upload size={24} style={{ color: 'var(--primary-color)' }} />
                    Tải Lên Tập Dữ Liệu Tham Chiếu
                </h3>
                <p style={{ fontSize: '0.95rem', color: 'var(--text-secondary)', marginBottom: '1.5rem' }}>
                    Tải lên file chứa dữ liệu tham chiếu cho mô hình học máy. File phải có các cột dạng <code style={{ background: 'var(--bg-body)', padding: '2px 6px', borderRadius: '4px' }}>Môn_Kỳ_Lớp</code> (VD: <code style={{ background: 'var(--bg-body)', padding: '2px 6px', borderRadius: '4px' }}>Toán_1_10</code>).
                </p>

                <div style={{ marginBottom: '1.5rem' }}>
                    <input
                        type="file"
                        accept=".xlsx,.xls,.csv"
                        onChange={handleFileChange}
                        className="input-field"
                        style={{
                            padding: '1rem',
                            border: '2px dashed var(--border-color)',
                            borderRadius: 'var(--radius-md)',
                            width: '100%',
                            cursor: 'pointer',
                            background: 'var(--bg-body)'
                        }}
                    />
                    {file && (
                        <p style={{ marginTop: '0.75rem', fontSize: '0.95rem', color: 'var(--primary-color)', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                            <FileText size={16} />
                            Đã chọn: <strong>{file.name}</strong>
                        </p>
                    )}
                </div>

                <button
                    className="btn btn-primary"
                    onClick={handleUpload}
                    disabled={!file || uploading}
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
                        {summary.warnings && summary.warnings.length > 0 && (
                            <details style={{ marginTop: '1rem' }}>
                                <summary style={{ cursor: 'pointer', color: 'var(--warning-color)', fontWeight: '600' }}>
                                    ⚠️ Cảnh báo ({summary.warnings.length})
                                </summary>
                                <ul style={{ marginTop: '0.5rem', fontSize: '0.9rem', color: 'var(--text-secondary)', paddingLeft: '1.5rem' }}>
                                    {summary.warnings.map((w, i) => <li key={i}>{w}</li>)}
                                </ul>
                            </details>
                        )}
                        {summary.errors && summary.errors.length > 0 && (
                            <details style={{ marginTop: '1rem' }}>
                                <summary style={{ cursor: 'pointer', color: 'var(--danger-color)', fontWeight: '600' }}>
                                    ❗ Lỗi ({summary.errors.length})
                                </summary>
                                <ul style={{ marginTop: '0.5rem', fontSize: '0.9rem', color: 'var(--danger-color)', paddingLeft: '1.5rem' }}>
                                    {summary.errors.map((e, i) => <li key={i}>{e}</li>)}
                                </ul>
                            </details>
                        )}
                    </div>
                )}
            </div>

            {/* Model Parameters Section */}
            <div className="card" style={{ marginBottom: '2rem', borderLeft: '4px solid var(--warning-color)' }}>
                <h3 style={{ fontSize: '1.25rem', fontWeight: '600', marginBottom: '0.5rem', display: 'flex', alignItems: 'center', gap: '0.75rem', color: 'var(--text-primary)' }}>
                    <Settings size={24} style={{ color: 'var(--warning-color)' }} />
                    Cấu Hình Thông Số Mô Hình ML
                </h3>
                <p style={{ fontSize: '0.95rem', color: 'var(--text-secondary)', marginBottom: '1.5rem' }}>
                    Tùy chỉnh các thông số cho các mô hình KNN, Kernel Regression, và LWLR. Những thay đổi sẽ được áp dụng cho cả tính năng đánh giá và dự đoán.
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
                                    <p style={{ fontSize: '0.9rem', color: 'var(--text-secondary)', margin: 0 }}>Số mẫu tham chiếu gần nhất được sử dụng. Phạm vi: 1-100</p>
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
                                <Lightbulb size={14} /> Giá trị mặc định: 15. Giá trị cao hơn = xem xét nhiều lân cận hơn.
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
                                <Lightbulb size={14} /> Giá trị mặc định: 1.25. Giá trị cao hơn = nhân cục gần nhất được tính nhiều hơn.
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
                                <Lightbulb size={14} /> Giá trị mặc định: 3.0. Giá trị cao hơn = cửa sổ rộng hơn, mịn hơn.
                            </div>
                        </div>

                        <button
                            className="btn btn-primary"
                            onClick={handleSaveParameters}
                            disabled={savingParams}
                        >
                            <Save size={18} />
                            {savingParams ? 'Đang lưu...' : 'Lưu Thông Số'}
                        </button>
                    </div>
                )}
            </div>

            {/* Model Evaluation Section */}
            <div className="card" style={{ marginBottom: '2rem', borderLeft: '4px solid var(--accent-color)' }}>
                <h3 style={{ fontSize: '1.25rem', fontWeight: '600', marginBottom: '0.5rem', display: 'flex', alignItems: 'center', gap: '0.75rem', color: 'var(--text-primary)' }}>
                    <Zap size={24} style={{ color: 'var(--accent-color)' }} />
                    Đánh Giá Mô Hình ML
                </h3>
                <p style={{ fontSize: '0.95rem', color: 'var(--text-secondary)', marginBottom: '1.5rem' }}>
                    Đánh giá và so sánh 3 mô hình (KNN, Kernel Regression, LWLR) trên 2 nhiệm vụ dự đoán:
                </p>
                <ul style={{ fontSize: '0.95rem', color: 'var(--text-secondary)', marginBottom: '1.5rem', paddingLeft: '1.5rem' }}>
                    <li>Dữ liệu lớp 10+11 - dự đoán lớp 12</li>
                    <li>Dữ liệu lớp 10 - dự đoán lớp 11</li>
                </ul>

                <button
                    className="btn btn-primary"
                    onClick={handleEvaluateModels}
                    disabled={evaluating || !datasetStatus?.has_dataset}
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
                        {/* Recommendation Box */}
                        {evaluationResults.recommendation && (
                            <div style={{
                                padding: '1.5rem',
                                background: 'var(--bg-surface)',
                                border: '2px solid var(--primary-color)',
                                borderRadius: 'var(--radius-md)',
                                marginBottom: '2rem',
                                boxShadow: 'var(--shadow-sm)'
                            }}>
                                <div style={{ fontSize: '1rem', color: 'var(--text-secondary)', marginBottom: '0.5rem' }}>
                                    <strong>🎯 Mô hình được đề xuất:</strong>
                                </div>
                                <div style={{ fontSize: '1.25rem', fontWeight: '700', color: 'var(--primary-color)' }}>
                                    {evaluationResults.recommendation}
                                </div>
                                <div style={{ fontSize: '0.95rem', color: 'var(--text-secondary)', marginTop: '0.5rem' }}>
                                    Độ chính xác: <strong>{evaluationResults.best_accuracy}%</strong>
                                </div>
                            </div>
                        )}

                        {/* Task 1 Results Table */}
                        {evaluationResults.task_1 && Object.keys(evaluationResults.task_1).length > 0 && (
                            <div style={{ marginBottom: '2rem' }}>
                                <h4 style={{ fontSize: '1.1rem', fontWeight: '600', marginBottom: '1rem', color: 'var(--text-primary)' }}>
                                    Nhiệm vụ 1: Dữ liệu lớp 10+11 - dự đoán lớp 12
                                </h4>
                                <div style={{ overflowX: 'auto', borderRadius: 'var(--radius-md)', border: '1px solid var(--border-color)' }}>
                                    <table style={{
                                        width: '100%',
                                        borderCollapse: 'collapse',
                                        fontSize: '0.95rem'
                                    }}>
                                        <thead style={{ background: 'var(--bg-body)' }}>
                                            <tr>
                                                <th style={{ padding: '1rem', textAlign: 'left', borderBottom: '1px solid var(--border-color)', color: 'var(--text-secondary)' }}>Mô hình</th>
                                                <th style={{ padding: '1rem', textAlign: 'center', borderBottom: '1px solid var(--border-color)', color: 'var(--text-secondary)' }}>MAE</th>
                                                <th style={{ padding: '1rem', textAlign: 'center', borderBottom: '1px solid var(--border-color)', color: 'var(--text-secondary)' }}>MSE</th>
                                                <th style={{ padding: '1rem', textAlign: 'center', borderBottom: '1px solid var(--border-color)', color: 'var(--text-secondary)' }}>RMSE</th>
                                                <th style={{ padding: '1rem', textAlign: 'center', borderBottom: '1px solid var(--border-color)', color: 'var(--primary-color)', fontWeight: '700' }}>Accuracy</th>
                                            </tr>
                                        </thead>
                                        <tbody>
                                            {[
                                                { key: 'knn', label: 'KNN' },
                                                { key: 'kernel_regression', label: 'Kernel Regression' },
                                                { key: 'lwlr', label: 'LWLR' }
                                            ].map(model => {
                                                const metrics = evaluationResults.task_1[model.key];
                                                return (
                                                    <tr key={model.key} style={{ borderBottom: '1px solid var(--border-color)' }}>
                                                        <td style={{ padding: '1rem', fontWeight: '500', color: 'var(--text-primary)' }}>{model.label}</td>
                                                        <td style={{ padding: '1rem', textAlign: 'center', color: 'var(--text-secondary)' }}>
                                                            {metrics ? metrics.mae.toFixed(4) : '-'}
                                                        </td>
                                                        <td style={{ padding: '1rem', textAlign: 'center', color: 'var(--text-secondary)' }}>
                                                            {metrics ? metrics.mse.toFixed(4) : '-'}
                                                        </td>
                                                        <td style={{ padding: '1rem', textAlign: 'center', color: 'var(--text-secondary)' }}>
                                                            {metrics ? metrics.rmse.toFixed(4) : '-'}
                                                        </td>
                                                        <td style={{
                                                            padding: '1rem',
                                                            textAlign: 'center',
                                                            background: metrics ? (metrics.accuracy >= 90 ? '#f0fdf4' : metrics.accuracy >= 80 ? '#fefce8' : '#fef2f2') : 'transparent',
                                                            fontWeight: '600',
                                                            color: metrics ? (metrics.accuracy >= 90 ? '#166534' : metrics.accuracy >= 80 ? '#854d0e' : 'var(--danger-color)') : 'var(--text-tertiary)'
                                                        }}>
                                                            {metrics ? metrics.accuracy.toFixed(2) + '%' : '-'}
                                                        </td>
                                                    </tr>
                                                );
                                            })}
                                        </tbody>
                                    </table>
                                </div>
                            </div>
                        )}

                        {/* Task 2 Results Table */}
                        {evaluationResults.task_2 && Object.keys(evaluationResults.task_2).length > 0 && (
                            <div>
                                <h4 style={{ fontSize: '1.1rem', fontWeight: '600', marginBottom: '1rem', color: 'var(--text-primary)' }}>
                                    Nhiệm vụ 2: Dữ liệu lớp 10 - dự đoán lớp 11
                                </h4>
                                <div style={{ overflowX: 'auto', borderRadius: 'var(--radius-md)', border: '1px solid var(--border-color)' }}>
                                    <table style={{
                                        width: '100%',
                                        borderCollapse: 'collapse',
                                        fontSize: '0.95rem'
                                    }}>
                                        <thead style={{ background: 'var(--bg-body)' }}>
                                            <tr>
                                                <th style={{ padding: '1rem', textAlign: 'left', borderBottom: '1px solid var(--border-color)', color: 'var(--text-secondary)' }}>Mô hình</th>
                                                <th style={{ padding: '1rem', textAlign: 'center', borderBottom: '1px solid var(--border-color)', color: 'var(--text-secondary)' }}>MAE</th>
                                                <th style={{ padding: '1rem', textAlign: 'center', borderBottom: '1px solid var(--border-color)', color: 'var(--text-secondary)' }}>MSE</th>
                                                <th style={{ padding: '1rem', textAlign: 'center', borderBottom: '1px solid var(--border-color)', color: 'var(--text-secondary)' }}>RMSE</th>
                                                <th style={{ padding: '1rem', textAlign: 'center', borderBottom: '1px solid var(--border-color)', color: 'var(--primary-color)', fontWeight: '700' }}>Accuracy</th>
                                            </tr>
                                        </thead>
                                        <tbody>
                                            {[
                                                { key: 'knn', label: 'KNN' },
                                                { key: 'kernel_regression', label: 'Kernel Regression' },
                                                { key: 'lwlr', label: 'LWLR' }
                                            ].map(model => {
                                                const metrics = evaluationResults.task_2[model.key];
                                                return (
                                                    <tr key={model.key} style={{ borderBottom: '1px solid var(--border-color)' }}>
                                                        <td style={{ padding: '1rem', fontWeight: '500', color: 'var(--text-primary)' }}>{model.label}</td>
                                                        <td style={{ padding: '1rem', textAlign: 'center', color: 'var(--text-secondary)' }}>
                                                            {metrics ? metrics.mae.toFixed(4) : '-'}
                                                        </td>
                                                        <td style={{ padding: '1rem', textAlign: 'center', color: 'var(--text-secondary)' }}>
                                                            {metrics ? metrics.mse.toFixed(4) : '-'}
                                                        </td>
                                                        <td style={{ padding: '1rem', textAlign: 'center', color: 'var(--text-secondary)' }}>
                                                            {metrics ? metrics.rmse.toFixed(4) : '-'}
                                                        </td>
                                                        <td style={{
                                                            padding: '1rem',
                                                            textAlign: 'center',
                                                            background: metrics ? (metrics.accuracy >= 90 ? '#f0fdf4' : metrics.accuracy >= 80 ? '#fefce8' : '#fef2f2') : 'transparent',
                                                            fontWeight: '600',
                                                            color: metrics ? (metrics.accuracy >= 90 ? '#166534' : metrics.accuracy >= 80 ? '#854d0e' : 'var(--danger-color)') : 'var(--text-tertiary)'
                                                        }}>
                                                            {metrics ? metrics.accuracy.toFixed(2) + '%' : '-'}
                                                        </td>
                                                    </tr>
                                                );
                                            })}
                                        </tbody>
                                    </table>
                                </div>
                            </div>
                        )}

                        {/* Dataset Info */}
                        <div style={{ marginTop: '1.5rem', padding: '1rem', background: 'var(--bg-body)', borderRadius: 'var(--radius-md)', fontSize: '0.9rem', color: 'var(--text-secondary)', border: '1px solid var(--border-color)' }}>
                            <strong style={{ color: 'var(--text-primary)' }}>ℹ️ Thông tin đánh giá:</strong>
                            <ul style={{ margin: '0.5rem 0 0 1rem', paddingLeft: '1rem' }}>
                                <li>Bộ dữ liệu: {evaluationResults.dataset_size} mẫu</li>
                                <li>Nhiệm vụ 1 (Predict 12): {evaluationResults.task_1_train_samples} train + {evaluationResults.task_1_test_samples} test</li>
                                <li>Nhiệm vụ 2 (Predict 11): {evaluationResults.task_2_train_samples} train + {evaluationResults.task_2_test_samples} test</li>
                            </ul>
                        </div>
                    </div>
                )}
            </div>

            {/* ML Model Selection Section */}
            <div className="card">
                <h3 style={{ fontSize: '1.25rem', fontWeight: '600', marginBottom: '1rem', display: 'flex', alignItems: 'center', gap: '0.75rem', color: 'var(--text-primary)' }}>
                    <Brain size={24} style={{ color: 'var(--primary-color)' }} />
                    Thiết Lập Mô Hình
                </h3>
                <p style={{ fontSize: '0.95rem', color: 'var(--text-secondary)', marginBottom: '1.5rem' }}>
                    Chọn mô hình học máy để dự đoán điểm số:
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
                                    border: '2px solid ' + (selectedModel === model ? 'var(--primary-color)' : 'var(--border-color)'),
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
                                        color: 'var(--primary-color)'
                                    }}>
                                        <CheckCircle size={18} />
                                    </div>
                                )}
                            </div>
                        ))}
                    </div>
                ) : (
                    <p style={{ color: 'var(--danger-color)' }}>Không thể tải trạng thái mô hình.</p>
                )}
            </div>
        </div>
    );
};

export default Developer;

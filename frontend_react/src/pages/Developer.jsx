import React, { useState, useEffect, useRef } from 'react';
import * as XLSX from 'xlsx';
import { useAuth } from '../context/AuthContext';
import axiosClient from '../api/axiosClient';
import { Upload, RefreshCw, AlertCircle, Brain, Database, Clock, FileText, Zap, CheckCircle, Settings, Lightbulb, Save, Download } from 'lucide-react';
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
    const [originalParameters, setOriginalParameters] = useState({ knn_n: 15, kr_bandwidth: 1.25, lwlr_tau: 3.0 });
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
            setOriginalParameters(res.data); // Save original values
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
            setOriginalParameters(parameters); // Update original values after successful save
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
            if (ext !== 'xlsx' && ext !== 'xls') {
                setMessage({ type: 'error', text: 'Chỉ chấp nhận file Excel (.xlsx, .xls)' });
                return;
            }
            setFile(selectedFile);
            setMessage({ type: '', text: '' });
        }
    };

    const handleDownloadTemplate = () => {
        // Template columns
        const columns = [
            'Maths_1_10', 'Literature_1_10', 'Physics_1_10', 'Chemistry_1_10', 'Biology_1_10', 'History_1_10', 'Geography_1_10', 'English_1_10', 'Civic Education_1_10',
            'Maths_2_10', 'Literature_2_10', 'Physics_2_10', 'Chemistry_2_10', 'Biology_2_10', 'History_2_10', 'Geography_2_10', 'English_2_10', 'Civic Education_2_10',
            'Maths_1_11', 'Literature_1_11', 'Physics_1_11', 'Chemistry_1_11', 'Biology_1_11', 'History_1_11', 'Geography_1_11', 'English_1_11', 'Civic Education_1_11',
            'Maths_2_11', 'Literature_2_11', 'Physics_2_11', 'Chemistry_2_11', 'Biology_2_11', 'History_2_11', 'Geography_2_11', 'English_2_11', 'Civic Education_2_11',
            'Maths_1_12', 'Literature_1_12', 'Physics_1_12', 'Chemistry_1_12', 'Biology_1_12', 'History_1_12', 'Geography_1_12', 'English_1_12', 'Civic Education_1_12',
            'Maths_2_12', 'Literature_2_12', 'Physics_2_12', 'Chemistry_2_12', 'Biology_2_12', 'History_2_12', 'Geography_2_12', 'English_2_12', 'Civic Education_2_12'
        ];

        // Create Excel file using xlsx library
        const exampleRow = columns.map(() => '8.5');
        const ws = XLSX.utils.aoa_to_sheet([columns, exampleRow]);
        const wb = XLSX.utils.book_new();
        XLSX.utils.book_append_sheet(wb, ws, 'Scores');
        XLSX.writeFile(wb, 'edutwin_template.xlsx');
    };

    const handleUpload = async () => {
        if (!file) {
            setMessage({ type: 'error', text: 'Vui lòng chọn file trước khi upload.' });
            return;
        }

        setUploading(true);
        setMessage({ type: '', text: '' });
        setSummary(null);
        notifyPipelineProcessing({ reason: 'dataset-import', message: 'Đang import dataset và cập nhật pipeline...' });

        const formData = new FormData();
        formData.append('file', file);

        try {
            const res = await axiosClient.post('/developer/import-excel', formData, {
                headers: { 'Content-Type': 'multipart/form-data' },
                timeout: 90000
            });
            setSummary(res.data.summary || {});
            setMessage({ type: 'success', text: 'Import thành công!' });
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
                                    <strong style={{ fontSize: '1rem', color: 'var(--text-secondary)' }}>Lần import gần nhất:</strong>
                                </div>
                                <div style={{ fontSize: '0.95rem', color: 'var(--text-primary)', lineHeight: '1.8' }}>
                                    <div><span style={{ color: 'var(--text-secondary)' }}>File:</span> <strong>{datasetStatus.last_import.filename}</strong></div>
                                    <div><span style={{ color: 'var(--text-secondary)' }}>Thời gian:</span> {new Date(datasetStatus.last_import.created_at).toLocaleString('vi-VN')}</div>
                                    <div><span style={{ color: 'var(--text-secondary)' }}>Đã import:</span> {datasetStatus.last_import.imported_rows.toLocaleString('vi-VN')} / {datasetStatus.last_import.total_rows.toLocaleString('vi-VN')} dòng</div>
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
                                Chưa có bộ dữ liệu tham chiếu. Vui lòng import file Excel để sử dụng tính năng dự đoán.
                            </div>
                        )}
                    </div>
                ) : (
                    <p style={{ color: 'var(--danger-color)' }}>Không thể tải trạng thái dataset.</p>
                )}
            </div>

            {/* Import Excel Section */}
            <div className="card" style={{
                marginBottom: '2rem',
                background: 'white',
                border: '1px solid var(--border-color)',
                boxShadow: '0 1px 3px rgba(0, 0, 0, 0.1)',
                overflow: 'hidden',
                padding: 0
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
                            padding: '0.5rem',
                            borderRadius: '8px',
                            display: 'flex',
                            alignItems: 'center',
                            justifyContent: 'center',
                            color: 'var(--primary-color)'
                        }}>
                            <Upload size={20} />
                        </div>
                        <div>
                            <h3 style={{ fontSize: '1rem', fontWeight: '600', margin: 0, color: 'var(--text-primary)' }}>
                                Tải Lên Tập Dữ Liệu Tham Chiếu
                            </h3>
                            <p style={{ fontSize: '0.85rem', color: 'var(--text-secondary)', margin: 0 }}>
                                Tải lên file Excel theo định dạng mẫu được cung cấp
                            </p>
                        </div>
                    </div>
                    <button
                        className="btn btn-ghost"
                        onClick={handleDownloadTemplate}
                        style={{
                            fontSize: '0.85rem',
                            display: 'flex',
                            alignItems: 'center',
                            gap: '0.5rem',
                            color: 'var(--primary-color)',
                            fontWeight: '500'
                        }}
                    >
                        <Download size={16} />
                        Tải file định dạng mẫu
                    </button>
                </div>

                <div style={{ padding: '2rem' }}>
                    {!file ? (
                        <>
                            <input
                                type="file"
                                accept=".xlsx,.xls"
                                onChange={handleFileChange}
                                className="input-field"
                                id="dataset-upload-input"
                                style={{ display: 'none' }}
                            />
                            <label
                                htmlFor="dataset-upload-input"
                                style={{
                                    display: 'flex',
                                    flexDirection: 'column',
                                    alignItems: 'center',
                                    justifyContent: 'center',
                                    padding: '3rem',
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
                                    <Database size={24} />
                                </div>
                                <div style={{ textAlign: 'center' }}>
                                    <span style={{ display: 'block', fontSize: '1rem', fontWeight: '600', color: 'var(--text-primary)', marginBottom: '0.25rem' }}>
                                        Click để tải lên tập dữ liệu
                                    </span>
                                    <span style={{ fontSize: '0.85rem', color: 'var(--text-tertiary)' }}>
                                        Hỗ trợ .xlsx, .xls
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
                            <h4 style={{ margin: '0 0 0.25rem 0', color: 'var(--text-primary)', fontWeight: '600' }}>{file.name}</h4>
                            <p style={{ margin: '0 0 1.5rem 0', color: 'var(--text-secondary)', fontSize: '0.85rem' }}>
                                {(file.size / 1024).toFixed(1)} KB
                            </p>
                            <div style={{ display: 'flex', gap: '0.75rem' }}>
                                <button
                                    onClick={() => setFile(null)}
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
                                    onClick={handleUpload}
                                    disabled={uploading}
                                    className="btn btn-primary"
                                    style={{ padding: '0.5rem 1.5rem' }}
                                >
                                    {uploading ? <RefreshCw size={18} className="spin" /> : <Upload size={18} />}
                                    <span style={{ marginLeft: '0.5rem' }}>{uploading ? 'Đang upload...' : 'Upload Dataset'}</span>
                                </button>
                            </div>
                        </div>
                    )}

                    {summary && (
                        <div style={{ marginTop: '1.5rem', padding: '1.25rem', background: 'var(--bg-body)', borderRadius: 'var(--radius-md)', border: '1px solid var(--border-color)' }}>
                            <h4 style={{ fontSize: '1rem', fontWeight: '600', marginBottom: '1rem', color: 'var(--text-primary)' }}>📊 Kết quả Import:</h4>
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
                                        style={{
                                            width: '100px',
                                            textAlign: 'center',
                                            borderColor: parameters.knn_n !== originalParameters.knn_n ? '#dc2626' : 'var(--border-color)',
                                            borderWidth: parameters.knn_n !== originalParameters.knn_n ? '2px' : '1px',
                                            backgroundColor: parameters.knn_n !== originalParameters.knn_n ? '#fef2f2' : 'transparent',
                                            boxShadow: parameters.knn_n !== originalParameters.knn_n ? '0 0 0 3px rgba(220, 38, 38, 0.1)' : 'none'
                                        }}
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
                                        style={{
                                            width: '100px',
                                            textAlign: 'center',
                                            borderColor: parameters.kr_bandwidth !== originalParameters.kr_bandwidth ? '#dc2626' : 'var(--border-color)',
                                            borderWidth: parameters.kr_bandwidth !== originalParameters.kr_bandwidth ? '2px' : '1px',
                                            backgroundColor: parameters.kr_bandwidth !== originalParameters.kr_bandwidth ? '#fef2f2' : 'transparent',
                                            boxShadow: parameters.kr_bandwidth !== originalParameters.kr_bandwidth ? '0 0 0 3px rgba(220, 38, 38, 0.1)' : 'none'
                                        }}
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
                                        style={{
                                            width: '100px',
                                            textAlign: 'center',
                                            borderColor: parameters.lwlr_tau !== originalParameters.lwlr_tau ? '#dc2626' : 'var(--border-color)',
                                            borderWidth: parameters.lwlr_tau !== originalParameters.lwlr_tau ? '2px' : '1px',
                                            backgroundColor: parameters.lwlr_tau !== originalParameters.lwlr_tau ? '#fef2f2' : 'transparent',
                                            boxShadow: parameters.lwlr_tau !== originalParameters.lwlr_tau ? '0 0 0 3px rgba(220, 38, 38, 0.1)' : 'none'
                                        }}
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

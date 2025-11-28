import React, { useState, useEffect, useRef } from 'react';
import { useAuth } from '../context/AuthContext';
import axiosClient from '../api/axiosClient';
import { Upload, RefreshCw, AlertCircle, Brain, Database, Clock, FileText, Zap } from 'lucide-react';
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
    const [rebuilding, setRebuilding] = useState(false);
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
            <div style={{ maxWidth: '600px', margin: '0 auto', padding: '2rem' }}>
                <div className="card" style={{ textAlign: 'center', padding: '3rem' }}>
                    <AlertCircle size={48} color="#c62828" style={{ marginBottom: '1rem' }} />
                    <h2 style={{ color: '#c62828', marginBottom: '1rem' }}>Truy cập bị từ chối</h2>
                    <p style={{ color: '#666' }}>Bạn không có quyền truy cập vào trang này.</p>
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
            notifyPipelineCompleted({ reason: 'model-parameters', stats: res.data.pipeline, message: 'Pipeline đã cập nhật theo thông số mới.' });
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
            notifyPipelineCompleted({ reason: 'model-selection', stats: res.data.pipeline, message: 'Pipeline đã áp dụng mô hình mới.' });
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

    const handleRebuildEmbeddings = async () => {
        if (!window.confirm('Bạn có chắc muốn tái xây dựng vector database?')) return;

        setRebuilding(true);
        setMessage({ type: '', text: '' });

        try {
            await axiosClient.post('/developer/rebuild-embeddings', {}, { timeout: 90000 });
            setMessage({ type: 'success', text: 'Đã tái xây dựng vector database thành công!' });
        } catch (e) {
            setMessage({ type: 'error', text: 'Lỗi: ' + (e.response?.data?.detail || e.message) });
        } finally {
            setRebuilding(false);
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
        <div style={{ maxWidth: '900px', margin: '0 auto' }}>

            {message.text && (
                <div style={{
                    padding: '1rem',
                    borderRadius: '8px',
                    marginBottom: '1.5rem',
                    background: message.type === 'error' ? '#ffebee' : message.type === 'success' ? '#e8f5e9' : '#e3f2fd',
                    color: message.type === 'error' ? '#c62828' : message.type === 'success' ? '#2e7d32' : '#1565c0'
                }}>
                    {message.text}
                </div>
            )}

            {pipelineBanner.text && (
                <div style={{
                    padding: '1rem',
                    borderRadius: '8px',
                    marginBottom: '1.5rem',
                    background: pipelineBanner.type === 'error' ? '#ffebee' : pipelineBanner.type === 'success' ? '#e8f5e9' : '#fffde7',
                    color: pipelineBanner.type === 'error' ? '#c62828' : pipelineBanner.type === 'success' ? '#2e7d32' : '#8d6e63'
                }}>
                    {pipelineBanner.text}
                </div>
            )}

            {/* Dataset Status Section */}
            <div className="card" style={{ marginBottom: '2rem' }}>
                <h3 style={{ fontSize: '1.3rem', fontWeight: '600', marginBottom: '1rem' }}>
                    <Database size={20} style={{ display: 'inline', marginRight: '0.5rem' }} />
                    Trạng Thái Bộ Dữ Liệu Tham Chiếu
                </h3>
                {loadingDataset ? (
                    <p style={{ color: '#999' }}>Đang tải...</p>
                ) : datasetStatus ? (
                    <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
                        <div style={{ 
                            padding: '1rem', 
                            background: datasetStatus.has_dataset ? '#e8f5e9' : '#fff3e0', 
                            borderRadius: '8px',
                            border: `2px solid ${datasetStatus.has_dataset ? '#4caf50' : '#ff9800'}`
                        }}>
                            <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginBottom: '0.5rem' }}>
                                <strong style={{ fontSize: '1.1rem' }}>
                                    {datasetStatus.has_dataset ? '✓ Đã có bộ dữ liệu' : '⚠ Chưa có bộ dữ liệu'}
                                </strong>
                            </div>
                            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: '1rem', marginTop: '1rem' }}>
                                <div>
                                    <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginBottom: '0.25rem' }}>
                                        <FileText size={16} color="#666" />
                                        <span style={{ fontSize: '0.9rem', color: '#666' }}>Số mẫu tham chiếu:</span>
                                    </div>
                                    <strong style={{ fontSize: '1.2rem', color: '#2c3e50' }}>
                                        {datasetStatus.sample_count.toLocaleString('vi-VN')}
                                    </strong>
                                </div>
                                <div>
                                    <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginBottom: '0.25rem' }}>
                                        <Database size={16} color="#666" />
                                        <span style={{ fontSize: '0.9rem', color: '#666' }}>Kích thước (ước tính):</span>
                                    </div>
                                    <strong style={{ fontSize: '1.2rem', color: '#2c3e50' }}>
                                        {datasetStatus.size_mb} MB
                                    </strong>
                                </div>
                            </div>
                        </div>
                        
                        {datasetStatus.last_import && (
                            <div style={{ 
                                padding: '1rem', 
                                background: '#f5f5f5', 
                                borderRadius: '8px',
                                border: '1px solid #e0e0e0'
                            }}>
                                <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginBottom: '0.75rem' }}>
                                    <Clock size={16} color="#666" />
                                    <strong style={{ fontSize: '0.95rem', color: '#666' }}>Lần import gần nhất:</strong>
                                </div>
                                <div style={{ fontSize: '0.9rem', color: '#555', lineHeight: '1.6' }}>
                                    <div><strong>File:</strong> {datasetStatus.last_import.filename}</div>
                                    <div><strong>Thời gian:</strong> {new Date(datasetStatus.last_import.created_at).toLocaleString('vi-VN')}</div>
                                    <div><strong>Đã import:</strong> {datasetStatus.last_import.imported_rows.toLocaleString('vi-VN')} / {datasetStatus.last_import.total_rows.toLocaleString('vi-VN')} dòng</div>
                                    {datasetStatus.last_import.skipped_rows > 0 && (
                                        <div style={{ color: '#f57c00' }}>
                                            <strong>Đã bỏ qua:</strong> {datasetStatus.last_import.skipped_rows.toLocaleString('vi-VN')} dòng
                                        </div>
                                    )}
                                </div>
                            </div>
                        )}
                        
                        {!datasetStatus.has_dataset && (
                            <div style={{ 
                                padding: '0.75rem', 
                                background: '#fff3e0', 
                                borderRadius: '6px',
                                color: '#e65100',
                                fontSize: '0.9rem'
                            }}>
                                ⚠️ Chưa có bộ dữ liệu tham chiếu. Vui lòng import file Excel để sử dụng tính năng dự đoán.
                            </div>
                        )}
                    </div>
                ) : (
                    <p style={{ color: '#c62828' }}>Không thể tải trạng thái dataset.</p>
                )}
            </div>

            {/* Import Excel Section */}
            <div className="card" style={{ marginBottom: '2rem' }}>
                <h3 style={{ fontSize: '1.3rem', fontWeight: '600', marginBottom: '1rem' }}>
                    📥 Import Dataset Tham Chiếu
                </h3>
                <p style={{ fontSize: '0.9rem', color: '#666', marginBottom: '1.5rem' }}>
                    Upload file Excel chứa dữ liệu tham chiếu cho mô hình học máy. File phải có các cột dạng <code>Môn_Kỳ_Lớp</code> (VD: <code>Toán_1_10</code>).
                </p>

                <div style={{ marginBottom: '1.5rem' }}>
                    <input
                        type="file"
                        accept=".xlsx,.xls"
                        onChange={handleFileChange}
                        style={{
                            padding: '0.75rem',
                            border: '2px dashed #ccc',
                            borderRadius: '8px',
                            width: '100%',
                            cursor: 'pointer'
                        }}
                    />
                    {file && (
                        <p style={{ marginTop: '0.5rem', fontSize: '0.9rem', color: '#555' }}>
                            Đã chọn: <strong>{file.name}</strong>
                        </p>
                    )}
                </div>

                <button
                    className="btn btn-primary"
                    onClick={handleUpload}
                    disabled={!file || uploading}
                    style={{ opacity: (!file || uploading) ? 0.5 : 1 }}
                >
                    <Upload size={18} />
                    {uploading ? 'Đang upload...' : 'Upload Dataset'}
                </button>

                {summary && (
                    <div style={{ marginTop: '1.5rem', padding: '1rem', background: '#f5f5f5', borderRadius: '8px' }}>
                        <h4 style={{ fontSize: '1rem', fontWeight: '600', marginBottom: '0.75rem' }}>📊 Kết quả Import:</h4>
                        <ul style={{ margin: 0, paddingLeft: '1.5rem', fontSize: '0.9rem' }}>
                            <li>Tổng số dòng hợp lệ: <strong>{summary.total_rows || 0}</strong></li>
                            <li>Số mẫu tham chiếu: <strong>{summary.reference_samples || 0}</strong></li>
                            {summary.cleared_existing && <li style={{ color: '#f57c00' }}>Đã thay thế dữ liệu cũ</li>}
                        </ul>
                        {summary.warnings && summary.warnings.length > 0 && (
                            <details style={{ marginTop: '0.75rem' }}>
                                <summary style={{ cursor: 'pointer', color: '#f57c00', fontWeight: '600' }}>
                                    ⚠️ Cảnh báo ({summary.warnings.length})
                                </summary>
                                <ul style={{ marginTop: '0.5rem', fontSize: '0.85rem', color: '#666' }}>
                                    {summary.warnings.map((w, i) => <li key={i}>{w}</li>)}
                                </ul>
                            </details>
                        )}
                        {summary.errors && summary.errors.length > 0 && (
                            <details style={{ marginTop: '0.75rem' }}>
                                <summary style={{ cursor: 'pointer', color: '#c62828', fontWeight: '600' }}>
                                    ❗ Lỗi ({summary.errors.length})
                                </summary>
                                <ul style={{ marginTop: '0.5rem', fontSize: '0.85rem', color: '#c62828' }}>
                                    {summary.errors.map((e, i) => <li key={i}>{e}</li>)}
                                </ul>
                            </details>
                        )}
                    </div>
                )}
            </div>

            {/* Rebuild Embeddings Section */}
            <div className="card" style={{ marginBottom: '2rem' }}>
                <h3 style={{ fontSize: '1.3rem', fontWeight: '600', marginBottom: '1rem' }}>
                    🔄 Tái Xây Dựng Vector Database
                </h3>
                <p style={{ fontSize: '0.9rem', color: '#666', marginBottom: '1.5rem' }}>
                    Tái xây dựng vector database từ dữ liệu hiện có. Thao tác này có thể mất vài phút.
                </p>

                <button
                    className="btn btn-outline"
                    onClick={handleRebuildEmbeddings}
                    disabled={rebuilding}
                    style={{
                        borderColor: '#2196f3',
                        color: '#2196f3',
                        opacity: rebuilding ? 0.5 : 1
                    }}
                >
                    <RefreshCw size={18} />
                    {rebuilding ? 'Đang xây dựng...' : 'Rebuild Embeddings'}
                </button>
            </div>

            {/* Model Parameters Section */}
            <div className="card" style={{ marginBottom: '2rem', backgroundColor: '#fffef2', borderLeft: '4px solid #ff9800' }}>
                <h3 style={{ fontSize: '1.3rem', fontWeight: '600', marginBottom: '0.5rem' }}>
                    ⚙️ Cấu Hình Thông Số Mô Hình ML
                </h3>
                <p style={{ fontSize: '0.9rem', color: '#666', marginBottom: '1.5rem' }}>
                    Tùy chỉnh các thông số cho các mô hình KNN, Kernel Regression, và LWLR. Những thay đổi sẽ được áp dụng cho cả tính năng đánh giá và dự đoán.
                </p>

                {paramMessage && (
                    <div style={{
                        padding: '0.75rem',
                        borderRadius: '8px',
                        marginBottom: '1rem',
                        background: paramMessage.startsWith('Lỗi') ? '#ffebee' : '#e8f5e9',
                        color: paramMessage.startsWith('Lỗi') ? '#c62828' : '#2e7d32'
                    }}>
                        {paramMessage}
                    </div>
                )}

                {loadingParams ? (
                    <p style={{ color: '#999' }}>Đang tải thông số...</p>
                ) : (
                    <div>
                        {/* KNN Parameter */}
                        <div style={{
                            marginBottom: '1.25rem',
                            padding: '1rem',
                            background: '#f9f9f9',
                            borderRadius: '8px',
                            border: '1px solid #e0e0e0'
                        }}>
                            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.75rem' }}>
                                <div>
                                    <strong style={{ display: 'block', fontSize: '1rem', marginBottom: '0.25rem' }}>KNN - Số lân cận (n)</strong>
                                    <p style={{ fontSize: '0.85rem', color: '#666', margin: 0 }}>Số mẫu tham chiếu gần nhất được sử dụng. Phạm vi: 1-100</p>
                                </div>
                                <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                                    <input
                                        type="number"
                                        min="1"
                                        max="100"
                                        value={parameters.knn_n}
                                        onChange={(e) => setParameters({...parameters, knn_n: parseInt(e.target.value) || 15})}
                                        style={{
                                            padding: '0.5rem',
                                            borderRadius: '6px',
                                            border: '1px solid #ccc',
                                            width: '80px',
                                            fontSize: '1rem'
                                        }}
                                    />
                                </div>
                            </div>
                            <div style={{ fontSize: '0.8rem', color: '#ff9800' }}>
                                💡 Giá trị mặc định: 15. Giá trị cao hơn = xem xét nhiều lân cận hơn.
                            </div>
                        </div>

                        {/* Kernel Regression Parameter */}
                        <div style={{
                            marginBottom: '1.25rem',
                            padding: '1rem',
                            background: '#f9f9f9',
                            borderRadius: '8px',
                            border: '1px solid #e0e0e0'
                        }}>
                            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.75rem' }}>
                                <div>
                                    <strong style={{ display: 'block', fontSize: '1rem', marginBottom: '0.25rem' }}>Kernel Regression - Bandwidth (σ)</strong>
                                    <p style={{ fontSize: '0.85rem', color: '#666', margin: 0 }}>Bề rộng hạt nhân Gaussian. Phạm vi: 0.1-10.0</p>
                                </div>
                                <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                                    <input
                                        type="number"
                                        min="0.1"
                                        max="10"
                                        step="0.05"
                                        value={parameters.kr_bandwidth}
                                        onChange={(e) => setParameters({...parameters, kr_bandwidth: parseFloat(e.target.value) || 1.25})}
                                        style={{
                                            padding: '0.5rem',
                                            borderRadius: '6px',
                                            border: '1px solid #ccc',
                                            width: '90px',
                                            fontSize: '1rem'
                                        }}
                                    />
                                </div>
                            </div>
                            <div style={{ fontSize: '0.8rem', color: '#ff9800' }}>
                                💡 Giá trị mặc định: 1.25. Giá trị cao hơn = nhân cục gần nhất được tính nhiều hơn.
                            </div>
                        </div>

                        {/* LWLR Parameter */}
                        <div style={{
                            marginBottom: '1.5rem',
                            padding: '1rem',
                            background: '#f9f9f9',
                            borderRadius: '8px',
                            border: '1px solid #e0e0e0'
                        }}>
                            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.75rem' }}>
                                <div>
                                    <strong style={{ display: 'block', fontSize: '1rem', marginBottom: '0.25rem' }}>LWLR - Tham số cửa sổ (τ)</strong>
                                    <p style={{ fontSize: '0.85rem', color: '#666', margin: 0 }}>Điều khiển kích thước cửa sổ bộ lọc. Phạm vi: 0.5-10.0</p>
                                </div>
                                <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                                    <input
                                        type="number"
                                        min="0.5"
                                        max="10"
                                        step="0.1"
                                        value={parameters.lwlr_tau}
                                        onChange={(e) => setParameters({...parameters, lwlr_tau: parseFloat(e.target.value) || 3.0})}
                                        style={{
                                            padding: '0.5rem',
                                            borderRadius: '6px',
                                            border: '1px solid #ccc',
                                            width: '90px',
                                            fontSize: '1rem'
                                        }}
                                    />
                                </div>
                            </div>
                            <div style={{ fontSize: '0.8rem', color: '#ff9800' }}>
                                💡 Giá trị mặc định: 3.0. Giá trị cao hơn = cửa sổ rộng hơn, mịn hơn.
                            </div>
                        </div>

                        <button
                            className="btn btn-primary"
                            onClick={handleSaveParameters}
                            disabled={savingParams}
                            style={{ opacity: savingParams ? 0.5 : 1 }}
                        >
                            💾 {savingParams ? 'Đang lưu...' : 'Lưu Thông Số'}
                        </button>
                    </div>
                )}
            </div>

            {/* Model Evaluation Section */}
            <div className="card" style={{ marginBottom: '2rem', backgroundColor: '#f8f9fa', borderLeft: '4px solid #7c3aed' }}>
                <h3 style={{ fontSize: '1.3rem', fontWeight: '600', marginBottom: '0.5rem' }}>
                    <Zap size={20} style={{ display: 'inline', marginRight: '0.5rem', color: '#7c3aed' }} />
                    Đánh Giá Mô Hình ML
                </h3>
                <p style={{ fontSize: '0.9rem', color: '#666', marginBottom: '1.5rem' }}>
                    Đánh giá và so sánh 3 mô hình (KNN, Kernel Regression, LWLR) trên 2 nhiệm vụ dự đoán:
                </p>
                <ul style={{ fontSize: '0.9rem', color: '#666', marginBottom: '1.5rem', paddingLeft: '1.5rem' }}>
                    <li>Dữ liệu lớp 10+11 - dự đoán lớp 12</li>
                    <li>Dữ liệu lớp 10 - dự đoán lớp 11</li>
                </ul>

                <button
                    className="btn btn-primary"
                    onClick={handleEvaluateModels}
                    disabled={evaluating || !datasetStatus?.has_dataset}
                    style={{ opacity: (evaluating || !datasetStatus?.has_dataset) ? 0.5 : 1 }}
                >
                    <Zap size={18} />
                    {evaluating ? 'Đang đánh giá...' : 'Đánh Giá Mô Hình'}
                </button>

                {evaluationMessage && (
                    <div style={{
                        padding: '1rem',
                        borderRadius: '8px',
                        marginTop: '1rem',
                        background: evaluationMessage.startsWith('Lỗi') ? '#ffebee' : '#e8f5e9',
                        color: evaluationMessage.startsWith('Lỗi') ? '#c62828' : '#2e7d32'
                    }}>
                        {evaluationMessage}
                    </div>
                )}

                {evaluationResults && !evaluationResults.error && (
                    <div style={{ marginTop: '1.5rem' }}>
                        {/* Recommendation Box */}
                        {evaluationResults.recommendation && (
                            <div style={{
                                padding: '1rem',
                                background: '#e3f2fd',
                                border: '2px solid #2196f3',
                                borderRadius: '8px',
                                marginBottom: '1.5rem'
                            }}>
                                <div style={{ fontSize: '0.9rem', color: '#666', marginBottom: '0.5rem' }}>
                                    <strong>🎯 Mô hình được đề xuất:</strong>
                                </div>
                                <div style={{ fontSize: '1.1rem', fontWeight: '600', color: '#2196f3' }}>
                                    {evaluationResults.recommendation}
                                </div>
                                <div style={{ fontSize: '0.85rem', color: '#666', marginTop: '0.5rem' }}>
                                    Độ chính xác: <strong>{evaluationResults.best_accuracy}%</strong>
                                </div>
                            </div>
                        )}

                        {/* Task 1 Results Table */}
                        {evaluationResults.task_1 && Object.keys(evaluationResults.task_1).length > 0 && (
                            <div style={{ marginBottom: '1.5rem' }}>
                                <h4 style={{ fontSize: '0.95rem', fontWeight: '600', marginBottom: '0.75rem', color: '#2c3e50' }}>
                                    Nhiệm vụ 1: Dữ liệu lớp 10+11 - dự đoán lớp 12
                                </h4>
                                <div style={{ overflowX: 'auto' }}>
                                    <table style={{
                                        width: '100%',
                                        borderCollapse: 'collapse',
                                        fontSize: '0.9rem'
                                    }}>
                                        <thead style={{ background: '#f5f5f5' }}>
                                            <tr>
                                                <th style={{ padding: '0.75rem', textAlign: 'left', borderBottom: '2px solid #ddd' }}>Mô hình</th>
                                                <th style={{ padding: '0.75rem', textAlign: 'center', borderBottom: '2px solid #ddd' }}>MAE</th>
                                                <th style={{ padding: '0.75rem', textAlign: 'center', borderBottom: '2px solid #ddd' }}>MSE</th>
                                                <th style={{ padding: '0.75rem', textAlign: 'center', borderBottom: '2px solid #ddd' }}>RMSE</th>
                                                <th style={{ padding: '0.75rem', textAlign: 'center', borderBottom: '2px solid #ddd', color: '#2196f3', fontWeight: '600' }}>Accuracy</th>
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
                                                    <tr key={model.key} style={{ borderBottom: '1px solid #e0e0e0' }}>
                                                        <td style={{ padding: '0.75rem', fontWeight: '500' }}>{model.label}</td>
                                                        <td style={{ padding: '0.75rem', textAlign: 'center' }}>
                                                            {metrics ? metrics.mae.toFixed(4) : '-'}
                                                        </td>
                                                        <td style={{ padding: '0.75rem', textAlign: 'center' }}>
                                                            {metrics ? metrics.mse.toFixed(4) : '-'}
                                                        </td>
                                                        <td style={{ padding: '0.75rem', textAlign: 'center' }}>
                                                            {metrics ? metrics.rmse.toFixed(4) : '-'}
                                                        </td>
                                                        <td style={{
                                                            padding: '0.75rem',
                                                            textAlign: 'center',
                                                            background: metrics ? (metrics.accuracy >= 90 ? '#e8f5e9' : metrics.accuracy >= 80 ? '#fff9c4' : '#ffebee') : '#f5f5f5',
                                                            fontWeight: '600',
                                                            color: metrics ? (metrics.accuracy >= 90 ? '#2e7d32' : metrics.accuracy >= 80 ? '#f57f17' : '#c62828') : '#666'
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
                                <h4 style={{ fontSize: '0.95rem', fontWeight: '600', marginBottom: '0.75rem', color: '#2c3e50' }}>
                                    Nhiệm vụ 2: Dữ liệu lớp 10 - dự đoán lớp 11
                                </h4>
                                <div style={{ overflowX: 'auto' }}>
                                    <table style={{
                                        width: '100%',
                                        borderCollapse: 'collapse',
                                        fontSize: '0.9rem'
                                    }}>
                                        <thead style={{ background: '#f5f5f5' }}>
                                            <tr>
                                                <th style={{ padding: '0.75rem', textAlign: 'left', borderBottom: '2px solid #ddd' }}>Mô hình</th>
                                                <th style={{ padding: '0.75rem', textAlign: 'center', borderBottom: '2px solid #ddd' }}>MAE</th>
                                                <th style={{ padding: '0.75rem', textAlign: 'center', borderBottom: '2px solid #ddd' }}>MSE</th>
                                                <th style={{ padding: '0.75rem', textAlign: 'center', borderBottom: '2px solid #ddd' }}>RMSE</th>
                                                <th style={{ padding: '0.75rem', textAlign: 'center', borderBottom: '2px solid #ddd', color: '#2196f3', fontWeight: '600' }}>Accuracy</th>
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
                                                    <tr key={model.key} style={{ borderBottom: '1px solid #e0e0e0' }}>
                                                        <td style={{ padding: '0.75rem', fontWeight: '500' }}>{model.label}</td>
                                                        <td style={{ padding: '0.75rem', textAlign: 'center' }}>
                                                            {metrics ? metrics.mae.toFixed(4) : '-'}
                                                        </td>
                                                        <td style={{ padding: '0.75rem', textAlign: 'center' }}>
                                                            {metrics ? metrics.mse.toFixed(4) : '-'}
                                                        </td>
                                                        <td style={{ padding: '0.75rem', textAlign: 'center' }}>
                                                            {metrics ? metrics.rmse.toFixed(4) : '-'}
                                                        </td>
                                                        <td style={{
                                                            padding: '0.75rem',
                                                            textAlign: 'center',
                                                            background: metrics ? (metrics.accuracy >= 90 ? '#e8f5e9' : metrics.accuracy >= 80 ? '#fff9c4' : '#ffebee') : '#f5f5f5',
                                                            fontWeight: '600',
                                                            color: metrics ? (metrics.accuracy >= 90 ? '#2e7d32' : metrics.accuracy >= 80 ? '#f57f17' : '#c62828') : '#666'
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
                        <div style={{ marginTop: '1rem', padding: '0.75rem', background: '#f0f0f0', borderRadius: '6px', fontSize: '0.85rem', color: '#666' }}>
                            <strong>ℹ️ Thông tin đánh giá:</strong> 
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
                <h3 style={{ fontSize: '1.3rem', fontWeight: '600', marginBottom: '1rem' }}>
                    <Brain size={20} style={{ display: 'inline', marginRight: '0.5rem' }} />
                    Thiết Lập Mô Hình
                </h3>
                <p style={{ fontSize: '0.9rem', color: '#745757ff', marginBottom: '1.5rem' }}>
                    Chọn mô hình học máy để dự đoán điểm số:
                </p>

                {modelMsg && (
                    <div style={{
                        padding: '0.75rem',
                        borderRadius: '8px',
                        marginBottom: '1rem',
                        background: modelMsg.startsWith('Lỗi') ? '#ffebee' : '#e8f5e9',
                        color: modelMsg.startsWith('Lỗi') ? '#c62828' : '#2e7d32'
                    }}>
                        {modelMsg}
                    </div>
                )}

                {loadingModels ? (
                    <p style={{ color: '#999' }}>Đang tải...</p>
                ) : modelStatus ? (
                    <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
                        {modelStatus.available_models.map((model) => (
                            <div 
                                key={model} 
                                style={{ 
                                    display: 'flex', 
                                    alignItems: 'center', 
                                    gap: '0.75rem', 
                                    padding: '1rem', 
                                    background: selectedModel === model ? '#e3f2fd' : '#f9f9f9', 
                                    borderRadius: '8px', 
                                    border: '2px solid ' + (selectedModel === model ? '#2196f3' : '#e0e0e0'),
                                    cursor: 'pointer',
                                    transition: 'all 0.2s'
                                }}
                                onClick={() => handleSelectModel(model)}
                            >
                                <input
                                    type="radio"
                                    name="ml-model"
                                    value={model}
                                    checked={selectedModel === model}
                                    onChange={() => handleSelectModel(model)}
                                    style={{ cursor: 'pointer' }}
                                />
                                <div style={{ flex: 1 }}>
                                    <strong style={{ fontSize: '1rem', display: 'block', marginBottom: '0.25rem' }}>
                                        {model === 'knn' ? 'KNN' : model === 'kernel_regression' ? 'Kernel Regression' : 'LWLR'}
                                    </strong>
                                    {modelStatus.descriptions && modelStatus.descriptions[model] && (
                                        <p style={{ fontSize: '0.85rem', color: '#666', margin: 0 }}>
                                            {modelStatus.descriptions[model]}
                                        </p>
                                    )}
                                </div>
                                {selectedModel === model && (
                                    <span style={{ color: '#2196f3', fontWeight: '600' }}>✓ Đang hoạt động</span>
                                )}
                            </div>
                        ))}
                    </div>
                ) : (
                    <p style={{ color: '#c62828' }}>Không thể tải trạng thái mô hình.</p>
                )}
            </div>
        </div>
    );
};

export default Developer;

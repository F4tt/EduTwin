import React, { useState, useEffect } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import * as XLSX from 'xlsx';
import { Settings, Save, FileText, Upload, Database, Trash2, ChevronDown, ChevronUp, X, Brain, Zap, CheckCircle, Lightbulb, File, FileUp } from 'lucide-react';
import { LineChart, Line, BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer } from 'recharts';
import axiosClient from '../api/axiosClient';
import { uploadStructureDocument, getStructureDocuments, deleteStructureDocument } from '../api/documentApi';
import { useAuth } from '../context/AuthContext';

const Developer = () => {
    const { user } = useAuth();
    // Form states for creating new structure
    const [structureName, setStructureName] = useState('');
    const [numTimePoints, setNumTimePoints] = useState('');
    const [numSubjects, setNumSubjects] = useState('');
    const [timePointLabels, setTimePointLabels] = useState([]);
    const [subjectLabels, setSubjectLabels] = useState([]);
    const [scaleType, setScaleType] = useState('0-10'); // Default scale type
    const [structureConfirmed, setStructureConfirmed] = useState(false);
    const [savingStructure, setSavingStructure] = useState(false);
    const [structureMessage, setStructureMessage] = useState('');

    // Structure list and active structure
    const [allStructures, setAllStructures] = useState([]);
    const [expandedStructureId, setExpandedStructureId] = useState(null);

    // Per-structure data (keyed by structure_id)
    const [structureDatasets, setStructureDatasets] = useState({}); // Stats for each structure
    const [uploadingFiles, setUploadingFiles] = useState({}); // Upload states
    const [activeStructureId, setActiveStructureId] = useState(null); // Currently active structure for all users

    // Document management states (keyed by structure_id)
    const [structureDocuments, setStructureDocuments] = useState({}); // Documents for each structure
    const [uploadingDocuments, setUploadingDocuments] = useState({}); // Document upload states
    const [documentMessages, setDocumentMessages] = useState({}); // Messages per structure

    // ML Model Management States
    const [evaluating, setEvaluating] = useState(false);
    const [evaluationResults, setEvaluationResults] = useState(null);
    const [evaluationMessage, setEvaluationMessage] = useState('');
    const [parameters, setParameters] = useState({ knn_n: 15, kr_bandwidth: 1.25, lwlr_tau: 3.0 });
    const [originalParameters, setOriginalParameters] = useState({ knn_n: 15, kr_bandwidth: 1.25, lwlr_tau: 3.0 });
    const [loadingParams, setLoadingParams] = useState(false);
    const [savingParams, setSavingParams] = useState(false);
    const [paramMessage, setParamMessage] = useState('');
    const [modelStatus, setModelStatus] = useState(null);
    const [selectedModel, setSelectedModel] = useState('');
    const [modelMsg, setModelMsg] = useState('');
    const [loadingModels, setLoadingModels] = useState(false);

    // Model evaluation - multi-select arrays
    const [evalInputTimepoints, setEvalInputTimepoints] = useState([]);
    const [evalOutputTimepoints, setEvalOutputTimepoints] = useState([]);

    // Reset evaluation selections when active structure changes
    useEffect(() => {
        setEvalInputTimepoints([]);
        setEvalOutputTimepoints([]);
        setEvaluationResults(null);
        setEvaluationMessage('');
    }, [activeStructureId]);

    // Check permissions first
    if (!user || (user.role !== 'developer' && user.role !== 'admin')) {
        return (
            <div style={{ padding: '4rem 2rem', textAlign: 'center' }}>
                <h2 style={{ color: 'var(--danger-color)' }}>Truy cập bị từ chối</h2>
                <p>Bạn không có quyền truy cập vào trang này.</p>
            </div>
        );
    }

    useEffect(() => {
        fetchAllStructures();
        fetchModelStatus();
        fetchModelParameters();
    }, []);

    const fetchAllStructures = async () => {
        try {
            console.log('Fetching all structures...');
            const res = await axiosClient.get('/custom-model/teaching-structures');
            console.log('API Response:', res.data);
            const structures = res.data.structures || [];
            console.log('Structures found:', structures.length, structures);
            setAllStructures(structures);

            // Set active structure from API or first structure
            const activeStruct = structures.find(s => s.is_active);
            if (activeStruct) {
                setActiveStructureId(activeStruct.id);
            }

            // Load dataset stats for each structure
            for (const struct of structures) {
                loadDatasetStats(struct.id);
            }
        } catch (e) {
            console.error('Error fetching structures:', e);
            console.error('Error details:', e.response?.data);
        }
    };

    const loadDatasetStats = async (structureId) => {
        try {
            const res = await axiosClient.get(`/custom-model/dataset-stats/${structureId}`);
            setStructureDatasets(prev => ({
                ...prev,
                [structureId]: {
                    reference_count: res.data.reference_count || 0,
                    last_upload: res.data.last_upload || null
                }
            }));
        } catch (e) {
            console.error('Error loading dataset stats:', e);
        }
    };

    const handleSetActiveStructure = async (structureId) => {
        try {
            const res = await axiosClient.post(`/custom-model/teaching-structure/activate/${structureId}`);
            setActiveStructureId(structureId);
            setStructureMessage('✓ Đã kích hoạt cấu trúc cho toàn bộ hệ thống!');
            setTimeout(() => setStructureMessage(''), 3000);
            await fetchAllStructures();
        } catch (e) {
            setStructureMessage('Lỗi: ' + (e.response?.data?.detail || e.message));
        }
    };

    const handleConfirmStructure = () => {
        const numTP = parseInt(numTimePoints);
        const numSub = parseInt(numSubjects);

        if (isNaN(numTP) || numTP < 2) {
            alert('Vui lòng nhập số lượng mốc thời gian từ 2 trở lên');
            return;
        }

        if (isNaN(numSub) || numSub < 1) {
            alert('Vui lòng nhập số lượng môn học từ 1 trở lên');
            return;
        }

        // Initialize labels arrays
        const newTimeLabels = Array(numTP).fill('');
        const newSubjectLabels = Array(numSub).fill('');

        setTimePointLabels(newTimeLabels);
        setSubjectLabels(newSubjectLabels);
        setStructureConfirmed(true);
    };

    const handleSaveStructure = async () => {
        if (!structureName.trim()) {
            alert('Vui lòng nhập tên cấu trúc');
            return;
        }

        if (timePointLabels.some(l => !l.trim()) || subjectLabels.some(l => !l.trim())) {
            alert('Vui lòng nhập tên cho tất cả mốc thời gian và môn học');
            return;
        }

        setSavingStructure(true);
        setStructureMessage('');

        try {
            console.log('Saving structure:', {
                structure_name: structureName,
                num_time_points: parseInt(numTimePoints),
                num_subjects: parseInt(numSubjects),
                time_point_labels: timePointLabels,
                subject_labels: subjectLabels,
                scale_type: scaleType
            });

            const res = await axiosClient.post('/custom-model/teaching-structure', {
                structure_name: structureName,
                num_time_points: parseInt(numTimePoints),
                num_subjects: parseInt(numSubjects),
                time_point_labels: timePointLabels,
                subject_labels: subjectLabels,
                scale_type: scaleType
            });

            console.log('Save response:', res.data);
            setStructureMessage('✓ ' + res.data.message);
            setTimeout(() => setStructureMessage(''), 3000);

            // Reset form
            setStructureName('');
            setNumTimePoints('');
            setNumSubjects('');
            setTimePointLabels([]);
            setSubjectLabels([]);
            setScaleType('0-10');
            setStructureConfirmed(false);

            console.log('Fetching updated structures...');
            await fetchAllStructures();
            console.log('Fetch completed');
        } catch (e) {
            console.error('Error saving structure:', e);
            console.error('Error response:', e.response?.data);
            setStructureMessage('Lỗi: ' + (e.response?.data?.detail || e.message));
        } finally {
            setSavingStructure(false);
        }
    };

    const handleDeleteStructure = async (structureId, structureName) => {
        if (!window.confirm(`Bạn có chắc muốn xóa cấu trúc "${structureName}"?`)) return;

        try {
            const res = await axiosClient.delete(`/custom-model/teaching-structure/${structureId}`);
            setStructureMessage('✓ ' + res.data.message);
            setTimeout(() => setStructureMessage(''), 3000);
            if (expandedStructureId === structureId) {
                setExpandedStructureId(null);
            }
            await fetchAllStructures();
        } catch (e) {
            setStructureMessage('Lỗi: ' + (e.response?.data?.detail || e.message));
        }
    };

    const handleDownloadTemplate = (struct) => {
        const headers = [];
        struct.time_point_labels.forEach(timePoint => {
            struct.subject_labels.forEach(subject => {
                headers.push(`${subject}_${timePoint}`);
            });
        });

        // Create Excel file using xlsx library
        const ws = XLSX.utils.aoa_to_sheet([headers]);
        const wb = XLSX.utils.book_new();
        XLSX.utils.book_append_sheet(wb, ws, 'Data');
        XLSX.writeFile(wb, `${struct.structure_name}_template.xlsx`);
    };

    const handleFileUpload = async (event, structureId) => {
        const file = event.target.files[0];
        if (!file) return;

        setUploadingFiles(prev => ({ ...prev, [structureId]: true }));

        const formData = new FormData();
        formData.append('file', file);

        try {
            const res = await axiosClient.post(`/custom-model/upload-dataset/${structureId}`, formData, {
                headers: {
                    'Content-Type': 'multipart/form-data',
                },
            });
            setStructureMessage('✓ ' + res.data.message);
            setTimeout(() => setStructureMessage(''), 5000);

            // Reload dataset stats from backend
            loadDatasetStats(structureId);
        } catch (e) {
            setStructureMessage('Lỗi: ' + (e.response?.data?.detail || e.message));
        } finally {
            setUploadingFiles(prev => ({ ...prev, [structureId]: false }));
        }
    };

    const toggleExpand = (structureId) => {
        const newExpandedId = expandedStructureId === structureId ? null : structureId;
        setExpandedStructureId(newExpandedId);

        // Load documents when expanding
        if (newExpandedId === structureId) {
            loadStructureDocuments(structureId);
        }
    };

    // ========== Document Management Functions ==========

    const loadStructureDocuments = async (structureId) => {
        try {
            const response = await getStructureDocuments(structureId);
            setStructureDocuments(prev => ({
                ...prev,
                [structureId]: response.documents || []
            }));
        } catch (e) {
            console.error('Failed to load documents:', e);
        }
    };

    const handleDocumentUpload = async (structureId, file) => {
        // Validate file type
        const allowedTypes = ['pdf', 'docx', 'doc', 'txt'];
        const fileExt = file.name.split('.').pop().toLowerCase();

        if (!allowedTypes.includes(fileExt)) {
            setDocumentMessages(prev => ({
                ...prev,
                [structureId]: 'Chỉ hỗ trợ file PDF, DOCX, TXT'
            }));
            return;
        }

        // Check file size (max 10MB)
        if (file.size > 10 * 1024 * 1024) {
            setDocumentMessages(prev => ({
                ...prev,
                [structureId]: 'File quá lớn (tối đa 10MB)'
            }));
            return;
        }

        setUploadingDocuments(prev => ({ ...prev, [structureId]: true }));
        setDocumentMessages(prev => ({ ...prev, [structureId]: '' }));

        try {
            const response = await uploadStructureDocument(structureId, file);
            setDocumentMessages(prev => ({
                ...prev,
                [structureId]: `✓ ${response.message} (Nén: ${response.document.compression_ratio}x)`
            }));

            // Reload documents
            await loadStructureDocuments(structureId);
        } catch (e) {
            setDocumentMessages(prev => ({
                ...prev,
                [structureId]: 'Lỗi: ' + (e.response?.data?.detail || e.message)
            }));
        } finally {
            setUploadingDocuments(prev => ({ ...prev, [structureId]: false }));
        }
    };

    const handleDeleteDocument = async (structureId, docId, fileName) => {
        if (!confirm(`Xóa tài liệu "${fileName}"?`)) return;

        try {
            await deleteStructureDocument(docId);
            setDocumentMessages(prev => ({
                ...prev,
                [structureId]: '✓ Đã xóa tài liệu'
            }));

            // Reload documents
            await loadStructureDocuments(structureId);
        } catch (e) {
            setDocumentMessages(prev => ({
                ...prev,
                [structureId]: 'Lỗi: ' + (e.response?.data?.detail || e.message)
            }));
        }
    };

    // ========== ML Model Management Functions ==========

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

    const fetchModelParameters = async () => {
        setLoadingParams(true);
        try {
            const res = await axiosClient.get('/developer/model-parameters');
            setParameters(res.data);
            setOriginalParameters(res.data);
        } catch (e) {
            console.error('Error fetching model parameters:', e);
        } finally {
            setLoadingParams(false);
        }
    };

    const handleSaveParameters = async () => {
        setSavingParams(true);
        setParamMessage('');

        try {
            const res = await axiosClient.post('/developer/model-parameters', parameters);
            setParamMessage('✓ ' + (res.data.message || 'Đã cập nhật thông số thành công'));
            setOriginalParameters(parameters);
            setTimeout(() => setParamMessage(''), 3000);
        } catch (e) {
            const errorMsg = e.response?.data?.detail || e.message || 'Lỗi không xác định';
            setParamMessage('Lỗi: ' + errorMsg);
            console.error('Error saving parameters:', e);
        } finally {
            setSavingParams(false);
        }
    };

    const handleSelectModel = async (modelName) => {
        setModelMsg('');
        try {
            const res = await axiosClient.post('/developer/select-model', { model: modelName });
            setSelectedModel(modelName);
            setModelMsg('✓ ' + (res.data.message || 'Đã cập nhật mô hình dự đoán.'));
            setTimeout(() => setModelMsg(''), 3000);
            await fetchModelStatus();
        } catch (e) {
            const errorMsg = e.response?.data?.detail || e.message || 'Lỗi không xác định';
            setModelMsg('Lỗi: ' + errorMsg);
            console.error('Error selecting model:', e);
        }
    };

    const handleEvaluateModels = async () => {
        // Check if there's an active structure
        if (!activeStructureId) {
            setEvaluationMessage('Vui lòng kích hoạt một cấu trúc trước khi đánh giá mô hình');
            return;
        }

        // Validate selection
        if (evalInputTimepoints.length === 0) {
            setEvaluationMessage('Vui lòng chọn ít nhất 1 mốc thời gian đầu vào');
            return;
        }
        if (evalOutputTimepoints.length === 0) {
            setEvaluationMessage('Vui lòng chọn ít nhất 1 mốc thời gian dự đoán');
            return;
        }

        // Get active structure to convert indices to labels
        const activeStruct = allStructures.find(s => s.id === activeStructureId);
        if (!activeStruct) {
            setEvaluationMessage('Không tìm thấy cấu trúc đang kích hoạt');
            return;
        }

        // Convert indices to timepoint labels
        const inputLabels = evalInputTimepoints.map(idx => activeStruct.time_point_labels[idx]);
        const outputLabels = evalOutputTimepoints.map(idx => activeStruct.time_point_labels[idx]);

        // Validate timepoint order
        const maxInputIdx = Math.max(...evalInputTimepoints);
        const minOutputIdx = Math.min(...evalOutputTimepoints);
        if (minOutputIdx <= maxInputIdx) {
            setEvaluationMessage('Tất cả mốc dự đoán phải sau mốc đầu vào lớn nhất');
            return;
        }

        setEvaluating(true);
        setEvaluationMessage('Đang khởi tạo đánh giá...');
        setEvaluationResults(null);

        try {
            const payload = {
                structure_id: activeStructureId,
                input_timepoints: inputLabels,
                output_timepoints: outputLabels
            };

            console.log('[Evaluate] Sending payload:', payload);

            // Start background evaluation
            const startRes = await axiosClient.post('/custom-model/evaluate-models', payload);

            if (startRes.data.error) {
                setEvaluationMessage('Lỗi: ' + startRes.data.error);
                setEvaluating(false);
                return;
            }

            const evaluationId = startRes.data.evaluation_id;
            if (!evaluationId) {
                // Backwards compatibility: if no evaluation_id, results are immediate
                setEvaluationResults(startRes.data);
                setEvaluationMessage('✓ Đánh giá hoàn tất!');
                setEvaluating(false);
                return;
            }

            setEvaluationMessage(`Đang đánh giá ${startRes.data.reference_count} mẫu dữ liệu... (chạy nền)`);

            // Poll for status every 2 seconds
            const pollInterval = setInterval(async () => {
                try {
                    const statusRes = await axiosClient.get(`/custom-model/evaluate-status/${evaluationId}`);
                    const status = statusRes.data;

                    if (status.status === 'completed') {
                        clearInterval(pollInterval);
                        setEvaluationResults(status.results);
                        setEvaluationMessage('✓ Đánh giá hoàn tất!');
                        setEvaluating(false);
                    } else if (status.status === 'failed') {
                        clearInterval(pollInterval);
                        setEvaluationMessage('Lỗi: ' + (status.error || 'Đánh giá thất bại'));
                        setEvaluating(false);
                    } else {
                        // Still running, update message
                        setEvaluationMessage(status.message || 'Đang xử lý...');
                    }
                } catch (pollError) {
                    console.error('[Evaluate] Poll error:', pollError);
                    // Don't stop polling on temporary errors, but log them
                }
            }, 2000);

            // Timeout after 10 minutes
            setTimeout(() => {
                clearInterval(pollInterval);
                if (evaluating) {
                    setEvaluationMessage('Đánh giá đã timeout. Vui lòng thử lại với ít dữ liệu hơn.');
                    setEvaluating(false);
                }
            }, 600000);

        } catch (e) {
            console.error('[Evaluate] Error:', e);
            setEvaluationMessage('Lỗi: ' + (e.response?.data?.detail || e.message));
            setEvaluating(false);
        }
    };

    return (
        <div style={{ padding: '2rem', maxWidth: '1400px', margin: '0 auto' }}>
            <motion.div
                initial={{ opacity: 0, y: 20 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ duration: 0.3 }}
            >
                {/* Page Header */}
                <div style={{ marginBottom: '2rem' }}>
                    <h1 style={{ fontSize: '2rem', fontWeight: '700', color: 'var(--text-primary)', marginBottom: '0.5rem', display: 'flex', alignItems: 'center', gap: '1rem' }}>
                        <Settings size={32} style={{ color: '#8b5cf6' }} />
                        Quản Lý Hệ Thống (Developer/Admin)
                    </h1>
                    <p style={{ fontSize: '1rem', color: 'var(--text-secondary)' }}>
                        Quản lý cấu trúc giảng dạy, tập dữ liệu, cấu hình mô hình ML và đánh giá hiệu suất
                    </p>
                </div>

                {/* Message Display */}
                {structureMessage && (
                    <div style={{
                        padding: '1rem',
                        marginBottom: '1.5rem',
                        borderRadius: 'var(--radius-md)',
                        background: structureMessage.startsWith('✓') ? '#d1fae5' : '#fee2e2',
                        color: structureMessage.startsWith('✓') ? '#065f46' : '#991b1b',
                        fontWeight: '500'
                    }}>
                        {structureMessage}
                    </div>
                )}

                {/* Create New Structure Section */}
                <div style={{ background: 'var(--bg-surface)', padding: '2rem', borderRadius: 'var(--radius-lg)', marginBottom: '2rem', border: '1px solid var(--border-color)' }}>
                    <h3 style={{ fontSize: '1.25rem', fontWeight: '600', marginBottom: '1.5rem', color: 'var(--text-primary)' }}>
                        Thiết lập cấu trúc giảng dạy mới
                    </h3>

                    <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '2rem', marginBottom: '2rem' }}>
                        {/* Left Column - Form Inputs */}
                        <div>
                            <div style={{ marginBottom: '1.5rem' }}>
                                <label style={{ display: 'block', marginBottom: '0.5rem', fontWeight: '500', color: 'var(--text-primary)' }}>
                                    Tên cấu trúc:
                                </label>
                                <input
                                    type="text"
                                    value={structureName}
                                    onChange={(e) => setStructureName(e.target.value)}
                                    placeholder="VD: THPT 3 năm, TOEIC 4 khóa..."
                                    className="input-field"
                                    style={{ width: '100%', padding: '0.75rem', borderRadius: 'var(--radius-md)', border: '1px solid var(--border-color)' }}
                                />
                            </div>

                            <div style={{ marginBottom: '1.5rem' }}>
                                <label style={{ display: 'block', marginBottom: '0.5rem', fontWeight: '500', color: 'var(--text-primary)' }}>
                                    Số lượng mốc thời gian:
                                </label>
                                <input
                                    type="number"
                                    min="2"
                                    value={numTimePoints}
                                    onChange={(e) => setNumTimePoints(e.target.value)}
                                    placeholder="VD: 3 (Lớp 10, 11, 12)"
                                    className="input-field"
                                    style={{ width: '100%', padding: '0.75rem', borderRadius: 'var(--radius-md)', border: '1px solid var(--border-color)' }}
                                />
                            </div>

                            <div style={{ marginBottom: '1.5rem' }}>
                                <label style={{ display: 'block', marginBottom: '0.5rem', fontWeight: '500', color: 'var(--text-primary)' }}>
                                    Số lượng môn học:
                                </label>
                                <input
                                    type="number"
                                    min="1"
                                    value={numSubjects}
                                    onChange={(e) => setNumSubjects(e.target.value)}
                                    placeholder="VD: 9 (Toán, Lý, Hóa...)"
                                    className="input-field"
                                    style={{ width: '100%', padding: '0.75rem', borderRadius: 'var(--radius-md)', border: '1px solid var(--border-color)' }}
                                />
                            </div>

                            <div style={{ marginBottom: '1.5rem' }}>
                                <label style={{ display: 'block', marginBottom: '0.5rem', fontWeight: '500', color: 'var(--text-primary)' }}>
                                    Thang điểm:
                                </label>
                                <select
                                    value={scaleType}
                                    onChange={(e) => setScaleType(e.target.value)}
                                    className="input-field"
                                    style={{ width: '100%', padding: '0.75rem', borderRadius: 'var(--radius-md)', border: '1px solid var(--border-color)' }}
                                >
                                    <option value="0-10">Thang 0.0 - 10.0</option>
                                    <option value="0-100">Thang 0.0 - 100.0</option>
                                    <option value="0-10000">Thang 0 - 10000</option>
                                    <option value="A-F">Thang A - F</option>
                                    <option value="GPA">Thang GPA 0.0 - 4.0</option>
                                </select>
                            </div>

                            <button
                                onClick={handleConfirmStructure}
                                disabled={!numTimePoints || !numSubjects}
                                className="button-secondary"
                                style={{
                                    width: '100%',
                                    padding: '0.75rem',
                                    borderRadius: 'var(--radius-md)',
                                    background: (!numTimePoints || !numSubjects) ? '#9ca3af' : '#8b5cf6',
                                    color: 'white',
                                    border: 'none',
                                    cursor: (!numTimePoints || !numSubjects) ? 'not-allowed' : 'pointer',
                                    fontWeight: '600'
                                }}
                            >
                                Xác nhận và nhập chi tiết
                            </button>
                        </div>

                        {/* Right Column - Instructions */}
                        <div style={{
                            background: '#dbeafe',
                            padding: '1.5rem',
                            borderRadius: 'var(--radius-md)'
                        }}>
                            <p style={{ fontWeight: '600', color: '#1e40af', marginBottom: '0.75rem' }}>
                                💡 Hướng dẫn:
                            </p>
                            <ul style={{ fontSize: '0.9rem', color: '#1e40af', lineHeight: '1.8', paddingLeft: '1.5rem' }}>
                                <li>Ví dụ 1: Giám sát điểm số học sinh THPT với 3 năm học, 9 môn: Số lượng mốc thời gian là 3 (Lớp 10, Lớp 11, Lớp 12). Số lượng môn học: 9.</li>
                                <li>Ví dụ 2: Giám sát điểm học viên luyện thi TOEIC với 4 khóa học, 4 kỹ năng: Số lượng mốc thời gian là 4 (Khóa 1, Khóa 2, Khóa 3, Khóa 4). Số lượng môn học: 4 (Reading, Listening, Speaking, Writing).</li>
                                <li>Tên các môn học và mốc thời gian nhập thủ công. Nhập mốc thời gian tăng dần từ trái sang phải.</li>
                            </ul>
                        </div>
                    </div>

                    {/* Label Inputs (shown after confirm) */}
                    {structureConfirmed && (
                        <>
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

                            <div style={{ display: 'flex', justifyContent: 'center', paddingTop: '1rem', borderTop: '1px solid var(--border-color)' }}>
                                <button
                                    onClick={handleSaveStructure}
                                    disabled={!structureName.trim() || timePointLabels.some(l => !l.trim()) || subjectLabels.some(l => !l.trim()) || savingStructure}
                                    className="button-primary"
                                    style={{
                                        padding: '1rem 2rem',
                                        borderRadius: 'var(--radius-md)',
                                        background: (!structureName.trim() || timePointLabels.some(l => !l.trim()) || subjectLabels.some(l => !l.trim()) || savingStructure) ? '#9ca3af' : '#3b82f6',
                                        color: 'white',
                                        border: 'none',
                                        cursor: (!structureName.trim() || timePointLabels.some(l => !l.trim()) || subjectLabels.some(l => !l.trim()) || savingStructure) ? 'not-allowed' : 'pointer',
                                        fontWeight: '600',
                                        fontSize: '1rem',
                                        display: 'flex',
                                        alignItems: 'center',
                                        gap: '0.5rem'
                                    }}
                                >
                                    <Save size={18} />
                                    {savingStructure ? 'Đang lưu...' : 'Lưu cấu trúc'}
                                </button>
                            </div>
                        </>
                    )}
                </div>

                {/* Structures List */}
                <div style={{ background: 'var(--bg-surface)', padding: '2rem', borderRadius: 'var(--radius-lg)', border: '1px solid var(--border-color)' }}>
                    <h3 style={{ fontSize: '1.25rem', fontWeight: '600', marginBottom: '1rem', display: 'flex', alignItems: 'center', gap: '0.75rem', color: 'var(--text-primary)' }}>
                        <Database size={24} style={{ color: '#8b5cf6' }} />
                        Các cấu trúc đã tạo ({allStructures.length}/5)
                    </h3>

                    {allStructures.length > 0 ? (
                        <div style={{ display: 'grid', gap: '1rem' }}>
                            {allStructures.map((struct) => {
                                const isExpanded = expandedStructureId === struct.id;
                                return (
                                    <div
                                        key={struct.id}
                                        style={{
                                            border: '2px solid var(--border-color)',
                                            borderRadius: 'var(--radius-md)',
                                            background: 'var(--bg-body)',
                                            overflow: 'hidden',
                                            transition: 'all 0.2s'
                                        }}
                                    >
                                        {/* Structure Header (Always visible) */}
                                        <div
                                            style={{
                                                padding: '1.5rem',
                                                cursor: 'pointer',
                                                display: 'flex',
                                                justifyContent: 'space-between',
                                                alignItems: 'center'
                                            }}
                                            onClick={() => toggleExpand(struct.id)}
                                        >
                                            <div style={{ flex: 1 }}>
                                                <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem', marginBottom: '0.5rem' }}>
                                                    <h4 style={{ fontSize: '1.1rem', fontWeight: '600', color: 'var(--text-primary)', margin: 0 }}>
                                                        {struct.structure_name}
                                                    </h4>
                                                </div>
                                                <div style={{ display: 'flex', gap: '1.5rem', fontSize: '0.9rem', color: 'var(--text-secondary)' }}>
                                                    <span>📊 {struct.num_time_points} mốc thời gian</span>
                                                    <span>📚 {struct.num_subjects} môn học</span>
                                                </div>
                                            </div>
                                            <div style={{ display: 'flex', gap: '0.5rem', alignItems: 'center' }}>
                                                <button
                                                    onClick={(e) => {
                                                        e.stopPropagation();
                                                        handleDeleteStructure(struct.id, struct.structure_name);
                                                    }}
                                                    style={{
                                                        padding: '0.5rem',
                                                        background: '#fee2e2',
                                                        color: '#dc2626',
                                                        border: 'none',
                                                        borderRadius: 'var(--radius-md)',
                                                        cursor: 'pointer',
                                                        display: 'flex',
                                                        alignItems: 'center'
                                                    }}
                                                    title="Xóa cấu trúc"
                                                >
                                                    <Trash2 size={18} />
                                                </button>
                                                {isExpanded ? <ChevronUp size={24} /> : <ChevronDown size={24} />}
                                            </div>
                                        </div>

                                        {/* Expanded Content */}
                                        <AnimatePresence>
                                            {isExpanded && (
                                                <motion.div
                                                    initial={{ height: 0, opacity: 0 }}
                                                    animate={{ height: 'auto', opacity: 1 }}
                                                    exit={{ height: 0, opacity: 0 }}
                                                    transition={{ duration: 0.3 }}
                                                    style={{ borderTop: '1px solid var(--border-color)' }}
                                                >
                                                    <div style={{ padding: '1.5rem', background: 'white' }}>
                                                        {/* Structure Details */}
                                                        <div style={{ marginBottom: '2rem' }}>
                                                            <h5 style={{ fontSize: '1rem', fontWeight: '600', marginBottom: '1rem', color: 'var(--text-primary)' }}>
                                                                Chi tiết cấu trúc:
                                                            </h5>
                                                            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1rem' }}>
                                                                <div>
                                                                    <p style={{ fontSize: '0.85rem', fontWeight: '600', color: 'var(--text-secondary)', marginBottom: '0.5rem' }}>
                                                                        Mốc thời gian:
                                                                    </p>
                                                                    <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.5rem' }}>
                                                                        {struct.time_point_labels.map((label, idx) => (
                                                                            <span key={idx} style={{
                                                                                padding: '0.25rem 0.75rem',
                                                                                background: '#dbeafe',
                                                                                color: '#1e40af',
                                                                                borderRadius: 'var(--radius-sm)',
                                                                                fontSize: '0.85rem'
                                                                            }}>
                                                                                {label}
                                                                            </span>
                                                                        ))}
                                                                    </div>
                                                                </div>
                                                                <div>
                                                                    <p style={{ fontSize: '0.85rem', fontWeight: '600', color: 'var(--text-secondary)', marginBottom: '0.5rem' }}>
                                                                        Môn học:
                                                                    </p>
                                                                    <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.5rem' }}>
                                                                        {struct.subject_labels.map((label, idx) => (
                                                                            <span key={idx} style={{
                                                                                padding: '0.25rem 0.75rem',
                                                                                background: '#fef3c7',
                                                                                color: '#92400e',
                                                                                borderRadius: 'var(--radius-sm)',
                                                                                fontSize: '0.85rem'
                                                                            }}>
                                                                                {label}
                                                                            </span>
                                                                        ))}
                                                                    </div>
                                                                </div>
                                                            </div>

                                                            {/* Scale Type Section - Read Only */}
                                                            <div style={{ marginTop: '1rem', paddingTop: '1rem', borderTop: '1px solid #e5e7eb' }}>
                                                                <p style={{ fontSize: '0.85rem', fontWeight: '600', color: 'var(--text-secondary)', marginBottom: '0.5rem' }}>
                                                                    Thang điểm:
                                                                </p>
                                                                <span style={{
                                                                    padding: '0.25rem 0.75rem',
                                                                    background: '#f0fdf4',
                                                                    color: '#166534',
                                                                    borderRadius: 'var(--radius-sm)',
                                                                    fontSize: '0.85rem',
                                                                    fontWeight: '600'
                                                                }}>
                                                                    {(() => {
                                                                        const scaleMap = {
                                                                            '0-10': 'Thang 0.0 - 10.0',
                                                                            '0-100': 'Thang 0.0 - 100.0',
                                                                            '0-10000': 'Thang 0 - 10000',
                                                                            'A-F': 'Thang A - F',
                                                                            'GPA': 'Thang GPA 0.0 - 4.0'
                                                                        };
                                                                        return scaleMap[struct.scale_type] || 'Thang 0.0 - 10.0';
                                                                    })()}
                                                                </span>
                                                            </div>
                                                        </div>

                                                        {/* Actions Grid */}
                                                        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: '1rem', marginBottom: '2rem' }}>
                                                            {/* Download Template */}
                                                            <div style={{
                                                                padding: '1.5rem',
                                                                background: '#f0fdf4',
                                                                borderRadius: 'var(--radius-md)',
                                                                border: '1px solid #86efac'
                                                            }}>
                                                                <FileText size={24} style={{ color: '#16a34a', marginBottom: '0.75rem' }} />
                                                                <h6 style={{ fontSize: '0.9rem', fontWeight: '600', marginBottom: '0.5rem', color: 'var(--text-primary)' }}>
                                                                    File định dạng mẫu
                                                                </h6>
                                                                <p style={{ fontSize: '0.8rem', color: 'var(--text-secondary)', marginBottom: '1rem' }}>
                                                                    Tải xuống file định dạng mẫu
                                                                </p>
                                                                <button
                                                                    onClick={() => handleDownloadTemplate(struct)}
                                                                    style={{
                                                                        width: '100%',
                                                                        padding: '0.5rem',
                                                                        background: '#16a34a',
                                                                        color: 'white',
                                                                        border: 'none',
                                                                        borderRadius: 'var(--radius-md)',
                                                                        cursor: 'pointer',
                                                                        fontWeight: '600',
                                                                        fontSize: '0.85rem'
                                                                    }}
                                                                >
                                                                    Tải xuống
                                                                </button>
                                                            </div>

                                                            {/* Upload Dataset */}
                                                            <div style={{
                                                                padding: '1.5rem',
                                                                background: '#fef3c7',
                                                                borderRadius: 'var(--radius-md)',
                                                                border: '1px solid #fde047'
                                                            }}>
                                                                <Upload size={24} style={{ color: '#ca8a04', marginBottom: '0.75rem' }} />
                                                                <h6 style={{ fontSize: '0.9rem', fontWeight: '600', marginBottom: '0.5rem', color: 'var(--text-primary)' }}>
                                                                    Tập dữ liệu tham chiếu
                                                                </h6>
                                                                <p style={{ fontSize: '0.8rem', color: 'var(--text-secondary)', marginBottom: '1rem' }}>
                                                                    Upload file Excel (.xlsx)
                                                                </p>
                                                                <input
                                                                    type="file"
                                                                    accept=".csv,.xlsx,.xls"
                                                                    onChange={(e) => handleFileUpload(e, struct.id)}
                                                                    disabled={uploadingFiles[struct.id]}
                                                                    style={{ display: 'none' }}
                                                                    id={`file-upload-${struct.id}`}
                                                                />
                                                                <label
                                                                    htmlFor={`file-upload-${struct.id}`}
                                                                    style={{
                                                                        display: 'block',
                                                                        width: '100%',
                                                                        padding: '0.5rem',
                                                                        background: uploadingFiles[struct.id] ? '#9ca3af' : '#ca8a04',
                                                                        color: 'white',
                                                                        border: 'none',
                                                                        borderRadius: 'var(--radius-md)',
                                                                        cursor: uploadingFiles[struct.id] ? 'not-allowed' : 'pointer',
                                                                        fontWeight: '600',
                                                                        fontSize: '0.85rem',
                                                                        textAlign: 'center'
                                                                    }}
                                                                >
                                                                    {uploadingFiles[struct.id] ? 'Đang tải...' : 'Chọn file'}
                                                                </label>
                                                            </div>

                                                            {/* Set Active Structure */}
                                                            <div style={{
                                                                padding: '1.5rem',
                                                                background: activeStructureId === struct.id ? '#dbeafe' : '#f3f4f6',
                                                                borderRadius: 'var(--radius-md)',
                                                                border: `2px solid ${activeStructureId === struct.id ? '#3b82f6' : '#d1d5db'}`
                                                            }}>
                                                                <CheckCircle size={24} style={{ color: activeStructureId === struct.id ? '#3b82f6' : '#6b7280', marginBottom: '0.75rem' }} />
                                                                <h6 style={{ fontSize: '0.9rem', fontWeight: '600', marginBottom: '0.5rem', color: 'var(--text-primary)' }}>
                                                                    {activeStructureId === struct.id ? 'Đang kích hoạt' : 'Kích hoạt cấu trúc'}
                                                                </h6>
                                                                <p style={{ fontSize: '0.8rem', color: 'var(--text-secondary)', marginBottom: '1rem' }}>
                                                                    {activeStructureId === struct.id ? 'Áp dụng cho toàn bộ user' : 'Áp dụng cho toàn hệ thống'}
                                                                </p>
                                                                <button
                                                                    onClick={() => handleSetActiveStructure(struct.id)}
                                                                    disabled={activeStructureId === struct.id}
                                                                    style={{
                                                                        width: '100%',
                                                                        padding: '0.5rem',
                                                                        background: activeStructureId === struct.id ? '#9ca3af' : '#3b82f6',
                                                                        color: 'white',
                                                                        border: 'none',
                                                                        borderRadius: 'var(--radius-md)',
                                                                        cursor: activeStructureId === struct.id ? 'not-allowed' : 'pointer',
                                                                        fontWeight: '600',
                                                                        fontSize: '0.85rem'
                                                                    }}
                                                                >
                                                                    {activeStructureId === struct.id ? '✓ Đã kích hoạt' : 'Kích hoạt'}
                                                                </button>
                                                            </div>
                                                        </div>

                                                        {/* Dataset Status - Simplified */}
                                                        <div style={{ marginBottom: '2rem' }}>
                                                            <h5 style={{ fontSize: '1rem', fontWeight: '600', marginBottom: '1rem', color: 'var(--text-primary)' }}>
                                                                Trạng thái tập dữ liệu:
                                                            </h5>
                                                            {(() => {
                                                                const structId = struct.id;
                                                                const stats = structureDatasets[structId];
                                                                const hasData = stats && stats.reference_count > 0;

                                                                return (
                                                                    <div style={{
                                                                        padding: '1.25rem',
                                                                        background: hasData ? '#ecfdf5' : '#fef3c7',
                                                                        borderRadius: 'var(--radius-md)',
                                                                        border: `2px solid ${hasData ? '#10b981' : '#f59e0b'}`
                                                                    }}>
                                                                        <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem', marginBottom: '0.5rem' }}>
                                                                            <Database size={20} style={{ color: hasData ? '#10b981' : '#f59e0b' }} />
                                                                            <h6 style={{ fontSize: '0.95rem', fontWeight: '600', margin: 0, color: 'var(--text-primary)' }}>
                                                                                Tập dữ liệu tham chiếu
                                                                            </h6>
                                                                        </div>
                                                                        <p style={{ fontSize: '0.85rem', color: 'var(--text-secondary)', margin: 0 }}>
                                                                            {hasData
                                                                                ? `✓ Đã tải ${stats.reference_count} mẫu dữ liệu`
                                                                                : '⚠ Chưa có dữ liệu tham chiếu'}
                                                                        </p>
                                                                    </div>
                                                                );
                                                            })()}
                                                        </div>

                                                        {/* Reference Documents Section */}
                                                        <div style={{ marginBottom: '2rem' }}>
                                                            <h5 style={{ fontSize: '1rem', fontWeight: '600', marginBottom: '1rem', color: 'var(--text-primary)' }}>
                                                                Tài liệu tham khảo:
                                                            </h5>

                                                            {/* Upload Document */}
                                                            <div style={{
                                                                padding: '1.5rem',
                                                                background: '#eff6ff',
                                                                borderRadius: 'var(--radius-md)',
                                                                border: '1px solid #3b82f6',
                                                                marginBottom: '1rem'
                                                            }}>
                                                                <FileUp size={24} style={{ color: '#3b82f6', marginBottom: '0.75rem' }} />
                                                                <h6 style={{ fontSize: '0.9rem', fontWeight: '600', marginBottom: '0.5rem', color: 'var(--text-primary)' }}>
                                                                    Upload tài liệu (.pdf, .docx, .txt)
                                                                </h6>
                                                                <p style={{ fontSize: '0.75rem', color: 'var(--text-secondary)', marginBottom: '1rem' }}>
                                                                    AI sẽ trích xuất kiến thức quan trọng
                                                                </p>
                                                                <input
                                                                    type="file"
                                                                    accept=".pdf,.docx,.doc,.txt"
                                                                    onChange={(e) => {
                                                                        if (e.target.files && e.target.files[0]) {
                                                                            handleDocumentUpload(struct.id, e.target.files[0]);
                                                                            e.target.value = '';
                                                                        }
                                                                    }}
                                                                    disabled={uploadingDocuments[struct.id]}
                                                                    style={{ display: 'none' }}
                                                                    id={`doc-upload-${struct.id}`}
                                                                />
                                                                <label
                                                                    htmlFor={`doc-upload-${struct.id}`}
                                                                    style={{
                                                                        display: 'block',
                                                                        width: '100%',
                                                                        padding: '0.5rem',
                                                                        background: uploadingDocuments[struct.id] ? '#9ca3af' : '#3b82f6',
                                                                        color: 'white',
                                                                        border: 'none',
                                                                        borderRadius: 'var(--radius-md)',
                                                                        cursor: uploadingDocuments[struct.id] ? 'not-allowed' : 'pointer',
                                                                        fontWeight: '600',
                                                                        fontSize: '0.85rem',
                                                                        textAlign: 'center'
                                                                    }}
                                                                >
                                                                    {uploadingDocuments[struct.id] ? 'Đang xử lý...' : 'Chọn file (tối đa 10MB)'}
                                                                </label>
                                                                {documentMessages[struct.id] && (
                                                                    <p style={{
                                                                        fontSize: '0.8rem',
                                                                        color: documentMessages[struct.id].startsWith('✓') ? '#10b981' : '#dc2626',
                                                                        marginTop: '0.5rem',
                                                                        marginBottom: 0
                                                                    }}>
                                                                        {documentMessages[struct.id]}
                                                                    </p>
                                                                )}
                                                            </div>

                                                            {/* Document List */}
                                                            {structureDocuments[struct.id] && structureDocuments[struct.id].length > 0 ? (
                                                                <div style={{
                                                                    background: 'var(--bg-surface)',
                                                                    borderRadius: 'var(--radius-md)',
                                                                    border: '1px solid var(--border-color)',
                                                                    overflow: 'hidden'
                                                                }}>
                                                                    {structureDocuments[struct.id].map((doc, idx) => (
                                                                        <div
                                                                            key={doc.id}
                                                                            style={{
                                                                                padding: '1rem',
                                                                                borderBottom: idx < structureDocuments[struct.id].length - 1 ? '1px solid var(--border-color)' : 'none',
                                                                                display: 'flex',
                                                                                alignItems: 'flex-start',
                                                                                gap: '1rem'
                                                                            }}
                                                                        >
                                                                            <File size={20} style={{ color: '#3b82f6', flexShrink: 0, marginTop: '0.25rem' }} />
                                                                            <div style={{ flex: 1, minWidth: 0 }}>
                                                                                <h6 style={{
                                                                                    fontSize: '0.85rem',
                                                                                    fontWeight: '600',
                                                                                    marginBottom: '0.25rem',
                                                                                    color: 'var(--text-primary)',
                                                                                    overflow: 'hidden',
                                                                                    textOverflow: 'ellipsis',
                                                                                    whiteSpace: 'nowrap'
                                                                                }}>
                                                                                    {doc.file_name}
                                                                                </h6>
                                                                                <p style={{
                                                                                    fontSize: '0.75rem',
                                                                                    color: 'var(--text-secondary)',
                                                                                    marginBottom: '0.5rem'
                                                                                }}>
                                                                                    {(doc.file_size / 1024).toFixed(1)} KB •
                                                                                    Nén: {doc.compression_ratio}x •
                                                                                    {doc.summary_length} chars
                                                                                </p>
                                                                                {doc.summary_preview && (
                                                                                    <p style={{
                                                                                        fontSize: '0.75rem',
                                                                                        color: 'var(--text-tertiary)',
                                                                                        marginTop: '0.5rem',
                                                                                        fontStyle: 'italic',
                                                                                        overflow: 'hidden',
                                                                                        textOverflow: 'ellipsis',
                                                                                        display: '-webkit-box',
                                                                                        WebkitLineClamp: 2,
                                                                                        WebkitBoxOrient: 'vertical'
                                                                                    }}>
                                                                                        {doc.summary_preview}
                                                                                    </p>
                                                                                )}
                                                                            </div>
                                                                            <button
                                                                                onClick={() => handleDeleteDocument(struct.id, doc.id, doc.file_name)}
                                                                                style={{
                                                                                    padding: '0.5rem',
                                                                                    background: '#fee2e2',
                                                                                    color: '#dc2626',
                                                                                    border: 'none',
                                                                                    borderRadius: 'var(--radius-md)',
                                                                                    cursor: 'pointer',
                                                                                    flexShrink: 0
                                                                                }}
                                                                                title="Xóa tài liệu"
                                                                            >
                                                                                <Trash2 size={16} />
                                                                            </button>
                                                                        </div>
                                                                    ))}
                                                                </div>
                                                            ) : (
                                                                <div style={{
                                                                    padding: '2rem',
                                                                    textAlign: 'center',
                                                                    background: 'var(--bg-body)',
                                                                    borderRadius: 'var(--radius-md)',
                                                                    border: '2px dashed var(--border-color)'
                                                                }}>
                                                                    <FileText size={32} style={{ color: 'var(--text-secondary)', opacity: 0.5, marginBottom: '0.5rem' }} />
                                                                    <p style={{ fontSize: '0.85rem', color: 'var(--text-secondary)', margin: 0 }}>
                                                                        Chưa có tài liệu nào
                                                                    </p>
                                                                </div>
                                                            )}
                                                        </div>
                                                    </div>
                                                </motion.div>
                                            )}
                                        </AnimatePresence>
                                    </div>
                                );
                            })}
                        </div>
                    ) : (
                        <div style={{
                            padding: '3rem 2rem',
                            textAlign: 'center',
                            background: 'var(--bg-body)',
                            borderRadius: 'var(--radius-md)',
                            border: '2px dashed var(--border-color)'
                        }}>
                            <Database size={48} style={{ color: 'var(--text-secondary)', opacity: 0.5, marginBottom: '1rem' }} />
                            <p style={{ fontSize: '1rem', color: 'var(--text-secondary)', margin: 0 }}>
                                Chưa có cấu trúc nào. Bạn có thể tạo tối đa 5 cấu trúc khác nhau.
                            </p>
                        </div>
                    )}
                </div>

                {/* ML Model Parameters Section */}
                <div style={{ background: 'var(--bg-surface)', padding: '2rem', borderRadius: 'var(--radius-lg)', marginBottom: '2rem', border: '1px solid var(--border-color)' }}>
                    <h3 style={{ fontSize: '1.25rem', fontWeight: '600', marginBottom: '1rem', color: 'var(--text-primary)', display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
                        <Settings size={24} style={{ color: '#8b5cf6' }} />
                        Thông Số Mô Hình ML
                    </h3>

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
                            <span className="spinner"></span> Đang tải...
                        </div>
                    ) : (
                        <div>
                            <div style={{ marginBottom: '1.25rem', padding: '1.25rem', background: 'var(--bg-body)', borderRadius: 'var(--radius-md)', border: '1px solid var(--border-color)' }}>
                                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.75rem' }}>
                                    <div>
                                        <strong style={{ display: 'block', fontSize: '1rem', marginBottom: '0.25rem', color: 'var(--text-primary)' }}>KNN - K Neighbors</strong>
                                        <p style={{ fontSize: '0.9rem', color: 'var(--text-secondary)', margin: 0 }}>Số lượng hàng xóm gần nhất. Phạm vi: 1-50</p>
                                    </div>
                                    <input
                                        type="number"
                                        min="1"
                                        max="50"
                                        value={parameters.knn_n}
                                        onChange={(e) => setParameters({ ...parameters, knn_n: parseInt(e.target.value) || 15 })}
                                        style={{
                                            width: '100px',
                                            padding: '0.5rem',
                                            textAlign: 'center',
                                            borderRadius: 'var(--radius-md)',
                                            border: parameters.knn_n !== originalParameters.knn_n ? '2px solid #dc2626' : '1px solid var(--border-color)',
                                            background: parameters.knn_n !== originalParameters.knn_n ? '#fef2f2' : 'white'
                                        }}
                                    />
                                </div>
                                <div style={{ fontSize: '0.85rem', color: '#f59e0b', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                                    <Lightbulb size={14} /> Giá trị mặc định: 15
                                </div>
                            </div>

                            <div style={{ marginBottom: '1.25rem', padding: '1.25rem', background: 'var(--bg-body)', borderRadius: 'var(--radius-md)', border: '1px solid var(--border-color)' }}>
                                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.75rem' }}>
                                    <div>
                                        <strong style={{ display: 'block', fontSize: '1rem', marginBottom: '0.25rem', color: 'var(--text-primary)' }}>Kernel Regression - Bandwidth</strong>
                                        <p style={{ fontSize: '0.9rem', color: 'var(--text-secondary)', margin: 0 }}>Bề rộng hạt nhân. Phạm vi: 0.1-10.0</p>
                                    </div>
                                    <input
                                        type="number"
                                        min="0.1"
                                        max="10"
                                        step="0.05"
                                        value={parameters.kr_bandwidth}
                                        onChange={(e) => setParameters({ ...parameters, kr_bandwidth: parseFloat(e.target.value) || 1.25 })}
                                        style={{
                                            width: '100px',
                                            padding: '0.5rem',
                                            textAlign: 'center',
                                            borderRadius: 'var(--radius-md)',
                                            border: parameters.kr_bandwidth !== originalParameters.kr_bandwidth ? '2px solid #dc2626' : '1px solid var(--border-color)',
                                            background: parameters.kr_bandwidth !== originalParameters.kr_bandwidth ? '#fef2f2' : 'white'
                                        }}
                                    />
                                </div>
                                <div style={{ fontSize: '0.85rem', color: '#f59e0b', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                                    <Lightbulb size={14} /> Giá trị mặc định: 1.25
                                </div>
                            </div>

                            <div style={{ marginBottom: '1.5rem', padding: '1.25rem', background: 'var(--bg-body)', borderRadius: 'var(--radius-md)', border: '1px solid var(--border-color)' }}>
                                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.75rem' }}>
                                    <div>
                                        <strong style={{ display: 'block', fontSize: '1rem', marginBottom: '0.25rem', color: 'var(--text-primary)' }}>LWLR - Tau</strong>
                                        <p style={{ fontSize: '0.9rem', color: 'var(--text-secondary)', margin: 0 }}>Tham số cửa sổ. Phạm vi: 0.5-10.0</p>
                                    </div>
                                    <input
                                        type="number"
                                        min="0.5"
                                        max="10"
                                        step="0.1"
                                        value={parameters.lwlr_tau}
                                        onChange={(e) => setParameters({ ...parameters, lwlr_tau: parseFloat(e.target.value) || 3.0 })}
                                        style={{
                                            width: '100px',
                                            padding: '0.5rem',
                                            textAlign: 'center',
                                            borderRadius: 'var(--radius-md)',
                                            border: parameters.lwlr_tau !== originalParameters.lwlr_tau ? '2px solid #dc2626' : '1px solid var(--border-color)',
                                            background: parameters.lwlr_tau !== originalParameters.lwlr_tau ? '#fef2f2' : 'white'
                                        }}
                                    />
                                </div>
                                <div style={{ fontSize: '0.85rem', color: '#f59e0b', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                                    <Lightbulb size={14} /> Giá trị mặc định: 3.0
                                </div>
                            </div>

                            <button
                                onClick={handleSaveParameters}
                                disabled={savingParams}
                                style={{
                                    padding: '0.75rem 1.5rem',
                                    borderRadius: 'var(--radius-md)',
                                    background: savingParams ? '#9ca3af' : '#3b82f6',
                                    color: 'white',
                                    border: 'none',
                                    cursor: savingParams ? 'not-allowed' : 'pointer',
                                    fontWeight: '600',
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

                {/* ML Model Selection Section */}
                <div style={{ background: 'var(--bg-surface)', padding: '2rem', borderRadius: 'var(--radius-lg)', marginBottom: '2rem', border: '1px solid var(--border-color)' }}>
                    <h3 style={{ fontSize: '1.25rem', fontWeight: '600', marginBottom: '1rem', display: 'flex', alignItems: 'center', gap: '0.75rem', color: 'var(--text-primary)' }}>
                        <Brain size={24} style={{ color: '#8b5cf6' }} />
                        Lựa Chọn Mô Hình ML
                    </h3>

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
                        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(250px, 1fr))', gap: '1rem' }}>
                            {modelStatus.available_models.map((model) => (
                                <div
                                    key={model}
                                    style={{
                                        padding: '1.25rem',
                                        background: selectedModel === model ? '#dbeafe' : 'white',
                                        borderRadius: 'var(--radius-md)',
                                        border: '2px solid ' + (selectedModel === model ? '#3b82f6' : 'var(--border-color)'),
                                        cursor: 'pointer',
                                        transition: 'all 0.2s',
                                        position: 'relative'
                                    }}
                                    onClick={() => handleSelectModel(model)}
                                >
                                    <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem', marginBottom: '0.5rem' }}>
                                        <input
                                            type="radio"
                                            checked={selectedModel === model}
                                            onChange={() => { }}
                                            style={{ cursor: 'pointer' }}
                                        />
                                        <strong style={{ fontSize: '1rem', color: 'var(--text-primary)' }}>
                                            {model === 'knn' ? 'KNN' : model === 'kernel_regression' ? 'Kernel Regression' : 'LWLR'}
                                        </strong>
                                    </div>
                                    {modelStatus.descriptions && modelStatus.descriptions[model] && (
                                        <p style={{ fontSize: '0.85rem', color: 'var(--text-secondary)', margin: 0, lineHeight: '1.5', paddingLeft: '2rem' }}>
                                            {modelStatus.descriptions[model]}
                                        </p>
                                    )}
                                    {selectedModel === model && (
                                        <div style={{ position: 'absolute', top: '0.75rem', right: '0.75rem', color: '#3b82f6' }}>
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

                {/* Model Evaluation Section */}
                <div style={{ background: 'var(--bg-surface)', padding: '2rem', borderRadius: 'var(--radius-lg)', marginBottom: '2rem', border: '1px solid var(--border-color)' }}>
                    <h3 style={{ fontSize: '1.25rem', fontWeight: '600', marginBottom: '1rem', display: 'flex', alignItems: 'center', gap: '0.75rem', color: 'var(--text-primary)' }}>
                        <Zap size={24} style={{ color: '#8b5cf6' }} />
                        Đánh Giá Mô Hình ML
                    </h3>
                    <p style={{ fontSize: '0.95rem', color: 'var(--text-secondary)', marginBottom: '1.5rem' }}>
                        Chọn mốc thời gian để đánh giá và so sánh các mô hình
                    </p>

                    {/* Check if active structure has dataset */}
                    {(() => {
                        const activeStruct = allStructures.find(s => s.id === activeStructureId);
                        const hasDataset = activeStructureId && structureDatasets[activeStructureId]?.reference_count > 0;

                        if (!activeStructureId || !activeStruct) {
                            return (
                                <div style={{
                                    padding: '1.5rem',
                                    background: '#fef3c7',
                                    border: '1px solid #fbbf24',
                                    borderRadius: 'var(--radius-md)',
                                    color: '#92400e',
                                    marginBottom: '1rem'
                                }}>
                                    <p style={{ margin: 0, fontWeight: '500' }}>
                                        ⚠️ Vui lòng chọn cấu trúc giảng dạy active trước
                                    </p>
                                </div>
                            );
                        }

                        if (!hasDataset) {
                            return (
                                <div style={{
                                    padding: '1.5rem',
                                    background: '#fef3c7',
                                    border: '1px solid #fbbf24',
                                    borderRadius: 'var(--radius-md)',
                                    color: '#92400e',
                                    marginBottom: '1rem'
                                }}>
                                    <p style={{ margin: 0, fontWeight: '500' }}>
                                        📊 Hãy cập nhật tập dữ liệu cho cấu trúc <strong>{activeStruct.structure_name}</strong> để đánh giá mô hình
                                    </p>
                                </div>
                            );
                        }

                        return null;
                    })()}

                    {/* Dropdown Selection */}
                    {activeStructureId && structureDatasets[activeStructureId]?.reference_count > 0 && (() => {
                        const activeStruct = allStructures.find(s => s.id === activeStructureId);
                        if (!activeStruct?.time_point_labels) return null;

                        const timepoints = activeStruct.time_point_labels;

                        return (
                            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '2rem', marginBottom: '1.5rem' }}>
                                {/* Input Timepoints - Checkbox List */}
                                <div>
                                    <label style={{ display: 'block', fontSize: '1rem', fontWeight: '600', marginBottom: '0.75rem', color: 'var(--text-primary)' }}>
                                        📊 Đầu vào (chọn nhiều):
                                    </label>
                                    <div style={{
                                        maxHeight: '200px',
                                        overflowY: 'auto',
                                        padding: '0.75rem',
                                        background: 'var(--bg-primary)',
                                        border: '2px solid #8b5cf6',
                                        borderRadius: 'var(--radius-md)'
                                    }}>
                                        {timepoints.map((label, idx) => (
                                            <label
                                                key={idx}
                                                style={{
                                                    display: 'flex',
                                                    alignItems: 'center',
                                                    padding: '0.5rem',
                                                    marginBottom: '0.25rem',
                                                    borderRadius: 'var(--radius-sm)',
                                                    cursor: 'pointer',
                                                    background: evalInputTimepoints.includes(idx) ? '#f3e8ff' : 'transparent',
                                                    transition: 'all 0.2s'
                                                }}
                                                onMouseEnter={(e) => {
                                                    if (!evalInputTimepoints.includes(idx)) {
                                                        e.currentTarget.style.background = '#f9fafb';
                                                    }
                                                }}
                                                onMouseLeave={(e) => {
                                                    if (!evalInputTimepoints.includes(idx)) {
                                                        e.currentTarget.style.background = 'transparent';
                                                    }
                                                }}
                                            >
                                                <input
                                                    type="checkbox"
                                                    checked={evalInputTimepoints.includes(idx)}
                                                    onChange={(e) => {
                                                        if (e.target.checked) {
                                                            setEvalInputTimepoints(prev => [...prev, idx].sort((a, b) => a - b));
                                                        } else {
                                                            setEvalInputTimepoints(prev => prev.filter(i => i !== idx));
                                                        }

                                                        // Auto-clean invalid outputs
                                                        const newInputs = e.target.checked
                                                            ? [...evalInputTimepoints, idx]
                                                            : evalInputTimepoints.filter(i => i !== idx);
                                                        if (newInputs.length > 0) {
                                                            const maxInput = Math.max(...newInputs);
                                                            setEvalOutputTimepoints(prev => prev.filter(i => i > maxInput));
                                                        }
                                                    }}
                                                    style={{
                                                        marginRight: '0.75rem',
                                                        width: '18px',
                                                        height: '18px',
                                                        cursor: 'pointer',
                                                        accentColor: '#8b5cf6'
                                                    }}
                                                />
                                                <span style={{ fontSize: '0.95rem', color: 'var(--text-primary)' }}>
                                                    {label}
                                                </span>
                                            </label>
                                        ))}
                                    </div>
                                    <p style={{ fontSize: '0.85rem', color: '#8b5cf6', marginTop: '0.5rem', fontWeight: '500' }}>
                                        ✓ Đã chọn: {evalInputTimepoints.length} mốc
                                    </p>
                                </div>

                                {/* Output Timepoints - Checkbox List */}
                                <div>
                                    <label style={{ display: 'block', fontSize: '1rem', fontWeight: '600', marginBottom: '0.75rem', color: 'var(--text-primary)' }}>
                                        🎯 Mục tiêu dự đoán (chọn nhiều):
                                    </label>
                                    <div style={{
                                        maxHeight: '200px',
                                        overflowY: 'auto',
                                        padding: '0.75rem',
                                        background: evalInputTimepoints.length === 0 ? '#f3f4f6' : 'var(--bg-primary)',
                                        border: evalInputTimepoints.length === 0 ? '2px dashed #d1d5db' : '2px solid #10b981',
                                        borderRadius: 'var(--radius-md)',
                                        opacity: evalInputTimepoints.length === 0 ? 0.6 : 1
                                    }}>
                                        {timepoints.map((label, idx) => {
                                            const maxInput = evalInputTimepoints.length > 0 ? Math.max(...evalInputTimepoints) : -1;
                                            const disabled = evalInputTimepoints.length === 0 || idx <= maxInput;

                                            return (
                                                <label
                                                    key={idx}
                                                    style={{
                                                        display: 'flex',
                                                        alignItems: 'center',
                                                        padding: '0.5rem',
                                                        marginBottom: '0.25rem',
                                                        borderRadius: 'var(--radius-sm)',
                                                        cursor: disabled ? 'not-allowed' : 'pointer',
                                                        background: evalOutputTimepoints.includes(idx) ? '#d1fae5' : 'transparent',
                                                        opacity: disabled ? 0.4 : 1,
                                                        transition: 'all 0.2s'
                                                    }}
                                                    onMouseEnter={(e) => {
                                                        if (!disabled && !evalOutputTimepoints.includes(idx)) {
                                                            e.currentTarget.style.background = '#f9fafb';
                                                        }
                                                    }}
                                                    onMouseLeave={(e) => {
                                                        if (!disabled && !evalOutputTimepoints.includes(idx)) {
                                                            e.currentTarget.style.background = 'transparent';
                                                        }
                                                    }}
                                                >
                                                    <input
                                                        type="checkbox"
                                                        checked={evalOutputTimepoints.includes(idx)}
                                                        disabled={disabled}
                                                        onChange={(e) => {
                                                            if (e.target.checked) {
                                                                setEvalOutputTimepoints(prev => [...prev, idx].sort((a, b) => a - b));
                                                            } else {
                                                                setEvalOutputTimepoints(prev => prev.filter(i => i !== idx));
                                                            }
                                                        }}
                                                        style={{
                                                            marginRight: '0.75rem',
                                                            width: '18px',
                                                            height: '18px',
                                                            cursor: disabled ? 'not-allowed' : 'pointer',
                                                            accentColor: '#10b981'
                                                        }}
                                                    />
                                                    <span style={{ fontSize: '0.95rem', color: disabled ? 'var(--text-muted)' : 'var(--text-primary)' }}>
                                                        {label} {disabled && idx > -1 && '(⛔ không hợp lệ)'}
                                                    </span>
                                                </label>
                                            );
                                        })}
                                    </div>
                                    <p style={{ fontSize: '0.85rem', color: '#10b981', marginTop: '0.5rem', fontWeight: '500' }}>
                                        ✓ Đã chọn: {evalOutputTimepoints.length} mốc
                                    </p>
                                </div>
                            </div>
                        );
                    })()}

                    <button
                        onClick={handleEvaluateModels}
                        disabled={
                            evaluating ||
                            evalInputTimepoints.length === 0 ||
                            evalOutputTimepoints.length === 0 ||
                            !activeStructureId ||
                            !structureDatasets[activeStructureId]?.reference_count
                        }
                        style={{
                            padding: '0.75rem 1.5rem',
                            borderRadius: 'var(--radius-md)',
                            background: (
                                evaluating ||
                                evalInputTimepoints.length === 0 ||
                                evalOutputTimepoints.length === 0 ||
                                !activeStructureId ||
                                !structureDatasets[activeStructureId]?.reference_count
                            ) ? '#9ca3af' : '#8b5cf6',
                            color: 'white',
                            border: 'none',
                            cursor: (
                                evaluating ||
                                evalInputTimepoints.length === 0 ||
                                evalOutputTimepoints.length === 0 ||
                                !activeStructureId ||
                                !structureDatasets[activeStructureId]?.reference_count
                            ) ? 'not-allowed' : 'pointer',
                            fontWeight: '600',
                            display: 'flex',
                            alignItems: 'center',
                            gap: '0.5rem'
                        }}
                    >
                        <Zap size={18} />
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

                    {evaluationResults && !evaluationResults.error && evaluationResults.recommendation && (
                        <div style={{ marginTop: '2rem' }}>
                            {/* Evaluation Configuration Info */}
                            {evaluationResults.structure_name && (
                                <div style={{ marginBottom: '1rem', padding: '1rem', background: 'var(--bg-primary)', borderRadius: 'var(--radius-md)', border: '1px solid var(--border-color)' }}>
                                    <div style={{ fontSize: '0.9rem', color: 'var(--text-secondary)' }}>
                                        <strong>Cấu trúc:</strong> {evaluationResults.structure_name}
                                    </div>

                                    <div style={{ fontSize: '0.9rem', color: 'var(--text-secondary)', marginTop: '0.25rem' }}>
                                        <strong>Dataset:</strong> {evaluationResults.dataset_size} mẫu
                                        (Train: {evaluationResults.train_samples}, Test: {evaluationResults.test_samples})
                                    </div>
                                </div>
                            )}

                            {/* Recommendation Box */}
                            <div style={{ padding: '1.5rem', background: '#dbeafe', border: '2px solid #3b82f6', borderRadius: 'var(--radius-md)' }}>
                                <div style={{ fontSize: '1rem', color: 'var(--text-secondary)', marginBottom: '0.5rem' }}>
                                    <strong>🎯 Mô hình được đề xuất:</strong>
                                </div>
                                <div style={{ fontSize: '1.25rem', fontWeight: '700', color: '#3b82f6' }}>
                                    {evaluationResults.recommendation}
                                </div>
                                <div style={{ fontSize: '0.95rem', color: 'var(--text-secondary)', marginTop: '0.5rem' }}>
                                    Độ chính xác: <strong>{evaluationResults.best_accuracy}%</strong>
                                </div>
                            </div>

                            {/* Detailed Metrics Table */}
                            {evaluationResults.models && (evaluationResults.models.knn || evaluationResults.models.kernel_regression || evaluationResults.models.lwlr) && (
                                <div style={{ marginTop: '1.5rem', overflowX: 'auto' }}>
                                    <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.9rem' }}>
                                        <thead>
                                            <tr style={{ background: 'var(--bg-primary)', borderBottom: '2px solid var(--border-color)' }}>
                                                <th style={{ padding: '0.75rem', textAlign: 'left', fontWeight: '600' }}>Mô hình</th>
                                                <th style={{ padding: '0.75rem', textAlign: 'center', fontWeight: '600' }}>MAE</th>
                                                <th style={{ padding: '0.75rem', textAlign: 'center', fontWeight: '600' }}>MSE</th>
                                                <th style={{ padding: '0.75rem', textAlign: 'center', fontWeight: '600' }}>RMSE</th>
                                                <th style={{ padding: '0.75rem', textAlign: 'center', fontWeight: '600' }}>Độ chính xác</th>
                                            </tr>
                                        </thead>
                                        <tbody>
                                            {['knn', 'kernel_regression', 'lwlr'].map(modelKey => {
                                                const modelData = evaluationResults.models[modelKey];
                                                if (!modelData) return null;
                                                const modelNames = {
                                                    knn: 'KNN',
                                                    kernel_regression: 'Kernel Regression',
                                                    lwlr: 'LWLR'
                                                };
                                                return (
                                                    <tr key={modelKey} style={{ borderBottom: '1px solid var(--border-color)' }}>
                                                        <td style={{ padding: '0.75rem', fontWeight: '500' }}>{modelNames[modelKey]}</td>
                                                        <td style={{ padding: '0.75rem', textAlign: 'center' }}>{modelData.mae ?? 'N/A'}</td>
                                                        <td style={{ padding: '0.75rem', textAlign: 'center' }}>{modelData.mse ?? 'N/A'}</td>
                                                        <td style={{ padding: '0.75rem', textAlign: 'center' }}>{modelData.rmse ?? 'N/A'}</td>
                                                        <td style={{ padding: '0.75rem', textAlign: 'center', fontWeight: '600', color: '#10b981' }}>
                                                            {modelData.accuracy ? `${modelData.accuracy}%` : 'N/A'}
                                                        </td>
                                                    </tr>
                                                );
                                            })}
                                        </tbody>
                                    </table>
                                </div>
                            )}
                        </div>
                    )}
                </div>
            </motion.div>
        </div>
    );
};

export default Developer;

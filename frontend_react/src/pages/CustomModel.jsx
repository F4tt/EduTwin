import React, { useState, useEffect } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import * as XLSX from 'xlsx';
import { Settings, Save, FileText, Upload, Database, Trash2, ChevronDown, ChevronUp, X } from 'lucide-react';
import { LineChart, Line, BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer } from 'recharts';
import axiosClient from '../api/axiosClient';

const CustomModel = () => {
    // Form states for creating new structure
    const [structureName, setStructureName] = useState('');
    const [numTimePoints, setNumTimePoints] = useState('');
    const [numSubjects, setNumSubjects] = useState('');
    const [timePointLabels, setTimePointLabels] = useState([]);
    const [subjectLabels, setSubjectLabels] = useState([]);
    const [structureConfirmed, setStructureConfirmed] = useState(false);
    const [savingStructure, setSavingStructure] = useState(false);
    const [structureMessage, setStructureMessage] = useState('');

    // Structure list and active structure
    const [allStructures, setAllStructures] = useState([]);
    const [expandedStructureId, setExpandedStructureId] = useState(null);

    // Per-structure data (keyed by structure_id)
    const [structureDatasets, setStructureDatasets] = useState({}); // Stats for each structure
    const [uploadingFiles, setUploadingFiles] = useState({}); // Upload states
    const [userScores, setUserScores] = useState({}); // User scores per structure {structureId: {subject_timepoint: value}}
    const [currentTimePoints, setCurrentTimePoints] = useState({}); // Selected time point per structure
    const [showScoreModal, setShowScoreModal] = useState(false);
    const [selectedStructureForScores, setSelectedStructureForScores] = useState(null);
    const [scoreInputs, setScoreInputs] = useState({});
    const [savingScores, setSavingScores] = useState(false);
    const [activeChartTab, setActiveChartTab] = useState({}); // Active tab per structure {structureId: 'Chung' | subjectName}

    useEffect(() => {
        fetchAllStructures();
    }, []);

    const fetchAllStructures = async () => {
        try {
            console.log('Fetching all structures...');
            const res = await axiosClient.get('/custom-model/teaching-structures');
            console.log('API Response:', res.data);
            const structures = res.data.structures || [];
            console.log('Structures found:', structures.length, structures);
            setAllStructures(structures);
            
            // Initialize current time points from database or default to first
            const defaultTimePoints = {};
            structures.forEach(struct => {
                if (struct.time_point_labels && struct.time_point_labels.length > 0) {
                    // Use current_time_point from database, or default to first time point
                    defaultTimePoints[struct.id] = struct.current_time_point || struct.time_point_labels[0];
                }
            });
            setCurrentTimePoints(prev => ({ ...prev, ...defaultTimePoints }));
            
            // Load user scores and dataset stats for each structure
            for (const struct of structures) {
                loadUserScores(struct.id);
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

    const loadUserScores = async (structureId) => {
        try {
            const res = await axiosClient.get(`/custom-model/user-scores/${structureId}`);
            const scoresData = res.data.scores || {};
            
            // Transform API format to include both actual and predicted with metadata
            const transformedScores = {};
            const timePointsWithActual = new Set();
            
            Object.keys(scoresData).forEach(key => {
                const scoreInfo = scoresData[key];
                transformedScores[key] = {
                    actual: scoreInfo.actual_score,
                    predicted: scoreInfo.predicted_score,
                    predictedSource: scoreInfo.predicted_source,
                    predictedStatus: scoreInfo.predicted_status
                };
                
                // Track time points that have actual scores
                if (scoreInfo.actual_score !== null && scoreInfo.actual_score !== undefined) {
                    const parts = key.split('_');
                    const timePoint = parts[parts.length - 1];
                    timePointsWithActual.add(timePoint);
                }
            });
            
            setUserScores(prev => ({
                ...prev,
                [structureId]: transformedScores
            }));
            
            // Auto-set current time point based on actual scores (prefer latest with actual data)
            if (timePointsWithActual.size > 0) {
                // Get structure to find latest time point with data
                const struct = allStructures.find(s => s.id === structureId);
                if (struct) {
                    let latestTP = null;
                    for (const tp of struct.time_point_labels) {
                        if (timePointsWithActual.has(tp)) {
                            latestTP = tp;
                        }
                    }
                    if (latestTP) {
                        setCurrentTimePoints(prev => ({
                            ...prev,
                            [structureId]: latestTP
                        }));
                    }
                }
            }
        } catch (e) {
            console.error('Error loading user scores:', e);
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
                subject_labels: subjectLabels
            });
            
            const res = await axiosClient.post('/custom-model/teaching-structure', {
                structure_name: structureName,
                num_time_points: parseInt(numTimePoints),
                num_subjects: parseInt(numSubjects),
                time_point_labels: timePointLabels,
                subject_labels: subjectLabels
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
            const res = await axiosClient.post('/custom-model/upload-dataset', formData, {
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
        
        // Set default chart tab if expanding
        if (newExpandedId === structureId && !activeChartTab[structureId]) {
            setActiveChartTab(prev => ({ ...prev, [structureId]: 'Chung' }));
        }
    };

    const openScoreModal = (struct) => {
        setSelectedStructureForScores(struct);
        setShowScoreModal(true);
        
        // Load existing scores for this structure and transform to simple format
        const structScores = userScores[struct.id] || {};
        const simpleScores = {};
        Object.keys(structScores).forEach(key => {
            const scoreInfo = structScores[key];
            // For input, use actual score if available
            if (scoreInfo && scoreInfo.actual !== null && scoreInfo.actual !== undefined) {
                simpleScores[key] = scoreInfo.actual;
            }
        });
        setScoreInputs(simpleScores);
        
        // Set default time point if not selected
        if (!currentTimePoints[struct.id] && struct.time_point_labels.length > 0) {
            setCurrentTimePoints(prev => ({
                ...prev,
                [struct.id]: struct.time_point_labels[0]
            }));
        }
    };

    const closeScoreModal = () => {
        setShowScoreModal(false);
        setSelectedStructureForScores(null);
    };

    const handleSaveCurrentTimePoint = async (structureId, newTimePoint) => {
        if (!newTimePoint) {
            setStructureMessage('Lỗi: Vui lòng chọn mốc thời gian');
            return;
        }

        try {
            await axiosClient.post(`/custom-model/update-current-time-point/${structureId}`, {
                current_time_point: newTimePoint
            });
            
            // Update local state
            setCurrentTimePoints(prev => ({
                ...prev,
                [structureId]: newTimePoint
            }));
            
            setStructureMessage('Đã lưu mốc thời gian hiện tại!');
            setTimeout(() => setStructureMessage(''), 3000);
        } catch (e) {
            console.error('Error saving current time point:', e);
            setStructureMessage('Lỗi: Không thể lưu mốc thời gian');
        }
    };

    const handleScoreChange = (key, value) => {
        setScoreInputs(prev => ({ ...prev, [key]: value }));
    };

    const handleSaveScores = async () => {
        if (!selectedStructureForScores) return;
        
        const structId = selectedStructureForScores.id;
        const currentTimePoint = currentTimePoints[structId];
        
        if (!currentTimePoint) {
            setStructureMessage('Lỗi: Vui lòng chọn mốc thời gian hiện tại');
            return;
        }

        setSavingScores(true);
        setStructureMessage('');

        try {
            // Validate and filter scores (only up to current time point)
            const validScores = {};
            let hasError = false;
            const currentIdx = selectedStructureForScores.time_point_labels.indexOf(currentTimePoint);

            Object.keys(scoreInputs).forEach(key => {
                const rawVal = String(scoreInputs[key] || '').trim();
                if (rawVal) {
                    const val = parseFloat(rawVal.replace(',', '.'));
                    if (isNaN(val) || val < 0.01 || val >= 10000) {
                        hasError = true;
                        return;
                    }
                    
                    // Parse key format: subject_timepoint
                    const parts = key.split('_');
                    if (parts.length >= 2) {
                        const timepoint = parts[parts.length - 1];
                        
                        // Only save scores up to current time point
                        const scoreIdx = selectedStructureForScores.time_point_labels.indexOf(timepoint);
                        
                        if (scoreIdx <= currentIdx && scoreIdx !== -1) {
                            validScores[key] = val;
                        }
                    }
                }
            });

            if (hasError) {
                setStructureMessage('Lỗi: Điểm số phải từ 0.01 đến 9999.99');
                setSavingScores(false);
                return;
            }

            if (Object.keys(validScores).length === 0) {
                setStructureMessage('Không có điểm nào để lưu');
                setSavingScores(false);
                setTimeout(() => setStructureMessage(''), 2000);
                closeScoreModal();
                return;
            }

            // Call API to save scores to database
            await axiosClient.post('/custom-model/user-scores', {
                structure_id: structId,
                scores: validScores
            });

            // Reload scores from server to get correct format with predictions
            await loadUserScores(structId);
            
            setStructureMessage('✓ Đã lưu điểm số thành công!');
            setTimeout(() => setStructureMessage(''), 3000);
            closeScoreModal();

        } catch (e) {
            setStructureMessage('Lỗi: ' + (e.response?.data?.detail || e.message));
        } finally {
            setSavingScores(false);
        }
    };

    const isUnsavedScore = (key, currentValue) => {
        if (!selectedStructureForScores) return false;
        
        const structId = selectedStructureForScores.id;
        const savedScores = userScores[structId] || {};
        
        const inputVal = String(currentValue || '').trim();
        if (!inputVal) return false;
        
        const parsedVal = parseFloat(inputVal.replace(',', '.'));
        if (isNaN(parsedVal)) return false;
        
        const scoreInfo = savedScores[key];
        const savedActual = scoreInfo?.actual;
        return parsedVal !== parseFloat(savedActual || 0);
    };

    // Build chart data for a structure
    const buildChartData = (struct) => {
        const structId = struct.id;
        const stats = structureDatasets[structId];
        const scores = userScores[structId] || {};
        const currentTP = currentTimePoints[structId];
        
        if (!stats || !stats.reference_count || !currentTP) {
            return null;
        }

        const currentIdx = struct.time_point_labels.indexOf(currentTP);
        if (currentIdx === -1) return null;

        const activeTab = activeChartTab[structId] || 'Chung';
        
        // Build data for line chart - follow DataViz.jsx pattern
        const chartData = struct.time_point_labels.map((tp, idx) => {
            const dataPoint = { name: tp };
            
            if (activeTab === 'Chung') {
                // Average across all subjects
                let sum = 0, count = 0;
                
                struct.subject_labels.forEach(subj => {
                    const key = `${subj}_${tp}`;
                    const scoreInfo = scores[key] || {};
                    
                    // Prefer actual, fallback to predicted
                    let val = null;
                    if (scoreInfo.actual !== null && scoreInfo.actual !== undefined) {
                        val = parseFloat(scoreInfo.actual);
                    } else if (scoreInfo.predicted !== null && scoreInfo.predicted !== undefined) {
                        val = parseFloat(scoreInfo.predicted);
                    }
                    
                    if (val !== null && !isNaN(val) && val > 0) {
                        sum += val;
                        count++;
                    }
                });
                
                if (count > 0) {
                    const avgValue = parseFloat((sum / count).toFixed(2));
                    dataPoint.display = avgValue;
                    // Split into past/future for line styling
                    dataPoint.pastValue = idx <= currentIdx ? avgValue : null;
                    dataPoint.futureValue = idx >= currentIdx ? avgValue : null;
                }
            } else {
                // Single subject
                const key = `${activeTab}_${tp}`;
                const scoreInfo = scores[key] || {};
                
                // Prefer actual, fallback to predicted
                let val = null;
                if (scoreInfo.actual !== null && scoreInfo.actual !== undefined) {
                    val = parseFloat(scoreInfo.actual);
                } else if (scoreInfo.predicted !== null && scoreInfo.predicted !== undefined) {
                    val = parseFloat(scoreInfo.predicted);
                }
                
                if (val !== null && !isNaN(val) && val > 0) {
                    dataPoint.display = val;
                    dataPoint.pastValue = idx <= currentIdx ? val : null;
                    dataPoint.futureValue = idx >= currentIdx ? val : null;
                }
            }
            
            return dataPoint;
        });

        return chartData;
    };

    // Get dataset stats display
    const getDatasetStatusInfo = (struct) => {
        const structId = struct.id;
        const stats = structureDatasets[structId];
        const scores = userScores[structId] || {};
        
        const totalCells = struct.num_time_points * struct.num_subjects;
        let filledCells = 0;
        let totalScores = 0; // Count both actual and predicted for chart display
        
        struct.time_point_labels.forEach(tp => {
            struct.subject_labels.forEach(subj => {
                const key = `${subj}_${tp}`;
                const scoreInfo = scores[key];
                // Count filled if actual score exists
                if (scoreInfo && scoreInfo.actual !== null && scoreInfo.actual !== undefined) {
                    const val = parseFloat(scoreInfo.actual);
                    if (!isNaN(val) && val > 0) {
                        filledCells++;
                        totalScores++;
                    }
                }
                // Also count predicted scores for chart display
                else if (scoreInfo && scoreInfo.predicted !== null && scoreInfo.predicted !== undefined) {
                    const val = parseFloat(scoreInfo.predicted);
                    if (!isNaN(val) && val > 0) {
                        totalScores++;
                    }
                }
            });
        });

        return {
            hasReferenceData: stats && stats.reference_count > 0,
            referenceCount: stats?.reference_count || 0,
            userScoreFilled: filledCells,
            userScoreTotal: totalCells,
            userScorePercent: totalCells > 0 ? Math.round((filledCells / totalCells) * 100) : 0,
            totalDataPoints: totalScores // New field: total actual + predicted scores
        };
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
                        Thiết Lập Mô Hình Tùy Chỉnh
                    </h1>
                    <p style={{ fontSize: '1rem', color: 'var(--text-secondary)' }}>
                        Tạo và quản lý các cấu trúc giảng dạy tùy chỉnh cho dự đoán điểm số
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

                                                            {/* User Scores */}
                                                            <div style={{
                                                                padding: '1.5rem',
                                                                background: '#dbeafe',
                                                                borderRadius: 'var(--radius-md)',
                                                                border: '1px solid #93c5fd'
                                                            }}>
                                                                <FileText size={24} style={{ color: '#2563eb', marginBottom: '0.75rem' }} />
                                                                <h6 style={{ fontSize: '0.9rem', fontWeight: '600', marginBottom: '0.5rem', color: 'var(--text-primary)' }}>
                                                                    Điểm của bạn
                                                                </h6>
                                                                <p style={{ fontSize: '0.8rem', color: 'var(--text-secondary)', marginBottom: '1rem' }}>
                                                                    Nhập để dự đoán
                                                                </p>
                                                                <button
                                                                    onClick={() => openScoreModal(struct)}
                                                                    style={{
                                                                        width: '100%',
                                                                        padding: '0.5rem',
                                                                        background: '#2563eb',
                                                                        color: 'white',
                                                                        border: 'none',
                                                                        borderRadius: 'var(--radius-md)',
                                                                        cursor: 'pointer',
                                                                        fontWeight: '600',
                                                                        fontSize: '0.85rem'
                                                                    }}
                                                                >
                                                                    Nhập điểm
                                                                </button>
                                                            </div>
                                                        </div>

                                                        {/* Dataset Status Section */}
                                                        {(() => {
                                                            const statusInfo = getDatasetStatusInfo(struct);
                                                            return (
                                                                <div style={{ marginBottom: '2rem' }}>
                                                                    <h5 style={{ fontSize: '1rem', fontWeight: '600', marginBottom: '1rem', color: 'var(--text-primary)' }}>
                                                                        Trạng thái tập dữ liệu:
                                                                    </h5>
                                                                    <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1rem' }}>
                                                                        {/* Reference Dataset Card */}
                                                                        <div style={{
                                                                            padding: '1.25rem',
                                                                            background: statusInfo.hasReferenceData ? '#ecfdf5' : '#fef3c7',
                                                                            borderRadius: 'var(--radius-md)',
                                                                            border: `2px solid ${statusInfo.hasReferenceData ? '#10b981' : '#f59e0b'}`
                                                                        }}>
                                                                            <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem', marginBottom: '0.75rem' }}>
                                                                                <Database size={20} style={{ color: statusInfo.hasReferenceData ? '#10b981' : '#f59e0b' }} />
                                                                                <h6 style={{ fontSize: '0.95rem', fontWeight: '600', margin: 0, color: 'var(--text-primary)' }}>
                                                                                    Tập dữ liệu tham chiếu 
                                                                                </h6>
                                                                            </div>
                                                                            <p style={{ fontSize: '0.85rem', color: 'var(--text-secondary)', marginBottom: '0.5rem' }}>
                                                                                {statusInfo.hasReferenceData 
                                                                                    ? `✓ Đã tải ${statusInfo.referenceCount} mẫu`
                                                                                    : '⚠ Chưa tải tập dữ liệu'}
                                                                            </p>
                                                                        </div>

                                                                        {/* User Scores Card */}
                                                                        <div style={{
                                                                            padding: '1.25rem',
                                                                            background: statusInfo.userScoreFilled > 0 ? '#dbeafe' : '#fee2e2',
                                                                            borderRadius: 'var(--radius-md)',
                                                                            border: `2px solid ${statusInfo.userScoreFilled > 0 ? '#3b82f6' : '#ef4444'}`
                                                                        }}>
                                                                            <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem', marginBottom: '0.75rem' }}>
                                                                                <FileText size={20} style={{ color: statusInfo.userScoreFilled > 0 ? '#3b82f6' : '#ef4444' }} />
                                                                                <h6 style={{ fontSize: '0.95rem', fontWeight: '600', margin: 0, color: 'var(--text-primary)' }}>
                                                                                    Điểm Của Bạn
                                                                                </h6>
                                                                            </div>
                                                                            <p style={{ fontSize: '0.85rem', color: 'var(--text-secondary)', marginBottom: '0.5rem' }}>
                                                                                {statusInfo.userScoreFilled > 0
                                                                                    ? `✓ Đã nhập ${statusInfo.userScoreFilled}/${statusInfo.userScoreTotal} điểm (${statusInfo.userScorePercent}%)`
                                                                                    : '⚠ Chưa nhập điểm nào'}
                                                                            </p>
                                                                        </div>
                                                                    </div>
                                                                </div>
                                                            );
                                                        })()}

                                                        {/* Charts Section */}
                                                        {(() => {
                                                            const statusInfo = getDatasetStatusInfo(struct);
                                                            const chartData = buildChartData(struct);
                                                            // Show charts if has reference data AND (has actual scores OR predicted scores)
                                                            const canShowCharts = statusInfo.hasReferenceData && statusInfo.totalDataPoints > 0 && chartData;
                                                            const activeTab = activeChartTab[struct.id] || 'Chung';

                                                            if (!canShowCharts) {
                                                                return (
                                                                    <div style={{
                                                                        padding: '2rem',
                                                                        background: '#f9fafb',
                                                                        borderRadius: 'var(--radius-md)',
                                                                        border: '2px dashed #d1d5db',
                                                                        textAlign: 'center'
                                                                    }}>
                                                                        <p style={{ fontSize: '1rem', color: 'var(--text-secondary)', marginBottom: '0.5rem' }}>
                                                                            📊 Biểu đồ không thể hiển thị
                                                                        </p>
                                                                        <p style={{ fontSize: '0.85rem', color: 'var(--text-tertiary)', margin: 0 }}>
                                                                            {!statusInfo.hasReferenceData && !statusInfo.userScoreFilled 
                                                                                ? 'Vui lòng tải Tập dữ liệu tham chiếu  và nhập điểm của bạn'
                                                                                : !statusInfo.hasReferenceData 
                                                                                    ? 'Vui lòng tải Tập dữ liệu tham chiếu '
                                                                                    : !statusInfo.userScoreFilled 
                                                                                        ? 'Vui lòng nhập điểm của bạn'
                                                                                        : !currentTimePoints[struct.id]
                                                                                            ? 'Vui lòng chọn mốc thời gian hiện tại'
                                                                                            : 'Đang tải dữ liệu...'}
                                                                        </p>
                                                                    </div>
                                                                );
                                                            }

                                                            return (
                                                                <div>
                                                                    <h5 style={{ fontSize: '1rem', fontWeight: '600', marginBottom: '1rem', color: 'var(--text-primary)' }}>
                                                                        Biểu đồ phân tích:
                                                                    </h5>

                                                                    {/* Tab Buttons */}
                                                                    <div style={{ display: 'flex', gap: '0.5rem', marginBottom: '1.5rem', flexWrap: 'wrap' }}>
                                                                        <button
                                                                            onClick={() => setActiveChartTab(prev => ({ ...prev, [struct.id]: 'Chung' }))}
                                                                            style={{
                                                                                padding: '0.5rem 1rem',
                                                                                background: activeTab === 'Chung' ? '#3b82f6' : '#e5e7eb',
                                                                                color: activeTab === 'Chung' ? 'white' : '#374151',
                                                                                border: 'none',
                                                                                borderRadius: 'var(--radius-md)',
                                                                                cursor: 'pointer',
                                                                                fontWeight: '600',
                                                                                fontSize: '0.85rem',
                                                                                transition: 'all 0.2s'
                                                                            }}
                                                                        >
                                                                            Chung
                                                                        </button>
                                                                        {struct.subject_labels.map((subject, idx) => (
                                                                            <button
                                                                                key={idx}
                                                                                onClick={() => setActiveChartTab(prev => ({ ...prev, [struct.id]: subject }))}
                                                                                style={{
                                                                                    padding: '0.5rem 1rem',
                                                                                    background: activeTab === subject ? '#3b82f6' : '#e5e7eb',
                                                                                    color: activeTab === subject ? 'white' : '#374151',
                                                                                    border: 'none',
                                                                                    borderRadius: 'var(--radius-md)',
                                                                                    cursor: 'pointer',
                                                                                    fontWeight: '600',
                                                                                    fontSize: '0.85rem',
                                                                                    transition: 'all 0.2s'
                                                                                }}
                                                                            >
                                                                                {subject}
                                                                            </button>
                                                                        ))}
                                                                    </div>

                                                                    {/* Line Chart */}
                                                                    <div style={{ marginBottom: '2rem' }}>
                                                                        <h6 style={{ fontSize: '0.9rem', fontWeight: '600', marginBottom: '1rem', color: 'var(--text-secondary)' }}>
                                                                            Biểu đồ xu hướng (Line Chart)
                                                                        </h6>
                                                                        <ResponsiveContainer width="100%" height={300}>
                                                                            <LineChart data={chartData}>
                                                                                <CartesianGrid strokeDasharray="3 3" />
                                                                                <XAxis dataKey="name" />
                                                                                <YAxis domain={[0, 'auto']} />
                                                                                <Tooltip />
                                                                                <Legend />
                                                                                <Line 
                                                                                    type="monotone" 
                                                                                    dataKey="pastValue" 
                                                                                    stroke="#3b82f6" 
                                                                                    strokeWidth={3}
                                                                                    dot={{ r: 5 }}
                                                                                    connectNulls
                                                                                    name="Xu hướng hiện tại"
                                                                                />
                                                                                <Line 
                                                                                    type="monotone" 
                                                                                    dataKey="futureValue" 
                                                                                    stroke="#f59e0b" 
                                                                                    strokeWidth={3}
                                                                                    strokeDasharray="6 4"
                                                                                    dot={{ r: 4 }}
                                                                                    connectNulls
                                                                                    name="Dự đoán"
                                                                                />
                                                                            </LineChart>
                                                                        </ResponsiveContainer>
                                                                    </div>

                                                                    {/* Bar Chart */}
                                                                    <div>
                                                                        <h6 style={{ fontSize: '0.9rem', fontWeight: '600', marginBottom: '1rem', color: 'var(--text-secondary)' }}>
                                                                            Biểu đồ cột (Bar Chart)
                                                                        </h6>
                                                                        <ResponsiveContainer width="100%" height={300}>
                                                                            <BarChart data={chartData}>
                                                                                <CartesianGrid strokeDasharray="3 3" />
                                                                                <XAxis dataKey="name" />
                                                                                <YAxis domain={[0, 'auto']} />
                                                                                <Tooltip />
                                                                                <Legend />
                                                                                <Bar 
                                                                                    dataKey="display" 
                                                                                    fill="#10b981"
                                                                                    name="Điểm số"
                                                                                />
                                                                            </BarChart>
                                                                        </ResponsiveContainer>
                                                                    </div>
                                                                </div>
                                                            );
                                                        })()}
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

                {/* Score Input Modal */}
                {showScoreModal && selectedStructureForScores && (
                    <div style={{
                        position: 'fixed',
                        top: 0,
                        left: 0,
                        right: 0,
                        bottom: 0,
                        background: 'rgba(0, 0, 0, 0.5)',
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'center',
                        zIndex: 1000,
                        padding: '1rem'
                    }}>
                        <motion.div
                            initial={{ opacity: 0, scale: 0.9 }}
                            animate={{ opacity: 1, scale: 1 }}
                            exit={{ opacity: 0, scale: 0.9 }}
                            style={{
                                background: 'white',
                                borderRadius: 'var(--radius-lg)',
                                padding: '2rem',
                                maxWidth: '900px',
                                width: '100%',
                                maxHeight: '80vh',
                                overflow: 'auto',
                                boxShadow: '0 20px 25px -5px rgba(0, 0, 0, 0.1), 0 10px 10px -5px rgba(0, 0, 0, 0.04)'
                            }}
                        >
                            {/* Modal Header */}
                            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1.5rem', borderBottom: '2px solid #e5e7eb', paddingBottom: '1rem' }}>
                                <h3 style={{ fontSize: '1.5rem', fontWeight: '700', color: 'var(--text-primary)', margin: 0 }}>
                                    Nhập điểm - {selectedStructureForScores.structure_name}
                                </h3>
                                <button
                                    onClick={closeScoreModal}
                                    style={{
                                        background: 'none',
                                        border: 'none',
                                        cursor: 'pointer',
                                        padding: '0.5rem',
                                        color: '#6b7280'
                                    }}
                                >
                                    <X size={24} />
                                </button>
                            </div>

                            {/* Current Time Point Selector */}
                            <div style={{ marginBottom: '2rem', padding: '1rem', background: '#f9fafb', borderRadius: 'var(--radius-md)', border: '1px solid #e5e7eb' }}>
                                <label style={{ display: 'block', marginBottom: '0.75rem', fontWeight: '600', color: 'var(--text-primary)' }}>
                                    Mốc thời gian hiện tại của bạn:
                                </label>
                                <div style={{ display: 'flex', gap: '0.75rem', alignItems: 'center' }}>
                                    <select
                                        value={currentTimePoints[selectedStructureForScores.id] || ''}
                                        onChange={async (e) => {
                                            const newTimePoint = e.target.value;
                                            // Update local state immediately
                                            setCurrentTimePoints(prev => ({
                                                ...prev,
                                                [selectedStructureForScores.id]: newTimePoint
                                            }));
                                            // Auto-save to backend
                                            if (newTimePoint) {
                                                try {
                                                    await axiosClient.post(`/custom-model/update-current-time-point/${selectedStructureForScores.id}`, {
                                                        current_time_point: newTimePoint
                                                    });
                                                    console.log('Auto-saved current time point:', newTimePoint);
                                                } catch (e) {
                                                    console.error('Error auto-saving time point:', e);
                                                }
                                            }
                                        }}
                                        style={{
                                            flex: 1,
                                            padding: '0.75rem',
                                            borderRadius: 'var(--radius-md)',
                                            border: '2px solid #3b82f6',
                                            fontSize: '1rem',
                                            fontWeight: '500',
                                            color: 'var(--text-primary)',
                                            background: 'white'
                                        }}
                                    >
                                        <option value="">-- Chọn mốc thời gian --</option>
                                        {selectedStructureForScores.time_point_labels.map((label, idx) => (
                                            <option key={idx} value={label}>{label}</option>
                                        ))}
                                    </select>
                                    {/* Auto-save enabled - no manual save button needed */}
                                </div>
                                <p style={{ fontSize: '0.875rem', color: '#6b7280', marginTop: '0.5rem', marginBottom: 0 }}>
                                    💡 Mốc thời gian được lưu tự động khi bạn chọn
                                </p>
                                <p style={{ fontSize: '0.85rem', color: '#6b7280', marginTop: '0.5rem', marginBottom: 0 }}>
                                    💡 Chỉ có thể nhập điểm cho các mốc thời gian từ đầu đến mốc hiện tại (Điểm số {'>'} 0 và {'<'} 10000)
                                </p>
                            </div>

                            {currentTimePoints[selectedStructureForScores.id] ? (
                                <>
                                    {/* Score Inputs by Time Point */}
                                    {selectedStructureForScores.time_point_labels.map((timePoint, tpIdx) => {
                                        const currentTimePoint = currentTimePoints[selectedStructureForScores.id];
                                        const currentIdx = selectedStructureForScores.time_point_labels.indexOf(currentTimePoint);
                                        const isFutureTimePoint = tpIdx > currentIdx;
                                        
                                        return (
                                            <div 
                                                key={tpIdx} 
                                                style={{ 
                                                    marginBottom: '2rem',
                                                    opacity: isFutureTimePoint ? 0.4 : 1,
                                                    pointerEvents: isFutureTimePoint ? 'none' : 'auto'
                                                }}
                                            >
                                                <h4 style={{ 
                                                    fontSize: '1.1rem', 
                                                    fontWeight: '600', 
                                                    marginBottom: '1rem', 
                                                    color: 'var(--text-primary)',
                                                    display: 'flex',
                                                    alignItems: 'center',
                                                    gap: '0.5rem'
                                                }}>
                                                    📊 {timePoint}
                                                    {isFutureTimePoint && (
                                                        <span style={{
                                                            fontSize: '0.75rem',
                                                            padding: '0.25rem 0.5rem',
                                                            background: '#fef3c7',
                                                            color: '#92400e',
                                                            borderRadius: 'var(--radius-sm)',
                                                            fontWeight: '500'
                                                        }}>
                                                            Chưa tới
                                                        </span>
                                                    )}
                                                </h4>
                                                <div style={{ 
                                                    display: 'grid', 
                                                    gridTemplateColumns: 'repeat(auto-fill, minmax(200px, 1fr))', 
                                                    gap: '1rem' 
                                                }}>
                                                    {selectedStructureForScores.subject_labels.map((subject, subIdx) => {
                                                        const key = `${subject}_${timePoint}`;
                                                        const scoreInfo = userScores[selectedStructureForScores.id]?.[key] || {};
                                                        const value = scoreInputs[key] || '';
                                                        const hasUnsavedChanges = isUnsavedScore(key, value);
                                                        
                                                        // Determine placeholder and styling based on time point and data
                                                        let placeholder = 'Nhập điểm';
                                                        let placeholderClass = '';
                                                        let showBadge = false;
                                                        let badgeText = '';
                                                        
                                                        if (scoreInfo.actual !== null && scoreInfo.actual !== undefined) {
                                                            // Has actual score - no placeholder needed
                                                            placeholder = '';
                                                        } else if (isFutureTimePoint) {
                                                            // Future time point - show predicted value in yellow
                                                            if (scoreInfo.predicted !== null && scoreInfo.predicted !== undefined) {
                                                                placeholder = parseFloat(scoreInfo.predicted).toFixed(2);
                                                                placeholderClass = 'custom-placeholder-yellow';
                                                                showBadge = true;
                                                                badgeText = 'Dự đoán';
                                                            }
                                                        } else {
                                                            // Past/current time point
                                                            if (scoreInfo.predictedSource === 'knn_imputer' && scoreInfo.predicted !== null) {
                                                                // KNN imputed value - show in gray
                                                                placeholder = parseFloat(scoreInfo.predicted).toFixed(2);
                                                                placeholderClass = 'custom-placeholder-gray';
                                                                showBadge = true;
                                                                badgeText = 'Dự đoán';
                                                            }
                                                            // Empty with no imputed value - leave blank
                                                        }
                                                        
                                                        return (
                                                            <div key={subIdx}>
                                                                <label style={{ 
                                                                    display: 'block', 
                                                                    marginBottom: '0.5rem', 
                                                                    fontSize: '0.9rem', 
                                                                    fontWeight: '500', 
                                                                    color: 'var(--text-secondary)' 
                                                                }}>
                                                                    {subject}
                                                                </label>
                                                                <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                                                                    <input
                                                                        type="number"
                                                                        min="0.01"
                                                                        max="9999.99"
                                                                        step="0.01"
                                                                        value={value}
                                                                        onChange={(e) => handleScoreChange(key, e.target.value)}
                                                                        placeholder={placeholder}
                                                                        disabled={isFutureTimePoint}
                                                                        style={{
                                                                            width: '100%',
                                                                            padding: '0.75rem',
                                                                            borderRadius: 'var(--radius-md)',
                                                                            border: hasUnsavedChanges ? '2px solid #dc2626' : '1px solid var(--border-color)',
                                                                            fontSize: '1rem',
                                                                            background: hasUnsavedChanges ? '#fef2f2' : 'white',
                                                                            boxShadow: hasUnsavedChanges ? '0 0 0 3px rgba(220, 38, 38, 0.1)' : 'none',
                                                                            transition: 'all 0.2s'
                                                                        }}
                                                                        className={placeholderClass}
                                                                    />
                                                                    {showBadge && (
                                                                        <div style={{ 
                                                                            fontSize: '0.75rem', 
                                                                            color: 'var(--text-secondary)', 
                                                                            padding: '2px 8px', 
                                                                            borderRadius: '12px', 
                                                                            background: 'var(--secondary-light)', 
                                                                            border: '1px solid var(--border-color)',
                                                                            whiteSpace: 'nowrap'
                                                                        }}>
                                                                            {badgeText}
                                                                        </div>
                                                                    )}
                                                                </div>
                                                            </div>
                                                        );
                                                    })}
                                                </div>
                                            </div>
                                        );
                                    })}

                                    {/* Modal Actions */}
                                    <div style={{ 
                                        display: 'flex', 
                                        gap: '1rem', 
                                        justifyContent: 'flex-end',
                                        paddingTop: '1.5rem',
                                        borderTop: '2px solid #e5e7eb'
                                    }}>
                                        <button
                                            onClick={closeScoreModal}
                                            disabled={savingScores}
                                            style={{
                                                padding: '0.75rem 1.5rem',
                                                borderRadius: 'var(--radius-md)',
                                                border: '1px solid var(--border-color)',
                                                background: 'white',
                                                color: 'var(--text-primary)',
                                                cursor: savingScores ? 'not-allowed' : 'pointer',
                                                fontWeight: '600',
                                                fontSize: '1rem'
                                            }}
                                        >
                                            Hủy
                                        </button>
                                        <button
                                            onClick={handleSaveScores}
                                            disabled={savingScores}
                                            style={{
                                                padding: '0.75rem 2rem',
                                                borderRadius: 'var(--radius-md)',
                                                background: savingScores ? '#9ca3af' : '#3b82f6',
                                                color: 'white',
                                                border: 'none',
                                                cursor: savingScores ? 'not-allowed' : 'pointer',
                                                fontWeight: '600',
                                                fontSize: '1rem',
                                                display: 'flex',
                                                alignItems: 'center',
                                                gap: '0.5rem'
                                            }}
                                        >
                                            <Save size={18} />
                                            {savingScores ? 'Đang lưu...' : 'Lưu điểm'}
                                        </button>
                                    </div>
                                </>
                            ) : (
                                <div style={{
                                    padding: '3rem',
                                    textAlign: 'center',
                                    color: '#6b7280'
                                }}>
                                    <p style={{ fontSize: '1rem', marginBottom: '0.5rem' }}>
                                        ⬆️ Vui lòng chọn mốc thời gian hiện tại của bạn
                                    </p>
                                    <p style={{ fontSize: '0.85rem' }}>
                                        Để bắt đầu nhập điểm số
                                    </p>
                                </div>
                            )}
                        </motion.div>
                    </div>
                )}
            </motion.div>
        </div>
    );
};

export default CustomModel;

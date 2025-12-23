import React, { useState, useEffect, useMemo, useCallback, useRef } from 'react';
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer, BarChart, Bar, RadarChart, PolarGrid, PolarAngleAxis, PolarRadiusAxis, Radar, Cell, LabelList } from 'recharts';
import axiosClient from '../api/axiosClient';
import { useAuth } from '../context/AuthContext';
import { calculateChartDomain, formatScore, getScaleMax } from '../utils/scaleUtils';
import {
    REFRESH_DATA_EVENTS,
    ML_PIPELINE_PROCESSING_EVENT,
    ML_PIPELINE_COMPLETED_EVENT,
} from '../utils/eventBus';
import { useIsMobile } from '../hooks/useIsMobile';

const formatScoreValue = (value) => {
    if (value === null || value === undefined || Number.isNaN(Number(value))) return null;
    return Number(value).toFixed(2);
};

const renderLineLabel = ({ x, y, value }) => {
    if (value === null || value === undefined) return null;
    return (
        <text x={x} y={y - 8} textAnchor="middle" fill="#444" fontSize={11}>
            {formatScoreValue(value)}
        </text>
    );
};

const renderFutureLineLabel = (props) => {
    const { value } = props;
    if (value === null || value === undefined) return null;
    return renderLineLabel(props);
};

const renderBarLabel = ({ x, y, width, value }) => {
    if (value === null || value === undefined) return null;
    const textX = x + width + 6;
    const textY = y + 4;
    return (
        <text x={textX} y={textY} textAnchor="start" fill="#444" fontSize={11}>
            {formatScoreValue(value)}
        </text>
    );
};

const renderRadarLabel = (props) => {
    const { x, y, value, cx, cy } = props;
    if (value === null || value === undefined) return null;

    // If cx/cy are available, calculate outward position
    let labelX = x;
    let labelY = y;

    if (cx !== undefined && cy !== undefined) {
        const angle = Math.atan2(y - cy, x - cx);
        const offset = 25; // Reduced offset to prevent clipping
        labelX = x + Math.cos(angle) * offset;
        labelY = y + Math.sin(angle) * offset;
    } else {
        // Fallback: just place it slightly above
        labelY = y - 15;
    }

    return (
        <text
            x={labelX}
            y={labelY}
            textAnchor="middle"
            dominantBaseline="middle"
            fill="#5a67d8"
            fontSize={13}
            fontWeight="700"
            style={{
                textShadow: '0 0 3px white, 0 0 3px white, 0 0 3px white',
                pointerEvents: 'none'
            }}
        >
            {formatScoreValue(value)}
        </text>
    );
};

// Moved into component - needs access to activeStructure

const computeTermAverageMap = (data) => {
    const buckets = new Map();
    data.forEach(item => {
        const displayValue = item.actual !== null && item.actual !== undefined
            ? Number(item.actual)
            : item.predicted !== null && item.predicted !== undefined
                ? Number(item.predicted)
                : null;
        if (displayValue === null || Number.isNaN(displayValue)) return;
        const timepointKey = item.timepoint;
        if (!buckets.has(timepointKey)) buckets.set(timepointKey, []);
        buckets.get(timepointKey).push(displayValue);
    });

    const averages = new Map();
    buckets.forEach((values, key) => {
        const avg = values.reduce((sum, val) => sum + val, 0) / values.length;
        // Round to 2 decimal places for consistent display
        averages.set(key, Math.round(avg * 100) / 100);
    });
    return averages;
};

// Function to get XAxis ticks without the highest value
const getXAxisTicks = (data) => {
    if (!data || data.length === 0) return [];
    const allTerms = data.map(d => d.term);
    // Remove the last (highest) value
    return allTerms.slice(0, -1);
};

// Format Y-axis tick: hide very small numbers and format nicely
const formatYAxisTick = (value, index, ticks) => {
    // Hide values that are essentially zero or very small decimals
    if (value < 0.01 && value > -0.01 && value !== 0) return '';
    // Hide the maximum tick if it's the last one (topmost)
    if (ticks && index === ticks.length - 1) return '';
    // Format number nicely
    if (Number.isInteger(value)) return value;
    return Number(value).toFixed(1);
};

// Format X-axis tick for BarCharts: round to 2 decimal places
const formatBarXAxisTick = (value) => {
    if (value === null || value === undefined || Number.isNaN(Number(value))) return '';
    return Number(value).toFixed(2);
};

// Moved into component - needs access to activeStructure

const TermAverageTooltip = ({ active, payload, formatTermLabel }) => {
    if (!active || !payload || payload.length === 0) {
        return null;
    }
    const point = payload[0].payload;
    if (point.display === null || point.display === undefined) {
        return null;
    }

    return (
        <div style={{
            background: 'white',
            padding: '8px 12px',
            border: '1px solid #ccc',
            borderRadius: '6px',
            boxShadow: '0 2px 8px rgba(0,0,0,0.15)'
        }}>
            <p style={{ margin: 0, fontSize: '0.9rem', fontWeight: 600, color: '#333' }}>
                {point.term}
            </p>
            <p style={{ margin: '4px 0 0 0', fontSize: '0.85rem', color: '#d32f2f' }}>
                {formatTermLabel(point.term)}
            </p>
            <p style={{ margin: '4px 0 0 0', fontSize: '0.85rem', color: '#555' }}>
                Điểm trung bình: {Number(point.display).toFixed(2)}
            </p>
        </div>
    );
};

const TrendLegend = ({ color, showPast, showFuture }) => {
    if (!showPast && !showFuture) return null;
    return (
        <div style={{ display: 'flex', gap: '1.5rem', flexWrap: 'wrap', marginTop: '0.75rem', fontSize: '0.85rem', color: '#555' }}>
            {showPast && (
                <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                    <span style={{ width: '30px', borderTop: `3px solid ${color}` }} />
                    <span>Xu hướng hiện tại</span>
                </div>
            )}
            {showFuture && (
                <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                    <span style={{ width: '30px', borderTop: `3px dashed ${color}` }} />
                    <span>Xu hướng dự đoán</span>
                </div>
            )}
        </div>
    );
};

const InsightBox = ({ title, text, compact = false }) => {
    if (!text) return null;
    return (
        <div
            style={{
                marginTop: compact ? '1rem' : '1.5rem',
                padding: compact ? '1.25rem 1.5rem' : '1.75rem 2rem',
                background: 'linear-gradient(135deg, #667eea15 0%, #764ba215 100%)',
                borderRadius: '16px',
                border: '2px solid #e8eaf6',
                boxShadow: '0 4px 12px rgba(102, 126, 234, 0.08)',
                color: '#2c3e50',
                fontSize: compact ? '0.95rem' : '1rem',
                lineHeight: 1.7,
                position: 'relative',
                overflow: 'hidden',
            }}
        >
            <div style={{
                position: 'absolute',
                top: 0,
                left: 0,
                width: '5px',
                height: '100%',
                background: 'linear-gradient(180deg, #667eea 0%, #764ba2 100%)',
            }} />
            {title && (
                <div style={{
                    display: 'flex',
                    alignItems: 'center',
                    gap: '0.75rem',
                    marginBottom: compact ? '0.75rem' : '1rem',
                    fontWeight: '700',
                    fontSize: compact ? '1.05rem' : '1.15rem',
                    color: '#5a67d8',
                }}>
                    <span style={{ fontSize: '1.4rem' }}></span>
                    <span>{title}</span>
                </div>
            )}
            <div style={{
                paddingLeft: title ? '0' : '0',
                color: '#34495e',
                fontWeight: '400',
            }}>
                {text}
            </div>
        </div>
    );
};

// Function to get user-specific storage key
const getAiCommentsStorageKey = (userId) => `dataviz_ai_comments_user_${userId || 'anonymous'}`;
const AI_COMMENTS_VERSION = 3;

const DataViz = () => {
    const { user } = useAuth();
    const isMobile = useIsMobile();
    const [scores, setScores] = useState([]);
    const [termAverages, setTermAverages] = useState([]);
    const [currentGrade, setCurrentGrade] = useState(null);
    const [activeTab, setActiveTab] = useState('Chung');
    const [loading, setLoading] = useState(true);
    const [aiInsights, setAiInsights] = useState(null);
    const [pipelineStatus, setPipelineStatus] = useState({ type: '', text: '' });
    const [aiProcessing, setAiProcessing] = useState(false);
    const pipelineTimeoutRef = useRef(null);

    // Active structure state
    const [activeStructure, setActiveStructure] = useState(null);
    const [loadingStructure, setLoadingStructure] = useState(true);

    // Custom combination state
    const [customSubject1, setCustomSubject1] = useState('');
    const [customSubject2, setCustomSubject2] = useState('');
    const [customSubject3, setCustomSubject3] = useState('');

    // Fetch active structure
    const fetchActiveStructure = useCallback(async () => {
        try {
            setLoadingStructure(true);
            console.log('[DataViz] Fetching active structure...');
            const res = await axiosClient.get('/custom-model/get-active-structure');
            console.log('[DataViz] Active structure response:', res.data);
            console.log('[DataViz] subject_labels from API:', res.data.subject_labels);

            if (res.data.has_structure) {
                const structureData = {
                    id: res.data.structure_id,
                    name: res.data.structure_name,
                    timePoints: res.data.time_point_labels || [],
                    subjects: res.data.subject_labels || [],
                    scaleType: res.data.scale_type || '0-10'
                };
                console.log('[DataViz] Setting activeStructure:', structureData);
                console.log('[DataViz] structureData.subjects:', structureData.subjects);
                setActiveStructure(structureData);

                // Fetch current_timepoint for this structure
                try {
                    const timepointRes = await axiosClient.get(`/user/current-timepoint/${structureData.id}`);
                    console.log('[DataViz] Current timepoint response:', timepointRes.data);
                    const currentTimepoint = timepointRes.data.current_timepoint;
                    if (currentTimepoint && structureData.timePoints.includes(currentTimepoint)) {
                        console.log('[DataViz] Setting currentGrade from structure preference:', currentTimepoint);
                        setCurrentGrade(currentTimepoint);
                    } else {
                        console.log('[DataViz] No valid current_timepoint for this structure');
                        setCurrentGrade(null);
                    }
                } catch (timepointErr) {
                    console.error('[DataViz] Error fetching current timepoint:', timepointErr);
                    setCurrentGrade(null);
                }
            } else {
                console.log('[DataViz] No active structure found');
                setActiveStructure(null);
                setCurrentGrade(null);
            }
        } catch (e) {
            console.error('[DataViz] Error fetching active structure:', e);
            setActiveStructure(null);
            setCurrentGrade(null);
        } finally {
            setLoadingStructure(false);
        }
    }, []);

    useEffect(() => {
        fetchActiveStructure();
    }, [fetchActiveStructure]);

    // Track previous structure ID to detect actual changes
    const prevStructureIdRef = useRef(null);

    // Clear AI insights when activeStructure changes (prevents showing stale insights from different structure)
    useEffect(() => {
        const currentStructureId = activeStructure?.id;
        const prevStructureId = prevStructureIdRef.current;

        // Only clear if we're switching FROM one structure TO another (not on initial load)
        if (prevStructureId !== null && currentStructureId !== null && prevStructureId !== currentStructureId) {
            console.log(`[DataViz] Structure changed from ${prevStructureId} to ${currentStructureId}, clearing AI insights`);
            setAiInsights(null);
            // Also clear localStorage cache for this user to ensure fresh insights
            if (typeof window !== 'undefined' && window.localStorage && user?.user_id) {
                try {
                    const storageKey = getAiCommentsStorageKey(user.user_id);
                    window.localStorage.removeItem(storageKey);
                    console.log('[DataViz] Cleared localStorage AI cache for structure change');
                } catch (e) {
                    console.error('[DataViz] Failed to clear localStorage AI cache:', e);
                }
            }
        }

        // Update ref for next comparison
        prevStructureIdRef.current = currentStructureId;
    }, [activeStructure?.id, user?.user_id]); // Only trigger when structure ID changes

    // Helper functions that depend on activeStructure
    const formatTermLabel = useCallback((term) => {
        // Return timepoint label as-is from structure
        return term || '';
    }, []);

    const formatCurrentTerm = useCallback((term) => {
        const formatted = formatTermLabel(term);
        return formatted || null;
    }, [formatTermLabel]);

    const slotIndexForTerm = useCallback((token) => {
        if (!token || !activeStructure?.timePoints) return null;
        const normalized = String(token).toUpperCase();
        for (let i = 0; i < activeStructure.timePoints.length; i += 1) {
            if (activeStructure.timePoints[i].toUpperCase() === normalized) {
                return i;
            }
        }
        return null;
    }, [activeStructure]);

    const buildTermSeries = useCallback((termAverageMap, currentIdx) => {
        if (!activeStructure?.timePoints) return [];
        return activeStructure.timePoints.map((term, idx) => {
            const average = termAverageMap.has(term) ? Number(termAverageMap.get(term)) : null;
            if (average === null || Number.isNaN(average)) {
                return {
                    term,
                    label: formatTermLabel(term),
                    display: null,
                    pastValue: null,
                    futureValue: null,
                };
            }

            const rounded = Number(average.toFixed(2));
            const pastValue = currentIdx === null || idx <= currentIdx ? rounded : null;
            const futureValue = currentIdx !== null && idx >= currentIdx ? rounded : null;

            return {
                term,
                label: formatTermLabel(term),
                display: rounded,
                pastValue,
                futureValue,
            };
        });
    }, [activeStructure, formatTermLabel]);

    const fetchData = useCallback(async (silent = false) => {
        try {
            if (!silent) {
                setLoading(true);
            }

            // Wait for activeStructure to load first
            if (loadingStructure) {
                console.log('[DataViz] Waiting for structure to load...');
                return;
            }

            // If no active structure, don't fetch anything - UI will show empty state
            if (!activeStructure?.id) {
                console.log('[DataViz] No active structure, skipping data fetch');
                setScores([]);
                setTermAverages([]);
                setCurrentGrade(null);
                if (!silent) {
                    setLoading(false);
                }
                return;
            }

            // Fetch from custom model
            console.log('[DataViz] Fetching data for structure:', activeStructure.name);
            const res = await axiosClient.get(`/custom-model/user-scores/${activeStructure.id}`);
            const scoreData = res.data.scores || {};

            console.log('[DataViz] Raw score data:', scoreData);

            // Transform custom scores to old format for compatibility
            const transformedScores = [];
            Object.entries(scoreData).forEach(([key, scoreInfo]) => {
                // Key format: "subject_timepoint"
                const parts = key.split('_');

                console.log('[DataViz] Parsing key:', key, '→ parts:', parts);

                if (parts.length >= 2) {
                    const subject = parts[0].trim(); // TRIM whitespace from subject name
                    const timepoint = parts.slice(1).join('_'); // Join remaining parts as timepoint

                    console.log('[DataViz] Extracted:', { subject, timepoint });

                    // Create single entry with both actual and predicted
                    transformedScores.push({
                        subject,
                        timepoint,
                        actual: scoreInfo.actual_score !== null && scoreInfo.actual_score !== undefined ? scoreInfo.actual_score : null,
                        predicted: scoreInfo.predicted_score !== null && scoreInfo.predicted_score !== undefined ? scoreInfo.predicted_score : null
                    });
                }
            });

            console.log('[DataViz] Transformed scores:', transformedScores);
            setScores(transformedScores);

            // Calculate term averages from transformed scores using structure's timePoints
            const termAvgMap = new Map();
            transformedScores.forEach(score => {
                const value = score.actual !== null ? score.actual : score.predicted;
                if (value !== null && score.timepoint) {
                    if (!termAvgMap.has(score.timepoint)) {
                        termAvgMap.set(score.timepoint, []);
                    }
                    termAvgMap.get(score.timepoint).push(value);
                }
            });

            const termAveragesArray = Array.from(termAvgMap.entries()).map(([timepoint, values]) => ({
                timepoint,
                average: values.reduce((sum, v) => sum + v, 0) / values.length
            }));
            console.log('[DataViz] Term averages:', termAveragesArray);
            setTermAverages(termAveragesArray);

        } catch (e) {
            console.error(e);
        } finally {
            if (!silent) {
                setLoading(false);
            }
        }
    }, [activeStructure, loadingStructure]);

    useEffect(() => {
        fetchData();
    }, [fetchData]);

    useEffect(() => {
        const handler = () => {
            fetchData(true);
            // Also refresh currentGrade from user profile when scores updated
            fetchActiveStructure();
        };
        REFRESH_DATA_EVENTS.forEach(evt => window.addEventListener(evt, handler));
        return () => {
            REFRESH_DATA_EVENTS.forEach(evt => window.removeEventListener(evt, handler));
        };
    }, [fetchData, fetchActiveStructure]);

    useEffect(() => {
        const interval = setInterval(() => fetchData(true), 60000);
        return () => clearInterval(interval);
    }, [fetchData]);

    useEffect(() => {
        const handleProcessing = (event) => {
            if (pipelineTimeoutRef.current) {
                clearTimeout(pipelineTimeoutRef.current);
            }
            const detail = event?.detail || {};
            setPipelineStatus({ type: 'info', text: detail.message || 'Pipeline đang chạy, dữ liệu sẽ được cập nhật...' });
        };
        const handleCompleted = (event) => {
            if (pipelineTimeoutRef.current) {
                clearTimeout(pipelineTimeoutRef.current);
            }
            const detail = event?.detail || {};
            if (detail.error) {
                setPipelineStatus({ type: 'error', text: detail.error });
            } else {
                const stats = detail.stats || detail.pipeline || {};
                const processed = stats.processed_users ? ` (${stats.processed_users} người dùng)` : '';
                setPipelineStatus({ type: 'success', text: detail.message || `Pipeline đã hoàn tất${processed}.` });
            }
            pipelineTimeoutRef.current = setTimeout(() => setPipelineStatus({ type: '', text: '' }), 4000);
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

    const persistAiInsightsState = useCallback((insights, version = AI_COMMENTS_VERSION) => {
        setAiInsights(insights);
        if (typeof window === 'undefined' || !window.localStorage) return;
        try {
            const storageKey = getAiCommentsStorageKey(user?.user_id);
            window.localStorage.setItem(storageKey, JSON.stringify({ version, insights }));
        } catch (storageErr) {
            console.error('Failed to persist AI comments', storageErr);
        }
    }, [user?.user_id]);

    useEffect(() => {
        if (typeof window === 'undefined' || !window.localStorage) return;

        // Clear insights first when user or structure changes
        setAiInsights(null);

        // If no user, don't load any insights
        if (!user?.user_id) {
            console.log('[DataViz] No user logged in, skipping AI insights load');
            return;
        }

        // If no active structure, don't load insights
        if (!activeStructure?.id) {
            console.log('[DataViz] No active structure, skipping AI insights load');
            return;
        }

        // Step 1: Load từ localStorage ngay lập tức (instant UX) - per user AND structure
        const storageKey = getAiCommentsStorageKey(user.user_id, activeStructure.id);
        try {
            const raw = window.localStorage.getItem(storageKey);
            if (raw) {
                const parsed = JSON.parse(raw);
                if (parsed && parsed.version === AI_COMMENTS_VERSION && parsed.insights) {
                    setAiInsights(parsed.insights);
                    console.log('[DataViz] Loaded AI insights from localStorage cache for user:', user.user_id, 'structure:', activeStructure.id);
                } else {
                    window.localStorage.removeItem(storageKey);
                }
            }
        } catch (storageErr) {
            console.error('Failed to restore AI comments from localStorage', storageErr);
        }

        // Step 2: Fetch từ database trong background (cross-device sync)
        const fetchFromDatabase = async () => {
            try {
                console.log('[DataViz] Fetching AI insights from database for structure:', activeStructure.id);
                const res = await axiosClient.get('/chatbot/insights', {
                    params: {
                        insight_type: 'slide_comment',
                        structure_id: activeStructure.id  // Filter by current structure
                    }
                });

                console.log('[DataViz] Fetched insights:', res.data);

                if (res.data.insights && res.data.insights.length > 0) {
                    // Reconstruct slide_comments structure từ database
                    const slideComments = {
                        overview: {},
                        exam_blocks: { blocks: {} },
                        subjects: {}
                    };

                    res.data.insights.forEach(insight => {
                        const { context_key, content } = insight;

                        // Backend saves context_key as: "{active_tab}_{section}"
                        // Examples: "Chung_summary", "Tổ Hợp_A00", "Từng Môn_Toán"

                        if (context_key?.startsWith('Chung_')) {
                            const section = context_key.replace('Chung_', '');
                            slideComments.overview[section] = {
                                comment: content,
                                narrative: { comment: content }
                            };
                        } else if (context_key?.startsWith('Tổ Hợp_')) {
                            const block = context_key.replace('Tổ Hợp_', '');
                            slideComments.exam_blocks.blocks[block] = {
                                comment: content,
                                narrative: { comment: content }
                            };
                        } else if (context_key?.startsWith('Từng Môn_')) {
                            const subject = context_key.replace('Từng Môn_', '');
                            slideComments.subjects[subject] = {
                                comment: content,
                                narrative: { comment: content }
                            };
                        }
                    });

                    console.log('[DataViz] Reconstructed slide comments:', slideComments);

                    // Update state và localStorage
                    setAiInsights(slideComments);
                    window.localStorage.setItem(
                        storageKey,
                        JSON.stringify({ version: AI_COMMENTS_VERSION, insights: slideComments })
                    );

                    console.log('[DataViz] ✅ Synced AI insights from database (per-user, per-structure)');
                } else {
                    // No insights in database - clear any stale cache
                    console.log('[DataViz] No insights found in database for this user/structure');
                    setAiInsights(null);
                    window.localStorage.removeItem(storageKey);
                }
            } catch (error) {
                console.error('[DataViz] Failed to fetch insights from database:', error);
                // Không cần alert - localStorage cache vẫn hoạt động
            }
        };

        fetchFromDatabase();
    }, [user?.user_id, activeStructure?.id]); // Re-fetch when user OR structure changes

    // Track which tab is being processed for AI
    const [aiProcessingTab, setAiProcessingTab] = useState(null);

    const handleGenerateComments = async (silent = false) => {
        // Check if user is logged in
        if (!user?.user_id) {
            if (!silent) {
                alert('Vui lòng đăng nhập để sử dụng tính năng phân tích AI.');
            }
            return;
        }

        // Prevent multiple simultaneous requests
        if (aiProcessing) {
            if (!silent) {
                alert('Đang xử lý phân tích AI, vui lòng đợi...');
            }
            return;
        }

        // Capture current tab for background processing
        const processingTab = activeTab;

        if (!silent) {
            setAiProcessing(true);
            setAiProcessingTab(processingTab);
        }
        try {
            // 1. Xác định tab đang active và các sections cần tạo AI insight
            let sections = [];

            if (activeTab === 'Chung') {
                sections = [
                    {
                        section: 'summary',
                        prompt: `Với vai trò chuyên gia tư vấn giáo dục, hãy tổng kết tình hình học tập của học sinh này trong 3-4 câu:
- Đánh giá tổng thể: xuất sắc/khá/trung bình/cần cải thiện
- So sánh với mức chuẩn (nếu thang 10: 8+ giỏi, 6.5-8 khá, 5-6.5 TB)
- Xu hướng chung: đang đi lên, ổn định, hay đi xuống?
- Kết thúc bằng: "Hãy cùng EduTwin đi sâu vào phân tích chi tiết nhé!"
LƯU Ý: Không liệt kê lại điểm số, hãy đưa ra ĐÁNH GIÁ và NHẬN ĐỊNH có chiều sâu.`
                    },
                    {
                        section: 'trend',
                        prompt: `Với vai trò nhà phân tích dữ liệu giáo dục, phân tích XU HƯỚNG điểm số qua các kỳ (2-3 câu):
- Phát hiện: điểm có tăng/giảm đều hay có ĐIỂM ĐỘT PHÁ/SUY GIẢM bất thường?
- Tốc độ thay đổi: tiến bộ nhanh/chậm, giảm sút đột ngột/từ từ?
- Dự đoán: nếu duy trì xu hướng này, kết quả kỳ tới sẽ như thế nào?
- Cảnh báo nếu có dấu hiệu đáng lo ngại, hoặc khen ngợi nếu thấy nỗ lực rõ rệt.
LƯU Ý: Tìm pattern ẩn, không chỉ mô tả "điểm kỳ 1 là X, kỳ 2 là Y".`
                    },
                    {
                        section: 'subjects',
                        prompt: `Với vai trò cố vấn học thuật, phân tích ẢNH HƯỞNG của từng môn đến kết quả tổng thể (2-3 câu):
- Môn nào đang "kéo" điểm trung bình lên? Môn nào đang "ghì" xuống?
- Sự chênh lệch giữa các môn có đáng lo ngại không? (phân hóa cao hay đồng đều?)
- Xác định 1-2 môn "chiến lược" - cải thiện sẽ tạo đột phá lớn nhất cho điểm tổng.
LƯU Ý: Phân tích như một chiến lược gia, không liệt kê "môn A được X điểm, môn B được Y điểm".`
                    },
                    {
                        section: 'radar',
                        prompt: `Với vai trò chuyên gia hướng nghiệp, phân tích NĂNG LỰC và GỢI Ý ĐỊNH HƯỚNG (2-3 câu):
- Xác định "vùng sáng" (thế mạnh nổi trội) và "vùng tối" (cần đầu tư) của học sinh.
- Mô hình năng lực: thiên về Tự nhiên, Xã hội, hay Đa năng cân bằng?
- Gợi ý: với profile này, những tổ hợp/ngành nghề nào phù hợp? Môn nào cần ưu tiên cải thiện để mở rộng lựa chọn?
LƯU Ý: Đưa ra insight về tiềm năng và định hướng, không đọc lại radar chart.`
                    }
                ];
            } else if (activeTab === 'Tổ Hợp') {
                // Mỗi block là một section - với prompt chuyên sâu
                sections = Object.keys(EXAM_BLOCKS).map(block => ({
                    section: block,
                    prompt: `Với vai trò tư vấn viên tuyển sinh đại học, phân tích tổ hợp ${block} (${EXAM_BLOCKS[block].join(', ')}) trong 2-4 câu:
- Đánh giá khả năng cạnh tranh của học sinh với tổ hợp này (dựa trên điểm tổng và sự cân bằng giữa các môn).
- Môn nào đang là "trụ cột"? Môn nào đang là "điểm yếu chí mạng" cần khắc phục?
- Xu hướng điểm tổ hợp: ổn định, đang lên, hay đáng lo?
- Nhận định: tổ hợp này nên là lựa chọn CHÍNH, DỰ PHÒNG, hay CẦN CÂN NHẮC KỸ?
LƯU Ý: Phân tích chiến lược như tư vấn viên, không liệt kê lại điểm từng môn.`
                }));
            } else if (activeTab.startsWith('Block-')) {
                const blockName = activeTab.split('-')[1];
                sections = [{
                    section: blockName,
                    prompt: `Phân tích chuyên sâu tổ hợp ${blockName} (${EXAM_BLOCKS[blockName]?.join(', ')}) trong 3-4 câu với góc nhìn chiến lược thi đại học.`
                }];
            } else if (activeTab === 'Từng Môn') {
                sections = ALL_SUBJECTS.map(subject => ({
                    section: subject,
                    prompt: `Với vai trò giáo viên chuyên môn, phân tích môn ${subject} trong 2-3 câu:
- Điều GÌ THÚ VỊ hoặc BẤT THƯỜNG trong kết quả môn này? (tăng đột biến? giảm bất ngờ? ổn định khác thường?)
- So với các môn khác, môn này đóng vai trò gì? (môn thế mạnh? môn cần đầu tư? môn tiềm năng chưa khai phá?)
- Một gợi ý CỤ THỂ để cải thiện hoặc duy trì phong độ môn này.
LƯU Ý: Tìm điểm ĐẶC BIỆT, không nhắc lại "điểm kỳ 1 là..., kỳ 2 là..."`
                }));
            } else if (activeTab.startsWith('Subject-')) {
                const subjectName = activeTab.split('-')[1];
                sections = [{
                    section: subjectName,
                    prompt: `Phân tích chuyên sâu môn ${subjectName} với góc nhìn của giáo viên bộ môn có kinh nghiệm (3-4 câu).`
                }];
            }

            // 2. Chuẩn bị dữ liệu điểm số từ dataset (scores) trong structure đang active
            const scoreData = {};
            if (scores && scores.length > 0) {
                // Tổ chức điểm theo môn học
                const bySubject = {};
                scores.forEach(item => {
                    const subject = item.subject;
                    if (!bySubject[subject]) {
                        bySubject[subject] = [];
                    }
                    const score = item.actual !== null ? item.actual : item.predicted;
                    if (score !== null && score !== undefined) {
                        bySubject[subject].push({
                            timepoint: item.timepoint,
                            score: Number(score).toFixed(2),
                            isActual: item.actual !== null,
                            isPredicted: item.actual === null && item.predicted !== null
                        });
                    }
                });
                scoreData.bySubject = bySubject;

                // Tính điểm trung bình tổng theo từng kỳ
                const byTimepoint = {};
                scores.forEach(item => {
                    const tp = item.timepoint;
                    if (!byTimepoint[tp]) {
                        byTimepoint[tp] = [];
                    }
                    const score = item.actual !== null ? item.actual : item.predicted;
                    if (score !== null && score !== undefined) {
                        byTimepoint[tp].push(Number(score));
                    }
                });
                scoreData.averageByTimepoint = {};
                Object.entries(byTimepoint).forEach(([tp, values]) => {
                    if (values.length > 0) {
                        scoreData.averageByTimepoint[tp] = (values.reduce((a, b) => a + b, 0) / values.length).toFixed(2);
                    }
                });

                // Thông tin structure
                if (activeStructure) {
                    scoreData.structure = {
                        name: activeStructure.name || activeStructure.structure_name,
                        scaleType: activeStructure.scaleType || activeStructure.scale_type,
                        subjects: activeStructure.subjects,
                        timePoints: activeStructure.timePoints || activeStructure.time_points,
                        currentGrade: currentGrade
                    };
                }
            }

            // 3. Lấy thông tin từ documents được tải lên trong structure đang active
            let documentContext = null;
            if (activeStructure?.id) {
                try {
                    const docRes = await axiosClient.get(`/developer/structure-documents/${activeStructure.id}`);
                    const documents = docRes.data?.documents || [];
                    if (documents.length > 0) {
                        // Lấy summary của các documents
                        documentContext = {
                            documentCount: documents.length,
                            summaries: documents.map(doc => ({
                                fileName: doc.file_name,
                                summary: doc.summary_preview || doc.extracted_summary?.substring(0, 500)
                            })).filter(d => d.summary)
                        };
                        console.log(`[DataViz] Found ${documents.length} reference documents for structure`);
                    }
                } catch (docErr) {
                    console.log('[DataViz] No documents found or error fetching:', docErr.message);
                }
            }

            // 4. Gửi 1 request duy nhất với tất cả thông tin
            console.log(`[DataViz] Sending AI request for tab: ${activeTab}, sections: ${sections.length}, hasDocContext: ${!!documentContext}`);

            const res = await axiosClient.post('/chatbot/comment', {
                insight_type: 'slide_comment',
                active_tab: activeTab,
                sections,
                score_data: scoreData,
                document_context: documentContext,
                structure_id: activeStructure?.id, // Include structure ID for filtering
                persist: true
            }, {
                timeout: 120000, // 120s cho nhiều section với context đầy đủ
            });

            // 5. Nhận response và tách thông tin cho từng section
            if (!silent) {
                const newInsights = res.data.slide_comments || {};
                setAiInsights(newInsights);

                // Lưu vào localStorage để cache
                try {
                    const storageKey = getAiCommentsStorageKey(user?.user_id);
                    window.localStorage.setItem(
                        storageKey,
                        JSON.stringify({ version: AI_COMMENTS_VERSION, insights: newInsights })
                    );
                } catch (storageErr) {
                    console.error('Failed to persist AI comments', storageErr);
                }
                console.log(`[DataViz] AI insight generated for tab: ${activeTab}`, newInsights);
                alert('✅ Đã sinh phân tích AI thành công!');
            }
        } catch (e) {
            if (!silent) {
                console.error('[DataViz] Failed to generate AI insights:', e);

                // Provide specific error messages for common cases
                let errorMessage = 'Không thể tạo phân tích AI.';
                const errorDetail = e.response?.data?.detail || e.message || '';

                if (errorDetail.includes('RESOURCE_EXHAUSTED') || errorDetail.includes('quota') || errorDetail.includes('rate limit')) {
                    errorMessage = '⚠️ Đã hết giới hạn AI cho hôm nay. Vui lòng thử lại sau vài phút hoặc liên hệ quản trị viên.';
                } else if (errorDetail.includes('401') || errorDetail.includes('Chưa đăng nhập')) {
                    errorMessage = '⚠️ Phiên đăng nhập đã hết hạn. Vui lòng đăng nhập lại.';
                } else if (errorDetail.includes('timeout') || errorDetail.includes('TIMEOUT')) {
                    errorMessage = '⚠️ Yêu cầu quá lâu. Vui lòng thử lại.';
                } else if (errorDetail.includes('Network') || errorDetail.includes('ERR_EMPTY_RESPONSE')) {
                    errorMessage = '⚠️ Lỗi kết nối mạng. Vui lòng kiểm tra kết nối internet.';
                } else if (errorDetail) {
                    errorMessage = `Lỗi: ${errorDetail}`;
                }

                alert(errorMessage);
            }
            // otherwise fail silently
        } finally {
            if (!silent) {
                setAiProcessing(false);
                setAiProcessingTab(null);
            }
        }
    };

    // Data Processing Helpers - use activeStructure for dynamic subjects
    // Only THPT structure has exam blocks
    const EXAM_BLOCKS = useMemo(() => {
        if (activeStructure?.name === 'THPT') {
            return {
                'A00': ['Toán', 'Lý', 'Hóa'],
                'B00': ['Toán', 'Hóa', 'Sinh'],
                'C00': ['Văn', 'Sử', 'Địa'],
                'D01': ['Toán', 'Văn', 'Anh']
            };
        }
        return {};
    }, [activeStructure]);

    const ALL_SUBJECTS = useMemo(() => {
        return activeStructure?.subjects || [];
    }, [activeStructure]);

    // Subject labels - just use subject name as-is (works for both THPT and custom)
    const SUBJECT_LABELS = useMemo(() => {
        const labels = {};
        ALL_SUBJECTS.forEach(subject => {
            labels[subject] = subject; // Use subject name directly
        });
        return labels;
    }, [ALL_SUBJECTS]);

    // Subject color mapping
    const getSubjectColor = useCallback((subjectId) => {
        const SUBJECT_COLORS = {
            'Toán': '#1f77b4',
            'Văn': '#e74c3c',
            'Anh': '#f1c40f',
            'Lý': '#9b59b6',
            'Hóa': '#16a085',
            'Sinh': '#2ecc71',
            'Sử': '#d35400',
            'Địa': '#2980b9',
            'GDCD': '#34495e',
            // TOEIC subjects
            'Listening': '#1f77b4',
            'Reading': '#e74c3c',
            'Speaking': '#f1c40f',
            'Writing': '#16a085'
        };
        return SUBJECT_COLORS[subjectId] || '#7f8c8d';
    }, []);

    const getFilteredScores = () => {
        // Removed Khối XH and Khối TN filtering
        if (activeTab.startsWith('Block-')) {
            const blockName = activeTab.split('-')[1];
            return scores.filter(s => EXAM_BLOCKS[blockName]?.includes(s.subject));
        }
        if (activeTab.startsWith('Subject-')) {
            const subjectId = activeTab.split('-')[1];
            return scores.filter(s => s.subject === subjectId);
        }
        return scores;
    };

    const processBarData = (data, currentIdx = null) => {
        // Filter data up to and including current grade/term if currentIdx provided and valid
        let filteredData = data;
        // Only filter if currentIdx is a valid positive number
        if (currentIdx !== null && currentIdx !== undefined && currentIdx >= 0 && activeStructure?.timePoints) {
            const filtered = data.filter(item => {
                const timepointIdx = activeStructure.timePoints.indexOf(item.timepoint);
                return timepointIdx !== -1 && timepointIdx <= currentIdx;
            });
            // Only use filtered data if it's not empty
            if (filtered.length > 0) {
                filteredData = filtered;
            }
        }

        const grouped = {};
        filteredData.forEach(item => {
            // Prefer actual, fallback to predicted
            let val = null;
            if (item.actual !== null && item.actual !== undefined) {
                val = Number(item.actual);
            } else if (item.predicted !== null && item.predicted !== undefined) {
                val = Number(item.predicted);
            }

            if (val === null || Number.isNaN(val)) return;

            if (!grouped[item.subject]) grouped[item.subject] = [];
            grouped[item.subject].push(val);
        });

        const result = Object.entries(grouped).map(([subject, values]) => {
            const rawAvg = values.length > 0 ? values.reduce((a, b) => a + b, 0) / values.length : 0;
            // Round to 2 decimal places, remove trailing zeros
            const avg = Math.round(rawAvg * 100) / 100;

            return {
                subjectId: subject,
                subjectLabel: subject, // Use subject name directly from activeStructure
                avg
            };
        }).sort((a, b) => b.avg - a.avg);

        return result;
    };

    // Helper to compute dynamic domain for charts based on data and scale type
    const computeChartDomain = useCallback((data, dataKey = 'display') => {
        if (!activeStructure?.scaleType) {
            return [0, 10]; // Default fallback
        }

        const values = data
            .map(item => item[dataKey])
            .filter(v => v !== null && v !== undefined && !isNaN(v));

        return calculateChartDomain(values, activeStructure.scaleType, 10);
    }, [activeStructure?.scaleType]);

    // Helper to compute domain for bar charts (X axis)
    const computeBarChartDomain = useCallback((barData) => {
        if (!activeStructure?.scaleType) {
            return [0, 10]; // Default fallback
        }

        const values = barData.map(item => item.avg);
        return calculateChartDomain(values, activeStructure.scaleType, 10);
    }, [activeStructure?.scaleType]);

    // Helper to compute domain for radar charts
    const computeRadarDomain = useCallback((radarData, dataKey = 'value') => {
        if (!activeStructure?.scaleType) {
            return [0, 10]; // Default fallback
        }

        const values = radarData
            .map(item => item[dataKey])
            .filter(v => v !== null && v !== undefined && !isNaN(v));

        const maxScale = getScaleMax(activeStructure.scaleType);
        const domain = calculateChartDomain(values, activeStructure.scaleType, 10);

        // Ensure domain doesn't exceed scale max
        return [domain[0], Math.min(domain[1], maxScale)];
    }, [activeStructure?.scaleType]);

    const buildCurrentTermRadarData = (data, currentTermToken) => {
        if (!currentTermToken || !activeStructure?.subjects) {
            console.log('[buildCurrentTermRadarData] Missing requirements:', { currentTermToken, hasSubjects: !!activeStructure?.subjects });
            return [];
        }

        const subjectValues = new Map();
        data.forEach(item => {
            // Match based on timepoint
            if (item.timepoint !== currentTermToken) return;

            const value = item.actual !== null && item.actual !== undefined
                ? Number(item.actual)
                : item.predicted !== null && item.predicted !== undefined
                    ? Number(item.predicted)
                    : null;
            if (value === null || Number.isNaN(value)) return;
            // Round to 2 decimal places for consistent display
            subjectValues.set(item.subject, Math.round(value * 100) / 100);
        });

        if (subjectValues.size === 0) {
            console.log('[buildCurrentTermRadarData] No subject values found');
            return [];
        }

        const dataPoints = [];
        activeStructure.subjects.forEach(subjectId => {
            if (subjectValues.has(subjectId)) {
                dataPoints.push({
                    subjectId,
                    subjectLabel: subjectId, // Use subject name directly
                    value: subjectValues.get(subjectId),
                });
            }
        });

        // Add any remaining subjects not in activeStructure.subjects
        const remainingSubjects = Array.from(subjectValues.keys())
            .filter(subjectId => !activeStructure.subjects.includes(subjectId))
            .sort();
        remainingSubjects.forEach(subjectId => {
            dataPoints.push({
                subjectId,
                subjectLabel: subjectId,
                value: subjectValues.get(subjectId),
            });
        });

        console.log('[buildCurrentTermRadarData] Result:', dataPoints);
        return dataPoints;
    };

    // Build term series with proper past/future connection (general version for averages)
    // Build term series with improved past/future connection (for general average)
    const buildGeneralTermSeriesV2 = (scores) => {
        if (!activeStructure?.timePoints) {
            console.log('[buildGeneralTermSeriesV2] No activeStructure, using legacy buildTermSeries');
            return null; // Signal to use legacy function
        }

        console.log('[buildGeneralTermSeriesV2] Input scores:', scores.length, 'currentGrade:', currentGrade);

        // Group by timepoint to calculate average
        const termDataMap = new Map();

        scores.forEach(item => {
            const timepoint = item.timepoint;

            // Prefer actual, fallback to predicted
            let value = null;
            if (item.actual !== null && item.actual !== undefined) {
                value = Number(item.actual);
            } else if (item.predicted !== null && item.predicted !== undefined) {
                value = Number(item.predicted);
            }

            if (value === null || Number.isNaN(value)) return;

            if (!termDataMap.has(timepoint)) {
                termDataMap.set(timepoint, []);
            }
            termDataMap.get(timepoint).push(value);
        });

        // Calculate average for each timepoint
        const termAvgs = new Map();
        termDataMap.forEach((values, timepoint) => {
            const avg = values.reduce((a, b) => a + b, 0) / values.length;
            const roundedAvg = Math.round(avg * 100) / 100;
            termAvgs.set(timepoint, roundedAvg);
        });

        console.log('[buildGeneralTermSeriesV2] termAvgs:', Array.from(termAvgs.entries()));
        console.log('[buildGeneralTermSeriesV2] currentGrade:', currentGrade);

        // Find currentGrade index
        let currentGradeIdx = -1;
        if (currentGrade) {
            currentGradeIdx = activeStructure.timePoints.findIndex(tp => tp === currentGrade);
            console.log('[buildGeneralTermSeriesV2] currentGradeIdx:', currentGradeIdx);
        }

        // Build result with past/future logic based on position relative to currentGrade
        const result = activeStructure.timePoints.map((timepoint, idx) => {
            const avg = termAvgs.get(timepoint) || null;

            // Past = before or at currentGrade index
            // Future = after currentGrade index
            const isPast = currentGradeIdx >= 0 ? idx <= currentGradeIdx : false;

            return {
                timepoint,
                term: timepoint, // Keep 'term' for backward compatibility with charts
                display: avg,
                pastValue: isPast ? avg : null,
                futureValue: null,
                isPast,
            };
        });

        // Connect future line from currentGrade onwards
        if (currentGradeIdx >= 0) {
            // Start from currentGrade index and set futureValue for all points after (including currentGrade for connection)
            for (let i = currentGradeIdx; i < result.length; i++) {
                if (result[i].display !== null) {
                    result[i].futureValue = result[i].display;
                }
            }
            console.log(`[buildGeneralTermSeriesV2] Connecting future from currentGrade index ${currentGradeIdx} (${result[currentGradeIdx].term})`);
        } else {
            // No currentGrade set: show all as future line
            console.log('[buildGeneralTermSeriesV2] No currentGrade, showing all as future');
            for (let i = 0; i < result.length; i++) {
                if (result[i].display !== null) {
                    result[i].futureValue = result[i].display;
                }
            }
        }

        result.forEach(r => delete r.isPast);

        console.log('[buildGeneralTermSeriesV2] Result:', result);
        return result;
    };

    // Build term series for exam blocks: calculate SUM (not average) of subjects per term
    const buildExamBlockSumSeries = (blockScores, currentIdx) => {
        console.log('[buildExamBlockSumSeries] Input:', { blockScoresLength: blockScores.length, currentIdx, currentGrade });

        if (!activeStructure?.timePoints) {
            console.log('[buildExamBlockSumSeries] No timePoints available');
            return [];
        }

        // Group by timepoint, then by subject to get one score per subject per timepoint
        const termSubjectMap = new Map();

        blockScores.forEach(item => {
            const timepoint = item.timepoint;

            // Prefer actual, fallback to predicted
            let termValue = null;
            if (item.actual !== null && item.actual !== undefined) {
                termValue = Number(item.actual);
            } else if (item.predicted !== null && item.predicted !== undefined) {
                termValue = Number(item.predicted);
            }

            if (termValue === null || Number.isNaN(termValue)) return;

            if (!termSubjectMap.has(timepoint)) {
                termSubjectMap.set(timepoint, new Map());
            }
            // Store one score per subject (latest if multiple)
            termSubjectMap.get(timepoint).set(item.subject, termValue);
        });

        console.log('[buildExamBlockSumSeries] termSubjectMap:', Array.from(termSubjectMap.entries()));

        // Calculate sum of all subjects for each timepoint
        const termSums = new Map();
        termSubjectMap.forEach((subjectMap, timepoint) => {
            const sum = Array.from(subjectMap.values()).reduce((a, b) => a + b, 0);
            // Round to 2 decimal places, remove trailing zeros
            const roundedSum = Math.round(sum * 100) / 100;
            termSums.set(timepoint, roundedSum);
        });

        console.log('[buildExamBlockSumSeries] termSums:', Array.from(termSums.entries()));
        console.log('[buildExamBlockSumSeries] currentGrade:', currentGrade);

        // Find currentGrade index
        let currentGradeIdx = -1;
        if (currentGrade) {
            currentGradeIdx = activeStructure.timePoints.findIndex(tp => tp === currentGrade);
            console.log('[buildExamBlockSumSeries] currentGradeIdx:', currentGradeIdx);
        }

        // Build series data with past/future based on position relative to currentGrade
        const result = activeStructure.timePoints.map((timepoint, idx) => {
            const sum = termSums.get(timepoint) || null;

            // Past = before or at currentGrade index
            // Future = after currentGrade index
            const isPast = currentGradeIdx >= 0 ? idx <= currentGradeIdx : false;

            console.log(`[buildExamBlockSumSeries] ${timepoint} (idx=${idx}): sum=${sum}, isPast=${isPast}, currentGradeIdx=${currentGradeIdx}`);

            return {
                timepoint,
                term: timepoint, // Keep 'term' for backward compatibility with charts
                display: sum,
                pastValue: isPast ? sum : null,
                futureValue: null, // Will set below
                isPast,
            };
        });

        // Connect future line from currentGrade onwards
        if (currentGradeIdx >= 0) {
            // Start from currentGrade index and set futureValue for all points after (including currentGrade for connection)
            for (let i = currentGradeIdx; i < result.length; i++) {
                if (result[i].display !== null) {
                    result[i].futureValue = result[i].display;
                }
            }
            console.log(`[buildExamBlockSumSeries] Connecting future line from currentGrade index ${currentGradeIdx} (${result[currentGradeIdx].term})`);
        } else {
            // No currentGrade set: show all as future line
            console.log('[buildExamBlockSumSeries] No currentGrade, showing all as future');
            for (let i = 0; i < result.length; i++) {
                if (result[i].display !== null) {
                    result[i].futureValue = result[i].display;
                }
            }
        }

        // Clean up temporary isPast field
        result.forEach(r => delete r.isPast);

        console.log('[buildExamBlockSumSeries] Result:', result);
        return result;
    };

    // Get current semester scores for exam block subjects (for BarChart)
    const getExamBlockCurrentScores = (blockScores, currentGrade) => {
        console.log('[getExamBlockCurrentScores] Input:', { blockScoresCount: blockScores.length, currentGrade });

        if (!currentGrade) {
            console.log('[getExamBlockCurrentScores] No currentGrade, returning empty');
            return [];
        }

        // Get all unique subjects in this block
        const allSubjects = new Set(blockScores.map(item => item.subject));
        console.log('[getExamBlockCurrentScores] All subjects in block:', Array.from(allSubjects));

        const result = [];

        // For each subject, find best score at currentGrade (actual > predicted > null)
        allSubjects.forEach(subject => {
            // Filter scores for this subject at currentGrade
            const scoresForSubject = blockScores.filter(item => {
                return item.subject === subject && item.timepoint === currentGrade;
            });

            console.log(`[getExamBlockCurrentScores] ${subject} at ${currentGrade}:`, scoresForSubject.length, 'records');

            // Find best score: actual > predicted > null
            let bestScore = null;

            for (const item of scoresForSubject) {
                // Prefer actual
                if (item.actual !== null && item.actual !== undefined) {
                    bestScore = Number(item.actual);
                    console.log(`[getExamBlockCurrentScores] ${subject}: Using actual = ${bestScore}`);
                    break; // Found actual, stop looking
                }
                // Fallback to predicted
                if (item.predicted !== null && item.predicted !== undefined && bestScore === null) {
                    bestScore = Number(item.predicted);
                    console.log(`[getExamBlockCurrentScores] ${subject}: Using predicted = ${bestScore}`);
                }
            }

            // Always add subject to result (even if no score)
            if (bestScore !== null && !Number.isNaN(bestScore)) {
                result.push({
                    subjectId: subject,
                    subjectLabel: SUBJECT_LABELS[subject] || subject,
                    avg: Math.round(bestScore * 100) / 100
                });
            } else {
                console.log(`[getExamBlockCurrentScores] ${subject}: No score found at ${currentGrade}`);
            }
        });

        console.log('[getExamBlockCurrentScores] Final result:', result);
        return result.sort((a, b) => b.avg - a.avg);
    };

    const currentIdx = slotIndexForTerm(currentGrade);
    const filteredData = getFilteredScores();
    const barData = processBarData(filteredData, currentIdx);
    const currentGradeLabel = currentGrade ? formatCurrentTerm(currentGrade) : null;
    const currentTermRadarData = useMemo(
        () => buildCurrentTermRadarData(scores, currentGrade),
        [scores, currentGrade, activeStructure]
    );

    const generalTermSeries = useMemo(() => {
        const map = new Map();
        termAverages.forEach(item => {
            if (!item || !item.timepoint || item.average === undefined || item.average === null) return;
            map.set(item.timepoint, Number(item.average));
        });
        return buildTermSeries(map, currentIdx);
    }, [termAverages, currentIdx, buildTermSeries]);

    const filteredTermSeries = useMemo(() => {
        const averages = computeTermAverageMap(filteredData);
        return buildTermSeries(averages, currentIdx);
    }, [filteredData, currentIdx, buildTermSeries]);

    const activeTermSeries = useMemo(() => {
        // Removed Khối XH and Khối TN tabs
        if (activeTab === 'Chung') {
            return generalTermSeries;
        }
        return generalTermSeries;
    }, [activeTab, generalTermSeries]);

    const hasPastSegment = useMemo(() => activeTermSeries.some(point => point.pastValue !== null), [activeTermSeries]);
    const hasFutureSegment = useMemo(() => activeTermSeries.some(point => point.futureValue !== null), [activeTermSeries]);
    const hasAnyTermData = useMemo(() => activeTermSeries.some(point => point.display !== null), [activeTermSeries]);

    const radarNoteText = useMemo(() => {
        if (!currentGradeLabel) {
            return 'Vui lòng chọn mốc thời gian hiện tại để hiển thị biểu đồ radar.';
        }
        if (!currentTermRadarData.length) {
            return `Chưa có điểm nào cho ${currentGradeLabel}, vui lòng bổ sung dữ liệu để xem biểu đồ.`;
        }
        return `Biểu đồ hiển thị điểm từng môn trong ${currentGradeLabel}.`;
    }, [currentGradeLabel, currentTermRadarData]);

    // Dynamic tabs based on structure - only THPT has "Tổ Hợp" tab
    const tabs = useMemo(() => {
        const baseTabs = ['Chung', 'Từng Môn'];
        if (activeStructure?.name === 'THPT') {
            return ['Chung', 'Tổ Hợp', 'Từng Môn'];
        }
        return baseTabs;
    }, [activeStructure]);

    // Map insight to current tab, even if only one insight exists
    const overviewInsights = aiInsights?.overview || {};
    const examBlockInsights = aiInsights?.exam_blocks || {};
    const examBlockDetails = examBlockInsights.blocks || {};

    // For tab 'Chung', get insight text for each chart section
    const getOverviewText = (key) => {
        if (!overviewInsights || Object.keys(overviewInsights).length === 0) return null;

        // Get section-specific insight
        const sectionInsight = overviewInsights[key];
        if (sectionInsight) {
            return sectionInsight?.narrative?.comment || sectionInsight?.comment || null;
        }

        // Fallback: if only one insight exists, use it for all
        const firstKey = Object.keys(overviewInsights)[0];
        if (firstKey && Object.keys(overviewInsights).length === 1) {
            const fallbackInsight = overviewInsights[firstKey];
            return fallbackInsight?.narrative?.comment || fallbackInsight?.comment || null;
        }

        return null;
    };
    // For exam blocks, map to correct block
    const getExamBlockInsight = (blockName) => {
        if (!examBlockDetails) return null;
        return examBlockDetails[blockName] || examBlockDetails[Object.keys(examBlockDetails)[0]] || null;
    };

    // Show loading spinner while fetching structure or data
    if (loading || loadingStructure) {
        return <div style={{ padding: '2rem', textAlign: 'center' }}>
            <div className="spinner" style={{ margin: '0 auto' }}></div>
            <p style={{ marginTop: '1rem', color: '#666' }}>Đang tải dữ liệu...</p>
        </div>;
    }

    // Handle case when no active structure
    if (!activeStructure) {
        return (
            <div className="container" style={{ maxWidth: isMobile ? '100%' : '1000px', paddingTop: isMobile ? '1rem' : '2rem', paddingBottom: isMobile ? '80px' : '3rem' }}>
                <div className="card" style={{
                    padding: '3rem 2rem',
                    textAlign: 'center',
                    background: 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)',
                    color: 'white',
                    borderRadius: '12px'
                }}>
                    <div style={{ fontSize: '4rem', marginBottom: '1rem' }}></div>
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

    // Debug logging
    console.log('[DataViz Render] activeStructure:', activeStructure);
    console.log('[DataViz Render] scores:', scores.length);
    console.log('[DataViz Render] termAverages:', termAverages.length);
    console.log('[DataViz Render] currentGrade:', currentGrade);
    console.log('[DataViz Render] activeTab:', activeTab);
    console.log('[DataViz Render] ALL_SUBJECTS:', ALL_SUBJECTS);
    console.log('[DataViz Render] EXAM_BLOCKS:', EXAM_BLOCKS);

    // Get available subjects for custom combination (not yet selected)
    const getAvailableSubjects = (currentSelect) => {
        const selected = [customSubject1, customSubject2, customSubject3].filter(s => s && s !== currentSelect);
        return ALL_SUBJECTS.filter(s => !selected.includes(s));
    };

    // Check if custom combination is valid
    const isCustomCombinationValid = customSubject1 && customSubject2 && customSubject3 &&
        customSubject1 !== customSubject2 && customSubject1 !== customSubject3 && customSubject2 !== customSubject3;

    // Render custom combination chart
    const renderCustomCombination = () => {
        if (!isCustomCombinationValid) return null;

        const subjects = [customSubject1, customSubject2, customSubject3];
        const blockScores = scores.filter(s => subjects.includes(s.subject));
        const blockSeries = buildTermSeries(computeTermAverageMap(blockScores), currentIdx);
        const blockHasData = blockSeries.some(point => point.display !== null);
        const blockHasPast = blockSeries.some(point => point.pastValue !== null);
        const blockHasFuture = blockSeries.some(point => point.futureValue !== null);
        const blockBarData = processBarData(blockScores, currentIdx);
        const blockColor = '#3498db';

        return (
            <div className="card" style={{ borderTop: `4px solid ${blockColor}`, width: '100%', padding: '2rem', marginTop: '2rem' }}>
                <h3 style={{ marginBottom: '1.25rem', fontSize: '1.3rem', fontWeight: '600', color: blockColor }}>
                    Tổ Hợp Tùy Chọn
                </h3>
                <p style={{ fontSize: '0.9rem', color: '#666', marginBottom: '1.5rem' }}>
                    {subjects.map(s => SUBJECT_LABELS[s]).join(', ')}
                </p>
                {blockHasData ? (
                    <div style={{ display: 'flex', flexDirection: 'column' }}>
                        <div style={{ height: '320px', width: '100%' }}>
                            <ResponsiveContainer width="100%" height="100%">
                                <LineChart data={blockSeries}>
                                    <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
                                    <XAxis dataKey="term" tick={{ fontSize: 12 }} tickFormatter={formatTermLabel} interval={0} ticks={getXAxisTicks(blockSeries)} />
                                    <YAxis domain={computeChartDomain(blockSeries)} tick={{ fontSize: 12 }} tickFormatter={formatYAxisTick} />
                                    <Tooltip content={<TermAverageTooltip formatTermLabel={formatTermLabel} />} />
                                    {blockHasPast && (
                                        <Line
                                            type="monotone"
                                            dataKey="pastValue"
                                            name="Xu hướng hiện tại"
                                            stroke={blockColor}
                                            strokeWidth={3}
                                            dot={{ r: 5 }}
                                            activeDot={{ r: 7 }}
                                            connectNulls
                                        >
                                            <LabelList dataKey="pastValue" content={renderLineLabel} />
                                        </Line>
                                    )}
                                    {blockHasFuture && (
                                        <Line
                                            type="monotone"
                                            dataKey="futureValue"
                                            name="Xu hướng tương lai"
                                            stroke={blockColor}
                                            strokeWidth={3}
                                            strokeDasharray="6 4"
                                            dot={{ r: 5 }}
                                            activeDot={{ r: 7 }}
                                            connectNulls
                                        >
                                            <LabelList dataKey="futureValue" content={renderFutureLineLabel} />
                                        </Line>
                                    )}
                                </LineChart>
                            </ResponsiveContainer>
                        </div>
                        <div style={{ marginTop: '1rem' }}>
                            <TrendLegend color={blockColor} showPast={blockHasPast} showFuture={blockHasFuture} />
                        </div>

                        <div style={{ height: '220px', marginTop: '2rem' }}>
                            <ResponsiveContainer width="100%" height="100%">
                                <BarChart data={blockBarData} layout="vertical">
                                    <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" horizontal={false} />
                                    <XAxis type="number" domain={computeBarChartDomain(blockBarData)} tick={{ fontSize: 11 }} tickFormatter={formatBarXAxisTick} />
                                    <YAxis type="category" dataKey="subjectLabel" width={90} tick={{ fontSize: 11 }} />
                                    <Tooltip formatter={(value) => (value === null || value === undefined ? '-' : Number(value).toFixed(2))} contentStyle={{ borderRadius: '6px', fontSize: '0.85rem' }} />
                                    <Bar dataKey="avg" radius={[0, 4, 4, 0]} barSize={24}>
                                        {blockBarData.map(item => (
                                            <Cell key={item.subjectId} fill={getSubjectColor(item.subjectId)} />
                                        ))}
                                        <LabelList dataKey="avg" content={renderBarLabel} />
                                    </Bar>
                                </BarChart>
                            </ResponsiveContainer>
                        </div>
                    </div>
                ) : (
                    <div style={{ padding: '3rem', textAlign: 'center', color: '#999', fontSize: '1rem' }}>Chưa có dữ liệu</div>
                )}
            </div>
        );
    };

    // Render Exam Blocks View (single-column: one chart per row)
    const renderExamBlocks = (blockComments = {}) => (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '2rem' }}>
            {Object.entries(EXAM_BLOCKS).map(([blockName, subjects]) => {
                // Always get insight for this block, fallback to first key if only one exists
                let blockInsight = blockComments[blockName];
                if (!blockInsight && Object.keys(blockComments).length === 1) {
                    blockInsight = blockComments[Object.keys(blockComments)[0]];
                }
                const insight = blockInsight?.narrative?.comment || blockInsight?.structured?.comment || blockInsight?.comment || '';
                // ...existing code...
                const blockScores = scores.filter(s => subjects.includes(s.subject));
                const blockSeries = buildExamBlockSumSeries(blockScores, currentIdx);
                const blockHasData = blockSeries.some(point => point.display !== null);
                const blockHasPast = blockSeries.some(point => point.pastValue !== null);
                const blockHasFuture = blockSeries.some(point => point.futureValue !== null);
                const blockBarData = getExamBlockCurrentScores(blockScores, currentGrade);
                const colors = { 'A00': '#e74c3c', 'B00': '#f39c12', 'C00': '#16a085', 'D01': '#8e44ad' };
                return (
                    <div key={blockName} className="card" style={{ borderTop: `4px solid ${colors[blockName]}`, width: '100%', padding: '2rem' }}>
                        <h3 style={{ marginBottom: '1.25rem', fontSize: '1.3rem', fontWeight: '600', color: colors[blockName] }}>
                            Tổ Hợp {blockName}
                        </h3>
                        <p style={{ fontSize: '0.9rem', color: '#666', marginBottom: '1.5rem' }}>
                            {subjects.map(s => SUBJECT_LABELS[s]).join(', ')}
                        </p>
                        {(blockHasData || blockBarData.length > 0) ? (
                            <div style={{ display: 'flex', flexDirection: 'column' }}>
                                {/* Only render LineChart if has past or future data */}
                                {(blockHasPast || blockHasFuture) && (
                                    <>
                                        <div style={{ height: '320px', width: '100%' }}>
                                            <ResponsiveContainer width="100%" height="100%">
                                                <LineChart data={blockSeries}>
                                                    <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
                                                    <XAxis dataKey="term" tick={{ fontSize: 12 }} tickFormatter={formatTermLabel} interval={0} ticks={getXAxisTicks(blockSeries)} />
                                                    <YAxis domain={[0, 30]} tick={{ fontSize: 12 }} tickFormatter={formatYAxisTick} />
                                                    <Tooltip content={<TermAverageTooltip formatTermLabel={formatTermLabel} />} />
                                                    {blockHasPast && (
                                                        <Line
                                                            type="monotone"
                                                            dataKey="pastValue"
                                                            name="Xu hướng hiện tại"
                                                            stroke={colors[blockName]}
                                                            strokeWidth={3}
                                                            dot={{ r: 5 }}
                                                            activeDot={{ r: 7 }}
                                                            connectNulls
                                                        >
                                                            <LabelList dataKey="pastValue" content={renderLineLabel} />
                                                        </Line>
                                                    )}
                                                    {blockHasFuture && (
                                                        <Line
                                                            type="monotone"
                                                            dataKey="futureValue"
                                                            name="Xu hướng tương lai"
                                                            stroke={colors[blockName]}
                                                            strokeWidth={3}
                                                            strokeDasharray="6 4"
                                                            dot={{ r: 5 }}
                                                            activeDot={{ r: 7 }}
                                                            connectNulls
                                                        >
                                                            <LabelList dataKey="futureValue" content={renderFutureLineLabel} />
                                                        </Line>
                                                    )}
                                                </LineChart>
                                            </ResponsiveContainer>
                                        </div>
                                        <div style={{ marginTop: '1rem' }}>
                                            <TrendLegend color={colors[blockName]} showPast={blockHasPast} showFuture={blockHasFuture} />
                                        </div>
                                    </>
                                )}

                                <div style={{ marginTop: '2rem' }}>
                                    <p style={{ fontSize: '0.9rem', color: '#666', marginBottom: '0.75rem', fontStyle: 'italic' }}>
                                        Điểm các môn trong mốc thời gian hiện tại ({currentGradeLabel || 'N/A'})
                                    </p>
                                    {blockBarData.length > 0 ? (
                                        <div style={{ height: '220px', minHeight: '220px', width: '100%', minWidth: '300px' }}>
                                            <ResponsiveContainer width="100%" height="100%">
                                                <BarChart data={blockBarData} layout="vertical">
                                                    <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" horizontal={false} />
                                                    <XAxis type="number" domain={computeBarChartDomain(blockBarData)} tick={{ fontSize: 11 }} tickFormatter={formatBarXAxisTick} />
                                                    <YAxis type="category" dataKey="subjectLabel" width={90} tick={{ fontSize: 11 }} />
                                                    <Tooltip formatter={(value) => (value === null || value === undefined ? '-' : Number(value).toFixed(2))} contentStyle={{ borderRadius: '6px', fontSize: '0.85rem' }} />
                                                    <Bar dataKey="avg" radius={[0, 4, 4, 0]} barSize={24}>
                                                        {blockBarData.map(item => (
                                                            <Cell key={item.subjectId} fill={getSubjectColor(item.subjectId)} />
                                                        ))}
                                                        <LabelList dataKey="avg" content={renderBarLabel} />
                                                    </Bar>
                                                </BarChart>
                                            </ResponsiveContainer>
                                        </div>
                                    ) : (
                                        <div style={{ padding: '2rem', textAlign: 'center', color: '#999', fontSize: '0.95rem' }}>
                                            Chưa có dữ liệu cho mốc thời gian hiện tại
                                        </div>
                                    )}
                                </div>

                                {insight && (
                                    <div style={{
                                        marginTop: '1.5rem',
                                        padding: '1rem 1.25rem',
                                        background: '#fafafa',
                                        borderLeft: `4px solid ${colors[blockName]}`,
                                        borderRadius: '6px',
                                        color: '#555',
                                        fontSize: '0.95rem',
                                        lineHeight: 1.6,
                                    }}>
                                        <div style={{ fontWeight: '600', color: colors[blockName], marginBottom: '0.5rem' }}>💡 Đánh giá khối {blockName}</div>
                                        <div>{insight}</div>
                                    </div>
                                )}
                            </div>
                        ) : (
                            <div style={{ padding: '3rem', textAlign: 'center', color: '#999', fontSize: '1rem' }}>Chưa có dữ liệu</div>
                        )}
                    </div>
                );
            })}
        </div>
    );

    // Render Subject-specific View (single-column layout)
    const renderSubjects = (subjectComments = {}) => {
        if (scores.length === 0) {
            return (
                <div className="card" style={{ padding: '3rem 2rem', textAlign: 'center' }}>
                    <h3 style={{ color: '#666', marginBottom: '0.5rem' }}>Chưa có dữ liệu điểm</h3>
                </div>
            );
        }
        return (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '1.5rem' }}>
                {ALL_SUBJECTS.map((subjectId) => {
                    // Always get insight for this subject, fallback to first key if only one exists
                    let subjectInsightPayload = subjectComments[subjectId];
                    if (!subjectInsightPayload && Object.keys(subjectComments).length === 1) {
                        subjectInsightPayload = subjectComments[Object.keys(subjectComments)[0]];
                    }
                    const subjectInsight = subjectInsightPayload?.narrative?.comment || subjectInsightPayload?.structured?.comment || subjectInsightPayload?.comment || '';
                    // ...existing code...
                    const subjectScores = scores.filter(s => s.subject === subjectId);
                    const subjectSeriesV2 = buildGeneralTermSeriesV2(subjectScores);
                    const subjectSeries = subjectSeriesV2 || buildTermSeries(computeTermAverageMap(subjectScores), currentIdx);
                    const subjectHasData = subjectSeries.some(point => point.display !== null);
                    const subjectHasPast = subjectSeries.some(point => point.pastValue !== null);
                    const subjectHasFuture = subjectSeries.some(point => point.futureValue !== null);
                    const subjectColor = getSubjectColor(subjectId);
                    return (
                        <div key={subjectId} className="card" style={{ borderLeft: `4px solid ${subjectColor}`, width: '100%', padding: '1.75rem' }}>
                            <h3 style={{ marginBottom: '1.25rem', fontSize: '1.2rem', fontWeight: '600', color: subjectColor }}>
                                {SUBJECT_LABELS[subjectId]}
                            </h3>
                            {subjectHasData ? (
                                <div style={{ display: 'flex', flexDirection: 'column' }}>
                                    <div style={{ height: '280px', width: '100%' }}>
                                        <ResponsiveContainer width="100%" height="100%">
                                            <LineChart data={subjectSeries}>
                                                <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
                                                <XAxis dataKey="term" tick={{ fontSize: 11 }} tickFormatter={formatTermLabel} interval={0} ticks={getXAxisTicks(subjectSeries)} />
                                                <YAxis domain={computeChartDomain(subjectSeries)} tick={{ fontSize: 11 }} tickFormatter={formatYAxisTick} />
                                                <Tooltip content={<TermAverageTooltip formatTermLabel={formatTermLabel} />} />
                                                {subjectHasPast && (
                                                    <Line
                                                        type="monotone"
                                                        dataKey="pastValue"
                                                        name="Xu hướng hiện tại"
                                                        stroke={subjectColor}
                                                        strokeWidth={2.5}
                                                        dot={{ r: 4 }}
                                                        activeDot={{ r: 6 }}
                                                        connectNulls
                                                    >
                                                        <LabelList dataKey="pastValue" content={renderLineLabel} />
                                                    </Line>
                                                )}
                                                {subjectHasFuture && (
                                                    <Line
                                                        type="monotone"
                                                        dataKey="futureValue"
                                                        name="Xu hướng tương lai"
                                                        stroke={subjectColor}
                                                        strokeWidth={2.5}
                                                        strokeDasharray="6 4"
                                                        dot={{ r: 4 }}
                                                        activeDot={{ r: 6 }}
                                                        connectNulls
                                                    >
                                                        <LabelList dataKey="futureValue" content={renderFutureLineLabel} />
                                                    </Line>
                                                )}
                                            </LineChart>
                                        </ResponsiveContainer>
                                    </div>
                                    <div style={{ marginTop: '1rem' }}>
                                        <TrendLegend color={subjectColor} showPast={subjectHasPast} showFuture={subjectHasFuture} />
                                    </div>

                                    {subjectInsight && (
                                        <div style={{
                                            marginTop: '1.5rem',
                                            padding: '1rem 1.25rem',
                                            background: '#fafafa',
                                            borderLeft: `4px solid ${subjectColor}`,
                                            borderRadius: '6px',
                                            color: '#555',
                                            fontSize: '0.95rem',
                                            lineHeight: 1.6,
                                        }}>
                                            <div style={{ fontWeight: '600', color: subjectColor, marginBottom: '0.5rem' }}>💡 Nhận xét môn {SUBJECT_LABELS[subjectId]}</div>
                                            <div>{subjectInsight}</div>
                                        </div>
                                    )}
                                </div>
                            ) : (
                                <div style={{ padding: '2.5rem', textAlign: 'center', color: '#999', fontSize: '0.95rem' }}>Chưa có dữ liệu</div>
                            )}
                        </div>
                    );
                })}
            </div>
        );
    };

    return (
        <div style={{ maxWidth: '1400px', margin: '0 auto' }}>
            {pipelineStatus.text && (
                <div style={{
                    padding: '1rem',
                    borderRadius: '10px',
                    marginBottom: '1.25rem',
                    background: pipelineStatus.type === 'error' ? '#ffebee' : pipelineStatus.type === 'success' ? '#e8f5e9' : '#fffde7',
                    color: pipelineStatus.type === 'error' ? '#c62828' : pipelineStatus.type === 'success' ? '#2e7d32' : '#8d6e63'
                }}>
                    {pipelineStatus.text}
                </div>
            )}
            {/* Tabs and AI Analysis Button */}
            <div style={{ display: 'flex', gap: '0.75rem', marginBottom: '2rem', flexWrap: 'wrap', alignItems: 'center' }}>
                {tabs.map(tab => (
                    <button
                        key={tab}
                        onClick={() => setActiveTab(tab)}
                        className={`btn ${activeTab === tab ? 'btn-primary' : 'btn-outline'}`}
                        style={{ fontSize: '0.9rem' }}
                    >
                        {tab}
                    </button>
                ))}
                <div style={{ marginLeft: 'auto', display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
                    {aiProcessing && (
                        <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', color: '#5a67d8', fontSize: '0.85rem' }}>
                            <span className="spinner" aria-hidden="true"></span>
                            <span>Đang phân tích tab "{aiProcessingTab || activeTab}"...</span>
                        </div>
                    )}
                    <button
                        className="btn btn-primary"
                        onClick={() => handleGenerateComments(false)}
                        style={{
                            fontSize: '0.9rem',
                            opacity: aiProcessing ? 0.6 : 1,
                            cursor: aiProcessing ? 'not-allowed' : 'pointer'
                        }}
                        disabled={aiProcessing}
                    >
                        {aiProcessing ? `⏳ Đang xử lý...` : '✨ Phân tích AI'}
                    </button>
                </div>
            </div>

            {/* AI Overview Summary */}
            {activeTab === 'Chung' && getOverviewText('summary') && (
                <div style={{
                    background: 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)',
                    color: 'white',
                    padding: '1.5rem',
                    borderRadius: '12px',
                    marginBottom: '2rem',
                    boxShadow: '0 4px 6px rgba(0,0,0,0.1)'
                }}>
                    <strong>💡 Tổng quan:</strong>
                    <p style={{ marginTop: '0.5rem', opacity: 0.9 }}>{getOverviewText('summary')}</p>
                </div>
            )}

            {/* Content based on active tab */}
            {activeTab === 'Tổ Hợp' ? (
                (() => {
                    // Fallback headline logic for examHeadlineText
                    const examHeadlineText = null; // TODO: Replace with real logic if needed
                    return <>
                        {Object.keys(EXAM_BLOCKS).length === 0 ? (
                            <div style={{ padding: '3rem', textAlign: 'center', color: '#999', fontSize: '1rem' }}>
                                Tổ hợp chỉ khả dụng cho cấu trúc THPT
                            </div>
                        ) : (
                            <>
                                {examHeadlineText && (
                                    <div style={{
                                        background: 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)',
                                        color: 'white',
                                        padding: '1.5rem',
                                        borderRadius: '12px',
                                        marginBottom: '2rem',
                                        boxShadow: '0 4px 6px rgba(0,0,0,0.1)'
                                    }}>
                                        <strong>🎯 Gợi ý khối thi phù hợp:</strong>
                                        <p style={{ marginTop: '0.5rem', opacity: 0.9 }}>{examHeadlineText}</p>
                                    </div>
                                )}
                                {renderExamBlocks(examBlockDetails)}
                                {/* Custom Combination Selector */}
                                <div style={{ marginTop: '3rem', padding: '2rem', background: '#f8f9fa', borderRadius: '12px', border: '2px solid #e9ecef' }}>
                                    <h3 style={{ marginBottom: '1.5rem', fontSize: '1.3rem', fontWeight: '600', color: '#495057' }}>
                                        Lựa chọn tổ hợp:
                                    </h3>
                                    <div style={{ display: 'flex', gap: '1.5rem', flexWrap: 'wrap', alignItems: 'flex-start' }}>
                                        {/* Subject 1 */}
                                        <div style={{ flex: '1 1 200px', minWidth: '200px' }}>
                                            <label style={{ display: 'block', marginBottom: '0.5rem', fontWeight: '500', color: '#495057', fontSize: '0.95rem' }}>
                                                Môn 1:
                                            </label>
                                            <select
                                                value={customSubject1}
                                                onChange={(e) => setCustomSubject1(e.target.value)}
                                                style={{
                                                    width: '100%',
                                                    padding: '0.75rem',
                                                    fontSize: '0.95rem',
                                                    borderRadius: '8px',
                                                    border: '2px solid #dee2e6',
                                                    background: 'white',
                                                    cursor: 'pointer',
                                                    outline: 'none',
                                                    transition: 'border-color 0.2s',
                                                }}
                                                onFocus={(e) => e.target.style.borderColor = '#3498db'}
                                                onBlur={(e) => e.target.style.borderColor = '#dee2e6'}
                                            >
                                                <option value="">-- Chọn môn --</option>
                                                {getAvailableSubjects(customSubject1).map(subjectId => (
                                                    <option key={subjectId} value={subjectId}>
                                                        {SUBJECT_LABELS[subjectId]}
                                                    </option>
                                                ))}
                                            </select>
                                        </div>

                                        {/* Subject 2 */}
                                        <div style={{ flex: '1 1 200px', minWidth: '200px' }}>
                                            <label style={{ display: 'block', marginBottom: '0.5rem', fontWeight: '500', color: '#495057', fontSize: '0.95rem' }}>
                                                Môn 2:
                                            </label>
                                            <select
                                                value={customSubject2}
                                                onChange={(e) => setCustomSubject2(e.target.value)}
                                                style={{
                                                    width: '100%',
                                                    padding: '0.75rem',
                                                    fontSize: '0.95rem',
                                                    borderRadius: '8px',
                                                    border: '2px solid #dee2e6',
                                                    background: 'white',
                                                    cursor: 'pointer',
                                                    outline: 'none',
                                                    transition: 'border-color 0.2s',
                                                }}
                                                onFocus={(e) => e.target.style.borderColor = '#3498db'}
                                                onBlur={(e) => e.target.style.borderColor = '#dee2e6'}
                                            >
                                                <option value="">-- Chọn môn --</option>
                                                {getAvailableSubjects(customSubject2).map(subjectId => (
                                                    <option key={subjectId} value={subjectId}>
                                                        {SUBJECT_LABELS[subjectId]}
                                                    </option>
                                                ))}
                                            </select>
                                        </div>

                                        {/* Subject 3 */}
                                        <div style={{ flex: '1 1 200px', minWidth: '200px' }}>
                                            <label style={{ display: 'block', marginBottom: '0.5rem', fontWeight: '500', color: '#495057', fontSize: '0.95rem' }}>
                                                Môn 3:
                                            </label>
                                            <select
                                                value={customSubject3}
                                                onChange={(e) => setCustomSubject3(e.target.value)}
                                                style={{
                                                    width: '100%',
                                                    padding: '0.75rem',
                                                    fontSize: '0.95rem',
                                                    borderRadius: '8px',
                                                    border: '2px solid #dee2e6',
                                                    background: 'white',
                                                    cursor: 'pointer',
                                                    outline: 'none',
                                                    transition: 'border-color 0.2s',
                                                }}
                                                onFocus={(e) => e.target.style.borderColor = '#3498db'}
                                                onBlur={(e) => e.target.style.borderColor = '#dee2e6'}
                                            >
                                                <option value="">-- Chọn môn --</option>
                                                {getAvailableSubjects(customSubject3).map(subjectId => (
                                                    <option key={subjectId} value={subjectId}>
                                                        {SUBJECT_LABELS[subjectId]}
                                                    </option>
                                                ))}
                                            </select>
                                        </div>
                                    </div>

                                    {!isCustomCombinationValid && (customSubject1 || customSubject2 || customSubject3) && (
                                        <div style={{
                                            marginTop: '1rem',
                                            padding: '0.75rem 1rem',
                                            background: '#fff3cd',
                                            border: '1px solid #ffc107',
                                            borderRadius: '6px',
                                            color: '#856404',
                                            fontSize: '0.9rem'
                                        }}>
                                            Vui lòng chọn đủ 3 môn khác nhau để xem biểu đồ
                                        </div>
                                    )}
                                </div>

                                {/* Render custom combination chart */}
                                {renderCustomCombination()}
                            </>
                        )}
                    </>
                })()
            ) : activeTab === 'Từng Môn' ? (
                (() => {
                    console.log('[DataViz] Rendering "Từng Môn" tab');
                    // Use aiInsights?.subjects or fallback to empty object
                    return renderSubjects(aiInsights?.subjects || {});
                })()
            ) : (
                <div style={{ display: 'flex', flexDirection: 'column', gap: '2rem' }}>
                    {/* Line Chart */}
                    <div className="card" style={{ width: '100%', padding: '2rem' }}>
                        <h3 style={{ marginBottom: '1.5rem', fontSize: '1.3rem', fontWeight: '600' }}>Diễn biến điểm trung bình theo từng học kỳ</h3>
                        <p style={{ marginTop: '-1rem', marginBottom: '1.5rem', fontSize: '0.9rem', color: '#666' }}>
                            Mốc thời gian hiện tại: {currentGradeLabel || 'Chưa thiết lập'}
                        </p>
                        {hasAnyTermData ? (
                            (() => {
                                // Use improved V2 logic if activeStructure exists, else fallback to legacy
                                const generalSeriesV2 = buildGeneralTermSeriesV2(filteredData);
                                const chartData = generalSeriesV2 || activeTermSeries;
                                const hasPastData = chartData.some(d => d.pastValue !== null);
                                const hasFutureData = chartData.some(d => d.futureValue !== null);
                                const lineColor = '#d32f2f';

                                return (
                                    <div style={{ display: 'flex', flexDirection: 'column' }}>
                                        <div style={{ height: '400px', width: '100%' }}>
                                            <ResponsiveContainer width="100%" height="100%">
                                                <LineChart data={chartData}>
                                                    <defs>
                                                        <linearGradient id="colorValue" x1="0" y1="0" x2="0" y2="1">
                                                            <stop offset="5%" stopColor={lineColor} stopOpacity={0.8} />
                                                            <stop offset="95%" stopColor={lineColor} stopOpacity={0.1} />
                                                        </linearGradient>
                                                    </defs>
                                                    <CartesianGrid strokeDasharray="3 3" stroke="#eee" />
                                                    <XAxis dataKey="term" stroke="#888" tickFormatter={formatTermLabel} interval={0} tick={{ fontSize: 12 }} ticks={getXAxisTicks(chartData)} />
                                                    <YAxis domain={computeChartDomain(chartData)} stroke="#888" tick={{ fontSize: 12 }} tickFormatter={formatYAxisTick} />
                                                    <Tooltip content={<TermAverageTooltip formatTermLabel={formatTermLabel} />} />
                                                    {hasPastData && (
                                                        <Line
                                                            type="monotone"
                                                            dataKey="pastValue"
                                                            name="Xu hướng hiện tại"
                                                            stroke={lineColor}
                                                            strokeWidth={3.5}
                                                            dot={{ r: 6 }}
                                                            activeDot={{ r: 8 }}
                                                            connectNulls
                                                            isAnimationActive
                                                        >
                                                            <LabelList dataKey="pastValue" content={renderLineLabel} />
                                                        </Line>
                                                    )}
                                                    {hasFutureData && (
                                                        <Line
                                                            type="monotone"
                                                            dataKey="futureValue"
                                                            name="Xu hướng tương lai"
                                                            stroke={lineColor}
                                                            strokeWidth={3.5}
                                                            strokeDasharray="6 4"
                                                            dot={{ r: 6 }}
                                                            activeDot={{ r: 8 }}
                                                            connectNulls
                                                            isAnimationActive
                                                        >
                                                            <LabelList dataKey="futureValue" content={renderFutureLineLabel} />
                                                        </Line>
                                                    )}
                                                </LineChart>
                                            </ResponsiveContainer>
                                        </div>
                                        <div style={{ marginTop: '1rem' }}>
                                            <TrendLegend color={lineColor} showPast={hasPastData} showFuture={hasFutureData} />
                                            {getOverviewText('trend') && (
                                                <div style={{
                                                    marginTop: '1.5rem',
                                                    padding: '1rem 1.25rem',
                                                    background: '#fafafa',
                                                    borderLeft: `4px solid ${lineColor}`,
                                                    borderRadius: '6px',
                                                    color: '#555',
                                                    fontSize: '0.95rem',
                                                    lineHeight: 1.6,
                                                }}>
                                                    <div style={{ fontWeight: '600', color: lineColor, marginBottom: '0.5rem' }}>💡 Phân tích xu hướng học tập</div>
                                                    <div>{getOverviewText('trend')}</div>
                                                </div>
                                            )}
                                        </div>
                                    </div>
                                );
                            })()
                        ) : (
                            <div style={{ padding: '3rem', textAlign: 'center', color: '#999', fontSize: '1rem' }}>Chưa có dữ liệu</div>
                        )}
                    </div>
                    {/* Bar Chart - Split Layout */}
                    <div className="card" style={{ width: '100%', padding: '2rem' }}>
                        <h3 style={{ marginBottom: '1.5rem', fontSize: '1.3rem', fontWeight: '600' }}>So sánh các môn</h3>
                        <p style={{ marginTop: '-1rem', marginBottom: '1.5rem', fontSize: '0.9rem', color: '#666' }}>
                            Trung bình theo từng môn học tính tới hiện tại
                        </p>
                        {barData.length > 0 ? (
                            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '2rem', alignItems: 'start' }}>
                                {/* Chart - Left */}
                                <div style={{ height: '400px' }}>
                                    <ResponsiveContainer width="100%" height="100%">
                                        <BarChart data={barData} layout="vertical">
                                            <CartesianGrid strokeDasharray="3 3" stroke="#eee" horizontal={false} />
                                            <XAxis type="number" domain={computeBarChartDomain(barData)} stroke="#888" tick={{ fontSize: 12 }} tickFormatter={formatBarXAxisTick} />
                                            <YAxis dataKey="subjectLabel" type="category" width={110} stroke="#888" tick={{ fontSize: 12 }} />
                                            <Tooltip formatter={(value) => (value === null || value === undefined ? '-' : Number(value).toFixed(2))} cursor={{ fill: '#f5f5f5' }} contentStyle={{ borderRadius: '8px' }} />
                                            <Bar dataKey="avg" name="Điểm TB" radius={[0, 4, 4, 0]} barSize={26}>
                                                {barData.map(item => (
                                                    <Cell key={item.subjectId} fill={getSubjectColor(item.subjectId)} />
                                                ))}
                                                <LabelList dataKey="avg" content={renderBarLabel} />
                                            </Bar>
                                        </BarChart>
                                    </ResponsiveContainer>
                                </div>
                                {/* AI Insight - Right */}
                                <div style={{ display: 'flex', flexDirection: 'column', justifyContent: 'center', minHeight: '400px' }}>
                                    {getOverviewText('subjects') ? (
                                        <div style={{
                                            padding: '2rem',
                                            background: 'linear-gradient(135deg, #667eea15 0%, #764ba215 100%)',
                                            borderRadius: '16px',
                                            border: '2px solid #e8eaf6',
                                            boxShadow: '0 4px 12px rgba(102, 126, 234, 0.08)',
                                            position: 'relative',
                                            overflow: 'hidden',
                                        }}>
                                            <div style={{
                                                position: 'absolute',
                                                top: 0,
                                                left: 0,
                                                width: '5px',
                                                height: '100%',
                                                background: 'linear-gradient(180deg, #667eea 0%, #764ba2 100%)',
                                            }} />
                                            <div style={{
                                                display: 'flex',
                                                alignItems: 'center',
                                                gap: '0.75rem',
                                                marginBottom: '1.25rem',
                                                fontWeight: '700',
                                                fontSize: '1.15rem',
                                                color: '#5a67d8',
                                            }}>
                                                <span>💡 Đánh giá theo từng môn</span>
                                            </div>
                                            <div style={{
                                                color: '#34495e',
                                                fontSize: '1rem',
                                                lineHeight: 1.7,
                                                fontWeight: '400',
                                            }}>{getOverviewText('subjects')}</div>
                                        </div>
                                    ) : (
                                        <div style={{
                                            padding: '2rem',
                                            background: '#f8f9fa',
                                            borderRadius: '8px',
                                            textAlign: 'center',
                                            color: '#999'
                                        }}>
                                            <p>Hãy nhấn "Phân tích AI" để nhận đánh giá chi tiết về các môn học của bạn.</p>
                                        </div>
                                    )}
                                </div>
                            </div>
                        ) : (
                            <div style={{ padding: '3rem', textAlign: 'center', color: '#999', fontSize: '1rem' }}>Chưa có dữ liệu</div>
                        )}
                    </div>

                    {/* Radar Chart - Split Layout */}
                    <div className="card" style={{ width: '100%', padding: '2rem' }}>
                        <h3 style={{ marginBottom: '1.5rem', fontSize: '1.3rem', fontWeight: '600' }}>Biểu đồ năng lực</h3>
                        {barData.length > 0 ? (
                            <div style={{
                                display: 'grid',
                                gridTemplateColumns: '1fr 1fr',
                                gap: '2rem',
                                alignItems: 'center'
                            }}>
                                {/* Left side - AI Insight */}
                                <div style={{
                                    display: 'flex',
                                    flexDirection: 'column',
                                    justifyContent: 'center',
                                    minHeight: '500px'
                                }}>
                                    <div style={{
                                        padding: '2rem',
                                        background: 'linear-gradient(135deg, #667eea15 0%, #764ba215 100%)',
                                        borderRadius: '16px',
                                        border: '2px solid #e8eaf6',
                                        boxShadow: '0 4px 12px rgba(102, 126, 234, 0.08)',
                                        position: 'relative',
                                        overflow: 'hidden',
                                    }}>
                                        <div style={{
                                            position: 'absolute',
                                            top: 0,
                                            left: 0,
                                            width: '5px',
                                            height: '100%',
                                            background: 'linear-gradient(180deg, #667eea 0%, #764ba2 100%)',
                                        }} />
                                        <div style={{
                                            display: 'flex',
                                            alignItems: 'center',
                                            gap: '0.75rem',
                                            marginBottom: '1.25rem',
                                            fontWeight: '700',
                                            fontSize: '1.15rem',
                                            color: '#5a67d8',
                                        }}>
                                            <span style={{ fontSize: '1.5rem' }}></span>
                                            <span>💡 Ưu - nhược điểm</span>
                                        </div>
                                        <div style={{
                                            color: '#34495e',
                                            fontSize: '1rem',
                                            lineHeight: 1.7,
                                            fontWeight: '400',
                                        }}>
                                            {getOverviewText('radar') || 'Biểu đồ thể hiện năng lực của bạn trên các môn học khác nhau. Các đỉnh cao hơn cho thấy những môn bạn đang làm tốt, trong khi các đỉnh thấp hơn là những môn cần cải thiện.'}
                                        </div>
                                    </div>
                                </div>

                                {/* Right side - Radar Chart */}
                                <div style={{
                                    display: 'flex',
                                    alignItems: 'center',
                                    justifyContent: 'center',
                                    minHeight: '500px'
                                }}>
                                    {currentTermRadarData.length > 0 ? (
                                        <ResponsiveContainer width="100%" height={500}>
                                            <RadarChart cx="50%" cy="50%" outerRadius="70%" data={currentTermRadarData}>
                                                <PolarGrid
                                                    stroke="#d1d5db"
                                                    strokeWidth={1.5}
                                                />
                                                <PolarAngleAxis
                                                    dataKey="subjectLabel"
                                                    tick={{
                                                        fill: '#374151',
                                                        fontSize: 14,
                                                        fontWeight: '600'
                                                    }}
                                                />
                                                <PolarRadiusAxis
                                                    angle={90}
                                                    domain={computeRadarDomain(currentTermRadarData)}
                                                    tick={false}
                                                    tickLine={false}
                                                    axisLine={false}
                                                />
                                                <Radar
                                                    name="Điểm mốc thời gian hiện tại"
                                                    dataKey="value"
                                                    stroke="#5a67d8"
                                                    fill="#667eea"
                                                    fillOpacity={0.5}
                                                    strokeWidth={3}
                                                >
                                                    <LabelList dataKey="value" content={renderRadarLabel} />
                                                </Radar>
                                                <Legend
                                                    wrapperStyle={{
                                                        fontSize: '1rem',
                                                        fontWeight: '600',
                                                        paddingTop: '1rem'
                                                    }}
                                                />
                                            </RadarChart>
                                        </ResponsiveContainer>
                                    ) : (
                                        <div style={{ textAlign: 'center', color: '#999', fontSize: '0.95rem' }}>
                                            {currentGradeLabel ? `Chưa có dữ liệu cho ${currentGradeLabel}.` : 'Chưa xác định mốc thời gian hiện tại.'}
                                        </div>
                                    )}
                                </div>
                            </div>
                        ) : (
                            <div style={{ padding: '3rem', textAlign: 'center', color: '#999', fontSize: '1rem' }}>Chưa có dữ liệu</div>
                        )}
                        <div style={{
                            marginTop: '1.25rem',
                            padding: '0.85rem 1rem',
                            background: '#f4f5fb',
                            borderRadius: '8px',
                            color: '#5a67d8',
                            fontSize: '0.9rem',
                            textAlign: 'center'
                        }}>
                            {radarNoteText}
                        </div>
                    </div>
                </div>
            )}
        </div>
    );
};

export default DataViz;

import React, { useState, useEffect, useMemo, useCallback, useRef } from 'react';
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer, BarChart, Bar, RadarChart, PolarGrid, PolarAngleAxis, PolarRadiusAxis, Radar, Cell, LabelList } from 'recharts';
import axiosClient from '../api/axiosClient';
import {
    REFRESH_DATA_EVENTS,
    ML_PIPELINE_PROCESSING_EVENT,
    ML_PIPELINE_COMPLETED_EVENT,
} from '../utils/eventBus';

const TERM_ORDER = ['1_10', '2_10', '1_11', '2_11', '1_12', '2_12'];

const formatTermLabel = (term) => {
    if (!term) return '';
    const [semester, grade] = term.split('_');
    return `Học kỳ ${semester} lớp ${grade}`;
};

const formatCurrentTerm = (term) => {
    const formatted = formatTermLabel(term);
    return formatted || null;
};

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

const slotIndexForTerm = (token) => {
    if (!token) return null;
    const normalized = String(token).toUpperCase();
    for (let i = 0; i < TERM_ORDER.length; i += 1) {
        if (TERM_ORDER[i].toUpperCase() === normalized) {
            return i;
        }
    }
    return null;
};

const computeTermAverageMap = (data) => {
    const buckets = new Map();
    data.forEach(item => {
        const displayValue = item.actual !== null && item.actual !== undefined
            ? Number(item.actual)
            : item.predicted !== null && item.predicted !== undefined
                ? Number(item.predicted)
                : null;
        if (displayValue === null || Number.isNaN(displayValue)) return;
        const termKey = `${item.semester}_${item.grade_level}`;
        if (!buckets.has(termKey)) buckets.set(termKey, []);
        buckets.get(termKey).push(displayValue);
    });

    const averages = new Map();
    buckets.forEach((values, key) => {
        const avg = values.reduce((sum, val) => sum + val, 0) / values.length;
        averages.set(key, avg);
    });
    return averages;
};

const buildTermSeries = (termAverageMap, currentIdx) => (
    TERM_ORDER.map((term, idx) => {
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
    })
);

const TermAverageTooltip = ({ active, payload }) => {
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

const SUBJECT_COLORS = {
    'Toan': '#1f77b4',
    'Ngu van': '#e74c3c',
    'Tieng Anh': '#f1c40f',
    'Vat ly': '#9b59b6',
    'Hoa hoc': '#16a085',
    'Sinh hoc': '#2ecc71',
    'Lich su': '#d35400',
    'Dia ly': '#2980b9',
    'Giao duc cong dan': '#34495e',
};

const getSubjectColor = (subjectId) => SUBJECT_COLORS[subjectId] || '#7f8c8d';

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

const AI_COMMENTS_STORAGE_KEY = 'dataviz_ai_comments';
const AI_COMMENTS_VERSION = 3;

const DataViz = () => {
    const [scores, setScores] = useState([]);
    const [termAverages, setTermAverages] = useState([]);
    const [currentGrade, setCurrentGrade] = useState(null);
    const [activeTab, setActiveTab] = useState('Chung');
    const [loading, setLoading] = useState(true);
    const [aiInsights, setAiInsights] = useState(null);
    const [pipelineStatus, setPipelineStatus] = useState({ type: '', text: '' });
    const [aiProcessing, setAiProcessing] = useState(false);
    const pipelineTimeoutRef = useRef(null);
    
    // Custom combination state
    const [customSubject1, setCustomSubject1] = useState('');
    const [customSubject2, setCustomSubject2] = useState('');
    const [customSubject3, setCustomSubject3] = useState('');

    const fetchData = useCallback(async (silent = false) => {
        try {
            if (!silent) {
                setLoading(true);
            }
            const res = await axiosClient.get('/study/scores');
            setScores(res.data.scores || []);
            setTermAverages(res.data.term_averages || []);
            if (Object.prototype.hasOwnProperty.call(res.data, 'current_grade')) {
                setCurrentGrade(res.data.current_grade || null);
            }
        } catch (e) {
            console.error(e);
        } finally {
            if (!silent) {
                setLoading(false);
            }
        }
    }, []);

    useEffect(() => {
        fetchData();
    }, [fetchData]);

    useEffect(() => {
        const handler = () => fetchData(true);
        REFRESH_DATA_EVENTS.forEach(evt => window.addEventListener(evt, handler));
        return () => {
            REFRESH_DATA_EVENTS.forEach(evt => window.removeEventListener(evt, handler));
        };
    }, [fetchData]);

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
            window.localStorage.setItem(AI_COMMENTS_STORAGE_KEY, JSON.stringify({ version, insights }));
        } catch (storageErr) {
            console.error('Failed to persist AI comments', storageErr);
        }
    }, []);

    useEffect(() => {
        if (typeof window === 'undefined' || !window.localStorage) return;
        try {
            const raw = window.localStorage.getItem(AI_COMMENTS_STORAGE_KEY);
            if (!raw) return;
            const parsed = JSON.parse(raw);
            if (parsed && parsed.version === AI_COMMENTS_VERSION && parsed.insights) {
                setAiInsights(parsed.insights);
            } else {
                window.localStorage.removeItem(AI_COMMENTS_STORAGE_KEY);
            }
        } catch (storageErr) {
            console.error('Failed to restore AI comments', storageErr);
        }
    }, []);

    const handleGenerateComments = async (silent = false) => {
        if (!silent) {
            setAiProcessing(true);
        }
        try {
            const res = await axiosClient.post('/study/generate-slide-comments', {}, {
                timeout: 60000, // 60s timeout for AI analysis
            });
            if (!silent) {
                persistAiInsightsState(res.data.slide_comments || {}, res.data.comments_version || AI_COMMENTS_VERSION);
            }
        } catch (e) {
            if (!silent) alert('Lỗi sinh nhận xét: ' + e.message);
            // otherwise fail silently
        } finally {
            if (!silent) {
                setAiProcessing(false);
            }
        }
    };

    // Data Processing Helpers
    const KHOI_XH = ['Toan', 'Ngu van', 'Tieng Anh', 'Lich su', 'Dia ly', 'Giao duc cong dan'];
    const KHOI_TN = ['Toan', 'Ngu van', 'Tieng Anh', 'Vat ly', 'Hoa hoc', 'Sinh hoc'];
    const EXAM_BLOCKS = {
        'A00': ['Toan', 'Vat ly', 'Hoa hoc'],
        'B00': ['Toan', 'Hoa hoc', 'Sinh hoc'],
        'C00': ['Ngu van', 'Lich su', 'Dia ly'],
        'D01': ['Toan', 'Ngu van', 'Tieng Anh']
    };
    const ALL_SUBJECTS = ['Toan', 'Ngu van', 'Tieng Anh', 'Vat ly', 'Hoa hoc', 'Sinh hoc', 'Lich su', 'Dia ly', 'Giao duc cong dan'];
    const SUBJECT_LABELS = {
        'Toan': 'Toán',
        'Ngu van': 'Ngữ văn',
        'Tieng Anh': 'Tiếng Anh',
        'Vat ly': 'Vật lý',
        'Hoa hoc': 'Hóa học',
        'Sinh hoc': 'Sinh học',
        'Lich su': 'Lịch sử',
        'Dia ly': 'Địa lý',
        'Giao duc cong dan': 'GDCD'
    };

    const getFilteredScores = () => {
        if (activeTab === 'Khối XH') return scores.filter(s => KHOI_XH.includes(s.subject));
        if (activeTab === 'Khối TN') return scores.filter(s => KHOI_TN.includes(s.subject));
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

    const processBarData = (data) => {
        const grouped = {};
        data.forEach(item => {
            if (!grouped[item.subject]) grouped[item.subject] = [];
            const val = (item.actual !== null && item.actual !== undefined) ? Number(item.actual) : ((item.predicted !== null && item.predicted !== undefined) ? Number(item.predicted) : 0);
            grouped[item.subject].push(val);
        });

        return Object.entries(grouped).map(([subject, values]) => ({
            subjectId: subject,
            subjectLabel: SUBJECT_LABELS[subject] || subject,
            avg: values.reduce((a, b) => a + b, 0) / values.length
        })).sort((a, b) => b.avg - a.avg);
    };

    const buildCurrentTermRadarData = (data, currentTermToken) => {
        if (!currentTermToken) return [];
        const parts = String(currentTermToken).split('_');
        if (parts.length !== 2) return [];
        const [semesterToken, gradeToken] = parts;
        if (!semesterToken || !gradeToken) return [];
        const semester = semesterToken.toString();
        const grade = gradeToken.toString();

        const subjectValues = new Map();
        data.forEach(item => {
            if (item.grade_level !== grade || item.semester !== semester) return;
            const value = item.actual !== null && item.actual !== undefined
                ? Number(item.actual)
                : item.predicted !== null && item.predicted !== undefined
                    ? Number(item.predicted)
                    : null;
            if (value === null || Number.isNaN(value)) return;
            subjectValues.set(item.subject, Number(value));
        });

        if (subjectValues.size === 0) return [];

        const dataPoints = [];
        ALL_SUBJECTS.forEach(subjectId => {
            if (subjectValues.has(subjectId)) {
                dataPoints.push({
                    subjectId,
                    subjectLabel: SUBJECT_LABELS[subjectId] || subjectId,
                    value: subjectValues.get(subjectId),
                });
            }
        });

        const remainingSubjects = Array.from(subjectValues.keys()).filter(subjectId => !ALL_SUBJECTS.includes(subjectId)).sort();
        remainingSubjects.forEach(subjectId => {
            dataPoints.push({
                subjectId,
                subjectLabel: SUBJECT_LABELS[subjectId] || subjectId,
                value: subjectValues.get(subjectId),
            });
        });

        return dataPoints;
    };

    const filteredData = getFilteredScores();
    const barData = processBarData(filteredData);
    const currentIdx = slotIndexForTerm(currentGrade);
    const currentGradeLabel = currentGrade ? formatCurrentTerm(currentGrade) : null;
    const currentTermRadarData = useMemo(
        () => buildCurrentTermRadarData(scores, currentGrade),
        [scores, currentGrade]
    );

    const generalTermSeries = useMemo(() => {
        const map = new Map();
        termAverages.forEach(item => {
            if (!item || !item.term || item.average === undefined || item.average === null) return;
            map.set(item.term, Number(item.average));
        });
        return buildTermSeries(map, currentIdx);
    }, [termAverages, currentIdx]);

    const filteredTermSeries = useMemo(() => {
        const averages = computeTermAverageMap(filteredData);
        return buildTermSeries(averages, currentIdx);
    }, [filteredData, currentIdx]);

    const activeTermSeries = useMemo(() => {
        if (activeTab === 'Chung') {
            return generalTermSeries;
        }
        if (activeTab === 'Khối XH' || activeTab === 'Khối TN') {
            return filteredTermSeries;
        }
        return generalTermSeries;
    }, [activeTab, generalTermSeries, filteredTermSeries]);

    const hasPastSegment = useMemo(() => activeTermSeries.some(point => point.pastValue !== null), [activeTermSeries]);
    const hasFutureSegment = useMemo(() => activeTermSeries.some(point => point.futureValue !== null), [activeTermSeries]);
    const hasAnyTermData = useMemo(() => activeTermSeries.some(point => point.display !== null), [activeTermSeries]);

    const radarNoteText = useMemo(() => {
        if (!currentGradeLabel) {
            return 'Vui lòng chọn học kỳ hiện tại để hiển thị biểu đồ radar.';
        }
        if (!currentTermRadarData.length) {
            return `Chưa có điểm nào cho ${currentGradeLabel}, vui lòng bổ sung dữ liệu để xem biểu đồ.`;
        }
        return `Biểu đồ hiển thị điểm từng môn trong ${currentGradeLabel}.`;
    }, [currentGradeLabel, currentTermRadarData]);

    const tabs = ['Chung', 'Khối XH', 'Khối TN', 'Tổ Hợp', 'Từng Môn'];

    const overviewInsights = aiInsights?.overview || {};
    const examBlockInsights = aiInsights?.exam_blocks || {};
    const examHeadlineCard = examBlockInsights.headline || {};
    const examBlockDetails = examBlockInsights.blocks || {};
    const examHeadlineText = examHeadlineCard?.narrative?.headline || examHeadlineCard?.structured || '';
    const subjectInsightMap = aiInsights?.subjects || {};
    const activeOverview = overviewInsights[activeTab];
    const getOverviewText = (key) => {
        if (!activeOverview) return null;
        return activeOverview?.narrative?.[key] || activeOverview?.structured?.[key] || null;
    };

    if (loading) return <div style={{ padding: '2rem' }}>Đang tải dữ liệu...</div>;

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
        const blockBarData = processBarData(blockScores);
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
                                    <XAxis dataKey="term" tick={{ fontSize: 12 }} tickFormatter={formatTermLabel} interval={0} />
                                    <YAxis domain={[0, 10]} tick={{ fontSize: 12 }} />
                                    <Tooltip content={<TermAverageTooltip />} />
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
                                    <XAxis type="number" domain={[0, 10]} tick={{ fontSize: 11 }} />
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
                const blockScores = scores.filter(s => subjects.includes(s.subject));
                const blockSeries = buildTermSeries(computeTermAverageMap(blockScores), currentIdx);
                const blockHasData = blockSeries.some(point => point.display !== null);
                const blockHasPast = blockSeries.some(point => point.pastValue !== null);
                const blockHasFuture = blockSeries.some(point => point.futureValue !== null);
                const blockBarData = processBarData(blockScores);
                const colors = { 'A00': '#e74c3c', 'B00': '#f39c12', 'C00': '#16a085', 'D01': '#8e44ad' };
                const blockInsight = blockComments[blockName];
                const insight = blockInsight?.narrative?.comment || blockInsight?.structured?.comment || blockInsight?.comment || '';

                return (
                    <div key={blockName} className="card" style={{ borderTop: `4px solid ${colors[blockName]}`, width: '100%', padding: '2rem' }}>
                        <h3 style={{ marginBottom: '1.25rem', fontSize: '1.3rem', fontWeight: '600', color: colors[blockName] }}>
                            Tổ Hợp {blockName}
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
                                            <XAxis dataKey="term" tick={{ fontSize: 12 }} tickFormatter={formatTermLabel} interval={0} />
                                            <YAxis domain={[0, 10]} tick={{ fontSize: 12 }} />
                                            <Tooltip content={<TermAverageTooltip />} />
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

                                <div style={{ height: '220px', marginTop: '2rem' }}>
                                    <ResponsiveContainer width="100%" height="100%">
                                        <BarChart data={blockBarData} layout="vertical">
                                            <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" horizontal={false} />
                                            <XAxis type="number" domain={[0, 10]} tick={{ fontSize: 11 }} />
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
    const renderSubjects = (subjectComments = {}) => (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '1.5rem' }}>
            {ALL_SUBJECTS.map((subjectId) => {
                const subjectScores = scores.filter(s => s.subject === subjectId);
                const subjectSeries = buildTermSeries(computeTermAverageMap(subjectScores), currentIdx);
                const subjectHasData = subjectSeries.some(point => point.display !== null);
                const subjectHasPast = subjectSeries.some(point => point.pastValue !== null);
                const subjectHasFuture = subjectSeries.some(point => point.futureValue !== null);
                const subjectColor = getSubjectColor(subjectId);
                const subjectInsightPayload = subjectComments[subjectId];
                const subjectInsight = subjectInsightPayload?.narrative?.comment || subjectInsightPayload?.structured?.comment || subjectInsightPayload?.comment || '';

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
                                            <XAxis dataKey="term" tick={{ fontSize: 11 }} tickFormatter={formatTermLabel} interval={0} />
                                            <YAxis domain={[0, 10]} tick={{ fontSize: 11 }} />
                                            <Tooltip content={<TermAverageTooltip />} />
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
                            Đang sinh phân tích AI...
                        </div>
                    )}
                    <button
                        className="btn btn-primary"
                        onClick={() => handleGenerateComments(false)}
                        style={{ fontSize: '0.9rem' }}
                        disabled={aiProcessing}
                    >
                        {aiProcessing ? 'Đang xử lý...' : 'Phân tích AI'}
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
                <>
                    <InsightBox title="Gợi ý khối thi phù hợp" text={examHeadlineText} />
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
                                ⚠️ Vui lòng chọn đủ 3 môn khác nhau để xem biểu đồ
                            </div>
                        )}
                    </div>
                    
                    {/* Render custom combination chart */}
                    {renderCustomCombination()}
                </>
            ) : activeTab === 'Từng Môn' ? (
                renderSubjects(subjectInsightMap)
            ) : (
                <div style={{ display: 'flex', flexDirection: 'column', gap: '2rem' }}>
                    {/* Line Chart */}
                    <div className="card" style={{ width: '100%', padding: '2rem' }}>
                        <h3 style={{ marginBottom: '1.5rem', fontSize: '1.3rem', fontWeight: '600' }}> Diễn biến điểm trung bình</h3>
                        <p style={{ marginTop: '-1rem', marginBottom: '1.5rem', fontSize: '0.9rem', color: '#666' }}>
                            Học kỳ hiện tại: {currentGradeLabel || 'Chưa thiết lập'}
                        </p>
                        {hasAnyTermData ? (
                            (() => {
                                // Determine color based on activeTab
                                const lineColor = activeTab === 'Khối TN' ? '#2ecc71' : activeTab === 'Khối XH' ? '#f1c40f' : '#d32f2f';

                                return (
                                    <div style={{ display: 'flex', flexDirection: 'column' }}>
                                        <div style={{ height: '400px', width: '100%' }}>
                                            <ResponsiveContainer width="100%" height="100%">
                                                <LineChart data={activeTermSeries}>
                                                    <defs>
                                                        <linearGradient id="colorValue" x1="0" y1="0" x2="0" y2="1">
                                                            <stop offset="5%" stopColor={lineColor} stopOpacity={0.8} />
                                                            <stop offset="95%" stopColor={lineColor} stopOpacity={0.1} />
                                                        </linearGradient>
                                                    </defs>
                                                    <CartesianGrid strokeDasharray="3 3" stroke="#eee" />
                                                    <XAxis dataKey="term" stroke="#888" tickFormatter={formatTermLabel} interval={0} tick={{ fontSize: 12 }} />
                                                    <YAxis domain={[0, 10]} stroke="#888" tick={{ fontSize: 12 }} />
                                                    <Tooltip content={<TermAverageTooltip />} />
                                                    {hasPastSegment && (
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
                                                    {hasFutureSegment && (
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
                                            <TrendLegend color={lineColor} showPast={hasPastSegment} showFuture={hasFutureSegment} />
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
                    {/* Bar Chart */}
                    <div className="card" style={{ width: '100%', padding: '2rem' }}>
                        <h3 style={{ marginBottom: '1.5rem', fontSize: '1.3rem', fontWeight: '600' }}>So sánh các môn</h3>
                        {barData.length > 0 ? (
                            <div style={{ display: 'flex', flexDirection: 'column' }}>
                                <div style={{ height: '380px', width: '100%' }}>
                                    <ResponsiveContainer width="100%" height="100%">
                                        <BarChart data={barData} layout="vertical">
                                            <CartesianGrid strokeDasharray="3 3" stroke="#eee" horizontal={false} />
                                            <XAxis type="number" domain={[0, 10]} stroke="#888" tick={{ fontSize: 12 }} />
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
                                {getOverviewText('subjects') && (
                                    <div style={{
                                        marginTop: '1.5rem',
                                        padding: '1rem 1.25rem',
                                        background: '#fafafa',
                                        borderLeft: '4px solid #667eea',
                                        borderRadius: '6px',
                                        color: '#555',
                                        fontSize: '0.95rem',
                                        lineHeight: 1.6,
                                    }}>
                                        <div style={{ fontWeight: '600', color: '#667eea', marginBottom: '0.5rem' }}>💡 Đánh giá theo từng môn</div>
                                        <div>{getOverviewText('subjects')}</div>
                                    </div>
                                )}
                            </div>
                        ) : (
                            <div style={{ padding: '3rem', textAlign: 'center', color: '#999', fontSize: '1rem' }}>Chưa có dữ liệu</div>
                        )}
                    </div>

                    {/* Radar Chart */}
                    <div className="card" style={{ width: '100%', padding: '2rem' }}>
                        <h3 style={{ marginBottom: '1.5rem', fontSize: '1.3rem', fontWeight: '600' }}> Biểu đồ năng lực</h3>
                        {barData.length > 0 ? (
                            <div style={{
                                display: 'flex',
                                gap: '2rem',
                                alignItems: 'stretch',
                                minHeight: '500px'
                            }}>
                                {/* Left side - AI Comments */}
                                <div style={{
                                    flex: '0 0 40%',
                                    display: 'flex',
                                    flexDirection: 'column',
                                    justifyContent: 'center'
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
                                    flex: '0 0 60%',
                                    display: 'flex',
                                    alignItems: 'center',
                                    justifyContent: 'center'
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
                                                    domain={[0, 10]}
                                                    tick={false}
                                                    tickLine={false}
                                                    axisLine={false}
                                                />
                                                <Radar
                                                    name="Điểm học kỳ hiện tại"
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
                                            {currentGradeLabel ? `Chưa có dữ liệu cho ${currentGradeLabel}.` : 'Chưa xác định học kỳ hiện tại.'}
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

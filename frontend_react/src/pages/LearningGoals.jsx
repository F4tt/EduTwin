import React, { useState, useEffect } from 'react';
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer, BarChart, Bar, Cell, LabelList } from 'recharts';
import axiosClient from '../api/axiosClient';
import { Target, TrendingUp, Award, Lightbulb } from 'lucide-react';
import { REFRESH_DATA_EVENTS } from '../utils/eventBus';
import { useAuth } from '../context/AuthContext';

const AI_STRATEGY_VERSION = 1;

// Helper to get user-specific storage key for AI strategy
const getAiStrategyStorageKey = (username) => {
    return username ? `learning_goals_strategy_${username}` : 'learning_goals_strategy_guest';
};

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

const formatTermLabel = (term) => {
    if (!term) return '';
    const [semester, grade] = term.split('_');
    return `HK${semester} L${grade}`;
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

const renderBarLabel = ({ x, y, width, height, value }) => {
    if (value === null || value === undefined) return null;
    // Position label to the right of bar with some padding
    const textX = x + width + 8;
    const textY = y + height / 2 + 4; // Center vertically
    return (
        <text x={textX} y={textY} textAnchor="start" fill="#444" fontSize={10} fontWeight="500">
            {formatScoreValue(value)}
        </text>
    );
};

const LearningGoals = () => {
    const { user } = useAuth();
    const [targetScore, setTargetScore] = useState('');
    const [currentGoal, setCurrentGoal] = useState(null);
    const [loading, setLoading] = useState(true);
    const [submitting, setSubmitting] = useState(false);
    const [generatingStrategy, setGeneratingStrategy] = useState(false);
    const [error, setError] = useState(null);
    const [currentScores, setCurrentScores] = useState({});
    const [aiStrategy, setAiStrategy] = useState(null);

    useEffect(() => {
        fetchCurrentGoal();
        fetchCurrentScores();

        // Listen for data refresh events from StudyUpdate
        const handleDataRefresh = () => {
            console.log('Refreshing learning goals data after study update');
            fetchCurrentScores();
        };

        REFRESH_DATA_EVENTS.forEach(eventName => {
            window.addEventListener(eventName, handleDataRefresh);
        });

        return () => {
            REFRESH_DATA_EVENTS.forEach(eventName => {
                window.removeEventListener(eventName, handleDataRefresh);
            });
        };
    }, []);

    // Restore AI strategy from localStorage on mount
    useEffect(() => {
        if (typeof window === 'undefined' || !window.localStorage) return;
        if (!user?.username || !currentGoal) {
            return;
        }

        try {
            const storageKey = getAiStrategyStorageKey(user.username);
            const raw = window.localStorage.getItem(storageKey);
            if (!raw) return;

            const parsed = JSON.parse(raw);
            // Only restore if version matches and goal_id matches
            if (parsed &&
                parsed.version === AI_STRATEGY_VERSION &&
                parsed.goal_id === currentGoal.id &&
                parsed.strategy) {
                setAiStrategy(parsed.strategy);
            } else {
                // Clear outdated strategy
                window.localStorage.removeItem(storageKey);
            }
        } catch (storageErr) {
            console.error('Failed to restore AI strategy', storageErr);
        }
    }, [user?.username, currentGoal?.id]);

    const fetchCurrentGoal = async () => {
        try {
            setLoading(true);
            const res = await axiosClient.get('/learning-goals/current-goal');
            if (res.data.has_goal) {
                setCurrentGoal(res.data);
                setTargetScore(res.data.target_average.toString());
                // Load AI strategy if exists
                if (res.data.ai_analysis && res.data.ai_analysis !== 'Đang tạo phân tích AI cho bạn... Vui lòng chờ trong giây lát và làm mới trang.') {
                    setAiStrategy(res.data.ai_analysis);
                }
            }
        } catch (e) {
            console.error('Error fetching goal:', e);
        } finally {
            setLoading(false);
        }
    };

    const fetchCurrentScores = async () => {
        try {
            const res = await axiosClient.get('/study/scores');
            const scores = res.data.scores || [];

            // Build current scores map by subject
            const scoresMap = {};
            scores.forEach(score => {
                const value = score.actual !== null && score.actual !== undefined
                    ? Number(score.actual)
                    : (score.predicted !== null && score.predicted !== undefined ? Number(score.predicted) : null);

                if (value !== null) {
                    if (!scoresMap[score.subject]) {
                        scoresMap[score.subject] = [];
                    }
                    scoresMap[score.subject].push(value);
                }
            });

            // Calculate average per subject
            const avgScores = {};
            Object.entries(scoresMap).forEach(([subject, values]) => {
                avgScores[subject] = values.reduce((a, b) => a + b, 0) / values.length;
            });

            setCurrentScores(avgScores);
        } catch (e) {
            console.error('Error fetching current scores:', e);
        }
    };

    const handleSubmit = async (e) => {
        e.preventDefault();
        setError(null);

        const score = parseFloat(targetScore);
        if (isNaN(score) || score < 0 || score > 10) {
            setError('Vui lòng nhập điểm từ 0.0 đến 10.0');
            return;
        }

        try {
            setSubmitting(true);
            const res = await axiosClient.post('/learning-goals/set-goal', {
                target_average: score
            });
            setCurrentGoal(res.data);
            // Clear old AI strategy when setting new goal
            setAiStrategy(null);
            // Clear from localStorage
            if (typeof window !== 'undefined' && window.localStorage && user?.username) {
                const storageKey = getAiStrategyStorageKey(user.username);
                window.localStorage.removeItem(storageKey);
            }
        } catch (e) {
            setError(e.response?.data?.detail || 'Đã xảy ra lỗi khi lưu mục tiêu');
        } finally {
            setSubmitting(false);
        }
    };

    const handleGenerateStrategy = async () => {
        if (!currentGoal) return;

        try {
            setGeneratingStrategy(true);
            const res = await axiosClient.post('/learning-goals/generate-strategy', {
                goal_id: currentGoal.id
            }, {
                timeout: 60000 // 60 seconds timeout for LLM
            });
            const newStrategy = res.data.ai_analysis;
            setAiStrategy(newStrategy);

            // Persist to localStorage
            if (typeof window !== 'undefined' && window.localStorage && user?.username) {
                try {
                    const storageKey = getAiStrategyStorageKey(user.username);
                    window.localStorage.setItem(storageKey, JSON.stringify({
                        version: AI_STRATEGY_VERSION,
                        goal_id: currentGoal.id,
                        strategy: newStrategy,
                        timestamp: new Date().toISOString()
                    }));
                } catch (storageErr) {
                    console.error('Failed to persist AI strategy', storageErr);
                }
            }
        } catch (e) {
            alert('Lỗi khi tạo chiến lược: ' + (e.response?.data?.detail || e.message));
        } finally {
            setGeneratingStrategy(false);
        }
    };

    // Prepare line chart data
    const prepareLineChartData = () => {
        if (!currentGoal || !currentGoal.trajectory_data) return [];

        const data = currentGoal.trajectory_data.map(point => ({
            term: point.term,
            label: formatTermLabel(point.term),
            current: point.current,
            goal: point.goal
        }));

        return data;
    };

    // Prepare bar chart data
    const prepareBarChartData = () => {
        if (!currentGoal || !currentGoal.predicted_scores) return [];

        const data = Object.entries(currentGoal.predicted_scores).map(([subject, predictedScore]) => ({
            subject: SUBJECT_LABELS[subject] || subject,
            subjectId: subject,
            current: currentScores[subject] || 0,
            predicted: predictedScore
        }));

        return data.sort((a, b) => b.predicted - a.predicted);
    };

    const lineChartData = prepareLineChartData();
    const barChartData = prepareBarChartData();

    if (loading) {
        return (
            <div style={{ padding: '2rem', textAlign: 'center' }}>
                <div>Đang tải...</div>
            </div>
        );
    }

    return (
        <div className="container" style={{ maxWidth: '1400px', paddingBottom: '3rem' }}>
            {/* Header */}
            <div style={{
                display: 'flex',
                alignItems: 'center',
                gap: '1rem',
                marginBottom: '2rem'
            }}>
            </div>

            {/* Goal Input Section */}
            <div className="card" style={{ padding: '2rem', marginBottom: '2rem' }}>
                <h3 style={{ marginBottom: '1.5rem', fontSize: '1.25rem', fontWeight: '600', color: 'var(--primary-color)', display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
                    <Award size={24} />
                    Đặt mục tiêu và xem lộ trình đạt được điểm mong muốn
                </h3>

                <form onSubmit={handleSubmit} style={{ display: 'flex', flexDirection: 'column', gap: '1.5rem' }}>
                    <div>
                        <label className="label" style={{ fontSize: '1rem', marginBottom: '0.75rem' }}>
                            Mục tiêu cho học kỳ sau của bạn là:
                        </label>
                        <div style={{ display: 'flex', gap: '1rem', alignItems: 'flex-start', flexWrap: 'wrap' }}>
                            <input
                                className="input-field"
                                type="number"
                                step="0.1"
                                min="0"
                                max="10"
                                value={targetScore}
                                onChange={(e) => setTargetScore(e.target.value)}
                                placeholder="0.0 đến 10.0"
                                style={{
                                    flex: '0 0 200px',
                                    fontSize: '1rem',
                                    borderColor: (() => {
                                        const hasChanges = currentGoal && targetScore && 
                                            parseFloat(targetScore) !== currentGoal.target_average;
                                        return hasChanges ? '#dc2626' : 'var(--border-color)';
                                    })(),
                                    borderWidth: (() => {
                                        const hasChanges = currentGoal && targetScore && 
                                            parseFloat(targetScore) !== currentGoal.target_average;
                                        return hasChanges ? '2px' : '1px';
                                    })(),
                                    backgroundColor: (() => {
                                        const hasChanges = currentGoal && targetScore && 
                                            parseFloat(targetScore) !== currentGoal.target_average;
                                        return hasChanges ? '#fef2f2' : 'transparent';
                                    })(),
                                    boxShadow: (() => {
                                        const hasChanges = currentGoal && targetScore && 
                                            parseFloat(targetScore) !== currentGoal.target_average;
                                        return hasChanges ? '0 0 0 3px rgba(220, 38, 38, 0.1)' : 'none';
                                    })()
                                }}
                            />
                            <button
                                type="submit"
                                disabled={submitting}
                                className="btn btn-primary"
                            >
                                {submitting ? 'Đang xử lý...' : 'Xác nhận mục tiêu'}
                            </button>
                            {currentGoal && (
                                <button
                                    type="button"
                                    disabled={generatingStrategy}
                                    onClick={handleGenerateStrategy}
                                    className="btn btn-outline"
                                    style={{
                                        display: 'flex',
                                        alignItems: 'center',
                                        gap: '0.5rem',
                                        borderColor: 'var(--primary-color)',
                                        color: 'var(--primary-color)'
                                    }}
                                >
                                    <Lightbulb size={18} />
                                    {generatingStrategy ? 'Đang tạo chiến lược...' : 'Đề xuất chiến lược'}
                                </button>
                            )}
                        </div>
                        {error && (
                            <div style={{ marginTop: '0.75rem', color: 'var(--danger-color)', fontSize: '0.9rem', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                                <Target size={16} /> {error}
                            </div>
                        )}
                    </div>

                    {currentGoal && (
                        <div style={{
                            padding: '1.25rem',
                            background: 'var(--bg-body)',
                            borderRadius: 'var(--radius-md)',
                            borderLeft: '4px solid var(--primary-color)',
                            display: 'flex',
                            alignItems: 'center',
                            gap: '1rem'
                        }}>
                            <Target size={24} style={{ color: 'var(--primary-color)' }} />
                            <div style={{ fontSize: '1rem', color: 'var(--text-secondary)' }}>
                                <strong>Mục tiêu hiện tại:</strong> <span style={{ color: 'var(--primary-color)', fontWeight: '700', fontSize: '1.1rem' }}>{currentGoal.target_average}</span> điểm cho
                                học kỳ {currentGoal.target_semester} lớp {currentGoal.target_grade_level}
                            </div>
                        </div>
                    )}
                </form>
            </div>

            {/* Charts and Analysis - Only show after goal is set */}
            {currentGoal && (
                <>
                    {/* Line Chart - Trajectory */}
                    <div className="card" style={{ padding: '2rem', marginBottom: '2rem' }}>
                        <h3 style={{ marginBottom: '1.5rem', fontSize: '1.25rem', fontWeight: '600', color: 'var(--text-primary)', display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
                            <TrendingUp size={24} style={{ color: 'var(--primary-color)' }} />
                            Xu hướng học tập
                        </h3>

                        <div style={{ height: '400px' }}>
                            <ResponsiveContainer width="100%" height="100%">
                                <LineChart data={lineChartData}>
                                    <CartesianGrid strokeDasharray="3 3" stroke="var(--border-color)" />
                                    <XAxis dataKey="label" stroke="var(--text-tertiary)" tick={{ fontSize: 12, fill: 'var(--text-secondary)' }} />
                                    <YAxis domain={[0, 10]} stroke="var(--text-tertiary)" tick={{ fontSize: 12, fill: 'var(--text-secondary)' }} />
                                    <Tooltip
                                        formatter={(value) => value !== null ? Number(value).toFixed(2) : '-'}
                                        contentStyle={{ borderRadius: 'var(--radius-md)', border: '1px solid var(--border-color)', boxShadow: 'var(--shadow-sm)' }}
                                    />
                                    {/* Legend removed - using custom legend below */}

                                    {/* Goal trend line (dashed) - render FIRST so it's below */}
                                    <Line
                                        type="monotone"
                                        dataKey="goal"
                                        name="Xu hướng để đạt mục tiêu"
                                        stroke="var(--success-color, #2ecc71)"
                                        strokeWidth={3}
                                        strokeDasharray="6 4"
                                        dot={{ r: 5, fill: 'var(--success-color, #2ecc71)' }}
                                        activeDot={{ r: 7 }}
                                        connectNulls
                                    >
                                        <LabelList dataKey="goal" content={renderLineLabel} />
                                    </Line>

                                    {/* Current trend line (solid) - render SECOND so it's on top */}
                                    <Line
                                        type="monotone"
                                        dataKey="current"
                                        name="Xu hướng hiện tại"
                                        stroke="var(--danger-color)"
                                        strokeWidth={3}
                                        dot={{ r: 5, fill: 'var(--danger-color)' }}
                                        activeDot={{ r: 7 }}
                                        connectNulls
                                    >
                                        <LabelList dataKey="current" content={renderLineLabel} />
                                    </Line>
                                </LineChart>
                            </ResponsiveContainer>
                        </div>

                        <div style={{ marginTop: '1.5rem', display: 'flex', gap: '2rem', justifyContent: 'center', fontSize: '0.9rem', color: 'var(--text-secondary)' }}>
                            <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                                <span style={{ width: '30px', height: '3px', background: 'var(--danger-color)', borderRadius: '2px' }} />
                                <span>Xu hướng hiện tại</span>
                            </div>
                            <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                                <span style={{ width: '30px', height: '3px', borderTop: '3px dashed var(--success-color, #2ecc71)' }} />
                                <span>Xu hướng để đạt mục tiêu</span>
                            </div>
                        </div>
                    </div>

                    {/* Bar Chart - Subject Comparison */}
                    <div className="card" style={{ padding: '2rem', marginBottom: '2rem' }}>
                        <h3 style={{ marginBottom: '1.5rem', fontSize: '1.25rem', fontWeight: '600', color: 'var(--text-primary)', display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
                            <Award size={24} style={{ color: 'var(--primary-color)' }} />
                            So sánh điểm hiện tại và dự đoán
                        </h3>

                        <div style={{ height: '500px' }}>
                            <ResponsiveContainer width="100%" height="100%">
                                <BarChart data={barChartData} layout="vertical" margin={{ left: 20, right: 40 }}>
                                    <CartesianGrid strokeDasharray="3 3" stroke="var(--border-color)" horizontal={false} />
                                    <XAxis type="number" domain={[0, 10]} tick={{ fontSize: 11, fill: 'var(--text-secondary)' }} stroke="var(--text-tertiary)" />
                                    <YAxis type="category" dataKey="subject" width={120} tick={{ fontSize: 12, fill: 'var(--text-primary)', fontWeight: 500 }} stroke="var(--text-tertiary)" />
                                    <Tooltip
                                        formatter={(value) => value !== null ? Number(value).toFixed(2) : '-'}
                                        contentStyle={{ borderRadius: 'var(--radius-md)', fontSize: '0.9rem', border: '1px solid var(--border-color)', boxShadow: 'var(--shadow-sm)' }}
                                        cursor={{ fill: 'var(--bg-body)' }}
                                    />
                                    <Legend wrapperStyle={{ paddingTop: '1.5rem' }} align="center" verticalAlign="bottom" iconType="circle" />

                                    <Bar dataKey="current" name="Điểm tương lai của bạn" fill="var(--danger-color)" radius={[0, 4, 4, 0]} barSize={18}>
                                        <LabelList dataKey="current" content={renderBarLabel} />
                                    </Bar>
                                    <Bar dataKey="predicted" name="Điểm để đạt mục tiêu" fill="var(--success-color, #2ecc71)" radius={[0, 4, 4, 0]} barSize={18}>
                                        <LabelList dataKey="predicted" content={renderBarLabel} />
                                    </Bar>
                                </BarChart>
                            </ResponsiveContainer>
                        </div>
                    </div>

                    {/* AI Strategy Analysis - Only show when explicitly generated */}
                    {aiStrategy && (
                        <div className="card" style={{
                            padding: '2rem',
                            background: 'linear-gradient(135deg, rgba(var(--primary-rgb), 0.05) 0%, rgba(var(--accent-rgb), 0.05) 100%)',
                            border: '1px solid var(--primary-light)',
                            position: 'relative',
                            overflow: 'hidden'
                        }}>
                            <div style={{
                                position: 'absolute',
                                top: 0,
                                left: 0,
                                width: '4px',
                                height: '100%',
                                background: 'var(--primary-color)'
                            }} />
                            <div style={{
                                display: 'flex',
                                alignItems: 'center',
                                gap: '1rem',
                                marginBottom: '1.5rem'
                            }}>
                                <div style={{
                                    width: '40px',
                                    height: '40px',
                                    borderRadius: '50%',
                                    background: 'var(--bg-surface)',
                                    display: 'flex',
                                    alignItems: 'center',
                                    justifyContent: 'center',
                                    boxShadow: 'var(--shadow-sm)'
                                }}>
                                    <Lightbulb size={24} style={{ color: 'var(--primary-color)' }} />
                                </div>
                                <h3 style={{ margin: 0, fontSize: '1.25rem', fontWeight: '700', color: 'var(--primary-color)' }}>
                                    Chiến lược học tập được đề xuất
                                </h3>
                            </div>

                            <div style={{
                                color: 'var(--text-primary)',
                                fontSize: '1rem',
                                lineHeight: 1.8,
                                whiteSpace: 'pre-wrap'
                            }}>
                                {aiStrategy}
                            </div>
                        </div>
                    )}
                </>
            )}
        </div>
    );
};

export default LearningGoals;

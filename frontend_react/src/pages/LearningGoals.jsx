import React, { useState, useEffect } from 'react';
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer, BarChart, Bar, Cell, LabelList } from 'recharts';
import axiosClient from '../api/axiosClient';
import { Target, TrendingUp, Award } from 'lucide-react';

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

const LearningGoals = () => {
    const [targetScore, setTargetScore] = useState('');
    const [currentGoal, setCurrentGoal] = useState(null);
    const [loading, setLoading] = useState(true);
    const [submitting, setSubmitting] = useState(false);
    const [error, setError] = useState(null);
    const [currentScores, setCurrentScores] = useState({});

    useEffect(() => {
        fetchCurrentGoal();
        fetchCurrentScores();
    }, []);

    const fetchCurrentGoal = async () => {
        try {
            setLoading(true);
            const res = await axiosClient.get('/learning-goals/current-goal');
            if (res.data.has_goal) {
                setCurrentGoal(res.data);
                setTargetScore(res.data.target_average.toString());
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
        } catch (e) {
            setError(e.response?.data?.detail || 'Đã xảy ra lỗi khi lưu mục tiêu');
        } finally {
            setSubmitting(false);
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
        <div style={{ maxWidth: '1400px', margin: '0 auto' }}>
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
                <h3 style={{ marginBottom: '1.5rem', fontSize: '1.2rem', fontWeight: '600', color: '#5a67d8' }}>
                    <Award size={20} style={{ display: 'inline', marginRight: '0.5rem', verticalAlign: 'middle' }} />
                    Đặt mục tiêu và xem lộ trình đạt được điểm mong muốn
                </h3>
                
                <form onSubmit={handleSubmit} style={{ display: 'flex', flexDirection: 'column', gap: '1.5rem' }}>
                    <div>
                        <label style={{ display: 'block', marginBottom: '0.5rem', fontWeight: '500', color: '#555' }}>
                            Mục tiêu cho học kỳ sau của bạn là:
                        </label>
                        <div style={{ display: 'flex', gap: '1rem', alignItems: 'flex-start' }}>
                            <input
                                type="number"
                                step="0.1"
                                min="0"
                                max="10"
                                value={targetScore}
                                onChange={(e) => setTargetScore(e.target.value)}
                                placeholder="Nhập điểm từ 0.0 đến 10.0"
                                style={{
                                    flex: '0 0 200px',
                                    padding: '0.75rem',
                                    fontSize: '1rem',
                                    border: '2px solid #e0e0e0',
                                    borderRadius: '8px',
                                    outline: 'none',
                                    transition: 'border-color 0.2s'
                                }}
                                onFocus={(e) => e.target.style.borderColor = '#5a67d8'}
                                onBlur={(e) => e.target.style.borderColor = '#e0e0e0'}
                            />
                            <button
                                type="submit"
                                disabled={submitting}
                                className="btn btn-primary"
                                style={{ padding: '0.75rem 1.5rem' }}
                            >
                                {submitting ? 'Đang xử lý...' : 'Xác nhận mục tiêu'}
                            </button>
                        </div>
                        {error && (
                            <div style={{ marginTop: '0.5rem', color: '#e74c3c', fontSize: '0.9rem' }}>
                                {error}
                            </div>
                        )}
                    </div>

                    {currentGoal && (
                        <div style={{
                            padding: '1rem',
                            background: '#f0f4ff',
                            borderRadius: '8px',
                            borderLeft: '4px solid #5a67d8'
                        }}>
                            <div style={{ fontSize: '0.9rem', color: '#555' }}>
                                <strong>Mục tiêu hiện tại:</strong> {currentGoal.target_average} điểm cho 
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
                        <h3 style={{ marginBottom: '1.5rem', fontSize: '1.2rem', fontWeight: '600', color: '#2c3e50' }}>

                            Xu hướng học tập
                        </h3>
                        
                        <div style={{ height: '400px' }}>
                            <ResponsiveContainer width="100%" height="100%">
                                <LineChart data={lineChartData}>
                                    <CartesianGrid strokeDasharray="3 3" stroke="#eee" />
                                    <XAxis dataKey="label" stroke="#888" tick={{ fontSize: 12 }} />
                                    <YAxis domain={[0, 10]} stroke="#888" tick={{ fontSize: 12 }} />
                                    <Tooltip 
                                        formatter={(value) => value !== null ? Number(value).toFixed(2) : '-'}
                                        contentStyle={{ borderRadius: '8px' }}
                                    />
                                    <Legend wrapperStyle={{ paddingTop: '1rem' }} />
                                    
                                    {/* Goal trend line (dashed) - render FIRST so it's below */}
                                    <Line
                                        type="monotone"
                                        dataKey="goal"
                                        name="Xu hướng để đạt mục tiêu"
                                        stroke="#2ecc71"
                                        strokeWidth={3}
                                        strokeDasharray="6 4"
                                        dot={{ r: 5 }}
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
                                        stroke="#d32f2f"
                                        strokeWidth={3}
                                        dot={{ r: 5 }}
                                        activeDot={{ r: 7 }}
                                        connectNulls
                                    >
                                        <LabelList dataKey="current" content={renderLineLabel} />
                                    </Line>
                                </LineChart>
                            </ResponsiveContainer>
                        </div>

                        <div style={{ marginTop: '1rem', display: 'flex', gap: '2rem', fontSize: '0.85rem', color: '#555' }}>
                            <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                                <span style={{ width: '30px', borderTop: '3px solid #d32f2f' }} />
                                <span>Xu hướng hiện tại</span>
                            </div>
                            <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                                <span style={{ width: '30px', borderTop: '3px dashed #2ecc71' }} />
                                <span>Xu hướng để đạt mục tiêu</span>
                            </div>
                        </div>
                    </div>

                    {/* Bar Chart - Subject Comparison */}
                    <div className="card" style={{ padding: '2rem', marginBottom: '2rem' }}>
                        <h3 style={{ marginBottom: '1.5rem', fontSize: '1.2rem', fontWeight: '600', color: '#2c3e50' }}>
                            So sánh điểm hiện tại và dự đoán
                        </h3>
                        
                        <div style={{ height: '400px' }}>
                            <ResponsiveContainer width="100%" height="100%">
                                <BarChart data={barChartData} layout="vertical">
                                    <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" horizontal={false} />
                                    <XAxis type="number" domain={[0, 10]} tick={{ fontSize: 11 }} />
                                    <YAxis type="category" dataKey="subject" width={100} tick={{ fontSize: 11 }} />
                                    <Tooltip 
                                        formatter={(value) => value !== null ? Number(value).toFixed(2) : '-'}
                                        contentStyle={{ borderRadius: '6px', fontSize: '0.85rem' }}
                                    />
                                    <Legend wrapperStyle={{ paddingTop: '1rem' }} />
                                    
                                    <Bar dataKey="current" name="Điểm hiện tại" fill="#d32f2f" radius={[0, 4, 4, 0]} barSize={20}>
                                        <LabelList dataKey="current" content={renderBarLabel} />
                                    </Bar>
                                    <Bar dataKey="predicted" name="Điểm để đạt mục tiêu" fill="#2ecc71" radius={[0, 4, 4, 0]} barSize={20}>
                                        <LabelList dataKey="predicted" content={renderBarLabel} />
                                    </Bar>
                                </BarChart>
                            </ResponsiveContainer>
                        </div>
                    </div>

                    {/* AI Analysis */}
                    {currentGoal.ai_analysis && (
                        <div className="card" style={{
                            padding: '2rem',
                            background: 'linear-gradient(135deg, #667eea15 0%, #764ba215 100%)',
                            border: '2px solid #e8eaf6',
                            borderRadius: '16px'
                        }}>
                            <div style={{
                                display: 'flex',
                                alignItems: 'center',
                                gap: '0.75rem',
                                marginBottom: '1.5rem'
                            }}>
                                
                                <h3 style={{ margin: 0, fontSize: '1.2rem', fontWeight: '700', color: '#5a67d8' }}>
                                    Phân tích & Chiến lược
                                </h3>
                            </div>
                            
                            <div style={{
                                color: '#34495e',
                                fontSize: '1rem',
                                lineHeight: 1.8,
                                whiteSpace: 'pre-wrap'
                            }}>
                                {currentGoal.ai_analysis}
                            </div>
                        </div>
                    )}
                </>
            )}
        </div>
    );
};

export default LearningGoals;

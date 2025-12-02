import React from 'react';
import { motion } from 'framer-motion';

const InstitutionDashboard = () => {
    return (
        <div style={{ padding: '2rem', maxWidth: '1400px', margin: '0 auto' }}>
            <motion.div
                initial={{ opacity: 0, y: 20 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ duration: 0.3 }}
            >
                <h1 style={{ fontSize: '2rem', fontWeight: '700', marginBottom: '1.5rem', color: 'var(--text-primary)' }}>
                    Tổng quan
                </h1>
                
                {/* Statistics Cards */}
                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(250px, 1fr))', gap: '1.5rem', marginBottom: '2rem' }}>
                    {[
                        { label: 'Tổng học sinh', value: '0', icon: '👥', color: '#3b82f6' },
                        { label: 'Lớp học', value: '0', icon: '🏫', color: '#10b981' },
                        { label: 'Giáo viên', value: '0', icon: '👨‍🏫', color: '#f59e0b' },
                        { label: 'Điểm trung bình', value: 'N/A', icon: '📊', color: '#8b5cf6' }
                    ].map((stat, idx) => (
                        <div
                            key={idx}
                            style={{
                                background: 'var(--bg-surface)',
                                padding: '1.5rem',
                                borderRadius: 'var(--radius-lg)',
                                boxShadow: '0 1px 3px rgba(0,0,0,0.1)',
                                border: '1px solid var(--border-color)'
                            }}
                        >
                            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '0.75rem' }}>
                                <span style={{ fontSize: '2rem' }}>{stat.icon}</span>
                                <div style={{
                                    width: '40px',
                                    height: '40px',
                                    borderRadius: '50%',
                                    background: `${stat.color}20`
                                }}></div>
                            </div>
                            <div style={{ fontSize: '0.9rem', color: 'var(--text-secondary)', marginBottom: '0.25rem' }}>
                                {stat.label}
                            </div>
                            <div style={{ fontSize: '2rem', fontWeight: '700', color: stat.color }}>
                                {stat.value}
                            </div>
                        </div>
                    ))}
                </div>

                {/* Welcome Message */}
                <div style={{
                    background: 'linear-gradient(135deg, #10b98120 0%, #05966920 100%)',
                    padding: '2rem',
                    borderRadius: 'var(--radius-lg)',
                    border: '1px solid #10b98140'
                }}>
                    <h3 style={{ fontSize: '1.5rem', fontWeight: '700', marginBottom: '1rem', color: '#059669' }}>
                        Chào mừng đến với EduTwin! 🎓
                    </h3>
                    <p style={{ fontSize: '1.05rem', color: 'var(--text-primary)', lineHeight: '1.6' }}>
                        Trang tổng quan sẽ được cập nhật sớm với các thống kê chi tiết về học sinh, biểu đồ phân tích kết quả học tập và báo cáo tự động.
                    </p>
                </div>
            </motion.div>
        </div>
    );
};

export default InstitutionDashboard;

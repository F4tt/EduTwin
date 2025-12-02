import React from 'react';
import { motion } from 'framer-motion';

const InstitutionStudents = () => {
    return (
        <div style={{ padding: '2rem', maxWidth: '1400px', margin: '0 auto' }}>
            <motion.div
                initial={{ opacity: 0, y: 20 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ duration: 0.3 }}
            >
                <h1 style={{ fontSize: '2rem', fontWeight: '700', marginBottom: '1.5rem', color: 'var(--text-primary)' }}>
                    Danh sách Học sinh
                </h1>
                
                <div style={{
                    background: 'var(--bg-surface)',
                    padding: '3rem',
                    borderRadius: 'var(--radius-lg)',
                    textAlign: 'center',
                    border: '2px dashed var(--border-color)'
                }}>
                    <div style={{ fontSize: '4rem', marginBottom: '1rem' }}>📚</div>
                    <h3 style={{ fontSize: '1.3rem', fontWeight: '600', marginBottom: '0.5rem', color: 'var(--text-primary)' }}>
                        Chức năng đang được phát triển
                    </h3>
                    <p style={{ fontSize: '1rem', color: 'var(--text-secondary)' }}>
                        Trang quản lý học sinh sẽ sớm có các tính năng: thêm/sửa/xóa học sinh, phân lớp, theo dõi kết quả học tập.
                    </p>
                </div>
            </motion.div>
        </div>
    );
};

export default InstitutionStudents;

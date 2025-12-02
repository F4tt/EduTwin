import React from 'react';
import { useAuth } from '../context/AuthContext';
import { motion } from 'framer-motion';

const InstitutionSettings = () => {
    const { user } = useAuth();

    return (
        <div style={{ padding: '2rem', maxWidth: '1400px', margin: '0 auto' }}>
            <motion.div
                initial={{ opacity: 0, y: 20 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ duration: 0.3 }}
            >
                <h1 style={{ fontSize: '2rem', fontWeight: '700', marginBottom: '1.5rem', color: 'var(--text-primary)' }}>
                    Cài đặt
                </h1>
                
                <div style={{ background: 'var(--bg-surface)', padding: '2rem', borderRadius: 'var(--radius-lg)', border: '1px solid var(--border-color)' }}>
                    <h3 style={{ fontSize: '1.3rem', fontWeight: '600', marginBottom: '1.5rem', color: 'var(--text-primary)' }}>
                        Thông tin cơ sở giáo dục
                    </h3>
                    <div style={{ display: 'grid', gap: '1rem' }}>
                        <InfoRow label="Tên cơ sở" value={user?.institution_name || 'N/A'} />
                        <InfoRow label="Loại hình" value={
                            user?.institution_type === 'high_school' ? 'Trường THPT' :
                            user?.institution_type === 'university' ? 'Đại học' :
                            user?.institution_type === 'training_center' ? 'Trung tâm đào tạo' : 
                            user?.institution_type || 'Khác'
                        } />
                        <InfoRow label="Tên đăng nhập" value={user?.username || 'N/A'} />
                        <InfoRow label="Email" value={user?.email || 'Chưa cập nhật'} />
                        <InfoRow label="Số điện thoại" value={user?.phone || 'Chưa cập nhật'} />
                        <InfoRow label="Địa chỉ" value={user?.address || 'Chưa cập nhật'} />
                        <InfoRow label="Người liên hệ" value={user?.contact_person || 'Chưa cập nhật'} />
                    </div>
                </div>

                <div style={{ marginTop: '2rem', padding: '1.5rem', background: '#f0f9ff', borderRadius: 'var(--radius-lg)', border: '1px solid #bfdbfe' }}>
                    <p style={{ fontSize: '0.95rem', color: '#1e40af', margin: 0 }}>
                        💡 <strong>Lưu ý:</strong> Để cập nhật thông tin cơ sở giáo dục, vui lòng liên hệ quản trị viên hệ thống.
                    </p>
                </div>
            </motion.div>
        </div>
    );
};

const InfoRow = ({ label, value }) => (
    <div style={{ display: 'flex', padding: '1rem', background: 'var(--bg-body)', borderRadius: 'var(--radius-md)' }}>
        <div style={{ flex: '0 0 200px', fontWeight: '600', color: 'var(--text-secondary)' }}>{label}:</div>
        <div style={{ flex: 1, color: 'var(--text-primary)' }}>{value}</div>
    </div>
);

export default InstitutionSettings;

import React from 'react';
import { NavLink, Outlet, useNavigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { MessageSquare, BarChart2, BookOpen, Settings, LogOut, Wrench, Target } from 'lucide-react';

const Layout = () => {
    const { user, logout } = useAuth();
    const navigate = useNavigate();

    const handleLogout = () => {
        logout();
        navigate('/login');
    };

    const navItems = [
        { path: '/chat', icon: <MessageSquare size={20} />, label: 'Trò chuyện' },
        { path: '/data', icon: <BarChart2 size={20} />, label: 'Phân tích' },
        { path: '/goals', icon: <Target size={20} />, label: 'Mục tiêu' },
        { path: '/study', icon: <BookOpen size={20} />, label: 'Điểm số' },
        { path: '/settings', icon: <Settings size={20} />, label: 'Cài đặt' },
    ];

    // Add Developer Tools for privileged users
    const isDeveloper = user?.role === 'developer' || user?.role === 'admin';
    if (isDeveloper) {
        navItems.push({ path: '/developer', icon: <Wrench size={20} />, label: 'Quản lý hệ thống' });
    }

    return (
        <div style={{ display: 'flex', height: '100vh', background: '#f8f9fa' }}>
            {/* Sidebar */}
            <aside style={{
                width: '260px',
                background: '#ffffff',
                borderRight: '1px solid #e0e0e0',
                display: 'flex',
                flexDirection: 'column',
                padding: '1.5rem'
            }}>
                <div style={{ marginBottom: '2rem', display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
                    <div style={{
                        width: '40px', height: '40px', background: '#d32f2f', borderRadius: '8px',
                        display: 'flex', alignItems: 'center', justifyContent: 'center', color: 'white', fontWeight: 'bold', fontSize: '1.2rem'
                    }}>
                        E
                    </div>
                    <span style={{ fontSize: '1.25rem', fontWeight: '700', color: '#2c3e50' }}>EduTwin</span>
                </div>

                <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem', flex: 1 }}>
                    {navItems.map((item) => (
                        <NavLink
                            key={item.path}
                            to={item.path}
                            style={({ isActive }) => ({
                                display: 'flex',
                                alignItems: 'center',
                                gap: '0.75rem',
                                padding: '0.75rem 1rem',
                                borderRadius: '8px',
                                textDecoration: 'none',
                                color: isActive ? '#d32f2f' : '#636e72',
                                background: isActive ? '#fee2e2' : 'transparent',
                                fontWeight: isActive ? '600' : '500',
                                transition: 'all 0.2s'
                            })}
                        >
                            {item.icon}
                            {item.label}
                        </NavLink>
                    ))}
                </div>

                <div style={{ borderTop: '1px solid #eee', paddingTop: '1rem' }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem', marginBottom: '1rem' }}>
                        <div style={{ width: '32px', height: '32px', borderRadius: '50%', background: '#eee', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                            👤
                        </div>
                        <div style={{ overflow: 'hidden' }}>
                            <div style={{ fontSize: '0.9rem', fontWeight: '600', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
                                {user?.name || user?.username}
                            </div>
                            <div style={{ fontSize: '0.75rem', color: '#888' }}>Học sinh</div>
                        </div>
                    </div>
                    <button
                        onClick={handleLogout}
                        style={{
                            width: '100%',
                            display: 'flex',
                            alignItems: 'center',
                            gap: '0.5rem',
                            padding: '0.5rem',
                            color: '#d32f2f',
                            background: 'transparent',
                            border: 'none',
                            fontSize: '0.9rem',
                            cursor: 'pointer'
                        }}
                    >
                        <LogOut size={16} /> Đăng xuất
                    </button>
                </div>
            </aside>

            {/* Main Content */}
            <main style={{ flex: 1, overflowY: 'auto', padding: '2rem' }}>
                <Outlet />
            </main>
        </div>
    );
};

export default Layout;

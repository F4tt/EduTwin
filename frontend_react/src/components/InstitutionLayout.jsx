import React from 'react';
import { NavLink, Outlet, useNavigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { LayoutDashboard, Users, Wrench, Settings, LogOut } from 'lucide-react';

const InstitutionLayout = () => {
    const { user, logout } = useAuth();
    const navigate = useNavigate();

    const handleLogout = () => {
        logout();
        navigate('/login/institution');
    };

    const navItems = [
        { path: '/institution/dashboard', icon: <LayoutDashboard size={20} />, label: 'Tổng quan' },
        { path: '/institution/students', icon: <Users size={20} />, label: 'Danh sách học sinh' },
        { path: '/institution/admin-tools', icon: <Wrench size={20} />, label: 'Công cụ quản trị' },
        { path: '/institution/settings', icon: <Settings size={20} />, label: 'Cài đặt' },
    ];

    return (
        <div style={{ display: 'flex', height: '100vh', background: 'var(--bg-background)' }}>
            {/* Sidebar */}
            <aside style={{
                width: '280px',
                background: 'var(--bg-surface)',
                borderRight: '1px solid var(--border-color)',
                display: 'flex',
                flexDirection: 'column',
                padding: '1.5rem',
                zIndex: 10
            }}>
                <div style={{ marginBottom: '2.5rem', display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
                    <div style={{
                        width: '40px', height: '40px', background: '#10b981', borderRadius: '12px',
                        display: 'flex', alignItems: 'center', justifyContent: 'center', color: 'white', fontWeight: 'bold', fontSize: '1.2rem',
                        boxShadow: 'var(--shadow-md)'
                    }}>
                        E
                    </div>
                    <span style={{ fontSize: '1.25rem', fontWeight: '700', color: 'var(--text-primary)', letterSpacing: '-0.5px' }}>EduTwin</span>
                </div>

                <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem', flex: 1 }}>
                    {navItems.map((item) => (
                        <NavLink
                            key={item.path}
                            to={item.path}
                            className={({ isActive }) =>
                                `btn ${isActive ? 'btn-primary' : 'btn-ghost'}`
                            }
                            style={({ isActive }) => ({
                                justifyContent: 'flex-start',
                                width: '100%',
                                padding: '0.75rem 1rem',
                                fontSize: '0.95rem',
                                background: isActive ? '#10b981' : 'transparent',
                                color: isActive ? 'white' : 'var(--text-primary)'
                            })}
                        >
                            {item.icon}
                            {item.label}
                        </NavLink>
                    ))}
                </div>

                <div style={{ borderTop: '1px solid var(--border-color)', paddingTop: '1.5rem' }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem', marginBottom: '1rem', padding: '0.5rem', borderRadius: 'var(--radius-md)', background: '#10b98110' }}>
                        <div style={{
                            width: '36px', height: '36px', borderRadius: '50%', background: 'white',
                            display: 'flex', alignItems: 'center', justifyContent: 'center',
                            color: 'var(--text-secondary)', border: '1px solid var(--border-color)',
                            boxShadow: 'var(--shadow-sm)'
                        }}>
                            🏫
                        </div>
                        <div style={{ overflow: 'hidden', flex: 1 }}>
                            <div style={{ fontSize: '0.9rem', fontWeight: '600', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis', color: 'var(--text-primary)' }}>
                                {user?.institution_name || user?.username}
                            </div>
                            <div style={{ fontSize: '0.75rem', color: 'var(--text-tertiary)' }}>Cơ sở giáo dục</div>
                        </div>
                    </div>
                    <button
                        onClick={handleLogout}
                        className="btn btn-outline"
                        style={{
                            width: '100%',
                            borderColor: 'var(--danger-color)',
                            color: 'var(--danger-color)',
                            justifyContent: 'center'
                        }}
                    >
                        <LogOut size={18} />
                        Đăng xuất
                    </button>
                </div>
            </aside>

            {/* Main Content */}
            <main style={{ flex: 1, overflow: 'auto', background: 'var(--bg-body)' }}>
                <Outlet />
            </main>
        </div>
    );
};

export default InstitutionLayout;

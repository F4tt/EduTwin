import React from 'react';
import { NavLink, Outlet, useNavigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { MessageSquare, BarChart2, BookOpen, Settings, LogOut, Wrench } from 'lucide-react';
import { useIsMobile } from '../hooks/useIsMobile';

const Layout = () => {
    const { user, logout } = useAuth();
    const navigate = useNavigate();
    const isMobile = useIsMobile();

    const handleLogout = async () => {
        await logout();
        navigate('/login');
    };

    const navItems = [
        { path: '/chat', icon: <MessageSquare size={20} />, label: 'Trò chuyện', shortLabel: 'Chat' },
        { path: '/data', icon: <BarChart2 size={20} />, label: 'Phân tích', shortLabel: 'Phân tích' },
        { path: '/study', icon: <BookOpen size={20} />, label: 'Điểm số', shortLabel: 'Điểm' },
        { path: '/settings', icon: <Settings size={20} />, label: 'Cài đặt', shortLabel: 'Cài đặt' },
    ];

    // Add Developer Tools for privileged users
    const isDeveloper = user?.role === 'developer' || user?.role === 'admin';
    if (isDeveloper) {
        navItems.push({ path: '/developer', icon: <Wrench size={20} />, label: 'Quản lý hệ thống', shortLabel: 'Admin' });
    }

    // Mobile Layout
    if (isMobile) {
        return (
            <div style={{ display: 'flex', flexDirection: 'column', height: '100vh', background: 'var(--bg-body)' }}>
                {/* Mobile Header */}
                <header style={{
                    height: '56px',
                    background: 'var(--bg-surface)',
                    borderBottom: '1px solid var(--border-color)',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'space-between',
                    padding: '0 1rem',
                    position: 'sticky',
                    top: 0,
                    zIndex: 100
                }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                        <div style={{
                            width: '32px', height: '32px', background: 'var(--primary-color)', borderRadius: '8px',
                            display: 'flex', alignItems: 'center', justifyContent: 'center', color: 'white', fontWeight: 'bold', fontSize: '1rem'
                        }}>
                            E
                        </div>
                        <span style={{ fontSize: '1.1rem', fontWeight: '700', color: 'var(--text-primary)' }}>EduTwin</span>
                    </div>
                    <div id="header-portal" style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}></div>
                </header>

                {/* Main Content */}
                <main style={{ flex: 1, overflowY: 'auto', paddingBottom: '72px' }}>
                    <div style={{ padding: '1rem' }}>
                        <Outlet />
                    </div>
                </main>

                {/* Mobile Bottom Navigation */}
                <nav style={{
                    position: 'fixed',
                    bottom: 0,
                    left: 0,
                    right: 0,
                    height: '64px',
                    background: 'var(--bg-surface)',
                    borderTop: '1px solid var(--border-color)',
                    display: 'flex',
                    justifyContent: 'space-around',
                    alignItems: 'center',
                    zIndex: 1000,
                    paddingBottom: 'env(safe-area-inset-bottom, 0px)'
                }}>
                    {navItems.map((item) => (
                        <NavLink
                            key={item.path}
                            to={item.path}
                            style={({ isActive }) => ({
                                display: 'flex',
                                flexDirection: 'column',
                                alignItems: 'center',
                                gap: '2px',
                                padding: '8px 12px',
                                borderRadius: '8px',
                                color: isActive ? 'var(--primary-color)' : 'var(--text-secondary)',
                                textDecoration: 'none',
                                fontSize: '0.7rem',
                                fontWeight: isActive ? '600' : '500',
                                transition: 'all 0.2s',
                                minWidth: '56px'
                            })}
                        >
                            {React.cloneElement(item.icon, { size: 22 })}
                            <span>{item.shortLabel}</span>
                        </NavLink>
                    ))}
                </nav>
            </div>
        );
    }

    // Desktop Layout (existing)
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
                        width: '40px', height: '40px', background: 'var(--primary-color)', borderRadius: '12px',
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
                            style={{
                                justifyContent: 'flex-start',
                                width: '100%',
                                padding: '0.75rem 1rem',
                                fontSize: '0.95rem'
                            }}
                        >
                            {item.icon}
                            {item.label}
                        </NavLink>
                    ))}
                </div>

                <div style={{ borderTop: '1px solid var(--border-color)', paddingTop: '1.5rem' }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem', marginBottom: '1rem', padding: '0.5rem', borderRadius: 'var(--radius-md)', background: 'var(--secondary-light)' }}>
                        <div style={{
                            width: '36px', height: '36px', borderRadius: '50%', background: 'white',
                            display: 'flex', alignItems: 'center', justifyContent: 'center',
                            color: 'var(--text-secondary)', border: '1px solid var(--border-color)',
                            boxShadow: 'var(--shadow-sm)'
                        }}>
                            👤
                        </div>
                        <div style={{ overflow: 'hidden', flex: 1 }}>
                            <div style={{ fontSize: '0.9rem', fontWeight: '600', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis', color: 'var(--text-primary)' }}>
                                {user?.last_name && user?.first_name
                                    ? `${user.last_name} ${user.first_name}`
                                    : user?.name || user?.username}
                            </div>
                            <div style={{ fontSize: '0.75rem', color: 'var(--text-tertiary)' }}>Học sinh</div>
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
                        onMouseEnter={(e) => {
                            e.currentTarget.style.background = '#fef2f2';
                        }}
                        onMouseLeave={(e) => {
                            e.currentTarget.style.background = 'transparent';
                        }}
                    >
                        <LogOut size={18} /> Đăng xuất
                    </button>
                </div>
            </aside>

            {/* Main Content */}
            <main style={{ flex: 1, overflowY: 'auto', position: 'relative', background: 'var(--bg-body)' }}>
                {/* Top bar */}
                <div style={{
                    position: 'sticky',
                    top: 0,
                    zIndex: 100,
                    background: 'var(--bg-body)',
                    borderBottom: '1px solid var(--border-color)',
                    padding: '0.5rem 2rem',
                    height: '80px',
                    display: 'flex',
                    justifyContent: 'center',
                    alignItems: 'center',
                    boxSizing: 'border-box'
                }}>
                    <div id="header-portal" style={{ flex: 1, display: 'flex', alignItems: 'center', justifyContent: 'center', height: '100%' }}></div>
                </div>

                <div style={{ padding: '2rem' }}>
                    <Outlet />
                </div>
            </main>
        </div>
    );
};

export default Layout;

import React, { useEffect, useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { User, TrendingUp, Zap } from 'lucide-react';

// Custom Modern Robot Icon - Cute floating robot with visor (inspired by reference image)
const RobotIcon = ({ size = 14, color = "white" }) => (
    <svg
        width={size}
        height={size}
        viewBox="0 0 24 24"
        fill="none"
        style={{ display: 'block' }}
    >
        {/* Head/Body - egg shape, no antenna */}
        <ellipse cx="12" cy="11" rx="8" ry="9" fill={color} />

        {/* Visor/Face screen - dark rounded area */}
        <rect x="5.5" y="6" width="13" height="8" rx="4" fill="#2d3748" />

        {/* Left eye - green LED */}
        <circle cx="8.5" cy="10" r="1.8" fill="#48bb78" />
        <circle cx="8" cy="9.5" r="0.6" fill="white" opacity="0.9" />

        {/* Right eye - green LED */}
        <circle cx="15.5" cy="10" r="1.8" fill="#48bb78" />
        <circle cx="15" cy="9.5" r="0.6" fill="white" opacity="0.9" />

        {/* Heart/core on chest - orange */}
        <circle cx="12" cy="17" r="1.5" fill="#f6ad55" />

        {/* Floating shadow */}
        <ellipse cx="12" cy="22" rx="4" ry="1" fill={color} opacity="0.4" />
    </svg>
);

// Circular Progress Ring Component
const CircularProgress = ({ percent, size = 50, strokeWidth = 4, color = "#7C3AED" }) => {
    const radius = (size - strokeWidth) / 2;
    const circumference = 2 * Math.PI * radius;
    const offset = circumference - (percent / 100) * circumference;

    return (
        <svg width={size} height={size} style={{ transform: 'rotate(-90deg)' }}>
            {/* Background Circle */}
            <circle
                cx={size / 2}
                cy={size / 2}
                r={radius}
                fill="none"
                stroke="#F3E8FF"
                strokeWidth={strokeWidth}
            />
            {/* Progress Circle */}
            <motion.circle
                cx={size / 2}
                cy={size / 2}
                r={radius}
                fill="none"
                stroke={color}
                strokeWidth={strokeWidth}
                strokeDasharray={circumference}
                strokeDashoffset={offset}
                strokeLinecap="round"
                initial={{ strokeDashoffset: circumference }}
                animate={{ strokeDashoffset: offset }}
                transition={{ duration: 1, ease: "easeOut" }}
                style={{
                    filter: 'drop-shadow(0 0 4px rgba(124, 58, 237, 0.4))'
                }}
            />
        </svg>
    );
};

// Particle Effect Component
const DataParticle = ({ delay = 0 }) => (
    <motion.div
        initial={{ opacity: 0, scale: 0, x: 0, y: 0 }}
        animate={{
            opacity: [0, 1, 0],
            scale: [0, 1, 0],
            x: [0, (Math.random() - 0.5) * 30],
            y: [0, -20 - Math.random() * 20]
        }}
        transition={{
            duration: 2,
            delay,
            repeat: Infinity,
            repeatDelay: 1
        }}
        style={{
            position: 'absolute',
            width: '3px',
            height: '3px',
            borderRadius: '50%',
            background: `hsl(${Math.random() * 60 + 200}, 70%, 60%)`,
            left: '50%',
            top: '50%'
        }}
    />
);

// Modern User Card
const ModernUserCard = ({ isAnimating }) => (
    <motion.div
        animate={isAnimating ? { scale: [1, 1.05, 1] } : {}}
        transition={{ duration: 1.5, ease: "easeInOut" }}
        style={{
            position: 'relative',
            padding: '8px 16px',
            borderRadius: '12px',
            background: 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)',
            boxShadow: '0 4px 12px rgba(102, 126, 234, 0.3)',
            display: 'flex',
            alignItems: 'center',
            gap: '10px',
            minWidth: '120px',
            height: '50px',
            overflow: 'hidden'
        }}
    >
        {/* Animated Background Gradient */}
        <motion.div
            animate={{
                background: [
                    'radial-gradient(circle at 20% 50%, rgba(255,255,255,0.1) 0%, transparent 50%)',
                    'radial-gradient(circle at 80% 50%, rgba(255,255,255,0.1) 0%, transparent 50%)',
                    'radial-gradient(circle at 20% 50%, rgba(255,255,255,0.1) 0%, transparent 50%)'
                ]
            }}
            transition={{ duration: 3, repeat: Infinity, ease: "linear" }}
            style={{
                position: 'absolute',
                inset: 0,
                pointerEvents: 'none'
            }}
        />

        {/* Avatar with Glow */}
        <div style={{ position: 'relative', zIndex: 1 }}>
            {isAnimating && (
                <motion.div
                    animate={{ scale: [1, 1.4, 1], opacity: [0.5, 0, 0.5] }}
                    transition={{ duration: 1.5, repeat: Infinity }}
                    style={{
                        position: 'absolute',
                        inset: -4,
                        borderRadius: '50%',
                        background: 'radial-gradient(circle, rgba(255,255,255,0.6) 0%, transparent 70%)',
                        zIndex: 0
                    }}
                />
            )}
            <div style={{
                position: 'relative',
                width: '32px',
                height: '32px',
                borderRadius: '50%',
                background: 'white',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                boxShadow: '0 2px 8px rgba(0,0,0,0.15)',
                zIndex: 1
            }}>
                <User size={18} color="#667eea" strokeWidth={2.5} />
                {/* Status Badge */}
                <div style={{
                    position: 'absolute',
                    bottom: -1,
                    right: -1,
                    width: '10px',
                    height: '10px',
                    borderRadius: '50%',
                    background: '#10B981',
                    border: '2px solid white',
                    boxShadow: '0 1px 4px rgba(16, 185, 129, 0.4)'
                }} />
            </div>
        </div>

        {/* User Info */}
        <div style={{ zIndex: 1 }}>
            <div style={{ fontSize: '13px', fontWeight: '700', color: 'white', letterSpacing: '0.3px', lineHeight: 1 }}>BẠN</div>
            <div style={{ fontSize: '10px', color: 'rgba(255,255,255,0.8)', marginTop: '2px' }}>Học sinh</div>
        </div>

        {/* Particles when animating */}
        {isAnimating && (
            <>
                {[...Array(3)].map((_, i) => (
                    <DataParticle key={i} delay={i * 0.2} />
                ))}
            </>
        )}
    </motion.div>
);

// Modern Twin Card with Progress Ring
const ModernTwinCard = ({ percent, isAnimating, showConfetti }) => (
    <motion.div
        animate={isAnimating ? { scale: [1, 1.05, 1] } : {}}
        transition={{ duration: 1.5, ease: "easeInOut" }}
        style={{
            position: 'relative',
            padding: '8px 16px',
            borderRadius: '12px',
            background: 'linear-gradient(135deg, #f093fb 0%, #f5576c 100%)',
            boxShadow: '0 4px 12px rgba(240, 147, 251, 0.3)',
            display: 'flex',
            alignItems: 'center',
            gap: '10px',
            minWidth: '130px',
            height: '50px',
            overflow: 'hidden'
        }}
    >
        {/* Animated Background */}
        <motion.div
            animate={{
                background: [
                    'radial-gradient(circle at 80% 50%, rgba(255,255,255,0.15) 0%, transparent 50%)',
                    'radial-gradient(circle at 20% 50%, rgba(255,255,255,0.15) 0%, transparent 50%)',
                    'radial-gradient(circle at 80% 50%, rgba(255,255,255,0.15) 0%, transparent 50%)'
                ]
            }}
            transition={{ duration: 3, repeat: Infinity, ease: "linear" }}
            style={{
                position: 'absolute',
                inset: 0,
                pointerEvents: 'none'
            }}
        />

        {/* Progress Ring with Robot Icon */}
        <div style={{ position: 'relative', zIndex: 1, display: 'flex', alignItems: 'center' }}>
            <div style={{ position: 'relative', width: '36px', height: '36px' }}>
                <CircularProgress percent={percent} size={36} strokeWidth={3} color="white" />
                <div style={{
                    position: 'absolute',
                    top: '50%',
                    left: '50%',
                    transform: 'translate(-50%, -50%)',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center'
                }}>
                    <RobotIcon size={16} color="white" />
                </div>
            </div>

            {/* Confetti Burst */}
            <AnimatePresence>
                {showConfetti && (
                    <>
                        {[...Array(12)].map((_, i) => (
                            <motion.div
                                key={i}
                                initial={{ opacity: 1, scale: 0, x: 0, y: 0, rotate: 0 }}
                                animate={{
                                    opacity: 0,
                                    scale: [0, 1, 0.5],
                                    x: (Math.random() - 0.5) * 80,
                                    y: (Math.random() - 0.5) * 80,
                                    rotate: Math.random() * 360
                                }}
                                transition={{ duration: 1.5, ease: "easeOut" }}
                                style={{
                                    position: 'absolute',
                                    top: '50%',
                                    left: '50%',
                                    width: '4px',
                                    height: '4px',
                                    borderRadius: Math.random() > 0.5 ? '50%' : '2px',
                                    background: ['#FFD700', '#FF69B4', '#00CED1', '#FF6347', '#7FFF00'][i % 5],
                                    zIndex: 40
                                }}
                            />
                        ))}
                    </>
                )}
            </AnimatePresence>
        </div>

        {/* Twin Info */}
        <div style={{ zIndex: 1 }}>
            <div style={{ fontSize: '13px', fontWeight: '700', color: 'white', letterSpacing: '0.3px', lineHeight: 1 }}>TWIN</div>
            <div style={{
                fontSize: '10px',
                color: 'rgba(255,255,255,0.9)',
                marginTop: '2px',
                display: 'flex',
                alignItems: 'center',
                gap: '4px'
            }}>
                <TrendingUp size={10} />
                {percent}%
            </div>
        </div>
    </motion.div>
);

// Data Transfer Animation
const DataTransferAnimation = ({ isAnimating }) => (
    <div style={{
        flex: 1,
        position: 'relative',
        height: '40px',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        maxWidth: '150px'
    }}>
        {/* Connection Line */}
        <svg width="100%" height="100%" style={{ position: 'absolute', top: 0, left: 0 }}>
            <defs>
                <linearGradient id="line-gradient" x1="0%" y1="0%" x2="100%" y2="0%">
                    <stop offset="0%" stopColor="#667eea" />
                    <stop offset="100%" stopColor="#f093fb" />
                </linearGradient>
            </defs>
            <motion.line
                x1="0"
                y1="20"
                x2="100%"
                y2="20"
                stroke="url(#line-gradient)"
                strokeWidth={isAnimating ? "2" : "1"}
                strokeDasharray="4 2"
                initial={{ pathLength: 0, opacity: 0.3 }}
                animate={{
                    pathLength: 1,
                    opacity: isAnimating ? 1 : 0.3
                }}
                transition={{ duration: 1 }}
            />
        </svg>

        {/* Data Packets */}
        {isAnimating && (
            <>
                {[...Array(3)].map((_, i) => (
                    <motion.div
                        key={i}
                        initial={{ left: '0%', opacity: 0 }}
                        animate={{
                            left: '100%',
                            opacity: [0, 1, 1, 0]
                        }}
                        transition={{
                            duration: 1.5,
                            delay: i * 0.3,
                            ease: "easeInOut"
                        }}
                        style={{
                            position: 'absolute',
                            top: '50%',
                            transform: 'translateY(-50%)',
                            width: '8px',
                            height: '8px',
                            borderRadius: '2px',
                            background: 'linear-gradient(135deg, #667eea, #f093fb)',
                            boxShadow: '0 0 8px rgba(102, 126, 234, 0.6)',
                            zIndex: 10
                        }}
                    />
                ))}
            </>
        )}

        {/* Status Text */}
        <AnimatePresence mode="wait">
            {isAnimating && (
                <motion.div
                    initial={{ opacity: 0, scale: 0.8 }}
                    animate={{ opacity: 1, scale: 1 }}
                    exit={{ opacity: 0, scale: 0.8 }}
                    style={{
                        position: 'absolute',
                        top: '-15px',
                        left: '50%',
                        transform: 'translateX(-50%)',
                        display: 'flex',
                        alignItems: 'center',
                        gap: '4px',
                        padding: '2px 8px',
                        borderRadius: '10px',
                        background: 'rgba(255, 255, 255, 0.9)',
                        boxShadow: '0 2px 6px rgba(0,0,0,0.05)',
                        backdropFilter: 'blur(4px)',
                        zIndex: 20,
                        whiteSpace: 'nowrap'
                    }}
                >
                    <motion.div
                        animate={{ rotate: 360 }}
                        transition={{ duration: 1, repeat: Infinity, ease: "linear" }}
                    >
                        <Zap size={10} color="#667eea" />
                    </motion.div>
                    <span style={{
                        fontSize: '9px',
                        fontWeight: '600',
                        background: 'linear-gradient(135deg, #667eea, #f093fb)',
                        WebkitBackgroundClip: 'text',
                        WebkitTextFillColor: 'transparent',
                        letterSpacing: '0.3px'
                    }}>
                        Đang học...
                    </span>
                </motion.div>
            )}
        </AnimatePresence>
    </div>
);

// Main Component
const PreferenceVisualizer = ({ preferenceCount = 0, maxPreferences = 30 }) => {
    const [displayCount, setDisplayCount] = useState(preferenceCount);
    const [isAnimating, setIsAnimating] = useState(false);
    const [showConfetti, setShowConfetti] = useState(false);

    useEffect(() => {
        if (preferenceCount > displayCount) {
            setIsAnimating(true);
            const timer = setTimeout(() => {
                setDisplayCount(preferenceCount);
                setIsAnimating(false);
                if ([5, 10, 20, 30].includes(preferenceCount)) {
                    setShowConfetti(true);
                    setTimeout(() => setShowConfetti(false), 2500);
                }
            }, 1500);
            return () => clearTimeout(timer);
        } else {
            setDisplayCount(preferenceCount);
        }
    }, [preferenceCount, displayCount]);

    const rawPercent = (displayCount / maxPreferences) * 100;
    const percent = displayCount >= maxPreferences ? 100 : Math.round(rawPercent);

    return (
        <div style={{
            position: 'relative',
            padding: '0 10px',
            height: '100%',
            width: '100%',
            maxWidth: '600px',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            gap: '20px',
            fontFamily: "'Inter', -apple-system, BlinkMacSystemFont, sans-serif"
        }}>
            <ModernUserCard isAnimating={isAnimating} />
            <DataTransferAnimation isAnimating={isAnimating} />
            <ModernTwinCard percent={percent} isAnimating={isAnimating} showConfetti={showConfetti} />
        </div>
    );
};

export default PreferenceVisualizer;

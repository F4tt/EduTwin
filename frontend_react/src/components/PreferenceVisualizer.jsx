import React, { useEffect, useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { User, Brain, Sparkles, Zap } from 'lucide-react';

// --- Components ---

const GlassUser = ({ isAnimating }) => (
    <div style={{ position: 'relative', width: '56px', height: '56px' }}>
        {/* Outer Glow Ring */}
        {isAnimating && (
            <motion.div
                initial={{ scale: 1, opacity: 0.6 }}
                animate={{ scale: 1.3, opacity: 0 }}
                transition={{ duration: 2, repeat: Infinity }}
                style={{
                    position: 'absolute',
                    inset: 0,
                    borderRadius: '50%',
                    border: '2px solid #3B82F6',
                    zIndex: 0
                }}
            />
        )}

        {/* Avatar Circle */}
        <div style={{
            position: 'relative',
            width: '100%',
            height: '100%',
            borderRadius: '50%',
            background: 'linear-gradient(145deg, #ffffff, #e6e6e6)',
            boxShadow: '5px 5px 10px #d1d1d1, -5px -5px 10px #ffffff', // Neumorphism
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            zIndex: 1,
            border: '2px solid white'
        }}>
            <User size={28} color="#2563EB" strokeWidth={2} />

            {/* Online Badge */}
            <div style={{
                position: 'absolute',
                bottom: '2px',
                right: '2px',
                width: '12px',
                height: '12px',
                borderRadius: '50%',
                background: '#10B981',
                border: '2px solid white',
                boxShadow: '0 2px 4px rgba(0,0,0,0.1)'
            }} />
        </div>
    </div>
);

const LiquidBrain = ({ percent, isAnimating }) => {
    // Calculate water level (y-coordinate of the surface)
    // 24 is bottom, 0 is top.
    // Cap at 100 to prevent overflow
    const cappedPercent = Math.min(percent, 100);
    const yLevel = 24 - (24 * (cappedPercent / 100));

    return (
        <div style={{ position: 'relative', width: '60px', height: '60px', filter: 'drop-shadow(0 4px 6px rgba(124, 58, 237, 0.2))' }}>
            <svg width="100%" height="100%" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
                <defs>
                    <clipPath id="brain-clip">
                        <path d="M9.5 2A2.5 2.5 0 0 1 12 4.5v15a2.5 2.5 0 0 1-4.96.44 2.5 2.5 0 0 1-2.96-3.08 3 3 0 0 1-.34-5.58 2.5 2.5 0 0 1 1.32-4.24 2.5 2.5 0 0 1 1.98-3A2.5 2.5 0 0 1 9.5 2Z" />
                        <path d="M14.5 2A2.5 2.5 0 0 0 12 4.5v15a2.5 2.5 0 0 0 4.96.44 2.5 2.5 0 0 0 2.96-3.08 3 3 0 0 0 .34-5.58 2.5 2.5 0 0 0-1.32-4.24 2.5 2.5 0 0 0-1.98-3A2.5 2.5 0 0 0 14.5 2Z" />
                    </clipPath>
                    <linearGradient id="liquid-gradient" x1="0" y1="0" x2="0" y2="1">
                        <stop offset="0%" stopColor="#A78BFA" />
                        <stop offset="100%" stopColor="#7C3AED" />
                    </linearGradient>
                </defs>

                {/* Background (Empty State) */}
                <rect width="24" height="24" fill="#F3E8FF" clipPath="url(#brain-clip)" />

                {/* Liquid Fill with Wave Animation */}
                <g clipPath="url(#brain-clip)">
                    <motion.path
                        fill="url(#liquid-gradient)"
                        // Wave path: Starts wide to allow scrolling
                        d="M-24,0 C-12,1.5 0,1.5 12,0 S36,-1.5 48,0 V30 H-24 Z"
                        animate={{
                            x: [0, -24], // Scroll left to create wave effect
                            y: yLevel    // Rise based on percentage
                        }}
                        transition={{
                            x: { repeat: Infinity, duration: 2, ease: "linear" },
                            y: { duration: 0.8, ease: "easeInOut" }
                        }}
                    />
                </g>

                {/* Brain Outline */}
                <path d="M9.5 2A2.5 2.5 0 0 1 12 4.5v15a2.5 2.5 0 0 1-4.96.44 2.5 2.5 0 0 1-2.96-3.08 3 3 0 0 1-.34-5.58 2.5 2.5 0 0 1 1.32-4.24 2.5 2.5 0 0 1 1.98-3A2.5 2.5 0 0 1 9.5 2Z" stroke="#7C3AED" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
                <path d="M14.5 2A2.5 2.5 0 0 0 12 4.5v15a2.5 2.5 0 0 0 4.96.44 2.5 2.5 0 0 0 2.96-3.08 3 3 0 0 0 .34-5.58 2.5 2.5 0 0 0-1.32-4.24 2.5 2.5 0 0 0-1.98-3A2.5 2.5 0 0 0 14.5 2Z" stroke="#7C3AED" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
            </svg>
        </div>
    );
};

const PaperPlaneIcon = () => (
    <svg width="28" height="28" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg" style={{ filter: 'drop-shadow(0 2px 4px rgba(59, 130, 246, 0.5))' }}>
        <path d="M22 2L11 13" stroke="white" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
        <path d="M22 2L15 22L11 13L2 9L22 2Z" fill="#3B82F6" stroke="white" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
);

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
            }, 2500);
            return () => clearTimeout(timer);
        } else {
            setDisplayCount(preferenceCount);
        }
    }, [preferenceCount, displayCount]);

    // Calculate percentage with proper rounding
    // Each preference = 100/30 = 3.333...%
    // Round to get exact 100% at max (30 preferences)
    const rawPercent = (displayCount / maxPreferences) * 100;
    const percent = displayCount >= maxPreferences ? 100 : Math.round(rawPercent);

    return (
        <div style={{
            position: 'relative',
            padding: '0 20px',
            height: '100%',
            width: '100%',
            maxWidth: '650px',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            gap: '30px',
            fontFamily: "'Inter', sans-serif"
        }}>
            {/* User Side */}
            <div style={{ display: 'flex', alignItems: 'center', gap: '12px', zIndex: 10 }}>
                <GlassUser isAnimating={isAnimating} />
                <div style={{ display: 'flex', flexDirection: 'column' }}>
                    <span style={{ fontSize: '13px', fontWeight: '700', color: '#1E293B', letterSpacing: '-0.3px' }}>YOU</span>
                    <span style={{ fontSize: '11px', color: '#64748B' }}>Student</span>
                </div>
            </div>

            {/* Flight Area */}
            <div style={{ flex: 1, position: 'relative', height: '80px', display: 'flex', alignItems: 'center' }}>
                {/* Flight Path Visualization (Subtle Guide) */}
                <svg width="100%" height="100%" style={{ position: 'absolute', top: 0, left: 0, overflow: 'visible' }}>
                    <path
                        d="M 0,40 C 50,-20 150,-20 200,40"
                        fill="none"
                        stroke={isAnimating ? "url(#gradient-path)" : "#F1F5F9"}
                        strokeWidth="2"
                        strokeDasharray="4 4"
                        style={{ transition: 'stroke 0.5s' }}
                    />
                    <defs>
                        <linearGradient id="gradient-path" x1="0" y1="0" x2="1" y2="0">
                            <stop offset="0%" stopColor="#3B82F6" stopOpacity="0" />
                            <stop offset="50%" stopColor="#3B82F6" stopOpacity="0.5" />
                            <stop offset="100%" stopColor="#3B82F6" stopOpacity="0" />
                        </linearGradient>
                    </defs>
                </svg>

                {/* The Paper Plane */}
                <div style={{ position: 'absolute', left: 0, top: 0, width: '100%', height: '100%', pointerEvents: 'none' }}>
                    {/* Idle Plane */}
                    {!isAnimating && (
                        <div style={{ position: 'absolute', left: '-10px', top: '50%', transform: 'translateY(-50%) rotate(15deg)', opacity: 0.6, filter: 'grayscale(100%)' }}>
                            <PaperPlaneIcon />
                        </div>
                    )}

                    {/* Flying Plane */}
                    <AnimatePresence>
                        {isAnimating && (
                            <motion.div
                                initial={{ left: '0%', top: '50%', scale: 0.8, rotate: 0, opacity: 0 }}
                                animate={{
                                    left: ['0%', '20%', '40%', '50%', '60%', '80%', '100%'],
                                    top: ['50%', '20%', '80%', '50%', '20%', '50%', '50%'], // Figure-8 / Loop
                                    rotate: [0, -30, 30, 0, -30, 10, 0],
                                    scale: [1, 1.2, 1.2, 1.2, 1.2, 1, 0.5],
                                    opacity: [0, 1, 1, 1, 1, 1, 0]
                                }}
                                transition={{ duration: 2.2, ease: "easeInOut" }}
                                style={{
                                    position: 'absolute',
                                    transform: 'translate(-50%, -50%)',
                                    zIndex: 20
                                }}
                            >
                                <PaperPlaneIcon />
                                {/* Jet Stream */}
                                <motion.div
                                    style={{
                                        position: 'absolute',
                                        top: '50%',
                                        right: '80%',
                                        height: '3px',
                                        width: '40px',
                                        background: 'linear-gradient(to left, rgba(59, 130, 246, 0.6), transparent)',
                                        borderRadius: '2px'
                                    }}
                                />
                            </motion.div>
                        )}
                    </AnimatePresence>
                </div>

                {/* Status Text (Only when syncing) */}
                <div style={{ position: 'absolute', bottom: '10px', width: '100%', textAlign: 'center' }}>
                    <AnimatePresence mode='wait'>
                        {isAnimating && (
                            <motion.span
                                key="syncing"
                                initial={{ opacity: 0, y: 5 }}
                                animate={{ opacity: 1, y: 0 }}
                                exit={{ opacity: 0 }}
                                style={{ fontSize: '11px', color: '#8B5CF6', fontWeight: '600', display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '6px', textTransform: 'uppercase', letterSpacing: '0.5px' }}
                            >
                                <Sparkles size={12} /> Syncing...
                            </motion.span>
                        )}
                    </AnimatePresence>
                </div>
            </div>

            {/* Twin Side */}
            <div style={{ display: 'flex', alignItems: 'center', gap: '12px', zIndex: 10 }}>
                <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'flex-end' }}>
                    <span style={{ fontSize: '13px', fontWeight: '700', color: '#4C1D95', letterSpacing: '-0.3px' }}>TWIN</span>
                    <span style={{ fontSize: '14px', color: '#7C3AED', fontWeight: '700' }}>{percent}%</span>
                </div>

                <div style={{ position: 'relative' }}>
                    {/* Confetti */}
                    <AnimatePresence>
                        {showConfetti && (
                            <>
                                {[...Array(16)].map((_, i) => (
                                    <motion.div
                                        key={i}
                                        initial={{ opacity: 1, scale: 0, x: 0, y: 0 }}
                                        animate={{
                                            opacity: 0,
                                            scale: 1,
                                            x: (Math.random() - 0.5) * 120,
                                            y: (Math.random() - 0.5) * 120
                                        }}
                                        transition={{ duration: 1.2, ease: "easeOut" }}
                                        style={{
                                            position: 'absolute',
                                            top: '50%',
                                            left: '50%',
                                            width: '6px',
                                            height: '6px',
                                            borderRadius: '50%',
                                            background: ['#F472B6', '#60A5FA', '#34D399', '#FBBF24', '#A78BFA'][i % 5],
                                            zIndex: 30
                                        }}
                                    />
                                ))}
                            </>
                        )}
                    </AnimatePresence>
                    <LiquidBrain percent={percent} isAnimating={isAnimating} />
                </div>
            </div>
        </div>
    );
};

export default PreferenceVisualizer;

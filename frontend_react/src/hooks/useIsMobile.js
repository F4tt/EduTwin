import { useState, useEffect } from 'react';

/**
 * Custom hook to detect mobile viewport
 * @param {number} breakpoint - Width breakpoint in pixels (default: 768)
 * @returns {boolean} - True if viewport width is less than breakpoint
 */
export function useIsMobile(breakpoint = 768) {
    const [isMobile, setIsMobile] = useState(() => {
        if (typeof window === 'undefined') return false;
        return window.innerWidth < breakpoint;
    });

    useEffect(() => {
        if (typeof window === 'undefined') return;

        const checkMobile = () => {
            setIsMobile(window.innerWidth < breakpoint);
        };

        // Check immediately
        checkMobile();

        // Add resize listener with debounce for performance
        let timeoutId;
        const handleResize = () => {
            clearTimeout(timeoutId);
            timeoutId = setTimeout(checkMobile, 100);
        };

        window.addEventListener('resize', handleResize);
        return () => {
            window.removeEventListener('resize', handleResize);
            clearTimeout(timeoutId);
        };
    }, [breakpoint]);

    return isMobile;
}

export default useIsMobile;

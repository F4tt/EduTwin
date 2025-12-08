/**
 * Utility functions for handling different score scales
 */

export const SCALE_CONFIGS = {
    '0-10': {
        min: 0,
        max: 10,
        step: 0.01,
        label: 'Thang 0.0 - 10.0',
        format: (value) => value?.toFixed(2)
    },
    '0-100': {
        min: 0,
        max: 100,
        step: 0.01,
        label: 'Thang 0.0 - 100.0',
        format: (value) => value?.toFixed(2)
    },
    '0-10000': {
        min: 0,
        max: 10000,
        step: 1,
        label: 'Thang 0 - 10000',
        format: (value) => Math.round(value)
    },
    'A-F': {
        min: 0,
        max: 100,
        step: 0.01,
        label: 'Thang A - F',
        format: (value) => {
            if (value >= 90) return 'A';
            if (value >= 80) return 'B';
            if (value >= 70) return 'C';
            if (value >= 60) return 'D';
            return 'F';
        },
        formatNumeric: (value) => value?.toFixed(2)
    },
    'GPA': {
        min: 0,
        max: 4,
        step: 0.01,
        label: 'Thang GPA 0.0 - 4.0',
        format: (value) => value?.toFixed(2)
    }
};

/**
 * Get scale configuration
 * @param {string} scaleType - Scale type ('0-10', '0-100', etc.)
 * @returns {object} Scale configuration
 */
export const getScaleConfig = (scaleType) => {
    return SCALE_CONFIGS[scaleType] || SCALE_CONFIGS['0-10'];
};

/**
 * Get min value for a scale
 * @param {string} scaleType - Scale type
 * @returns {number} Minimum value
 */
export const getScaleMin = (scaleType) => {
    return getScaleConfig(scaleType).min;
};

/**
 * Get max value for a scale
 * @param {string} scaleType - Scale type
 * @returns {number} Maximum value
 */
export const getScaleMax = (scaleType) => {
    return getScaleConfig(scaleType).max;
};

/**
 * Get step value for a scale (for input fields)
 * @param {string} scaleType - Scale type
 * @returns {number} Step value
 */
export const getScaleStep = (scaleType) => {
    return getScaleConfig(scaleType).step;
};

/**
 * Format a score value according to scale type
 * @param {number} value - Score value
 * @param {string} scaleType - Scale type
 * @returns {string} Formatted score
 */
export const formatScore = (value, scaleType) => {
    if (value === null || value === undefined || isNaN(value)) return null;
    const config = getScaleConfig(scaleType);
    return config.format(value);
};

/**
 * Validate if a score is within scale range
 * @param {number} value - Score value
 * @param {string} scaleType - Scale type
 * @returns {boolean} Whether the score is valid
 */
export const isValidScore = (value, scaleType) => {
    const config = getScaleConfig(scaleType);
    return value >= config.min && value <= config.max;
};

/**
 * Calculate dynamic domain for charts based on data and scale
 * @param {number[]} values - Array of score values
 * @param {string} scaleType - Scale type
 * @param {number} paddingPercent - Padding percentage (default 10%)
 * @returns {[number, number]} Domain [min, max]
 */
export const calculateChartDomain = (values, scaleType, paddingPercent = 10) => {
    const config = getScaleConfig(scaleType);
    const scaleMax = config.max;
    
    if (!values || values.length === 0) {
        return [config.min, scaleMax];
    }
    
    const validValues = values.filter(v => v !== null && v !== undefined && !isNaN(v));
    if (validValues.length === 0) {
        return [config.min, scaleMax];
    }
    
    const dataMax = Math.max(...validValues);
    const padding = dataMax * (paddingPercent / 100);
    const calculatedMax = Math.min(dataMax + padding, scaleMax);
    
    return [config.min, calculatedMax];
};

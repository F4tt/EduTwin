/**
 * Checks if a username is valid (alphanumeric, underscores, hyphens, ascii only).
 * @param {string} username 
 * @returns {boolean}
 */
export const isValidUsername = (username) => {
    if (!username) return false;
    // ASCII only, alphanumeric + underscore + hyphen
    const regex = /^[a-zA-Z0-9_-]+$/;
    return regex.test(username);
};

/**
 * Checks if a string contains only letters and spaces (for names).
 * @param {string} name 
 * @returns {boolean}
 */
export const isValidName = (name) => {
    if (!name) return false;
    // Allow unicode letters and spaces
    // Simple regex for letters and spaces, might need refinement for full Vietnamese support if strictness is needed
    // But for now, let's allow most characters but maybe warn on numbers/symbols if needed.
    // The python code used `isalpha() or isspace()`.
    // In JS, we can use a regex that allows unicode letters.
    return /^[a-zA-Z\u00C0-\u024F\u1E00-\u1EFF\s]+$/.test(name);
};

/**
 * Validates profile fields.
 * @param {string} email 
 * @param {string} phone 
 * @param {string} age 
 * @returns {{isValid: boolean, error: string}}
 */
export const validateProfileFields = (email, phone, age) => {
    if (email && !email.includes('@')) {
        return { isValid: false, error: "Email không hợp lệ. Vui lòng nhập đúng định dạng email." };
    }

    if (phone && !/^\d[\d\s]*$/.test(phone)) {
        return { isValid: false, error: "Số điện thoại chỉ được chứa chữ số và khoảng trắng." };
    }

    if (age) {
        const ageInt = parseInt(age, 10);
        if (isNaN(ageInt) || ageInt < 1 || ageInt > 120) {
            return { isValid: false, error: "Tuổi không hợp lệ. Vui lòng nhập số từ 1 đến 120." };
        }
    }

    return { isValid: true, error: "" };
};

/**
 * Validates a score value.
 * @param {string|number} value 
 * @returns {string|null} Error message or null if valid
 */
export const validateScore = (value) => {
    if (value === null || value === undefined || value === '') return null; // Empty is valid (means delete/no score)

    // Replace comma with dot for float parsing
    const strVal = String(value).replace(',', '.');
    const numVal = parseFloat(strVal);

    if (isNaN(numVal)) return "Phải là số";
    if (numVal < 0 || numVal > 10) return "0 - 10";

    return null;
};

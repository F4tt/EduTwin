/**
 * Error Message Translator
 * Converts backend error messages to user-friendly Vietnamese
 */

const ERROR_TRANSLATIONS = {
    // Pipeline & Prediction errors
    "No reference dataset": "Chưa có dữ liệu mẫu. Vui lòng liên hệ quản trị viên để tải dữ liệu tham chiếu.",
    "No reference dataset uploaded": "Chưa tải lên dữ liệu mẫu. Admin cần tải file dữ liệu tham chiếu trước.",
    "No user scores": "Bạn chưa nhập điểm số nào. Hãy nhập điểm để hệ thống có thể dự đoán.",
    "No valid current time point": "Chưa chọn mốc thời gian hiện tại. Vui lòng chọn học kỳ/kỳ thi hiện tại.",
    "Structure not found": "Không tìm thấy cấu trúc học tập. Vui lòng thử lại sau.",
    "Prediction failed": "Dự đoán thất bại. Hệ thống đang gặp sự cố, xin thử lại sau.",

    // Authentication errors
    "Chưa đăng nhập": "Phiên đăng nhập đã hết hạn. Vui lòng đăng nhập lại.",
    "Session không hợp lệ": "Phiên làm việc không còn hiệu lực. Vui lòng đăng nhập lại.",
    "Session không hợp lệ hoặc đã hết hạn": "Phiên làm việc đã hết hạn. Vui lòng đăng nhập lại.",

    // Permission errors
    "Only admins can view structures": "Bạn không có quyền xem cấu trúc này. Chỉ quản trị viên có thể thực hiện.",
    "Only admins can activate structures": "Chỉ quản trị viên mới có thể kích hoạt cấu trúc.",
    "Only admins can delete structures": "Chỉ quản trị viên mới có thể xóa cấu trúc.",
    "Only admins can create structures": "Chỉ quản trị viên mới có thể tạo cấu trúc mới.",
    "Only admins can toggle pipeline": "Chỉ quản trị viên mới có thể bật/tắt pipeline.",
    "Only admins can upload datasets": "Chỉ quản trị viên mới có thể tải lên dữ liệu.",
    "Cannot delete admin documents": "Không thể xóa tài liệu này vì thuộc quyền quản trị viên.",

    // Document & File errors
    "Document not found": "Không tìm thấy tài liệu. Tài liệu có thể đã bị xóa.",
    "User not found": "Không tìm thấy người dùng. Vui lòng đăng nhập lại.",
    "Unsupported file type": "Định dạng file không được hỗ trợ. Vui lòng dùng file Excel (.xlsx, .xls).",
    "File too large": "File quá lớn. Kích thước tối đa là 20MB.",
    "No content extracted": "Không thể đọc nội dung file. Vui lòng kiểm tra file và thử lại.",

    // Validation errors
    "No active structure": "Chưa kích hoạt cấu trúc học tập nào. Vui lòng liên hệ quản trị viên.",
    "structure_id is required": "Thiếu thông tin cấu trúc. Vui lòng thử lại.",

    // ML Model errors
    "Cần ít nhất 20 mẫu": "Dữ liệu chưa đủ để đánh giá. Cần ít nhất 20 mẫu tham chiếu.",
    "Cần ít nhất 20 mẫu để đánh giá": "Dữ liệu chưa đủ để đánh giá mô hình. Cần ít nhất 20 mẫu.",
    "No predictions made": "Không thể tạo dự đoán. Vui lòng kiểm tra dữ liệu đầu vào.",
    "Clustering failed": "Phân cụm dữ liệu thất bại. Hệ thống đang gặp sự cố.",

    // Developer/LLM errors
    "Invalid secret key": "Mã bí mật không hợp lệ.",
    "Username is required": "Vui lòng nhập tên người dùng.",
    "Missing 'message' in request body": "Tin nhắn không được để trống.",
    "LLM request failed": "Yêu cầu AI thất bại. Vui lòng thử lại sau.",

    // Generic network errors
    "Network Error": "Lỗi kết nối mạng. Vui lòng kiểm tra kết nối internet.",
    "Request failed": "Yêu cầu thất bại. Vui lòng thử lại.",
    "timeout": "Yêu cầu quá thời gian chờ. Vui lòng thử lại.",
    "ECONNREFUSED": "Không thể kết nối đến máy chủ. Vui lòng thử lại sau.",

    // New Vietnamese backend messages (pass through)
    "Không tìm thấy cấu trúc": "Không tìm thấy cấu trúc học tập. Vui lòng thử lại sau.",
    "Không tìm thấy người dùng": "Không tìm thấy người dùng. Vui lòng đăng nhập lại.",
    "Không tìm thấy tài liệu": "Không tìm thấy tài liệu. Tài liệu có thể đã bị xóa.",
    "Mốc thời gian không hợp lệ": "Mốc thời gian không hợp lệ. Vui lòng chọn lại.",
    "Vui lòng chọn mốc thời gian hiện tại": "Vui lòng chọn mốc thời gian hiện tại trước khi dự đoán.",
    "Chỉ quản trị viên mới có thể": "Bạn không có quyền thực hiện thao tác này.",
};

/**
 * Translate a backend error message to user-friendly Vietnamese
 * @param {string} errorMessage - Original error message from backend
 * @returns {string} User-friendly Vietnamese message
 */
export function translateError(errorMessage) {
    if (!errorMessage) return "Đã xảy ra lỗi. Vui lòng thử lại.";

    const msg = String(errorMessage);

    // Check for exact matches first
    if (ERROR_TRANSLATIONS[msg]) {
        return ERROR_TRANSLATIONS[msg];
    }

    // Check for partial matches (for messages with dynamic parts)
    for (const [pattern, translation] of Object.entries(ERROR_TRANSLATIONS)) {
        if (msg.toLowerCase().includes(pattern.toLowerCase())) {
            return translation;
        }
    }

    // Handle specific patterns
    if (msg.includes("Prediction failed:")) {
        return "Dự đoán thất bại: " + msg.replace("Prediction failed:", "").trim();
    }

    if (msg.includes("Unsupported file type:")) {
        const ext = msg.match(/Unsupported file type: (\.\w+)/)?.[1] || "";
        return `Định dạng file ${ext} không được hỗ trợ. Vui lòng dùng Excel (.xlsx, .xls).`;
    }

    if (msg.includes("Chỉ có") && msg.includes("mẫu hợp lệ")) {
        return msg; // Already in Vietnamese
    }

    if (msg.includes("User '") && msg.includes("' not found")) {
        const username = msg.match(/User '([^']+)' not found/)?.[1] || "";
        return `Không tìm thấy người dùng '${username}'.`;
    }

    // If message already contains Vietnamese characters, return as-is
    if (/[àảãáạăằẳẵắặâầẩẫấậèẻẽéẹêềểễếệìỉĩíịòỏõóọôồổỗốộơờởỡớợùủũúụưừửữứựỳỷỹýỵđ]/i.test(msg)) {
        return msg;
    }

    // Generic fallback
    return `Đã xảy ra lỗi: ${msg}`;
}

/**
 * Format pipeline error for display
 * @param {string|object} error - Error from pipeline or API response
 * @returns {string} User-friendly error message
 */
export function formatPipelineError(error) {
    if (!error) return "";

    // Handle object with detail field
    if (typeof error === 'object') {
        if (error.detail) {
            return translateError(error.detail);
        }
        if (error.message) {
            return translateError(error.message);
        }
        return translateError(JSON.stringify(error));
    }

    return translateError(String(error));
}

/**
 * Create a user-friendly error display message
 * @param {Error|string} error - Error object or message
 * @param {string} prefix - Optional prefix for the message
 * @returns {string} Formatted error message
 */
export function createErrorMessage(error, prefix = "") {
    const errorText = error?.response?.data?.detail
        || error?.message
        || String(error);

    const translated = translateError(errorText);

    if (prefix) {
        return `${prefix}: ${translated}`;
    }
    return translated;
}

export default {
    translateError,
    formatPipelineError,
    createErrorMessage,
};

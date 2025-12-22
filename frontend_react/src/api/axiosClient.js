import axios from 'axios';

// Dev mode: use VITE_API_URL from env
// Production mode: empty string (relative URL - API calls go through ALB routing)
const API_URL = import.meta.env.VITE_API_URL || '';

const axiosClient = axios.create({
    baseURL: API_URL,
    headers: {
        'Content-Type': 'application/json',
    },
    withCredentials: true,
    timeout: 120000, // 120 seconds timeout (increased for LLM requests)
});

axiosClient.interceptors.response.use(
    (response) => response,
    (error) => {
        if (error.response && error.response.status === 401) {
            // Skip redirect for /auth/me (used for initial auth check)
            const requestUrl = error.config?.url || '';
            if (requestUrl.includes('/auth/me')) {
                return Promise.reject(error);
            }

            // For other endpoints, redirect to login (but avoid loop)
            if (window.location.pathname !== '/login' && window.location.pathname !== '/register') {
                window.location.href = '/login';
            }
        }
        return Promise.reject(error);
    }
);

export default axiosClient;

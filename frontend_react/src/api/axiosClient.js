import axios from 'axios';

// Dev mode: use VITE_API_URL from env or default to localhost:8000
// Production mode: empty string (use Nginx proxy)
const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

const axiosClient = axios.create({
    baseURL: API_URL,
    headers: {
        'Content-Type': 'application/json',
    },
    withCredentials: true,
    timeout: 10000, // 10 seconds timeout
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
            
            // Skip redirect if user is trying to login (avoid clearing error messages)
            if (requestUrl.includes('/auth/login') || requestUrl.includes('/auth/register') || 
                requestUrl.includes('/auth/institution/login') || requestUrl.includes('/auth/institution/register')) {
                return Promise.reject(error);
            }
            
            // For other endpoints, redirect to login (but avoid loop)
            const currentPath = window.location.pathname;
            if (!currentPath.startsWith('/login') && currentPath !== '/register') {
                window.location.href = '/login';
            }
        }
        return Promise.reject(error);
    }
);

export default axiosClient;

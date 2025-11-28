import React, { Suspense, lazy } from 'react';
import { BrowserRouter as Router, Routes, Route, Navigate, useLocation } from 'react-router-dom';
import { AuthProvider, useAuth } from './context/AuthContext';
import Layout from './components/Layout';

// Lazy load pages for code splitting (reduce initial bundle size)
const Auth = lazy(() => import('./pages/Auth'));
const FirstLogin = lazy(() => import('./pages/FirstLogin'));
const Chatbot = lazy(() => import('./pages/Chatbot'));
const DataViz = lazy(() => import('./pages/DataViz'));
const StudyUpdate = lazy(() => import('./pages/StudyUpdate'));
const Settings = lazy(() => import('./pages/Settings'));
const Developer = lazy(() => import('./pages/Developer'));
const LearningGoals = lazy(() => import('./pages/LearningGoals'));

// Loading fallback component
const PageLoader = () => (
  <div style={{ 
    display: 'flex', 
    justifyContent: 'center', 
    alignItems: 'center', 
    height: '100vh',
    fontSize: '1.2rem',
    color: '#666'
  }}>
    Đang tải...
  </div>
);

const ProtectedRoute = ({ children }) => {
  const { user, loading } = useAuth();
  const location = useLocation();

  if (loading) return <div>Loading...</div>;
  if (!user) return <Navigate to="/login" state={{ from: location }} replace />;

  // Check for first login flag (logic adapted from app.py)
  // If user has no email/phone/grade, they might need first-time setup
  // But we'll rely on the is_first_login flag from backend or simple check
  const needsOnboarding = user.is_first_login;

  if (needsOnboarding && location.pathname !== '/first-time') {
    return <Navigate to="/first-time" replace />;
  }

  return children;
};

function AppRoutes() {
  return (
    <Routes>
      <Route path="/login" element={
        <Suspense fallback={<PageLoader />}>
          <Auth />
        </Suspense>
      } />
      <Route
        path="/first-time"
        element={
          <ProtectedRoute>
            <Suspense fallback={<PageLoader />}>
              <FirstLogin />
            </Suspense>
          </ProtectedRoute>
        }
      />
      <Route
        path="/"
        element={
          <ProtectedRoute>
            <Layout />
          </ProtectedRoute>
        }
      >
        <Route index element={<Navigate to="/chat" replace />} />
        <Route path="chat" element={
          <Suspense fallback={<PageLoader />}>
            <Chatbot />
          </Suspense>
        } />
        <Route path="data" element={
          <Suspense fallback={<PageLoader />}>
            <DataViz />
          </Suspense>
        } />
        <Route path="goals" element={
          <Suspense fallback={<PageLoader />}>
            <LearningGoals />
          </Suspense>
        } />
        <Route path="study" element={
          <Suspense fallback={<PageLoader />}>
            <StudyUpdate />
          </Suspense>
        } />
        <Route path="developer" element={
          <Suspense fallback={<PageLoader />}>
            <Developer />
          </Suspense>
        } />
        <Route path="settings" element={
          <Suspense fallback={<PageLoader />}>
            <Settings />
          </Suspense>
        } />
      </Route>
    </Routes>
  );
}

function App() {
  return (
    <AuthProvider>
      <Router>
        <AppRoutes />
      </Router>
    </AuthProvider>
  );
}

export default App;

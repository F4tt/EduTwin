import React, { Suspense, lazy } from 'react';
import { BrowserRouter as Router, Routes, Route, Navigate, useLocation } from 'react-router-dom';
import { AuthProvider, useAuth } from './context/AuthContext';
import { WebSocketProvider } from './context/WebSocketContext';
import Layout from './components/Layout';
import InstitutionLayout from './components/InstitutionLayout';

// Lazy load pages for code splitting (reduce initial bundle size)
const Auth = lazy(() => import('./pages/Auth'));
const LoginChoice = lazy(() => import('./pages/LoginChoice'));
const LoginStudent = lazy(() => import('./pages/LoginStudent'));
const LoginInstitution = lazy(() => import('./pages/LoginInstitution'));
const InstitutionDashboard = lazy(() => import('./pages/InstitutionDashboard'));
const InstitutionStudents = lazy(() => import('./pages/InstitutionStudents'));
const InstitutionAdminTools = lazy(() => import('./pages/InstitutionAdminTools'));
const InstitutionSettings = lazy(() => import('./pages/InstitutionSettings'));
const FirstLogin = lazy(() => import('./pages/FirstLogin'));
const Chatbot = lazy(() => import('./pages/Chatbot'));
const DataViz = lazy(() => import('./pages/DataViz'));
const StudyUpdate = lazy(() => import('./pages/StudyUpdate'));
const Settings = lazy(() => import('./pages/Settings'));
const Developer = lazy(() => import('./pages/Developer'));
const LearningGoals = lazy(() => import('./pages/LearningGoals'));

// Loading fallback component
const PageLoader = () => (
  <div className="page-loader">
    <div className="spinner" style={{ marginRight: '0.75rem' }}></div>
    Đang tải...
  </div>
);

const ProtectedRoute = ({ children }) => {
  const { user, loading } = useAuth();
  const location = useLocation();

  if (loading) return <PageLoader />;
  
  // If no user, redirect to login choice page
  if (!user) return <Navigate to="/login" state={{ from: location }} replace />;
  
  // If user is institution (has user_type field), redirect to institution dashboard
  if (user.user_type === 'institution') {
    return <Navigate to="/institution/dashboard" replace />;
  }

  // For regular students (no user_type or user_type is undefined)
  // Check for first login flag
  const needsOnboarding = user.is_first_login;

  if (needsOnboarding && location.pathname !== '/first-time') {
    return <Navigate to="/first-time" replace />;
  }

  return children;
};

const InstitutionProtectedRoute = ({ children }) => {
  const { user, loading } = useAuth();
  const location = useLocation();

  if (loading) return <PageLoader />;
  if (!user || user.user_type !== 'institution') {
    return <Navigate to="/login/institution" state={{ from: location }} replace />;
  }

  return children;
};

function AppRoutes() {
  return (
    <Routes>
      {/* Main Login Choice Page */}
      <Route path="/login" element={
        <Suspense fallback={<PageLoader />}>
          <LoginChoice />
        </Suspense>
      } />
      
      {/* Student Login */}
      <Route path="/login/student" element={
        <Suspense fallback={<PageLoader />}>
          <LoginStudent />
        </Suspense>
      } />
      
      {/* Institution Login */}
      <Route path="/login/institution" element={
        <Suspense fallback={<PageLoader />}>
          <LoginInstitution />
        </Suspense>
      } />

      {/* Institution Routes with Layout */}
      <Route path="/institution" element={
        <InstitutionProtectedRoute>
          <InstitutionLayout />
        </InstitutionProtectedRoute>
      }>
        <Route index element={<Navigate to="/institution/dashboard" replace />} />
        <Route path="dashboard" element={
          <Suspense fallback={<PageLoader />}>
            <InstitutionDashboard />
          </Suspense>
        } />
        <Route path="students" element={
          <Suspense fallback={<PageLoader />}>
            <InstitutionStudents />
          </Suspense>
        } />
        <Route path="admin-tools" element={
          <Suspense fallback={<PageLoader />}>
            <InstitutionAdminTools />
          </Suspense>
        } />
        <Route path="settings" element={
          <Suspense fallback={<PageLoader />}>
            <InstitutionSettings />
          </Suspense>
        } />
      </Route>
      
      {/* Student First Time Setup */}
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
      
      {/* Student Routes */}
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
      <WebSocketProvider>
        <Router>
          <AppRoutes />
        </Router>
      </WebSocketProvider>
    </AuthProvider>
  );
}

export default App;

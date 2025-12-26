import React, { Suspense, lazy } from 'react';
import { BrowserRouter as Router, Routes, Route, Navigate, useLocation } from 'react-router-dom';
import { AuthProvider, useAuth } from './context/AuthContext';
import { WebSocketProvider } from './context/WebSocketContext';
import Layout from './components/Layout';

// Lazy load pages for code splitting (reduce initial bundle size)
const Auth = lazy(() => import('./pages/Auth'));
const Chat = lazy(() => import('./pages/Chat'));
const Learning = lazy(() => import('./pages/Learning'));
const DataViz = lazy(() => import('./pages/DataViz'));
const StudyUpdate = lazy(() => import('./pages/StudyUpdate'));
const Settings = lazy(() => import('./pages/Settings'));
const Developer = lazy(() => import('./pages/Developer'));

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
  if (!user) return <Navigate to="/login" state={{ from: location }} replace />;

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
            <Chat />
          </Suspense>
        } />
        <Route path="learning" element={
          <Suspense fallback={<PageLoader />}>
            <Learning />
          </Suspense>
        } />
        <Route path="data" element={
          <Suspense fallback={<PageLoader />}>
            <DataViz />
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

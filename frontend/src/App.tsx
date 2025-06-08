import React from 'react';
import { BrowserRouter as Router, Routes, Route, useLocation, Navigate } from 'react-router-dom';
import SideNavigation from '@/components/SideNavigation';
import HomePage from '@/pages/HomePage';
import ChatPage from '@/pages/ChatPage';
import TestCasePage from '@/pages/TestCasePage';
import ScrollTestPage from '@/pages/ScrollTestPage';
import LoginPage from '@/pages/LoginPage';
import UserProfilePage from '@/pages/UserProfilePage';
import { isAuthenticated } from '@/services/auth';

// 认证保护组件
const ProtectedRoute: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  return isAuthenticated() ? <>{children}</> : <Navigate to="/login" replace />;
};

const AppContent: React.FC = () => {
  const location = useLocation();
  const isHomePage = location.pathname === '/';
  const isLoginPage = location.pathname === '/login';

  // 登录页面独立显示
  if (isLoginPage) {
    return (
      <Routes>
        <Route path="/login" element={<LoginPage />} />
      </Routes>
    );
  }

  // 首页不显示侧边栏，其他页面显示
  if (isHomePage) {
    return (
      <Routes>
        <Route path="/" element={
          <ProtectedRoute>
            <HomePage />
          </ProtectedRoute>
        } />
      </Routes>
    );
  }

  return (
    <ProtectedRoute>
      <SideNavigation>
        <Routes>
          <Route path="/chat" element={<ChatPage />} />
          <Route path="/testcase" element={<TestCasePage />} />
          <Route path="/scroll-test" element={<ScrollTestPage />} />
          <Route path="/profile" element={<UserProfilePage />} />
        </Routes>
      </SideNavigation>
    </ProtectedRoute>
  );
};

const App: React.FC = () => {
  return (
    <Router>
      <AppContent />
    </Router>
  );
};

export default App;

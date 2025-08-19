import { Routes, Route } from 'react-router';
import '@ant-design/v5-patch-for-react-19';
import { App } from 'antd';
import './App.css'

import LoginPage from './pages/LoginPage';
import DashboardPage from './pages/DashboardPage';
import KeyManagementPage from './pages/KeyManagementPage';
import ConfigPage from './pages/ConfigPage';
import AboutPage from './pages/AboutPage';
import ProtectedRoute from "./components/ProtectedRoute";
import NotFoundPage from "./pages/NotFoundPage";
import MainLayout from "./components/MainLayout";

function RootApp() {
    return (
        <App>
            <Routes>
                {/* 公共路由 不需要登陆 */}
                <Route path="/login" element={<LoginPage />} />
                {/* 受保护路由组 */}
                <Route element={<ProtectedRoute />}>
                    <Route element={<MainLayout />}>
                        <Route path="/" element={<DashboardPage />} />
                        <Route path="/keys" element={<KeyManagementPage />} />
                        <Route path="/config" element={<ConfigPage />} />
                        <Route path="/about" element={<AboutPage />} />
                    </Route>
                </Route>
                {/*<Route path="*" element={<div>404 Not Found</div>}/>*/}
                <Route path="*" element={<NotFoundPage />} />
            </Routes>
        </App>
    );
}

export default RootApp;

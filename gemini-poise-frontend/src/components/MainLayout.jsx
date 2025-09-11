import { Layout, Breadcrumb } from 'antd';
import { Outlet, useLocation, useNavigate } from 'react-router';
import { useTranslation } from 'react-i18next';
import { useTheme } from '../contexts/ThemeContext';
import Header from './Header';
import Sidebar from './Sidebar';

const { Content } = Layout;

const MainLayout = () => {
  const location = useLocation();
  const navigate = useNavigate();
  const { t } = useTranslation();
  const { currentTheme } = useTheme();
  const isDark = currentTheme === 'dark';

  const getSelectedKey = () => {
    const path = location.pathname;
    if (path.includes('/keys')) return t('sidebar.apiKeys');
    if (path.includes('/about')) return t('sidebar.about');
    if (path.includes('/config')) return t('sidebar.configuration');
    return t('sidebar.dashboard');
  };

  const getBreadcrumbItems = () => {
    const key = getSelectedKey();
    return [
      {
        title: <a onClick={() => navigate('/')}>{t('sidebar.home')}</a>,
      },
      {
        title: key.charAt(0).toUpperCase() + key.slice(1)
      }
    ];
  };

  const contentStyle = {
    padding: 24,
    margin: 0,
    background: isDark ? 'rgba(51, 65, 85, 0.75)' : 'rgba(255, 255, 255, 0.7)',
    backdropFilter: 'blur(16px)',
    borderRadius: '12px',
    border: isDark ? '1px solid rgba(255, 255, 255, 0.08)' : '1px solid rgba(0, 0, 0, 0.1)',
    boxShadow: isDark 
      ? '0 8px 32px rgba(0, 0, 0, 0.4), inset 0 1px 0 rgba(255, 255, 255, 0.05)' 
      : '0 8px 32px rgba(0, 0, 0, 0.1), inset 0 1px 0 rgba(255, 255, 255, 0.8)',
    overflowY: 'auto',
    flex: 1,
  };

  const layoutStyle = {
    padding: '0 24px 24px',
    height: '100%',
    display: 'flex',
    flexDirection: 'column',
    background: isDark 
      ? 'linear-gradient(135deg, rgba(15, 23, 42, 0.3), rgba(30, 41, 59, 0.5))'
      : 'linear-gradient(135deg, rgba(248, 250, 252, 0.3), rgba(241, 245, 249, 0.5))',
  };

  return (
    <Layout style={{ maxHeight: '100vh' }}>
      <Header />
      <Layout style={{ height: 'calc(100vh - 64px)' }}>
        <Sidebar />
        <Layout style={layoutStyle}>
          <Breadcrumb
            style={{ margin: '16px 0' }}
            items={getBreadcrumbItems()}
          />
          <Content style={contentStyle}>
            <Outlet />
          </Content>
        </Layout>
      </Layout>
    </Layout>
  );
};

export default MainLayout;
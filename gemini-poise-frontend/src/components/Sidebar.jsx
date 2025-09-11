import { Layout, Menu, theme } from 'antd';
import { Link, useLocation } from 'react-router';
import { useTranslation } from 'react-i18next';
import {
  KeyOutlined,
  SettingOutlined,
  DashboardOutlined,
  InfoCircleOutlined,
} from '@ant-design/icons';
import { useTheme } from '../contexts/ThemeContext';

const { Sider: AntSider } = Layout;

const Sidebar = () => {
  const location = useLocation();
  const { currentTheme } = useTheme();
  const { t } = useTranslation();
  const isDark = currentTheme === 'dark';

  const getSelectedKey = () => {
    const path = location.pathname;
    if (path.includes('/keys')) return 'keys';
    if (path.includes('/config')) return 'config';
    if (path.includes('/about')) return 'about';
    return 'dashboard';
  };

  const menuItems = [
    { key: 'dashboard', icon: <DashboardOutlined />, label: <Link to="/">{t('sidebar.dashboard')}</Link> },
    { key: 'keys', icon: <KeyOutlined />, label: <Link to="/keys">{t('sidebar.apiKeys')}</Link> },
    { key: 'config', icon: <SettingOutlined />, label: <Link to="/config">{t('sidebar.configuration')}</Link> },
    { key: 'about', icon: <InfoCircleOutlined />, label: <Link to="/about">{t('sidebar.about')}</Link> },
  ];

  const siderStyle = {
    background: isDark ? 'rgba(30, 41, 59, 0.85)' : 'rgba(255, 255, 255, 0.85)',
    backdropFilter: 'blur(12px)',
    borderRight: isDark ? '1px solid rgba(255, 255, 255, 0.08)' : '1px solid rgba(0, 0, 0, 0.1)',
    boxShadow: isDark 
      ? '2px 0 8px rgba(0, 0, 0, 0.4)' 
      : '2px 0 8px rgba(0, 0, 0, 0.05)',
  };

  const menuStyle = {
    height: '100%',
    borderRight: 0,
    background: 'transparent',
  };

  return (
    <AntSider width={200} style={siderStyle}>
      <Menu
        mode="inline"
        selectedKeys={[getSelectedKey()]}
        style={menuStyle}
        items={menuItems}
        theme={isDark ? 'dark' : 'light'}
      />
    </AntSider>
  );
};

export default Sidebar;
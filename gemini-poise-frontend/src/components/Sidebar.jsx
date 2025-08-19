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

  const {
    token: { colorBgContainer },
  } = theme.useToken();

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

  return (
    <AntSider width={200} style={{
      background: colorBgContainer,
    }}>
      <Menu
        mode="inline"
        selectedKeys={[getSelectedKey()]}
        style={{ height: '100%', borderRight: 0 }}
        items={menuItems}
        theme={isDark ? 'dark' : 'light'}
      />
    </AntSider>
  );
};

export default Sidebar;
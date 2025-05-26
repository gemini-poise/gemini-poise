import { Layout, Typography, Space, Switch, theme } from 'antd';
import { useAuth } from '../contexts/AuthContext';
import { useTheme } from '../contexts/ThemeContext';
import {
  LogoutOutlined,
  GithubOutlined,
  SunOutlined,
  MoonOutlined
} from '@ant-design/icons';

const { Header: AntHeader } = Layout;
const { Title, Text } = Typography;

const Header = () => {
  const { user, logout } = useAuth();
  const { currentTheme, toggleTheme } = useTheme();
  const isDark = currentTheme === 'dark';

  const {
    token: { colorPrimary },
  } = theme.useToken();

  const headerStyle = {
    display: 'flex',
    alignItems: 'center',
    background: isDark ? '#001529' : colorPrimary,
    padding: '0 24px'
  };

  const handleLogout = (e) => {
    e.preventDefault();
    logout();
  };

  return (
    <AntHeader style={headerStyle}>
      <div style={{ display: 'flex', alignItems: 'center', marginRight: 'auto' }}>
        <Title level={4} style={{ color: 'white', margin: 0 }}>
          Gemini Poise
        </Title>
      </div>

      <Space size="middle">
        <a
          href="https://github.com/alterem"
          target="_blank"
          rel="noopener noreferrer"
          style={{ color: 'white' }}
        >
          <GithubOutlined style={{ fontSize: '20px' }} />
        </a>

        <Switch
          checkedChildren={<MoonOutlined />}
          unCheckedChildren={<SunOutlined />}
          checked={isDark}
          onChange={toggleTheme}
        />

        {user && (
          <Text style={{ color: 'white' }}>
            {`Welcome, ${user.username}`}
          </Text>
        )}

        <a
          onClick={handleLogout}
          style={{ color: 'white' }}
        >
          <Space>
            <LogoutOutlined />
            <span>Logout</span>
          </Space>
        </a>
      </Space>
    </AntHeader>
  );
};

export default Header;
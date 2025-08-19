import { Layout, Breadcrumb, theme } from 'antd';
import { Outlet, useLocation, useNavigate } from 'react-router';
import Header from './Header';
import Sidebar from './Sidebar';

const { Content } = Layout;

const MainLayout = () => {
  const location = useLocation();
  const navigate = useNavigate();

  const {
    token: { colorBgContainer, borderRadiusLG },
  } = theme.useToken();

  const getSelectedKey = () => {
    const path = location.pathname;
    if (path.includes('/keys')) return 'keys';
    if (path.includes('/config')) return 'config';
    return 'dashboard';
  };

  const getBreadcrumbItems = () => {
    const key = getSelectedKey();
    return [
      {
        title: <a onClick={() => navigate('/')}>Home</a>,
      },
      {
        title: key.charAt(0).toUpperCase() + key.slice(1)
      }
    ];
  };

  return (
    <Layout style={{ maxHeight: '100vh' }}>
      <Header />
      <Layout style={{ height: 'calc(100vh - 64px)' }}>
        <Sidebar />
        <Layout style={{ padding: '0 24px 24px', height: '100%', display: 'flex', flexDirection: 'column' }}>
          <Breadcrumb
            style={{ margin: '16px 0' }}
            items={getBreadcrumbItems()}
          />
          <Content
            style={{
              padding: 24,
              margin: 0,
              background: colorBgContainer,
              borderRadius: borderRadiusLG,
              overflowY: 'auto',
              flex: 1,
            }}
          >
            <Outlet />
          </Content>
        </Layout>
      </Layout>
    </Layout>
  );
};

export default MainLayout;
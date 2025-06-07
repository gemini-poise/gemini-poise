import { Layout, Typography, Space, Switch, theme, Modal, Form, Input, Button, message } from 'antd';
import { useAuth } from '../contexts/AuthContext';
import { useTheme } from '../contexts/ThemeContext';
import { changePassword } from '../api/api';
import { useState } from 'react';
import {
  LogoutOutlined,
  GithubOutlined,
  SunOutlined,
  MoonOutlined,
  UserOutlined
} from '@ant-design/icons';

const { Header: AntHeader } = Layout;
const { Title } = Typography;

const Header = () => {
  const { user, logout } = useAuth();
  const { currentTheme, toggleTheme } = useTheme();
  const isDark = currentTheme === 'dark';
  const [isPasswordModalVisible, setIsPasswordModalVisible] = useState(false);
  const [passwordForm] = Form.useForm();
  const [loading, setLoading] = useState(false);

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

  const handleUsernameClick = () => {
    setIsPasswordModalVisible(true);
  };

  const handlePasswordModalCancel = () => {
    setIsPasswordModalVisible(false);
    passwordForm.resetFields();
  };

  const handlePasswordChange = async (values) => {
    setLoading(true);
    try {
      await changePassword({
        current_password: values.currentPassword,
        new_password: values.newPassword
      });
      message.success('Password changed successfully!');
      setIsPasswordModalVisible(false);
      passwordForm.resetFields();
    } catch (error) {
      message.error(error.response?.data?.detail || 'Failed to change password, please try again');
    } finally {
      setLoading(false);
    }
  };

  return (
    <>
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
            <Button
              type="text"
              icon={<UserOutlined />}
              onClick={handleUsernameClick}
              style={{
                color: 'white',
                border: 'none',
                padding: '4px 8px',
                height: 'auto'
              }}
            >
              {user.username}
            </Button>
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

      <Modal
        title="Change Password"
        open={isPasswordModalVisible}
        onCancel={handlePasswordModalCancel}
        footer={null}
        width={400}
      >
        <Form
          form={passwordForm}
          layout="vertical"
          onFinish={handlePasswordChange}
          autoComplete="off"
        >
          <Form.Item
            label="Current Password"
            name="currentPassword"
            rules={[
              { required: true, message: 'Please enter current password' }
            ]}
          >
            <Input.Password placeholder="Enter current password" />
          </Form.Item>

          <Form.Item
            label="New Password"
            name="newPassword"
            rules={[
              { required: true, message: 'Please enter new password' },
              { min: 6, message: 'Password must be at least 6 characters' }
            ]}
          >
            <Input.Password placeholder="Enter new password" />
          </Form.Item>

          <Form.Item
            label="Confirm New Password"
            name="confirmPassword"
            dependencies={['newPassword']}
            rules={[
              { required: true, message: 'Please confirm new password' },
              ({ getFieldValue }) => ({
                validator(_, value) {
                  if (!value || getFieldValue('newPassword') === value) {
                    return Promise.resolve();
                  }
                  return Promise.reject(new Error('The two passwords do not match'));
                },
              }),
            ]}
          >
            <Input.Password placeholder="Enter new password again" />
          </Form.Item>

          <Form.Item style={{ marginBottom: 0, marginTop: 24 }}>
            <Space style={{ width: '100%', justifyContent: 'flex-end' }}>
              <Button onClick={handlePasswordModalCancel}>
                Cancel
              </Button>
              <Button type="primary" htmlType="submit" loading={loading}>
                Confirm
              </Button>
            </Space>
          </Form.Item>
        </Form>
      </Modal>
    </>
  );
};

export default Header;
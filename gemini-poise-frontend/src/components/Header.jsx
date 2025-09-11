import { Layout, Typography, Space, Switch, theme, Modal, Form, Input, Button, message } from 'antd';
import { useAuth } from '../contexts/AuthContext';
import { useTheme } from '../contexts/ThemeContext';
import { changePassword } from '../api/api';
import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import LanguageSwitcher from './LanguageSwitcher';
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
  const { t } = useTranslation();
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
      message.success(t('header.passwordChangedSuccess'));
      setIsPasswordModalVisible(false);
      passwordForm.resetFields();
    } catch (error) {
      message.error(error.response?.data?.detail || t('header.passwordChangeFailed'));
    } finally {
      setLoading(false);
    }
  };

  return (
    <>
      <AntHeader style={headerStyle}>
        <div style={{ display: 'flex', alignItems: 'center', marginRight: 'auto' }}>
          <Title level={4} style={{ color: 'white', margin: 0 }}>
            {t('header.title')}
          </Title>
        </div>

        <Space size="middle">
          <LanguageSwitcher style={{ color: 'white' }} />

          <a
            href="https://github.com/gemini-poise/gemini-poise"
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
            <a
              onClick={handleUsernameClick}
              style={{ 
                color: 'white',
                cursor: 'pointer',
                textDecoration: 'none'
              }}
            >
              <Space>
                <UserOutlined />
                <span>{user.username}</span>
              </Space>
            </a>
          )}

          <a
            onClick={handleLogout}
            style={{ color: 'white' }}
          >
            <Space>
              <LogoutOutlined />
              <span>{t('header.logout')}</span>
            </Space>
          </a>
        </Space>
      </AntHeader>

      <Modal
        title={t('header.changePassword')}
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
            label={t('header.currentPassword')}
            name="currentPassword"
            rules={[
              { required: true, message: t('header.currentPasswordRequired') }
            ]}
          >
            <Input.Password placeholder={t('header.enterCurrentPassword')} />
          </Form.Item>

          <Form.Item
            label={t('header.newPassword')}
            name="newPassword"
            rules={[
              { required: true, message: t('header.newPasswordRequired') },
              { min: 6, message: t('header.passwordMinLength') }
            ]}
          >
            <Input.Password placeholder={t('header.enterNewPassword')} />
          </Form.Item>

          <Form.Item
            label={t('header.confirmNewPassword')}
            name="confirmPassword"
            dependencies={['newPassword']}
            rules={[
              { required: true, message: t('header.confirmPasswordRequired') },
              ({ getFieldValue }) => ({
                validator(_, value) {
                  if (!value || getFieldValue('newPassword') === value) {
                    return Promise.resolve();
                  }
                  return Promise.reject(new Error(t('header.passwordsNotMatch')));
                },
              }),
            ]}
          >
            <Input.Password placeholder={t('header.enterNewPasswordAgain')} />
          </Form.Item>

          <Form.Item style={{ marginBottom: 0, marginTop: 24 }}>
            <Space style={{ width: '100%', justifyContent: 'flex-end' }}>
              <Button onClick={handlePasswordModalCancel}>
                {t('common.cancel')}
              </Button>
              <Button type="primary" htmlType="submit" loading={loading}>
                {t('common.confirm')}
              </Button>
            </Space>
          </Form.Item>
        </Form>
      </Modal>
    </>
  );
};

export default Header;
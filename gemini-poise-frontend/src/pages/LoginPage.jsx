import React, { useCallback, useMemo } from 'react';
import {Button, Card, Checkbox, Form, Input, Layout, Space, Typography, message} from 'antd';
import {LockOutlined, UserOutlined, DownloadOutlined} from '@ant-design/icons';
import {useTranslation} from 'react-i18next';
import LanguageSwitcher from '../components/LanguageSwitcher';
import {useLogin} from '../hooks/useLogin';
import useBingWallpaper from '../hooks/useBingWallpaper';

const {Title} = Typography;
const {Content} = Layout;

const LoginPage = () => {
  const [form] = Form.useForm();
  const {t} = useTranslation();
  const {loading, handleLogin, rememberedUsername} = useLogin(form, t);
  const {wallpaperUrl, isLoading: wallpaperLoading} = useBingWallpaper();

  const handleDownloadWallpaper = useCallback(async () => {
    if (!wallpaperUrl) return;
    
    try {
      message.loading({
        content: t('wallpaper.downloading'), 
        key: 'download'
      });
      
      const response = await fetch(wallpaperUrl);
      if (!response.ok) {
        throw new Error('Download failed');
      }
      
      const blob = await response.blob();
      const url = window.URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = url;
      
      // Generate filename with today's date
      const today = new Date();
      const dateString = `${today.getFullYear()}-${String(today.getMonth() + 1).padStart(2, '0')}-${String(today.getDate()).padStart(2, '0')}`;
      link.download = `bing-wallpaper-${dateString}.jpg`;
      
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
      window.URL.revokeObjectURL(url);
      
      message.success({
        content: t('wallpaper.downloadSuccess'), 
        key: 'download'
      });
    } catch (error) {
      console.error('Download failed:', error);
      message.error({
        content: t('wallpaper.downloadError'), 
        key: 'download'
      });
    }
  }, [wallpaperUrl, t]);

  const backgroundStyle = useMemo(() => {
    return wallpaperUrl ? {
      backgroundImage: `url(${wallpaperUrl})`,
      backgroundSize: 'cover',
      backgroundPosition: 'center',
      backgroundRepeat: 'no-repeat'
    } : {};
  }, [wallpaperUrl]);

  const formInitialValues = useMemo(() => ({
    username: rememberedUsername || '',
    password: '',
    remember: true,
  }), [rememberedUsername]);

  const usernameRules = useMemo(() => ([{
    required: true,
    message: t('login.usernameRequired'),
    whitespace: true
  }]), [t]);

  const passwordRules = useMemo(() => ([{
    required: true,
    message: t('login.passwordRequired'),
    whitespace: true
  }]), [t]);

  return (
    <Layout 
      className="h-screen flex flex-col justify-center items-center bg-gray-100 relative" 
      style={backgroundStyle}
    >
      {/* Light frosted glass overlay for the entire screen */}
      <div 
        className="absolute inset-0 z-0"
        style={{
          backdropFilter: 'blur(2px)',
          backgroundColor: 'rgba(255, 255, 255, 0.1)'
        }}
      />
      
      {/* Language switcher */}
      <div style={{position: 'absolute', top: '20px', right: '20px', zIndex: 1000}}>
        <div 
          className="p-2 rounded-lg"
          style={{
            backdropFilter: 'blur(8px)',
            backgroundColor: 'rgba(255, 255, 255, 0.8)'
          }}
        >
          <Space>
            <Typography.Text type="secondary">
              {t('language.switch')}:
            </Typography.Text>
            <LanguageSwitcher/>
          </Space>
        </div>
      </div>
      
      {/* Download wallpaper button */}
      <div style={{position: 'absolute', bottom: '20px', right: '20px', zIndex: 1000}}>
        <Button 
          type="default" 
          shape="circle"
          size="large"
          icon={<DownloadOutlined />}
          onClick={handleDownloadWallpaper}
          disabled={!wallpaperUrl || wallpaperLoading}
          loading={wallpaperLoading}
          style={{
            backdropFilter: 'blur(8px)',
            backgroundColor: 'rgba(255, 255, 255, 0.8)',
            border: 'none',
            boxShadow: '0 4px 12px rgba(0, 0, 0, 0.1)'
          }}
          title={t('wallpaper.download')}
        />
      </div>
      
      {/* Login form */}
      <Content className="w-full max-w-md p-4 flex flex-col justify-center relative z-10">
        <Card 
          className="shadow-lg rounded-lg border-0"
          style={{
            backdropFilter: 'blur(6px)',
            backgroundColor: 'rgba(255, 255, 255, 0.4)'
          }}
        >
          <div className="text-center mb-6">
            <Title level={2} className="m-0">
              {t('login.title')}
            </Title>
            <Typography.Text type="secondary">
              {t('login.subtitle')}
            </Typography.Text>
          </div>
          
          <Form
            form={form}
            name="login_form"
            initialValues={formInitialValues}
            onFinish={handleLogin}
            autoComplete="on"
          >
            <Form.Item
              name="username"
              rules={usernameRules}
            >
              <Input
                prefix={<UserOutlined className="site-form-item-icon"/>}
                placeholder={t('login.username')}
                autoComplete="username"
              />
            </Form.Item>

            <Form.Item
              name="password"
              rules={passwordRules}
            >
              <Input.Password
                prefix={<LockOutlined className="site-form-item-icon"/>}
                placeholder={t('login.password')}
                autoComplete="current-password"
              />
            </Form.Item>

            <Form.Item>
              <Form.Item name="remember" valuePropName="checked" noStyle>
                <Checkbox>{t('login.rememberMe')}</Checkbox>
              </Form.Item>
            </Form.Item>

            <Form.Item>
              <Button
                type="primary"
                htmlType="submit"
                className="w-full"
                loading={loading}
              >
                {t('login.loginButton')}
              </Button>
            </Form.Item>
          </Form>
        </Card>
      </Content>
    </Layout>
  );
};

export default LoginPage;


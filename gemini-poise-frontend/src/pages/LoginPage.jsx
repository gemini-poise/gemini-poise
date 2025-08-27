import {Button, Card, Checkbox, Form, Input, Layout, Space, Typography} from 'antd';
import {LockOutlined, UserOutlined} from '@ant-design/icons';
import {useTranslation} from 'react-i18next';
import LanguageSwitcher from '../components/LanguageSwitcher';
import {useLogin} from '../hooks/useLogin';

const {Title} = Typography;
const {Content} = Layout;

const LoginPage = () => {
  const [form] = Form.useForm();
  const {t} = useTranslation();
  const {loading, handleLogin, rememberedUsername} = useLogin(form, t);

  return (
    <Layout className="h-screen flex flex-col justify-center items-center bg-gray-100 login-background">
      <div style={{position: 'absolute', top: '20px', right: '20px', zIndex: 1000}}>
        <Space>
          <Typography.Text type="secondary">{t('language.switch')}:</Typography.Text>
          <LanguageSwitcher/>
        </Space>
      </div>
      <Content className="w-full max-w-md p-4 flex flex-col justify-center">
        <Card className="shadow-lg rounded-lg">
          <div className="text-center mb-6">
            <Title level={2} className="m-0">{t('login.title')}</Title>
            <Typography.Text type="secondary">{t('login.subtitle')}</Typography.Text>
          </div>
          <Form
            form={form}
            name="login_form"
            initialValues={{
              username: rememberedUsername || '',
              password: '',
              remember: true,
            }}
            onFinish={handleLogin}
            autoComplete="on"
          >
            <Form.Item
              name="username"
              rules={[{
                required: true,
                message: t('login.usernameRequired'),
                whitespace: true
              }]}
            >
              <Input
                prefix={<UserOutlined className="site-form-item-icon"/>}
                placeholder={t('login.username')}
                autoComplete="username"
              />
            </Form.Item>

            <Form.Item
              name="password"
              rules={[{
                required: true,
                message: t('login.passwordRequired'),
                whitespace: true
              }]}
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


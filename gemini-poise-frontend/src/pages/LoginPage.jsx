import { Form, Input, Button, Card, Typography, Checkbox, Layout } from 'antd';
import { UserOutlined, LockOutlined } from '@ant-design/icons';
import { useLogin } from '../hooks/useLogin';

const { Title } = Typography;
const { Content } = Layout;

const LoginPage = () => {
  const [form] = Form.useForm();
  const { loading, handleLogin, rememberedUsername } = useLogin(form);

  return (
    <Layout className="h-screen flex flex-col justify-center items-center bg-gray-100 login-background">
      <Content className="w-full max-w-md p-4 flex flex-col justify-center">
        <Card className="shadow-lg rounded-lg">
          <div className="text-center mb-6">
            <Title level={2} className="m-0">Gemini Poise Login</Title>
            <Typography.Text type="secondary">Gemini Proxy Tool</Typography.Text>
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
                message: 'Please input your Username!',
                whitespace: true
              }]}
            >
              <Input
                prefix={<UserOutlined className="site-form-item-icon" />}
                placeholder="Username"
                autoComplete="username"
              />
            </Form.Item>

            <Form.Item
              name="password"
              rules={[{
                required: true,
                message: 'Please input your Password!',
                whitespace: true
              }]}
            >
              <Input.Password
                prefix={<LockOutlined className="site-form-item-icon" />}
                placeholder="Password"
                autoComplete="current-password"
              />
            </Form.Item>

            <Form.Item>
              <Form.Item name="remember" valuePropName="checked" noStyle>
                <Checkbox>Remember me</Checkbox>
              </Form.Item>
            </Form.Item>

            <Form.Item>
              <Button
                type="primary"
                htmlType="submit"
                className="w-full"
                loading={loading}
              >
                Log in
              </Button>
            </Form.Item>
          </Form>
        </Card>
      </Content>
    </Layout>
  );
};

export default LoginPage;


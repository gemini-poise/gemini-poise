import { useEffect } from 'react';
import { Form, Input, Button, Card, Typography, App, Watermark } from 'antd';
import { useConfigManagement } from '../hooks/useConfigManagement';

const { Title } = Typography;

const configDefinitions = [
    { "k": "target_api_url", "l": "Target AI API URL", "required": true, "type": "text" },
    { "k": "api_token", "l": "API Token", "required": true, "type": "password" },
    { "k": "key_validation_interval_seconds", "l": "Key Validation Interval (seconds)", "required": true, "type": "number" },
    { "k": "key_validation_max_failed_count", "l": "Key Validation Max Failed Count", "required": true, "type": "number" },
    { "k": "key_validation_timeout_seconds", "l": "Key Validation Timeout (seconds)", "required": true, "type": "number" },
    { "k": "key_validation_model_name", "l": "Key Validation Model Name", "required": false, "type": "text" },
    // { k: "another_key", l: "Another Label", required: false, type: 'text' },
];

const ConfigPage = () => {
    const [form] = Form.useForm();
    const { loading, saving, fetchConfig, saveConfig } = useConfigManagement(configDefinitions);

    useEffect(() => {
        fetchConfig(form);
    }, [fetchConfig, form]);

    const onFinish = async (values) => {
        await saveConfig(values, form);
    };

    return (
        <App> {/* App context is still needed here */}
            <Watermark content="Gemini Poise Config">
                <div className="flex justify-center">
                    <Card className="w-full max-w-xl" hoverable>
                        <Title level={2} className="text-center">Configuration</Title>
                        <Form
                            form={form}
                            layout="vertical"
                            name="config"
                            onFinish={onFinish}
                            autoComplete="off"
                            disabled={loading}
                        >
                            {configDefinitions.map(item => (
                                <Form.Item
                                    key={item.k}
                                    label={item.l}
                                    name={item.k}
                                    rules={[{ required: item.required, message: `Please input the ${item.l}!` }]}
                                >
                                    {item.type === 'password' ? (
                                        <Input.Password />
                                    ) : (
                                        <Input type={item.type} showCount />
                                    )}
                                </Form.Item>
                            ))}
                            <Form.Item>
                                <Button type="primary" htmlType="submit" className="w-full"
                                    loading={saving}>
                                    Save Configuration
                                </Button>
                            </Form.Item>
                        </Form>
                    </Card>
                </div>
            </Watermark>
        </App>
    );
};

export default ConfigPage;

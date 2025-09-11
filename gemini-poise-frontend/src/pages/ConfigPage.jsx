import {useEffect, useMemo} from 'react';
import {App, Button, Card, Form, Input, Typography, Watermark} from 'antd';
import {useTranslation} from 'react-i18next';
import {useConfigManagement} from '../hooks/useConfigManagement';

const {Title} = Typography;

const getConfigDefinitions = (t) => [
  {"k": "target_api_url", "l": t('config.targetApiUrl'), "required": true, "type": "text"},
  {"k": "api_token", "l": t('config.apiToken'), "required": true, "type": "password"},
  {"k": "key_validation_active_interval_seconds", "l": t('config.keyValidationActiveInterval'), "required": true, "type": "number"},
  {"k": "key_validation_exhausted_interval_seconds", "l": t('config.keyValidationExhaustedInterval'), "required": false, "type": "number"},
  {"k": "key_validation_error_interval_seconds", "l": t('config.keyValidationErrorInterval'), "required": false, "type": "number"},
  {"k": "key_validation_max_failed_count", "l": t('config.keyValidationMaxFailedCount'), "required": true, "type": "number"},
  {"k": "key_validation_timeout_seconds", "l": t('config.keyValidationTimeout'), "required": true, "type": "number"},
  {"k": "key_validation_model_name", "l": t('config.keyValidationModelName'), "required": false, "type": "text"},
  {"k": "key_validation_concurrent_count", "l": t('config.keyValidationConcurrentCount'), "required": false, "type": "number"},
  {"k": "proxy_retry_max_count", "l": t('config.proxyRetryMaxCount'), "required": false, "type": "number"},
];

const ConfigPage = () => {
  const [form] = Form.useForm();
  const {t} = useTranslation();
  const configDefinitions = useMemo(() => getConfigDefinitions(t), [t]);
  const {loading, saving, fetchConfig, saveConfig} = useConfigManagement(configDefinitions, t);

  useEffect(() => {
    fetchConfig(form).catch(console.error);
  }, [fetchConfig, form]);

  const onFinish = async (values) => {
    await saveConfig(values, form);
  };

  return (
    <App>
      <Watermark content={t('config.watermarkText')}>
        <div className="flex justify-center">
          <Card className="w-full max-w-3xl" hoverable>
            <Title level={2} className="text-center">{t('config.title')}</Title>
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
                  rules={[{required: item.required, message: t('config.pleaseInputField', {field: item.l})}]}
                >
                  {item.type === 'password' ? (
                    <Input.Password/>
                  ) : (
                    <Input type={item.type} showCount/>
                  )}
                </Form.Item>
              ))}
              <Form.Item>
                <Button type="primary" htmlType="submit" className="w-full"
                        loading={saving}>
                  {t('config.save')}
                </Button>
              </Form.Item>
            </Form>
          </Card>
        </div>
        <div className='pt-4'></div>
      </Watermark>
    </App>
  );
};

export default ConfigPage;

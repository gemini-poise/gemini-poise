import { Result, Button, Space, Typography } from 'antd';
import { Link } from 'react-router';
import LanguageSwitcher from '../components/LanguageSwitcher';
import { useTranslation } from 'react-i18next';

const NotFoundPage = () => {
  const { t } = useTranslation();
  return (
    <div className="flex justify-center items-center min-h-screen bg-gray-100">
      <div style={{ position: 'absolute', top: '20px', right: '20px' }}>
        <Space>
          <Typography.Text type="secondary">{t('language.switch')}:</Typography.Text>
          <LanguageSwitcher />
        </Space>
      </div>
      <div style={{ position: 'relative', width: '100%', maxWidth: '600px' }}>
        <Result
          status="404"
          title={t('notFound.title')}
          subTitle={t('notFound.subtitle')}
          extra={
            <Button type="primary">
              <Link to="/">{t('notFound.backHome')}</Link>
            </Button>
          }
        />
      </div>
    </div>
  );
};

export default NotFoundPage;

import { Typography, Card } from 'antd';
import { useTranslation } from 'react-i18next';

const { Title, Paragraph } = Typography;

const AboutPage = () => {
  const { t } = useTranslation();
  return (
    <div style={{ padding: '24px' }}>
      <Card hoverable>
        <Title level={4}>{t('about.title')}</Title>
        <Paragraph>
          {t('about.intro')}
        </Paragraph>
        <Paragraph>
          {t('about.featuresTitle')}
          <ul>
            <li>{t('about.feature1')}</li>
            <li>{t('about.feature2')}</li>
            <li>{t('about.feature3')}</li>
            <li>{t('about.feature4')}</li>
            <li>{t('about.feature5')}</li>
          </ul>
        </Paragraph>
        <Paragraph>
          {t('about.goal')}
        </Paragraph>
        <Paragraph>
          {t('about.contact')}
        </Paragraph>
      </Card>
    </div>
  );
};

export default AboutPage;
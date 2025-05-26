import { Typography, Card } from 'antd';

const { Title, Paragraph } = Typography;

const AboutPage = () => {
  return (
    <div style={{ padding: '24px' }}>
      <Card>
        <Title level={4}>About Gemini Poise</Title>
        <Paragraph>
          Gemini Poise is an application for managing and proxying Gemini API keys. It provides a user-friendly interface that allows you to add, manage, and monitor the usage of your Gemini API keys.
        </Paragraph>
        <Paragraph>
          Key features include:
          <ul>
            <li>Centralized management of multiple Gemini API keys</li>
            <li>Automatic rotation and usage of active API keys</li>
            <li>Monitoring of API key usage statistics and status</li>
            <li>Supports request proxying in OpenAI format and Gemini native format</li>
            <li>Supports streaming responses</li>
          </ul>
        </Paragraph>
        <Paragraph>
          The goal of this project is to simplify the management of Gemini API keys and improve API availability and stability.
        </Paragraph>
        <Paragraph>
          If you have any questions or suggestions, feel free to ask.
        </Paragraph>
      </Card>
    </div>
  );
};

export default AboutPage;
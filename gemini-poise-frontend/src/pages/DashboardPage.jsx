import { Card, Col, Row, Statistic, Spin, Alert } from 'antd';
import CountUp from 'react-countup';
import { Line } from 'react-chartjs-2';
import { useTranslation } from 'react-i18next';
import {
  Chart as ChartJS,
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  Title,
  Tooltip,
  Legend,
} from 'chart.js';
import { useKeyStatistics, useApiCallStatistics, useApiCallLogsByMinute } from '../hooks/useApiStatistics';

ChartJS.register(
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  Title,
  Tooltip,
  Legend
);

const DashboardPage = () => {
  const { t } = useTranslation();
  const { totalKeys, activeKeys, exhaustedKeys, backendErrorKeys, loadingKeys, errorFetchingKeys } = useKeyStatistics();
  const { callsLast1Minute, callsLast1Hour, callsLast24Hours, monthlyUsage, loadingCalls, errorCalls } = useApiCallStatistics();
  const { apiCallLogs, loadingApiCallLogs, errorApiCallLogs } = useApiCallLogsByMinute(24);

  const renderStatisticValue = (value, isLoading, isError) => {
    if (isLoading) {
      return <Spin size="small" />;
    }
    if (isError) {
      return 'N/A';
    }
    return <CountUp end={value} duration={1.5} />;
  };

  return (
    <div>
      <Row gutter={16}>
        <Col span={12}>
          <Card
            variant="borderless"
            hoverable
            title={
              <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                <span>{t('dashboard.keyStatistics')}</span>
                <span>{t('dashboard.total')}: {renderStatisticValue(totalKeys, loadingKeys, errorFetchingKeys)}</span>
              </div>
            }
          >
            {errorFetchingKeys && <Alert message={errorFetchingKeys} type="error" showIcon />}
            <Statistic
              title={t('dashboard.activeKeys')}
              value={activeKeys}
              valueStyle={{ color: '#3f8600' }}
              formatter={(value) => renderStatisticValue(value, loadingKeys, errorFetchingKeys)}
            />
            <Statistic
              title={t('dashboard.exhaustedKeys')}
              value={exhaustedKeys}
              valueStyle={{ color: '#faad14' }}
              formatter={(value) => renderStatisticValue(value, loadingKeys, errorFetchingKeys)}
            />
            <Statistic
              title={t('dashboard.errorKeys')}
              value={backendErrorKeys}
              valueStyle={{ color: '#cf1322' }}
              formatter={(value) => renderStatisticValue(value, loadingKeys, errorFetchingKeys)}
            />
          </Card>
        </Col>
        <Col span={12}>
          <Card
            variant="borderless"
            hoverable
            title={
              <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                <span>{t('dashboard.apiCallStatistics')}</span>
                <span>{t('dashboard.monthlyUsage')}: {renderStatisticValue(monthlyUsage, loadingCalls, errorCalls)}</span>
              </div>
            }
          >
            {errorCalls && <Alert message={errorCalls} type="error" showIcon />}
            <Statistic
              title={t('dashboard.oneMinuteCalls')}
              value={callsLast1Minute}
              formatter={(value) => renderStatisticValue(value, loadingCalls, errorCalls)}
            />
            <Statistic
              title={t('dashboard.oneHourCalls')}
              value={callsLast1Hour}
              formatter={(value) => renderStatisticValue(value, loadingCalls, errorCalls)}
            />
            <Statistic
              title={t('dashboard.twentyFourHourCalls')}
              value={callsLast24Hours}
              formatter={(value) => renderStatisticValue(value, loadingCalls, errorCalls)}
            />
          </Card>
        </Col>
      </Row>
      <Row gutter={16} style={{ marginTop: 16 }}>
        <Col span={24}>
          <Card
            variant="borderless"
            hoverable
            title={t('dashboard.apiCallTrends')}
          >
            {loadingApiCallLogs && <Spin />}
            {errorApiCallLogs && <Alert message={errorApiCallLogs} type="error" showIcon />}
            {!loadingApiCallLogs && !errorApiCallLogs && (
              <Line data={processApiCallLogs(apiCallLogs)} options={chartOptions(t)} />
            )}
          </Card>
        </Col>
      </Row>
    </div>
  );
};

const processApiCallLogs = (logs) => {
  const dataMap = new Map();

  logs.forEach(log => {
    const timestamp = new Date(log.timestamp).toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit', hour12: false });
    if (!dataMap.has(timestamp)) {
      dataMap.set(timestamp, new Map());
    }
    dataMap.get(timestamp).set(log.api_key_id, log.call_count);
  });

  const labels = Array.from(dataMap.keys()).sort();
  const datasets = [];
  const keyColors = {};

  const uniqueKeyIds = new Set();
  logs.forEach(log => uniqueKeyIds.add(log.api_key_id));

  Array.from(uniqueKeyIds).forEach(keyId => {
    keyColors[keyId] = `rgba(${Math.floor(Math.random() * 255)}, ${Math.floor(Math.random() * 255)}, ${Math.floor(Math.random() * 255)}, 0.8)`;
  });

  uniqueKeyIds.forEach(keyId => {
    const data = labels.map(label => {
      const keyData = dataMap.get(label);
      return keyData ? keyData.get(keyId) || 0 : 0;
    });

    const key_value = logs.find(log => log.api_key_id === keyId)?.key_value || `Key ID: ${keyId}`;

    datasets.push({
      label: key_value.substring(0, 8) + '...',
      data: data,
      borderColor: keyColors[keyId],
      backgroundColor: keyColors[keyId].replace('0.8', '0.2'),
      fill: false,
      tension: 0.1,
    });
  });

  return {
    labels,
    datasets,
  };
};

const chartOptions = (t) => ({
  responsive: true,
  plugins: {
    legend: {
      position: 'top',
    },
    title: {
      display: true,
      text: t('dashboard.apiCallsPerMinute'),
    },
  },
  scales: {
    x: {
      title: {
        display: true,
        text: t('dashboard.time'),
      },
    },
    y: {
      title: {
        display: true,
        text: t('dashboard.callCount'),
      },
      beginAtZero: true,
    },
  },
});

export default DashboardPage;

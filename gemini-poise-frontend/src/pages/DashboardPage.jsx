import { Card, Col, Row, Statistic, Spin, Alert } from 'antd';
import CountUp from 'react-countup';
import { Line } from 'react-chartjs-2';
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
  const { totalKeys, validKeys, invalidKeys, loadingKeys, errorKeys } = useKeyStatistics();
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
                <span>Key Statistics</span>
                <span>Total: {renderStatisticValue(totalKeys, loadingKeys, errorKeys)}</span>
              </div>
            }
          >
            {errorKeys && <Alert message={errorKeys} type="error" showIcon />}
            <Statistic
              title="Total Keys"
              value={totalKeys}
              formatter={(value) => renderStatisticValue(value, loadingKeys, errorKeys)}
            />
            <Statistic
              title="Valid Keys"
              value={validKeys}
              valueStyle={{ color: '#3f8600' }}
              formatter={(value) => renderStatisticValue(value, loadingKeys, errorKeys)}
            />
            <Statistic
              title="Invalid Keys"
              value={invalidKeys}
              valueStyle={{ color: '#cf1322' }}
              formatter={(value) => renderStatisticValue(value, loadingKeys, errorKeys)}
            />
          </Card>
        </Col>
        <Col span={12}>
          <Card
            variant="borderless"
            hoverable
            title={
              <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                <span>API Call Statistics</span>
                <span>Monthly Usage: {renderStatisticValue(monthlyUsage, loadingCalls, errorCalls)}</span>
              </div>
            }
          >
            {errorCalls && <Alert message={errorCalls} type="error" showIcon />}
            <Statistic
              title="1 Minute Calls"
              value={callsLast1Minute}
              formatter={(value) => renderStatisticValue(value, loadingCalls, errorCalls)}
            />
            <Statistic
              title="1 Hour Calls"
              value={callsLast1Hour}
              formatter={(value) => renderStatisticValue(value, loadingCalls, errorCalls)}
            />
            <Statistic
              title="24 Hour Calls"
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
            title="API Call Trends (Last 24 Hours)"
          >
            {loadingApiCallLogs && <Spin />}
            {errorApiCallLogs && <Alert message={errorApiCallLogs} type="error" showIcon />}
            {!loadingApiCallLogs && !errorApiCallLogs && (
              <Line data={processApiCallLogs(apiCallLogs)} options={chartOptions} />
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

const chartOptions = {
  responsive: true,
  plugins: {
    legend: {
      position: 'top',
    },
    title: {
      display: true,
      text: 'API Calls Per Minute by Key',
    },
  },
  scales: {
    x: {
      title: {
        display: true,
        text: 'Time (Minute)',
      },
    },
    y: {
      title: {
        display: true,
        text: 'Call Count',
      },
      beginAtZero: true,
    },
  },
};

export default DashboardPage;

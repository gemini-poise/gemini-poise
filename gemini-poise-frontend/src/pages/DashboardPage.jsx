import { Card, Col, Row, Statistic, Spin, Alert } from 'antd';
import CountUp from 'react-countup';
import { useKeyStatistics, useApiCallStatistics } from '../hooks/useApiStatistics';

const DashboardPage = () => {
  const { totalKeys, validKeys, invalidKeys, loadingKeys, errorKeys } = useKeyStatistics();
  const { callsLast1Minute, callsLast1Hour, callsLast24Hours, monthlyUsage, loadingCalls, errorCalls } = useApiCallStatistics();

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
  );
};

export default DashboardPage;

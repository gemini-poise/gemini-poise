import { Alert, Card, Col, Row, Spin, Statistic } from 'antd';
import CountUp from 'react-countup';
import { Line } from 'react-chartjs-2';
import { useTranslation } from 'react-i18next';
import { CategoryScale, Chart as ChartJS, Legend, LinearScale, LineElement, PointElement, Title, Tooltip, } from 'chart.js';
import { useApiCallStatistics, useKeyStatistics, useKeySurvivalStatistics } from '../hooks/useApiStatistics';

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
  const {t} = useTranslation();
  const {totalKeys, activeKeys, exhaustedKeys, backendErrorKeys, loadingKeys, errorFetchingKeys} = useKeyStatistics();
  const {callsLast1Minute, callsLast1Hour, callsLast24Hours, monthlyUsage, loadingCalls, errorCalls} = useApiCallStatistics();
  const {keySurvivalStatistics, loadingKeySurvival, errorKeySurvival} = useKeySurvivalStatistics();

  const renderStatisticValue = (value, isLoading, isError) => {
    if (isLoading) {
      return <Spin size="small"/>;
    }
    if (isError) {
      return 'N/A';
    }
    return <CountUp end={value} duration={1.5}/>;
  };

  return (
    <div>
      <Row gutter={16}>
        <Col span={12}>
          <Card
            variant="borderless"
            hoverable
            title={
              <div style={{display: 'flex', justifyContent: 'space-between'}}>
                <span>{t('dashboard.keyStatistics')}</span>
                <span>{t('dashboard.total')}: {renderStatisticValue(totalKeys, loadingKeys, errorFetchingKeys)}</span>
              </div>
            }
          >
            {errorFetchingKeys && <Alert message={errorFetchingKeys} type="error" showIcon/>}
            <Statistic
              title={t('dashboard.activeKeys')}
              value={activeKeys}
              valueStyle={{color: '#3f8600'}}
              formatter={(value) => renderStatisticValue(value, loadingKeys, errorFetchingKeys)}
            />
            <Statistic
              title={t('dashboard.exhaustedKeys')}
              value={exhaustedKeys}
              valueStyle={{color: '#faad14'}}
              formatter={(value) => renderStatisticValue(value, loadingKeys, errorFetchingKeys)}
            />
            <Statistic
              title={t('dashboard.errorKeys')}
              value={backendErrorKeys}
              valueStyle={{color: '#cf1322'}}
              formatter={(value) => renderStatisticValue(value, loadingKeys, errorFetchingKeys)}
            />
          </Card>
        </Col>
        <Col span={12}>
          <Card
            variant="borderless"
            hoverable
            title={
              <div style={{display: 'flex', justifyContent: 'space-between'}}>
                <span>{t('dashboard.apiCallStatistics')}</span>
                <span>{t('dashboard.monthlyUsage')}: {renderStatisticValue(monthlyUsage, loadingCalls, errorCalls)}</span>
              </div>
            }
          >
            {errorCalls && <Alert message={errorCalls} type="error" showIcon/>}
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
      <Row gutter={16} style={{marginTop: 16}}>
        <Col span={24}>
          <Card
            variant="borderless"
            hoverable
            title={t('dashboard.keySurvivalTrends')}
          >
            {loadingKeySurvival && <Spin/>}
            {errorKeySurvival && <Alert message={errorKeySurvival} type="error" showIcon/>}
            {!loadingKeySurvival && !errorKeySurvival && (
              <Line data={processKeySurvivalStatistics(keySurvivalStatistics, t)} options={keySurvivalChartOptions(t)}/>
            )}
          </Card>
        </Col>
      </Row>
    </div>
  );
};

const processKeySurvivalStatistics = (statistics, t) => {
  if (!statistics || statistics.length === 0) {
    return {
      labels: [],
      datasets: []
    };
  }

  const labels = statistics.map(stat => {
    const date = new Date(stat.timestamp);
    return date.toLocaleString(undefined, {
      month: '2-digit',
      day: '2-digit',
      hour: '2-digit',
      minute: '2-digit'
    });
  });

  const activeData = statistics.map(stat => stat.active_keys);
  const exhaustedData = statistics.map(stat => stat.exhausted_keys);
  const errorData = statistics.map(stat => stat.error_keys);
  const totalData = statistics.map(stat => stat.total_keys);

  return {
    labels,
    datasets: [
      {
        label: t('dashboard.totalKeys'),
        data: totalData,
        borderColor: 'rgba(24, 144, 255, 0.8)',
        backgroundColor: 'rgba(24, 144, 255, 0.2)',
        fill: false,
        tension: 0.1,
        hidden: true,
      },
      {
        label: t('dashboard.activeKeys'),
        data: activeData,
        borderColor: 'rgba(63, 134, 0, 0.8)',
        backgroundColor: 'rgba(63, 134, 0, 0.2)',
        fill: false,
        tension: 0.1,
      },
      {
        label: t('dashboard.exhaustedKeys'),
        data: exhaustedData,
        borderColor: 'rgba(250, 173, 20, 0.8)',
        backgroundColor: 'rgba(250, 173, 20, 0.2)',
        fill: false,
        tension: 0.1,
      },
      {
        label: t('dashboard.errorKeys'),
        data: errorData,
        borderColor: 'rgba(207, 19, 34, 0.8)',
        backgroundColor: 'rgba(207, 19, 34, 0.2)',
        fill: false,
        tension: 0.1,
      }
    ],
  };
};

const keySurvivalChartOptions = (t) => ({
  responsive: true,
  plugins: {
    legend: {
      position: 'top',
    },
    title: {
      display: true,
      text: t('dashboard.keySurvivalOverTime'),
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
        text: t('dashboard.keyCount'),
      },
      beginAtZero: true,
    },
  },
});

export default DashboardPage;

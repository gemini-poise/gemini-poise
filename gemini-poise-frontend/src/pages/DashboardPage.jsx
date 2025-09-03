import {Card, Col, Row, Statistic, Spin, Alert, DatePicker, ConfigProvider} from 'antd';
import enUS from 'antd/es/locale/en_US';
import zhCN from 'antd/es/locale/zh_CN';
import CountUp from 'react-countup';
import {Line} from 'react-chartjs-2';
import {useTranslation} from 'react-i18next';
import {
    Chart as ChartJS,
    CategoryScale, // 类别轴
    LinearScale,   // 线性轴
    PointElement,  // 点元素
    LineElement,   // 线元素
    Title,         // 标题
    Tooltip,       // 工具提示
    Legend,        // 图例
    TimeScale,     // 时间轴
    TimeSeriesScale, // 时间序列轴
} from 'chart.js';
import 'chartjs-adapter-date-fns';
import {useKeyStatistics, useApiCallStatistics, useKeySurvivalStatistics} from '../hooks/useApiStatistics';
import {useState, useMemo} from "react";
import dayjs from 'dayjs';

// 注册 Chart.js 所需组件
ChartJS.register(
    CategoryScale,
    LinearScale,
    PointElement,
    LineElement,
    Title,
    Tooltip,
    Legend,
    TimeScale,
    TimeSeriesScale
);


// 仪表盘页面组件
const DashboardPage = () => {
    // 使用翻译 hook
    const {t, i18n} = useTranslation();
    const currentLocale = i18n.language === 'zh' ? zhCN : enUS;
    const [selectedStartTime, setSelectedStartTime] = useState(() => dayjs().subtract(12, 'hour').toDate());
    const [selectedEndTime, setSelectedEndTime] = useState(() => dayjs().toDate());

    const { startTime, endTime } = useMemo(() => {
        return { startTime: selectedStartTime, endTime: selectedEndTime };
    }, [selectedStartTime, selectedEndTime]);

    // 获取 Key 统计数据
    const {totalKeys, activeKeys, exhaustedKeys, backendErrorKeys, loadingKeys, errorFetchingKeys} = useKeyStatistics();
    // 获取 API 调用统计数据
    const {
        callsLast1Minute,
        callsLast1Hour,
        callsLast24Hours,
        monthlyUsage,
        loadingCalls,
        errorCalls
    } = useApiCallStatistics();
    // 获取 Key 生存统计数据
    const {keySurvivalStatistics, loadingKeySurvival, errorKeySurvival} = useKeySurvivalStatistics(startTime, endTime);

    // 渲染统计值的函数，处理加载和错误状态
    const renderStatisticValue = (value, isLoading, isError) => {
        if (isLoading) {
            return <Spin size="small"/>; // 加载中显示加载动画
        }
        if (isError) {
            return 'N/A'; // 错误时显示 N/A
        }
        return <CountUp end={value} duration={1.5}/>; // 正常显示数字动画
    };

    return (
        <ConfigProvider locale={currentLocale}>
            <div>
            {/* 第一行：Key 统计和 API 调用统计 */}
            <Row gutter={16}>
                {/* Key 统计卡片 */}
                <Col span={12}>
                    <Card
                        variant="borderless"
                        hoverable
                        title={
                            <div style={{display: 'flex', justifyContent: 'space-between'}}>
                                <span>{t('dashboard.keyStatistics')}</span> {/* Key 统计标题 */}
                                <span>{t('dashboard.total')}: {renderStatisticValue(totalKeys, loadingKeys, errorFetchingKeys)}</span> {/* 总 Key 数量 */}
                            </div>
                        }
                    >
                        {/* Key 统计错误提示 */}
                        {errorFetchingKeys && <Alert message={errorFetchingKeys} type="error" showIcon/>}
                        {/* 活跃 Key 统计 */}
                        <Statistic
                            title={t('dashboard.activeKeys')}
                            value={activeKeys}
                            valueStyle={{color: '#3f8600'}}
                            formatter={(value) => renderStatisticValue(value, loadingKeys, errorFetchingKeys)}
                        />
                        {/* 已耗尽 Key 统计 */}
                        <Statistic
                            title={t('dashboard.exhaustedKeys')}
                            value={exhaustedKeys}
                            valueStyle={{color: '#faad14'}}
                            formatter={(value) => renderStatisticValue(value, loadingKeys, errorFetchingKeys)}
                        />
                        {/* 错误 Key 统计 */}
                        <Statistic
                            title={t('dashboard.errorKeys')}
                            value={backendErrorKeys}
                            valueStyle={{color: '#cf1322'}}
                            formatter={(value) => renderStatisticValue(value, loadingKeys, errorFetchingKeys)}
                        />
                    </Card>
                </Col>
                {/* API 调用统计卡片 */}
                <Col span={12}>
                    <Card
                        variant="borderless"
                        hoverable
                        title={
                            <div style={{display: 'flex', justifyContent: 'space-between'}}>
                                <span>{t('dashboard.apiCallStatistics')}</span> {/* API 调用统计标题 */}
                                <span>{t('dashboard.monthlyUsage')}: {renderStatisticValue(monthlyUsage, loadingCalls, errorCalls)}</span> {/* 月度使用量 */}
                            </div>
                        }
                    >
                        {/* API 调用统计错误提示 */}
                        {errorCalls && <Alert message={errorCalls} type="error" showIcon/>}
                        {/* 过去 1 分钟调用量 */}
                        <Statistic
                            title={t('dashboard.oneMinuteCalls')}
                            value={callsLast1Minute}
                            formatter={(value) => renderStatisticValue(value, loadingCalls, errorCalls)}
                        />
                        {/* 过去 1 小时调用量 */}
                        <Statistic
                            title={t('dashboard.oneHourCalls')}
                            value={callsLast1Hour}
                            formatter={(value) => renderStatisticValue(value, loadingCalls, errorCalls)}
                        />
                        {/* 过去 24 小时调用量 */}
                        <Statistic
                            title={t('dashboard.twentyFourHourCalls')}
                            value={callsLast24Hours}
                            formatter={(value) => renderStatisticValue(value, loadingCalls, errorCalls)}
                        />
                    </Card>
                </Col>
            </Row>
            {/* 第二行：Key 生存趋势图表 */}
            <Row gutter={16} style={{marginTop: 16}}>
                <Col span={24}>
                    <Card
                        variant="borderless"
                        hoverable
                        title={
                            <div style={{display: 'flex', justifyContent: 'space-between', alignItems: 'center'}}>
                                <span>{t('dashboard.keySurvivalTrends')}</span> {/* Key 生存趋势标题 */}
                                <DatePicker.RangePicker
                                    showTime
                                    value={[dayjs(selectedStartTime), dayjs(selectedEndTime)]}
                                    presets={[
                                        {
                                            label: t('dashboard.last12Hours'),
                                            value: [dayjs().subtract(12, 'hour'), dayjs()],
                                        },
                                        {
                                            label: t('dashboard.last1Day'),
                                            value: [dayjs().subtract(1, 'day'), dayjs()],
                                        },
                                        {
                                            label: t('dashboard.last3Days'),
                                            value: [dayjs().subtract(3, 'day'), dayjs()],
                                        },
                                        {
                                            label: t('dashboard.last7Days'),
                                            value: [dayjs().subtract(7, 'day'), dayjs()],
                                        },
                                    ]}
                                    onChange={(dates) => {
                                        if (dates && dates.length === 2) {
                                            setSelectedStartTime(dates[0].toDate());
                                            setSelectedEndTime(dates[1].toDate());
                                        } else {
                                            setSelectedStartTime(dayjs().subtract(12, 'hour').toDate());
                                            setSelectedEndTime(dayjs().toDate());
                                        }
                                    }}
                                />
                            </div>
                        }
                    >
                        {/* Key 生存统计加载中 */}
                        {loadingKeySurvival && <Spin/>}
                        {/* Key 生存统计错误提示 */}
                        {errorKeySurvival && <Alert message={errorKeySurvival} type="error" showIcon/>}
                        {/* Key 生存趋势图表 */}
                        {!loadingKeySurvival && !errorKeySurvival && (
                            <Line data={processKeySurvivalStatistics(keySurvivalStatistics, t)}
                                  options={keySurvivalChartOptions(t, keySurvivalStatistics, startTime, endTime)}/>
                        )}
                    </Card>
                </Col>
            </Row>
        </div>
    </ConfigProvider>
    );
};

// 处理 Key 生存统计数据，转换为 Chart.js 可用的格式
const processKeySurvivalStatistics = (statistics, t) => {
    if (!statistics || statistics.length === 0) {
        return {
            labels: [],
            datasets: []
        };
    }

    // 提取时间戳作为图表标签
    const labels = statistics.map(stat => stat.timestamp);

    // 提取不同 Key 状态的数据
    const activeData = statistics.map(stat => stat.active_keys);
    const exhaustedData = statistics.map(stat => stat.exhausted_keys);
    const errorData = statistics.map(stat => stat.error_keys);
    const totalData = statistics.map(stat => stat.total_keys);

    return {
        labels,
        datasets: [
            {
                label: t('dashboard.totalKeys'), // 总 Key 数量
                data: totalData,
                borderColor: 'rgba(24, 144, 255, 0.8)',
                backgroundColor: 'rgba(24, 144, 255, 0.2)',
                fill: false,
                tension: 0.1,
                hidden: true, // 默认隐藏
            },
            {
                label: t('dashboard.activeKeys'), // 活跃 Key 数量
                data: activeData,
                borderColor: 'rgba(63, 134, 0, 0.8)',
                backgroundColor: 'rgba(63, 134, 0, 0.2)',
                fill: false,
                tension: 0.1,
            },
            {
                label: t('dashboard.exhaustedKeys'), // 已耗尽 Key 数量
                data: exhaustedData,
                borderColor: 'rgba(250, 173, 20, 0.8)',
                backgroundColor: 'rgba(250, 173, 20, 0.2)',
                fill: false,
                tension: 0.1,
            },
            {
                label: t('dashboard.errorKeys'), // 错误 Key 数量
                data: errorData,
                borderColor: 'rgba(207, 19, 34, 0.8)',
                backgroundColor: 'rgba(207, 19, 34, 0.2)',
                fill: false,
                tension: 0.1,
            }
        ],
    };
};

// Key 生存趋势图表的配置选项
const keySurvivalChartOptions = (t, statistics, startTime, endTime) => {
    let unit = 'hour';
    let displayFormats = {
        hour: 'MM/dd HH:mm',
        day: 'MM/dd',
    };

    if (startTime && endTime) {
        const durationMs = endTime.getTime() - startTime.getTime();
        const oneDayMs = 24 * 60 * 60 * 1000;
        const sevenDaysMs = 7 * oneDayMs;

        if (durationMs <= oneDayMs) {
            unit = 'hour';
            displayFormats = {
                minute: 'HH:mm',
                hour: 'MM/dd HH:mm',
                day: 'MM/dd',
            };
        } else if (durationMs <= sevenDaysMs) {
            unit = 'day';
            displayFormats = {
                day: 'MM/dd',
                hour: 'MM/dd HH:mm',
            };
        } else {
            unit = 'week';
            displayFormats = {
                day: 'MM/dd',
                week: 'yyyy-MMM-dd',
            };
        }
    }

    return {
        responsive: true, // 响应式
        plugins: {
            legend: {
                position: 'top', // 图例位置
            },
            title: {
                display: true,
                text: t('dashboard.keySurvivalOverTime'), // 图表标题
            },
        },
        scales: {
            x: {
                type: 'time', // 将 X 轴类型设置为时间轴
                time: {
                    unit: unit, // 时间单位，可以根据数据密度调整，例如 'hour', 'day'
                    tooltipFormat: 'MM/dd HH:mm', // 鼠标悬停时显示的时间格式
                    displayFormats: displayFormats,
                },
                title: {
                    display: true,
                    text: t('dashboard.time'), // X 轴标题
                },
                min: startTime ? startTime.toISOString() : undefined,
                max: endTime ? endTime.toISOString() : undefined,
            },
            y: {
                title: {
                    display: true,
                    text: t('dashboard.keyCount'), // Y 轴标题
                },
                beginAtZero: true, // Y 轴从 0 开始
            },
        },
    };
};

export default DashboardPage;
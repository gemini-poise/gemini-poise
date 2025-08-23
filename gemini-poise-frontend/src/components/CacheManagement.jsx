import React, { useState, useEffect } from 'react';
import { Card, Button, Space, Statistic, Row, Col, Tag, Alert, Spin, App } from 'antd';
import { ReloadOutlined, DeleteOutlined, InfoCircleOutlined, ClearOutlined } from '@ant-design/icons';
import { useTranslation } from 'react-i18next';
import { getCacheStatus, invalidateCache, refreshCache, resetCacheStatistics } from '../api/api';

const CacheManagement = () => {
    const { t } = useTranslation();
    const { message } = App.useApp();
    const [cacheStatus, setCacheStatus] = useState(null);
    const [loading, setLoading] = useState(false);
    const [operationLoading, setOperationLoading] = useState(false);

    const fetchCacheStatus = async () => {
        setLoading(true);
        try {
            const response = await getCacheStatus();
            setCacheStatus(response.data);
        } catch (error) {
            console.error('Failed to fetch cache status:', error);
            message.error(t('cache.fetchStatusError'));
        } finally {
            setLoading(false);
        }
    };

    const handleInvalidateCache = async () => {
        setOperationLoading(true);
        try {
            await invalidateCache();
            message.success(t('cache.invalidateSuccess'));
            await fetchCacheStatus();
        } catch (error) {
            console.error('Failed to invalidate cache:', error);
            message.error(t('cache.invalidateError'));
        } finally {
            setOperationLoading(false);
        }
    };

    const handleRefreshCache = async () => {
        setOperationLoading(true);
        try {
            const response = await refreshCache();
            message.success(t('cache.refreshSuccess', { count: response.data.cached_keys_count }));
            await fetchCacheStatus();
        } catch (error) {
            console.error('Failed to refresh cache:', error);
            message.error(t('cache.refreshError'));
        } finally {
            setOperationLoading(false);
        }
    };

    const handleResetCacheStatistics = async () => {
        setOperationLoading(true);
        try {
            await resetCacheStatistics();
            message.success(t('cache.resetStatsSuccess'));
            await fetchCacheStatus();
        } catch (error) {
            console.error('Failed to reset cache statistics:', error);
            message.error(t('cache.resetStatsError'));
        } finally {
            setOperationLoading(false);
        }
    };

    useEffect(() => {
        fetchCacheStatus();
    }, []);

    const getCacheStatusColor = (status) => {
        return status === 'hit' ? 'success' : 'warning';
    };

    const getCacheAccuracyColor = (accuracy) => {
        return accuracy ? 'success' : 'error';
    };

    return (
        <Card 
            title={
                <Space>
                    <InfoCircleOutlined />
                    {t('cache.title')}
                </Space>
            }
            extra={
                <Button 
                    icon={<ReloadOutlined />} 
                    onClick={fetchCacheStatus}
                    loading={loading}
                    size="small"
                >
                    {t('cache.refresh')}
                </Button>
            }
            size="small"
        >
            {loading ? (
                <div style={{ textAlign: 'center', padding: '20px 0' }}>
                    <Spin size="large" />
                </div>
            ) : cacheStatus ? (
                <>
                    <Alert
                        message={t('cache.description')}
                        type="info"
                        showIcon
                        style={{ marginBottom: 16 }}
                    />
                    
                    <Row gutter={16} style={{ marginBottom: 16 }}>
                        <Col span={6}>
                            <Statistic
                                title={t('cache.status')}
                                value={cacheStatus.cache_status}
                                valueRender={() => (
                                    <Tag color={getCacheStatusColor(cacheStatus.cache_status)}>
                                        {cacheStatus.cache_status === 'hit' ? t('cache.hit') : t('cache.miss')}
                                    </Tag>
                                )}
                            />
                        </Col>
                        <Col span={6}>
                            <Statistic
                                title={t('cache.cachedKeysCount')}
                                value={cacheStatus.cached_keys_count}
                                suffix={t('cache.keys')}
                            />
                        </Col>
                        <Col span={6}>
                            <Statistic
                                title={t('cache.actualKeysCount')}
                                value={cacheStatus.actual_active_keys_count}
                                suffix={t('cache.keys')}
                            />
                        </Col>
                        <Col span={6}>
                            <Statistic
                                title={t('cache.accuracy')}
                                value={cacheStatus.cache_accuracy}
                                valueRender={() => (
                                    <Tag color={getCacheAccuracyColor(cacheStatus.cache_accuracy)}>
                                        {cacheStatus.cache_accuracy ? t('cache.accurate') : t('cache.inaccurate')}
                                    </Tag>
                                )}
                            />
                        </Col>
                    </Row>

                    <Row gutter={16} style={{ marginBottom: 16 }}>
                        <Col span={12}>
                            <Statistic
                                title={t('cache.ttl')}
                                value={cacheStatus.cache_ttl_seconds}
                                suffix={t('cache.seconds')}
                            />
                        </Col>
                        <Col span={12}>
                            <Statistic
                                title={t('cache.hitRate')}
                                value={cacheStatus.statistics?.hit_rate || 0}
                                suffix="%"
                                precision={2}
                                valueStyle={{ 
                                    color: (cacheStatus.statistics?.hit_rate || 0) >= 70 ? '#3f8600' : 
                                           (cacheStatus.statistics?.hit_rate || 0) >= 40 ? '#d48806' : '#cf1322'
                                }}
                            />
                        </Col>
                    </Row>

                    {/* 新增详细统计信息 */}
                    <Row gutter={16} style={{ marginBottom: 16 }}>
                        <Col span={6}>
                            <Statistic
                                title={t('cache.totalRequests')}
                                value={cacheStatus.statistics?.total_requests || 0}
                                valueStyle={{ fontSize: '16px' }}
                            />
                        </Col>
                        <Col span={6}>
                            <Statistic
                                title={t('cache.cacheHits')}
                                value={cacheStatus.statistics?.cache_hits || 0}
                                valueStyle={{ color: '#3f8600', fontSize: '16px' }}
                            />
                        </Col>
                        <Col span={6}>
                            <Statistic
                                title={t('cache.cacheMisses')}
                                value={cacheStatus.statistics?.cache_misses || 0}
                                valueStyle={{ color: '#cf1322', fontSize: '16px' }}
                            />
                        </Col>
                        <Col span={6}>
                            <Statistic
                                title={t('cache.runningHours')}
                                value={cacheStatus.statistics?.duration_hours || 0}
                                suffix={t('cache.hours')}
                                precision={1}
                                valueStyle={{ fontSize: '16px' }}
                            />
                        </Col>
                    </Row>

                    {!cacheStatus.cache_accuracy && (
                        <Alert
                            message={t('cache.inaccuracyWarning')}
                            type="warning"
                            showIcon
                            style={{ marginBottom: 16 }}
                        />
                    )}

                    <Space>
                        <Button
                            type="primary"
                            icon={<ReloadOutlined />}
                            onClick={handleRefreshCache}
                            loading={operationLoading}
                        >
                            {t('cache.refreshCache')}
                        </Button>
                        <Button
                            danger
                            icon={<DeleteOutlined />}
                            onClick={handleInvalidateCache}
                            loading={operationLoading}
                        >
                            {t('cache.invalidateCache')}
                        </Button>
                        <Button
                            icon={<ClearOutlined />}
                            onClick={handleResetCacheStatistics}
                            loading={operationLoading}
                        >
                            {t('cache.resetStats')}
                        </Button>
                    </Space>
                </>
            ) : (
                <Alert
                    message={t('cache.loadError')}
                    type="error"
                    showIcon
                />
            )}
        </Card>
    );
};

export default CacheManagement;
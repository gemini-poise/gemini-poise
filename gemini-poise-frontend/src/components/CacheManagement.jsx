import React, { useState, useEffect } from 'react';
import { Card, Button, Space, Statistic, Row, Col, Tag, Alert, Spin, App } from 'antd';
import { ReloadOutlined, DeleteOutlined, InfoCircleOutlined } from '@ant-design/icons';
import { useTranslation } from 'react-i18next';
import { getCacheStatus, invalidateCache, refreshCache } from '../api/api';

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
                                value={cacheStatus.cache_status === 'hit' ? '100%' : '0%'}
                                valueStyle={{ 
                                    color: cacheStatus.cache_status === 'hit' ? '#3f8600' : '#cf1322' 
                                }}
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
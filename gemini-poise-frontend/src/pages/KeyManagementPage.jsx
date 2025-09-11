import {App, Button, Collapse, Form, Input, Modal, Progress, Select, Space, Table, Tag, Tooltip, Typography} from 'antd';
import {useTranslation} from 'react-i18next';
import {useKeyManagement} from '../hooks/useKeyManagement';
import CacheManagement from '../components/CacheManagement';

const {Title} = Typography;
const {Option} = Select;

const KeyManagementPage = () => {
  const [form] = Form.useForm();
  const [bulkAddForm] = Form.useForm();
  const {t} = useTranslation();

  const {
    keys,
    loading,
    modalVisible,
    setModalVisible,
    bulkAddModalVisible,
    setBulkAddModalVisible,
    editingKey,
    bulkAdding,
    selectedRowKeys,
    searchKey,
    setSearchKey,
    minFailedCount,
    setMinFailedCount,
    filterStatus,
    setFilterStatus,
    pagination,
    fetchKeys,
    handleTableChange,
    handleBulkAdd,
    handleSaveSingle,
    handleDelete,
    showAddModal,
    onSelectChange,
    handleCopySelectedKeys,
    handleBulkDelete,
    showEditModal,
    bulkCheckModalVisible,
    setBulkCheckModalVisible,
    bulkCheckResults,
    bulkChecking,
    bulkCheckProgress,
    bulkCheckStatus,
    stopBulkCheckTask,
    handleBulkCheckKeys,
    handleCheckSingleKey,
    handleBulkActivateKeys,
  } = useKeyManagement(form, bulkAddForm, t);

  const rowSelection = {
    selectedRowKeys,
    onChange: onSelectChange,
  };

  const columns = [
    {title: 'ID', dataIndex: 'id', key: 'id'},
    {
      title: t('apiKeys.keyValue'),
      dataIndex: 'key_value',
      key: 'key_value',
      render: (text) => {
        if (!text) return '-';
        const maskedText = text.length > 16 ? `${text.substring(0, 8)}...gemini...${text.substring(text.length - 8)}` : text;
        return (
          <Tooltip title={text}>
                        <span
                          style={{cursor: 'pointer'}}
                          onClick={() => {
                            navigator.clipboard.writeText(text);
                            App.useApp().message.success(t('apiKeys.apiKeyCopied'));
                          }}
                        >
                            {maskedText}
                        </span>
          </Tooltip>
        );
      }
    },
    {
      title: t('apiKeys.status'),
      dataIndex: 'status',
      key: 'status',
      render: (status, record) => {
        let color;
        switch (status) {
          case 'active':
            color = 'green';
            break;
          case 'exhausted':
            color = 'yellow';
            break;
          case 'error':
            color = 'red';
            break;
          default:
            color = 'default';
        }
        return (
          <Tag
            color={color}
            style={{cursor: 'pointer'}}
            onClick={() => handleCheckSingleKey(record.id)}
          >
            {status ? (
              status === 'active' ? t('apiKeys.active') :
                status === 'exhausted' ? t('apiKeys.exhausted') :
                  status === 'error' ? t('apiKeys.error') :
                    status.toUpperCase()
            ) : 'N/A'}
          </Tag>
        );
      }
    },
    {title: t('apiKeys.description'), dataIndex: 'description', key: 'description'},
    {title: t('apiKeys.usageCount'), dataIndex: 'usage_count', key: 'usage_count'},
    {title: t('apiKeys.failedCount'), dataIndex: 'failed_count', key: 'failed_count'},
    {
      title: t('apiKeys.createdAt'),
      dataIndex: 'created_at',
      key: 'created_at',
      render: text => text ? new Date(text).toLocaleString() : '-'
    },
    {
      title: t('apiKeys.lastUsedAt'),
      dataIndex: 'last_used_at',
      key: 'last_used_at',
      render: text => text ? new Date(text).toLocaleString() : '-'
    },
    {
      title: t('apiKeys.actions'),
      key: 'action',
      render: (_, record) => (
        <Space size="middle">
          <Button onClick={() => showEditModal(record)}>{t('apiKeys.edit')}</Button>
          <Button danger onClick={() => handleDelete(record.id)}>{t('apiKeys.delete')}</Button>
        </Space>
      ),
    },
  ];

  return (
    <App>
      <div className="p-4">
        {/*<Title level={2} className="text-center">{t('apiKeys.title')}</Title>*/}

        {/* 缓存管理面板 */}
        <Collapse
          style={{marginBottom: 16}}
          items={[
            {
              key: 'cache-management',
              label: t('cache.advancedManagement'),
              children: <CacheManagement/>
            }
          ]}
        />

        <Space className="mb-4" wrap>
          <Input
            placeholder={t('apiKeys.searchApiKey')}
            value={searchKey}
            onChange={e => setSearchKey(e.target.value)}
            style={{width: 200}}
          />
          <Input
            type="number"
            placeholder={t('apiKeys.minFailedCount')}
            value={minFailedCount}
            onChange={e => {
              const value = e.target.value;
              const parsedValue = parseInt(value);
              setMinFailedCount(value === '' || isNaN(parsedValue) ? undefined : parsedValue);
            }}
            style={{width: 150}}
          />
          <Select
            placeholder={t('apiKeys.selectStatus')}
            value={filterStatus}
            onChange={value => setFilterStatus(value)}
            style={{width: 150}}
            allowClear
          >
            <Option value="active">{t('apiKeys.active')}</Option>
            <Option value="exhausted">{t('apiKeys.exhausted')}</Option>
            <Option value="error">{t('apiKeys.error')}</Option>
          </Select>
          <Button type="primary" onClick={() => fetchKeys(1, pagination.pageSize, {search_key: searchKey, min_failed_count: minFailedCount, status: filterStatus})}>
            {t('apiKeys.filter')}
          </Button>
        </Space>

        <div className="mb-4">
          <Space>
            <Button type="primary" onClick={showAddModal}>{t('apiKeys.addSingleKey')}</Button>
            <Button onClick={() => setBulkAddModalVisible(true)}>{t('apiKeys.bulkAddApiKeys')}</Button>
            <Button
              onClick={handleCopySelectedKeys}
              disabled={selectedRowKeys.length === 0}
            >
              {t('apiKeys.copySelectedKeys')}
            </Button>
            <Button
              danger
              onClick={() => handleBulkDelete(selectedRowKeys, t('apiKeys.confirmDeleteSelected'))}
              disabled={selectedRowKeys.length === 0}
            >
              {t('apiKeys.bulkDeleteSelected')}
            </Button>
            <Button
              onClick={handleBulkCheckKeys}
              disabled={selectedRowKeys.length === 0 || bulkChecking}
              loading={bulkChecking}
            >
              {bulkChecking ? t('apiKeys.checking') : t('apiKeys.bulkCheckKeys')}
            </Button>
          </Space>
        </div>
        <Table
          columns={columns}
          dataSource={keys}
          rowKey="id"
          loading={loading}
          rowSelection={rowSelection}
          rowClassName={(record) => {
            if (record.status === 'error') return 'row-error';
            if (record.status === 'exhausted') return 'row-exhausted';
            return '';
          }}
          pagination={{
            current: pagination.current,
            pageSize: pagination.pageSize,
            total: pagination.total,
            showSizeChanger: true,
            pageSizeOptions: ['10', '50', '100', '500', '1000'],
          }}
          onChange={handleTableChange}
        />
        <Modal
          title={t('apiKeys.bulkKeyCheckResults')}
          open={bulkCheckModalVisible}
          onCancel={() => setBulkCheckModalVisible(false)}
          footer={[
            ...(bulkChecking ? [
              <Button
                key="cancel"
                onClick={stopBulkCheckTask}
              >
                {t('apiKeys.cancelCheck')}
              </Button>
            ] : []),
            <Button
              key="deleteInvalid"
              danger
              onClick={() => {
                const invalidKeyIds = bulkCheckResults
                  .filter(result => result.status === 'invalid' || result.status === 'error')
                  .map(result => result.key_id)
                  .filter(id => id != null);
                handleBulkDelete(invalidKeyIds, t('apiKeys.confirmDeleteInvalidError'));
              }}
              disabled={bulkChecking || bulkCheckResults.filter(r => r.status === 'invalid' || r.status === 'error').length === 0}
            >
              {t('apiKeys.deleteInvalidErrorKeys')}
            </Button>,
            <Button
              key="activateValid"
              type="primary"
              onClick={() => {
                const validKeyIds = bulkCheckResults
                  .filter(result => result.status === 'valid')
                  .map(result => result.key_id)
                  .filter(id => id != null);
                handleBulkActivateKeys(validKeyIds);
              }}
              disabled={bulkChecking || bulkCheckResults.filter(r => r.status === 'valid').length === 0}
            >
              {t('apiKeys.activateValidKeys')}
            </Button>,
            <Button key="close" onClick={() => setBulkCheckModalVisible(false)} disabled={bulkChecking}>
              {t('apiKeys.close')}
            </Button>,
          ]}
          width={1000}
        >
          {bulkChecking ? (
            <div style={{textAlign: 'center', padding: '30px 0'}}>
              <div style={{marginBottom: '20px'}}>
                <Progress
                  type="circle"
                  percent={bulkCheckProgress}
                  size={120}
                  status={bulkCheckStatus === 'failed' ? 'exception' : 'active'}
                />
              </div>
              <h3>
                {bulkCheckStatus === 'pending' && t('apiKeys.checkingPending')}
                {bulkCheckStatus === 'running' && `${t('apiKeys.checkingInProgress')} ${bulkCheckProgress.toFixed(1)}%`}
                {bulkCheckStatus === 'failed' && t('apiKeys.checkingFailed')}
              </h3>
              <p style={{color: '#666'}}>
                {bulkCheckStatus === 'running' && t('apiKeys.checkingDescription')}
                {bulkCheckStatus === 'pending' && t('apiKeys.checkingPendingDescription')}
                {bulkCheckStatus === 'failed' && t('apiKeys.checkingFailedDescription')}
              </p>
            </div>
          ) : bulkCheckResults.length > 0 ? (
            <Table
              dataSource={bulkCheckResults}
              columns={[
                {
                  title: t('apiKeys.keyValue'), dataIndex: 'key_value', key: 'key_value', width: '30%',
                  render: (text) => {
                    if (!text) return '-';
                    const maskedText = text.length > 16 ? `${text.substring(0, 8)}...${text.substring(text.length - 8)}` : text;
                    return (
                      <Tooltip title={text}>
                        <span>{maskedText}</span>
                      </Tooltip>
                    );
                  }
                },
                {
                  title: t('apiKeys.status'), dataIndex: 'status', key: 'status', width: '15%',
                  render: (status) => {
                    let color;
                    switch (status) {
                      case 'valid':
                        color = 'green';
                        break;
                      case 'invalid':
                        color = 'red';
                        break;
                      case 'error':
                        color = 'volcano';
                        break;
                      case 'exhausted':
                        color = 'yellow';
                        break;
                      case 'timeout':
                        color = 'orange';
                        break;
                      default:
                        color = 'default';
                    }
                    const statusText = status === 'valid' ? t('apiKeys.valid') :
                      status === 'invalid' ? t('apiKeys.invalid') :
                        status === 'error' ? t('apiKeys.error') :
                          status === 'exhausted' ? t('apiKeys.exhausted') :
                            status === 'timeout' ? t('apiKeys.timeout') : 'N/A';
                    return <Tag color={color}>{statusText}</Tag>;
                  }
                },
                {
                  title: t('apiKeys.message'), 
                  dataIndex: 'message', 
                  key: 'message', 
                  width: '55%',
                  render: (message) => {
                    // 如果是国际化键，则翻译；否则直接显示
                    if (message && message.startsWith('apiKeys.validation.')) {
                      return t(message);
                    }
                    return message || '-';
                  }
                },
              ]}
              rowKey="key_value"
              pagination={false}
              scroll={{y: 400}}
            />
          ) : (
            <p>{t('apiKeys.noResultsToDisplay')}</p>
          )}
        </Modal>

        <Modal
          title={editingKey ? t('apiKeys.editApiKey') : t('apiKeys.addNewKey')}
          open={modalVisible}
          onCancel={() => {
            setModalVisible(false);
            form.resetFields();
          }}
          footer={null}
        >
          <Form
            form={form}
            layout="vertical"
            onFinish={handleSaveSingle}
          >
            <Form.Item
              label={t('apiKeys.keyValue')}
              name="key_value"
              rules={[{required: true, message: t('apiKeys.pleaseInputApiKey')}]}
            >
              <Input/>
            </Form.Item>
            <Form.Item
              label={t('apiKeys.status')}
              name="status"
              rules={[{required: true, message: t('apiKeys.pleaseSelectStatus')}]}
            >
              <Select>
                <Option value="active">{t('apiKeys.active')}</Option>
                <Option value="error">{t('apiKeys.error')}</Option>
                <Option value="exhausted">{t('apiKeys.exhausted')}</Option>
              </Select>
            </Form.Item>
            <Form.Item
              label={t('apiKeys.description')}
              name="description"
            >
              <Input.TextArea/>
            </Form.Item>
            <Form.Item>
              <Button type="primary" htmlType="submit">
                {t('apiKeys.save')}
              </Button>
            </Form.Item>
          </Form>
        </Modal>

        <Modal
          title={t('apiKeys.bulkAddApiKeys')}
          open={bulkAddModalVisible}
          onCancel={() => {
            setBulkAddModalVisible(false);
            bulkAddForm.resetFields();
          }}
          footer={null}
        >
          <Form
            form={bulkAddForm}
            layout="vertical"
            name="bulk_add_form"
            onFinish={handleBulkAdd}
          >
            <Form.Item
              label={t('apiKeys.apiKeysCommaSeparated')}
              name="keys_string"
              rules={[{required: true, message: t('apiKeys.pleaseInputApiKeys')}]}
            >
              <Input.TextArea rows={8} placeholder={t('apiKeys.pasteApiKeysPlaceholder')}/>
            </Form.Item>
            <Form.Item>
              <Button type="primary" htmlType="submit" loading={bulkAdding}>
                {t('apiKeys.addKeys')}
              </Button>
            </Form.Item>
          </Form>
        </Modal>

      </div>
    </App>
  );
};

export default KeyManagementPage;

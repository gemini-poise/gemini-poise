import { Table, Button, Space, Modal, Form, Input, Select, Typography, Tooltip, App, Tag } from 'antd';
import { useKeyManagement } from '../hooks/useKeyManagement';

const { Title } = Typography;
const { Option } = Select;

const KeyManagementPage = () => {
    const [form] = Form.useForm();
    const [bulkAddForm] = Form.useForm();

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
        handleBulkCheckKeys,
        handleCheckSingleKey,
    } = useKeyManagement(form, bulkAddForm);

    const rowSelection = {
        selectedRowKeys,
        onChange: onSelectChange,
    };

    const columns = [
        { title: 'ID', dataIndex: 'id', key: 'id' },
        {
            title: 'API Key',
            dataIndex: 'key_value',
            key: 'key_value',
            render: (text) => {
                if (!text) return '-';
                const maskedText = text.length > 16 ? `${text.substring(0, 8)}...gemini...${text.substring(text.length - 8)}` : text;
                return (
                    <Tooltip title={text}>
                        <span
                            style={{ cursor: 'pointer' }}
                            onClick={() => {
                                navigator.clipboard.writeText(text);
                                App.useApp().message.success('API Key copied to clipboard!');
                            }}
                        >
                            {maskedText}
                        </span>
                    </Tooltip>
                );
            }
        },
        {
            title: 'Status',
            dataIndex: 'status',
            key: 'status',
            render: (status, record) => {
                let color;
                switch (status) {
                    case 'active':
                        color = 'green';
                        break;
                    case 'inactive':
                        color = 'volcano';
                        break;
                    case 'exhausted':
                        color = 'red';
                        break;
                    default:
                        color = 'default';
                }
                return (
                    <Tag
                        color={color}
                        style={{ cursor: 'pointer' }}
                        onClick={() => handleCheckSingleKey(record.id)}
                    >
                        {status ? status.toUpperCase() : 'N/A'}
                    </Tag>
                );
            }
        },
        { title: 'Description', dataIndex: 'description', key: 'description' },
        { title: 'Usage Count', dataIndex: 'usage_count', key: 'usage_count' },
        { title: 'Failed Count', dataIndex: 'failed_count', key: 'failed_count' },
        {
            title: 'Created At',
            dataIndex: 'created_at',
            key: 'created_at',
            render: text => text ? new Date(text).toLocaleString() : '-'
        },
        {
            title: 'Last Used At',
            dataIndex: 'last_used_at',
            key: 'last_used_at',
            render: text => text ? new Date(text).toLocaleString() : '-'
        },
        {
            title: 'Action',
            key: 'action',
            render: (_, record) => (
                <Space size="middle">
                    <Button onClick={() => showEditModal(record)}>Edit</Button>
                    <Button danger onClick={() => handleDelete(record.id)}>Delete</Button>
                </Space>
            ),
        },
    ];

    return (
        <App>
            <div className="p-4">
                <Title level={2} className="text-center">API Key Management</Title>

            <Space className="mb-4" wrap>
                <Input
                    placeholder="Search API Key"
                    value={searchKey}
                    onChange={e => setSearchKey(e.target.value)}
                    style={{ width: 200 }}
                />
                <Input
                    type="number"
                    placeholder="Min Failed Count"
                    value={minFailedCount}
                    onChange={e => {
                        const value = e.target.value;
                        const parsedValue = parseInt(value);
                        setMinFailedCount(value === '' || isNaN(parsedValue) ? undefined : parsedValue);
                    }}
                    style={{ width: 150 }}
                />
                <Select
                    placeholder="Select Status"
                    value={filterStatus}
                    onChange={value => setFilterStatus(value)}
                    style={{ width: 150 }}
                    allowClear
                >
                    <Option value="active">Active</Option>
                    <Option value="inactive">Inactive</Option>
                    <Option value="exhausted">Exhausted</Option>
                </Select>
                <Button type="primary" onClick={() => fetchKeys(1, pagination.pageSize, { search_key: searchKey, min_failed_count: minFailedCount, status: filterStatus })}>
                    Filter
                </Button>
            </Space>

            <div className="mb-4">
                <Space>
                    <Button type="primary" onClick={showAddModal}>Add Single Key</Button>
                    <Button onClick={() => setBulkAddModalVisible(true)}>Bulk Add API Keys</Button>
                    <Button
                        onClick={handleCopySelectedKeys}
                        disabled={selectedRowKeys.length === 0}
                    >
                        Copy Selected Keys
                    </Button>
                    <Button
                        danger
                        onClick={() => handleBulkDelete(selectedRowKeys)}
                        disabled={selectedRowKeys.length === 0}
                    >
                        Bulk Delete Selected
                    </Button>
                    <Button
                        onClick={handleBulkCheckKeys}
                        disabled={selectedRowKeys.length === 0 || bulkChecking}
                        loading={bulkChecking}
                    >
                        {bulkChecking ? 'Checking...' : 'Bulk Check Keys'}
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
                    if (record.status === 'inactive') return 'row-inactive';
                    if (record.status === 'exhausted') return 'row-exhausted';
                    return '';
                }}
                pagination={{
                    current: pagination.current,
                    pageSize: pagination.pageSize,
                    total: pagination.total,
                    showSizeChanger: true,
                    pageSizeOptions: ['10', '20', '50', '100'],
                }}
                onChange={handleTableChange}
            />
            <Modal
                title="Bulk Key Check Results"
                open={bulkCheckModalVisible}
                onCancel={() => setBulkCheckModalVisible(false)}
                footer={[
                    <Button
                        key="deleteInvalid"
                        danger
                        onClick={() => {
                            const invalidKeyIds = bulkCheckResults
                                .filter(result => result.status === 'invalid' || result.status === 'error')
                                .map(result => {
                                    const foundKey = keys.find(k => k.key_value === result.key_value);
                                    return foundKey ? foundKey.id : null;
                                })
                                .filter(id => id !== null);
                            handleBulkDelete(invalidKeyIds, 'Are you sure you want to delete invalid/error');
                        }}
                        disabled={bulkCheckResults.filter(r => r.status === 'invalid' || r.status === 'error').length === 0}
                    >
                        Delete Invalid/Error Keys
                    </Button>,
                    <Button key="close" onClick={() => setBulkCheckModalVisible(false)}>
                        Close
                    </Button>,
                ]}
                width={1000}
            >
                {bulkCheckResults.length > 0 ? (
                    <Table
                        dataSource={bulkCheckResults}
                        columns={[
                            { title: 'API Key', dataIndex: 'key_value', key: 'key_value', width: '30%',
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
                            { title: 'Status', dataIndex: 'status', key: 'status', width: '15%',
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
                                        default:
                                            color = 'default';
                                    }
                                    return <Tag color={color}>{status ? status.toUpperCase() : 'N/A'}</Tag>;
                                }
                            },
                            { title: 'Message', dataIndex: 'message', key: 'message', width: '55%' },
                        ]}
                        rowKey="key_value"
                        pagination={false}
                        scroll={{ y: 400 }}
                    />
                ) : (
                    <p>No results to display. Please select keys and run the bulk check.</p>
                )}
            </Modal>

            <Modal
                title={editingKey ? 'Edit API Key' : 'Add New Key'}
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
                        label="API Key"
                        name="key_value"
                        rules={[{ required: true, message: 'Please input the API Key!' }]}
                    >
                        <Input />
                    </Form.Item>
                    <Form.Item
                        label="Status"
                        name="status"
                        rules={[{ required: true, message: 'Please select the Status!' }]}
                    >
                        <Select>
                            <Option value="active">Active</Option>
                            <Option value="inactive">Inactive</Option>
                            <Option value="exhausted">Exhausted</Option>
                        </Select>
                    </Form.Item>
                    <Form.Item
                        label="Description"
                        name="description"
                    >
                        <Input.TextArea />
                    </Form.Item>
                    <Form.Item>
                        <Button type="primary" htmlType="submit">
                            Save
                        </Button>
                    </Form.Item>
                </Form>
            </Modal>

            <Modal
                title="Bulk Add API Keys"
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
                        label="API Keys (comma or newline separated)"
                        name="keys_string"
                        rules={[{ required: true, message: 'Please input API keys!' }]}
                    >
                        <Input.TextArea rows={8} placeholder="Paste your API keys here, separated by commas or newlines." />
                    </Form.Item>
                    <Form.Item>
                        <Button type="primary" htmlType="submit" loading={bulkAdding}>
                            Add Keys
                        </Button>
                    </Form.Item>
                </Form>
            </Modal>

            </div>
        </App>
    );
};

export default KeyManagementPage;

import { useState, useEffect, useCallback, useRef } from 'react';
import { App, Modal } from 'antd';
import {
  getApiKeysPaginated,
  bulkAddApiKeys,
  createApiKey,
  updateApiKey,
  deleteApiKey,
  bulkDeleteApiKeys,
  bulkCheckApiKeys,
  getBulkCheckTaskStatus,
  checkApiKey,
} from '../api/api';

export const useKeyManagement = (form, bulkAddForm, t) => {
  const [keys, setKeys] = useState([]);
  const [loading, setLoading] = useState(false);
  const [modalVisible, setModalVisible] = useState(false);
  const [bulkAddModalVisible, setBulkAddModalVisible] = useState(false);
  const [editingKey, setEditingKey] = useState(null);
  const [bulkAdding, setBulkAdding] = useState(false);
  const [selectedRowKeys, setSelectedRowKeys] = useState([]);
  const [searchKey, setSearchKey] = useState('');
  const [minFailedCount, setMinFailedCount] = useState(undefined);
  const [filterStatus, setFilterStatus] = useState(undefined);
  const [bulkCheckModalVisible, setBulkCheckModalVisible] = useState(false);
  const [bulkCheckResults, setBulkCheckResults] = useState([]);
  const [bulkChecking, setBulkChecking] = useState(false);
  const [bulkCheckProgress, setBulkCheckProgress] = useState(0);
  const [bulkCheckTaskId, setBulkCheckTaskId] = useState(null);
  const [bulkCheckStatus, setBulkCheckStatus] = useState('pending'); // pending, running, completed, failed

  const bulkCheckPollingRef = useRef(null);

  const { message } = App.useApp();

  const [pagination, setPagination] = useState({
    current: 1,
    pageSize: 10,
    total: 0,
  });

  const fetchKeys = useCallback(async (page = 1, pageSize = 10, filters = {}) => {
    setLoading(true);
    try {
      const response = await getApiKeysPaginated({
        page: page,
        page_size: pageSize,
        search_key: filters.search_key,
        min_failed_count: filters.min_failed_count,
        status: filters.status,
      });
      setKeys(response.data.items);
      setPagination({
        current: page,
        pageSize: pageSize,
        total: response.data.total,
      });
    } catch (error) {
      console.error("Failed to fetch API keys:", error);
      message.error(t('apiKeys.failedToLoadKeys'));
    } finally {
      setLoading(false);
    }
  }, [message, t]);

  // 初始化加载和筛选条件变化时的数据获取
  useEffect(() => {
    fetchKeys(1, pagination.pageSize, {
      search_key: searchKey,
      min_failed_count: minFailedCount,
      status: filterStatus
    });
  }, [searchKey, minFailedCount, filterStatus]);

  // 处理表格分页变化
  const handleTableChange = useCallback((newPagination) => {
    if (newPagination.current !== pagination.current || newPagination.pageSize !== pagination.pageSize) {
      fetchKeys(newPagination.current, newPagination.pageSize, {
        search_key: searchKey,
        min_failed_count: minFailedCount,
        status: filterStatus
      });
    }
  }, [pagination.current, pagination.pageSize, searchKey, minFailedCount, filterStatus, fetchKeys]);

  const handleBulkAdd = async (values) => {
    const keysToAdd = values.keys_string.split(/[\n,]/).map(key => key.trim()).filter(key => key.length > 0);
    if (keysToAdd.length === 0) {
      message.warning(t('apiKeys.pleaseEnterKeysToAdd'));
      return;
    }
    setBulkAdding(true);
    try {
      const response = await bulkAddApiKeys({ keys: keysToAdd });
      message.success(t('apiKeys.bulkAddComplete', { processed: response.data.total_processed, added: response.data.total_added }));
      bulkAddForm.resetFields();
      setBulkAddModalVisible(false);
      await fetchKeys(pagination.current, pagination.pageSize, {
        search_key: searchKey,
        min_failed_count: minFailedCount,
        status: filterStatus
      });
    } catch (error) {
      console.error("Failed to add API keys from list:", error);
      message.error(t('apiKeys.failedToAddKeys'));
    } finally {
      setBulkAdding(false);
    }
  };

  const handleSaveSingle = async (values) => {
    setLoading(true);
    try {
      if (editingKey) {
        await updateApiKey(editingKey.id, values);
        message.success(t('apiKeys.keyUpdatedSuccess'));
      } else {
        await createApiKey(values);
        message.success(t('apiKeys.keyAddedSuccess'));
      }
      setModalVisible(false);
      form.resetFields();
      fetchKeys(pagination.current, pagination.pageSize, {
        search_key: searchKey,
        min_failed_count: minFailedCount,
        status: filterStatus
      });
    } catch (error) {
      console.error("Failed to save API key:", error);
      message.error(t('apiKeys.failedToSaveKey'));
    } finally {
      setLoading(false);
    }
  };

  const handleDelete = async (keyId) => {
    setLoading(true);
    try {
      await deleteApiKey(keyId);
      message.success(t('apiKeys.keyDeletedSuccess'));
      if (keys.length === 1 && pagination.current > 1) {
        fetchKeys(pagination.current - 1, pagination.pageSize, {
          search_key: searchKey,
          min_failed_count: minFailedCount,
          status: filterStatus
        });
      } else {
        fetchKeys(pagination.current, pagination.pageSize, {
          search_key: searchKey,
          min_failed_count: minFailedCount,
          status: filterStatus
        });
      }
    } catch (error) {
      console.error("Failed to delete API key:", error);
      message.error(t('apiKeys.failedToDeleteKey'));
    } finally {
      setLoading(false);
    }
  };

  const showAddModal = () => {
    setEditingKey(null);
    form.resetFields();
    form.setFieldsValue({ status: 'active' });
    setModalVisible(true);
  };

  const onSelectChange = (newSelectedRowKeys) => {
    setSelectedRowKeys(newSelectedRowKeys);
  };

  const handleCopySelectedKeys = () => {
    const selectedKeys = keys
      .filter(key => selectedRowKeys.includes(key.id))
      .map(key => key.key_value);
    if (selectedKeys.length > 0) {
      navigator.clipboard.writeText(selectedKeys.join(', '));
      message.success(t('apiKeys.keysCopiedSuccess', { count: selectedKeys.length }));
    } else {
      message.warning(t('apiKeys.noKeysSelected'));
    }
  };

  const handleBulkDelete = async (idsToDelete = selectedRowKeys, confirmMessage = 'Are you sure you want to delete') => {
    if (idsToDelete.length === 0) {
      message.warning(t('apiKeys.noKeysToDelete'));
      return;
    }

    Modal.confirm({
      title: t('apiKeys.confirmDelete'),
      content: t('apiKeys.confirmDeleteMessage', { message: confirmMessage, count: idsToDelete.length }),
      okText: t('apiKeys.yes'),
      okType: 'danger',
      cancelText: t('apiKeys.no'),
      onOk: async () => {
        setLoading(true);
        try {
          const response = await bulkDeleteApiKeys(idsToDelete);
          message.success(response.data.detail || t('apiKeys.keysDeletedSuccess'));
          setSelectedRowKeys([]);
          setBulkCheckResults([]);
          setBulkCheckModalVisible(false);

          const currentPage = pagination.current;
          const totalItemsAfterDeletion = pagination.total - idsToDelete.length;
          const totalPagesAfterDeletion = Math.ceil(totalItemsAfterDeletion / pagination.pageSize);
          const pageToFetch = currentPage > totalPagesAfterDeletion && totalPagesAfterDeletion > 0 ? totalPagesAfterDeletion : currentPage;

          fetchKeys(pageToFetch, pagination.pageSize, {
            search_key: searchKey,
            min_failed_count: minFailedCount,
            status: filterStatus
          });

        } catch (error) {
          console.error("Failed to bulk delete API keys:", error);
          message.error(t('apiKeys.failedToDeleteKeys'));
        } finally {
          setLoading(false);
        }
      },
    });
  };

  const showEditModal = (key) => {
    setEditingKey(key);
    form.setFieldsValue(key);
    setModalVisible(true);
  };

  const handleBulkCheckKeys = async () => {
    if (selectedRowKeys.length === 0) {
      message.warning(t('apiKeys.pleaseSelectKeysToCheck'));
      return;
    }

    setBulkChecking(true);
    setBulkCheckResults([]);
    setBulkCheckProgress(0);
    setBulkCheckStatus('pending');
    setBulkCheckModalVisible(true);

    try {
      // 启动异步任务
      const response = await bulkCheckApiKeys(selectedRowKeys);
      const taskId = response.data.task_id;
      setBulkCheckTaskId(taskId);
      
      message.success(response.data.message);
      
      // 开始轮询任务状态
      startPollingTaskStatus(taskId);
      
    } catch (error) {
      console.error("Failed to start bulk check task:", error);
      message.error(t('apiKeys.failedToBulkCheck'));
      setBulkChecking(false);
      setBulkCheckStatus('failed');
    }
  };

  const startPollingTaskStatus = (taskId) => {
    setBulkCheckStatus('running');
    
    const pollStatus = async () => {
      try {
        const response = await getBulkCheckTaskStatus(taskId);
        const taskData = response.data;
        
        setBulkCheckProgress(taskData.progress || 0);
        setBulkCheckStatus(taskData.status);
        
        if (taskData.status === 'completed') {
          setBulkCheckResults(taskData.results || []);
          setBulkChecking(false);
          setSelectedRowKeys([]);
          message.success(t('apiKeys.bulkCheckCompleted'));
          
          // 立即清理定时器，防止重复请求
          if (bulkCheckPollingRef.current) {
            clearInterval(bulkCheckPollingRef.current);
            bulkCheckPollingRef.current = null;
          }
          return; // 立即退出，不继续轮询
        } else if (taskData.status === 'failed') {
          setBulkChecking(false);
          message.error(taskData.error || t('apiKeys.failedToBulkCheck'));
          
          // 立即清理定时器
          if (bulkCheckPollingRef.current) {
            clearInterval(bulkCheckPollingRef.current);
            bulkCheckPollingRef.current = null;
          }
          return; // 立即退出，不继续轮询
        }
        // 如果状态是 running 或 pending，继续轮询（通过定时器）
        
      } catch (error) {
        console.error("Failed to get task status:", error);
        setBulkChecking(false);
        setBulkCheckStatus('failed');
        message.error(t('apiKeys.failedToBulkCheck'));
        
        // 出错时也清理定时器
        if (bulkCheckPollingRef.current) {
          clearInterval(bulkCheckPollingRef.current);
          bulkCheckPollingRef.current = null;
        }
      }
    };
    
    // 立即执行一次
    pollStatus();
    
    // 每2秒轮询一次，但需要检查轮询是否还应该继续
    bulkCheckPollingRef.current = setInterval(() => {
      // 如果定时器已被清理，直接返回
      if (!bulkCheckPollingRef.current) {
        return;
      }
      pollStatus();
    }, 2000);
  };

  // 清理轮询
  useEffect(() => {
    return () => {
      if (bulkCheckPollingRef.current) {
        clearInterval(bulkCheckPollingRef.current);
        bulkCheckPollingRef.current = null;
      }
    };
  }, []);

  const stopBulkCheckTask = () => {
    if (bulkCheckPollingRef.current) {
      clearInterval(bulkCheckPollingRef.current);
      bulkCheckPollingRef.current = null;
    }
    setBulkChecking(false);
    setBulkCheckStatus('cancelled');
    message.info(t('apiKeys.checkingCancelled'));
  };

  const handleCheckSingleKey = async (keyId) => {
    setLoading(true);
    try {
      const response = await checkApiKey(keyId);
      if (response.data.status === 'valid') {
        message.success(t('apiKeys.keyIsValid'));
      } else {
        message.error(t('apiKeys.keyIsInvalid', { message: response.data.message }));
      }
      await fetchKeys(pagination.current, pagination.pageSize, {
        search_key: searchKey,
        min_failed_count: minFailedCount,
        status: filterStatus
      });
    } catch (error) {
      console.error("Failed to check single API key:", error);
      message.error(t('apiKeys.failedToCheckKey', { message: error.response?.data?.detail || error.message }));
    } finally {
      setLoading(false);
    }
  };

  const handleBulkActivateKeys = async (validKeyValues) => {
    if (validKeyValues.length === 0) {
      message.warning(t('apiKeys.noValidKeysToActivate'));
      return;
    }

    const hideLoading = message.loading(t('apiKeys.activatingKeys'), 0);
    try {
      const updatePromises = validKeyValues.map(async (keyValue) => {
        const foundKey = keys.find(k => k.key_value === keyValue);
        if (foundKey) {
          await updateApiKey(foundKey.id, { ...foundKey, status: 'active' });
        }
      });
      await Promise.all(updatePromises);
      message.success(t('apiKeys.keysActivatedSuccess', { count: validKeyValues.length }));
      setBulkCheckModalVisible(false);
      setSelectedRowKeys([]);
      await fetchKeys(pagination.current, pagination.pageSize, {
        search_key: searchKey,
        min_failed_count: minFailedCount,
        status: filterStatus
      });
    } catch (error) {
      console.error("Failed to bulk activate API keys:", error);
      message.error(t('apiKeys.failedToActivateKeys'));
    } finally {
      hideLoading();
    }
  };

  return {
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
  };
};
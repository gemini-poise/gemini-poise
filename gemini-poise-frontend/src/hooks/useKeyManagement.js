import { useState, useEffect, useCallback } from 'react';
import { App, Modal } from 'antd';
import {
  getApiKeysPaginated,
  bulkAddApiKeys,
  createApiKey,
  updateApiKey,
  deleteApiKey,
  bulkDeleteApiKeys,
  bulkCheckApiKeys,
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

  const { message } = App.useApp();

  const [pagination, setPagination] = useState({
    current: 1,
    pageSize: 10,
    total: 0,
  });

  const fetchKeys = useCallback(async (page = pagination.current, pageSize = pagination.pageSize, filters = { search_key: searchKey, min_failed_count: minFailedCount, status: filterStatus }) => {
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
      setPagination(prev => ({
        ...prev,
        current: page,
        pageSize: pageSize,
        total: response.data.total,
      }));
    } catch (error) {
      console.error("Failed to fetch API keys:", error);
      message.error(t('apiKeys.failedToLoadKeys'));
    } finally {
      setLoading(false);
    }
  }, [pagination.current, pagination.pageSize, searchKey, minFailedCount, filterStatus, message]);

  useEffect(() => {
    fetchKeys(pagination.current, pagination.pageSize, { search_key: searchKey, min_failed_count: minFailedCount, status: filterStatus });
  }, [searchKey, minFailedCount, filterStatus, fetchKeys]);

  const handleTableChange = (newPagination) => {
    if (newPagination.current !== pagination.current || newPagination.pageSize !== pagination.pageSize) {
      fetchKeys(newPagination.current, newPagination.pageSize, { search_key: searchKey, min_failed_count: minFailedCount, status: filterStatus });
    }
  };

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
      await fetchKeys();
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
      fetchKeys(pagination.current, pagination.pageSize);
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
        fetchKeys(pagination.current - 1, pagination.pageSize, { search_key: searchKey, min_failed_count: minFailedCount, status: filterStatus });
      } else {
        fetchKeys(pagination.current, pagination.pageSize, { search_key: searchKey, min_failed_count: minFailedCount, status: filterStatus });
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

          fetchKeys(pageToFetch, pagination.pageSize, { search_key: searchKey, min_failed_count: minFailedCount, status: filterStatus });

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
    setBulkCheckModalVisible(true);

    try {
      const response = await bulkCheckApiKeys(selectedRowKeys);
      setBulkCheckResults(response.data.results);
      message.success(t('apiKeys.bulkCheckCompleted'));
      setSelectedRowKeys([]);
    } catch (error) {
      console.error("Failed to bulk check API keys:", error);
      message.error(t('apiKeys.failedToBulkCheck'));
      setBulkCheckResults([]);
    } finally {
      setBulkChecking(false);
    }
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
      await fetchKeys();
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
      await fetchKeys();
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
    handleBulkCheckKeys,
    handleCheckSingleKey,
    handleBulkActivateKeys,
  };
};
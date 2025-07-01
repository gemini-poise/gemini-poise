import { useState, useCallback } from 'react';
import { App } from 'antd';
import { getAllConfig, bulkSaveConfig } from '../api/api';

export const useConfigManagement = (configDefinitions, t) => {
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const { message } = App.useApp();

  const fetchConfig = useCallback(async (form) => {
    setLoading(true);
    try {
      const response = await getAllConfig();
      const dataArray = response.data;
      const formValues = dataArray.reduce((acc, item) => {
        if (configDefinitions.some(def => def.k === item.key)) {
          acc[item.key] = item.value;
        }
        return acc;
      }, {});

      const activeInterval = formValues['key_validation_active_interval_seconds'];
      if (!formValues['key_validation_exhausted_interval_seconds']) {
        formValues['key_validation_exhausted_interval_seconds'] = activeInterval;
      }
      // if (!formValues['key_validation_error_interval_seconds']) {
      //   formValues['key_validation_error_interval_seconds'] = '0';
      // }

      form.setFieldsValue(formValues);
    } catch (error) {
      console.error("Failed to fetch config:", error);
      message.error(t('config.failedToLoadConfig'));
    } finally {
      setLoading(false);
    }
  }, [configDefinitions, message]);

  const saveConfig = useCallback(async (values, form) => {
    setSaving(true);
    try {
      await form.validateFields();
      const dataArray = Object.keys(values)
        .map(key => ({
          key: key,
          value: values[key],
        }))
        .filter(item => item.value !== null && item.value !== undefined && item.value !== '');

      await bulkSaveConfig({ items: dataArray });
      message.success(t('config.configSavedSuccess'));
    } catch (error) {
      console.error("Failed to bulk save configs:", error);
      message.error(t('config.failedToSaveConfig'));
    } finally {
      setSaving(false);
    }
  }, [message]);

  return { loading, saving, fetchConfig, saveConfig };
};
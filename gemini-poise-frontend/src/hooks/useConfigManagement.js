import { useEffect, useState, useCallback } from 'react';
import { App } from 'antd';
import { getAllConfig, bulkSaveConfig } from '../api/api';

export const useConfigManagement = (configDefinitions) => {
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
      form.setFieldsValue(formValues);
    } catch (error) {
      console.error("Failed to fetch config:", error);
      message.error('Failed to load configuration.');
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
      message.success('All configurations saved successfully.');
    } catch (error) {
      console.error("Failed to bulk save configs:", error);
      message.error('Failed to save configurations.');
    } finally {
      setSaving(false);
    }
  }, [message]);

  return { loading, saving, fetchConfig, saveConfig };
};
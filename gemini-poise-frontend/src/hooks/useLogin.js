import { useState, useEffect } from 'react';
import { App } from 'antd';
import { useAuth } from '../contexts/AuthContext';

export const useLogin = (form, t) => {
  const { message } = App.useApp();
  const { login } = useAuth();
  const [loading, setLoading] = useState(false);

  const rememberedUsername = localStorage.getItem('rememberedUsername');

  useEffect(() => {
    if (rememberedUsername) {
      form.setFieldsValue({ username: rememberedUsername });
    }
  }, [form, rememberedUsername]);

  const handleLogin = async (values) => {
    if (!values.username || !values.password) {
      message.error(t('login.usernamePasswordRequired'));
      return;
    }

    setLoading(true);
    try {
      await login(values.username, values.password);
      if (values.remember) {
        localStorage.setItem('rememberedUsername', values.username);
      } else {
        localStorage.removeItem('rememberedUsername');
      }
      message.success(t('login.loginSuccessful'));
    } catch (error) {
      message.error(t('login.loginFailed'));
      console.error("Login failed:", error);
    } finally {
      setLoading(false);
    }
  };

  return { loading, handleLogin, rememberedUsername };
};
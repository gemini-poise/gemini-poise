import { useEffect, useState } from 'react';
import { getKeyStatistics, getApiCallStatistics, getApiCallLogsByMinute } from '../api/api';

export const useKeyStatistics = () => {
  const [keyStatistics, setKeyStatistics] = useState({ totalKeys: 0, validKeys: 0, invalidKeys: 0 });
  const [loadingKeys, setLoadingKeys] = useState(true);
  const [errorKeys, setErrorKeys] = useState(null);

  useEffect(() => {
    const fetchKeyStatistics = async () => {
      try {
        setLoadingKeys(true);
        const response = await getKeyStatistics();
        setKeyStatistics({
          totalKeys: response.data.total_keys,
          validKeys: response.data.valid_keys,
          invalidKeys: response.data.invalid_keys,
        });
        setErrorKeys(null);
      } catch (err) {
        console.error("Error fetching key statistics:", err);
        setErrorKeys("Failed to load key statistics.");
      } finally {
        setLoadingKeys(false);
      }
    };

    fetchKeyStatistics();
  }, []);

  return { ...keyStatistics, loadingKeys, errorKeys };
};

export const useApiCallStatistics = () => {
  const [callsLast1Minute, setCallsLast1Minute] = useState(0);
  const [callsLast1Hour, setCallsLast1Hour] = useState(0);
  const [callsLast24Hours, setCallsLast24Hours] = useState(0);
  const [monthlyUsage, setMonthlyUsage] = useState(0);
  const [loadingCalls, setLoadingCalls] = useState(true);
  const [errorCalls, setErrorCalls] = useState(null);

  useEffect(() => {
    const fetchApiCallStatistics = async () => {
      try {
        setLoadingCalls(true);
        const response = await getApiCallStatistics();
        const data = response.data;
        setCallsLast1Minute(data.calls_last_1_minute);
        setCallsLast1Hour(data.calls_last_1_hour);
        setCallsLast24Hours(data.calls_last_24_hours);
        setMonthlyUsage(data.monthly_usage);
        setErrorCalls(null);
      } catch (err) {
        console.error("Error fetching API call statistics:", err);
        setErrorCalls("Failed to load API call statistics.");
      } finally {
        setLoadingCalls(false);
      }
    };

    fetchApiCallStatistics();
  }, []);

  return { callsLast1Minute, callsLast1Hour, callsLast24Hours, monthlyUsage, loadingCalls, errorCalls };
};

export const useApiCallLogsByMinute = (hoursAgo = 24) => {
  const [apiCallLogs, setApiCallLogs] = useState([]);
  const [loadingApiCallLogs, setLoadingApiCallLogs] = useState(true);
  const [errorApiCallLogs, setErrorApiCallLogs] = useState(null);

  useEffect(() => {
    const fetchApiCallLogs = async () => {
      try {
        setLoadingApiCallLogs(true);
        const response = await getApiCallLogsByMinute(hoursAgo);
        setApiCallLogs(response.data.logs);
        setErrorApiCallLogs(null);
      } catch (err) {
        console.error("Error fetching API call logs by minute:", err);
        setErrorApiCallLogs("Failed to load API call logs by minute.");
      } finally {
        setLoadingApiCallLogs(false);
      }
    };

    fetchApiCallLogs();
  }, [hoursAgo]);

  return { apiCallLogs, loadingApiCallLogs, errorApiCallLogs };
};
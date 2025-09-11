import { useState, useEffect, useCallback } from 'react';

const CACHE_KEY = 'bingWallpaper';
const API_URL = 'https://bing.ee123.net/img/4k';
const FALLBACK_IMAGE = '/743986.jpg';

const useBingWallpaper = () => {
  const [wallpaperUrl, setWallpaperUrl] = useState('');
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState(null);

  const getTodayDateString = useCallback(() => {
    const today = new Date();
    const year = today.getFullYear();
    const month = String(today.getMonth() + 1).padStart(2, '0');
    const day = String(today.getDate()).padStart(2, '0');
    return `${year}${month}${day}`;
  }, []);

  const getCachedWallpaper = useCallback((dateString) => {
    try {
      const cachedData = localStorage.getItem(CACHE_KEY);
      if (cachedData) {
        const parsed = JSON.parse(cachedData);
        return parsed.date === dateString && 
               parsed.url && 
               parsed.url.includes('bing.ee123.net') ? parsed : null;
      }
    } catch (error) {
      console.warn('Failed to parse cached wallpaper data:', error);
      localStorage.removeItem(CACHE_KEY);
    }
    return null;
  }, []);

  const setCachedWallpaper = useCallback((dateString, url) => {
    try {
      const cacheData = {
        date: dateString,
        url: url,
        title: 'Bing Daily Wallpaper',
        copyright: 'Microsoft Bing',
        timestamp: Date.now()
      };
      localStorage.setItem(CACHE_KEY, JSON.stringify(cacheData));
    } catch (error) {
      console.warn('Failed to cache wallpaper data:', error);
    }
  }, []);

  const fetchBingWallpaper = useCallback(async () => {
    try {
      setIsLoading(true);
      setError(null);
      
      const dateString = getTodayDateString();
      
      // Check cache first
      const cached = getCachedWallpaper(dateString);
      if (cached) {
        setWallpaperUrl(cached.url);
        setIsLoading(false);
        return;
      }
      
      // Clear any invalid cache
      localStorage.removeItem(CACHE_KEY);
      
      // Use API endpoint
      setWallpaperUrl(API_URL);
      setCachedWallpaper(dateString, API_URL);
      
    } catch (err) {
      console.warn('Failed to set wallpaper, using fallback:', err.message);
      setError(err.message);
      setWallpaperUrl(FALLBACK_IMAGE);
    } finally {
      setIsLoading(false);
    }
  }, [getTodayDateString, getCachedWallpaper, setCachedWallpaper]);

  useEffect(() => {
    fetchBingWallpaper();
  }, [fetchBingWallpaper]);

  return { 
    wallpaperUrl, 
    isLoading, 
    error,
    refetch: fetchBingWallpaper 
  };
};

export default useBingWallpaper;
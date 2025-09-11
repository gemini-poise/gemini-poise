import { createContext, useContext, useState, useEffect } from 'react';
import { ConfigProvider, theme } from 'antd';

const ThemeContext = createContext(null);

export const ThemeProvider = ({ children }) => {
  const [currentTheme, setCurrentTheme] = useState(
    localStorage.getItem('theme') === 'dark' ? 'dark' : 'light'
  );

  const toggleTheme = (checked) => {
    const newTheme = checked ? 'dark' : 'light';
    setCurrentTheme(newTheme);
    localStorage.setItem('theme', newTheme);
    
    // Update body background dynamically
    updateBodyBackground(newTheme);
  };

  const updateBodyBackground = (theme) => {
    const body = document.body;
    const html = document.documentElement;
    
    // 设置 data-theme 属性用于CSS选择器
    html.setAttribute('data-theme', theme);
    
    if (theme === 'dark') {
      body.style.background = `linear-gradient(135deg,
        rgba(15, 23, 42, 1) 0%,
        rgba(30, 41, 59, 1) 25%,
        rgba(51, 65, 85, 1) 50%,
        rgba(71, 85, 105, 1) 75%,
        rgba(100, 116, 139, 1) 100%
      )`;
    } else {
      body.style.background = `linear-gradient(135deg, 
        rgba(219, 234, 254, 1) 0%,
        rgba(147, 197, 253, 1) 25%,
        rgba(96, 165, 250, 1) 50%,
        rgba(59, 130, 246, 1) 75%,
        rgba(37, 99, 235, 1) 100%
      )`;
    }
    body.style.backgroundAttachment = 'fixed';
    body.style.minHeight = '100vh';
  };

  // Update background on initial load
  useEffect(() => {
    updateBodyBackground(currentTheme);
  }, [currentTheme]);

  return (
    <ThemeContext.Provider value={{ currentTheme, toggleTheme }}>
      <ConfigProvider
        theme={{
          algorithm: currentTheme === 'dark' ? theme.darkAlgorithm : theme.defaultAlgorithm,
        }}
      >
        {children}
      </ConfigProvider>
    </ThemeContext.Provider>
  );
};

export const useTheme = () => {
  const context = useContext(ThemeContext);
  if (context === undefined) {
    throw new Error('useTheme must be used within a ThemeProvider');
  }
  return context;
};

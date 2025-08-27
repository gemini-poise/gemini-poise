import React from 'react'
import ReactDOM from 'react-dom/client'
import App from './App.jsx'
import './index.css'
import 'antd/dist/reset.css';
import { BrowserRouter } from 'react-router';
import { AuthProvider } from './contexts/AuthContext';
import { ThemeProvider } from './contexts/ThemeContext';
import i18n from './i18n'; // Import i18n instance
import dayjs from 'dayjs';
import 'dayjs/locale/zh-cn'; // Import Chinese locale for dayjs
import 'dayjs/locale/en'; // Import English locale for dayjs

// // Set dayjs locale based on i18n language changes
// i18n.on('languageChanged', (lng) => {
//   dayjs.locale(lng === 'zh' ? 'zh-cn' : 'en');
// });
//
// // Set initial dayjs locale
// dayjs.locale(i18n.language === 'zh' ? 'zh-cn' : 'en');

ReactDOM.createRoot(document.getElementById('root')).render(
  <React.StrictMode>
    <BrowserRouter>
      <ThemeProvider>
        <AuthProvider>
          <App />
        </AuthProvider>
      </ThemeProvider>
    </BrowserRouter>
  </React.StrictMode>,
)

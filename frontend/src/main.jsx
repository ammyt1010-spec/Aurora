import React from 'react';
import ReactDOM from 'react-dom/client';

import { AppProviders } from './AppProviders.jsx';
import { ToastProvider } from './components/ui/Toast.jsx';
import './index.css';
import './brand/brand-tokens.css';
import './design/aurora-brand.css';

ReactDOM.createRoot(document.getElementById('root')).render(
  <React.StrictMode>
    <ToastProvider>
      <AppProviders />
    </ToastProvider>
  </React.StrictMode>,
);

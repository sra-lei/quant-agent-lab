import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { ConfigProvider } from 'antd'
import zhCN from 'antd/locale/zh_CN'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { BrowserRouter, Route, Routes } from 'react-router-dom'

import AppLayout from './components/AppLayout'
import Dashboard from './pages/Dashboard'
import Signals from './pages/Signals'
import Strategies from './pages/Strategies'
import Runs from './pages/Runs'
import Reviews from './pages/Reviews'
import Agents from './pages/Agents'
import Reports from './pages/Reports'
import './styles.css'

const queryClient = new QueryClient({
  defaultOptions: { queries: { retry: 1, refetchOnWindowFocus: false } },
})

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <ConfigProvider locale={zhCN}>
      <QueryClientProvider client={queryClient}>
        <BrowserRouter>
          <Routes>
            <Route path="/" element={<AppLayout />}>
              <Route index element={<Dashboard />} />
              <Route path="signals" element={<Signals />} />
              <Route path="strategies" element={<Strategies />} />
              <Route path="agents" element={<Agents />} />
              <Route path="reports" element={<Reports />} />
              <Route path="runs" element={<Runs />} />
              <Route path="reviews" element={<Reviews />} />
            </Route>
          </Routes>
        </BrowserRouter>
      </QueryClientProvider>
    </ConfigProvider>
  </StrictMode>,
)

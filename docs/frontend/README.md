# 前端开发指南

本文档提供前端开发者集成宠物饮食计划智能助手 API 的完整指南。

---

## 目录

1. [快速开始](#快速开始)
2. [技术栈](#技术栈)
3. [项目初始化](#项目初始化)
4. [认证集成](#认证集成)
5. [接口封装](#接口封装)
6. [状态管理](#状态管理)
7. [路由配置](#路由配置)
8. [组件库](#组件库)
9. [样式规范](#样式规范)
10. [最佳实践](#最佳实践)

---

## 快速开始

### 环境要求

```bash
# 1. 克隆项目
git clone https://github.com/your-org/pet-food.git
cd pet-food

# 2. 安装依赖
npm install
# 或使用 pnpm
pnpm install
```

### 环境变量配置

创建 `.env.local` 文件：

```env
# API 地址
VITE_API_BASE_URL=http://localhost:8000/api/v1

# 开发环境
VITE_DEV=true
```

### 启动开发服务器

```bash
# 启动开发服务器
npm run dev

# 访问 API 文档
# http://localhost:8000/docs
```

---

## 技术栈

### React (推荐)

- React 18+
- TypeScript
- Vite
- Axios
- React Router v6+
- Zustand / Redux Toolkit
- Tailwind CSS / shadcn/ui
- React Query / SWR

### Vue (可选)

- Vue 3+
- TypeScript
- Vite
- Axios
- Vue Router 4+
- Pinia
- Element Plus / Ant Design Vue

### 其他框架

本项目 API 是 RESTful 风格，支持任何前端框架集成。

---

## 项目初始化

### 目录结构（推荐）

```
src/
├── api/              # API 封装
│   ├── client.ts     # Axios 客户端配置
│   ├── auth.ts       # 认证 API
│   ├── plans.ts      # 饮食计划 API
│   ├── tasks.ts      # 任务管理 API
│   └── types.ts      # TypeScript 类型定义
├── store/            # 状态管理
├── router/           # 路由配置
├── components/       # 可复用组件
└── utils/            # 工具函数
```

### Axios 客户端配置

```typescript
// src/api/client.ts
import axios from 'axios';

const apiClient = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000/api/v1',
  timeout: 30000,
  headers: {
    'Content-Type': 'application/json'
  }
});

// 请求拦截器 - 添加认证 Token
apiClient.interceptors.request.use((config) => {
  const token = localStorage.getItem('access_token');
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

// 响应拦截器 - 处理 Token 过期
apiClient.interceptors.response.use(
  async (response) => {
    if (response.status === 401) {
      // Token 过期
      const refreshToken = localStorage.getItem('refresh_token');
      if (refreshToken) {
        try {
          const refreshResponse = await axios.post(
            `${import.meta.env.VITE_API_BASE_URL}/auth/refresh`,
            { refresh_token: refreshToken }
          );

          if (refreshResponse.data.code === 0) {
            // 刷新成功，更新 Token
            localStorage.setItem('access_token', refreshResponse.data.data.access_token);
            localStorage.setItem('refresh_token', refreshResponse.data.data.refresh_token);
          } else {
            // 刷新失败，跳转登录
            window.location.href = '/login';
          }
        } catch (error) {
          console.error('Token 刷新失败:', error);
          window.location.href = '/login';
        }
      }
    }
    return response;
  }
);

// 错误拦截器 - 统一错误处理
apiClient.interceptors.response.use(
  (error) => {
    if (error.response) {
      const { status, data } = error.response;
      const errorData = data;

      // 根据 error code 显示友好提示
      const errorMessages: {
        401: '请重新登录',
        403: '资源不存在',
        404: '资源已存在',
        422: '验证码错误',
        429: '请求过于频繁',
        500: '服务器繁忙'
      };

      console.error('API Error:', status, errorData);

      // 开发环境显示详细错误
      if (import.meta.env.DEV && errorData.detail) {
        alert(`错误: ${errorMessages[status] || status}\n详情: ${errorData.detail}`);
      }
    }
  }
);

export default apiClient;
```

---

## 认证集成

### 登录组件示例（React）

```typescript
// src/components/auth/LoginForm.tsx
import { useState } from 'react';
import { login } from '@/api/auth';
import { useNavigate } from 'react-router-dom';

export const LoginForm = () => {
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const navigate = useNavigate();

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setError('');

    try {
      const result = await login(username, password);
      if (result.code === 0) {
        // 保存 Tokens
        localStorage.setItem('access_token', result.data.tokens.access_token);
        localStorage.setItem('refresh_token', result.data.tokens.refresh_token);
        localStorage.setItem('user', JSON.stringify(result.data.user));

        // 跳转到首页
        navigate('/');
      } else {
        setError(result.message);
      }
    } catch (err) {
      setError('登录失败，请重试');
    } finally {
      setLoading(false);
    }
  };

  return (
    <form onSubmit={handleSubmit}>
      {/* 登录表单 */}
    </form>
  );
};
```

### Token 自动刷新 Hook

```typescript
// src/hooks/useAuth.ts
import { useEffect, useCallback } from 'react';
import { apiClient } from '@/api/client';
import { useNavigate } from 'react-router-dom';

export const useAuth = () => {
  const navigate = useNavigate();

  const refreshToken = useCallback(async () => {
    try {
      const refreshToken = localStorage.getItem('refresh_token');
      if (!refreshToken) return false;

      const response = await apiClient.post('/auth/refresh', {
        refresh_token: refreshToken
      });

      if (response.data.code === 0) {
        localStorage.setItem('access_token', response.data.data.access_token);
        localStorage.setItem('refresh_token', response.data.data.refresh_token);
        return true;
      }
    } catch (error) {
      console.error('Token 刷新失败:', error);
      localStorage.clear();
      navigate('/login');
      return false;
    }
  }, []);

  return { refreshToken };
};
```

---

## 状态管理

### Zustand Store 示例

```typescript
// src/store/authStore.ts
import { create } from 'zustand';

interface AuthState {
  user: User | null;
  accessToken: string | null;
  refreshToken: string | null;
  isAuthenticated: boolean;
}

interface AuthActions {
  setUser: (user: User) => void;
  setTokens: (accessToken: string, refreshToken: string) => void;
  logout: () => void;
}

export const useAuthStore = create<AuthState & AuthActions>((set) => ({
  user: null,
  accessToken: null,
  refreshToken: null,
  isAuthenticated: false,
  setUser: (user) => set({ user, isAuthenticated: !!user }),
  setTokens: (accessToken, refreshToken) => set({ accessToken, refreshToken, isAuthenticated: true }),
  logout: () => set({
    user: null,
    accessToken: null,
    refreshToken: null,
    isAuthenticated: false
  }),
}));
```

### Context Provider 示例

```typescript
// src/contexts/AuthContext.tsx
import { createContext, useContext, useState, ReactNode } from 'react';

interface AuthContextType {
  user: User | null;
  login: (username: string, password: string) => Promise<void>;
  logout: () => void;
  isAuthenticated: boolean;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export const AuthProvider = ({ children }: { children: ReactNode }) => {
  const [user, setUser] = useState<User | null>(null);
  const [isAuthenticated, setAuthenticated] = useState(false);

  const login = async (username: string, password: string) => {
    // 调用 API 登录
    // 保存用户信息和 Token
    setAuthenticated(true);
  };

  const logout = () => {
    // 清除 Token
    setAuthenticated(false);
    setUser(null);
  };

  return (
    <AuthContext.Provider value={{ user, login, logout, isAuthenticated }}>
      {children}
    </AuthContext.Provider>
  );
};
```

---

## 路由配置

### React Router 示例

```typescript
// src/App.tsx
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { useAuthStore } from '@/store/authStore';
import { LoginPage } from '@/pages/Login';
import { DashboardPage } from '@/pages/Dashboard';

function ProtectedRoute({ children }: { children: ReactNode }) {
  const isAuthenticated = useAuthStore(state => state.isAuthenticated);

  if (!isAuthenticated) {
    return <Navigate to="/login" replace />;
  }

  return <>{children}</>;
}

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/login" element={<LoginPage />} />
        <Route path="/dashboard" element={
          <ProtectedRoute>
            <DashboardPage />
          </ProtectedRoute>
        } />
        <Route path="/" element={<Navigate to="/dashboard" />} />
      </Routes>
    </BrowserRouter>
  );
}
```

### Vue Router 示例

```typescript
// src/router/index.ts
import { createRouter, createWebHistory } from 'vue-router';
import { useAuthStore } from '@/store/authStore';

const router = createRouter({
  history: createWebHistory(),
  routes: [
    {
      path: '/login',
      name: 'Login',
      component: () => import('@/views/Login.vue'),
      meta: { requiresAuth: false }
    },
    {
      path: '/dashboard',
      name: 'Dashboard',
      component: () => import('@/views/Dashboard.vue'),
      meta: { requiresAuth: true }
    }
  ]
});

router.beforeEach((to, from, next) => {
  const isAuthenticated = useAuthStore().isAuthenticated;
  const requiresAuth = to.meta.requiresAuth;

  if (requiresAuth && !isAuthenticated) {
    return next({ name: 'Login', query: { redirect: to.fullPath } });
  }

  next();
});
```

---

## 组件库

### shadcn/ui 推荐使用

项目推荐使用 [shadcn/ui](https://ui.shadcn.com/) 作为基础组件库，提供：

- **Form 组件**: 表单输入
- **Button 组件**: 按钮
- **Card 组件**: 卡片容器
- **Input 组件**: 文本输入
- **Select 组件**: 下拉选择
- **Dialog 组件**: 对话框
- **Toast 组件**: 消息提示

### 安装 shadcn/ui

```bash
npx shadcn-ui@latest init
```

### 组件示例

```typescript
// 基于表单的宠物信息输入组件
import { Form, FormField, FormItem, FormLabel, FormControl } from '@/components/ui/form';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/card';

interface PetFormData {
  petType: 'dog' | 'cat';
  petBreed: string;
  age: number;
  weight: number;
  healthStatus: 'healthy' | 'sick';
  specialRequirements?: string;
}

export const PetForm = () => {
  const [formData, setFormData] = useState<PetFormData>({
    petType: 'dog',
    petBreed: '',
    age: 2,
    weight: 10,
    healthStatus: 'healthy'
  });

  const handleSubmit = async () => {
    // 调用创建计划 API
    // 处理响应
  };

  return (
    <Card className="w-full max-w-2xl">
      <CardHeader>
        <CardTitle>宠物信息</CardTitle>
      </CardHeader>
      <CardContent>
        <Form {...form}>
          {/* 表单字段 */}
        </Form>
      </CardContent>
    </Card>
  );
};
```

---

## 样式规范

### Tailwind CSS 类命名约定

| 用途 | 命名格式 | 示例 |
|------|----------|------|
| 布局 | `flex` 或 `grid` | `flex justify-center`, `grid grid-cols-2` |
| 间距 | `space` 或 `p` | `p-4`, `mt-2` |
| 间距 - | 内边距 | `mx-2`, `my-4` |
| 间距 - | 外边距 | `mx-4`, `my-6` |
| 文字 | `text` 或 `font` | `text-sm`, `text-lg` |
| 宽度 | `w` | `w-full`, `w-1/2` |
| 圆角 | `rounded` | `rounded`, `rounded-lg` |
| 颜色 | `bg` 或 `text` | `bg-white`, `bg-gray-50` |
| 边框 | `border` | `border`, `border-gray-200` |

### 响应式断点

| 断点 | 宽度 | 用途 |
|------|------|------|
| sm | 640px | 手机竖屏 |
| md | 768px | 平板横屏 |
| lg | 1024px | 平板横屏 |
| xl | 1280px | 桌面 |

---

## 最佳实践

### 1. 代码组织

- 按功能模块划分目录
- 复用公共组件
- 统一导出接口和类型
- 使用绝对路径导入

### 2. 性能优化

- 使用 React.memo 跳过不必要的渲染
- 使用 React.lazy 懒加载路由
- 使用 React Query 缓存 API 响应
- 图片懒加载

### 3. 安全

- 所有 API 请求使用 HTTPS
- Token 存储在 localStorage（生产环境考虑 Cookie）
- 敏感信息不在 URL 中传递
- 输入数据严格验证

### 4. 用户体验

- 骨架加载时显示骨架屏
- 操作反馈显示 Toast 提示
- 错误时显示友好提示
- 长时间操作显示进度

### 5. 测试

- 使用 MSW (Mock Service Worker) 模拟 API 响应
- 编写组件单元测试
- 编写 E2E 测试用例

---

## 相关文档

- [API 接口文档](../api/)
- [API 错误码说明](../API_ERRORS.md)
- [API 配置说明](../API_CONFIG.md)
- [系统架构图](../ARCHITECTURE.md)

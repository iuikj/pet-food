# 前端对接指南

> Pet-Food API 完整对接文档 - API 接口 + 数据结构 + TypeScript 类型

---

## 目录

1. [API 基础信息](#api-基础信息)
2. [认证模块](#认证模块)
3. [饮食计划模块](#饮食计划模块)
4. [任务管理模块](#任务管理模块)
5. [SSE 流式模块](#sse-流式模块)
6. [宠物管理模块](#宠物管理模块)
7. [饮食记录模块](#饮食记录模块)
8. [日历功能模块](#日历功能模块)
9. [营养分析模块](#营养分析模块)
10. [TypeScript 类型定义](#typescript-类型定义)
11. [完整代码示例](#完整代码示例)

---

## API 基础信息

```
Base URL: http://localhost:8000/api/v1
认证方式: JWT Bearer Token
响应格式: { code: number, message: string, data: any }
```

### 通用响应结构

```typescript
interface ApiResponse<T = any> {
  code: number;        // 0=成功, 其他为错误码
  message: string;       // 描述信息
  data: T;             // 响应数据
}
```

### 错误码

| code | 含义 | HTTP Status |
|------|------|-----------|
| 0 | 成功 | 200 |
| 400 | 请求参数错误 | 400 |
| 401 | 未认证/Token 过期 | 401 |
| 403 | 资源不存在 | 403 |
| 404/409 | 资源已存在 | 404 |
| 422 | 验证失败 | 422 |
| 429 | 请求过于频繁 | 429 |
| 500 | 服务器内部错误 | 500 |

---

## 认证模块

### 1. 用户注册

**请求：** `POST /auth/register`

**Request 数据结构：**
```typescript
interface RegisterRequest {
  username: string;      // 必填，3-50 字符，字母数字下划线
  email: string;        // 必填，有效邮箱格式
  password: string;       // 必填，至少 6 位字符
}
```

**Response 数据结构：**
```typescript
interface RegisterResponse {
  user: UserInfo;
  tokens: TokenData;
}
```

---

### 2. 验证码注册

**请求：** `POST /auth/verify-register`

**Request 数据结构：**
```typescript
interface VerifyRegisterRequest extends RegisterRequest {
  code: string;  // 6 位数字验证码
}
```

---

### 3. 发送验证码

**请求：** `POST /auth/send-code`

**Request 数据结构：**
```typescript
interface SendCodeRequest {
  email: string;           // 必填，有效邮箱格式
  code_type: 'register' | 'password_reset';  // 验证码类型
}
```

---

### 4. 用户登录

**请求：** `POST /auth/login`

**Request 数据结构：**
```typescript
interface LoginRequest {
  username: string;   // 必填，用户名或邮箱
  password: string;  // 必填，用户密码
}
```

---

### 5. 刷新 Token

**请求：** `POST /auth/refresh`

**Request Headers：**
```
Authorization: Bearer {refresh_token}
```

---

### 6. 获取用户信息

**请求：** `GET /auth/me`

---

### 7. 修改密码

**请求：** `PUT /auth/password`

**Request 数据结构：**
```typescript
interface ChangePasswordRequest {
  old_password: string;  // 必填，当前密码
  new_password: string;  // 必填，新密码，至少 6 位
}
```

---

### 8. 找回密码 - 发送验证码

**请求：** `POST /auth/password/send-code`

---

### 9. 找回密码 - 重置密码

**请求：** `POST /auth/password/reset`

---

### 10. 更新用户信息 ✨ 新增

**请求：** `PUT /auth/profile`

**Request 数据结构：**
```typescript
interface UpdateProfileRequest {
  nickname?: string;  // 昵称（可选）
  phone?: string;     // 手机号（可选）
}
```

**Response 数据结构：**
```typescript
interface UserProfileResponse {
  id: string;
  username: string;
  email: string;
  nickname?: string;
  phone?: string;
  avatar_url?: string;
  is_pro: boolean;
  plan_type?: 'monthly' | 'yearly';
  subscription_expired_at?: string;
  created_at: string;
}
```

---

### 11. 上传用户头像 ✨ 新增

**请求：** `POST /auth/avatar`

**Request Headers：**
```
Content-Type: multipart/form-data
```

**Request Body：**
```
file: Binary  // 头像文件，支持 jpg/png/webp，最大 2MB
```

**Response 数据结构：**
```typescript
interface AvatarUploadResponse {
  avatar_url: string;
}
```

---

### 12. 获取订阅状态 ✨ 新增

**请求：** `GET /auth/subscription`

**Response 数据结构：**
```typescript
interface SubscriptionStatusResponse {
  is_pro: boolean;
  plan_type?: 'monthly' | 'yearly';
  subscription_expired_at?: string;
  is_expired: boolean;
  days_remaining?: number;
}
```

---

## 饮食计划模块

### 1. 创建饮食计划（异步，后台执行）

**请求：** `POST /plans/`

**Request 数据结构：**
```typescript
interface CreatePlanRequest {
  pet_type: 'cat' | 'dog';  // 必填，宠物类型
  pet_breed?: string;           // 可选，品种
  pet_age: number;               // 必填，年龄（月）
  pet_weight: number;             // 必填，体重（千克）
  health_status?: string;         // 可选，健康状况
  special_requirements?: string;   // 可选，特殊需求
}
```

---

### 2. 创建饮食计划（流式 SSE）

**请求：** `POST /plans/stream`

**SSE 事件类型：**

| 事件 | 数据格式 | 说明 |
|------|----------|------|
| `task_created` | `{ type, task_id }` | 任务创建成功，返回 task_id |
| `node_started` | `{ type, node, timestamp }` | Agent 节点开始 |
| `node_completed` | `{ type, node, progress?, timestamp }` | Agent 节点完成 |
| `tool_started` | `{ type, node, tool, input?, timestamp }` | 工具开始调用 |
| `tool_completed` | `{ type, node, tool, output?, timestamp }` | 工具调用完成 |
| `task_completed` | `{ type, task_id, result? }` | 任务完成 |
| `error` | `{ type, error }` | 错误发生 |

---

### 3. 获取计划列表

**请求：** `GET /plans/`

---

### 4. 获取计划详情

**请求：** `GET /plans/{plan_id}`

---

### 5. 删除计划

**请求：** `DELETE /plans/{plan_id}`

---

## 任务管理模块

### 1. 获取任务列表

**请求：** `GET /tasks/`

---

### 2. 获取任务详情

**请求：** `GET /tasks/{task_id}`

---

### 3. 取消任务

**请求：** `DELETE /tasks/{task_id}`

---

### 4. 获取任务结果

**请求：** `GET /tasks/{task_id}/result`

---

## SSE 流式模块

### 1. 创建流式任务

**请求：** `POST /plans/stream`

---

### 2. 恢复 SSE 连接（断线重连）

**请求：** `GET /plans/stream?task_id={task_id}`

---

## 宠物管理模块 ✨ 新增

### 1. 获取宠物列表

**请求：** `GET /pets/`

**Query 参数：**
```typescript
interface GetPetsParams {
  is_active?: boolean;  // 可选，是否仅返回未删除的宠物，默认 true
}
```

**Response 数据结构：**
```typescript
interface PetListResponse {
  total: number;
  items: PetResponse[];
}

interface PetResponse {
  id: string;
  user_id: string;
  name: string;
  type: 'cat' | 'dog';
  breed?: string;
  age: number;              // 月
  weight: number;            // kg
  gender?: 'male' | 'female';
  avatar_url?: string;
  health_status?: string;
  special_requirements?: string;
  is_active: boolean;
  has_plan: boolean;          // 是否有饮食计划
  created_at: string;
  updated_at: string;
}
```

---

### 2. 创建宠物

**请求：** `POST /pets/`

**Request 数据结构：**
```typescript
interface CreatePetRequest {
  name: string;                      // 必填，宠物名称
  type: 'cat' | 'dog';            // 必填，宠物类型
  breed?: string;                     // 可选，品种
  age: number;                       // 必填，年龄（月）
  weight: number;                     // 必填，体重（kg）
  gender?: 'male' | 'female';       // 可选，性别
  health_status?: string;             // 可选，健康状况
  special_requirements?: string;       // 可选，特殊需求
}
```

---

### 3. 获取宠物详情

**请求：** `GET /pets/{pet_id}`

---

### 4. 更新宠物

**请求：** `PUT /pets/{pet_id}`

**Request 数据结构：**
```typescript
interface UpdatePetRequest {
  name?: string;
  type?: 'cat' | 'dog';
  breed?: string;
  age?: number;
  weight?: number;
  gender?: 'male' | 'female';
  health_status?: string;
  special_requirements?: string;
}
```

---

### 5. 删除宠物

**请求：** `DELETE /pets/{pet_id}`

**说明：** 软删除，设置 `is_active = false`

---

### 6. 上传宠物头像

**请求：** `POST /pets/{pet_id}/avatar`

**Request Headers：**
```
Content-Type: multipart/form-data
```

**Request Body：**
```
file: Binary  // 头像文件，支持 jpg/png/webp，最大 2MB
```

---

## 饮食记录模块 ✨ 新增

### 1. 获取今日餐食

**请求：** `GET /meals/today?pet_id={pet_id}`

**Response 数据结构：**
```typescript
interface TodayMealsResponse {
  date: string;               // YYYY-MM-DD
  meals: MealDetail[];
  nutrition_summary: NutritionSummary;
}

interface MealDetail {
  id: string;
  type: 'breakfast' | 'lunch' | 'dinner' | 'snack';
  name: string;
  time: string;              // HH:mm
  description?: string;
  calories?: number;
  is_completed: boolean;
  completed_at?: string;
  notes?: string;
  food_items?: any[];
  nutrition_data?: any;
  ai_tip?: string;
}

interface NutritionSummary {
  total_calories: number;
  consumed_calories: number;
  protein: { target: number; consumed: number };
  fat: { target: number; consumed: number };
  carbs: { target: number; consumed: number };
}
```

---

### 2. 获取指定日期餐食

**请求：** `GET /meals/date?pet_id={pet_id}&target_date={date}`

**Query 参数：**
```typescript
interface GetMealsByDateParams {
  pet_id: string;
  target_date: string;  // YYYY-MM-DD
}
```

---

### 3. 标记餐食完成

**请求：** `POST /meals/{meal_id}/complete`

**Request Body（可选）：**
```typescript
interface CompleteMealRequest {
  notes?: string;  // 备注（可选）
}
```

**Response 数据结构：**
```typescript
interface MealCompleteResponse {
  meal_id: string;
  is_completed: true;
  completed_at: string;
}
```

---

### 4. 取消餐食完成标记

**请求：** `DELETE /meals/{meal_id}/complete`

---

### 5. 获取餐食历史

**请求：** `GET /meals/history`

**Query 参数：**
```typescript
interface GetMealHistoryParams {
  pet_id: string;
  start_date?: string;  // YYYY-MM-DD
  end_date?: string;    // YYYY-MM-DD
  page?: number;        // 默认 1
  page_size?: number;    // 默认 10，最大 100
}
```

**Response 数据结构：**
```typescript
interface MealHistoryResponse {
  total: number;
  page: number;
  page_size: number;
  items: MealDetail[];
}
```

---

## 日历功能模块 ✨ 新增

### 1. 获取月度日历

**请求：** `GET /calendar/monthly`

**Query 参数：**
```typescript
interface GetMonthlyCalendarParams {
  pet_id: string;
  year?: number;   // 可选，默认当前年
  month?: number;  // 可选，默认当前月
}
```

**Response 数据结构：**
```typescript
interface MonthlyCalendarResponse {
  year: number;
  month: number;
  days: CalendarDay[];
}

interface CalendarDay {
  date: string;               // YYYY-MM-DD
  has_plan: boolean;
  completion_rate: number;     // 0-100
  total_meals: number;
  completed_meals: number;
  status: 'excellent' | 'good' | 'normal' | 'poor' | 'none';
}
```

---

### 2. 获取周视图

**请求：** `GET /calendar/weekly`

**Query 参数：**
```typescript
interface GetWeeklyCalendarParams {
  pet_id: string;
  start_date?: string;  // YYYY-MM-DD，可选，默认本周一
}
```

**Response 数据结构：**
```typescript
interface WeeklyCalendarResponse {
  week_number: number;
  start_date: string;
  end_date: string;
  days: WeekDay[];
}

interface WeekDay {
  date: string;
  day_of_week: number;      // 1-7，周日为 7
  has_plan: boolean;
  completion_rate: number;
  meals: MealDetail[];
}
```

---

## 营养分析模块 ✨ 新增

### 1. 获取营养分析

**请求：** `GET /analysis/nutrition`

**Query 参数：**
```typescript
interface GetNutritionAnalysisParams {
  pet_id: string;
  period?: 'week' | 'month' | 'year';  // 默认 week
}
```

**Response 数据结构：**
```typescript
interface NutritionAnalysisResponse {
  period: 'week' | 'month' | 'year';
  summary: NutritionSummary;
  daily_data: DailyNutritionData[];
  trend_chart: TrendChart;
  ai_insights: AIInsight[];
}

interface DailyNutritionData {
  date: string;
  calories: number;
  protein: number;
  fat: number;
  carbs: number;
  completion_rate: number;
}

interface TrendChart {
  calories: number[];
  protein: number[];
  fat: number[];
  carbs: number[];
  dates: string[];
}

interface AIInsight {
  type: 'positive' | 'suggestion' | 'warning';
  content: string;
}
```

---

## API 端点速查表

| 模块 | 方法 | 路径 | 说明 |
|------|------|------|----------|
| **认证** | | | |
| 认证 | 注册 | POST `/auth/register` | 直接注册 |
| 认证 | 登录 | POST `/auth/login` | 用户名/邮箱登录 |
| 认证 | 刷新 | POST `/auth/refresh` | 刷新 Access Token |
| 认证 | 获取用户 | GET `/auth/me` | 获取用户信息 |
| 认证 | 发送验证码 | POST `/auth/send-code` | 发送邮箱验证码 |
| 认证 | 验证码 | POST `/auth/verify-code` | 验证验证码 |
| 认证 | 验证注册 | POST `/auth/verify-register` | 验证码注册 |
| 认证 | 修改密码 | PUT `/auth/password` | 修改密码 |
| 认证 | 找回密码-发送验证码 | POST `/auth/password/send-code` | 找回密码验证码 |
| 认证 | 找回密码-重置密码 | POST `/auth/password/reset` | 重置密码 |
| 认证 | 更新用户信息 | PUT `/auth/profile` | ✨ 新增 |
| 认证 | 上传用户头像 | POST `/auth/avatar` | ✨ 新增 |
| 认证 | 获取订阅状态 | GET `/auth/subscription` | ✨ 新增 |
| **计划** | | | |
| 计划 | 创建（异步） | POST `/plans/` | 创建计划，后台执行 |
| 计划 | 创建（流式） | POST `/plans/stream` | 创建计划，SSE 流式 |
| 计划 | 获取列表 | GET `/plans/` | 获取计划列表 |
| 计划 | 获取详情 | GET `/plans/{plan_id}` | 获取计划详情 |
| 计划 | 删除 | DELETE `/plans/{plan_id}` | 删除计划 |
| **任务** | | | |
| 任务 | 获取列表 | GET `/tasks/` | 获取任务列表 |
| 任务 | 获取详情 | GET `/tasks/{task_id}` | 获取任务详情 |
| 任务 | 取消 | DELETE `/tasks/{task_id}` | 取消任务 |
| 任务 | 获取结果 | GET `/tasks/{task_id}/result` | 获取任务结果 |
| 任务 | 流式监听 | GET `/tasks/{task_id}/stream` | SSE 流式监听任务 |
| **宠物** | | | |
| 宠物 | 获取列表 | GET `/pets/` | ✨ 新增 |
| 宠物 | 创建 | POST `/pets/` | ✨ 新增 |
| 宠物 | 获取详情 | GET `/pets/{pet_id}` | ✨ 新增 |
| 宠物 | 更新 | PUT `/pets/{pet_id}` | ✨ 新增 |
| 宠物 | 删除 | DELETE `/pets/{pet_id}` | ✨ 新增 |
| 宠物 | 上传头像 | POST `/pets/{pet_id}/avatar` | ✨ 新增 |
| **饮食记录** | | | |
| 饮食 | 获取今日餐食 | GET `/meals/today` | ✨ 新增 |
| 饮食 | 获取指定日期餐食 | GET `/meals/date` | ✨ 新增 |
| 饮食 | 标记完成 | POST `/meals/{meal_id}/complete` | ✨ 新增 |
| 饮食 | 取消完成 | DELETE `/meals/{meal_id}/complete` | ✨ 新增 |
| 饮食 | 获取历史 | GET `/meals/history` | ✨ 新增 |
| **日历** | | | |
| 日历 | 月度日历 | GET `/calendar/monthly` | ✨ 新增 |
| 日历 | 周视图 | GET `/calendar/weekly` | ✨ 新增 |
| **营养分析** | | | |
| 分析 | 营养分析 | GET `/analysis/nutrition` | ✨ 新增 |

---

## TypeScript 类型定义

### 通用类型

```typescript
// 基础响应
interface ApiResponse<T = any> {
  code: number;
  message: string;
  data: T;
}

// 分页参数
interface PaginationParams {
  page?: number;
  page_size?: number;
}

// 分页响应
interface PaginatedResponse<T> {
  total: number;
  page: number;
  page_size: number;
  items: T[];
}
```

### 认证类型

```typescript
// 请求类型
interface LoginRequest {
  username: string;
  password: string;
}

interface RegisterRequest {
  username: string;
  email: string;
  password: string;
}

interface VerifyRegisterRequest extends RegisterRequest {
  code: string;
}

interface SendCodeRequest {
  email: string;
  code_type: 'register' | 'password_reset';
}

interface ChangePasswordRequest {
  old_password: string;
  new_password: string;
}

interface ResetPasswordRequest {
  email: string;
  code: string;
  new_password: string;
}

// 用户信息
interface UserInfo {
  id: string;
  username: string;
  email: string;
  nickname?: string;
  phone?: string;
  avatar_url?: string;
  is_pro: boolean;
  plan_type?: 'monthly' | 'yearly';
  subscription_expired_at?: string;
  is_active: boolean;
  is_superuser: boolean;
  created_at: string;
}

// Token 类型
interface TokenData {
  access_token: string;
  refresh_token: string;
  token_type: string;
  expires_in: number;
}
```

### 宠物类型 ✨ 新增

```typescript
// 宠物类型
type PetType = 'cat' | 'dog';
type PetGender = 'male' | 'female';

// 请求类型
interface CreatePetRequest {
  name: string;
  type: PetType;
  breed?: string;
  age: number;
  weight: number;
  gender?: PetGender;
  health_status?: string;
  special_requirements?: string;
}

interface UpdatePetRequest {
  name?: string;
  type?: PetType;
  breed?: string;
  age?: number;
  weight?: number;
  gender?: PetGender;
  health_status?: string;
  special_requirements?: string;
}

// 响应类型
interface PetResponse {
  id: string;
  user_id: string;
  name: string;
  type: PetType;
  breed?: string;
  age: number;
  weight: number;
  gender?: PetGender;
  avatar_url?: string;
  health_status?: string;
  special_requirements?: string;
  is_active: boolean;
  has_plan: boolean;
  created_at: string;
  updated_at: string;
}

interface PetListResponse extends PaginatedResponse<PetResponse> {}
```

### 饮食记录类型 ✨ 新增

```typescript
// 餐食类型
type MealType = 'breakfast' | 'lunch' | 'dinner' | 'snack';

interface MealDetail {
  id: string;
  type: MealType;
  name: string;
  time: string;
  description?: string;
  calories?: number;
  is_completed: boolean;
  completed_at?: string;
  notes?: string;
  food_items?: any[];
  nutrition_data?: any;
  ai_tip?: string;
}

interface NutritionSummary {
  total_calories: number;
  consumed_calories: number;
  protein: { target: number; consumed: number };
  fat: { target: number; consumed: number };
  carbs: { target: number; consumed: number };
}

interface TodayMealsResponse {
  date: string;
  meals: MealDetail[];
  nutrition_summary: NutritionSummary;
}

interface MealHistoryResponse extends PaginatedResponse<MealDetail> {}
```

### 日历类型 ✨ 新增

```typescript
type CalendarStatus = 'excellent' | 'good' | 'normal' | 'poor' | 'none';

interface CalendarDay {
  date: string;
  has_plan: boolean;
  completion_rate: number;
  total_meals: number;
  completed_meals: number;
  status: CalendarStatus;
}

interface MonthlyCalendarResponse {
  year: number;
  month: number;
  days: CalendarDay[];
}

interface WeekDay extends CalendarDay {
  day_of_week: number;  // 1-7，周日为 7
  meals: MealDetail[];
}

interface WeeklyCalendarResponse {
  week_number: number;
  start_date: string;
  end_date: string;
  days: WeekDay[];
}
```

### 营养分析类型 ✨ 新增

```typescript
type InsightType = 'positive' | 'suggestion' | 'warning';

interface DailyNutritionData {
  date: string;
  calories: number;
  protein: number;
  fat: number;
  carbs: number;
  completion_rate: number;
}

interface TrendChart {
  calories: number[];
  protein: number[];
  fat: number[];
  carbs: number[];
  dates: string[];
}

interface AIInsight {
  type: InsightType;
  content: string;
}

interface NutritionAnalysisResponse {
  period: 'week' | 'month' | 'year';
  summary: NutritionSummary;
  daily_data: DailyNutritionData[];
  trend_chart: TrendChart;
  ai_insights: AIInsight[];
}
```

---

## 完整代码示例

### Axios 客户端配置

```typescript
// src/api/client.ts
import axios, { AxiosInstance, InternalAxiosRequestConfig } from 'axios';

const API_BASE_URL = 'http://localhost:8000/api/v1';

export const apiClient: AxiosInstance = axios.create({
  baseURL: API_BASE_URL,
  timeout: 30000,
  headers: {
    'Content-Type': 'application/json',
  },
});

// 请求拦截器 - 添加 Token
apiClient.interceptors.request.use((config) => {
  const token = localStorage.getItem('access_token');
  if (token && config.headers) {
    (config.headers as Record<string, string>).Authorization = `Bearer ${token}`;
  }
  return config;
});

// 响应拦截器 - 统一错误处理
apiClient.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      // Token 过期，尝试刷新
      const refreshToken = localStorage.getItem('refresh_token');
      if (refreshToken) {
        return refreshAccessToken(refreshToken).then(() => {
          return axios(error.config);
        });
      }
    }
    return Promise.reject(error);
  }
);

export default apiClient;
```

### 认证服务

```typescript
// src/api/auth.ts
import apiClient from './client';
import type {
  ApiResponse,
  LoginRequest,
  RegisterRequest,
  ChangePasswordRequest,
  UpdateProfileRequest,
  TokenData,
  UserInfo,
  SubscriptionStatusResponse,
} from './types';

export async function login(data: LoginRequest): Promise<ApiResponse<{ user: UserInfo; tokens: TokenData }>> {
  return apiClient.post<ApiResponse<{ user: UserInfo; tokens: TokenData }>>('/auth/login', data)
    .then(res => res.data);
}

export async function refreshToken(refreshToken: string): Promise<ApiResponse<TokenData>> {
  return apiClient.post<ApiResponse<TokenData>>('/auth/refresh', { refresh_token })
    .then(res => res.data);
}

export async function getMe(): Promise<ApiResponse<UserInfo>> {
  return apiClient.get<ApiResponse<UserInfo>>('/auth/me')
    .then(res => res.data);
}

export async function updateProfile(data: UpdateProfileRequest): Promise<ApiResponse<UserInfo>> {
  return apiClient.put<ApiResponse<UserInfo>>('/auth/profile', data)
    .then(res => res.data);
}

export async function uploadAvatar(file: File): Promise<ApiResponse<{ avatar_url: string }>> {
  const formData = new FormData();
  formData.append('file', file);
  return apiClient.post<ApiResponse<{ avatar_url: string }>>('/auth/avatar', formData, {
    headers: { 'Content-Type': 'multipart/form-data' }
  }).then(res => res.data);
}

export async function getSubscription(): Promise<ApiResponse<SubscriptionStatusResponse>> {
  return apiClient.get<ApiResponse<SubscriptionStatusResponse>>('/auth/subscription')
    .then(res => res.data);
}
```

### 宠物管理服务 ✨ 新增

```typescript
// src/api/pets.ts
import apiClient from './client';
import type {
  ApiResponse,
  CreatePetRequest,
  UpdatePetRequest,
  PetResponse,
  PetListResponse,
} from './types';

export async function getPets(isActive = true): Promise<ApiResponse<PetListResponse>> {
  return apiClient.get<ApiResponse<PetListResponse>>('/pets/', {
    params: { is_active: isActive }
  }).then(res => res.data);
}

export async function createPet(data: CreatePetRequest): Promise<ApiResponse<PetResponse>> {
  return apiClient.post<ApiResponse<PetResponse>>('/pets/', data)
    .then(res => res.data);
}

export async function getPet(petId: string): Promise<ApiResponse<PetResponse>> {
  return apiClient.get<ApiResponse<PetResponse>>(`/pets/${petId}`)
    .then(res => res.data);
}

export async function updatePet(petId: string, data: UpdatePetRequest): Promise<ApiResponse<PetResponse>> {
  return apiClient.put<ApiResponse<PetResponse>>(`/pets/${petId}`, data)
    .then(res => res.data);
}

export async function deletePet(petId: string): Promise<ApiResponse<{ pet_id: string }>> {
  return apiClient.delete<ApiResponse<{ pet_id: string }>>(`/pets/${petId}`)
    .then(res => res.data);
}

export async function uploadPetAvatar(petId: string, file: File): Promise<ApiResponse<{ avatar_url: string }>> {
  const formData = new FormData();
  formData.append('file', file);
  return apiClient.post<ApiResponse<{ avatar_url: string }>>(`/pets/${petId}/avatar`, formData, {
    headers: { 'Content-Type': 'multipart/form-data' }
  }).then(res => res.data);
}
```

### 饮食记录服务 ✨ 新增

```typescript
// src/api/meals.ts
import apiClient from './client';
import type {
  ApiResponse,
  TodayMealsResponse,
  MealHistoryResponse,
  NutritionAnalysisResponse,
} from './types';

export async function getTodayMeals(petId: string): Promise<ApiResponse<TodayMealsResponse>> {
  return apiClient.get<ApiResponse<TodayMealsResponse>>('/meals/today', {
    params: { pet_id: petId }
  }).then(res => res.data);
}

export async function getMealsByDate(petId: string, date: string): Promise<ApiResponse<TodayMealsResponse>> {
  return apiClient.get<ApiResponse<TodayMealsResponse>>('/meals/date', {
    params: { pet_id: petId, target_date: date }
  }).then(res => res.data);
}

export async function completeMeal(mealId: string, notes?: string): Promise<ApiResponse<{ meal_id: string; is_completed: true }>> {
  return apiClient.post<ApiResponse<{ meal_id: string; is_completed: true }>>(`/meals/${mealId}/complete`, { notes })
    .then(res => res.data);
}

export async function uncompleteMeal(mealId: string): Promise<ApiResponse<{ meal_id: string; is_completed: false }>> {
  return apiClient.delete<ApiResponse<{ meal_id: string; is_completed: false }>>(`/meals/${mealId}/complete`)
    .then(res => res.data);
}

export async function getMealHistory(
  petId: string,
  params?: { start_date?: string; end_date?: string; page?: number; page_size?: number }
): Promise<ApiResponse<MealHistoryResponse>> {
  return apiClient.get<ApiResponse<MealHistoryResponse>>('/meals/history', {
    params: { pet_id: petId, ...params }
  }).then(res => res.data);
}
```

### 日历服务 ✨ 新增

```typescript
// src/api/calendar.ts
import apiClient from './client';
import type {
  ApiResponse,
  MonthlyCalendarResponse,
  WeeklyCalendarResponse,
} from './types';

export async function getMonthlyCalendar(
  petId: string,
  year?: number,
  month?: number
): Promise<ApiResponse<MonthlyCalendarResponse>> {
  return apiClient.get<ApiResponse<MonthlyCalendarResponse>>('/calendar/monthly', {
    params: { pet_id: petId, year, month }
  }).then(res => res.data);
}

export async function getWeeklyCalendar(
  petId: string,
  startDate?: string
): Promise<ApiResponse<WeeklyCalendarResponse>> {
  return apiClient.get<ApiResponse<WeeklyCalendarResponse>>('/calendar/weekly', {
    params: { pet_id: petId, start_date: startDate }
  }).then(res => res.data);
}
```

### 营养分析服务 ✨ 新增

```typescript
// src/api/analysis.ts
import apiClient from './client';
import type { ApiResponse, NutritionAnalysisResponse } from './types';

export async function getNutritionAnalysis(
  petId: string,
  period: 'week' | 'month' | 'year' = 'week'
): Promise<ApiResponse<NutritionAnalysisResponse>> {
  return apiClient.get<ApiResponse<NutritionAnalysisResponse>>('/analysis/nutrition', {
    params: { pet_id: petId, period }
  }).then(res => res.data);
}
```

### 错误处理 Hook

```typescript
// src/hooks/useApiError.ts
import { useCallback } from 'react';
import { showToast } from '@/components/ui/toast';

const ERROR_MESSAGES: Record<number, string> = {
  3000: '创建宠物失败',
  3001: '宠物不存在',
  4000: '日期格式错误，请使用 YYYY-MM-DD',
  4001: '餐食记录不存在',
  5000: '服务器内部错误',
  5002: '不支持的文件类型',
  5003: '文件大小超过限制',
  401: '请重新登录',
  403: '资源不存在，请刷新',
  404: '用户名或邮箱已被注册',
  409: '验证码错误或已过期',
  422: '验证码错误，请重新输入',
  429: '请求过于频繁，请稍后再试',
};

export function useApiError() {
  const handleError = useCallback((error: any) => {
    if (error.response) {
      const status = error.response.status;
      const data = error.response.data as ApiResponse<null>;

      if (status && ERROR_MESSAGES[status]) {
        showToast({
          title: '操作失败',
          description: ERROR_MESSAGES[status],
          variant: 'destructive',
        });

        // 401 特殊处理：跳转登录
        if (status === 401) {
          localStorage.clear();
          setTimeout(() => {
            window.location.href = '/login';
          }, 1000);
        }
      }
    }
  }, []);

  return { handleError };
}
```

---

## 环境变量配置

| 变量 | 说明 | 默认值 | 开发环境建议 |
|------|------|----------|
| `VITE_API_BASE_URL` | API 地址 | http://localhost:8000/api/v1 |
| `VITE_ENABLE_SSE` | 是否启用 SSE | true |
| `VITE_RECONNECT_DELAY` | 重连延迟（毫秒） | 3000 |

---

## Nginx 配置（生产环境）

```nginx
# SSE 特殊配置（重要）
location /api/v1/plans/stream {
    proxy_buffering off;      # 禁用缓冲
    proxy_cache off;
    proxy_read_timeout 300s;  # 长连接超时
    proxy_send_timeout 300s;
}

# 文件上传配置
location /static/uploads {
    alias /path/to/uploads;
    expires 30d;
    add_header Cache-Control "public, immutable";
}
```

---

## 实现状态

| 模块 | 接口数量 | 实现状态 |
|------|----------|----------|
| 认证 | 12 个 | ✅ 100% |
| 饮食计划 | 5 个 | ✅ 100% |
| 任务管理 | 4 个 | ✅ 100% |
| 宠物管理 | 6 个 | ✅ 100% |
| 饮食记录 | 5 个 | ✅ 100% |
| 日历功能 | 2 个 | ✅ 100% |
| 营养分析 | 1 个 | ✅ 100% |
| **合计** | **35 个** | **✅ 100%** |

---

## 相关文档

- [API 参考手册](../API_REFERENCE.md)
- [快速开始](../QUICKSTART.md)
- [前端用例流程](../from_frontend/USER_FLOWS.md)
- [架构设计](../architecture/)
- [部署指南](../deployment/)

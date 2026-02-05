# 后端缺失接口分析

> 基于前端 UI/UX 设计，分析后端尚未实现的功能接口

---

## 概述

通过对比前端页面功能需求与后端已实现的 API 接口，以下是后端需要补充的功能模块。

### 后端已实现接口

| 模块 | 接口 |
|------|------|
| 认证 | 注册、登录、刷新 Token、获取用户信息、修改密码 |
| 验证码 | 发送验证码、验证注册、找回密码 |
| 饮食计划 | 创建（异步/流式）、获取列表、获取详情、删除 |
| 任务管理 | 获取列表、获取详情、取消任务、获取结果、SSE 监听 |

---

## 一、宠物管理模块 ⚠️ 完全缺失

> [!CAUTION]
> 这是**最关键的缺失模块**。前端有完整的宠物 CRUD 功能，但后端没有提供任何宠物相关接口。

### 前端需求

| 页面 | 功能需求 |
|------|----------|
| `Profile.jsx` | 显示用户的宠物列表、删除宠物 |
| `PetEdit.jsx` | 编辑宠物信息（名字、类型、体重、年龄、头像） |
| `OnboardingName.jsx` | 添加新宠物（第一步：名字、头像） |
| `OnboardingBasic.jsx` | 添加新宠物（第二步：类型、体重、年龄） |
| `OnboardingHealth.jsx` | 添加新宠物（第三步：健康状况） |
| `HomePage.jsx` | 切换当前选中的宠物 |

### 需要新增的接口

#### 1. GET `/pets/`
获取当前用户的宠物列表

**Response:**
```json
{
  "code": 0,
  "data": {
    "total": 2,
    "items": [
      {
        "id": "pet_1",
        "name": "Cooper",
        "type": "dog",
        "breed": "金毛巡回犬",
        "age": 3,
        "weight": 32,
        "gender": "male",
        "avatar": "https://...",
        "health_status": "健康",
        "has_plan": true,
        "created_at": "2024-01-15T00:00:00Z"
      }
    ]
  }
}
```

#### 2. POST `/pets/`
创建新宠物

**Request:**
```json
{
  "name": "Cooper",
  "type": "dog",
  "breed": "金毛巡回犬",
  "age": 3,
  "weight": 32,
  "gender": "male",
  "avatar": "base64...",
  "health_status": "健康",
  "special_requirements": "无过敏"
}
```

#### 3. GET `/pets/{pet_id}`
获取单个宠物详情

#### 4. PUT `/pets/{pet_id}`
更新宠物信息

#### 5. DELETE `/pets/{pet_id}`
删除宠物

#### 6. POST `/pets/{pet_id}/avatar`
上传宠物头像

**Request:** `multipart/form-data`

---

## 二、用户信息管理模块 ⚠️ 部分缺失

### 前端需求

| 页面 | 功能需求 |
|------|----------|
| `Profile.jsx` | 显示用户头像、昵称、邮箱、PRO 会员状态 |
| `ProfileEdit.jsx` | 编辑用户昵称、手机号、头像 |

### 需要新增的接口

#### 1. PUT `/auth/profile`
更新用户基本信息（昵称、手机号等）

**Request:**
```json
{
  "name": "Alex Chen",
  "phone": "13800138000"
}
```

#### 2. POST `/auth/avatar`
上传用户头像

**Request:** `multipart/form-data`

#### 3. GET `/auth/subscription`
获取用户订阅/会员状态

**Response:**
```json
{
  "code": 0,
  "data": {
    "is_pro": true,
    "plan_type": "monthly",
    "expired_at": "2025-03-01T00:00:00Z"
  }
}
```

---

## 三、饮食记录与打卡模块 ⚠️ 完全缺失

### 前端需求

| 页面 | 功能需求 |
|------|----------|
| `HomePage.jsx` | 显示今日餐食列表、标记餐食完成状态 |
| `DashboardDaily.jsx` | 每日饮食详情、营养摄入统计 |

### 需要新增的接口

#### 1. GET `/meals/today`
获取今日餐食计划

**Query:** `pet_id`

**Response:**
```json
{
  "code": 0,
  "data": {
    "date": "2025-02-05",
    "meals": [
      {
        "id": "meal_1",
        "type": "breakfast",
        "name": "早晨干粮混合",
        "time": "08:00",
        "description": "鸡肉米饭配方",
        "calories": 350,
        "is_completed": false,
        "completed_at": null,
        "details": {
          "ingredients": ["鸡胸肉 100g", "糙米 50g"],
          "nutrition": { "fat": "12g", "protein": "28g" },
          "ai_tip": "早餐提供充足能量"
        }
      }
    ],
    "nutrition_summary": {
      "total_calories": 1180,
      "consumed_calories": 350,
      "protein": { "target": 95, "consumed": 28 },
      "fat": { "target": 58, "consumed": 12 },
      "carbs": { "target": 120, "consumed": 35 }
    }
  }
}
```

#### 2. POST `/meals/{meal_id}/complete`
标记餐食完成

**Response:**
```json
{
  "code": 0,
  "data": {
    "meal_id": "meal_1",
    "is_completed": true,
    "completed_at": "2025-02-05T08:15:00Z"
  }
}
```

#### 3. DELETE `/meals/{meal_id}/complete`
取消餐食完成标记

#### 4. GET `/meals/history`
获取历史饮食记录

**Query:** `pet_id`, `start_date`, `end_date`, `page`, `page_size`

---

## 四、日历功能模块 ⚠️ 完全缺失

### 前端需求

| 页面 | 功能需求 |
|------|----------|
| `CalendarPage.jsx` | 查看月度日历、每日饮食完成情况标记 |
| `HomePage.jsx` | 周视图日历、每日点击跳转 |

### 需要新增的接口

#### 1. GET `/calendar/monthly`
获取月度日历数据

**Query:** `pet_id`, `year`, `month`

**Response:**
```json
{
  "code": 0,
  "data": {
    "year": 2025,
    "month": 2,
    "days": [
      {
        "date": "2025-02-01",
        "has_plan": true,
        "completion_rate": 100,
        "total_meals": 3,
        "completed_meals": 3
      },
      {
        "date": "2025-02-02",
        "has_plan": true,
        "completion_rate": 67,
        "total_meals": 3,
        "completed_meals": 2
      }
    ]
  }
}
```

#### 2. GET `/calendar/weekly`
获取周视图数据

**Query:** `pet_id`, `start_date`

---

## 五、营养分析模块 ⚠️ 完全缺失

### 前端需求

| 页面 | 功能需求 |
|------|----------|
| `AnalysisPage.jsx` | 营养摄入统计、趋势图表、AI 建议 |

### 需要新增的接口

#### 1. GET `/analysis/nutrition`
获取营养分析数据

**Query:** `pet_id`, `period` (week/month/year)

**Response:**
```json
{
  "code": 0,
  "data": {
    "period": "week",
    "summary": {
      "avg_calories": 1150,
      "avg_completion_rate": 85,
      "calorie_trend": "stable"
    },
    "daily_data": [
      {
        "date": "2025-02-01",
        "calories": 1180,
        "protein": 95,
        "fat": 58,
        "carbs": 120,
        "completion_rate": 100
      }
    ],
    "ai_insights": [
      {
        "type": "positive",
        "content": "本周蛋白质摄入达标率 92%，保持良好！"
      },
      {
        "type": "suggestion",
        "content": "建议增加蔬菜摄入以补充纤维素"
      }
    ]
  }
}
```

---

## 六、计划关联宠物 ⚠️ 需要调整

### 问题

当前后端创建饮食计划的接口直接传入宠物信息，但没有关联到具体的宠物实体。

### 建议调整

#### 修改 POST `/plans/` 和 POST `/plans/stream`

**Request 增加字段：**
```json
{
  "pet_id": "pet_1",  // 新增：关联到已创建的宠物
  "pet_type": "dog",
  // ... 其他字段
}
```

或者简化为：
```json
{
  "pet_id": "pet_1"  // 直接从宠物信息获取类型、体重、年龄等
}
```

---

## 优先级建议

| 优先级 | 模块 | 原因 |
|--------|------|------|
| 🔴 P0 | 宠物管理 | 前端核心功能，无法使用应用 |
| 🔴 P0 | 计划关联宠物 | 需要调整现有接口 |
| 🟡 P1 | 饮食记录 | 用户每日使用功能 |
| 🟡 P1 | 用户信息管理 | 头像、昵称编辑 |
| 🟢 P2 | 日历功能 | 增强用户体验 |
| 🟢 P2 | 营养分析 | 数据可视化功能 |

---

## 数据库表设计建议

### pets 表

```sql
CREATE TABLE pets (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES users(id) ON DELETE CASCADE,
    name VARCHAR(50) NOT NULL,
    type VARCHAR(10) NOT NULL, -- 'cat' | 'dog'
    breed VARCHAR(50),
    age INTEGER,
    weight DECIMAL(5,2),
    gender VARCHAR(10),
    avatar_url TEXT,
    health_status TEXT,
    special_requirements TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

### meal_records 表

```sql
CREATE TABLE meal_records (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    pet_id UUID REFERENCES pets(id) ON DELETE CASCADE,
    plan_id UUID REFERENCES plans(id) ON DELETE CASCADE,
    meal_date DATE NOT NULL,
    meal_type VARCHAR(20) NOT NULL, -- 'breakfast' | 'lunch' | 'dinner' | 'snack'
    is_completed BOOLEAN DEFAULT FALSE,
    completed_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

---

## 总结

| 模块 | 缺失接口数 | 工作量估算 |
|------|------------|------------|
| 宠物管理 | 6 个 | 2-3 天 |
| 用户信息管理 | 3 个 | 1 天 |
| 饮食记录 | 4 个 | 2 天 |
| 日历功能 | 2 个 | 1 天 |
| 营养分析 | 1 个 | 1-2 天 |
| **合计** | **16 个** | **7-10 天** |

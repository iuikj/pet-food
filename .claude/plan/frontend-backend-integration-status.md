# 前后端集成开发计划 - 实施状态

**项目**: 宠物饮食计划智能助手 - 前后端集成
**版本**: v1.0.0
**创建日期**: 2025-02-05
**状态**: 部分完成

---

## 开发进度

### 已完成阶段

| 阶段 | 任务 | 状态 | 完成日期 |
|------|------|------|---------|
| 阶段一 | 数据库层 | ✅ | 2025-02-05 |
| 阶段二 | 宠物管理模块 (P0) | ✅ | 2025-02-05 |
| 阶段三 | 计划关联宠物 (P0) | ✅ | 2025-02-05 |
| 阶段四 | 用户信息管理 (P1) | ✅ | 2025-02-05 |
| 阶段五 | 饮食记录模块 (P1) | ✅ | 2025-02-05 |
| 阶段六 | 日历功能模块 (P2) | ✅ | 2025-02-05 |
| 阶段七 | 营养分析模块 (P2) | ✅ | 2025-02-05 |
| 阶段八 | 测试与文档 | ⏳ | 待完成 |

---

## 已实现功能清单

### ✅ 阶段一：数据库层

**文件修改:**
- `src/db/models.py` - 新增 Pet、MealRecord 模型
- `src/db/models.py` - User 模型新增字段
- `src/db/models.py` - DietPlan 模型新增 pet_id 外键
- `alembic/versions/002_add_pets_and_meals.py` - 数据库迁移脚本

**新增表:**
- `pets` - 宠物信息表
- `meal_records` - 餐食记录表

**修改表:**
- `users` - 新增 nickname, phone, avatar_url, is_pro, plan_type, subscription_expired_at 字段
- `diet_plans` - 新增 pet_id 外键

---

### ✅ 阶段二：宠物管理模块 (P0)

**新增文件:**
- `src/api/services/pet_service.py` - PetService 服务类
- `src/api/routes/pets.py` - 宠物管理路由

**新增接口:**
| 方法 | 路径 | 描述 |
|------|------|------|
| GET | `/api/v1/pets/` | 获取宠物列表 |
| POST | `/api/v1/pets/` | 创建宠物 |
| GET | `/api/v1/pets/{pet_id}` | 获取宠物详情 |
| PUT | `/api/v1/pets/{pet_id}` | 更新宠物 |
| DELETE | `/api/v1/pets/{pet_id}` | 删除宠物（软删除） |
| POST | `/api/v1/pets/{pet_id}/avatar` | 上传宠物头像 |

---

### ✅ 阶段三：计划关联宠物 (P0)

**修改文件:**
- `src/api/models/request.py` - CreatePlanRequest 新增 pet_id 字段
- `src/api/services/plan_service.py` - 支持从 Pet 表获取宠物信息
- `src/api/routes/plans.py` - 创建计划时优先使用 pet_id

**修改接口:**
| 方法 | 路径 | 变更 |
|------|------|------|
| POST | `/api/v1/plans/` | 新增 pet_id 参数 |
| POST | `/api/v1/plans/stream` | 新增 pet_id 参数 |

---

### ✅ 阶段四：用户信息管理 (P1)

**修改文件:**
- `src/api/models/request.py` - 新增 UpdateProfileRequest
- `src/api/models/response.py` - 新增 UserProfileResponse, AvatarUploadResponse, SubscriptionResponse
- `src/api/models/response.py` - UserResponse 新增字段
- `src/api/routes/auth.py` - 新增用户信息管理接口
- `src/api/services/auth_service.py` - 更新 _user_to_response 方法

**新增接口:**
| 方法 | 路径 | 描述 |
|------|------|------|
| PUT | `/api/v1/auth/profile` | 更新用户基本信息 |
| POST | `/api/v1/auth/avatar` | 上传用户头像 |
| GET | `/api/v1/auth/subscription` | 获取会员状态 |

---

### ✅ 阶段五：饮食记录模块 (P1)

**新增文件:**
- `src/api/services/meal_service.py` - MealService 服务类
- `src/api/routes/meals.py` - 餐食记录路由
- `src/api/routes/calendar.py` - 日历路由
- `src/api/routes/analysis.py` - 营养分析路由

**新增接口 - 餐食记录:**
| 方法 | 路径 | 描述 |
|------|------|------|
| GET | `/api/v1/meals/today` | 获取今日餐食 |
| GET | `/api/v1/meals/date` | 获取指定日期餐食 |
| POST | `/api/v1/meals/{meal_id}/complete` | 标记餐食完成 |
| DELETE | `/api/v1/meals/{meal_id}/complete` | 取消完成标记 |
| GET | `/api/v1/meals/history` | 获取历史记录 |

**新增接口 - 日历:**
| 方法 | 路径 | 描述 |
|------|------|------|
| GET | `/api/v1/calendar/monthly` | 获取月度日历 |
| GET | `/api/v1/calendar/weekly` | 获取周视图数据 |

**新增接口 - 营养分析:**
| 方法 | 路径 | 描述 |
|------|------|------|
| GET | `/api/v1/analysis/nutrition` | 获取营养分析数据 |

---

## 待完成工作

### ⏳ 阶段八：测试与文档

**需要完成:**
- [ ] 编写单元测试（PetService, MealService）
- [ ] 编写集成测试（完整流程）
- [ ] 更新 API 参考文档
- [ ] 生成 Swagger 文档

---

## 文件清单

### 新增文件

```
src/api/
├── services/
│   ├── pet_service.py          # ✅ 宠物管理服务
│   └── meal_service.py         # ✅ 餐食记录服务
└── routes/
    ├── pets.py                 # ✅ 宠物管理路由
    ├── meals.py                # ✅ 餐食记录路由
    ├── calendar.py             # ✅ 日历路由
    └── analysis.py             # ✅ 营养分析路由

alembic/versions/
└── 002_add_pets_and_meals.py  # ✅ 数据库迁移脚本
```

### 修改文件

```
src/api/
├── models/
│   ├── request.py              # ✅ 新增请求模型
│   └── response.py            # ✅ 新增响应模型
├── routes/
│   ├── auth.py                # ✅ 新增用户信息接口
│   ├── plans.py               # ✅ 修改支持 pet_id
│   └── main.py               # ✅ 注册新路由
├── services/
│   ├── auth_service.py         # ✅ 更新用户响应转换
│   └── plan_service.py        # ✅ 支持 pet_id 查询

src/db/
└── models.py                  # ✅ 新增 Pet、MealRecord，修改 User、DietPlan
```

---

## 数据库迁移

```bash
# 应用数据库迁移
alembic upgrade head

# 回滚迁移
alembic downgrade -1
```

---

## 注意事项

1. **饮食计划生成模块**: 用户手动编写，本计划仅负责相关功能开发
2. **PetDietPlan 结构**: 用作计划与饮食记录模块之间的桥梁
3. **文件上传**: 当前使用本地文件存储，生产环境建议配置 OSS
4. **软删除**: 宠物删除使用 is_active 标记软删除
5. **API 响应格式**: 统一使用 `ApiResponse<T>` 格式

---

## API 端点汇总

### 认证模块 (/api/v1/auth)
- ✅ POST `/register` - 用户注册
- ✅ POST `/login` - 用户登录
- ✅ POST `/refresh` - 刷新 Token
- ✅ GET `/me` - 获取当前用户信息
- ✅ PUT `/profile` - 更新用户信息
- ✅ POST `/avatar` - 上传用户头像
- ✅ GET `/subscription` - 获取订阅状态

### 验证码模块 (/api/v1/auth)
- ✅ POST `/send-code` - 发送验证码
- ✅ POST `/verify-register` - 验证码注册
- ✅ POST `/verify-reset-password` - 验证码重置密码
- ✅ POST `/reset-password` - 重置密码
- ✅ POST `/change-password` - 修改密码

### 宠物管理模块 (/api/v1/pets)
- ✅ GET `/` - 获取宠物列表
- ✅ POST `/` - 创建宠物
- ✅ GET `/{pet_id}` - 获取宠物详情
- ✅ PUT `/{pet_id}` - 更新宠物
- ✅ DELETE `/{pet_id}` - 删除宠物
- ✅ POST `/{pet_id}/avatar` - 上传宠物头像

### 饮食记录模块 (/api/v1/meals)
- ✅ GET `/today` - 获取今日餐食
- ✅ GET `/date` - 获取指定日期餐食
- ✅ POST `/{meal_id}/complete` - 标记餐食完成
- ✅ DELETE `/{meal_id}/complete` - 取消完成标记
- ✅ GET `/history` - 获取历史记录

### 日历模块 (/api/v1/calendar)
- ✅ GET `/monthly` - 获取月度日历
- ✅ GET `/weekly` - 获取周视图

### 营养分析模块 (/api/v1/analysis)
- ✅ GET `/nutrition` - 获取营养分析

### 饮食计划模块 (/api/v1/plans)
- ✅ POST `/` - 创建饮食计划（异步）
- ✅ POST `/stream` - 创建饮食计划（流式）
- ✅ GET `/stream?task_id=xxx` - 恢复流式连接
- ✅ GET `/` - 获取计划列表
- ✅ GET `/{plan_id}` - 获取计划详情
- ✅ DELETE `/{plan_id}` - 删除计划

### 任务管理模块 (/api/v1/tasks)
- ✅ GET `/` - 获取任务列表
- ✅ GET `/{task_id}` - 获取任务详情
- ✅ POST `/{task_id}/cancel` - 取消任务

---

**最后更新**: 2025-02-05

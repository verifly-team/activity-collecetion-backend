# 采集服务 · 前端对接文档（v2）

> 版本：v2（2026-10 按《Survey 调整内容》更新）
> 后端已完成联调与测试，前端按本文接即可。

---

## 0. 本次前端要改的三件事

| # | 改动 | 工作量 |
|---|---|---|
| 1 | `zones` 增加 **D 区**（原来只有 A/B/C） | 加一个选项 |
| 2 | 新增 **「品牌背景与经营情况」三大组共 12 道题** | 表单加字段 |
| 3 | 页面文案由后端下发（招募截止/回复时间、代表商品提示） | 拉接口替换硬编码 |

**关键：12 道新题服务端目前都是「可选」的**（`enforced: false`）。
前端可以先上一部分、慢慢补全，任何阶段都不会因为缺字段被拒。

---

## 1. 接口地址

```
https://api.66thandsecondlovehealgiveus.com
```

跨域已放开（`ALLOWED_ORIGINS=*`）。

---

## 2. 接口清单

| 方法 | 路径 | 用途 |
|---|---|---|
| `GET` | `/api/v1/form-schema` | **新增**：拉问卷结构 + 文案 |
| `POST` | `/api/v1/uploads` | 上传附件，拿 `file_id` |
| `POST` | `/api/v1/applications` | 提交报名 |
| `GET` | `/healthz` | 健康检查 |

典型流程：

```
① GET  /api/v1/form-schema      → 渲染表单（题目、选项、文案）
② POST /api/v1/uploads          → 每个附件拿一个 file_id（可并行）
③ POST /api/v1/applications     → 带上 file_ids 一起提交
```

---

## 3. `GET /api/v1/form-schema`

无需鉴权、无需参数。**题目、选项、必填、文案都从这儿取，不要在前端硬编码。**

### 返回结构

```json
{
  "version": "v2",
  "enforced": false,
  "required_hint": "带 * 为必填项",
  "copy": {
    "feedback": "提交后，主办方将在 48 小时内反馈审核结果或补充资料需求。2026.11.8 为第一轮公开招募截止时间，统一回复时间为 2026.11.10；2026.11.28 为最终轮公开招募截止时间，统一回复时间为 2026.12.1。",
    "items_hint": "添加代表商品可增加店家品牌力，显示商家独特性，会增加入选概率"
  },
  "zones": [
    { "value": "A", "label": "收藏级 Archive" },
    { "value": "B", "label": "工装与街头" },
    { "value": "C", "label": "二手名牌／样衣" },
    { "value": "D", "label": "D 区（新增开放）" }
  ],
  "groups": [
    {
      "title": "1. 品牌联络与定位特色",
      "questions": [
        {
          "key": "founded_year",
          "label": "品牌成立年份",
          "type": "year",
          "required": true,
          "min": 1900,
          "max": 2100,
          "help": "填四位年份，例如 2018"
        }
      ]
    }
  ]
}
```

### 字段说明

| 字段 | 含义 |
|---|---|
| `version` | 问卷版本，当前 `v2` |
| `enforced` | `true` = 服务端强制校验全部必填；`false` = 新题可选 |
| `copy.feedback` | 提交后反馈说明的文案（**必须展示**） |
| `copy.items_hint` | 代表商品表格下方的提示（**必须展示**） |
| `zones` | 区域选项，**含 D 区** |
| `groups[].questions[]` | 题目定义 |

### 题目 `type` 与对应控件

| type | 控件 | 额外字段 |
|---|---|---|
| `year` | 数字输入（4 位） | `min` `max` |
| `url_list` | 可增删的链接输入框 | `min_items` `max_items` `placeholder` |
| `textarea` | 多行文本 | `min_length` `max_length`（字数统计要显示） |
| `multi` | 多选（复选框 / chips） | `options[]` `min_items` |
| `single` | 单选（radio） | `options[]` |
| `bool` | 单选「有 / 没有」 | `options[]`（`value` 是 true/false） |

### 12 道题一览

| key | 题目 | 控件 | 必填 |
|---|---|---|---|
| `founded_year` | 品牌成立年份 | year | ✅ |
| `social_links` | Instagram / 小红书 / 抖音 | url_list（可多填） | ✅ |
| `brand_intro` | 品牌简介 | textarea 100–300 字 | ✅ |
| `channels` | 主要经营渠道 | multi | ✅ |
| `has_physical_store` | 是否有实体店？ | bool | ✅ |
| `attended_other_events` | 是否参加过其他市集或展会？ | bool | ✅ |
| `past_experience` | 过往参展经历 | textarea ≤1000 字 | 选填 |
| `brand_specialty` | 你认为自己的品牌最有特色的地方是什么？ | textarea 100–300 字 | ✅ |
| `target_consumers` | 你的品牌主要面向哪一类消费者？ | single | ✅ |
| `planned_activities` | 本次是否有计划推出特别商品或活动？ | multi | ✅ |
| `willing_to_promote` | 是否愿意配合主办方进行活动前的品牌宣传？ | single | ✅ |
| `authorize_media` | 是否同意主办方在宣传及回顾中使用品牌素材？ | single | ✅ |

---

## 4. `POST /api/v1/uploads`

上传附件，先拿 `file_id`，提交报名时再引用。

```
Content-Type: multipart/form-data
字段：
  file  必填  文件本体
  kind  可选  photos（商品照片）/ list（商品清单）/ other（其他）
```

### 限制

| 项 | 上限 |
|---|---|
| 单文件 | 20 MB |
| 扩展名 | jpg / jpeg / png / webp / heic / pdf / zip |
| 每份报名附件数 | 10 个 |
| 每份报名附件合计 | 100 MB |

> zip 会校验文件头，不是真 zip 会被拒。

### 成功（201）

```json
{
  "file_id": "6824bc4b50f44a278f01652e2c121a59",
  "original_name": "test.png",
  "size": 79,
  "kind": "photos"
}
```

### 失败（400）

```json
{
  "ok": false,
  "error": {
    "code": "BAD_REQUEST",
    "message": "不支持的文件类型 .exe，允许：['heic', 'jpeg', 'jpg', 'pdf', 'png', 'webp', 'zip']"
  }
}
```

---

## 5. `POST /api/v1/applications`

JSON 提交。**`Content-Type: application/json`**

### 完整字段表

#### 原有字段（不变）

| 字段 | 类型 | 必填 | 约束 |
|---|---|---|---|
| `brand_name` | string | ✅ | 1–120 字 |
| `contact_name` | string | ✅ | 1–60 字 |
| `phone` | string | ✅ | 11 位手机号，自动去掉 `+86`/空格/横线 |
| `wechat` | string \| null | 二选一 | ≤60 字 |
| `email` | string \| null | 二选一 | 邮箱格式 |
| `city` | string \| null | | ≤60 字 |
| `entity_type` | string \| null | | `company` / `individual` / `personal` |
| `is_first_time` | bool | | 默认 `false` |
| `categories` | string[] | ✅ | 至少 1 个 |
| `zones` | string[] | ✅ | 至少 1 个，**新增 `D`** |
| `expected_qty` | int \| null | | 0–1000000 |
| `price_min` | int \| null | | ≥ 0 |
| `price_max` | int \| null | | ≥ `price_min` |
| `structure` | object \| null | | 四项合计必须 = 100 |
| `items` | object[] | | ≤ 20 条 |
| `items[].name` | string | ✅ | 1–120 字 |
| `items[].era_series` | string \| null | | ≤200 字 |
| `items[].condition_source` | string \| null | | ≤200 字 |
| `items[].price` | int \| null | | ≥ 0 |
| `file_ids` | string[] | | 上传拿到的 id，≤ 20 个 |
| `consent` | bool | ✅ | **必须显式 `true`** |
| `source` | string \| null | | `h5` / `qrcode` / `word` |

#### v2 新增字段（12 个，目前全部可选）

| 字段 | 类型 | 约束 |
|---|---|---|
| `founded_year` | int \| null | 1900–2100 |
| `social_links` | string[] | 1–5 条，必须 `http://` 或 `https://` 开头，自动去重 |
| `brand_intro` | string \| null | 填了就 **100–300 字** |
| `channels` | string[] | 至少 1 个（选了才算） |
| `has_physical_store` | bool \| null | — |
| `attended_other_events` | bool \| null | — |
| `past_experience` | string \| null | ≤1000 字 |
| `brand_specialty` | string \| null | 填了就 **100–300 字** |
| `target_consumers` | string \| null | 见枚举 |
| `planned_activities` | string[] | 选 `none` 时不能再选其他 |
| `willing_to_promote` | string \| null | 见枚举 |
| `authorize_media` | string \| null | 见枚举 |

> ⚠️ `brand_intro` / `brand_specialty`：**没填不校验，填了就必须是 100–300 字**。
> 前端一定要做字数统计并提示，否则用户写到 99 字会被 422。

### 成功（201）

```json
{
  "id": 1,
  "files": 1,
  "created_at": "2026-10-31T16:35:31Z"
}
```

`id` 就是报名编号，可以展示给用户做凭证。

---

## 6. 枚举字典

```javascript
const categories = ['bag', 'watch', 'jewelry', 'apparel', 'shoe', 'other'];
// 箱包手袋 / 腕表 / 珠宝配饰 / 服饰 / 鞋履 / 其他藏品

const zones = ['A', 'B', 'C', 'D'];
// 收藏级 Archive / 工装与街头 / 二手名牌／样衣 / D 区

const entity_type = ['company', 'individual', 'personal'];
// 公司 / 个体工商户 / 个人

const channels = ['online_store', 'physical_store', 'personal_social', 'market_stall', 'multi_channel'];
// 线上店铺 / 线下实体店 / 个人社交媒体 / 市集摆摊 / 多渠道经营

const target_consumers = ['vintage', 'street', 'designer', 'young', 'collector', 'other'];
// Vintage／古着爱好者 / 潮流及街头文化消费者 / Designer／奢侈品消费者
// / 年轻消费群体 / 收藏爱好者 / 其他

const planned_activities = [
  'limited',        // 限量商品
  'first_release',  // 首次公开发售
  'discount',       // 特别折扣
  'collab',         // 品牌联名
  'onsite',         // 现场互动活动
  'pr_license',     // 品牌合作及宣传授权
  'none',           // 没有特别安排（与其他互斥）
];

const willing_to_promote = ['provide_material', 'need_talk'];
// 愿意提供品牌照片及商品素材；配合品牌介绍及社交媒体宣传；转发官方活动宣传
// / 希望主办方与我们进一步沟通

const authorize_media = ['agree', 'need_scope'];
// 同意 / 需要另行确认授权范围
```

> 这些值以后端 `/api/v1/form-schema` 返回的为准，上面的常量只是方便你写类型。

---

## 7. 错误格式

所有错误统一：

```json
{
  "ok": false,
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "表单校验未通过",
    "fields": [
      { "path": "social_links", "message": "链接需以 http:// 或 https:// 开头：instagram.com/x" }
    ]
  }
}
```

| code | HTTP | 含义 |
|---|---|---|
| `BAD_REQUEST` | 400 | 参数不对（文件类型、file_id 失效等） |
| `VALIDATION_ERROR` | 422 | 表单校验失败，`fields[]` 里有具体原因 |
| `PAYLOAD_TOO_LARGE` | 413 | 文件或附件合计超限 |
| `RATE_LIMITED` | 429 | 提交过于频繁（每 IP 每分钟 20 次） |
| `NOT_FOUND` | 404 | 路径不存在 |
| `INTERNAL_ERROR` | 500 | 服务端异常 |

**建议**：把 `fields[].message` 直接显示在对应输入框下面，`path` 就是字段名。

---

## 8. 完整示例

### 请求

```javascript
const res = await fetch('https://api.66thandsecondlovehealgiveus.com/api/v1/applications', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({
    brand_name: '拾光中古',
    contact_name: '陈小姐',
    phone: '13800138000',
    wechat: 'shiguang_vtg',
    city: '深圳',
    entity_type: 'company',
    is_first_time: false,
    categories: ['bag'],
    zones: ['D'],
    expected_qty: 120,
    price_min: 800,
    price_max: 28000,
    structure: { secondhand: 100, new_stock: 0, sample: 0, replica: 0 },
    items: [{ name: 'Hermès Birkin 30', era_series: '2015', price: 52000 }],
    file_ids: ['6824bc4b50f44a278f01652e2c121a59'],
    consent: true,
    source: 'h5',

    founded_year: 2018,
    social_links: ['https://instagram.com/x'],
    brand_intro: '（100–300 字）',
    channels: ['online_store'],
    has_physical_store: true,
    attended_other_events: false,
    past_experience: '2024 年参加深圳湾市集',
    brand_specialty: '（100–300 字）',
    target_consumers: 'vintage',
    planned_activities: ['limited'],
    willing_to_promote: 'provide_material',
    authorize_media: 'agree',
  }),
});
const data = await res.json();
if (!res.ok) {
  console.error(data.error.fields);   // 逐项提示
}
```

### 建议的表单顺序

```
① 品牌与联络（原有）
② 经营与参展内容（原有，代表商品下方展示 copy.items_hint）
③ 品牌联络与定位特色（新）
④ 品牌定位与特色（新）
⑤ 品牌意愿与授权（新）
⑥ 附件上传
⑦ 同意条款（consent）+ 提交
   提交按钮下方展示 copy.feedback
```

---

## 9. 前端联调自测

```bash
# 1. 问卷结构能拉到吗（应含 D 区 + v2）
curl -s https://api.66thandsecondlovehealgiveus.com/api/v1/form-schema | head -20

# 2. 老表单还能提交吗（不传新字段）
curl -s -X POST https://api.66thandsecondlovehealgiveus.com/api/v1/applications \
  -H 'Content-Type: application/json' \
  -d '{"brand_name":"自测","contact_name":"自测","phone":"13800138000","wechat":"t",
       "categories":["bag"],"zones":["A"],"consent":true}'
# 期望 201

# 3. D 区能提交吗
#    把上面 zones 改成 ["D"] 再试，期望 201
```

---

## 10. 后端开关（前端不用管）

服务端有个环境变量 `SURVEY_REQUIRED`：

| 值 | 行为 |
|---|---|
| `0`（当前默认） | 12 道新题**可选**，缺了也收 |
| `1` | 强制校验，缺任一项返回 422 并列出缺哪个 |

**等前端把 12 道题全部接完并上线后**，我们再把它改成 `1`。
在那之前前端可以随便分批上线，不会被拒。

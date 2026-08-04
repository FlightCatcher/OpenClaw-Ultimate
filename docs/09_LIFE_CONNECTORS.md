# VELA Life Connectors

VELA 的生活连接层坚持三个边界：优先本地中枢、只使用平台允许的接口、任何外部
影响操作都必须经过一次性确认。网页、设备名称和消息正文始终是不可信数据，不能
改变 VELA 的权限策略。

## 当前支持矩阵

| 场景 | 接入方式 | 当前能力 | 边界 |
|---|---|---|---|
| 米家 | Home Assistant 的 Xiaomi Home 集成 | 发现实体、读取状态、确认后控制 | 设备支持度由 Home Assistant 集成决定 |
| Matter 家居 | Home Assistant Matter | 发现实体、读取状态、确认后控制 | 需要设备先加入 Home Assistant |
| 华为智慧生活 | Matter 设备可经 Home Assistant；云云接口预留 | 暂不直接登录个人华为账号 | 完整云接口需要华为合作伙伴 AK/SK 和项目审批 |
| 微信 | 企业微信群官方机器人 Webhook | 确认后发送文本通知 | 不支持个人微信号挂机、读聊天或模拟点击 |
| QQ | QQ 开放平台官方机器人 v2 API | 确认后向授权用户或群 OpenID 发文本 | 需要机器人 AppID、ClientSecret 和官方事件提供的 OpenID |

## Home Assistant 与米家

1. 在独立设备、虚拟机或 Docker 中安装 Home Assistant。
2. 在 Home Assistant 的“设备与服务”中添加 `Xiaomi Home`，完成米家账号授权。
3. 在 Home Assistant 用户资料页创建 Long-Lived Access Token。
4. 在本机 `.env` 中填写：

```dotenv
OCU_HOME_ASSISTANT_ENABLED=true
OCU_HOME_ASSISTANT_BASE_URL=http://homeassistant.local:8123
OCU_HOME_ASSISTANT_TOKEN=只保存在本机的访问令牌
OCU_HOME_ASSISTANT_READ_ONLY=true
```

首次接入保持只读。VELA 此时可以调用 `home_status`、`home_list_entities` 和
`home_get_state`。核对设备清单后，再将 `OCU_HOME_ASSISTANT_READ_ONLY` 改为
`false`。控制工具 `home_call_service` 仍会为每个具体动作创建一次性确认；确认内容
绑定领域、服务、实体和参数，不能复用于另一个动作。

## 企业微信通知

个人微信没有适合 VELA 的通用机器人接口。当前只支持企业微信内部群的官方机器人
Webhook：

```dotenv
OCU_WECOM_ENABLED=true
OCU_WECOM_WEBHOOK_URL=https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=...
```

VELA 只接受 `qyapi.weixin.qq.com` 的 HTTPS Webhook。地址作为密钥处理，不写日志、
不写数据库、不提交 Git。每条消息发送前都要确认。

## QQ 官方机器人

在 QQ 开放平台创建机器人并获取 AppID、ClientSecret：

```dotenv
OCU_QQ_BOT_ENABLED=true
OCU_QQ_BOT_APP_ID=...
OCU_QQ_BOT_CLIENT_SECRET=...
```

发送目标必须是 QQ 官方事件提供的用户或群 OpenID，不能填写普通 QQ 号。访问令牌在
内存中缓存并在到期前刷新，不会持久化。每条主动消息发送前都要确认，并遵循 QQ 平台
频率和用户拒收设置。

## 华为智慧生活

VELA 不抓取华为个人账号 Cookie，也不逆向“智慧生活”客户端。可立即使用的路线是：

1. 支持 Matter 的华为或鸿蒙智联设备接入 Home Assistant；或
2. 申请华为全屋智能云云对接合作，获得项目级 AK/SK、项目 ID 和域名后，再启用专用
   连接器。

在没有上述任一条件时，界面应显示“等待官方授权”，而不是伪造已接入状态。

## 安全与审计

- 状态读取是只读操作，不要求逐次确认。
- 灯、开关、空调、门帘、扫地机、场景和脚本调用都要求一次性确认。
- 企业微信和 QQ 发送消息属于外部影响操作，风险级别为 `high`。
- 默认不允许门锁、安防撤防、支付、购买或账号设置操作。
- 所有确认和结果写入 `.openclaw/governance.db`，密钥不写入审计元数据。

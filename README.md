# astrbot_plugin_marry

「娶群友」群聊娱乐插件，为 [AstrBot](https://github.com/AstrBotDevs/AstrBot) 设计。

在群里发送指令，随机匹配群友结为夫妻，支持离婚、换一个，每个群可单独设置每日更换次数上限。

## ✨ 功能

- 💍 **娶群友**：随机匹配一位单身群友结为夫妻，绑定成功会 **@ 双方**
- 💔 **离婚**：解除当前的婚姻绑定
- 🔄 **换一个**：解除绑定并重新随机匹配一位群友（受每日次数限制）
- 🚫 **匹配排除**：自己、机器人、以及已被别人娶走的群友都不会被匹配
- ⚙️ **每群独立配置**：每个群可单独设置每日更换次数上限
- 💾 **数据持久化**：婚姻关系与更换记录存于 `data/plugin_data/`，重装/更新插件不丢数据

## 📦 安装

1. 克隆到 AstrBot 插件目录（`data/plugins/` 下）：

```bash
git clone https://github.com/PhiLia011/astrbot_plugin_marry.git
```

或者手动下载 zip 解压，把 `astrbot_plugin_marry` 文件夹放进 `data/plugins/`。

2. 在 AstrBot 管理面板 → 插件管理 → 刷新插件列表，找到「娶群友」并启用。

## 🎮 使用

在群内发送以下指令（支持或不支持 `/` 前缀均可）：

| 指令 | 别名 | 效果 |
|---|---|---|
| `娶群友` | `结婚`、`娶老婆` | 随机匹配一位单身群友结为夫妻 |
| `离婚` | `分手`、`解除婚约` | 解除当前婚姻绑定 |
| `换一个` | `换老婆`、`再娶一个` | 解除绑定并重新匹配一位群友 |

示例：

```
[群友A] 娶群友
[Bot] 🎉 恭喜 @群友A 和 @群友B 结为夫妻！祝你们幸福~ 💕

[群友A] 离婚
[Bot] 💔 @群友A 和 @群友B 离婚了……好聚好散，祝各自安好。

[群友A] 换一个
[Bot] 🔄 @群友A 换了一个老婆：@群友C！
```

## ⚙️ 配置

在 AstrBot WebUI 的插件配置页即可可视化编辑：

| 配置项 | 类型 | 默认值 | 说明 |
|---|---|---|---|
| `enable` | bool | `true` | 插件总开关 |
| `at_both` | bool | `true` | 绑定/离婚/更换时是否 @ 双方 |
| `default_daily_limit` | int | `3` | 每个用户每日可更换配偶的次数上限（全局默认） |
| `group_limits` | object | `{}` | 每群单独设置上限，格式：`{"群号": 次数}`，未配置的群使用全局默认值 |

### 示例

想让群 `123456` 每天最多换 5 次，其他群保持默认 3 次：

```json
{
  "default_daily_limit": 3,
  "group_limits": {
    "123456": 5
  }
}
```

## 📁 数据存储

- 数据文件：`data/plugin_data/astrbot_plugin_marry/data.json`
- 存储内容：婚姻关系映射、每日更换次数记录
- 每日更换次数按自然日自动重置

## 🔧 技术说明

- 使用 `@filter.event_message_type(EventMessageType.GROUP_MESSAGE)` 监听群消息，仅响应群聊
- 通过 OneBot `get_group_member_list` API 获取实时群成员列表，保证匹配准确
- 匹配时排除：发送者自己、机器人自身、已被他人绑定的成员
- 所有异常均有兜底处理，不会因 API 失败导致插件崩溃

## 📄 License

MIT

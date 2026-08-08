"""娶群友插件：随机匹配群友结为夫妻，支持离婚、换一个，每群可单独配置每日更换次数。"""
import json
import random
from datetime import date
from pathlib import Path

from astrbot.api import AstrBotConfig, logger
from astrbot.api.event import AstrMessageEvent, MessageChain, filter
from astrbot.api.message_components import At, Plain
from astrbot.api.star import Context, Star
from astrbot.core.utils.astrbot_path import get_astrbot_plugin_data_path

# 命令关键词
CMD_MARRY = ("娶群友", "结婚", "娶老婆")
CMD_DIVORCE = ("离婚", "分手", "解除婚约")
CMD_CHANGE = ("换一个", "换老婆", "再娶一个")

# 默认文案
MSG_NO_SPOUSE = "你还没有老婆呢，发送「娶群友」试试运气吧~"
MSG_ALREADY_MARRIED = "你已经有老婆了，想换一个的话发送「换一个」哦~"
MSG_NO_CANDIDATE = "群里没有合适的单身群友了……要不去隔壁群看看？"
MSG_FETCH_FAIL = "获取群成员列表失败了，稍后再试试吧~"
MSG_DAILY_LIMIT = "今天换老婆的次数已经用完啦（上限 {limit} 次），明天再来吧~"
MSG_CHANGE_NO_SPOUSE = "你还没有老婆呢，先「娶群友」再说~"


class MarryPlugin(Star):
    def __init__(self, context: Context, config: AstrBotConfig):
        super().__init__(context)
        self.config = config
        # 持久化数据目录：data/plugin_data/astrbot_plugin_marry/
        self.data_dir = Path(get_astrbot_plugin_data_path()) / "astrbot_plugin_marry"
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.data_file = self.data_dir / "data.json"
        self.marriages: dict = {}   # {group_id: {user_id: spouse_id}}
        self.change_count: dict = {}  # {group_id: {date: {user_id: count}}}
        self._load()

    # ---------- 数据持久化 ----------
    def _load(self):
        """从磁盘加载数据，文件不存在或损坏时使用空数据。"""
        try:
            if self.data_file.exists():
                data = json.loads(self.data_file.read_text(encoding="utf-8"))
                self.marriages = data.get("marriages", {})
                self.change_count = data.get("change_count", {})
        except Exception as e:
            logger.error(f"[娶群友] 加载数据失败: {e}")

    def _save(self):
        """保存数据到磁盘。"""
        try:
            self.data_file.write_text(
                json.dumps(
                    {"marriages": self.marriages, "change_count": self.change_count},
                    ensure_ascii=False,
                    indent=2,
                ),
                encoding="utf-8",
            )
        except Exception as e:
            logger.error(f"[娶群友] 保存数据失败: {e}")

    def _today(self) -> str:
        return date.today().isoformat()

    def _group_marriages(self, group_id: str) -> dict:
        return self.marriages.setdefault(group_id, {})

    def _get_daily_limit(self, group_id: str) -> int:
        """获取指定群的每日更换上限。优先群级配置，其次全局默认。"""
        limits: dict = self.config.get("group_limits", {}) or {}
        group_key = str(group_id)
        if group_key in limits:
            try:
                return max(1, int(limits[group_key]))
            except (TypeError, ValueError):
                pass
        return max(1, int(self.config.get("default_daily_limit", 3)))

    # ---------- 工具 ----------
    async def _get_member_list(self, event: AstrMessageEvent, group_id: str):
        """获取群成员列表，失败返回 None。"""
        try:
            bot = getattr(event, "bot", None)
            if bot is None:
                logger.error("[娶群友] 当前平台不支持 bot API 调用")
                return None
            members = await bot.call_action(
                "get_group_member_list", group_id=int(group_id)
            )
            return members if isinstance(members, list) else None
        except Exception as e:
            logger.error(f"[娶群友] 获取群成员列表失败: {e}")
            return None

    def _pick_spouse(self, group_id: str, members: list, user_id: str, self_id: str):
        """从群成员中随机挑选一位合适的“老婆”。
        排除：自己、机器人自身、以及已经被别人绑定为配偶的成员。
        """
        married_spouses = set()
        for _, spouse in self._group_marriages(group_id).items():
            married_spouses.add(str(spouse))

        candidates = []
        for m in members:
            uid = str(m.get("user_id", ""))
            if not uid:
                continue
            if uid == str(user_id) or uid == str(self_id):
                continue
            if uid in married_spouses:
                continue
            candidates.append(m)

        if not candidates:
            return None
        return random.choice(candidates)

    def _name_of(self, member) -> str:
        """取成员昵称，优先群名片，其次昵称。"""
        return (
            member.get("card")
            or member.get("nickname")
            or str(member.get("user_id", ""))
        )

    def _build_result(
        self,
        user_id: str,
        spouse_id: str,
        template: str,
        at_both: bool,
        user_name: str = "",
        spouse_name: str = "",
    ) -> MessageChain:
        """构造回复消息链，可选 @ 双方。"""
        if at_both:
            chain = []
            # 模板格式: "前缀 {user} 中间 {spouse} 后缀"
            parts = template.split("{user}")
            if len(parts) == 2:
                before = parts[0]
                after_parts = parts[1].split("{spouse}")
                if len(after_parts) == 2:
                    if before:
                        chain.append(Plain(text=before))
                    chain.append(At(qq=str(user_id)))
                    if after_parts[0]:
                        chain.append(Plain(text=after_parts[0]))
                    chain.append(At(qq=str(spouse_id)))
                    if after_parts[1]:
                        chain.append(Plain(text=after_parts[1]))
                    return MessageChain(chain=chain)
            # 兜底：模板不含占位符，退化为纯文本
        text = (
            template.replace("{user}", user_name or str(user_id))
            .replace("{spouse}", spouse_name or str(spouse_id))
            .strip()
        )
        return MessageChain(chain=[Plain(text=text)])

    # ---------- 核心逻辑 ----------
    def _marry_logic(self, group_id: str, user_id: str, members: list, self_id: str):
        """执行娶群友逻辑，返回 (spouse_member 或 None, 消息)。"""
        g_marriages = self._group_marriages(group_id)
        if user_id in g_marriages:
            return None, MSG_ALREADY_MARRIED

        spouse = self._pick_spouse(group_id, members, user_id, self_id)
        if spouse is None:
            return None, MSG_NO_CANDIDATE

        g_marriages[user_id] = str(spouse.get("user_id"))
        self._save()
        return spouse, None

    def _divorce_logic(self, group_id: str, user_id: str):
        """执行离婚逻辑，返回 (spouse_id 或 None, 消息)。"""
        g_marriages = self._group_marriages(group_id)
        spouse_id = g_marriages.pop(user_id, None)
        if spouse_id is None:
            return None, MSG_NO_SPOUSE
        self._save()
        return spouse_id, None

    def _change_logic(
        self, group_id: str, user_id: str, members: list, self_id: str
    ):
        """执行换一个逻辑，返回 (旧spouse, 新spouse 或 None, 消息)。"""
        g_marriages = self._group_marriages(group_id)
        old_spouse = g_marriages.get(user_id)
        if old_spouse is None:
            return None, None, MSG_CHANGE_NO_SPOUSE

        # 每日次数检查
        today = self._today()
        limit = self._get_daily_limit(group_id)
        count = (
            self.change_count.setdefault(group_id, {})
            .setdefault(today, {})
            .get(user_id, 0)
        )
        if count >= limit:
            return old_spouse, None, MSG_DAILY_LIMIT.format(limit=limit)

        new_spouse = self._pick_spouse(group_id, members, user_id, self_id)
        if new_spouse is None:
            return old_spouse, None, MSG_NO_CANDIDATE

        g_marriages[user_id] = str(new_spouse.get("user_id"))
        self.change_count[group_id][today][user_id] = count + 1
        self._save()
        return old_spouse, new_spouse, None

    # ---------- 事件入口 ----------
    @filter.event_message_type(filter.EventMessageType.GROUP_MESSAGE)
    async def on_group_message(self, event: AstrMessageEvent):
        """监听群消息，处理娶群友/离婚/换一个指令。"""
        if not self.config.get("enable", True):
            return

        text = event.message_str.strip()
        # 兼容带 / 前缀的指令，如 "/娶群友"
        if text.startswith("/"):
            text = text[1:].strip()

        if text in CMD_MARRY:
            await self._handle_marry(event)
        elif text in CMD_DIVORCE:
            await self._handle_divorce(event)
        elif text in CMD_CHANGE:
            await self._handle_change(event)

    async def _handle_marry(self, event: AstrMessageEvent):
        group_id = event.get_group_id()
        user_id = event.get_sender_id()
        if not group_id:
            return
        at_both = bool(self.config.get("at_both", True))

        members = await self._get_member_list(event, group_id)
        if members is None:
            yield event.plain_result(MSG_FETCH_FAIL)
            return
        self_id = event.get_self_id()

        spouse, msg = self._marry_logic(group_id, user_id, members, self_id)
        if msg:
            yield event.plain_result(msg)
            return
        # 成功
        result = self._build_result(
            user_id,
            spouse.get("user_id"),
            "🎉 恭喜 {user} 和 {spouse} 结为夫妻！祝你们幸福~ 💕",
            at_both,
            event.get_sender_name(),
            self._name_of(spouse),
        )
        yield event.chain_result(result.chain)

    async def _handle_divorce(self, event: AstrMessageEvent):
        group_id = event.get_group_id()
        user_id = event.get_sender_id()
        if not group_id:
            return
        at_both = bool(self.config.get("at_both", True))

        spouse_id, msg = self._divorce_logic(group_id, user_id)
        if msg:
            yield event.plain_result(msg)
            return
        result = self._build_result(
            user_id,
            spouse_id,
            "💔 {user} 和 {spouse} 离婚了……好聚好散，祝各自安好。",
            at_both,
            event.get_sender_name(),
            spouse_id,
        )
        yield event.chain_result(result.chain)

    async def _handle_change(self, event: AstrMessageEvent):
        group_id = event.get_group_id()
        user_id = event.get_sender_id()
        if not group_id:
            return
        at_both = bool(self.config.get("at_both", True))

        members = await self._get_member_list(event, group_id)
        if members is None:
            yield event.plain_result(MSG_FETCH_FAIL)
            return
        self_id = event.get_self_id()

        old_spouse, new_spouse, msg = self._change_logic(
            group_id, user_id, members, self_id
        )
        if msg:
            yield event.plain_result(msg)
            return
        result = self._build_result(
            user_id,
            new_spouse.get("user_id"),
            "🔄 {user} 换了一个老婆：{spouse}！",
            at_both,
            event.get_sender_name(),
            self._name_of(new_spouse),
        )
        yield event.chain_result(result.chain)

"""Separate observed text from optional visual/contextual inferences."""

LABELS = {"text": "文本", "emoji": "Emoji", "sticker": "表情包", "gif": "GIF / 动态表情",
          "image": "图片", "video_channel": "视频号", "article": "文章卡片", "video": "视频",
          "link": "链接", "file": "文件", "voice": "语音", "unknown": "未识别消息", "system": "系统"}

def message_text(message):
    if not isinstance(message, dict) or "type" not in message:
        return str(message.get("text", "")) if isinstance(message, dict) else str(message[1])
    kind = message["type"]
    meta = message.get("metadata") or {}
    lines = [f"类型：{LABELS.get(kind, kind)}"]
    if message.get("text"):
        lines.append("可见文字（OCR）：" + message["text"])
    for key, label in (("title", "标题（OCR）"), ("source", "来源（OCR）"), ("author", "作者（OCR）"),
                       ("local_semantics", "本地表情语义")):
        if meta.get(key):
            lines.append(f"{label}：{meta[key]}")
    visual = meta.get("visual") or {}
    if visual:
        lines.append(f"视觉推断（置信度 {visual.get('confidence', 0):.2f}）：{visual.get('visual_description', '')}")
        for key in ("title", "author", "source"):
            if visual.get(key):
                lines.append(f"视觉推断 {key}：{visual[key]}")
    intent = meta.get("intent") or {}
    if intent:
        lines.append(f"上下文意图推断（非事实，置信度 {intent.get('confidence', 0):.2f}）："
                     f"{intent.get('likely_intent', '')}；语气：{intent.get('tone', '')}")
    if kind not in ("text", "emoji"):
        lines.append("识别状态：" + meta.get("recognition_status", "未开启内容识别；仅知道可见卡片"))
        if kind in ("article", "link", "video", "video_channel"):
            lines.append("限制：仅有截图中的卡片/缩略图，未打开正文或播放视频")
    lines.append(f"消息置信度：{message.get('overall_confidence', 0):.2f}；"
                 f"发言人置信度：{message.get('sender_confidence', 0):.2f}")
    return "\n".join(lines)

def engine_messages(messages):
    return [{**m, "text": message_text(m)} if isinstance(m, dict) else m for m in messages]

def transcript(messages):
    lines = []
    for m in messages:
        who = m.get("from", "unknown")
        person = m.get("name") or {"her": "对方", "me": "我"}.get(who, "归属不确定")
        lines.append(f"[{person}]\n{message_text(m)}")
    return "\n\n".join(lines)


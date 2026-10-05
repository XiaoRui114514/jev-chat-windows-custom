# -*- coding: utf-8 -*-
"""两张来源表：判断模型 Jev / 起草语言模型。纯数据，不联网、不认 key。

表里只有协议、地址和默认模型，**绝不出现 key**（KICKOFF 硬约束 #6）——
key 一律由调用方从环境变量/注册表取了再传进来。协议具体怎么调见 core/llm.py。

全程只有两把 key：判断一把 JEV_API_KEY、起草一把 LLM_API_KEY，跟选哪家来源无关，
换来源就是换同一个槽里的值。
"""
from __future__ import annotations

import uuid
from collections import namedtuple

OPENROUTER_BASE = "https://openrouter.ai/api/v1"  # OpenAI 兼容；auth/key 探测也挂在它下面
# Jev 判断只有 OpenRouter 这条路要自己拼 HTTP：typesafe_sdk 把路径写死成 /v1/systemone，打不到这个地址
OPENROUTER_DECISIONS = "https://openrouter.ai/api/alpha/decisions"
# 免费的密钥探测端点：Jev 模型不在 /models 目录里（列表写死），key 对不对靠它验
OPENROUTER_KEY_URL = "https://openrouter.ai/api/v1/auth/key"
TYPESAFE_BASE = "https://api.typesafe.ai"

JEV_ENV = "JEV_API_KEY"    # 判断那把，不管选 OpenRouter 还是 TypeSafe
LLM_ENV = "LLM_API_KEY"    # 起草那把，不管选哪家语言模型
# 迁移：老版本按来源各存一个变量。新变量空着、老变量有值就先用老的（保存时抄进新的）
LEGACY = {JEV_ENV: "OPENROUTER_API_KEY", LLM_ENV: "DEEPSEEK_API_KEY"}

_Jev = namedtuple("_Jev", "name default")
JEV_PROVIDERS = {
    "openrouter": _Jev("OpenRouter", "typesafe/jev-1.13"),
    "typesafe": _Jev("TypeSafe 直连", "jev-latest"),
    "custom_openai": _Jev("自定义 · OpenAI 兼容", ""),
    "custom_typesafe": _Jev("自定义 · TypeSafe 兼容", ""),
}

# protocol ∈ {openai, anthropic, gemini}：决定 core/llm.py 用哪个官方 SDK
# base 空 = 用 SDK 自带的默认地址（gemini），或者等用户自己填（自定义来源）
# default 空 = 这家没有钦点的默认模型，用户得「获取模型」自己挑一个
# extra：OpenAI 协议下开/关思考模式要额外带的 body 字段，各家不一样；
#        anthropic / gemini 的思考开关是协议自带的参数，由 llm.py 直接处理，这里给空
# headers：有的来源要求每个请求带固定头（不含 key）。keep：从「获取模型」结果里留下哪些 id
_Draft = namedtuple("_Draft", "name protocol base default extra headers keep", defaults=(None, None))
_NONE = lambda on: {}  # noqa: E731 —— 没有思考开关的来源
# OpenCode Go 用这个头做路由和 prompt cache，缺了直接 400。进程内一个 UUID 就过格式校验
_OPENCODE_HEADERS = {
    "x-opencode-session": str(uuid.uuid4()),
    "User-Agent": "jev-chat-windows",
}
# /v1/models 还混着走 /messages、/responses 的模型，那些用 chat/completions 会失败
_OPENCODE_CHAT = ("deepseek-", "glm-", "kimi-", "mimo-", "longcat-", "hy", "space-bunny-")
_opencode_chat = lambda model_id: model_id.startswith(_OPENCODE_CHAT)  # noqa: E731
DRAFT_PROVIDERS = {  # 第一个就是默认：DeepSeek 官网直连
    "deepseek": _Draft("DeepSeek 官网", "openai", "https://api.deepseek.com", "deepseek-flash",
                       lambda on: {"thinking": {"type": "enabled" if on else "disabled"}}),
    "openrouter": _Draft("OpenRouter", "openai", OPENROUTER_BASE,
                         "deepseek/deepseek-v4.1-flash", lambda on: {"reasoning": {"enabled": on}}),
    "openai": _Draft("OpenAI", "openai", "https://api.openai.com/v1", "", _NONE),
    "moonshot": _Draft("Moonshot (Kimi)", "openai", "https://api.moonshot.cn/v1", "", _NONE),
    "zhipu": _Draft("智谱 GLM", "openai", "https://open.bigmodel.cn/api/paas/v4", "", _NONE),
    "dashscope": _Draft("通义千问", "openai",
                        "https://dashscope.aliyuncs.com/compatible-mode/v1", "", _NONE),
    "siliconflow": _Draft("硅基流动", "openai", "https://api.siliconflow.cn/v1", "", _NONE),
    "opencode": _Draft("OpenCode Go", "openai", "https://opencode.ai/zen/go/v1",
                       "deepseek-v4.1-flash", _NONE, _OPENCODE_HEADERS, _opencode_chat),
    "anthropic": _Draft("Anthropic", "anthropic", "https://api.anthropic.com", "", _NONE),
    "gemini": _Draft("Google Gemini", "gemini", "", "", _NONE),
    "custom_openai": _Draft("自定义 · OpenAI 兼容", "openai", "", "", _NONE),
    "custom_anthropic": _Draft("自定义 · Anthropic 兼容", "anthropic", "", "", _NONE),
}

# 这两个来源没有固定地址，设置页要多露一行 Base URL 出来
CUSTOM = ("custom_openai", "custom_anthropic")
# 起草时认思考开关的来源，设置页那句提示照着这里写
THINKING = ("DeepSeek", "OpenRouter", "Anthropic", "Gemini")
# 所有可能存 key 的环境变量（新两把 + 两个老名字），脱敏时一次全过一遍（jev_client.redact_secrets）
ENV_VARS = sorted({JEV_ENV, LLM_ENV, *LEGACY.values()})



JEV_CUSTOM = ("custom_openai", "custom_typesafe")
VISION_ENV = "VISION_API_KEY"
ENV_VARS = sorted({*ENV_VARS, VISION_ENV})

# -*- coding: utf-8 -*-
"""父进程：只管界面。截图 + OCR 在 app/worker.py 的子进程里跑，队列里收新消息 →
冒出新的对方消息才调 engine → 悬浮窗给 3 条候选 → 人点「填入」。发送永远手动。静默期零调用。
上下文、结果、聊天记录都按会话名（子进程 OCR 头部标题得来）分开存，切会话不串味。

    pip install rapidocr-onnxruntime numpy windows-capture PySide6-Fluent-Widgets
两个模型（判断 Jev / 起草语言模型）的来源和 key 在独立设置页填写，不用改代码。IDE 里直接 Run。
"""
import ctypes
import multiprocessing
import sys

if __name__ == "__main__" and len(sys.argv) == 3 and sys.argv[1] == "--smoke-test":
    multiprocessing.freeze_support()
    from app.smoke import run
    raise SystemExit(run(sys.argv[2]))

import queue
import threading
import traceback
import time
from core.media import MediaAnalyzer
from core.emoji.intent import EmojiIntentAnalyzer
from core.message.context import engine_messages, transcript
from core.providers import DRAFT_PROVIDERS
from core.errors import redact_secrets
from collections import deque, OrderedDict
from copy import deepcopy
from concurrent.futures import CancelledError
from core.errors import credential_snapshot
from core.providers import JEV_ENV, LLM_ENV

from app import settings, update, worker
from app.capture import find_chat_hwnd
from app.fill import fill
from app.overlay import Overlay
from app.version import VERSION
from core.engine import analyze
from app.i18n import T

# {会话名: {history, result, rev, target, senders}}：每个会话各自的上下文、上次结果和版本号，互不串味
# history 里是 [(who, text, name)]，engine 只认 her/me，name 是群里的发言人（单聊/自己说的是 None）；
# 只是缓冲区，实际喂模型几条由设置里的「参考上下文」决定
# senders：这个群里发过言的人，去重、最近的排最前；target：用户挑的回复对象（None = 跟着最近那个走）
media_analyzer = MediaAnalyzer()
emoji_analyzer = EmojiIntentAnalyzer()
chats = OrderedDict()
pending = OrderedDict()
active_cancel = None
active_title = None
state = {"area": None, "busy": False, "hwnd": None, "chat": ""}
results = queue.Queue()
update_result = queue.Queue()  # 独立小队列，别跟 results 的 (kind, r, title, revision) 形状搅在一起


def chat_of(title):
    if title not in chats:
        chats[title] = {"history": deque(maxlen=60), "result": None, "rev": 0,
                        "target": None, "senders": [], "crops": {}}
    chats.move_to_end(title)
    while len(chats) > 32:
        shown = ov.current_chat() if "ov" in globals() else ""
        victim = next((k for k in chats if k not in pending and k not in (title, active_title, state['chat'], shown)), None)
        if victim is None: break
        del chats[victim]
        if "ov" in globals(): ov.forget_chat(victim)
    return chats[title]


def target_of(title):
    """这个会话现在的回复对象：用户挑过且人还在就用它，否则用最近说话的那个；单聊没有发言人 → None。"""
    chat = chat_of(title)
    if chat["target"] in chat["senders"]:
        return chat["target"]
    return chat["senders"][0] if chat["senders"] else None


def fill_reply(text):
    if state["hwnd"] is None:  # 子进程重开过，hwnd 可能换了，用最新的
        raise RuntimeError(T("未找到聊天窗口，请确认已经打开"))
    if state["area"] is None:
        raise RuntimeError(T("输入区域尚不可用，请确认聊天窗口可见（不要最小化）"))
    if settings.reply_target() and ov.at_prefix_enabled():
        target = target_of(ov.current_chat())  # 填进去的是界面上正看着的那个会话的对象
        if target:
            text = f"@{target} " + text  # 纯文本，微信不认成真正的 @，只是让群里看得出在跟谁说
    fill(state["hwnd"], state["area"], text)


def spawn_worker():
    """开一个采集子进程，它跟着 capture_on 走：置位=采集，清掉=暂停。"""
    p = multiprocessing.Process(target=worker.run,
                                args=(q, state["hwnd"], capture_on, debug_on, state.get("app")),
                                daemon=True)
    p.start()
    return p


def set_debug(on):
    """调试视图开关：开 → 开窗 + 置位（子进程这才开始送帧，一帧 2~3MB）；关 → 清掉 + 收窗。"""
    global dbg
    if not on:
        debug_on.clear()
        if dbg is not None:
            dbg.hide()
        return
    if dbg is None:
        from app.debugwin import DebugWindow

        dbg = DebugWindow(on_close=on_debug_closed)
    dbg.show()
    debug_on.set()


def on_debug_closed():
    """用户直接关了调试窗 = 把开关也关了，否则设置页显示开着但没窗。"""
    debug_on.clear()
    ov.set_debug_switch(False)
    settings.save(debug_view_on=False)


def on_language_changed():
    """主界面切换语言后，同步刷新已经打开过的调试窗。"""
    if dbg is not None:
        dbg.retranslate()


def on_toggle_capture(on):
    """标题栏开关。启动时没找到微信就没有子进程，这会儿再找一次，找到了才真开得起来。"""
    global child
    if not on:
        capture_on.clear()
        return
    if child is None:
        try:
            state["hwnd"], found = find_chat_hwnd()
            state["app"] = found.key
        except RuntimeError:
            ov.set_capture(False, "未找到聊天窗口，打开后再开启采集")
            return
        child = spawn_worker()
    capture_on.set()


def analyze_bg(msgs, title, revision, reply_to, crops, cfg, cancel):
    started = time.perf_counter()
    def checkpoint(stage):
        if cancel.is_set(): raise CancelledError()
        results.put(("stage", stage, title, revision))
    with credential_snapshot(cfg['keys']):
        try:
            checkpoint("识别")
            enriched, stats = media_analyzer.enrich(msgs, crops or {}, cfg['recognition'], cfg['vision'])
            checkpoint("识别表情")
            spec = DRAFT_PROVIDERS[cfg['provider']]
            enriched, intent_stats = emoji_analyzer.enrich(enriched, cfg['recognition']["emoji_intent"],
                {"protocol": spec.protocol, "base_url": cfg['base_url'] or spec.base,
                 "api_key": cfg['keys'][LLM_ENV], "model": cfg['model'], "headers": spec.headers}, keep=cfg['context'])
            stats.update(intent_stats)
            args = {k:v for k,v in cfg.items() if k not in ('recognition','vision','keys')}
            result = analyze(engine_messages(enriched), reply_to=reply_to, checkpoint=checkpoint, **args)
            result["recognition"] = {**stats, "context": transcript(enriched[-cfg['context']:]),
                                     "messages": enriched, "total_ms": int((time.perf_counter()-started)*1000)}
            results.put(("ok", result, title, revision))
        except CancelledError:
            results.put(("cancel", "", title, revision))
        except Exception as exc:
            results.put(("err", f"{T('分析失败: ')}{redact_secrets(str(exc))}", title, revision))


def check_update_bg():
    """启动时后台查一次新版本，跟 analyze_bg 一个套路：网络调用在线程里，UI 只在 tick() 里动。"""
    r = update.check_latest(VERSION)
    if r:
        update_result.put(r)


def cancel_analysis():
    title = ov.current_chat()
    pending.pop(title, None)
    if title == active_title and active_cancel is not None:
        active_cancel.set()
        ov.set_status("正在停止生成…", "busy")


def request_reanalysis():
    title = ov.current_chat()
    msgs = list(chat_of(title)['history'])
    if not msgs:
        ov.set_status("当前会话还没有可分析的消息", "warning")
        return
    start_analyze(title, msgs)


def start_analyze(title, msgs):
    global active_cancel, active_title
    if state['busy']:
        pending[title] = deepcopy(msgs)
        while len(pending) > 32: pending.popitem(last=False)
        if active_cancel is not None: active_cancel.set()
        return
    if not settings.has_jev_key():
        ov.set_status("请先在设置中配置模型", "warning")
        return
    if not settings.has_llm_key():
        ov.set_status(lambda name=settings.draft_provider_name():
                      f"{T('起草来源 ')}{name}{T(' 没填密钥，去设置里补上')}", "warning")
        return
    state["busy"] = True
    ov.set_busy(True)
    reply_to = target_of(title) if settings.reply_target() else None  # 开关关着就是今天的行为
    crops = dict(chat_of(title)["crops"])
    cfg = {name: getattr(settings, name)() for name in ('relationship','context','style','thinking','jev_provider','jev_model','jev_base_url')}
    cfg.update(provider=settings.draft_provider(), model=settings.draft_model() or None,
               base_url=settings.draft_base_url() or None, recognition=deepcopy(settings.recognition()),
               vision=deepcopy(settings.vision_config()), keys={JEV_ENV: settings.jev_key(), LLM_ENV: settings.llm_key()})
    active_cancel, active_title = threading.Event(), title
    threading.Thread(target=analyze_bg, args=(deepcopy(msgs), title, chat_of(title)["rev"], reply_to, crops, cfg, active_cancel),
                     daemon=True).start()


def on_target_change(title, name):
    """用户挑了回复对象：记下来，这个会话里有对方的话就照新对象重跑一次。"""
    chat = chat_of(title)
    chat["target"] = name
    msgs = list(chat["history"])
    if not any(m.get("from") == "her" for m in msgs):
        return
    start_analyze(title, msgs)


def drain():
    """把子进程队列里攒的东西全收掉。"""
    global child
    while True:
        try:
            msg = q.get_nowait()
        except queue.Empty:
            return
        kind = msg[0]
        if kind == "area":  # 只是窗口挪了位置，坐标跟着更新，别的什么都不用动
            state["area"] = msg[1]
            continue
        if kind == "chat":  # 微信切了会话，界面跟过去（用户正浏览别的会话时也跟，微信是准的）
            state["chat"] = msg[1]
            ov.set_chat(msg[1])
            continue
        if kind == "debug":  # 调试视图的一帧；窗口不在就直接丢掉
            if dbg is not None:
                dbg.show_packet(msg[1])
            continue
        if kind == "status":  # 单帧识别失败/报错，提示一下就好，别把正在跑的分析和已知坐标清掉
            ov.set_status(msg[1], "warning")
            ov.log(msg[1])
            continue
        if kind == "paused":  # 子进程确认已暂停
            ov.set_capture(False)
            continue
        if kind == "resumed":  # 子进程重新开始采集
            ov.set_capture(True)
            continue
        if kind == "dead":  # 采集彻底停了（微信关了之类），这才是真的要清状态
            state["area"] = None
            for c in chats.values():  # 在跑的分析作废，回来的结果不再往界面上贴
                c["rev"] += 1
            state["rerun"] = None
            ov.invalidate_replies()
            ov.set_busy(False)
            ov.set_capture(False, msg[1])
            ov.log(msg[1])
            if child is not None:  # 子进程已经不干活了，收掉引用，下次打开开关重开一个
                child.terminate()
                child.join()
                child = None
            continue
        _, title, new, area, crops = msg
        state["area"] = area
        chat = chat_of(title)
        chat["rev"] += 1  # 这个会话有新消息了，它在跑的分析作废
        if title == ov.current_chat():  # 看的是别的会话就别把人家的候选划掉
            ov.invalidate_replies()
        chat["crops"].update(crops)
        for message in new:
            who, name, text = message["from"], message.get("name"), message.get("text") or "["+message["type"]+"]"
            chat["history"].append(message)
            ov.log_message(who, text, name, chat=title)
            if who == "her" and name:
                if name in chat["senders"]:
                    chat["senders"].remove(name)
                chat["senders"].insert(0, name)
        # Keep only a small recent crop buffer; images are never persisted.
        recent_ids = {m["id"] for m in list(chat["history"])[-settings.context():]}
        chat["crops"] = {k: v for k, v in chat["crops"].items() if k in recent_ids}
        while len(chat["crops"]) > 12:
            del chat["crops"][next(iter(chat["crops"]))]
        ov.set_targets(title, chat["senders"], target_of(title))  # 显不显示这一行由悬浮窗按开关决定
        if new[-1]["from"] == "her":  # 只有对方最新说话才值得分析
            msgs = list(chat["history"])
            start_analyze(title, msgs)
        else:
            pending.pop(title, None)
            if title == active_title and active_cancel is not None: active_cancel.set()
            ov.set_busy(False)
            ov.set_status("你已回复，等待对方的新消息")


def tick():
    try:
        drain()
        while not update_result.empty():
            latest, url = update_result.get()
            ov.set_update(latest, url)
        while not results.empty():
            kind, r, title, revision = results.get()
            if kind == 'stage':
                if title == ov.current_chat() and revision == chat_of(title)['rev']:
                    ov.set_status('正在' + r + '…', 'busy')
                continue
            state["busy"] = False
            if pending:
                t, msgs = pending.popitem(last=False)
                start_analyze(t, msgs)
                continue
            if kind == 'cancel':
                ov.set_busy(False)
                continue
            if revision != chat_of(title)["rev"]:  # 这个会话后来又说话了，这份结果过期了
                ov.set_busy(False)
                continue
            if kind == "ok":
                if dbg is not None and title == state["chat"]:
                    dbg.show_analysis(r.get("recognition", {}), r.get("diagnostics", []))
                chat_of(title)["result"] = r  # 先存着；正看着这个会话才立刻贴上去
                if title == ov.current_chat():
                    ov.show(r)
                else:
                    ov.set_busy(False)
            else:
                ov.set_busy(False)
                ov.set_status("生成失败，请检查网络和服务设置；新消息到来后会重试。", "error")
                ov.log(r)
    except Exception:
        traceback.print_exc()  # 一帧出错不退出
    ov.after(50, tick)


if __name__ == "__main__":  # Windows 的 spawn 会让子进程重新执行本文件，没这行就无限套娃开进程
    multiprocessing.freeze_support()  # 打包成 exe 后 spawn 出来的子进程会重跑一遍 exe，没这行就无限弹界面
    ctypes.windll.user32.SetProcessDPIAware()
    q = multiprocessing.Queue()
    capture_on = multiprocessing.Event()  # 父子进程共用的开关，置位=采集
    debug_on = multiprocessing.Event()  # 同上，置位=子进程往队列里送整帧给调试窗
    child = dbg = None
    ov = Overlay(on_fill=fill_reply, on_reanalyze=request_reanalysis, on_cancel=cancel_analysis, on_toggle_capture=on_toggle_capture,
                 on_target_change=on_target_change, on_toggle_debug=set_debug,
                 on_language_changed=on_language_changed,
                 result_of=lambda t: chats.get(t, {}).get("result"))
    try:
        state["hwnd"], found = find_chat_hwnd()
        state["app"] = found.key
    except RuntimeError:
        ov.set_capture(False, "未找到聊天窗口，打开后再开启采集")
    else:
        capture_on.set()
        child = spawn_worker()
    if settings.debug_view():  # 上次开着就直接开回来
        set_debug(True)
    if not settings.has_jev_key():
        ov.set_status("请先在设置中配置模型", "warning")
        ov.after(0, ov.open_settings)
    if settings.check_update() and update.parse_version(VERSION):  # 开发版没有版本号，不查也不烦源码用户
        threading.Thread(target=check_update_bg, daemon=True).start()
    ov.after(50, tick)
    try:
        ov.run()
    finally:
        if child is not None:
            child.terminate()

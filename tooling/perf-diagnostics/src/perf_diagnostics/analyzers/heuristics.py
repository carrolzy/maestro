from __future__ import annotations


def build_heuristics(
    trace_overview: dict[str, object],
    stalls: dict[str, object],
    hotspots: dict[str, object],
) -> dict[str, object]:
    top_scripts = hotspots.get("top_scripts", [])
    top_keywords = hotspots.get("top_keywords", [])
    top_stacks = hotspots.get("top_stacks", [])
    stack_text = " ".join(item["stack"] for item in top_stacks[:5])
    script_names = [item["script"] for item in top_scripts[:5]]

    cross_page_signals = []
    if any("cms-activity-page" in script for script in script_names) and any("pages/home" in script for script in script_names):
        cross_page_signals.append("旧页与返回目标页的脚本同时出现在主热点中，疑似跨页残留工作。")
    if "mergebodywithproducts" in stack_text.lower() or "loadproductmodulessequential" in stack_text.lower():
        cross_page_signals.append("模块加载或回包 merge 栈仍处于热点，疑似页面切走后旧任务未完全停下。")

    request_render_signals = []
    if any(item["keyword"] in {"patch", "diff", "flushSchedulerQueue", "cloneWithData"} for item in top_keywords[:4]):
        request_render_signals.append("热点以渲染 diff / patch 为主，说明瓶颈更偏向回包后的渲染负载。")
    if any(item["keyword"] == "request" for item in top_keywords):
        request_render_signals.append("存在请求回调与 merge 相关热点，需要区分网络耗时和回包后的主线程压力。")
    if any(item["keyword"] == "destroy" for item in top_keywords):
        request_render_signals.append("返回路径存在组件销毁热点，可能在 back navigation 时集中释放组件。")

    suspected_causes = []
    if cross_page_signals:
        suspected_causes.append(
            {
                "title": "旧页异步残留或跨页回调继续占用主线程",
                "confidence": "high",
                "evidence": cross_page_signals,
            }
        )
    if any(item["keyword"] == "destroy" for item in top_keywords):
        suspected_causes.append(
            {
                "title": "大量组件销毁导致返回路径卡顿",
                "confidence": "medium",
                "evidence": ["热点包含 destroy / detached / disconnect 相关栈。"],
            }
        )
    if any(item["keyword"] in {"patch", "diff", "flushSchedulerQueue", "cloneWithData"} for item in top_keywords):
        suspected_causes.append(
            {
                "title": "setData / diff / patch 触发的渲染峰值过重",
                "confidence": "medium",
                "evidence": ["热点包含渲染调度和 diff 关键词。"],
            }
        )

    recommended_actions = []
    if cross_page_signals:
        recommended_actions.append("优先排查页面卸载后的异步请求、定时器、延迟加载和回包 merge 是否仍继续执行。")
    if any(item["keyword"] == "destroy" for item in top_keywords):
        recommended_actions.append("减少离屏真实组件数量，把销毁成本分摊到滚动过程，而不是返回时集中销毁。")
    if any(item["keyword"] in {"patch", "diff", "flushSchedulerQueue", "cloneWithData"} for item in top_keywords):
        recommended_actions.append("继续压缩首屏和返回路径上的 setData / diff 范围，避免回包后一次性渲染峰值。")

    confidence = "medium"
    if suspected_causes and stalls.get("long_task_count", 0) >= 2 and trace_overview.get("task_event_count", 0) >= 3:
        confidence = "high"

    return {
        "cross_page_signals": cross_page_signals,
        "request_render_signals": request_render_signals,
        "suspected_causes": suspected_causes,
        "recommended_actions": recommended_actions,
        "confidence": confidence,
    }

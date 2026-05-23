from __future__ import annotations

from typing import Any


STYLE_CONFIG = {
    "hard_sell": {
        "label": "硬核带货",
        "tone": "直接、有冲击力、强调痛点和成交理由",
        "hook": "别再乱买了，真正好用的{product_name}，看这三个点就够了。",
    },
    "emotional_seed": {
        "label": "情绪种草",
        "tone": "有生活感、先共鸣再给解决方案",
        "hook": "如果你也被这个问题困住过，这个{product_name}可能刚好适合你。",
    },
    "review": {
        "label": "测评解说",
        "tone": "客观、拆解细节、像真实体验分享",
        "hook": "这款{product_name}到底值不值得买？我直接说结论。",
    },
    "story": {
        "label": "剧情短片",
        "tone": "场景化、轻剧情、用冲突推动卖点",
        "hook": "本来只是随手试了一下，没想到这个{product_name}真解决了问题。",
    },
}


def generate_commerce_package(
    *,
    product_name: str,
    product_highlights: str,
    target_audience: str,
    video_style: str,
    use_digital_human: bool,
) -> dict[str, Any]:
    style = STYLE_CONFIG.get(video_style, STYLE_CONFIG["hard_sell"])
    raw_points = [
        point.strip(" -，,.;；。")
        for point in product_highlights.replace("\n", "，").replace("、", "，").split("，")
        if point.strip(" -，,.;；。")
    ]
    if not raw_points:
        raw_points = ["解决真实使用痛点", "提升效率或体验", "适合日常高频场景"]

    selling_points = [
        {
            "index": index + 1,
            "point": point,
            "consumer_benefit": f"让{target_audience or '目标用户'}更快感知到{product_name}的实际价值。",
            "proof_angle": "用近景细节、使用前后对比或真实场景演示来证明。",
        }
        for index, point in enumerate(raw_points[:5])
    ]

    hook = style["hook"].format(product_name=product_name)
    script = build_script(
        product_name=product_name,
        target_audience=target_audience,
        selling_points=selling_points,
        hook=hook,
        style_label=style["label"],
    )
    shot_list = build_shot_list(
        product_name=product_name,
        target_audience=target_audience,
        selling_points=selling_points,
        hook=hook,
        use_digital_human=use_digital_human,
        style_label=style["label"],
    )
    title_options = [
        f"{product_name}到底值不值得买？看完这条就懂",
        f"给{target_audience or '同类人群'}的{product_name}真实推荐",
        f"这几个细节，决定了{product_name}好不好用",
        f"别急着下单，先看{product_name}这3个重点",
        f"{product_name}带货短视频脚本，一条讲清楚",
    ]
    caption = f"{product_name}｜{style['label']}｜适合{target_audience or '精准人群'}的半自动 AI 带货视频方案。"
    cover_text = f"别急着买\n先看这3点"
    cover_prompt = (
        f"{product_name} 抖音带货封面，9:16，商品主体清晰，强对比光影，"
        f"大字标题'{cover_text.replace(chr(10), ' ')}'，电影感，电商爆款视觉"
    )
    hashtags = [
        f"#{product_name}",
        "#抖音带货",
        "#好物推荐",
        f"#{style['label']}",
        f"#{target_audience or '精准人群'}",
    ]
    comment_prompt = f"评论区引导：你会为了{selling_points[0]['point']}入手{product_name}吗？"
    closing_cta = f"想少踩坑，先看详情页，再决定这款{product_name}适不适合你。"
    admin_workflow = build_admin_workflow(use_digital_human)

    return {
        "selling_points": selling_points,
        "hook": hook,
        "script": script,
        "shot_list": shot_list,
        "title_options": title_options,
        "caption": caption,
        "cover_text": cover_text,
        "cover_prompt": cover_prompt,
        "hashtags": hashtags,
        "comment_prompt": comment_prompt,
        "closing_cta": closing_cta,
        "admin_workflow": admin_workflow,
    }


def build_script(
    *,
    product_name: str,
    target_audience: str,
    selling_points: list[dict[str, Any]],
    hook: str,
    style_label: str,
) -> str:
    audience = target_audience or "正在挑选同类产品的人"
    point_lines = "\n".join(
        f"{item['index']}. {item['point']}，重点是{item['consumer_benefit']}"
        for item in selling_points[:3]
    )
    return (
        f"{hook}\n\n"
        f"如果你是{audience}，选{product_name}别只看表面参数，真正要看的是使用场景。\n\n"
        f"{point_lines}\n\n"
        f"这条视频用{style_label}的方式呈现：先抓痛点，再给细节，再用真实画面证明。"
        f"如果你正在找一款更省心的{product_name}，这款可以重点看看。"
    )


def build_shot_list(
    *,
    product_name: str,
    target_audience: str,
    selling_points: list[dict[str, Any]],
    hook: str,
    use_digital_human: bool,
    style_label: str,
) -> list[dict[str, Any]]:
    presenter = "数字人口播" if use_digital_human else "字幕旁白"
    first_point = selling_points[0]["point"]
    second_point = selling_points[1]["point"] if len(selling_points) > 1 else "核心功能演示"
    third_point = selling_points[2]["point"] if len(selling_points) > 2 else "细节特写"
    return [
        {
            "index": 1,
            "duration": "0-3s",
            "scene": "强钩子开场，产品快速入镜",
            "camera": "近景快速推进",
            "action": f"{presenter}直接说出痛点，产品图做闪切",
            "narration": hook,
            "visual_prompt": f"{product_name} 电商短视频开场，深色科技感，高对比光影，快速吸引注意力",
            "tool_suggestion": "HeyGen + 剪映",
        },
        {
            "index": 2,
            "duration": "3-10s",
            "scene": "目标人群痛点场景",
            "camera": "中景转产品特写",
            "action": f"展示{target_audience or '用户'}遇到的问题，再切到产品解决方案",
            "narration": f"如果你也遇到这个问题，{product_name}的关键在于{first_point}。",
            "visual_prompt": f"{target_audience} 使用 {product_name} 的真实生活场景，痛点对比，商业广告质感",
            "tool_suggestion": "即梦 / 可灵",
        },
        {
            "index": 3,
            "duration": "10-22s",
            "scene": "卖点一和卖点二拆解",
            "camera": "俯拍细节 + 手持跟拍",
            "action": f"连续展示{first_point}和{second_point}",
            "narration": f"第一，看{first_point}；第二，看{second_point}。",
            "visual_prompt": f"{product_name} 产品功能细节展示，手部操作，真实测评，清晰商品特写",
            "tool_suggestion": "可灵",
        },
        {
            "index": 4,
            "duration": "22-35s",
            "scene": "第三卖点和信任证明",
            "camera": "微距特写 + 使用前后对比",
            "action": f"展示{third_point}，加字幕强调利益点",
            "narration": f"真正拉开差距的是{third_point}，这才是日常高频使用时能感受到的地方。",
            "visual_prompt": f"{product_name} 使用前后对比，微距质感，干净背景，电商详情页风格",
            "tool_suggestion": "即梦 / 剪映",
        },
        {
            "index": 5,
            "duration": "35-45s",
            "scene": "成交收口",
            "camera": "产品定格 + 价格/权益信息留白",
            "action": "画面定格，保留商品链接和行动号召区域",
            "narration": f"想要省心一点，{product_name}可以直接加入备选，先看详情再决定。",
            "visual_prompt": f"{product_name} 电商成交页收口，干净构图，商品居中，留出文字和价格信息空间",
            "tool_suggestion": "剪映 / CapCut",
        },
    ]


def build_admin_workflow(use_digital_human: bool) -> list[dict[str, Any]]:
    workflow = [
        {
            "step": 1,
            "tool": "HeyGen",
            "action": "导入个人形象素材和参考语音，创建或选择 avatar / voice。",
        },
        {
            "step": 2,
            "tool": "HeyGen",
            "action": "复制 AI 口播脚本，生成数字人口播片段。" if use_digital_human else "如果不使用数字人，跳过口播人物生成，改用字幕旁白。",
        },
        {
            "step": 3,
            "tool": "即梦 / 可灵",
            "action": "按分镜复制 visual_prompt，生成商品场景、细节和使用画面。",
        },
        {
            "step": 4,
            "tool": "剪映 / CapCut",
            "action": "合并口播、商品镜头、字幕、标题和音乐，导出 9:16 MP4。",
        },
        {
            "step": 5,
            "tool": "Studio",
            "action": "上传最终 MP4，状态切换 completed，交付用户下载。",
        },
    ]
    return workflow

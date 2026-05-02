"""
视频索引优化 — 端到端测试脚本

使用方法:
  python tests/test_video_indexer.py          # 完整测试
  python tests/test_video_indexer.py --step 1 # 仅测试步骤 1（场景检测）
  python tests/test_video_indexer.py --step 4 # 仅测试步骤 4（索引构建）
  python tests/test_video_indexer.py --step 6 # 仅测试步骤 6（API 调用）

前置条件:
  1. 数据库中有视频素材（ID=1 或 ID=2）
  2. core-nexus-ai 服务可用（ASR/VL/LLM 需要调用外部 API）
"""
import sys
import os
import time
import json
import argparse

# 确保项目根目录在 Python 路径中
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))


def print_header(title):
    print(f"\n{'='*60}")
    print(f"  {title}")
    print(f"{'='*60}")


def print_result(name, result):
    if result:
        print(f"  [OK] {name}: {json.dumps(result, ensure_ascii=False, indent=2)[:500]}")
    else:
        print(f"  [FAIL] {name}: 返回 None")


# ── Step 1: 场景检测 ──

def test_scene_detection(video_path):
    """测试 ffmpeg 场景检测"""
    print_header("Step 1: 场景检测 (FFmpeg)")
    from src.application.services import ffmpeg_adapter as ffmpeg

    start = time.time()
    changes = ffmpeg.detect_scene_changes(video_path, threshold=0.3)
    elapsed = time.time() - start

    print(f"  场景切换点数: {len(changes)}")
    print(f"  耗时: {elapsed:.2f}s")
    for i, c in enumerate(changes[:10]):
        print(f"    [{i}] {c['time']:.2f}s")
    return changes


# ── Step 2: 关键帧提取 ──

def test_keyframe_extraction(video_path, output_dir):
    """测试关键帧提取"""
    print_header("Step 2: 关键帧提取 (FFmpeg)")
    from src.application.services import ffmpeg_adapter as ffmpeg

    os.makedirs(output_dir, exist_ok=True)

    start = time.time()
    keyframes = ffmpeg.extract_keyframes(
        video_path, output_dir, mode="smart", max_frames=10
    )
    elapsed = time.time() - start

    print(f"  关键帧数: {len(keyframes)}")
    print(f"  耗时: {elapsed:.2f}s")
    for kf in keyframes[:5]:
        print(f"    {os.path.basename(kf['path'])} @ {kf['timestamp']:.2f}s")
    return keyframes


# ── Step 3: ASR 转录 ──

def test_asr(video_path):
    """测试 ASR 转录"""
    print_header("Step 3: ASR 转录 (core-nexus)")
    from src.shared.utils.core_nexus_client import get_client
    from src.shared.utils.config_manager import get as cfg_get
    from src.shared.utils.result_cache import get_cached

    # 先查缓存
    cached = get_cached(video_path, "asr_raw", ttl=3600 * 2)
    if cached is not None:
        print(f"  缓存命中，{len(cached)} 个 segments")
        for seg in cached[:5]:
            print(f"    [{seg['start']:.1f}s - {seg['end']:.1f}s] {seg['text'][:50]}")
        return cached

    try:
        start = time.time()
        client = get_client()
        asr_model = cfg_get("core_nexus.asr_model") or None
        result = client.asr_transcribe(audio=video_path, language="zh", model=asr_model)
        elapsed = time.time() - start

        segments = result.get("segments", [])
        print(f"  segments 数: {len(segments)}")
        print(f"  耗时: {elapsed:.2f}s")
        for seg in segments[:5]:
            print(f"    [{seg.get('start', 0):.1f}s - {seg.get('end', 0):.1f}s] {seg.get('text', '')[:50]}")
        return segments
    except Exception as e:
        print(f"  ASR 跳过（降级）: {str(e)[:120]}")
        return []


# ── Step 4: 完整索引构建 ──

def test_index_pipeline(video_id):
    """测试完整索引 pipeline"""
    print_header("Step 4: 完整索引构建 (VideoIndexer)")
    from src.application.services.video_indexer import VideoIndexer

    indexer = VideoIndexer()

    start = time.time()
    result = indexer.get_or_create_index(video_id)
    elapsed = time.time() - start

    if result:
        print(f"  [OK] 索引构建成功")
        print(f"  镜头数: {len(result)}")
        print(f"  耗时: {elapsed:.2f}s")
        for shot in result:
            desc = shot.get("description", "")[:40] if shot.get("description") else "无"
            sub = shot.get("subtitle_text", "")[:40] if shot.get("subtitle_text") else "无"
            kfs = len(shot.get("keyframe_paths", []))
            print(f"    镜头 {shot['shot_index']}: [{shot['start_time']:.1f}s - {shot['end_time']:.1f}s] "
                  f"关键帧={kfs} 画面={desc} 字幕={sub}")
    else:
        print(f"  [FAIL] 索引构建失败")
    return result


# ── Step 5: 结构化上下文 ──

def test_structured_context(video_id):
    """测试结构化上下文生成"""
    print_header("Step 5: 结构化上下文文本")
    from src.application.services.video_indexer import VideoIndexer

    indexer = VideoIndexer()
    context = indexer.build_structured_context(video_id)

    if context:
        print(f"  [OK] 上下文长度: {len(context)} 字符")
        # 打印前 800 字符
        print(context[:800])
        if len(context) > 800:
            print(f"  ... (共 {len(context)} 字符)")
    else:
        print(f"  [FAIL] 上下文生成失败")
    return context


# ── Step 6: analyze_video_vl 工具（模拟 API 调用）──

async def test_analyze_video_vl(video_id):
    """测试 analyze_video_vl 工具（索引路径 vs VL 降级）"""
    print_header("Step 6: analyze_video_vl 工具调用")

    # 动态导入工具函数
    from src.agent.tool_registry import registry

    tool = registry.get_tool("analyze_video_vl")
    if not tool:
        print("  [FAIL] 工具未注册")
        return

    print(f"  调用 analyze_video_vl(video_id={video_id})...")
    start = time.time()
    result = await tool.execute(video_id=video_id, prompt="分析这个视频的内容和风格")
    elapsed = time.time() - start

    if result.get("success"):
        analysis = result.get("analysis", {})
        index_based = analysis.get("index_based", False)
        mode = "[INDEX] 基于索引" if index_based else "[VL] 基于VL"
        summary = analysis.get("ai_summary", "")[:200]
        print(f"  [OK] {mode} | 耗时: {elapsed:.2f}s")
        print(f"  摘要: {summary}")
    else:
        print(f"  [FAIL] 失败: {result.get('error')}")


# ── Step 7: 二次调用验证缓存 ──

async def test_cached_call(video_id):
    """验证二次调用命中索引缓存"""
    print_header("Step 7: 二次调用（验证缓存）")

    from src.agent.tool_registry import registry
    tool = registry.get_tool("analyze_video_vl")

    # 第二次调用
    start = time.time()
    result = await tool.execute(video_id=video_id, prompt="这个视频讲了什么")
    elapsed = time.time() - start

    if result.get("success"):
        index_based = result.get("analysis", {}).get("index_based", False)
        print(f"  [OK] index_based={index_based} | 耗时: {elapsed:.2f}s")
        print(f"  （如果 index_based=True 且耗时 <1s，说明索引缓存生效）")
    else:
        print(f"  [FAIL] 失败: {result.get('error')}")


# ── 主入口 ──

def main():
    parser = argparse.ArgumentParser(description="视频索引优化测试")
    parser.add_argument("--video-id", type=int, default=1, help="测试视频 ID（默认 1）")
    parser.add_argument("--step", type=int, default=None, help="仅运行指定步骤（1-7）")
    args = parser.parse_args()

    video_id = args.video_id

    # 获取视频文件路径
    from src.infrastructure.db.session import get_db_context
    from src.infrastructure.repositories import VideoRepository
    with get_db_context() as db:
        repo = VideoRepository(db)
        video = repo.get_by_id(video_id)
        if not video:
            print(f"[FAIL] 视频 ID={video_id} 不存在")
            return
        video_path = video.local_path
        print(f"测试视频: ID={video_id} name={video.video_name} "
              f"duration={video.duration}s path={video_path}")

    if not os.path.exists(video_path):
        print(f"[FAIL] 文件不存在: {video_path}")
        return

    output_dir = os.path.join(os.path.dirname(video_path), f"test_keyframes_{video_id}")

    step = args.step

    if step == 1 or step is None:
        test_scene_detection(video_path)

    if step == 2 or step is None:
        test_keyframe_extraction(video_path, output_dir)

    if step == 3 or step is None:
        test_asr(video_path)

    if step == 4 or step is None:
        test_index_pipeline(video_id)

    if step == 5 or step is None:
        test_structured_context(video_id)

    if step == 6 or step is None:
        asyncio.run(test_analyze_video_vl(video_id))

    if step == 7 or step is None:
        asyncio.run(test_cached_call(video_id))

    print_header("测试完成")


if __name__ == "__main__":
    import asyncio
    main()

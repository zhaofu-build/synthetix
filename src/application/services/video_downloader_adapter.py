import os
import random
import logging
import yt_dlp
from src.shared.utils.string_util import sanitize_title
from src.shared.utils import time_util
from src import config
import requests
from urllib.parse import urlencode
from src.infrastructure.db.session import get_db_context
from src.domain.entities.video_source import VideoSource

logger = logging.getLogger(__name__)


def dlp_download_video(info, output_dir, resolution='1080p'):
    """
    下载单个视频，并将其保存到指定目录。

    :param info: 包含视频信息的字典
    :param output_dir: 视频输出目录
    :param resolution: 分辨率，默认为'1080p'
    :return: 输出目录路径
    """
    # 清理标题中的非法字符
    series = sanitize_title(info.get('series', ""))
    season = sanitize_title(info.get('season', ""))
    title = sanitize_title(info['title'])

    # 准备下载选项
    ydl_opts = {
        'format': f'bestvideo[ext=mp4][height<={resolution}]+bestaudio[ext=m4a]/best[ext=mp4]/best',
        'writeinfojson': False,  # 关闭元数据文件生成
        'writethumbnail': False,  # 关闭缩略图下载
        'outtmpl': os.path.join(output_dir, f"{series}{season}{title}.%(ext)s"),
        'ignoreerrors': True,
        'noplaylist': True,  # 不下载播放列表（仅当前视频）,
        'no_check_certificate': True,  # 跳过 SSL 验证
        'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/136.0.0.0 Safari/537.36',
        **_get_cookie_source(),
    }

    # 执行下载
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        ydl.download([info['webpage_url']])
    return output_dir


def _get_cookie_source():
    """按优先级获取 cookie 来源：cookies.txt > 浏览器 cookie"""
    if os.path.exists("cookies.txt"):
        return {'cookiefile': 'cookies.txt'}
    try:
        return {'cookies_from_browser': ('chrome',)}
    except Exception:
        return {}


def _site_headers(url):
    """根据 URL 返回站点专用请求头"""
    if 'bilibili.com' in url:
        return {'Referer': 'https://www.bilibili.com', 'Origin': 'https://www.bilibili.com'}
    if 'douyin.com' in url:
        return {'Referer': 'https://www.douyin.com/', 'Cookie': 'msToken='}
    return {}


def download_videos_from_url(url, output_dir, resolution='1080p', limit=5, progress_dict=None):
    """
    从给定的URL下载视频（提取信息 + 下载合并为一次调用）。

    :param url: 视频 URL
    :param output_dir: 输出目录
    :param resolution: 目标分辨率，默认为'1080p'
    :param limit: 如果是播放列表，则限制下载的视频数量
    :param progress_dict: 可选 dict，yt-dlp 实时更新下载进度
    :return: (title, duration) 文件名和时长
    """
    ua = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/136.0.0.0 Safari/537.36'

    def _progress_hook(d):
        if progress_dict is None:
            return
        if d['status'] == 'downloading':
            progress_dict['percent'] = d.get('_percent_str', '').strip()
            progress_dict['speed'] = d.get('_speed_str', '').strip()
            progress_dict['eta'] = d.get('_eta_str', '').strip()
            progress_dict['total'] = d.get('_total_bytes_str', '').strip()
        elif d['status'] == 'finished':
            progress_dict['percent'] = '100%'
            progress_dict['speed'] = ''
            progress_dict['eta'] = ''
            progress_dict['total'] = d.get('_total_bytes_str', '').strip()

    site_headers = _site_headers(url)

    ydl_opts = {
        'format': f'bestvideo[ext=mp4][height<={resolution}]+bestaudio[ext=m4a]/best[ext=mp4]/best',
        'dump_single_json': True,
        'playlistend': limit,
        'ignoreerrors': True,
        'noplaylist': True,
        'no_check_certificate': True,
        'user_agent': ua,
        'outtmpl': os.path.join(output_dir, '%(title)s.%(ext)s'),
        'progress_hooks': [_progress_hook],
        **_get_cookie_source(),
    }
    if site_headers:
        ydl_opts['http_headers'] = site_headers

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        result = ydl.extract_info(url, download=True)

    if result is None:
        # 根据站点给出更具体的提示
        if 'douyin.com' in url:
            raise ValueError("抖音视频下载失败：需要登录 Cookie。请在浏览器登录抖音后导出 cookies.txt 放到项目根目录，或关闭 Chrome 后重试。")
        if 'bilibili.com' in url:
            raise ValueError("B站视频下载失败：需要登录 Cookie。请在浏览器登录B站后导出 cookies.txt 放到项目根目录，或关闭 Chrome 后重试。")
        raise ValueError(f"无法获取视频信息，请检查 URL 是否有效: {url}")

    title = sanitize_title(result['title']) + ".mp4"
    return title, result['duration']


# pexels视频下载
def search_videos_pexels(
        search_term: str,
        minimum_duration: int,
):
    """
    minimum_duration：所需的视频方向。当前支持的方向为：
    landscape = "16:9"  video_width, video_height = 1920, 1080
    portrait = "9:16"   video_width, video_height = 1080, 1920
    square = "1:1"      video_width, video_height = 1080, 1080
    """
    video_orientation = "landscape"
    video_width, video_height = 1920, 1080
    api_key = config.video_api_keys
    if not api_key:
        logger.warning("Pexels API key 未配置 (VIDEO_API_KEYS)")
        return []
    headers = {
        "Authorization": api_key,
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36",
    }
    # Build URL
    params = {"query": search_term, "per_page": 20, "orientation": video_orientation}
    query_url = f"https://api.pexels.com/videos/search?{urlencode(params)}"

    proxies = config.proxy if config.proxy else None
    r = requests.get(
        query_url,
        headers=headers,
        proxies={"http": proxies, "https": proxies} if proxies else None,
        timeout=(30, 60),
    )
    response = r.json()
    video_items = []
    if "videos" not in response:
        return video_items
    videos = response["videos"]
    # loop through each video in the result
    for v in videos:
        duration = v["duration"]
        # check if video has desired minimum duration
        if duration < minimum_duration:
            continue
        duration_formatted = time_util.seconds_to_hms(duration)
        video_files = v.get("video_files", [])
        # 选高清文件用于下载，小文件用于预览
        best = None
        preview = None
        fallback = None
        smallest = None
        for video in video_files:
            w = int(video.get("width", 0))
            h = int(video.get("height", 0))
            if w == video_width and h == video_height:
                best = video
            if w >= 1280 and h >= 720 and (fallback is None or w * h > int(fallback.get("width", 0)) * int(fallback.get("height", 0))):
                fallback = video
            if w > 0 and h > 0 and (smallest is None or w * h < int(smallest.get("width", 0)) * int(smallest.get("height", 0))):
                smallest = video
        chosen = best or fallback
        preview = smallest or chosen
        if chosen:
            item = {
                "provider": "pexels",
                "url": chosen["link"],
                "preview_url": preview["link"] if preview else chosen["link"],
                "duration": duration,
                "duration_hms": duration_formatted,
                "search_term": search_term,
                "image": v.get("image", ""),
            }
            video_items.append(item)
    return video_items


# pixabay视频下载
def search_videos_pixabay(
        search_term: str,
        minimum_duration: int
):
    video_width, video_height = 1920, 1080
    api_key = config.pixabay_api_key or config.video_api_keys
    if not api_key:
        logger.warning("Pixabay API key 未配置 (PIXABAY_API_KEY 或 VIDEO_API_KEYS)")
        return []
    params = {
        "q": search_term,
        "video_type": "all",
        "per_page": 50,
        "key": api_key,
        "safesearch": "true",
    }
    query_url = f"https://pixabay.com/api/videos/?{urlencode(params)}"

    proxies = config.proxy if config.proxy else None
    r = requests.get(
        query_url,
        proxies={"http": proxies, "https": proxies} if proxies else None,
        timeout=(30, 60),
    )
    response = r.json()
    video_items = []
    if "hits" not in response:
        return video_items
    videos = response["hits"]
    for v in videos:
        duration = v.get("duration", 0)
        if duration < minimum_duration:
            continue
        duration_formatted = time_util.seconds_to_hms(duration)
        video_files = v.get("videos", {})
        # Pixabay 提供 large/medium/small/tiny 四种分辨率
        best = None
        preview = None
        for quality in ["large", "medium", "small", "tiny"]:
            vf = video_files.get(quality)
            if not vf:
                continue
            w = int(vf.get("width", 0))
            h = int(vf.get("height", 0))
            if best is None or w * h > int(best.get("width", 0)) * int(best.get("height", 0)):
                best = vf
            if preview is None or (w * h < int(preview.get("width", 0)) * int(preview.get("height", 0)) and w > 0):
                preview = vf
        if best:
            # 用 medium 分辨率做预览（太小会模糊）
            preview = video_files.get("small") or video_files.get("tiny") or best
            item = {
                "provider": "pixabay",
                "url": best["url"],
                "preview_url": preview["url"],
                "duration": duration,
                "duration_hms": duration_formatted,
                "search_term": search_term,
                "image": v.get("userImageURL", "") or f"https://i.vimeocdn.com/video/{v.get('picture_id', '')}_640x360.jpg" if v.get("picture_id") else "",
            }
            video_items.append(item)
    return video_items


def search_videos(search_term: str, minimum_duration: int = 3, source: str = None):
    """统一搜索入口，支持 pexels / pixabay / all"""
    source = source or getattr(config, 'video_type', 'pexels')
    results = []

    if source in ('pexels', 'all'):
        try:
            results.extend(search_videos_pexels(search_term, minimum_duration))
        except Exception as e:
            logger.error(f"Pexels 搜索失败: {e}")

    if source in ('pixabay', 'all'):
        try:
            results.extend(search_videos_pixabay(search_term, minimum_duration))
        except Exception as e:
            logger.error(f"Pixabay 搜索失败: {e}")

    return results


def download_video(video_info):
    # 设置保存目录
    save_dir = config.ROOT_DIR_WIN / config.source_videos_dir
    url = video_info['url']
    # search_term = video_info['search_term']
    """下载单个视频到指定目录"""
    # 创建目录（如果不存在）
    os.makedirs(save_dir, exist_ok=True)
    # 从URL提取文件名
    filename = url.split('/')[-1]
    # 发送请求并下载
    response = requests.get(url, stream=True)
    response.raise_for_status()  # 检查请求状态
    filepath = os.path.join(save_dir, filename)
    # 写入文件
    with open(filepath, 'wb') as f:
        for chunk in response.iter_content(chunk_size=8192):
            if chunk:
                f.write(chunk)
    # 保存到数据库
    from src.application.services import ffmpeg_adapter as use_ffmpeg
    video_info_detail = use_ffmpeg.get_video_info(filepath)
    video_data = {
        "video_name": filename,
        "web_path": config.source_videos_dir + filename,
        "local_path": filepath,
        "duration": str(video_info['duration']),
        "duration_hms": video_info["duration_hms"],
    }
    with get_db_context() as db:
        video_obj = VideoSource(
            video_name=video_data["video_name"],
            web_path=video_data["web_path"],
            local_path=video_data["local_path"],
            duration=video_data["duration"],
            duration_hms=video_data["duration_hms"],
        )
        db.add(video_obj)
        db.commit()
        db.refresh(video_obj)
    logger.info(f"已下载：{filename}")
    return True


def keywords_download(keywords):
    logger.info("开始下载任务:")
    for keyword in keywords:
        logger.info(f"关键词:{keyword}")
        video_infos = search_videos_pexels(keyword, 0)
        count = 2
        if len(video_infos) < count:
            logger.warning(f"关键词 '{keyword}' 的视频数量不足 {count} 个（实际 {len(video_infos)} 个），跳过下载")
            continue  # 或改为下载所有可用视频
        # 随机选择？个URL
        video_infos = random.sample(video_infos, count)
        # 执行下载
        for video_info in video_infos:
            try:
                download_video(video_info)
            except Exception as e:
                logger.error(f"video_info：{video_info}，下载异常：{e}")
    logger.info("下载任务完成")
    return True


if __name__ == '__main__':
    # Bilbili Title 奥巴马开学演讲，纯英文字幕
    video_url = 'https://www.bilibili.com/video/BV1Tt411P72Q/'
    download_videos_from_url(video_url)

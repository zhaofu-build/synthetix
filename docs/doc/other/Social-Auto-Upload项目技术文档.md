# Social-Auto-Upload项目技术文档

## 概述

Social-Auto-Upload 是一款由开发者 dreammis 创建的开源社交媒体视频自动化上传工具，旨在解决内容创作者和运营团队面临的多平台重复发布痛点。该项目通过浏览器自动化技术模拟真实用户操作，实现了无需 API 权限的跨平台视频发布功能，覆盖国内抖音、Bilibili、小红书、快手、视频号、百家号以及国际平台 TikTok 等主流平台。

**项目核心价值**：
- **效率提升**：一次配置，多平台同步发布，**节省90%的重复工作时间**
- **智能调度**：支持复杂时间设定，**一次发布可覆盖一周或半个月的视频**
- **零API依赖**：通过浏览器模拟技术绕过平台API限制，**无需申请API密钥**
- **矩阵化管理**：支持多账号并行操作，**单个账号可独立执行任务**，适合机构团队
- **数据安全**：所有操作在本地完成，**敏感数据不上传服务器**，保障账号安全

**项目特点**：
- 开源免费（MIT协议）
- 支持 CLI 和 Web 界面双操作模式
- 基于 Playwright 浏览器自动化框架
- 集成 APScheduler 定时任务系统
- 支持多线程并发处理（开发中）
- 智能处理平台反爬虫机制
- 支持代理设置防封号
- 提供状态监控与失败告警

## 技术架构

![Social-Auto-Upload技术架构图](技术架构图链接)

Social-Auto-Upload 采用 **前后端分离** 的架构设计，通过清晰的模块划分和接口规范实现高可扩展性和易用性。核心组件包括：

### 1. 前端交互层

**技术栈**：Vue3 + FastAPI
- **功能模块**：
  - 提供直观的 Web 操作界面和 CLI 命令行接口
  - 支持视频文件上传与元数据配置
  - 实时监控任务执行状态与进度
  - 自定义任务调度和定时发布
  - 多账号管理和代理配置
  - 任务日志查询与回滚功能

**访问方式**：
- Web 界面：默认通过 `http://localhost:8080` 访问
- CLI 接口：通过 Python 脚本直接调用
- FastAPI API：默认通过 `http://localhost:8000/docs` 访问

**响应式设计**：支持 PC 端和移动端浏览，提供简洁直观的操作界面

### 2. 后端处理层

**技术栈**：Python 3.10+、FastAPI、APScheduler、SQLite
- **核心模块**：
  - **视频处理模块**：负责视频元数据提取、格式适配和预处理
  - **任务调度模块**：基于 APScheduler 实现定时任务管理
  - **账号管理模块**：处理 Cookie 存储、刷新和多账号隔离
  - **代理配置模块**：支持多账号多代理配置
  - **日志记录模块**：使用 SQLite 存储任务执行状态和历史记录
  - **监控告警模块**：集成 Slack/Webhook 实现失败告警

**部署方式**：
- Docker 一键部署（推荐）
- 本地环境部署
- 支持 Windows/macOS/Linux 跨平台运行

**访问方式**：
- Web 界面通过 REST API 调用后端功能
- CLI 脚本直接调用后端处理逻辑

### 3. 自动化引擎层

**核心技术**：Playwright + Python
- **功能模块**：
  - **浏览器实例管理**：管理铬浏览器等实例
  - **平台适配器**：为每个平台实现独立的 Uploader 模块
  - **任务执行器**：并行执行多个平台的上传任务
  - **异常处理器**：处理平台反爬虫和登录失效问题
  - **进度监控器**：实时监控任务执行进度

**技术特点**：
- **无痕上传**：模拟真实用户操作，避开平台反机器人检测机制
- **多线程优化**：支持多账号并行处理，提高上传效率
- **代理支持**：支持海外平台代理设置（SOCKS5/HTTP）
- **Cookie管理**：持久化存储登录状态，支持自动刷新

### 4. 平台适配层

**技术栈**：Python、Playwright
- **功能模块**：
  - **平台 Uploader 模块**：每个平台对应一个独立的 Uploader 类（如 `DouyinUploader`）
  - **动态元素定位**：处理平台页面元素随机化问题
  - **多平台同步**：实现一键多平台发布功能
  - **失败重试机制**：实现任务失败自动重试

**支持平台**：
- 国内平台：抖音、Bilibili、小红书、快手、视频号、百家号
- 国际平台：TikTok、YouTube（开发中）

## 核心技术实现

### 1. 平台适配技术

Social-Auto-Upload 采用 **模块化平台适配** 设计，通过抽象基类和具体实现类分离公共逻辑和平台特有逻辑：

```python
# 平台适配基类
class BasePlatformUploader:
    async def login(self, cookie_path):
        """抽象登录方法"""
        raise NotImplementedError

    async def upload_video(self, video_path, description, schedule_time):
        """抽象视频上传方法"""
        raise NotImplementedError

    async def generate_description(self, base_description):
        """抽象描述生成方法"""
        return base_description
```

**抖音平台适配实现**（处理动态元素定位问题）：

```python
# 抖音平台适配器
class DouyinUploader(BasePlatformUploader):
    async def login(self, cookie_path):
        # 登录实现
        ...

    async def upload_video(self, video_path, description, schedule_time):
        # 处理动态元素定位
        page = await self浏览器.new_page()
        await page.goto('https://www.douyin.com/ creator')

        # 抖音前端实现，诸多css class id 均为随机数
        # 故项目中locator多采用相对定位，而非固定定位
        await page.locator('button >> text="发布"').click()  # 通过文本内容定位

        # 等待上传页面加载
        await page.wait_for_load_state(timeout=10000)
        ...

    async def generate_description(self, base_description):
        # 适配抖音的描述格式
        return f"{base_description} #抖音挑战 #热门话题"
```

**技术优势**：
- **零API依赖**：完全通过浏览器操作实现，无需申请API权限
- **动态元素定位**：通过相对路径/XPath和文本匹配避开随机化CSS类
- **模块化设计**：新增平台只需继承基类并实现特有方法，扩展性强
- **代理支持**：通过 Playwright 的 `launch` 参数注入代理

### 2. 多线程任务调度

项目通过 **线程池** 实现多账号并行处理，同时通过配置参数控制并发规模，避免触发平台风控机制：

```python
# 多线程任务调度器
from concurrent.futures import ThreadPoolExecutor
import random
import time

class MatrixUploadManager:
    def __init__(self):
        self.config = {
            "max_concurrent_uploads": 3,  # 最大并发上传数
            "retry_attempts": 3,          # 失败重试次数
            "delay_between_uploads": 60  # 平台间延迟（秒）
        }

        # 初始化线程池
        self.executor = ThreadPoolExecutor(max_workers=self.config["max_concurrent_uploads"])

    async def execute_task(self, platform, video_path, description, schedule_time):
        """执行单个平台上传任务"""
        # 获取对应平台的 Uploader
        if platform == 'douyin':
            upstreamer = DouyinUploader
        elif platform == 'tiktok':
            upstreamer = TiktokUploader
        # ...其他平台

        # 随机延迟避免被识别为自动化工具
        time.sleep(random.uniform(1, self.config["delay_between_uploads"]))

        try:
            # 获取对应平台的 Cookie
            cookie_path = f'cookies/{platform}_{account}.json'

            # 执行上传
            result = await upstreamer.upload_video(video_path, description, schedule_time)
            return result
        except Exception as e:
            # 处理异常并重试
            if self.config["retry_attempts"] > 0:
                self.config["retry_attempts"] -= 1
                return await self.execute_task(platform, video_path, description, schedule_time)
            raise e
```

**技术特点**：
- **资源隔离**：每个账号使用独立线程，避免互相干扰
- **随机延迟**：通过 `time.sleep` 添加随机间隔，降低被平台检测风险
- **并发控制**：通过 `max_concurrent_uploads` 限制最大并发数，避免触发风控
- **失败重试**：设置 `retry_attempts` 实现任务失败自动重试

### 3. 定时发布机制

项目基于 **APScheduler** 实现复杂的定时发布功能，支持 Cron 表达式和预设时间段：

```python
# 定时发布核心实现
from apscheduler.schedulers.blocking import BlockingScheduler
import sqlite3

class ScheduleManager:
    def __init__(self):
        # 初始化调度器
        self.scheduler = BlockingScheduler()
        # 初始化数据库
        self连接 = sqlite3.connect('upload_schedule.db')
        self.游标 = self连接.cursor()

        # 创建任务表
        self.游标.execute('''
            CREATE TABLE IF NOT EXISTS tasks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                platform TEXT NOT NULL,
                account TEXT NOT NULL,
                video_path TEXT NOT NULL,
                description TEXT,
                schedule_time TEXT NOT NULL,
                status TEXT DEFAULT 'pending',
                retry_count INTEGER DEFAULT 0
            )
        ''')
        self.连接.commit()

    def add_schedule(self, platform, account, video_path, description, schedule_time):
        """添加定时发布任务"""
        # 将任务存入数据库
        self.游标.execute('''
            INSERT INTO tasks (platform, account, video_path, description, schedule_time)
            VALUES (?, ?, ?, ?, ?)
        ''', (platform, account, video_path, description, schedule_time))

        # 从数据库读取任务并注册到调度器
        self connection.commit()
        task_id = self.游标.lastrowid

        # 解析 schedule_time 为 Cron 表达式
        cron_expression = self._convert_time_to_cron(schedule_time)

        # 注册任务
        self scheduler.add_job(
            self._executeScheduledTask,
            'cron',
            hour=cron_expression.split(' ')[2],
            minute=cron_expression.split(' ')[1],
            second=cron_expression.split(' ')[0],
            args=(task_id,)
        )

    def _convert_time_to_cron(self, schedule_time):
        """将 schedule_time 转换为 Cron 表达式"""
        # 实现时间到 Cron 表达式的转换逻辑
        # 例如：将 "2026-04-24 19:30:00" 转换为 "00 30 19 * * ?"
        return cron_expression

    async def _executeScheduledTask(self, task_id):
        """执行定时发布任务"""
        # 从数据库获取任务详情
        self.游标.execute('SELECT * FROM tasks WHERE id=?', (task_id,))
        task = self.游标.fetchall()[0]

        try:
            # 执行上传任务
            await MatrixUploadManager.execute_task(
                task['platform'],
                task['video_path'],
                task['description'],
                task['schedule_time']
            )

            # 更新任务状态
            self.游标.execute('UPDATE tasks SET status=? WHERE id=?', ('success', task_id))
            self.连接.commit()

            # 发送成功通知
            self._send_alert(f'视频 {task["video_path"]} 在 {task["schedule_time"]} 成功上传至 {task["platform"]}')
        except Exception as e:
            # 更新任务状态
            self.游标.execute('UPDATE tasks SET status=?, retry_count=? WHERE id=?',
                     ('failed', task['retry_count'] + 1, task_id))
            self.连接.commit()

            # 发送失败通知
            self._send_alert(f'视频 {task["video_path"]} 在 {task["schedule_time"]} 上传至 {task["platform"]} 失败: {str(e)}')

            # 如果重试次数未用完，重新注册任务
            if task['retry_count'] < 3:  # 假设最大重试3次
                self scheduler.add_job(
                    self._executeScheduledTask,
                    'cron',
                    hour=cron_expression.split(' ')[2],
                    minute=cron_expression.split(' ')[1],
                    second=cron_expression.split(' ')[0],
                    args=(task_id,)
                )
```

**技术特点**：
- **Cron 表达式支持**：支持复杂时间设定，如"工作日18:00-20:00每30分钟"
- **任务持久化**：通过 SQLite 数据库存储任务，服务重启后任务不丢失
- **失败重试**：设置最大重试次数，避免任务永久失败
- **状态监控**：实时记录任务状态，支持历史回溯

### 4. 代理配置与反反爬虫策略

项目通过 **多代理配置** 和 **反反爬虫策略** 确保账号安全和上传稳定性：

```python
# 代理配置管理器
class ProxyManager:
    def __init__(self):
        # 从配置文件读取代理列表
        with open('config.yml', 'r') as f:
            config = yaml.load(f, Loader=yaml安全加载器)
            self.proxies = config.get('proxies', [])

    def get_proxy(self, account):
        """根据账号获取对应代理"""
        # 实现代理轮换逻辑
        # 可以是随机选择、按账号分配或按平台分配
        return proxy_config

# Playwright 浏览器实例创建（带代理）
def create BrowserWithProxy account, video_path):
    """创建带代理的浏览器实例"""
    proxy_config = ProxyManager().get_proxy(account)

    # 创建浏览器实例并注入代理
    browser = playwright.chromium.launch(
        proxy=proxy_config,
        headless=True
    )

    return browser
```

**反反爬虫技术**：
- **Cookie 自动刷新**：定期检查 Cookie 有效性，失效时自动重新获取
- **DOM 监控**：注入 JavaScript 监控 DOM 变化，确保操作稳定
- **随机行为**：添加随机点击、滚动和等待时间，模拟真人操作
- **IP 轮换**：通过代理配置实现 IP 轮换，避免单 IP 高频触发风控

### 5. 视频元数据处理

项目通过 **本地文本文件** 自动提取视频元数据，确保多平台内容一致性：

```python
# 元数据处理函数
def process metadata File(video_name):
    """从本地文本文件提取视频元数据"""
    try:
        # 寻找对应的元数据文件
        meta_file = None
        for extension in ['txt', 'md', 'json']:
            file_path = os.path.join(' videos', f'{video_name}.{extension}')
            if os.path.exists(file_path):
                meta_file = file_path
                break

        # 如果没有元数据文件，返回空值
        if not meta_file:
            return {}, []

        # 根据文件类型读取内容
        if meta_file.endswith('.txt'):
            with open(meta_file, 'r', encoding='utf-8') as f:
                lines = f.read().splitlines()
                title = lines[0] if lines else ''
                tags = [tag.strip('#') for tag in lines[1:] if tag.startswith('#')]
                return {'title': title}, tags

        elif meta_file.endswith('.json'):
            # 解析 JSON 格式元数据
            ...

        # 其他格式处理...
    except Exception as e:
        # 处理异常并记录日志
        ...
        return {}, []
```

**技术特点**：
- **多格式支持**：支持 .txt、.md、.json 等多种元数据格式
- **平台适配**：根据平台特性自动调整标题和标签格式
- **批量处理**：支持批量视频顺序发布，一次配置处理多个视频
- **失败回滚**：自动检测上传失败并回滚，保留已处理视频的元数据

## 视频上传/发布全流程逻辑

Social-Auto-Upload 的视频上传流程可分为五个主要阶段：**账号准备**、**视频配置**、**任务调度**、**自动执行**和**结果反馈**。整个流程高度自动化，用户只需提供视频文件和基础配置即可完成多平台发布。

### 1. 账号准备阶段

**核心逻辑**：
1. **获取平台 Cookie**：通过扫码登录方式获取各平台账号的登录凭证
   - 运行 `python examples/get_douyin_cookie.py` 获取抖音 Cookie
   - 运行 `python examples/get_xiaohongshu_cookie.py` 获取小红书 Cookie
   - 其他平台类似

2. **Cookie 存储**：将获取的 Cookie 存储在 `cookies/` 目录，每个账号独立文件
   - 文件名格式：`平台名_账号名.json`
   - 支持自动刷新机制，定期检查 Cookie 有效性

3. **代理配置**：为需要的账号配置代理设置
   - 在 `config.yml` 中添加代理列表
   - 支持随机代理选择和按账号固定代理

**技术实现**：
- **扫码登录**：通过 Playwright 打开登录页面并生成 QR 码
- **Cookie 自动化**：自动捕获并存储登录状态，支持长期有效
- **代理注入**：通过 `playwright launch` 参数注入代理配置

### 2. 视频配置阶段

**核心逻辑**：
1. **视频文件准备**：将视频文件放入 `videos/` 目录
   - 支持格式：MP4、MOV、AVI、WebM 等
   - 文件命名建议：包含日期和简要描述（如 `2026-04-24_16-29-52 - 这位勇敢的男子为了心爱之人每天坚守 .mp4`）

2. **元数据文件创建**：为每个视频创建对应的元数据文件
   - 文件格式：与视频同名的 .txt 或 .json 文件
   - 内容结构：
     ```
     这位勇敢的男子为了心爱之人每天坚守 🥺❤️🩹
     #坚持不懈 #爱情执着 #奋斗使者 #短视频
     ```

3. **封面图准备**：可选创建同名封面图片（如 `video1.png`）
   - 自动适配各平台封面尺寸要求
   - 支持动态调整和自定义

**技术实现**：
- **元数据解析**：自动提取标题和标签，支持多格式
- **封面图处理**：自动调整尺寸和格式以适应不同平台
- **批量处理**：支持批量视频顺序发布，一次配置处理多个视频

### 3. 任务调度阶段

**核心逻辑**：
1. **任务创建**：通过 CLI 或 Web 界面创建上传任务
   - 支持单次上传和批量上传
   - 支持单账号和多账号矩阵化上传

2. **定时设置**：为任务设置发布时间
   - 支持 Cron 表达式（如 `0 30 19 * * ?` 表示每天19:30:30）
   - 支持预设时间段（如"工作日18:00-20:00"）

3. **任务持久化**：将任务存入 SQLite 数据库
   - 字段包括：`task_id`, `platform`, `account`, `video_path`, `description`, `schedule_time`, `status`, `retry_count` 等
   - 支持任务状态查询和历史回溯

**技术实现**：
- **APScheduler 集成**：通过 CronTrigger 解析表达式
- **数据库操作**：使用 SQLite 管理任务生命周期
- **Web 界面**：提供直观的调度界面和 REST API

### 4. 自动执行阶段

**核心逻辑**：
1. **任务获取**：从数据库或队列中获取待执行任务
2. **账号选择**：根据任务选择对应的账号和代理
3. **浏览器实例创建**：启动带代理的浏览器
4. **平台登录**：通过 Cookie 登录目标平台
5. **视频上传**：模拟用户操作上传视频
6. **元数据填充**：自动填充标题、标签和描述
7. **发布时间设置**：设置视频发布时间
8. **任务完成**：关闭浏览器实例，更新任务状态

**技术实现**：
- **Playwright 自动化**：模拟用户点击、输入和等待
- **动态元素处理**：处理平台页面元素随机化问题
- **异常处理**：捕获并处理上传过程中的异常
- **进度监控**：实时记录上传进度，支持 Web 界面查询

### 5. 结果反馈阶段

**核心逻辑**：
1. **状态更新**：更新任务状态到数据库
2. **通知发送**：通过配置方式发送成功或失败通知
3. **日志记录**：记录详细操作日志，便于排查问题
4. **结果统计**：统计各平台上传成功率和耗时

**技术实现**：
- **状态监控**：实时记录任务状态和进度
- **通知集成**：支持 Slack/Webhook 邮件等多种通知方式
- **日志系统**：使用结构化日志记录操作细节
- **统计分析**：通过 Web 界面提供上传成功率和耗时统计

## 业务场景与应用价值

### 1. 核心应用场景

#### 1.1 个人创作者

**典型场景**：
- **短视频UP主**：周末批量准备一周视频，周一早晨一次性上传所有平台
- **YouTuber**：自动生成多语言字幕，降低国际化内容制作成本
- **Vlog博主**：自动整理长视频中的精彩片段，生成精华集并同步发布

**应用价值**：
- **节省时间**：**从手动上传的5-10小时减少到几分钟**
- **提高一致性**：确保各平台内容格式统一，提升专业形象
- **优化发布时间**：根据各平台用户活跃时段设置发布时间，最大化曝光率
- **降低学习成本**：无需掌握各平台 API，只需基础操作即可完成多平台发布

#### 1.2 企业营销团队

**典型场景**：
- **MCN 机构**：管理数百个账号的矩阵化内容分发，实现规模化运营
- **品牌推广**：同步发布产品宣传视频到多个平台，统一品牌形象
- **活动策划**：为节日或促销活动设置系列视频的定时发布

**应用价值**：
- **提升运营效率**：**支持批量上传数百个视频**，显著提高运营效率
- **扩大覆盖范围**：触达不同平台的用户群体，提升品牌曝光
- **降低人力成本**：**节省80%的时间**，释放人力资源专注于内容创作
- **统一发布节奏**：确保所有账号在相同时间段发布内容，形成传播合力

#### 1.3 跨境电商团队

**典型场景**：
- **海外平台运营**：通过代理配置支持 TikTok 等国际平台
- **多语言内容发布**：为不同市场定制视频标题和标签
- **合规性管理**：确保内容符合各平台政策要求

**应用价值**：
- **突破地域限制**：通过代理配置实现海外平台的无障碍访问
- **本地化内容适配**：根据平台特点自动调整内容格式，提升本地化效果
- **降低文化差异风险**：避免因不熟悉不同平台文化而发布的不当内容
- **提高跨国运营效率**：实现全球市场的统一内容分发策略

### 2. 扩展应用场景

#### 2.1 教育领域

**典型场景**：
- **在线教育平台**：批量处理教学视频，生成标准化字幕并同步发布
- **学术讲座**：自动整理学术讲座内容，生成适合不同平台的片段

**应用价值**：
- **提升教学效果**：通过多平台发布扩大课程影响力，提高学习参与度
- **降低制作成本**：自动处理视频元数据，减少人工编辑工作量
- **提高更新频率**：支持定期更新教育内容，保持平台活跃度

#### 2.2 政务宣传

**典型场景**：
- **政策解读**：将政策解读视频同步发布到抖音、微信视频号和百家号等平台
- **公共服务**：将便民服务指南视频同步发布到各平台，提高传播效率

**应用价值**：
- **扩大政策覆盖面**：触达不同平台的用户群体，提高政策知晓度
- **提高公共服务效率**：通过多平台同步发布，扩大信息传播范围
- **降低运营复杂度**：简化多平台发布流程，提高政务宣传效率

#### 2.3 健康科普

**典型场景**：
- **健康知识传播**：将健康科普视频同步发布到各平台，提高公众健康意识
- **疾病预防宣传**：针对特定疾病制作预防宣传视频并同步发布

**应用价值**：
- **提高健康信息传播效率**：通过多平台发布扩大健康科普覆盖面
- **降低制作门槛**：自动处理视频元数据，减少专业制作要求
- **提高公众健康意识**：通过精准内容分发，提升健康科普效果

### 3. 应用价值分析

**效率提升**：
- **传统方式**：手动上传每个平台需1-2小时，7个平台需7-14小时
- **Social-Auto-Upload 方式**：**一键多平台发布仅需几分钟**，**效率提升超过90%**
- **批量处理**：支持一次上传数百个视频，**适合 MCN 机构和 KOL 团队**

**成本节约**：
- **零订阅费用**：完全免费使用，无需支付第三方工具订阅费
- **本地化处理**：所有计算在本地完成，**无需云端处理费用**
- **人力成本优化**：**节省80%的运营人力**，可将更多资源投入到内容创作中

**数据安全**：
- **本地化存储**：账号信息和 Cookie 本地存储，**避免云端泄露风险**
- **隐私保护**：**敏感数据不上传服务器**，保障账号安全
- **合规性管理**：内置合规性检查，避免违反平台政策

**平台覆盖**：
- **国内主流平台**：覆盖抖音、Bilibili、小红书、快手、视频号、百家号等
- **国际平台**：支持 TikTok，YouTube 正在开发中
- **持续扩展**：开发者社区持续贡献新平台支持

**ROI 量化**：
- **时间成本**：**节省90%的重复工作时间**，显著提高工作效率
- **曝光提升**：**多平台发布可提升曝光率2-3倍**
- **流量增长**：MCN 机构实测流量和收益"直接爆表"
- **投资回报**：一次性部署，长期免费使用，ROI 极高

### 4. 典型业务案例

#### 案例1：MCN 机构的批量内容分发

**场景**：某 MCN 机构需要为旗下 100 个抖音账号同步发布最新一期短视频节目。

**传统方案**：
- 每个账号需单独登录并上传视频
- 手动设置发布时间和元数据
- 需要大量人力和长时间投入
- 上传失败率高，难以及时发现和处理

**Social-Auto-Upload 方案**：
- 通过 CLI 批量创建任务：`python cli_main.py batchupload all_accounts.txt`
- 系统自动处理账号登录和视频上传
- 实时监控上传进度和状态，失败任务自动重试
- 次日早晨，所有账号视频在预设时间同步发布
- **一个编辑人员可同时处理100+个账号**，大幅提高工作效率
- 系统自动生成上传报表并发送到邮箱，便于数据分析和优化

#### 案例2：跨境电商的多平台同步发布

**场景**：某跨境电商需要同时在抖音、小红书、视频号和 TikTok 等平台发布新品介绍视频。

**传统方案**：
- 需要处理不同平台的账号登录和视频上传
- 手动调整视频格式和元数据以适应各平台要求
- 为不同市场制作多语言版本，增加工作量
- 海外平台访问困难，需额外技术支持

**Social-Auto-Upload 方案**：
- 通过 CLI 批量创建多平台任务：`python cli_main.py multipupload new_product.mp4`
- 系统自动根据平台特点调整视频格式和元数据
- 为不同市场自动生成多语言版本（需集成翻译API）
- 通过代理配置实现 TikTok 等国际平台无障碍访问
- 按各平台用户活跃时段设置发布时间，最大化曝光
- **实现"一次制作，多平台发布"的高效运营模式**
- 系统监控上传状态，确保所有平台内容按时发布

#### 案例3：教育机构的课程视频分发

**场景**：某在线教育平台需要将最新课程视频发布到多个学习社区和视频平台。

**传统方案**：
- 需要熟悉各平台的上传流程和规则
- 手动调整视频标题和标签以适应不同平台用户偏好
- 课程视频较长，需手动剪辑为适合各平台的短片段
- 上传时间不统一，影响学习者的观看体验

**Social-Auto-Upload 方案**：
- 通过 CLI 创建定时发布任务：`python cli_main.py scheduleupload course.mp4 "每周一上午9点"`
- 系统自动根据平台特点剪辑视频为合适长度
- 为每个平台生成适配的标题和标签（如 B站使用番剧编号，小红书使用热门话题标签）
- **确保所有平台在同一时间发布相同内容**，提高学习者的观看体验
- 系统监控上传状态，失败任务自动重试
- **实现"一次制作，多平台同步"的高效教育内容分发**

## 部署与使用指南

### 1. 在线部署（推荐新手）

**环境要求**：
- 现代浏览器（Chrome/Firefox/Edge 85+或Safari 14+）
- 稳定的网络连接（用于首次模型下载）
- GitHub 账号（用于克隆仓库）

**部署步骤**：
```bash
# 1. 克隆项目仓库
git clone https://github.com/dreammis/social-auto-upload.git
cd social-auto-upload

# 2. 安装依赖
pip install -r requirements.txt
playwright install chromium firefox

# 3. 配置环境
# 生成配置文件
cp config.yml.example config.yml
# 编辑 config.yml 配置代理和账号信息

# 4. 准备账号凭证
# 为每个平台账号获取 Cookie
python examples/get_douyin_cookie.py  # 抖音
python examples/get_xiaohongshu_cookie.py  # 小红书
# 其他平台类似

# 5. 准备视频文件
# 在 videos/ 目录下创建视频文件和元数据文件
# 视频文件：video1.mp4
# 元数据文件：video1.txt（或 video1.json）
# 封面图（可选）：video1.png

# 6. 启动服务
# Web 界面模式
docker-compose up -d

# 或 CLI 模式
python cli_main.py
```

**在线版限制**：
- 首次使用需下载模型（约200-500MB）
- 需要稳定的网络连接（模型下载和更新）
- 文件大小可能受限（通常不超过500MB）
- 处理大型视频可能需要较长时间

### 2. 本地部署（推荐高级用户）

**环境要求**：
- Python 3.10+ 版本
- Node.js v16+（用于 Playwright）
- Docker（可选，用于容器化部署）
- 现代浏览器（Chrome/Firefox/Edge 85+或Safari 14+）

**部署步骤**：
```bash
# 1. 克隆项目仓库
git clone https://github.com/dreammis/social-auto-upload.git
cd social-auto-upload

# 2. 安装依赖
pip install -r requirements.txt
playwright install chromium firefox

# 3. 配置环境
# 编辑 config.yml 配置代理和账号信息
# 设置LOCAL_CHROME_PATH（可选，用于解决某些平台兼容性问题）

# 4. 准备账号凭证
# 为每个平台账号获取 Cookie
python examples/get_douyin_cookie.py  # 抖音
python examples/get_xiaohongshu_cookie.py  # 小红书
# 其他平台类似

# 5. 准备视频文件
# 在 videos/ 目录下创建视频文件和元数据文件
# 视频文件：video1.mp4
# 元数据文件：video1.txt（或 video1.json）
# 封面图（可选）：video1.png

# 6. 启动服务（Docker 方式）
# 启动完整本地环境
docker-compose up -d

# 7. 访问界面
# Web 界面：http://localhost:8080
# API 文档：http://localhost:8000/docs

# 8. 执行上传任务
# 批量上传到多个平台
python examples/batchupload.py video1.mp4

# 或定时上传
python examples/scheduleupload.py video1.mp4 "2026-04-25 19:30:00"
```

**本地部署优势**：
- 完全控制模型选择和版本
- 无网络依赖，可离线使用
- 支持自定义样式模板和导出设置
- 适合处理大量或大型视频文件
- 支持自定义 API 密钥和模型路径

### 3. 隐私与安全最佳实践

**数据安全策略**：
- **本地化存储**：所有账号信息和 Cookie 存储在本地，**不上传服务器**
- **定期刷新 Cookie**：设置定期刷新计划，避免因平台策略变化导致失效
- **代理轮换**：配置多代理并定期轮换，降低账号风险
- **权限隔离**：为不同账号分配不同权限，限制敏感操作
- **监控告警**：设置失败告警，及时发现和处理上传问题

**安全建议**：
- **定期更新代码**：获取最新安全补丁和平台适配
- **避免高并发**：合理设置并发数，避免触发平台风控
- **遵守平台政策**：确保内容符合各平台规定，避免违规
- **备份配置文件**：定期备份账号信息和配置文件，防止丢失
- **使用专用设备**：建议在专用设备上运行，避免与其他高风险应用共用

### 4. 性能优化建议

**处理大型视频**：
- **分段处理**：对于超过30分钟的视频，建议分段处理
- **代理文件**：使用 `--proxy_scale 0.5` 参数生成代理文件提高处理速度
- **多线程配置**：在 `config.yml` 中调整 `max_concurrent_uploads` 参数
- **代理优化**：为不同账号配置不同代理 IP，提高成功率

**提高上传成功率**：
- **定期刷新 Cookie**：设置每周刷新计划，确保登录状态有效
- **合理配置并发**：避免过高并发导致账号被封
- **使用随机延迟**：通过 `delay_between_uploads` 参数设置随机延迟
- **监控上传状态**：及时发现并处理上传失败

**导出优化**：
- **分块导出**：大型视频可分块导出，再通过专业软件合成
- **多平台适配**：为不同平台准备适配的视频格式和元数据
- **失败重试**：设置合理的 `retry_attempts` 和 `retry_delay` 参数
- **监控系统资源**：避免因资源耗尽导致任务失败

## 技术实现细节

### 1. Playwright 自动化实现

**核心优势**：
- **跨浏览器支持**：支持 Chromium、Firefox 和 WebKit 浏览器
- **无痕操作**：模拟真实用户行为，难以被平台检测为自动化工具
- **高效稳定**：相比 Selenium，Playwright 提供更高效和稳定的浏览器控制
- **强大的 DOM 控制**：支持复杂页面操作和元素定位

**典型操作流程**（以抖音为例）：
1. 启动浏览器实例：`browser = playwright.chromium.launch()`
2. 创建新页面：`page = await browser.new_page()`
3. 打开登录页面：`await page.goto('https://www.douyin.com/ creator')`
4. 登录：`await page.set Cookie from_file('cookies/douyin.json')`
5. 进入上传页面：`await page.goto('https://www.douyin.com/ creator/upload')`
6. 上传视频：`await page.locator('input[type="file"]').upload_file('video.mp4')`
7. 填写元数据：`await page.locator('textarea').fill('视频标题\n#标签1 #标签2')`
8. 设置发布时间：`await page.locator('button >> text="定时发布"').click()`
9. 选择时间：`await page.locator('div >> text="2026-04-25 19:30"').click()`
10. 提交发布：`await page.locator('button >> text="发布"').click()`
11. 关闭浏览器：`await browser.close()`

### 2. 账号矩阵化管理

**核心实现**：
- **Cookie 存储**：每个账号的 Cookie 存储在独立文件中
- **多线程隔离**：每个账号任务在独立线程中执行
- **代理配置**：支持为不同账号配置不同代理
- **失败隔离**：一个账号失败不影响其他账号

**实现代码片段**：
```python
# 账号管理器
class AccountManager:
    def __init__(self):
        self accounts = {}
        self proxies = {}
        self cookies = {}

    def load Accounts(self):
        """加载所有账号信息"""
        # 加载抖音账号
        self _load Accounts('douyin')

        # 加载小红书账号
        self _load Accounts('xiaohongshu')

        # 其他平台类似

    def _load Accounts(self, platform):
        """加载特定平台账号"""
        account_dir = f'cookies/{platform}'
        if not os.path.exists(account_dir):
            return

        for file in os.listdir(account_dir):
            if file.endswith('.json'):
                account_name = file.split('.')[0]
                cookie_path = os.path.join(account_dir, file)

                # 存储账号信息
                self accounts[account_name] = {
                    'platform': platform,
                    'cookie_path': cookie_path,
                    'proxy': self _get Proxy For Account平台, account_name)
                }

    def _get Proxy For Account(self, platform, account_name):
        """获取账号对应的代理"""
        # 从配置文件中获取代理配置
        # 可以是随机选择、按账号分配或按平台分配
        ...
```

**技术特点**：
- **灵活代理配置**：支持为不同账号分配不同代理
- **自动账号选择**：根据任务需求自动选择最佳账号
- **失败自动隔离**：上传失败的账号自动标记为不可用，避免影响其他账号
- **任务负载均衡**：自动平衡不同账号的任务量，提高整体效率

### 3. 定时发布与任务调度

**核心实现**：
- **Cron 表达式解析**：支持复杂时间设定
- **任务持久化**：通过 SQLite 存储任务状态
- **多平台适配**：为不同平台设置最佳发布时间
- **失败重试**：支持任务失败自动重试

**实现代码片段**：
```python
# 定时发布核心逻辑
from apscheduler.schedulers.blocking import BlockingScheduler
import sqlite3

class ScheduleManager:
    def __init__(self):
        # 初始化调度器
        self scheduler = BlockingScheduler()
        # 初始化数据库
        self connection = sqlite3.connect('upload_schedule.db')
        self cursor = self connection.cursor()

        # 创建任务表
        self cursor.execute('''
            CREATE TABLE IF NOT EXISTS tasks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                platform TEXT NOT NULL,
                account TEXT NOT NULL,
                video_path TEXT NOT NULL,
                description TEXT,
                schedule_time TEXT NOT NULL,
                status TEXT DEFAULT 'pending',
                retry_count INTEGER DEFAULT 0
            )
        ''')
        self connection.commit()

    def add Schedule(self, platform, account, video_path, description, schedule_time):
        """添加定时发布任务"""
        # 将任务存入数据库
        self cursor.execute('''
            INSERT INTO tasks (platform, account, video_path, description, schedule_time)
            VALUES (?, ?, ?, ?, ?)
        ''', (platform, account, video_path, description, schedule_time))

        # 从数据库读取任务并注册到调度器
        self connection.commit()
        task_id = self cursor.lastrowid

        # 解析 schedule_time 为 Cron 表达式
        cron_expression = self._convert Time To Cron(schedule_time)

        # 注册任务
        self scheduler.add_job(
            self._execute Scheduled Task,
            'cron',
            hour=cron_expression.split(' ')[2],
            minute=cron_expression.split(' ')[1],
            second=cron_expression.split(' ')[0],
            args=(task_id,)
        )

    def _convert Time To Cron(self, schedule_time):
        """将 schedule_time 转换为 Cron 表达式"""
        # 实现时间到 Cron 表达式的转换逻辑
        # 例如：将 "2026-04-25 19:30:00" 转换为 "00 30 19 * * ?"
        return cron_expression

    async def _execute Scheduled Task(self, task_id):
        """执行定时发布任务"""
        # 从数据库获取任务详情
        self cursor.execute('SELECT * FROM tasks WHERE id=?', (task_id,))
        task = self cursor.fetchall()[0]

        try:
            # 执行上传任务
            await MatrixUploadManager.execute_task(
                task['platform'],
                task['account'],
                task['video_path'],
                task['description']
            )

            # 更新任务状态
            self cursor.execute('UPDATE tasks SET status=? WHERE id=?', ('success', task_id))
            self connection.commit()

            # 发送成功通知
            self._send Alert(f'视频 {task["video_path"]} 在 {task["schedule_time"]} 成功上传至 {task["platform"]}')
        except Exception as e:
            # 更新任务状态
            self cursor.execute('UPDATE tasks SET status=?, retry_count=? WHERE id=?',
                     ('failed', task['retry_count'] + 1, task_id))
            self connection.commit()

            # 发送失败通知
            self._send Alert(f'视频 {task["video_path"]} 在 {task["schedule_time"]} 上传至 {task["platform"]} 失败: {str(e)}')

            # 如果重试次数未用完，重新注册任务
            if task['retry_count'] < 3:  # 假设最大重试3次
                self scheduler.add_job(
                    self._execute Scheduled Task,
                    'cron',
                    hour=cron_expression.split(' ')[2],
                    minute=cron_expression.split(' ')[1],
                    second=cron_expression.split(' ')[0],
                    args=(task_id,)
                )
```

**技术特点**：
- **灵活时间配置**：支持精确到秒的定时发布
- **任务持久化**：服务重启后任务不丢失，状态可查询
- **失败自动重试**：设置最大重试次数，提高上传成功率
- **多平台差异化**：为不同平台设置最佳发布时间，最大化曝光

### 4. 多平台适配与扩展

**核心实现**：
- **抽象基类**：`BasePlatformUploader` 定义公共方法
- **具体实现**：每个平台有独立的 Uploader 类（如 `DouyinUploader`）
- **动态元素处理**：通过相对路径/XPath和文本匹配定位元素
- **平台差异处理**：为不同平台实现特定的上传逻辑

**添加新平台支持示例**：
```python
# 添加新平台 Uploader
from uploader.base_uploader import BasePlatformUploader

class NewPlatformUploader(BasePlatformUploader):
    async def login(self, cookie_path):
        """实现新平台登录逻辑"""
        # 从 cookie_path 加载 Cookie
        ...

    async def upload_video(self, video_path, description, schedule_time):
        """实现新平台视频上传逻辑"""
        # 打开上传页面
        ...

        # 上传视频
        ...

        # 填写元数据
        ...

        # 设置发布时间
        ...

        # 提交发布
        ...

    async def generate_description(self, base_description):
        """为新平台生成适配的描述"""
        # 根据新平台特点调整描述
        return f"{base_description} [新平台话题标签]"
```

**技术特点**：
- **高度可扩展**：新增平台只需继承基类并实现特有方法
- **统一接口**：所有平台通过统一接口调用，简化使用
- **独立配置**：为不同平台设置独立的上传参数和策略
- **持续更新**：开发者社区持续贡献新平台支持

## 开发者指南

### 1. 贡献代码

Social-Auto-Upload 项目欢迎各种形式的贡献，包括但不限于：
- 提交 Bug 报告和 Feature 请求
- 改进代码、文档
- 分享使用经验和教程

**贡献步骤**：
```bash
# 1. Fork 本仓库
git fork https://github.com/dreammis/social-auto-upload.git

# 2. 创建新的分支
git checkout -b feature/YourFeature  # 添加新功能
# 或
git checkout -b bugfix/YourBugfix     # 修复 Bug

# 3. 提交您的更改
git commit -m 'Add support for YouTube'

# 4. Push到您的分支
git push origin feature/YourFeature

# 5. 创建 Pull Request
```

### 2. 问题排查

**常见问题**：
- **Cookie 失效**：定期运行 `python examples/validate_cookie.py 平台 账号` 验证 Cookie 有效性
- **代理问题**：检查代理配置是否正确，尝试更换代理
- **平台更新**：关注 GitHub Issue，及时更新 Uploader 代码
- **上传失败**：查看日志文件，定位具体失败原因

**排查流程**：
1. 检查日志：`tail -f upload.log`（Linux/macOS）或 `type upload.log`（Windows）
2. 验证 Cookie：`python examples/validate_cookie.py 平台 账号`
3. 检查代理：`python examples/test_proxy.py 平台 账号`
4. 手动测试：`python examples/upload_video_to_平台.py 账号 视频路径`
5. 更新代码：`git pull origin main` 并重新安装依赖

### 3. 高级定制

**自定义元数据模板**：
- 在 `config.yml` 中定义各平台的元数据模板
- 使用变量替换技术，如 `{{title}}` 和 `{{tags}}`

**自定义上传策略**：
- 修改 `config.yml` 中的 `max_concurrent_uploads` 和 `retry_attempts` 等参数
- 重写 `generate_description` 方法实现平台特定的元数据处理

**自定义失败处理**：
- 实现自定义的失败处理逻辑
- 集成第三方监控服务（如 Prometheus/Grafana）

### 4. 未来发展方向

**已规划功能**：
- **YouTube 支持**：正在开发中
- **GUI 界面**：简化非技术用户的使用
- **Docker 一键部署**：简化部署流程
- **更强大的代理管理**：支持更多代理类型和配置方式

**潜在扩展方向**：
- **视频剪辑功能**：集成视频剪辑工具，实现从剪辑到发布的全流程自动化
- **智能内容推荐**：基于平台算法推荐最佳发布时间和元数据
- **多语言自动生成**：集成 AI 翻译工具，自动生成多语言版本
- **数据分析与优化**：收集各平台数据，分析并优化发布策略

## 结论

Social-Auto-Upload 通过 **浏览器自动化技术** 和 **模块化设计**，成功解决了多平台视频发布的核心痛点，为内容创作者和运营团队提供了高效、安全、灵活的自动化上传解决方案。项目采用 **Playwright** 作为核心自动化引擎，实现了对主流社交媒体平台的无痕上传，同时通过 **APScheduler** 和 **SQLite** 实现了复杂的定时发布和任务管理功能。

**项目的主要价值在于**：
- **大幅提升效率**：从手动上传的5-10小时减少到几分钟，**效率提升超过90%**
- **降低使用门槛**：零 API 依赖，新手也能快速上手，**无需申请任何API密钥**
- **保障数据安全**：所有操作在本地完成，**敏感数据不上传服务器**
- **支持大规模运营**：通过矩阵化账号管理，**支持数百个账号的批量处理**
- **灵活配置**：支持自定义代理、并发数和重试策略，适应不同运营需求

随着内容创作和分发需求的不断增长，Social-Auto-Upload 的技术架构和实现方式为行业提供了宝贵参考，也为内容创作者和运营团队提供了强大的自动化工具。**项目持续扩展支持的新平台**（如 YouTube）和**不断优化的用户体验**（如 GUI 界面）将进一步扩大其应用范围和价值，成为数字内容分发领域的基础设施级工具。
import os, uvicorn

os.environ['HF_ENDPOINT'] = "https://hf-mirror.com"
os.environ['HF_HOME'] = 'D:/hf-model'
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
import log_config
import config
from api.svc_api import router as api_interface
from api.tool_api import router as api_tool
from api.video_api import router as video_api
from api.llm_clip_api import router as llm_clip_api
from api.video_generation_api import router as video_generation_api

from util import file_util

app = FastAPI()
app.include_router(api_interface)
app.include_router(api_tool)
app.include_router(video_api)
app.include_router(llm_clip_api)
app.include_router(video_generation_api)

# 配置静态文件服务
os.makedirs(config.UPLOAD_DIR, exist_ok=True)
app.mount("/static", StaticFiles(directory="static"), name="static")

# 添加 CORS 中间件
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 允许所有来源
    allow_credentials=True,
    allow_methods=["*"],  # 允许所有方法
    allow_headers=["*"],  # 允许所有头部
)


# 使用 Python 3 提供静态文件服务命令（在dist根目录运行）: python -m http.server 8688

# 启动命令（必须在主类目录下）：uvicorn run_api:app --reload
# 访问地址：http://127.0.0.1:8686
# 自动动生成交互式 API 文档，访问地址： http://127.0.0.1:8686/docs

# 列出已安装包：pip freeze
# 生成一个 requirements.txt，在项目根目录下运行：pipreqs . --use-local --encoding=utf8
# pip install pipreqs
def run():
    # 清除upload_dir
    file_util.clean_upload_dir(config.UPLOAD_DIR)
    # 开启日志配置
    log_config.log_run()
    import logging
    logging.info('------主程序开始运行-------')
    uvicorn.run(app='run_api:app',
                host="127.0.0.1",
                port=config.api_host,
                reload=True,
                access_log=True,  # 开启访问日志
                )


if __name__ == '__main__':
    run()

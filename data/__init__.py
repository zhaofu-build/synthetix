# import os

# 设置huggingface-hub代理

# 代码中设置代理和模型下载路径(需要放在最上面，否则不起作用)
# os.environ['HF_ENDPOINT'] = "https://hf-mirror.com/"
# os.environ['HF_HOME'] = 'D:/hf-model'

# 临时设置
# 在terminal窗口中运行：
# $env:HF_ENDPOINT = "https://hf-mirror.com/"
# $env:HF_HOME = "D:/develop/hf-model"
# 然后在窗口中运行程序即可设置临时代理成功
# .\run_index.py

# 永久设置：
# 打开“控制面板”。
# 选择“系统和安全” > “系统” > “高级系统设置”。
# 在“系统属性”窗口中，点击“环境变量”按钮。
# 在“环境变量”窗口中，找到“用户变量”或“系统变量”部分，然后点击“新建”来创建一个新的环境变量。
# 输入变量名 HF_ENDPOINT 和变量值 https://hf-mirror.com/。
# 点击“确定”保存设置。

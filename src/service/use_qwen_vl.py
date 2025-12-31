from transformers import Qwen3VLForConditionalGeneration, AutoProcessor
from qwen_vl_utils import process_vision_info
from modelscope import snapshot_download
import threading

# 全局模型和处理器变量
_model = None
_processor = None
_model_lock = threading.Lock()  # 模型初始化锁
_min_pixels = 256 * 28 * 28
_max_pixels = 1280 * 28 * 28


def _initialize_model():
    """初始化模型和处理器（线程安全）"""
    global _model, _processor

    if _model is None or _processor is None:
        with _model_lock:
            # 双重检查锁定
            if _model is None or _processor is None:
                # 下载模型（使用缓存避免重复下载）
                model_dir = snapshot_download('Qwen/Qwen3-VL-2B-Instruct', cache_dir='D:/hf-model')
                # model_dir = snapshot_download('Qwen/Qwen2.5-VL-7B-Instruct', cache_dir='D:/hf-model')

                # 初始化模型（自动检测设备）
                _model = Qwen3VLForConditionalGeneration.from_pretrained(
                    model_dir,
                    torch_dtype="auto",
                    device_map="auto"
                    # attn_implementation="flash_attention_2" # 启用flash_attention_2以获得更好的性能（推荐）
                )

                # 初始化处理器
                _processor = AutoProcessor.from_pretrained(
                    model_dir,
                    min_pixels=_min_pixels,
                    max_pixels=_max_pixels
                )


def generate_summary(messages: list):
    """通用生成函数，处理图像/视频并生成描述"""
    # 确保模型已初始化
    _initialize_model()

    # 应用聊天模板处理文本
    text = _processor.apply_chat_template(
        messages, tokenize=False, add_generation_prompt=True
    )

    # 处理视觉信息
    image_inputs, video_inputs = process_vision_info(messages)

    # 准备模型输入
    inputs = _processor(
        text=[text],
        images=image_inputs,
        videos=video_inputs,
        padding=True,
        return_tensors="pt",
    ).to(_model.device)

    # 生成文本
    generated_ids = _model.generate(**inputs, max_new_tokens=512)
    generated_ids_trimmed = [
        out_ids[len(in_ids):]
        for in_ids, out_ids in zip(inputs.input_ids, generated_ids)
    ]

    return _processor.batch_decode(
        generated_ids_trimmed,
        skip_special_tokens=True,
        clean_up_tokenization_spaces=False
    )[0]


def image_summary(tmp_path, prompt):
    """
    图片内容总结接口
    tmp_path：上传的图片文件
    prompt：可选的自定义提示词
    """
    if prompt is None:
        prompt = "用简练的语言描述这张图片"
    messages = [
        {
            "role": "user",
            "content": [
                {"type": "image", "image": tmp_path},
                {"type": "text", "text": prompt}
            ]
        }
    ]
    return generate_summary(messages)


def video_summary(tmp_path, prompt):
    """
    视频内容总结接口
    tmp_path：上传的视频文件
    prompt：可选的自定义提示词
    """
    if prompt is None:
        prompt = "用简练的语言描述这个视频，总结成一句话"
    messages = [
        {
            "role": "user",
            "content": [
                {"type": "video", "video": tmp_path},
                {"type": "text", "text": prompt}
            ]
        }
    ]
    return generate_summary(messages)


if __name__ == '__main__':
    tmp_path = "D:\\aupi\\8.png"
    result = image_summary(tmp_path, None)

    # tmp_path = "E:\\aupi\\2\\dfgdg.mp4"
    # result = video_summary(tmp_path,None)
    print(result)

import config
from fastapi import APIRouter
from src.model.base import BaseReq
import cv2

router = APIRouter()


@router.post("/frame_pack_generate")
async def generate_endpoint(req: BaseReq):
    from src.service.frame_pack import frame_pack_f1

    req_dict = req.dict()
    # 读取图像为numpy数组
    img_array = cv2.imread(req_dict.get("image_path", None))
    # 调用处理函数
    frame_pack_f1.worker(
        input_image=img_array,
        prompt=req_dict.get("prompt", None),
        n_prompt=req_dict.get("n_prompt", ""),
        seed=req_dict.get("seed", 31337),
        total_second_length=req_dict.get("total_second_length", 1),
        latent_window_size=req_dict.get("latent_window_size", 9),
        steps=req_dict.get("steps", 25),  # 默认值
        cfg=req_dict.get("cfg", 1),
        gs=req_dict.get("gs", 10),
        rs=req_dict.get("rs", 0),  # 默认值
        gpu_memory_preservation=req_dict.get("gpu_memory_preservation", 6),
        use_teacache=req_dict.get("use_teacache", True),
        mp4_crf=req_dict.get("mp4_crf", 16)
    )
    access_url_path = config.ROOT_DIR_WIN / config.UPLOAD_DIR / 'generated_latent_frames.mp4'
    return {
        "video_url": 'static/uploads/generated_latent_frames.mp4',
        "local_url": access_url_path
    }


@router.post("/cancel")
async def cancel_generation():
    from src.service.frame_pack import frame_pack_f1
    frame_pack_f1.end_process()
    # 这里实现取消生成逻辑
    return {"status": "cancelled"}

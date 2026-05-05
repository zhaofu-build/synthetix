const flux ={
    "flux_json":{
        "5": {
            "inputs": {
                "width": 1080,
                "height": 1280,
                "batch_size": 1
            },
            "class_type": "EmptyLatentImage",
            "_meta": {
                "title": "空Latent图像"
            }
        },
        "6": {
            "inputs": {
                "text": "Extreme panoramic view, low saturation warm tone, two astronauts standing in the vast waters that flooded their thighs. The people in front waded seriously, and the future aircraft behind them moored on the water. The background is boundless clouds and double suns, and the edge light outlines the outline of the spacesuit, and the balanced composition reproduces the classic of Miller Planet.",
                "clip": [
                    "11",
                    0
                ]
            },
            "class_type": "CLIPTextEncode",
            "_meta": {
                "title": "CLIP文本编码"
            }
        },
        "8": {
            "inputs": {
                "samples": [
                    "30",
                    0
                ],
                "vae": [
                    "10",
                    0
                ]
            },
            "class_type": "VAEDecode",
            "_meta": {
                "title": "VAE解码"
            }
        },
        "9": {
            "inputs": {
                "filename_prefix": "flux",
                "images": [
                    "8",
                    0
                ]
            },
            "class_type": "SaveImage",
            "_meta": {
                "title": "保存图像"
            }
        },
        "10": {
            "inputs": {
                "vae_name": "ae.safetensors"
            },
            "class_type": "VAELoader",
            "_meta": {
                "title": "加载VAE"
            }
        },
        "11": {
            "inputs": {
                "clip_name1": "clip_l.safetensors",
                "clip_name2": "umt5-xxl-enc-bf16.safetensors",
                "type": "flux",
                "device": "default"
            },
            "class_type": "DualCLIPLoader",
            "_meta": {
                "title": "双CLIP加载器"
            }
        },
        "12": {
            "inputs": {
                "unet_name": "flux1-dev-fp8.safetensors",
                "weight_dtype": "fp8_e4m3fn"
            },
            "class_type": "UNETLoader",
            "_meta": {
                "title": "UNet加载器"
            }
        },
        "30": {
            "inputs": {
                "seed": 211027433165818,
                "steps": 20,
                "cfg": 1,
                "sampler_name": "euler",
                "scheduler": "normal",
                "denoise": 1,
                "model": [
                    "12",
                    0
                ],
                "positive": [
                    "6",
                    0
                ],
                "negative": [
                    "31",
                    0
                ],
                "latent_image": [
                    "5",
                    0
                ]
            },
            "class_type": "KSampler",
            "_meta": {
                "title": "K采样器"
            }
        },
        "31": {
            "inputs": {
                "text": "",
                "clip": [
                    "11",
                    0
                ]
            },
            "class_type": "CLIPTextEncode",
            "_meta": {
                "title": "CLIP文本编码"
            }
        }
    },

    "flux_kontext_json":{
        "6": {
            "inputs": {
                "text": "Transform to oil painting with visible brushstrokes, thick paint texture",
                "clip": [
                    "38",
                    0
                ]
            },
            "class_type": "CLIPTextEncode",
            "_meta": {
                "title": "CLIP Text Encode (Positive Prompt)"
            }
        },
        "8": {
            "inputs": {
                "samples": [
                    "31",
                    0
                ],
                "vae": [
                    "39",
                    0
                ]
            },
            "class_type": "VAEDecode",
            "_meta": {
                "title": "VAE解码"
            }
        },
        "31": {
            "inputs": {
                "seed": 345724493977967,
                "steps": 20,
                "cfg": 1,
                "sampler_name": "euler",
                "scheduler": "simple",
                "denoise": 1,
                "model": [
                    "192",
                    0
                ],
                "positive": [
                    "35",
                    0
                ],
                "negative": [
                    "135",
                    0
                ],
                "latent_image": [
                    "124",
                    0
                ]
            },
            "class_type": "KSampler",
            "_meta": {
                "title": "K采样器"
            }
        },
        "35": {
            "inputs": {
                "guidance": 2.5,
                "conditioning": [
                    "177",
                    0
                ]
            },
            "class_type": "FluxGuidance",
            "_meta": {
                "title": "Flux引导"
            }
        },
        "37": {
            "inputs": {
                "unet_name": "flux1-dev-kontext_fp8_scaled.safetensors",
                "weight_dtype": "fp8_e4m3fn"
            },
            "class_type": "UNETLoader",
            "_meta": {
                "title": "UNet加载器"
            }
        },
        "38": {
            "inputs": {
                "clip_name1": "clip_l.safetensors",
                "clip_name2": "umt5-xxl-enc-bf16.safetensors",
                "type": "flux",
                "device": "default"
            },
            "class_type": "DualCLIPLoader",
            "_meta": {
                "title": "双CLIP加载器"
            }
        },
        "39": {
            "inputs": {
                "vae_name": "ae.safetensors"
            },
            "class_type": "VAELoader",
            "_meta": {
                "title": "加载VAE"
            }
        },
        "42": {
            "inputs": {
                "image": [
                    "146",
                    0
                ]
            },
            "class_type": "FluxKontextImageScale",
            "_meta": {
                "title": "FluxKontextImageScale"
            }
        },
        "124": {
            "inputs": {
                "pixels": [
                    "42",
                    0
                ],
                "vae": [
                    "39",
                    0
                ]
            },
            "class_type": "VAEEncode",
            "_meta": {
                "title": "VAE编码"
            }
        },
        "135": {
            "inputs": {
                "conditioning": [
                    "6",
                    0
                ]
            },
            "class_type": "ConditioningZeroOut",
            "_meta": {
                "title": "条件零化"
            }
        },
        "136": {
            "inputs": {
                "filename_prefix": "flux_kontext",
                "images": [
                    "8",
                    0
                ]
            },
            "class_type": "SaveImage",
            "_meta": {
                "title": "保存图像"
            }
        },
        "142": {
            "inputs": {
                "image": "flux_kontext_00011_.png [output]",
                "refresh": "refresh"
            },
            "class_type": "LoadImageOutput",
            "_meta": {
                "title": "加载图像（来自输出）"
            }
        },
        "146": {
            "inputs": {
                "direction": "right",
                "match_image_size": true,
                "spacing_width": 0,
                "spacing_color": "white",
                "image1": [
                    "142",
                    0
                ]
            },
            "class_type": "ImageStitch",
            "_meta": {
                "title": "Image Stitch"
            }
        },
        "173": {
            "inputs": {
                "images": [
                    "42",
                    0
                ]
            },
            "class_type": "PreviewImage",
            "_meta": {
                "title": "预览图像"
            }
        },
        "177": {
            "inputs": {
                "conditioning": [
                    "6",
                    0
                ],
                "latent": [
                    "124",
                    0
                ]
            },
            "class_type": "ReferenceLatent",
            "_meta": {
                "title": "ReferenceLatent"
            }
        },
        "188": {
            "inputs": {
                "width": 1024,
                "height": 1024,
                "batch_size": 1
            },
            "class_type": "EmptySD3LatentImage",
            "_meta": {
                "title": "空Latent图像（SD3）"
            }
        },
        "192": {
            "inputs": {
                "unet_name": "flux1-kontext-dev-Q8_0.gguf"
            },
            "class_type": "UnetLoaderGGUF",
            "_meta": {
                "title": "Unet Loader (GGUF)"
            }
        }
    },

    "ace_step_t2a_song_json":{
        "14": {
            "inputs": {
                "tags": "anime, soft female vocals, kawaii pop, j-pop, childish, piano, guitar, synthesizer, fast, happy, cheerful, lighthearted\t\n",
                "lyrics": "[inst]\n\n[verse]\nふわふわ　おみみが\nゆれるよ　かぜのなか\nきらきら　あおいめ\nみつめる　せかいを\n\n[verse]\nふわふわ　しっぽは\nおおきく　ゆれるよ\nきんいろ　かみのけ\nなびくよ　かぜのなか\n\n[verse]\nコンフィーユーアイの\nまもりびと\nピンクの　セーターで\nえがおを　くれるよ\n\nあおいろ　スカートと\nくろいコート　きんのもよう\nやさしい　ひかりが\nつつむよ　フェネックガール\n\n[verse]\nふわふわ　おみみで\nきこえる　こころの　こえ\nだいすき　フェネックガール\nいつでも　そばにいるよ\n\n\n",
                "lyrics_strength": 0.9900000000000002,
                "clip": [
                    "40",
                    1
                ]
            },
            "class_type": "TextEncodeAceStepAudio",
            "_meta": {
                "title": "TextEncodeAceStepAudio"
            }
        },
        "17": {
            "inputs": {
                "seconds": 120,
                "batch_size": 1
            },
            "class_type": "EmptyAceStepLatentAudio",
            "_meta": {
                "title": "EmptyAceStepLatentAudio"
            }
        },
        "18": {
            "inputs": {
                "samples": [
                    "52",
                    0
                ],
                "vae": [
                    "40",
                    2
                ]
            },
            "class_type": "VAEDecodeAudio",
            "_meta": {
                "title": "VAE解码（音频）"
            }
        },
        "40": {
            "inputs": {
                "ckpt_name": "ace_step_v1_3.5b.safetensors"
            },
            "class_type": "CheckpointLoaderSimple",
            "_meta": {
                "title": "Checkpoint加载器（简易）"
            }
        },
        "44": {
            "inputs": {
                "conditioning": [
                    "14",
                    0
                ]
            },
            "class_type": "ConditioningZeroOut",
            "_meta": {
                "title": "条件零化"
            }
        },
        "49": {
            "inputs": {
                "model": [
                    "51",
                    0
                ],
                "operation": [
                    "50",
                    0
                ]
            },
            "class_type": "LatentApplyOperationCFG",
            "_meta": {
                "title": "Latent应用操作CFG"
            }
        },
        "50": {
            "inputs": {
                "multiplier": 1.0000000000000002
            },
            "class_type": "LatentOperationTonemapReinhard",
            "_meta": {
                "title": "Latent操作色调映射Reinhard"
            }
        },
        "51": {
            "inputs": {
                "shift": 5.000000000000001,
                "model": [
                    "40",
                    0
                ]
            },
            "class_type": "ModelSamplingSD3",
            "_meta": {
                "title": "采样算法（SD3）"
            }
        },
        "52": {
            "inputs": {
                "seed": 468254064217849,
                "steps": 50,
                "cfg": 5,
                "sampler_name": "euler",
                "scheduler": "simple",
                "denoise": 1,
                "model": [
                    "49",
                    0
                ],
                "positive": [
                    "14",
                    0
                ],
                "negative": [
                    "44",
                    0
                ],
                "latent_image": [
                    "17",
                    0
                ]
            },
            "class_type": "KSampler",
            "_meta": {
                "title": "K采样器"
            }
        },
        "59": {
            "inputs": {
                "filename_prefix": "audio/ComfyUiImg",
                "quality": "V0",
                "audioUI": "",
                "audio": [
                    "18",
                    0
                ]
            },
            "class_type": "SaveAudioMP3",
            "_meta": {
                "title": "Save Audio (MP3)"
            }
        }
    },

    "wan2_2_t2v_json": {
        "2": {
            "inputs": {
                "model": [
                    "18",
                    0
                ],
                "block_swap_args": [
                    "8",
                    0
                ]
            },
            "class_type": "WanVideoSetBlockSwap",
            "_meta": {
                "title": "WanVideo Set BlockSwap"
            }
        },
        "3": {
            "inputs": {
                "model": [
                    "19",
                    0
                ],
                "block_swap_args": [
                    "8",
                    0
                ]
            },
            "class_type": "WanVideoSetBlockSwap",
            "_meta": {
                "title": "WanVideo Set BlockSwap"
            }
        },
        "4": {
            "inputs": {
                "model": [
                    "3",
                    0
                ],
                "lora": [
                    "10",
                    0
                ]
            },
            "class_type": "WanVideoSetLoRAs",
            "_meta": {
                "title": "WanVideo Set LoRAs"
            }
        },
        "5": {
            "inputs": {
                "enable_vae_tiling": false,
                "tile_x": 272,
                "tile_y": 272,
                "tile_stride_x": 144,
                "tile_stride_y": 128,
                "normalization": "default",
                "vae": [
                    "13",
                    0
                ],
                "samples": [
                    "16",
                    0
                ]
            },
            "class_type": "WanVideoDecode",
            "_meta": {
                "title": "WanVideo Decode"
            }
        },
        "6": {
            "inputs": {
                "model": [
                    "2",
                    0
                ],
                "lora": [
                    "9",
                    0
                ]
            },
            "class_type": "WanVideoSetLoRAs",
            "_meta": {
                "title": "WanVideo Set LoRAs"
            }
        },
        "7": {
            "inputs": {
                "image": [
                    "5",
                    0
                ]
            },
            "class_type": "GetImageSizeAndCount",
            "_meta": {
                "title": "Get Image Size & Count"
            }
        },
        "8": {
            "inputs": {
                "blocks_to_swap": 20,
                "offload_img_emb": false,
                "offload_txt_emb": false,
                "use_non_blocking": false,
                "vace_blocks_to_swap": 1
            },
            "class_type": "WanVideoBlockSwap",
            "_meta": {
                "title": "WanVideo Block Swap"
            }
        },
        "9": {
            "inputs": {
                "lora": "lightx2v_I2V_14B_480p_cfg_step_distill_rank64_bf16.safetensors",
                "strength": 3,
                "low_mem_load": true,
                "merge_loras": false
            },
            "class_type": "WanVideoLoraSelect",
            "_meta": {
                "title": "WanVideo Lora Select"
            }
        },
        "10": {
            "inputs": {
                "lora": "lightx2v_I2V_14B_480p_cfg_step_distill_rank64_bf16.safetensors",
                "strength": 1,
                "low_mem_load": true,
                "merge_loras": false
            },
            "class_type": "WanVideoLoraSelect",
            "_meta": {
                "title": "WanVideo Lora Select"
            }
        },
        "13": {
            "inputs": {
                "model_name": "Wan2_1_VAE_bf16.safetensors",
                "precision": "bf16"
            },
            "class_type": "WanVideoVAELoader",
            "_meta": {
                "title": "WanVideo VAE Loader"
            }
        },
        "14": {
            "inputs": {
                "positive_prompt": [
                    "28",
                    0
                ],
                "negative_prompt": "色调艳丽，过曝，静态，细节模糊不清，字幕，风格，作品，画作，画面，静止，整体发灰，最差质量，低质量，JPEG压缩残留，丑陋的，残缺的，多余的手指，画得不好的手部，画得不好的脸部，畸形的，毁容的，形态畸形的肢体，手指融合，静止不动的画面，杂乱的背景，三条腿，背景人很多，倒着走",
                "force_offload": true,
                "use_disk_cache": false,
                "device": "gpu",
                "t5": [
                    "15",
                    0
                ]
            },
            "class_type": "WanVideoTextEncode",
            "_meta": {
                "title": "WanVideo TextEncode"
            }
        },
        "15": {
            "inputs": {
                "model_name": "umt5-xxl-enc-bf16.safetensors",
                "precision": "bf16",
                "load_device": "offload_device",
                "quantization": "disabled"
            },
            "class_type": "LoadWanVideoT5TextEncoder",
            "_meta": {
                "title": "WanVideo T5 Text Encoder Loader"
            }
        },
        "16": {
            "inputs": {
                "steps": [
                    "23",
                    0
                ],
                "cfg": 1,
                "shift": 8,
                "seed": 46962144800973,
                "force_offload": true,
                "scheduler": "unipc",
                "riflex_freq_index": 0,
                "denoise_strength": 1,
                "batched_cfg": false,
                "rope_function": "comfy",
                "start_step": [
                    "24",
                    0
                ],
                "end_step": -1,
                "add_noise_to_samples": false,
                "model": [
                    "4",
                    0
                ],
                "image_embeds": [
                    "17",
                    0
                ],
                "text_embeds": [
                    "14",
                    0
                ],
                "samples": [
                    "20",
                    0
                ]
            },
            "class_type": "WanVideoSampler",
            "_meta": {
                "title": "WanVideo Sampler"
            }
        },
        "17": {
            "inputs": {
                "width": [
                    "37",
                    0
                ],
                "height": [
                    "38",
                    0
                ],
                "num_frames": [
                    "39",
                    0
                ]
            },
            "class_type": "WanVideoEmptyEmbeds",
            "_meta": {
                "title": "WanVideo Empty Embeds"
            }
        },
        "18": {
            "inputs": {
                "model": "Wan2_2-T2V-A14B_HIGH_fp8_e4m3fn_scaled_KJ.safetensors",
                "base_precision": "bf16",
                "quantization": "fp8_e4m3fn_scaled",
                "load_device": "offload_device",
                "attention_mode": "sageattn",
                "block_swap_args": [
                    "35",
                    0
                ]
            },
            "class_type": "WanVideoModelLoader",
            "_meta": {
                "title": "WanVideo Model Loader"
            }
        },
        "19": {
            "inputs": {
                "model": "Wan2_2-T2V-A14B-LOW_fp8_e4m3fn_scaled_KJ.safetensors",
                "base_precision": "bf16",
                "quantization": "fp8_e4m3fn_scaled",
                "load_device": "offload_device",
                "attention_mode": "sageattn",
                "block_swap_args": [
                    "36",
                    0
                ]
            },
            "class_type": "WanVideoModelLoader",
            "_meta": {
                "title": "WanVideo Model Loader"
            }
        },
        "20": {
            "inputs": {
                "steps": [
                    "23",
                    0
                ],
                "cfg": [
                    "21",
                    0
                ],
                "shift": 8,
                "seed": 46962144800973,
                "force_offload": true,
                "scheduler": "unipc",
                "riflex_freq_index": 0,
                "denoise_strength": 1,
                "batched_cfg": false,
                "rope_function": "comfy",
                "start_step": 0,
                "end_step": [
                    "24",
                    0
                ],
                "add_noise_to_samples": false,
                "model": [
                    "6",
                    0
                ],
                "image_embeds": [
                    "17",
                    0
                ],
                "text_embeds": [
                    "14",
                    0
                ]
            },
            "class_type": "WanVideoSampler",
            "_meta": {
                "title": "WanVideo Sampler"
            }
        },
        "21": {
            "inputs": {
                "steps": [
                    "23",
                    0
                ],
                "cfg_scale_start": 2,
                "cfg_scale_end": 2,
                "interpolation": "linear",
                "start_percent": 0,
                "end_percent": 0.01
            },
            "class_type": "CreateCFGScheduleFloatList",
            "_meta": {
                "title": "Create CFG Schedule Float List"
            }
        },
        "22": {
            "inputs": {
                "frame_rate": 16,
                "loop_count": 0,
                "filename_prefix": "WanVideo2_2_I2V",
                "format": "video/h264-mp4",
                "pix_fmt": "yuv420p",
                "crf": 19,
                "save_metadata": true,
                "trim_to_audio": false,
                "pingpong": false,
                "save_output": true,
                "images": [
                    "7",
                    0
                ]
            },
            "class_type": "VHS_VideoCombine",
            "_meta": {
                "title": "Video Combine 🎥🅥🅗🅢"
            }
        },
        "23": {
            "inputs": {
                "value": 8
            },
            "class_type": "INTConstant",
            "_meta": {
                "title": "Steps"
            }
        },
        "24": {
            "inputs": {
                "value": 4
            },
            "class_type": "INTConstant",
            "_meta": {
                "title": "Split_step"
            }
        },
        "28": {
            "inputs": {
                "prompt": "一个机器人正在穿越一个未来的赛博朋克城市，这里有霓虹灯，黑暗中有明亮的HDR灯光"
            },
            "class_type": "CR Prompt Text",
            "_meta": {
                "title": "⚙️ CR Prompt Text"
            }
        },
        "35": {
            "inputs": {
                "blocks_to_swap": 40,
                "offload_img_emb": false,
                "offload_txt_emb": false,
                "use_non_blocking": true,
                "vace_blocks_to_swap": 0
            },
            "class_type": "WanVideoBlockSwap",
            "_meta": {
                "title": "WanVideo Block Swap"
            }
        },
        "36": {
            "inputs": {
                "blocks_to_swap": 40,
                "offload_img_emb": false,
                "offload_txt_emb": false,
                "use_non_blocking": true,
                "vace_blocks_to_swap": 0
            },
            "class_type": "WanVideoBlockSwap",
            "_meta": {
                "title": "WanVideo Block Swap"
            }
        },
        "37": {
            "inputs": {
                "value": 1024
            },
            "class_type": "easy int",
            "_meta": {
                "title": "宽度"
            }
        },
        "38": {
            "inputs": {
                "value": 768
            },
            "class_type": "easy int",
            "_meta": {
                "title": "高度"
            }
        },
        "39": {
            "inputs": {
                "value": 24
            },
            "class_type": "easy int",
            "_meta": {
                "title": "总帧数"
            }
        }
    },

    "wan2_2_i2v_json":{
        "11": {
            "inputs": {
                "model_name": "umt5-xxl-enc-bf16.safetensors",
                "precision": "bf16",
                "load_device": "offload_device",
                "quantization": "disabled"
            },
            "class_type": "LoadWanVideoT5TextEncoder",
            "_meta": {
                "title": "WanVideo T5 Text Encoder Loader"
            }
        },
        "16": {
            "inputs": {
                "positive_prompt": [
                    "101",
                    0
                ],
                "negative_prompt": "色调艳丽，过曝，静态，细节模糊不清，字幕，风格，作品，画作，画面，静止，整体发灰，最差质量，低质量，JPEG压缩残留，丑陋的，残缺的，多余的手指，画得不好的手部，画得不好的脸部，畸形的，毁容的，形态畸形的肢体，手指融合，静止不动的画面，杂乱的背景，三条腿，背景人很多，倒着走",
                "force_offload": true,
                "use_disk_cache": false,
                "device": "gpu",
                "t5": [
                    "11",
                    0
                ]
            },
            "class_type": "WanVideoTextEncode",
            "_meta": {
                "title": "WanVideo TextEncode"
            }
        },
        "22": {
            "inputs": {
                "model": "Wan2_2-I2V-A14B-HIGH_fp8_e4m3fn_scaled_KJ.safetensors",
                "base_precision": "bf16",
                "quantization": "fp8_e4m3fn_scaled",
                "load_device": "offload_device",
                "attention_mode": "sageattn",
                "block_swap_args": [
                    "104",
                    0
                ]
            },
            "class_type": "WanVideoModelLoader",
            "_meta": {
                "title": "WanVideo Model Loader"
            }
        },
        "27": {
            "inputs": {
                "steps": [
                    "94",
                    0
                ],
                "cfg": [
                    "95",
                    0
                ],
                "shift": 8,
                "seed": 101984570542611,
                "force_offload": true,
                "scheduler": "unipc",
                "riflex_freq_index": 0,
                "denoise_strength": 1,
                "batched_cfg": false,
                "rope_function": "comfy",
                "start_step": 0,
                "end_step": [
                    "91",
                    0
                ],
                "add_noise_to_samples": false,
                "model": [
                    "80",
                    0
                ],
                "image_embeds": [
                    "89",
                    0
                ],
                "text_embeds": [
                    "16",
                    0
                ]
            },
            "class_type": "WanVideoSampler",
            "_meta": {
                "title": "WanVideo Sampler"
            }
        },
        "28": {
            "inputs": {
                "enable_vae_tiling": false,
                "tile_x": 272,
                "tile_y": 272,
                "tile_stride_x": 144,
                "tile_stride_y": 128,
                "normalization": "default",
                "vae": [
                    "38",
                    0
                ],
                "samples": [
                    "90",
                    0
                ]
            },
            "class_type": "WanVideoDecode",
            "_meta": {
                "title": "WanVideo Decode"
            }
        },
        "38": {
            "inputs": {
                "model_name": "Wan2_1_VAE_bf16.safetensors",
                "precision": "bf16"
            },
            "class_type": "WanVideoVAELoader",
            "_meta": {
                "title": "WanVideo VAE Loader"
            }
        },
        "39": {
            "inputs": {
                "blocks_to_swap": 20,
                "offload_img_emb": false,
                "offload_txt_emb": false,
                "use_non_blocking": false,
                "vace_blocks_to_swap": 1
            },
            "class_type": "WanVideoBlockSwap",
            "_meta": {
                "title": "WanVideo Block Swap"
            }
        },
        "56": {
            "inputs": {
                "lora": "lightx2v_I2V_14B_480p_cfg_step_distill_rank64_bf16.safetensors",
                "strength": 3,
                "low_mem_load": true,
                "merge_loras": false
            },
            "class_type": "WanVideoLoraSelect",
            "_meta": {
                "title": "WanVideo Lora Select"
            }
        },
        "60": {
            "inputs": {
                "frame_rate": 16,
                "loop_count": 0,
                "filename_prefix": "WanVideo2_2_I2V",
                "format": "video/h264-mp4",
                "pix_fmt": "yuv420p",
                "crf": 19,
                "save_metadata": true,
                "trim_to_audio": false,
                "pingpong": false,
                "save_output": true,
                "images": [
                    "69",
                    0
                ]
            },
            "class_type": "VHS_VideoCombine",
            "_meta": {
                "title": "Video Combine 🎥🅥🅗🅢"
            }
        },
        "67": {
            "inputs": {
                "image": "ComfyUI_00144_.png"
            },
            "class_type": "LoadImage",
            "_meta": {
                "title": "加载图像"
            }
        },
        "69": {
            "inputs": {
                "image": [
                    "28",
                    0
                ]
            },
            "class_type": "GetImageSizeAndCount",
            "_meta": {
                "title": "Get Image Size & Count"
            }
        },
        "71": {
            "inputs": {
                "model": "Wan2_2-I2V-A14B-LOW_fp8_e4m3fn_scaled_KJ.safetensors",
                "base_precision": "bf16",
                "quantization": "fp8_e4m3fn_scaled",
                "load_device": "offload_device",
                "attention_mode": "sageattn",
                "block_swap_args": [
                    "105",
                    0
                ]
            },
            "class_type": "WanVideoModelLoader",
            "_meta": {
                "title": "WanVideo Model Loader"
            }
        },
        "79": {
            "inputs": {
                "model": [
                    "93",
                    0
                ],
                "lora": [
                    "97",
                    0
                ]
            },
            "class_type": "WanVideoSetLoRAs",
            "_meta": {
                "title": "WanVideo Set LoRAs"
            }
        },
        "80": {
            "inputs": {
                "model": [
                    "92",
                    0
                ],
                "lora": [
                    "56",
                    0
                ]
            },
            "class_type": "WanVideoSetLoRAs",
            "_meta": {
                "title": "WanVideo Set LoRAs"
            }
        },
        "89": {
            "inputs": {
                "width": [
                    "99",
                    3
                ],
                "height": [
                    "99",
                    4
                ],
                "num_frames": [
                    "107",
                    0
                ],
                "noise_aug_strength": 0,
                "start_latent_strength": 1,
                "end_latent_strength": 1,
                "force_offload": true,
                "fun_or_fl2v_model": false,
                "tiled_vae": false,
                "vae": [
                    "38",
                    0
                ],
                "start_image": [
                    "99",
                    0
                ]
            },
            "class_type": "WanVideoImageToVideoEncode",
            "_meta": {
                "title": "WanVideo ImageToVideo Encode"
            }
        },
        "90": {
            "inputs": {
                "steps": [
                    "94",
                    0
                ],
                "cfg": 1,
                "shift": 8,
                "seed": 101984570542611,
                "force_offload": true,
                "scheduler": "unipc",
                "riflex_freq_index": 0,
                "denoise_strength": 1,
                "batched_cfg": false,
                "rope_function": "comfy",
                "start_step": [
                    "91",
                    0
                ],
                "end_step": -1,
                "add_noise_to_samples": false,
                "model": [
                    "79",
                    0
                ],
                "image_embeds": [
                    "89",
                    0
                ],
                "text_embeds": [
                    "16",
                    0
                ],
                "samples": [
                    "27",
                    0
                ]
            },
            "class_type": "WanVideoSampler",
            "_meta": {
                "title": "WanVideo Sampler"
            }
        },
        "91": {
            "inputs": {
                "value": 4
            },
            "class_type": "INTConstant",
            "_meta": {
                "title": "Split_step"
            }
        },
        "92": {
            "inputs": {
                "model": [
                    "22",
                    0
                ],
                "block_swap_args": [
                    "39",
                    0
                ]
            },
            "class_type": "WanVideoSetBlockSwap",
            "_meta": {
                "title": "WanVideo Set BlockSwap"
            }
        },
        "93": {
            "inputs": {
                "model": [
                    "71",
                    0
                ],
                "block_swap_args": [
                    "39",
                    0
                ]
            },
            "class_type": "WanVideoSetBlockSwap",
            "_meta": {
                "title": "WanVideo Set BlockSwap"
            }
        },
        "94": {
            "inputs": {
                "value": 8
            },
            "class_type": "INTConstant",
            "_meta": {
                "title": "Steps"
            }
        },
        "95": {
            "inputs": {
                "steps": [
                    "94",
                    0
                ],
                "cfg_scale_start": 2,
                "cfg_scale_end": 2,
                "interpolation": "linear",
                "start_percent": 0,
                "end_percent": 0.01
            },
            "class_type": "CreateCFGScheduleFloatList",
            "_meta": {
                "title": "Create CFG Schedule Float List"
            }
        },
        "97": {
            "inputs": {
                "lora": "lightx2v_I2V_14B_480p_cfg_step_distill_rank64_bf16.safetensors",
                "strength": 1,
                "low_mem_load": true,
                "merge_loras": false
            },
            "class_type": "WanVideoLoraSelect",
            "_meta": {
                "title": "WanVideo Lora Select"
            }
        },
        "99": {
            "inputs": {
                "aspect_ratio": "original",
                "proportional_width": 1,
                "proportional_height": 1,
                "fit": "crop",
                "method": "lanczos",
                "round_to_multiple": "16",
                "scale_to_side": "longest",
                "scale_to_length": [
                    "106",
                    0
                ],
                "background_color": "#000000",
                "image": [
                    "67",
                    0
                ]
            },
            "class_type": "LayerUtility: ImageScaleByAspectRatio V2",
            "_meta": {
                "title": "LayerUtility: ImageScaleByAspectRatio V2"
            }
        },
        "101": {
            "inputs": {
                "prompt": "女人拿出相机拍照"
            },
            "class_type": "CR Prompt Text",
            "_meta": {
                "title": "⚙️ CR Prompt Text"
            }
        },
        "104": {
            "inputs": {
                "blocks_to_swap": 40,
                "offload_img_emb": false,
                "offload_txt_emb": false,
                "use_non_blocking": true,
                "vace_blocks_to_swap": 0
            },
            "class_type": "WanVideoBlockSwap",
            "_meta": {
                "title": "WanVideo Block Swap"
            }
        },
        "105": {
            "inputs": {
                "blocks_to_swap": 40,
                "offload_img_emb": false,
                "offload_txt_emb": false,
                "use_non_blocking": true,
                "vace_blocks_to_swap": 0
            },
            "class_type": "WanVideoBlockSwap",
            "_meta": {
                "title": "WanVideo Block Swap"
            }
        },
        "106": {
            "inputs": {
                "value": 720
            },
            "class_type": "easy int",
            "_meta": {
                "title": "最长边"
            }
        },
        "107": {
            "inputs": {
                "value": 24
            },
            "class_type": "easy int",
            "_meta": {
                "title": "总帧数"
            }
        }
    }
}

export default flux;
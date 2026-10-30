# 可局部改稿的本地 AI 短片工作台

这个分支公开独立 Python 代码、分镜配置与出图提示词，不包含本案例的原始图片、成片或运行记录文件。可以用自己的三张图片运行；概念素材提示词在 `assets/prompts.json`。

## 环境与输入

- Python 3.9+ 和 Pillow。
- FFmpeg / ffprobe，需有 libx264、zoompan、overlay、loudnorm、amix、aevalsrc。无需 drawtext/subtitles。
- 当前使用 **macOS** 的 `say`、已安装的中文 `Tingting` 声音和 STHeiti 字体。Linux / Windows 需要替换 TTS 与字体适配。
- 先准备三张短边至少 720 像素的图片，分别存为 `assets/01-arrival.png`、`assets/02-memory.png`、`assets/03-future.png`。这里不自动请求图像生成服务。

```sh
git clone --branch video-workbench-code https://github.com/sshipanoo/alphandbelt-ai-lab.git
cd alphandbelt-ai-lab/video-workbench
python3 -m pip install -r requirements.txt
# 放入上述三张图片后：
python3 workbench.py --validate-only
python3 workbench.py
```

结果写入 `results/cloud-archive.mp4`。默认分镜三镜各 8 秒，合计 24 秒，1920×1080、30fps。画面是静帧加二维缩放和平移，不是生成式时序视频或真实三维场景。

## 改稿逻辑

```text
原图 + 运镜 + 时长 + 规格 -> 单镜头画面 -> 拼接画面 --┐
旁白 + 声音 + 语速 + 时长 -> 单镜头配音 -> 拼接配音 --┼-> 最终合成
文字 + 字体 + 尺寸       -> 透明字幕层 --------------┘
```

每个节点用配方、相关参数、依赖文件内容的 SHA-256 定位缓存；命中时再次核对产物哈希。只改旁白，复用画面；只换图片，复用其他镜头和声音。最终 MP4 仍重新编码。TTS 缓存包含系统版本和声音名，但不对声音包本体做指纹，更新声音包后应换缓存目录。

语音先测长度，超出镜头时长就拒绝，不截句尾。字幕为一镜一句，不逐字对齐。最终输出检查格式、分辨率、帧率、音画时长，并在首次生成时完整解码。

这是单机单进程教学实现。产物与元数据分别临时写入、替换；中断后通过哈希不匹配重建。没有多进程锁，不要同时操作同一缓存目录。机械检查不能代替人工判断叙事、发音或构图。

## 验证

放入三张图片后运行 `python3 experiments.py`：实际执行首次构建、原样重跑、改旁白、换一张图、损坏缓存修复，以及缺图、旁白超时和奇数宽度拒绝。每次用独立缓存，结果写入 `results/experiments.json`，可再运行 `python3 render_report.py` 生成自己的报告页。

执行计时从节点处理开始，到成片复制结束，不含清单预检、工具探测、出图、开发或安装。不同素材、系统声音和机器会改变耗时，不能照搬别人的记录。

代码遵循仓库 MIT 许可。图像与声音的使用仍应遵守对应来源/系统的条款。

# 阿德贝塔 · AI 技术小实验

用可运行的小例子解释 AI 机制和工程方法。包含本地模型调用、注意力、在线归一化、LoRA 矩阵更新、精确推测采样、GRPO 组内奖励归一化，以及检索、幂等、并发和视频合成。

## 运行

基础数值实验不下载模型、不调用云端 API；检索例子需要 Python 链接的 SQLite 启用 FTS5：

```sh
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python -m unittest -v test_lab.py
python ai_lab.py
python practical_examples.py
python tool_feedback.py
```

主要结果写入 `results/results.json`。运行环境、输入和实验范围均在结果中记录。参考运行使用 Python 3.9.6、NumPy 1.26.4；12 项 unittest 通过，另有 practical_examples 和 tool_feedback 的断言检查。

## 本地模型检查（可选）

需要先安装 Ollama，启动本地服务并下载 `qwen3:0.6b`。下载占用磁盘，模型运行也需要内存。本脚本只接受 loopback 地址，不会下载模型或请求云端：

```sh
ollama pull qwen3:0.6b
python ollama_check.py --base-url http://127.0.0.1:11434
```

已保存一次 Ollama 0.24.0 的真实运行记录：HTTP 回复、JSON Schema 输出、17+25 的工具调用与结果回传。单次链路检查不代表模型质量基准或任意工具调用可靠性。

## 可视化与视频

```sh
python build_report.py
python animate_attention.py
```

需要系统 `ffmpeg`、`ffprobe`，以及可用的中文字体。脚本搜索 macOS、Linux 和 Windows 的常见路径，也可用 `AI_LAB_FONT` 环境变量指定字体文件。Linux 可安装 Noto Sans CJK。

- `results/demo.html`：实际运行结果与 Attention 滑块；直接用浏览器打开。
- `results/attention-animation.mp4`：8 秒、1280×720、20fps 的计算驱动动画。
- `results/storyboard/demo-vertical.mp4`：18 秒、720×1280、25fps 的分镜清单合成示例。

视频画面是程序绘制的图形，没有冒充生成式视频模型的成片。脚本用 ffprobe 核对导出规格。仓库保留检查记录与代表帧；较大的中间文件不纳入版本控制。

## 论文演示的范围

| 主题 | 实际做了什么 | 没有声称完成的工作 |
|---|---|---|
| Attention | 二维缩放点积注意力与交互 | 训练 Transformer |
| FlashAttention 相关机制 | CPU 分块前向与在线归一化，对比完整前向 | CUDA 内核、反向、论文速度复现 |
| LoRA | 低秩矩阵更新、合并等价、参数量计算 | 语言模型微调、效果评测 |
| 推测采样 | 单位置接受/拒绝修正，10 万次抽样 | 大小模型多 token 解码、提速评测 |
| GRPO | 组内奖励归一化与零方差处理 | 策略训练、KL、完整 GRPO |
| AT-AT 相关讨论 | 手写工具反馈设计与边界检查 | 自动优化器与论文复现 |

这里的“验证”对应具体断言、数值容限和运行结果；不能把它扩展成完整研究结论已复现。

## 原始资料

- [Attention Is All You Need（2017）](https://arxiv.org/abs/1706.03762)
- [FlashAttention（2022）](https://arxiv.org/abs/2205.14135)
- [LoRA（2021）](https://arxiv.org/abs/2106.09685)
- [Fast Inference from Transformers via Speculative Decoding（2022）](https://arxiv.org/abs/2211.17192)
- [DeepSeekMath / GRPO（2024）](https://arxiv.org/abs/2402.03300)
- [AT-AT（2026-10-26 预印本）](https://arxiv.org/abs/2610.34679)
- [Ollama 原生工具调用文档](https://github.com/ollama/ollama/blob/main/docs/capabilities/tool-calling.mdx)
- [SQLite FTS5](https://sqlite.org/fts5.html)
- [FFmpeg 滤镜](https://ffmpeg.org/ffmpeg-filters.html)

代码为独立教学实现。MIT License。


## Screenshots from actual runs

![ollama-screenshot.png](https://pub-b4be6e3b9d5b4c6f94851aed459f14c8.r2.dev/images/0b26970e-cdd5-4951-b468-107812a64542.png)

![attention-screenshot.png](https://pub-b4be6e3b9d5b4c6f94851aed459f14c8.r2.dev/images/426ddc7e-b26a-424f-bf3f-24d7f5cf1482.png)

![speculative-screenshot.png](https://pub-b4be6e3b9d5b4c6f94851aed459f14c8.r2.dev/images/1885fd51-ce22-45ca-bc3f-39b514561040.png)

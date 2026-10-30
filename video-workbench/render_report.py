#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Render the actual experiment records into a shareable local review page."""
import html
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def main():
    data = json.loads((ROOT/'results/experiments.json').read_text(encoding='utf-8'))
    labels = ['首次构建', '原样重跑', '只改第二句旁白', '只换第二张图', '损坏一个画面缓存后重跑']
    rows = []
    for label, report in zip(labels, data['reports']):
        states = ''.join('<span class="'+('built' if e['status']=='BUILD' else 'hit')+'" title="'+html.escape(e['node'])+'">'+('B' if e['status']=='BUILD' else '·')+'</span>' for e in report['events'])
        rows.append('<tr><td>'+label+'</td><td class="dots">'+states+'</td><td>'+str(len(report['built']))+'</td><td>'+str(len(report['hits']))+'</td><td>'+f"{report['elapsed_seconds']:.2f}s"+'</td></tr>')
    errors = ''.join('<div class="check"><b>PASS</b><span>'+html.escape(e['case'])+'</span><code>'+html.escape(e['error'])+'</code></div>' for e in data['rejection_checks'])
    document = '''<!doctype html><html lang="zh-CN"><meta charset="utf-8"><title>云端档案馆 · 实测工作台</title>
<style>
*{box-sizing:border-box}body{margin:0;background:#f3f0e9;color:#20241f;font:16px/1.6 -apple-system,BlinkMacSystemFont,"PingFang SC",sans-serif}main{max-width:1480px;margin:auto;padding:48px 60px}header{display:flex;justify-content:space-between;align-items:end;margin-bottom:26px}.eyebrow{font:12px monospace;letter-spacing:.15em;color:#77644b}h1{font-size:36px;line-height:1.2;margin:12px 0}header p{margin:0;color:#6d6d63}.tag{border:1px solid #c9c5b9;padding:7px 12px;font:12px monospace}.hero{display:grid;grid-template-columns:1.7fr 1fr;background:#20251f;color:#f4eddd;border-radius:5px;overflow:hidden}.hero video{width:100%;display:block;aspect-ratio:16/9;background:#111}.intro{padding:30px}.intro h2{font-size:24px;margin:0 0 22px}.intro p{font-size:14px;color:#c7caba}.spec{font:12px monospace;border-top:1px solid #5d6254;padding-top:20px;color:#e5c17e}.panel{margin-top:26px;background:#fffdf8;padding:25px 32px;border:1px solid #dedacf;border-radius:5px}h2{font-size:21px;margin:0 0 12px}table{width:100%;border-collapse:collapse;font-size:15px}th{text-align:left;color:#6f7465;font-size:12px;font-weight:400;padding:10px 12px;border-bottom:1px solid #ddd8ca}td{padding:12px;border-bottom:1px solid #ece7da}.dots{white-space:nowrap}.dots span{display:inline-block;width:21px;height:23px;text-align:center;margin-right:3px;border-radius:2px;font:13px/23px monospace}.built{background:#e5bd73;color:#513f22}.hit{background:#e8eee2;color:#50703e}.note{font-size:12px;color:#6f7465;margin:16px 0 0}.checks{display:grid;gap:12px}.check{display:grid;grid-template-columns:60px 200px 1fr;gap:15px;align-items:center;font-size:13px}.check b{color:#537342}.check code{font-size:11px;color:#767668;overflow-wrap:anywhere}.flow{display:grid;grid-template-columns:1fr 1fr 1fr;gap:20px}.lane{border-left:3px solid #ba9253;background:#f7f4ec;padding:18px}.lane h3{margin:0 0 7px;font-size:16px}.lane p{font-size:13px;margin:0;color:#6d7165}.foot{font-size:12px;margin-top:30px;color:#747568}a{color:#65754c}@media(max-width:950px){main{padding:20px}.hero{grid-template-columns:1fr}.check{grid-template-columns:60px 1fr}.check code{grid-column:1/-1}.flow{grid-template-columns:1fr}}
</style><main><header><div><div class="eyebrow">ALPHANDBELT / LOCAL FILM WORKBENCH</div><h1>云端档案馆</h1><p>从三张 AI 概念画面，到可以反复改稿的成片</p></div><div class="tag">ACTUAL BUILD REPORT</div></header>
<section class="hero"><video controls preload="metadata" poster="assets/01-arrival.png" src="results/cloud-archive.mp4"></video><div class="intro"><h2>一份分镜，三条支路。</h2><p>画面、声音与字幕分别构建，输入变了才重做对应节点，再重新合成最终 MP4。</p><p>本片为 AI 静帧 + 二维程序运镜；声音使用 macOS TTS，低音氛围声由代码合成。</p><div class="spec">24 SEC · 1920 × 1080 · 30 FPS<br>H.264 / yuv420p · AAC / 48 kHz</div></div></section>
<section class="panel" id="evidence"><h2>实际改稿记录</h2><table><thead><tr><th>本轮操作</th><th>12 个节点：B 重做 / · 复用</th><th>BUILD</th><th>HIT</th><th>执行耗时</th></tr></thead><tbody>'''+''.join(rows)+'''</tbody></table><p class="note">单机单轮：计时从执行节点到复制成片，含节点哈希检查与音视频处理；不含清单预检、工具探测、AI 出图、开发及安装。最终合成仍需重编码。</p></section>
<section class="panel"><h2>依赖决定重建范围</h2><div class="flow"><div class="lane"><h3>画面支路</h3><p>原图 + 运镜 + 时长 + 规格<br>单镜头 → 拼接画面</p></div><div class="lane"><h3>声音支路</h3><p>文字 + 声音 + 语速 + 时长<br>实测时长 → 补齐每个镜头</p></div><div class="lane"><h3>字幕支路</h3><p>文字 + 字体 + 尺寸<br>透明图层 → 最后叠加</p></div></div></section>
<section class="panel"><h2>异常拦截与成片校验</h2><div class="checks">'''+errors+'''</div><p class="note">最终成片已检查音视频流、格式、分辨率、帧率与时长，并执行完整解码。人工观感仍需单独审看。</p></section><p class="foot">代码、分镜、提示词、原始运行记录：<a href="https://github.com/sshipanoo/alphandbelt-ai-lab/tree/video-workbench-code/video-workbench">GitHub / video-workbench</a> · 本例当前使用 macOS 语音与字体适配。</p></main></html>'''
    (ROOT/'report.html').write_text(document, encoding='utf-8')


if __name__ == '__main__':
    main()

"""Render an actual results dashboard and original storyboard video assets."""
from pathlib import Path
import html
import json,os
import shutil
import subprocess
from PIL import Image, ImageDraw, ImageFont
from ai_lab import validate_shots
from tool_feedback import usage_status

ROOT=Path(__file__).resolve().parent
OUT=ROOT/'results'
OUT.mkdir(exist_ok=True)
r=json.loads((OUT/'results.json').read_text())
cards=[
 ('attention','Attention：把加权求和算出来',r['attention'],'QKᵀ / √d → softmax → 乘 V；二维数值例子。'),
 ('online_attention','分块注意力：结果是否一致',r['online_attention'],'NumPy CPU 前向机制演示；没有复现 CUDA 内核，也没有测加速比。'),
 ('lora','LoRA：合并前后是否一致',r['lora'],'只验证低秩矩阵更新与合并等价，不是模型微调实验。'),
 ('speculative','推测采样：10 万次单步采样',r['speculative'],'验证拒绝后的分布修正，不是大模型推理速度测试。'),
 ('grpo','GRPO：组内奖励如何变成优势',r['grpo'],'验证奖励标准化，不包含策略更新、KL 或训练。'),
 ('tool_feedback','工具反馈：把确定性状态算出来',{'before':{'used':12,'limit':10},'after':usage_status(12,10)},'手写的反馈设计例子，不是 AT-AT 自动优化器复现。'),
 ('engineering','检索、重试与并发', {k:r[k] for k in ['retrieval','idempotency','concurrency']},'SQLite 内存数据库、模拟 I/O；不调用外部服务。'),
]
local_path=OUT/'ollama-check.json'
if local_path.exists():
    local=json.loads(local_path.read_text())
    cards.insert(0,('ollama','本地模型：真实 HTTP 与 JSON 输出',{'version':local['version'],'model':local['model'],'basic':local['basic'],'structured_result':local['structured']['response']},'本机临时服务实跑；记录为单次链路检查，不是质量基准。'))
    cards.insert(1,('tool_call','工具调用：模型提议，Python 执行',local['tool_call'],'真实本地模型调用 add，宿主验证参数后执行，并将结果交回模型。'))
style='''*{box-sizing:border-box}body{margin:0;background:#f5f3ec;color:#18232b;font:18px/1.7 -apple-system,BlinkMacSystemFont,"Arial",sans-serif}main{max-width:1180px;margin:auto;padding:44px 30px}header{border-bottom:2px solid #18232b;margin-bottom:34px}h1{font-size:38px;line-height:1.25}h2{font-size:27px;line-height:1.4}small{color:#59636c}section{background:white;border:1px solid #d8ddd9;border-radius:18px;padding:30px;margin:26px 0;scroll-margin-top:20px}pre{white-space:pre-wrap;overflow-wrap:anywhere;background:#112333;color:#d9f2ec;padding:22px;border-radius:12px;font:16px/1.5 Menlo,monospace}.note{color:#466257}.bars{display:flex;gap:22px;align-items:flex-end;height:180px;margin:30px}.bar{width:90px;background:#234ebd;position:relative;border-radius:8px 8px 0 0}.bar span{position:absolute;top:-32px;white-space:nowrap}.input{padding:18px;background:#f3f6fa;border-radius:8px}input{width:240px}button{padding:10px 18px;border:0;border-radius:8px;background:#234ebd;color:white}a{color:#234ebd}'''
body='<header><small>阿德贝塔 · AI 技术小实验 / ACTUAL RUN RESULTS</small><h1>把机制讲清楚，把结果跑出来。</h1><p>本页数值来自 ai_lab.py 的实际运行。论文机制演示与完整论文复现分开标注。</p></header>'
for ident,title,data,note in cards:
    extra=''
    if ident=='attention':
        extra='''<div class="input">改变查询向量的第一个分量，观察权重：<br><input id="q" type="range" min="-4" max="4" step="0.1" value="1" oninput="updateAttention()"><b id="qv"></b><div class="bars"><div class="bar" id="b0"><span id="w0"></span></div><div class="bar" id="b1"><span id="w1"></span></div></div><p id="attentionOut"></p></div>'''
    display='\n'.join(key+' = '+json.dumps(value,ensure_ascii=False) for key,value in data.items() if key!='scope')
    body+=f'<section id="{ident}"><h2>{html.escape(title)}</h2><p class="note">{html.escape(note)}</p><pre>{html.escape(display)}</pre>{extra}</section>'
body+='''<section id="video"><h2>18 秒竖屏：分镜清单驱动合成</h2><p>原创程序绘制的动态图形与字幕，无配音；不是生成式模型拍摄画面。用于验证分镜、时长、拼接和导出流程。</p><video controls style="max-height:600px;max-width:100%" src="storyboard/demo-vertical.mp4"></video></section>'''
js='''function updateAttention(){const q=Number(document.getElementById('q').value);const s=q/Math.sqrt(2);const m=Math.max(s,0);const e0=Math.exp(s-m),e1=Math.exp(-m);const w=e0/(e0+e1);document.getElementById('qv').textContent=q.toFixed(1);[w,1-w].forEach((v,i)=>{document.getElementById('b'+i).style.height=(v*160)+'px';document.getElementById('w'+i).textContent=v.toFixed(4)});document.getElementById('attentionOut').textContent='输出：['+(10*w).toFixed(4)+', '+(20*(1-w)).toFixed(4)+']'}updateAttention();'''
(OUT/'demo.html').write_text('<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>阿德贝塔 AI 技术小实验</title><style>'+style+'</style><main>'+body+'</main><script>'+js+'</script></html>')

story=OUT/'storyboard';story.mkdir(exist_ok=True)
shots=[
 {'id':'s01','duration':6,'caption':'问题：输入太多，成本太高','label':'01 / THE PROBLEM','detail':'每次请求，都把所有资料重新发一遍？'},
 {'id':'s02','duration':6,'caption':'检索：先找到需要的证据','label':'02 / RETRIEVE','detail':'从资料中选出相关片段，并保留来源。'},
 {'id':'s03','duration':6,'caption':'回答：只围绕证据展开','label':'03 / ANSWER','detail':'把问题和片段交给模型，再核对引用。'},
]
validate_shots(shots)
(story/'shots.json').write_text(json.dumps(shots,ensure_ascii=False,indent=2))
font_paths=([Path(os.environ['AI_LAB_FONT'])] if os.environ.get('AI_LAB_FONT') else [])+[Path('/System/Library/Fonts/STHeiti Medium.ttc'),Path('/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc'),Path('C:/Windows/Fonts/msyh.ttc')]
fp=next((x for x in font_paths if x.exists()),None)
if fp is None:raise RuntimeError('Install a CJK font and add its path to build_report.py')
def font(size):return ImageFont.truetype(str(fp),size)
palette=['#204ecc','#0f7c6b','#bd652b']
for i,shot in enumerate(shots):
    im=Image.new('RGB',(720,1280),'#f5f3ec');d=ImageDraw.Draw(im)
    d.text((50,95),'阿德贝塔 · AI 工作流',font=font(28),fill='#26343c')
    d.text((50,175),shot['label'],font=font(26),fill=palette[i])
    # Deliberately procedural artwork, not an AI-generated-image claim.
    for j in range(5):
        y=340+j*63
        color=palette[i] if (i==0 or j in [1,3]) else '#d9ddd9'
        d.rounded_rectangle((80,y,640,y+37),radius=10,fill=color)
    lines=[shot['caption'][:10],shot['caption'][10:]]
    y=790
    for line in lines:
        if line:d.text((50,y),line,font=font(47),fill='#152c38');y+=70
    text=shot['detail'];y=1000
    for start in range(0,len(text),18):
        d.text((50,y),text[start:start+18],font=font(30),fill='#52626b');y+=48
    d.text((50,1170),'分镜清单 → 素材 → FFmpeg 导出',font=font(25),fill='#52626b')
    im.save(story/(shot['id']+'.png'))

ffmpeg=shutil.which('ffmpeg');ffprobe=shutil.which('ffprobe')
if not ffmpeg or not ffprobe:raise RuntimeError('Install ffmpeg and ffprobe')
commands=[]
for shot in shots:
    command=[ffmpeg,'-hide_banner','-loglevel','error','-y','-loop','1','-i',shot['id']+'.png','-vf',"zoompan=z='min(zoom+0.0005,1.08)':d=150:s=720x1280:fps=25",'-t',str(shot['duration']),'-an','-c:v','libx264','-pix_fmt','yuv420p',shot['id']+'.mp4']
    subprocess.run(command,cwd=story,check=True);commands.append(command)
(story/'list.txt').write_text(''.join("file '"+s['id']+".mp4'\n" for s in shots))
command=[ffmpeg,'-hide_banner','-loglevel','error','-y','-f','concat','-safe','0','-i','list.txt','-c','copy','-movflags','+faststart','demo-vertical.mp4']
subprocess.run(command,cwd=story,check=True);commands.append(command)
probe=subprocess.check_output([ffprobe,'-v','error','-show_entries','stream=codec_name,width,height,r_frame_rate:format=duration','-of','json','demo-vertical.mp4'],cwd=story,text=True)
metadata=json.loads(probe)
assert abs(float(metadata['format']['duration'])-18)<.05
assert metadata['streams'][0]['width']==720 and metadata['streams'][0]['height']==1280
(story/'probe.json').write_text(probe)
(story/'commands.json').write_text(json.dumps(commands,indent=2))
print('Generated real results dashboard and verified 18s 720x1280 video.')

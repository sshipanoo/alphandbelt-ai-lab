"""An actual 8-second attention visualization. No generative video model."""
from pathlib import Path
import json, math, os, shutil, subprocess
import numpy as np
from PIL import Image,ImageDraw,ImageFont
from ai_lab import softmax

root=Path(__file__).resolve().parent
out=root/'results';out.mkdir(exist_ok=True)
width,height,fps,seconds=1280,720,20,8
fonts=([Path(os.environ['AI_LAB_FONT'])] if os.environ.get('AI_LAB_FONT') else [])+[Path('/System/Library/Fonts/STHeiti Medium.ttc'),Path('/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc'),Path('C:/Windows/Fonts/msyh.ttc')]
fp=next((p for p in fonts if p.exists()),None)
if not fp:raise RuntimeError('Install a CJK font and update the font path')
def font(n):return ImageFont.truetype(str(fp),n)
ffmpeg,ffprobe=shutil.which('ffmpeg'),shutil.which('ffprobe')
if not ffmpeg or not ffprobe:raise RuntimeError('Install ffmpeg and ffprobe, and add them to PATH')
cmd=[ffmpeg,'-hide_banner','-loglevel','error','-y','-f','rawvideo','-pixel_format','rgb24','-video_size',f'{width}x{height}','-framerate',str(fps),'-i','-','-an','-c:v','libx264','-pix_fmt','yuv420p','-movflags','+faststart',str(out/'attention-animation.mp4')]
process=subprocess.Popen(cmd,stdin=subprocess.PIPE)
frames=[]
try:
    for n in range(fps*seconds):
        q=4*n/(fps*seconds-1)
        w=softmax([q/math.sqrt(2),0])
        value=[10*w[0],20*w[1]]
        im=Image.new('RGB',(width,height),'#f5f3ec');draw=ImageDraw.Draw(im)
        draw.text((65,42),'阿德贝塔 · Attention 数值实验',font=font(31),fill='#52626b')
        draw.text((65,105),'查询变了，取用两个位置的比例也会变。',font=font(45),fill='#142c38')
        draw.text((65,200),f'q=[{q:.2f}, 0]     K=[[1,0],[0,1]]',font=font(31),fill='#142c38')
        draw.text((65,252),'weights = softmax([q[0] / sqrt(2), 0])',font=font(30),fill='#142c38')
        for j in range(2):
            y=345+j*108
            draw.text((65,y),f'位置{j+1}',font=font(29),fill='#142c38')
            draw.rounded_rectangle((200,y,1000,y+43),radius=12,fill='#e0e3df')
            draw.rounded_rectangle((200,y,200+800*float(w[j]),y+43),radius=12,fill=['#204ecc','#0f7c6b'][j])
            draw.text((1030,y),f'{w[j]:.4f}',font=font(29),fill='#142c38')
        draw.text((65,570),f'输出 = [{value[0]:.4f}, {value[1]:.4f}]',font=font(40),fill='#142c38')
        draw.text((65,650),'二维前向机制演示 / 非模型训练、非性能基准',font=font(24),fill='#52626b')
        process.stdin.write(im.tobytes())
        if n in [0,80,159]:
            im.save(out/f'attention-frame-{n:03d}.png')
            frames.append({'frame':n,'q0':q,'weights':w.tolist(),'output':value})
finally:
    process.stdin.close()
if process.wait()!=0:raise RuntimeError('ffmpeg encoding failed')
meta=json.loads(subprocess.check_output([ffprobe,'-v','error','-show_entries','format=duration:stream=width,height,r_frame_rate','-of','json',str(out/'attention-animation.mp4')],text=True))
assert abs(float(meta['format']['duration'])-seconds)<.05
(out/'attention-animation-check.json').write_text(json.dumps({'probe':meta,'selected_frames':frames},ensure_ascii=False,indent=2))
print('Generated and probed actual 8s attention animation (1280x720,20fps).')

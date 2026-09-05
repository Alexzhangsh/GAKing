"""
将金角大王 logo 最外圈圆以外的部分变为透明，圆内保持不变。
方法：从图片边界泛洪填充黑色背景，被填充到的像素设为透明。
"""
from PIL import Image
import numpy as np

SRC = "gak-logo.png"
DST = "gak-logo-transparent.png"

img = Image.open(SRC).convert("RGBA")
arr = np.array(img)
H, W = arr.shape[:2]
rgb = arr[:, :, :3]

# 背景判定：RGB 三通道都 < 30 视为黑色背景（可被泛洪填充）
bg_mask = np.all(rgb < 30, axis=2)

# 初始化：只有边界上的背景像素标记为"已填充（圆外）"
filled = np.zeros((H, W), dtype=bool)
border = np.zeros((H, W), dtype=bool)
border[0, :] = True
border[-1, :] = True
border[:, 0] = True
border[:, -1] = True
filled = border & bg_mask

# 迭代泛洪填充（4邻域膨胀），直到不再变化
print("泛洪填充中...")
iteration = 0
while True:
    iteration += 1
    new_filled = filled.copy()
    # 上/下/左/右 四个方向膨胀，且必须是背景像素
    new_filled[1:-1, 1:-1] |= (
        filled[:-2, 1:-1]   # 上
        | filled[2:, 1:-1]  # 下
        | filled[1:-1, :-2] # 左
        | filled[1:-1, 2:]  # 右
    ) & bg_mask[1:-1, 1:-1]

    if np.array_equal(new_filled, filled):
        break
    filled = new_filled
    if iteration % 50 == 0:
        print(f"  第 {iteration} 轮，已填充 {filled.sum()} 像素")

print(f"完成：共 {iteration} 轮，圆外像素 {filled.sum()} / {H*W}")

# 圆外像素 alpha 设为 0（透明），圆内保持不变
result = arr.copy()
result[filled, 3] = 0

# 保存
out = Image.fromarray(result, "RGBA")
out.save(DST, "PNG")
print(f"已保存: {DST} ({out.size[0]}x{out.size[1]})")

# 验证：统计透明像素和非透明像素
out_arr = np.array(out)
transparent = (out_arr[:, :, 3] == 0).sum()
opaque = (out_arr[:, :, 3] > 0).sum()
print(f"透明像素: {transparent}, 不透明像素: {opaque}")

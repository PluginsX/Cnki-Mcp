# CNKI 自动安全验证模块开发计划

## 一、项目概述

本模块用于自动处理知网 (CNKI) 的滑块拼图安全验证，通过图像处理算法识别缺口位置并模拟鼠标拖拽完成验证。

### 1.1 验证原理
- 滑块拼图验证：用户需要将拼图板块拖拽到背景图的缺口位置
- 背景图：横向图片，包含多个白色拼图缺口形状
- 拼图板块：竖向图片，带透明通道，需与缺口对齐

### 1.2 核心思路
1. 提取背景图中的白色缺口区域
2. 提取拼图板块的不透明区域
3. 通过图像重合度匹配找到最佳缺口
4. 计算拖拽距离并模拟鼠标操作

---

## 二、技术架构

### 2.1 技术选型
| 组件 | 用途 |
|------|------|
| OpenCV (cv2) | 图像处理、轮廓检测、模板匹配 |
| NumPy | 数组运算、图像矩阵操作 |
| Playwright | 浏览器自动化、鼠标控制 |

### 2.2 模块结构
```
AutomaticVerification/
├── __init__.py           # 模块导出
├── solver.py             # 验证求解器主类
├── image_processor.py    # 图像处理工具
├── captcha_detector.py   # 验证码检测
├── mouse_controller.py   # 鼠标控制
└── config.py             # 配置参数
```

---

## 三、核心算法设计

### 3.1 图像处理流程

#### 3.1.1 背景图处理
```
输入: 背景图 (bg.png)
  ↓
提取白色像素: 颜色 = #FFFFFF → 白色, 其他 → 黑色
  ↓
形态学闭运算: 填充缺口内部细小空洞
  ↓
轮廓检测: cv2.findContours()
  ↓
包围盒计算: cv2.boundingRect() → List[Rect]
  ↓
输出: 缺口包围盒列表
```

#### 3.1.2 拼图板块处理
```
输入: 拼图板块图 (piece.png)
  ↓
Alpha通道提取: 获取透明度信息
  ↓
二值化: 不透明 → 白色, 透明 → 黑色
  ↓
轮廓检测
  ↓
包围盒计算
  ↓
输出: 拼图板块包围盒
```

### 3.2 匹配算法

#### 3.2.1 多种相似度度量方法

**方法1: 加法计算 (基础方案)**
```python
def calculate_similarity_addition(bg_roi, piece_img):
    """
    使用加法计算重合度 (快速但不够精确)
    - 将两张图叠加，像素相加
    - 重合区域像素值 > 255
    - 总和越大，重合度越高
    """
    piece_resized = cv2.resize(piece_img, (bg_roi.shape[1], bg_roi.shape[0]))
    bg_roi = bg_roi.astype(np.float32)
    piece_resized = piece_resized.astype(np.float32)
    
    added = cv2.add(bg_roi, piece_resized)
    overlap_count = np.sum(added > 255)
    
    return overlap_count
```

**方法2: IoU (交集/并集) - 推荐**
```python
def calculate_similarity_iou(bg_roi, piece_img):
    """
    使用 IoU (Intersection over Union) 计算相似度
    - 更精确，不受边界噪声影响
    - 范围: 0-1, 越接近1越相似
    """
    piece_resized = cv2.resize(piece_img, (bg_roi.shape[1], bg_roi.shape[0]))
    
    # 二值化处理
    bg_binary = (bg_roi > 128).astype(np.uint8)
    piece_binary = (piece_resized > 128).astype(np.uint8)
    
    # 计算交集和并集
    intersection = np.sum((bg_binary > 0) & (piece_binary > 0))
    union = np.sum((bg_binary > 0) | (piece_binary > 0))
    
    if union == 0:
        return 0
    
    iou = intersection / union
    return iou
```

**方法3: 结构相似度 (SSIM) - 最精确**
```python
def calculate_similarity_ssim(bg_roi, piece_img):
    """
    使用结构相似度 (SSIM) 计算相似度
    - 最精确，考虑结构和纹理
    - 需要: pip install scikit-image
    """
    from skimage.metrics import structural_similarity as ssim
    
    piece_resized = cv2.resize(piece_img, (bg_roi.shape[1], bg_roi.shape[0]))
    
    # 转换为灰度图
    bg_gray = cv2.cvtColor(bg_roi, cv2.COLOR_BGR2GRAY) if len(bg_roi.shape) == 3 else bg_roi
    piece_gray = cv2.cvtColor(piece_resized, cv2.COLOR_BGR2GRAY) if len(piece_resized.shape) == 3 else piece_resized
    
    # 计算 SSIM
    similarity = ssim(bg_gray, piece_gray)
    
    return similarity
```

#### 3.2.2 最佳缺口筛选 (改进版)
```python
def find_best_gap(gap_boxes, piece_img, bg_image, method='iou'):
    """
    遍历所有缺口，找出重合度最高的那个
    
    参数:
        gap_boxes: 缺口包围盒列表
        piece_img: 拼图板块二值图
        bg_image: 背景图
        method: 相似度计算方法 ('addition', 'iou', 'ssim')
    """
    best_gap = None
    best_score = -1
    score_details = []
    
    for idx, gap_box in enumerate(gap_boxes):
        x, y, w, h = gap_box
        
        # 边界检查
        if y + h > bg_image.shape[0] or x + w > bg_image.shape[1]:
            continue
        
        bg_roi = bg_image[y:y+h, x:x+w]
        
        # 根据方法选择相似度计算
        if method == 'iou':
            score = calculate_similarity_iou(bg_roi, piece_img)
        elif method == 'ssim':
            score = calculate_similarity_ssim(bg_roi, piece_img)
        else:
            score = calculate_similarity_addition(bg_roi, piece_img)
        
        score_details.append({
            'gap_index': idx,
            'gap_box': gap_box,
            'score': score
        })
        
        if score > best_score:
            best_score = score
            best_gap = gap_box
    
    # 记录详细信息用于调试
    print(f"[匹配结果] 方法: {method}, 最佳分数: {best_score:.4f}")
    print(f"[详细信息] {score_details}")
    
    return best_gap, best_score, score_details
```

#### 3.2.3 Y轴对齐处理 (新增)
```python
def align_and_match(gap_boxes, piece_img, bg_image):
    """
    处理 Y 轴偏移，提高匹配精度
    
    关键改进:
    - 不仅忽略 X 轴，也处理 Y 轴偏移
    - 计算重叠区域，只在重叠部分计算相似度
    """
    best_gap = None
    best_score = -1
    
    piece_h = piece_img.shape[0]
    
    for gap_box in gap_boxes:
        x, y, w, h = gap_box
        
        # 计算 Y 轴重叠范围
        overlap_y_min = max(0, y)
        overlap_y_max = min(bg_image.shape[0], y + h)
        
        if overlap_y_max <= overlap_y_min:
            continue
        
        # 提取重叠区域
        overlap_h = overlap_y_max - overlap_y_min
        bg_roi = bg_image[overlap_y_min:overlap_y_max, x:x+w]
        
        # 调整拼图板块到相同高度
        if piece_h != overlap_h:
            piece_resized = cv2.resize(piece_img, (w, overlap_h))
        else:
            piece_resized = piece_img
        
        # 计算相似度
        score = calculate_similarity_iou(bg_roi, piece_resized)
        
        if score > best_score:
            best_score = score
            best_gap = gap_box
    
    return best_gap, best_score
```

### 3.3 拖拽距离计算 (改进版)
```python
def calculate_drag_distance(piece_box, best_gap, slider_width=40):
    """
    计算需要拖拽的距离
    
    关键点:
    - 拼图板块当前 X 位置
    - 缺口目标 X 位置
    - 滑块宽度补偿
    - 动态补偿值调整
    
    参数:
        piece_box: 拼图板块包围盒 (x, y, w, h)
        best_gap: 最佳缺口包围盒 (x, y, w, h)
        slider_width: 滑块宽度 (默认40px)
    """
    piece_x = piece_box[0]  # 拼图板块当前 X
    gap_x = best_gap[0]       # 缺口 X
    
    # 基础距离计算
    base_distance = gap_x - piece_x
    
    # 动态补偿: 根据缺口宽度调整
    gap_width = best_gap[2]
    compensation = max(0, (gap_width - slider_width) // 2)
    
    # 最终距离
    distance = base_distance + compensation
    
    # 确保距离为正
    distance = max(0, distance)
    
    print(f"[距离计算] 板块X: {piece_x}, 缺口X: {gap_x}, 补偿: {compensation}, 最终距离: {distance}")
    
    return distance
```

### 3.4 拖拽轨迹优化 (新增)
```python
def generate_drag_trajectory(start_x, start_y, distance, steps=20):
    """
    生成人类化的拖拽轨迹
    
    特点:
    - 使用缓动函数 (easing function)
    - 添加微小的随机抖动
    - 模拟加速和减速
    """
    import random
    
    trajectory = []
    
    for i in range(steps):
        # 进度比例 (0-1)
        progress = i / steps
        
        # 缓出效果 (ease-out): 开始快，结束慢
        eased_progress = 1 - (1 - progress) ** 2
        
        # 计算当前位置
        current_x = start_x + distance * eased_progress
        
        # 添加微小的 Y 轴抖动 (±2px)
        random_y = start_y + random.randint(-2, 2)
        
        # 添加微小的 X 轴抖动 (±1px)
        random_x = current_x + random.uniform(-1, 1)
        
        trajectory.append({
            'x': random_x,
            'y': random_y,
            'delay': random.uniform(0.02, 0.08)  # 随机延迟
        })
    
    return trajectory
```

---

## 四、详细实现步骤

### 4.1 第一阶段：基础框架搭建

#### Step 1.1: 创建配置模块 (config.py)
```python
# 图像处理参数
WHITE_THRESHOLD = (255, 255, 255)  # 白色阈值
MORPHOLOGY_KERNEL = (5, 5)         # 形态学卷积核大小
MIN_GAP_AREA = 100                 # 最小缺口面积
PIECE_COMPENSATION = 5            # 拖拽补偿像素

# 鼠标控制参数
DRAG_STEPS = 10                   # 拖拽分段数
DRAG_DURATION = 500               # 拖拽总时长 (ms)
RANDOM_DELAY_MIN = 100            # 随机延迟最小值 (ms)
RANDOM_DELAY_MAX = 300            # 随机延迟最大值 (ms)

# 重试参数
MAX_RETRY = 3                     # 最大重试次数
RETRY_DELAY = 2000                # 重试延迟 (ms)
```

#### Step 1.2: 创建鼠标控制器 (mouse_controller.py)
```python
class MouseController:
    """鼠标控制器"""
    
    def __init__(self, page: Page):
        self.page = page
    
    def drag_slider(self, start_x, start_y, distance):
        """
        模拟滑块拖拽
        
        实现要点:
        - 分段拖拽，模拟人类操作
        - 添加随机微小移动
        - 拖拽结束后松开
        """
        # 计算每段距离
        step_distance = distance // DRAG_STEPS
        
        # 移动到起始位置并按下
        self.page.mouse.move(start_x, start_y)
        self.page.mouse.down()
        
        # 分段拖拽
        for i in range(DRAG_STEPS):
            current_x = start_x + step_distance * (i + 1)
            # 添加随机 Y 轴抖动
            random_y = start_y + random.randint(-2, 2)
            self.page.mouse.move(current_x, random_y)
            # 随机停顿
            time.sleep(random.uniform(0.05, 0.15))
        
        # 松开鼠标
        self.page.mouse.up()
```

### 4.2 第二阶段：图像处理模块

#### Step 2.1: 创建图像处理器 (image_processor.py)
```python
class ImageProcessor:
    """图像处理工具类"""
    
    @staticmethod
    def extract_white_regions(image):
        """
        提取白色区域
        
        逻辑:
        - 白色像素 (#FFFFFF) → 白色 (255)
        - 其他颜色 → 黑色 (0)
        """
        # 转换为 HSV 或直接使用 BGR
        # 白色检测: R > 200 AND G > 200 AND B > 200
        white_mask = np.all(image > 200, axis=2).astype(np.uint8) * 255
        return white_mask
    
    @staticmethod
    def extract_piece_region(image):
        """
        提取拼图板块区域
        
        逻辑:
        - Alpha > 0 → 白色 (不透明)
        - Alpha = 0 → 黑色 (透明)
        """
        if image.shape[2] == 4:  # RGBA
            alpha = image[:, :, 3]
            return (alpha > 0).astype(np.uint8) * 255
        else:  # RGB
            return np.ones(image.shape[:2], dtype=np.uint8) * 255
    
    @staticmethod
    def fill_contours(binary_image):
        """
        形态学闭运算 - 填充内部空洞
        """
        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (5, 5))
        closed = cv2.morphologyEx(binary_image, cv2.MORPH_CLOSE, kernel)
        return closed
    
    @staticmethod
    def find_contour_boxes(image, min_area=100):
        """
        查找轮廓并返回包围盒列表
        """
        contours, _ = cv2.findContours(image, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        
        boxes = []
        for contour in contours:
            area = cv2.contourArea(contour)
            if area >= min_area:
                x, y, w, h = cv2.boundingRect(contour)
                boxes.append((x, y, w, h))
        
        return boxes
    
    @staticmethod
    def calculate_overlap_score(bg_roi, piece_img):
        """
        计算两张图的重合度分数
        
        使用加法计算:
        - 重合区域像素值 > 255
        - 分数越高，重合度越高
        """
        # 调整大小
        if bg_roi.shape[0] != piece_img.shape[0] or bg_roi.shape[1] != piece_img.shape[1]:
            piece_resized = cv2.resize(piece_img, (bg_roi.shape[1], bg_roi.shape[0]))
        else:
            piece_resized = piece_img
        
        # 确保类型正确
        bg_roi = bg_roi.astype(np.float32)
        piece_resized = piece_resized.astype(np.float32)
        
        # 加法计算
        added = cv2.add(bg_roi, piece_resized)
        
        # 统计 > 255 的像素数量
        overlap_count = np.sum(added > 255)
        
        return overlap_count
```

### 4.3 第三阶段：验证码检测与求解

#### Step 3.1: 创建验证码检测器 (captcha_detector.py)
```python
class CaptchaDetector:
    """验证码检测器"""
    
    # CSS 选择器配置
    SELECTORS = {
        'captcha_container': '.verifybox',
        'background_image': '.verify-img-panel img:first-child',
        'piece_image': '.verify-sub-block img',
        'slider_button': '.verify-move-block',
    }
    
    def is_captcha_present(self, page: Page) -> bool:
        """检测是否存在验证码"""
        try:
            return page.locator(self.SELECTORS['captcha_container']).is_visible()
        except:
            return False
    
    def capture_element_image(self, page: Page, selector: str) -> np.ndarray:
        """
        截图指定元素
        
        返回 NumPy 数组格式的图像
        """
        # 使用 element.screenshot() 获取二进制
        # 然后用 cv2.imdecode 转换为数组
        element = page.locator(selector)
        screenshot_bytes = element.screenshot()
        
        # 解码为图像
        nparr = np.frombuffer(screenshot_bytes, np.uint8)
        image = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        
        return image
    
    def get_slider_position(self, page: Page) -> tuple:
        """获取滑块按钮位置"""
        element = page.locator(self.SELECTORS['slider_button'])
        box = element.bounding_box()
        # 返回中心点
        return (box['x'] + box['width'] / 2, box['y'] + box['height'] / 2)
```

#### Step 3.2: 创建验证求解器 (solver.py)
```python
class CaptchaSolver:
    """验证求解器"""
    
    def __init__(self, page: Page):
        self.page = page
        self.detector = CaptchaDetector()
        self.image_processor = ImageProcessor()
        self.mouse = MouseController(page)
    
    def solve(self) -> bool:
        """
        执行验证求解
        
        返回: True = 成功, False = 失败
        """
        # Step 1: 捕获验证码图片
        bg_image = self.detector.capture_element_image(
            self.page, 
            self.detector.SELECTORS['background_image']
        )
        piece_image = self.detector.capture_element_image(
            self.page,
            self.detector.SELECTORS['piece_image']
        )
        
        # Step 2: 处理背景图 - 提取白色缺口
        bg_white = self.image_processor.extract_white_regions(bg_image)
        bg_filled = self.image_processor.fill_contours(bg_white)
        gap_boxes = self.image_processor.find_contour_boxes(bg_filled)
        
        # Step 3: 处理拼图板块
        piece_binary = self.image_processor.extract_piece_region(piece_image)
        piece_box = self.image_processor.find_contour_boxes(piece_binary)[0]
        
        # Step 4: 匹配最佳缺口
        best_gap = None
        best_score = 0
        
        for gap_box in gap_boxes:
            # 提取 ROI
            x, y, w, h = gap_box
            bg_roi = bg_white[y:y+h, x:x+w]
            
            # 调整拼图板块大小
            piece_resized = cv2.resize(piece_binary, (w, h))
            
            # 计算重合度
            score = self.image_processor.calculate_overlap_score(bg_roi, piece_resized)
            
            if score > best_score:
                best_score = score
                best_gap = gap_box
        
        if best_gap is None:
            print("未找到匹配的缺口")
            return False
        
        # Step 5: 计算拖拽距离
        drag_distance = self._calculate_distance(piece_box, best_gap)
        
        # Step 6: 执行拖拽
        slider_pos = self.detector.get_slider_position(self.page)
        self.mouse.drag_slider(slider_pos[0], slider_pos[1], drag_distance)
        
        # Step 7: 等待验证结果
        time.sleep(2)
        
        # Step 8: 验证是否成功
        return not self.detector.is_captcha_present(self.page)
    
    def _calculate_distance(self, piece_box, best_gap) -> int:
        """计算拖拽距离"""
        piece_x = piece_box[0]
        gap_x = best_gap[0]
        
        # 补偿值，根据实际情况调整
        distance = gap_x - piece_x + PIECE_COMPENSATION
        
        return max(0, distance)
```

### 4.4 第四阶段：集成与重试机制

#### Step 4.1: 主入口函数
```python
def auto_verify_with_retry(page: Page, max_retry: int = 3) -> bool:
    """
    带重试机制的自动验证
    
    参数:
        page: Playwright Page 对象
        max_retry: 最大重试次数
    
    返回: True = 验证成功, False = 验证失败
    """
    solver = CaptchaSolver(page)
    
    for attempt in range(1, max_retry + 1):
        print(f"尝试第 {attempt}/{max_retry} 次验证...")
        
        # 检查是否存在验证码
        if not solver.detector.is_captcha_present(page):
            print("无需验证")
            return True
        
        # 执行求解
        try:
            success = solver.solve()
            if success:
                print("验证成功!")
                return True
        except Exception as e:
            print(f"验证过程出错: {e}")
        
        # 重试前等待
        if attempt < max_retry:
            time.sleep(RETRY_DELAY)
    
    print("验证失败，已达到最大重试次数")
    return False
```

---

## 五、关键参数调优

### 5.1 图像处理参数
| 参数 | 默认值 | 调整建议 |
|------|--------|----------|
| WHITE_THRESHOLD | 200 | 如果背景有浅色干扰，可提高到 230 |
| MORPHOLOGY_KERNEL | (5, 5) | 缺口越大，核越大 |
| MIN_GAP_AREA | 100 | 根据实际缺口大小调整 |
| PIECE_COMPENSATION | 5 | 可能需要 -5 ~ +10 范围调整 |

### 5.2 鼠标控制参数
| 参数 | 默认值 | 调整建议 |
|------|--------|----------|
| DRAG_STEPS | 10 | 步骤越多越自然 |
| DRAG_DURATION | 500ms | 太快可能被检测 |
| RANDOM_DELAY | 100-300ms | 模拟人类停顿 |

---

## 六、测试计划

### 6.1 单元测试
- [ ] ImageProcessor 图像提取测试
- [ ] 重合度计算算法测试
- [ ] 包围盒计算测试

### 6.2 集成测试
- [ ] 完整验证流程测试
- [ ] 重试机制测试
- [ ] 异常处理测试

### 6.3 实际环境测试
- [ ] 不同网络环境下测试
- [ ] 不同验证码难度测试
- [ ] 多次连续验证测试

---

## 七、可能遇到的问题与解决方案

### 7.1 图像问题
| 问题 | 原因 | 解决方案 |
|------|------|----------|
| 缺口提取不全 | 白色阈值过高 | 降低阈值或改用边缘检测 |
| 拼图板块变形 | CSS transform | 使用实际截图而非样式计算 |

### 7.2 匹配问题
| 问题 | 原因 | 解决方案 |
|------|------|----------|
| 匹配失败 | 缺口与板块尺寸差异 | 缩放后再匹配 |
| 距离计算不准 | 基准点不一致 | 统一使用左上角或中心点 |

### 7.3 验证问题
| 问题 | 原因 | 解决方案 |
|------|------|----------|
| 验证失败 | 拖拽距离不准 | 添加补偿值微调 |
| 永远失败 | 验证码类型变化 | 检测并记录失败特征 |

---

## 八、开发优先级

1. **P0 (必须)**: 图像处理模块 + 基础匹配算法
2. **P1 (重要)**: 鼠标控制器 + 完整求解流程
3. **P2 (优化)**: 重试机制 + 日志记录
4. **P3 (增强)**: 可视化调试 + 参数自动调优

---

## 九、文件清单

| 文件路径 | 描述 |
|----------|------|
| `__init__.py` | 模块导出 |
| `config.py` | 配置参数 |
| `image_processor.py` | 图像处理 |
| `captcha_detector.py` | 验证码检测 |
| `mouse_controller.py` | 鼠标控制 |
| `solver.py` | 验证求解器 |
| `__main__.py` | 命令行入口 |

---

*文档版本: v1.0*
*最后更新: 2026-03-13*

import cv2
import numpy as np
from typing import List, Tuple, Optional


class CaptchaConfig:
    """验证码配置类 - 从配置文件读取或使用默认值"""
    
    def __init__(self):
        # 尝试从配置文件读取
        try:
            from .config import ConfigManager
            config = ConfigManager.get_instance()
            
            # 图像处理参数
            self.WHITE_THRESHOLD = 240
            self.MORPHOLOGY_KERNEL = (3, 3)
            self.MIN_GAP_AREA = 50
            self.PIECE_COMPENSATION = -3
            
            # 拖拽参数（从配置文件读取）
            self.DRAG_STEPS = 30
            self.DRAG_DURATION = config.get_captcha('drag_duration', 1.0)
            
            # 延迟参数
            self.RANDOM_DELAY_MIN = 100
            self.RANDOM_DELAY_MAX = 300
            
            # 重试参数（从配置文件读取）
            self.MAX_RETRY = config.get_captcha('max_retry', 3)
            self.RETRY_DELAY = 1000
            
        except Exception:
            # 如果配置文件读取失败，使用默认值
            self.WHITE_THRESHOLD = 240
            self.MORPHOLOGY_KERNEL = (3, 3)
            self.MIN_GAP_AREA = 50
            self.PIECE_COMPENSATION = -3
            self.DRAG_STEPS = 30
            self.DRAG_DURATION = 1.0
            self.RANDOM_DELAY_MIN = 100
            self.RANDOM_DELAY_MAX = 300
            self.MAX_RETRY = 3
            self.RETRY_DELAY = 1000


def imread_chinese(path: str, flag=cv2.IMREAD_COLOR) -> Optional[np.ndarray]:
    try:
        with open(path, 'rb') as f:
            data = f.read()
        arr = np.frombuffer(data, np.uint8)
        img = cv2.imdecode(arr, flag)
        return img
    except Exception as e:
        print(f"读取图片失败: {e}")
        return None


class ImageProcessor:
    @staticmethod
    def extract_white_regions(image: np.ndarray, threshold: int = 200) -> np.ndarray:
        if len(image.shape) == 3:
            white_mask = np.all(image > threshold, axis=2).astype(np.uint8) * 255
        else:
            white_mask = (image > threshold).astype(np.uint8) * 255
        return white_mask

    @staticmethod
    def extract_piece_region(image: np.ndarray) -> np.ndarray:
        if len(image.shape) == 3 and image.shape[2] == 4:
            alpha = image[:, :, 3]
            return (alpha > 0).astype(np.uint8) * 255
        else:
            return np.ones(image.shape[:2], dtype=np.uint8) * 255

    @staticmethod
    def fill_contours(binary_image: np.ndarray, kernel_size: Tuple[int, int] = (5, 5)) -> np.ndarray:
        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, kernel_size)
        closed = cv2.morphologyEx(binary_image, cv2.MORPH_CLOSE, kernel)
        return closed

    @staticmethod
    def find_contour_boxes(image: np.ndarray, min_area: int = 100) -> List[Tuple[int, int, int, int]]:
        contours, _ = cv2.findContours(image, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        boxes = []
        for contour in contours:
            area = cv2.contourArea(contour)
            if area >= min_area:
                x, y, w, h = cv2.boundingRect(contour)
                boxes.append((x, y, w, h))
        return boxes

    @staticmethod
    def calculate_overlap_addition(bg_roi: np.ndarray, piece_img: np.ndarray) -> float:
        if bg_roi.shape[0] != piece_img.shape[0] or bg_roi.shape[1] != piece_img.shape[1]:
            piece_resized = cv2.resize(piece_img, (bg_roi.shape[1], bg_roi.shape[0]))
        else:
            piece_resized = piece_img

        bg_roi = bg_roi.astype(np.float32)
        piece_resized = piece_resized.astype(np.float32)

        added = cv2.add(bg_roi, piece_resized)
        overlap_count = np.sum(added > 255)

        return float(overlap_count)

    @staticmethod
    def calculate_overlap_iou(bg_roi: np.ndarray, piece_img: np.ndarray) -> float:
        if bg_roi.shape[0] != piece_img.shape[0] or bg_roi.shape[1] != piece_img.shape[1]:
            piece_resized = cv2.resize(piece_img, (bg_roi.shape[1], bg_roi.shape[0]))
        else:
            piece_resized = piece_img

        bg_binary = (bg_roi > 128).astype(np.uint8)
        piece_binary = (piece_resized > 128).astype(np.uint8)

        intersection = np.sum((bg_binary > 0) & (piece_binary > 0))
        union = np.sum((bg_binary > 0) | (piece_binary > 0))

        if union == 0:
            return 0.0

        iou = intersection / union
        return float(iou)

    @staticmethod
    def calculate_overlap_ssim(bg_roi: np.ndarray, piece_img: np.ndarray) -> float:
        try:
            from skimage.metrics import structural_similarity as ssim
        except ImportError:
            return ImageProcessor.calculate_overlap_iou(bg_roi, piece_img)

        if bg_roi.shape[0] != piece_img.shape[0] or bg_roi.shape[1] != piece_img.shape[1]:
            piece_resized = cv2.resize(piece_img, (bg_roi.shape[1], bg_roi.shape[0]))
        else:
            piece_resized = piece_img

        if len(bg_roi.shape) == 3:
            bg_gray = cv2.cvtColor(bg_roi, cv2.COLOR_BGR2GRAY)
        else:
            bg_gray = bg_roi

        if len(piece_resized.shape) == 3:
            piece_gray = cv2.cvtColor(piece_resized, cv2.COLOR_BGR2GRAY)
        else:
            piece_gray = piece_resized

        similarity = ssim(bg_gray, piece_gray)
        return float(similarity)

    @staticmethod
    def calculate_y_overlap_ratio(gap_box: Tuple[int, int, int, int], piece_box: Tuple[int, int, int, int]) -> float:
        """计算两个包围盒在 Y 轴上的重叠比例
        
        Args:
            gap_box: 缺口包围盒 (x, y, w, h)
            piece_box: 拼图包围盒 (x, y, w, h)
            
        Returns:
            float: 重叠比例 (0.0 ~ 1.0)，0 表示无重叠，1 表示完全重叠
        """
        gap_y1 = gap_box[1]
        gap_y2 = gap_box[1] + gap_box[3]
        
        piece_y1 = piece_box[1]
        piece_y2 = piece_box[1] + piece_box[3]
        
        # 计算重叠区域
        overlap_y1 = max(gap_y1, piece_y1)
        overlap_y2 = min(gap_y2, piece_y2)
        
        # 无重叠
        if overlap_y1 >= overlap_y2:
            return 0.0
        
        # 重叠高度
        overlap_height = overlap_y2 - overlap_y1
        
        # 计算重叠比例（相对于拼图块的高度）
        piece_height = piece_box[3]
        if piece_height == 0:
            return 0.0
        
        ratio = overlap_height / piece_height
        return float(ratio)


class CaptchaDetector:
    # 知网验证码固定选择器
    CAPTCHA_CONTAINER = '.verifybox'
    BACKGROUND_IMAGE = '.verify-img-panel img:first-child'
    PIECE_IMAGE = '.verify-sub-block img'
    SLIDER_BUTTON = '.verify-move-block'

    def __init__(self, page=None):
        self.page = page

    def is_captcha_present(self) -> bool:
        if self.page is None:
            return False
        try:
            element = self.page.locator(self.CAPTCHA_CONTAINER).first
            if element.is_visible(timeout=500):
                return True
            return False
        except Exception:
            return False

    def capture_element_image(self, selector: str) -> Optional[np.ndarray]:
        if self.page is None:
            return None
        try:
            import time
            t_start = time.time()
            
            # 直接从 DOM 中获取图片 src，而不是截图
            t1 = time.time()
            src = self.page.eval_on_selector(
                selector,
                "el => el.getAttribute('src')"
            )
            print(f"[计时-图片] eval_on_selector 耗时: {time.time() - t1:.3f}秒")
            
            if not src:
                print(f"无法从元素 {selector} 获取 src 属性")
                return None

            # data URL（base64）
            if src.startswith("data:image"):
                try:
                    t2 = time.time()
                    header, b64_data = src.split(",", 1)
                    img_bytes = np.frombuffer(
                        __import__("base64").b64decode(b64_data),
                        np.uint8
                    )
                    image = cv2.imdecode(img_bytes, cv2.IMREAD_UNCHANGED)
                    print(f"[计时-图片] 解析 base64 耗时: {time.time() - t2:.3f}秒")
                    print(f"[计时-图片] 总耗时: {time.time() - t_start:.3f}秒")
                    return image
                except Exception as e:
                    print(f"解析 data URL 失败: {e}")
                    return None

            # 普通 URL：通过浏览器上下文 fetch，避免额外鉴权问题
            try:
                t3 = time.time()
                byte_list = self.page.evaluate(
                    """async (url) => {
                        const res = await fetch(url);
                        const buf = await res.arrayBuffer();
                        return Array.from(new Uint8Array(buf));
                    }""",
                    src,
                )
                print(f"[计时-图片] fetch 图片耗时: {time.time() - t3:.3f}秒")
                
                t4 = time.time()
                img_bytes = np.frombuffer(bytes(byte_list), np.uint8)
                image = cv2.imdecode(img_bytes, cv2.IMREAD_UNCHANGED)
                print(f"[计时-图片] 解码图片耗时: {time.time() - t4:.3f}秒")
                print(f"[计时-图片] 总耗时: {time.time() - t_start:.3f}秒")
                return image
            except Exception as e:
                print(f"通过 URL 获取图片失败: {e}")
                return None
        except Exception as e:
            print(f"获取图片失败: {e}")
            return None

    def get_slider_position(self) -> Optional[Tuple[float, float]]:
        if self.page is None:
            return None
        try:
            element = self.page.locator(self.SLIDER_BUTTON).first
            box = element.bounding_box()
            if box:
                return (box['x'] + box['width'] / 2, box['y'] + box['height'] / 2)
            return None
        except Exception as e:
            print(f"获取滑块位置失败: {e}")
            return None


class MouseController:
    def __init__(self, page=None):
        self.page = page
        self.config = CaptchaConfig()

    def drag_slider(self, start_x: float, start_y: float, distance: float) -> bool:
        if self.page is None:
            return False

        import random
        import time

        try:
            step_distance = distance / self.config.DRAG_STEPS

            self.page.mouse.move(start_x, start_y)
            self.page.mouse.down()

            for i in range(self.config.DRAG_STEPS):
                current_x = start_x + step_distance * (i + 1)
                random_y = start_y + random.randint(-2, 2)
                self.page.mouse.move(current_x, random_y)
                delay = random.uniform(0.05, 0.15)
                time.sleep(delay)

            self.page.mouse.up()
            return True
        except Exception as e:
            print(f"拖拽失败: {e}")
            return False

    def drag_slider_with_trajectory(self, start_x: float, start_y: float, distance: float, steps: int = 30, duration: float = 1.0) -> bool:
        """使用更自然的轨迹拖拽滑块
        
        模拟人类拖拽特点：
        1. 先快后慢（ease-out）
        2. 轻微的Y轴抖动
        3. 到达目标前有小幅回退
        """
        if self.page is None:
            return False

        import random
        import time

        try:
            trajectory = []
            
            # 生成轨迹点
            for i in range(steps):
                progress = (i + 1) / steps
                
                # 使用 ease-out 曲线：先快后慢
                if progress < 0.8:
                    # 前 80% 快速移动
                    eased_progress = 1 - (1 - progress / 0.8) ** 2
                    eased_progress *= 0.9  # 移动到 90% 位置
                else:
                    # 后 20% 慢速微调
                    eased_progress = 0.9 + (progress - 0.8) / 0.2 * 0.1
                
                current_x = start_x + distance * eased_progress
                
                # Y轴轻微抖动（±3像素）
                random_y = start_y + random.uniform(-3, 3)
                
                # X轴轻微抖动（±1像素）
                random_x = current_x + random.uniform(-1, 1)
                
                # 计算延迟：前期快，后期慢
                if progress < 0.8:
                    step_delay = duration * 0.6 / (steps * 0.8) * random.uniform(0.8, 1.2)
                else:
                    step_delay = duration * 0.4 / (steps * 0.2) * random.uniform(1.0, 1.5)
                
                trajectory.append({
                    'x': random_x,
                    'y': random_y,
                    'delay': step_delay
                })
            
            # 开始拖拽
            self.page.mouse.move(start_x, start_y)
            time.sleep(0.1)  # 短暂停顿
            self.page.mouse.down()
            time.sleep(0.05)  # 按下后短暂停顿
            
            # 执行轨迹
            for point in trajectory:
                self.page.mouse.move(point['x'], point['y'])
                time.sleep(point['delay'])
            
            # 到达目标后短暂停顿再释放
            time.sleep(0.1)
            self.page.mouse.up()
            
            print(f"[拖拽完成] 总距离: {distance:.2f}px, 耗时: {duration:.2f}s")
            return True
            
        except Exception as e:
            print(f"拖拽失败: {e}")
            return False


class CaptchaSolver:
    def __init__(self, page=None):
        self.page = page
        self.config = CaptchaConfig()
        self.detector = CaptchaDetector(page)
        self.image_processor = ImageProcessor()
        self.mouse = MouseController(page)

    def solve(self, method: str = 'iou') -> bool:
        import time
        start_time = time.time()
        
        # 获取背景图片
        print(f"[计时] 开始获取背景图片...")
        t1 = time.time()
        bg_image = self.detector.capture_element_image(self.detector.BACKGROUND_IMAGE)
        print(f"[计时] 获取背景图片耗时: {time.time() - t1:.3f}秒")
        
        # 获取拼图图片
        print(f"[计时] 开始获取拼图图片...")
        t2 = time.time()
        piece_image = self.detector.capture_element_image(self.detector.PIECE_IMAGE)
        print(f"[计时] 获取拼图图片耗时: {time.time() - t2:.3f}秒")

        if bg_image is None or piece_image is None:
            print("无法获取验证码图片")
            return False

        print(f"[计时] 开始图像处理...")
        t3 = time.time()
        bg_white = self.image_processor.extract_white_regions(bg_image, self.config.WHITE_THRESHOLD)
        bg_filled = self.image_processor.fill_contours(bg_white, self.config.MORPHOLOGY_KERNEL)
        gap_boxes = self.image_processor.find_contour_boxes(bg_filled, self.config.MIN_GAP_AREA)

        piece_binary = self.image_processor.extract_piece_region(piece_image)
        piece_boxes = self.image_processor.find_contour_boxes(piece_binary, self.config.MIN_GAP_AREA)
        print(f"[计时] 图像处理耗时: {time.time() - t3:.3f}秒")

        if not gap_boxes:
            print("未找到缺口")
            return False

        if not piece_boxes:
            print("未找到拼图板块")
            return False

        # 只使用第一个包围盒作为拼图主体区域，并裁剪出真实轮廓区域
        piece_box = piece_boxes[0]
        px, py, pw, ph = piece_box
        piece_mask = piece_binary[py:py+ph, px:px+pw]

        print(f"[计时] 开始两步筛选匹配，共 {len(gap_boxes)} 个候选缺口...")
        print(f"[拼图包围盒] X={px}, Y={py}, W={pw}, H={ph}")
        t4 = time.time()
        
        # ========== 第一步：Y 轴重叠筛选 ==========
        print(f"\n[第一步] Y 轴重叠筛选...")
        y_overlap_candidates = []
        
        for idx, gap_box in enumerate(gap_boxes):
            x, y, w, h = gap_box
            
            # 计算 Y 轴重叠比例
            y_overlap_ratio = self.image_processor.calculate_y_overlap_ratio(gap_box, piece_box)
            
            print(f"  缺口 {idx}: X={x}, Y={y}, W={w}, H={h}, Y轴重叠={y_overlap_ratio:.2f}")
            
            # 只保留有重叠的候选（重叠比例 > 0）
            if y_overlap_ratio > 0:
                y_overlap_candidates.append({
                    'index': idx,
                    'box': gap_box,
                    'y_overlap_ratio': y_overlap_ratio
                })
        
        print(f"\n[第一步结果] 筛选出 {len(y_overlap_candidates)} 个 Y 轴有重叠的候选")
        
        if len(y_overlap_candidates) == 0:
            print("[匹配失败] 没有找到 Y 轴重叠的缺口")
            return False
        
        # 如果只有一个候选，直接使用
        if len(y_overlap_candidates) == 1:
            best_gap = y_overlap_candidates[0]['box']
            best_score = y_overlap_candidates[0]['y_overlap_ratio']
            print(f"[匹配成功] 只有一个候选，直接使用: 缺口 {y_overlap_candidates[0]['index']}")
        else:
            # ========== 第二步：像素匹配检查 ==========
            print(f"\n[第二步] 对 {len(y_overlap_candidates)} 个候选进行像素匹配...")
            
            best_gap = None
            best_score = -1
            
            for candidate in y_overlap_candidates:
                gap_box = candidate['box']
                x, y, w, h = gap_box
                
                if y + h > bg_image.shape[0] or x + w > bg_image.shape[1]:
                    continue
                
                # 背景中的当前缺口区域
                bg_roi = bg_white[y:y+h, x:x+w]
                
                # 使用裁剪后的拼图轮廓进行匹配
                if method == 'iou':
                    score = self.image_processor.calculate_overlap_iou(bg_roi, piece_mask)
                elif method == 'ssim':
                    score = self.image_processor.calculate_overlap_ssim(bg_roi, piece_mask)
                else:
                    score = self.image_processor.calculate_overlap_addition(bg_roi, piece_mask)
                
                print(f"  缺口 {candidate['index']}: Y重叠={candidate['y_overlap_ratio']:.2f}, 像素匹配={score:.4f}")
                
                if score > best_score:
                    best_score = score
                    best_gap = gap_box
            
            print(f"\n[第二步结果] 最佳匹配分数: {best_score:.4f}")

        print(f"[计时] 匹配计算耗时: {time.time() - t4:.3f}秒")
        print(f"[最终结果] 方法: {method}, 最佳分数: {best_score:.4f}")

        if best_gap is None:
            print("未找到匹配的缺口")
            return False

        drag_distance = self._calculate_distance(piece_box, best_gap)

        print(f"[计时] 开始获取滑块位置...")
        t5 = time.time()
        slider_pos = self.detector.get_slider_position()
        if slider_pos is None:
            print("无法获取滑块位置")
            return False
        print(f"[计时] 获取滑块位置耗时: {time.time() - t5:.3f}秒")

        print(f"[计时] 总耗时（拖拽前）: {time.time() - start_time:.3f}秒")
        print(f"[距离计算] 板块X: {piece_box[0]}, 缺口X: {best_gap[0]}, 最终距离: {drag_distance}")

        print(f"[计时] 开始拖拽...")
        t6 = time.time()
        success = self.mouse.drag_slider_with_trajectory(
            slider_pos[0], slider_pos[1], drag_distance,
            duration=self.config.DRAG_DURATION
        )
        print(f"[计时] 拖拽耗时: {time.time() - t6:.3f}秒")

        if not success:
            return False

        time.sleep(2)

        return not self.detector.is_captcha_present()

    def _calculate_distance(self, piece_box: Tuple[int, int, int, int], best_gap: Tuple[int, int, int, int]) -> float:
        """计算拖拽距离
        
        知网验证码特点：
        - 拼图块的初始位置在左侧
        - 需要拖动到缺口位置
        - 距离 = 缺口X坐标 - 拼图块X坐标 + 微调
        """
        piece_x = piece_box[0]
        gap_x = best_gap[0]
        
        # 基础距离：缺口位置 - 拼图位置
        base_distance = gap_x - piece_x
        
        # 添加补偿（根据实际测试调整）
        distance = base_distance + self.config.PIECE_COMPENSATION
        
        print(f"[距离计算详情] 拼图X={piece_x}, 缺口X={gap_x}, 基础距离={base_distance}, 补偿={self.config.PIECE_COMPENSATION}, 最终={distance}")
        
        return max(0, distance)


def auto_verify_with_retry(page, max_retry: int = 3, method: str = 'iou', drag_duration: float = 1.0) -> bool:
    solver = CaptchaSolver(page)
    # 设置拖拽时长
    solver.config.DRAG_DURATION = drag_duration

    for attempt in range(1, max_retry + 1):
        print(f"尝试第 {attempt}/{max_retry} 次验证...")

        if not solver.detector.is_captcha_present():
            print("无需验证")
            return True

        try:
            success = solver.solve(method)
            if success:
                print("验证成功!")
                return True
        except Exception as e:
            print(f"验证过程出错: {e}")

        if attempt < max_retry:
            import time
            time.sleep(solver.config.RETRY_DELAY / 1000)

    print("验证失败，已达到最大重试次数")
    return False


def test_with_local_images(
    bg_path: str,
    piece_path: str,
    method: str = 'iou'
) -> Tuple[Optional[Tuple[int, int, int, int]], float, List[dict]]:
    config = CaptchaConfig()
    processor = ImageProcessor()

    bg_image = imread_chinese(bg_path)
    piece_image = imread_chinese(piece_path, cv2.IMREAD_UNCHANGED)

    if bg_image is None:
        print(f"无法读取背景图: {bg_path}")
        return None, 0, []

    if piece_image is None:
        print(f"无法读取拼图: {piece_path}")
        return None, 0, []

    bg_white = processor.extract_white_regions(bg_image, config.WHITE_THRESHOLD)
    bg_filled = processor.fill_contours(bg_white, config.MORPHOLOGY_KERNEL)
    gap_boxes = processor.find_contour_boxes(bg_filled, config.MIN_GAP_AREA)

    piece_binary = processor.extract_piece_region(piece_image)
    piece_boxes = processor.find_contour_boxes(piece_binary, config.MIN_GAP_AREA)

    if not gap_boxes:
        print("未找到缺口")
        return None, 0, []

    if not piece_boxes:
        print("未找到拼图板块")
        return None, 0, []

    # 同样裁剪出拼图主体轮廓区域，保证与在线求解逻辑一致
    piece_box = piece_boxes[0]
    px, py, pw, ph = piece_box
    piece_mask = piece_binary[py:py+ph, px:px+pw]

    print(f"[拼图包围盒] X={px}, Y={py}, W={pw}, H={ph}")
    
    # ========== 第一步：Y 轴重叠筛选 ==========
    print(f"\n[第一步] Y 轴重叠筛选，共 {len(gap_boxes)} 个候选缺口...")
    y_overlap_candidates = []
    
    for idx, gap_box in enumerate(gap_boxes):
        x, y, w, h = gap_box
        
        # 计算 Y 轴重叠比例
        y_overlap_ratio = processor.calculate_y_overlap_ratio(gap_box, piece_box)
        
        print(f"  缺口 {idx}: X={x}, Y={y}, W={w}, H={h}, Y轴重叠={y_overlap_ratio:.2f}")
        
        # 只保留有重叠的候选（重叠比例 > 0）
        if y_overlap_ratio > 0:
            y_overlap_candidates.append({
                'index': idx,
                'box': gap_box,
                'y_overlap_ratio': y_overlap_ratio
            })
    
    print(f"\n[第一步结果] 筛选出 {len(y_overlap_candidates)} 个 Y 轴有重叠的候选")
    
    if len(y_overlap_candidates) == 0:
        print("[匹配失败] 没有找到 Y 轴重叠的缺口")
        return None, 0, []
    
    best_gap = None
    best_score = -1
    score_details = []
    
    # 如果只有一个候选，直接使用
    if len(y_overlap_candidates) == 1:
        best_gap = y_overlap_candidates[0]['box']
        best_score = y_overlap_candidates[0]['y_overlap_ratio']
        print(f"[匹配成功] 只有一个候选，直接使用: 缺口 {y_overlap_candidates[0]['index']}")
        score_details.append({
            'gap_index': y_overlap_candidates[0]['index'],
            'gap_box': best_gap,
            'y_overlap': y_overlap_candidates[0]['y_overlap_ratio'],
            'pixel_score': best_score
        })
    else:
        # ========== 第二步：像素匹配检查 ==========
        print(f"\n[第二步] 对 {len(y_overlap_candidates)} 个候选进行像素匹配...")
        
        for candidate in y_overlap_candidates:
            gap_box = candidate['box']
            x, y, w, h = gap_box
            
            if y + h > bg_image.shape[0] or x + w > bg_image.shape[1]:
                continue
            
            bg_roi = bg_white[y:y+h, x:x+w]
            
            if method == 'iou':
                score = processor.calculate_overlap_iou(bg_roi, piece_mask)
            elif method == 'ssim':
                score = processor.calculate_overlap_ssim(bg_roi, piece_mask)
            else:
                score = processor.calculate_overlap_addition(bg_roi, piece_mask)
            
            print(f"  缺口 {candidate['index']}: Y重叠={candidate['y_overlap_ratio']:.2f}, 像素匹配={score:.4f}")
            
            score_details.append({
                'gap_index': candidate['index'],
                'gap_box': gap_box,
                'y_overlap': candidate['y_overlap_ratio'],
                'pixel_score': score
            })
            
            if score > best_score:
                best_score = score
                best_gap = gap_box
        
        print(f"\n[第二步结果] 最佳匹配分数: {best_score:.4f}")

    print(f"\n[最终结果] 方法: {method}, 最佳分数: {best_score:.4f}")
    for detail in score_details:
        print(f"  缺口 {detail['gap_index']}: {detail['gap_box']}, Y重叠={detail.get('y_overlap', 0):.2f}, 像素匹配={detail.get('pixel_score', 0):.4f}")

    return best_gap, best_score, score_details


if __name__ == "__main__":
    import sys
    import os

    base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    bg_path = os.path.join(base_dir, "SourcePage", "安全验证_files", "background", "bg_1.png")
    piece_path = os.path.join(base_dir, "SourcePage", "安全验证_files", "frame", "f_1.png")

    if len(sys.argv) > 1:
        bg_path = sys.argv[1]
    if len(sys.argv) > 2:
        piece_path = sys.argv[2]

    bg_path = bg_path.replace('/', os.sep).replace('\\', os.sep)
    piece_path = piece_path.replace('/', os.sep).replace('\\', os.sep)

    print(f"测试图片: {bg_path} + {piece_path}")
    print("-" * 50)

    print("\n=== 方法1: 加法计算 ===")
    best_gap, best_score, details = test_with_local_images(bg_path, piece_path, 'addition')

    print("\n=== 方法2: IoU ===")
    best_gap, best_score, details = test_with_local_images(bg_path, piece_path, 'iou')

    print("\n=== 方法3: SSIM ===")
    best_gap, best_score, details = test_with_local_images(bg_path, piece_path, 'ssim')

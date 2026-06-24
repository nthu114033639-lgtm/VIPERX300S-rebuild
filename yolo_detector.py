#!/usr/bin/env python3
import rclpy
from rclpy.node import Node
from sensor_msgs.msg import Image, CameraInfo
from cv_bridge import CvBridge
import cv2
from image_geometry import PinholeCameraModel
from geometry_msgs.msg import TransformStamped
from tf2_ros import TransformBroadcaster
from rclpy.qos import qos_profile_sensor_data
from ultralytics import YOLO

class YoloDetector(Node):
    def __init__(self):
        super().__init__('yolo_detector')
        self.bridge = CvBridge()
        
        # 載入 YOLOv8 官方預訓練模型 (第一次執行會自動下載 yolov8n.pt)
        self.get_logger().info("⏳ 正在載入 YOLOv8 模型...")
        self.model = YOLO('yolov8n.pt')
        self.get_logger().info("✅ 模型載入完成！開始辨識...")
        
        # 初始化深度圖與相機模型
        self.depth_image = None
        self.camera_model = PinholeCameraModel()
        self.camera_info_received = False
        
        # 訂閱彩色影像、深度影像、相機內參 (加入 QoS Sensor Data 設定)
        self.create_subscription(
            Image, '/camera/camera/color/image_raw', self.color_callback, qos_profile_sensor_data)
        self.create_subscription(
            Image, '/camera/camera/aligned_depth_to_color/image_raw', self.depth_callback, qos_profile_sensor_data)
        self.create_subscription(
            CameraInfo, '/camera/camera/color/camera_info', self.info_callback, qos_profile_sensor_data)
            
        # 發布影像與 TF
        self.publisher = self.create_publisher(Image, '/yolo/annotated_image', 10)
        self.tf_broadcaster = TransformBroadcaster(self)

    def info_callback(self, msg):
        if not self.camera_info_received:
            self.camera_model.fromCameraInfo(msg)
            self.camera_info_received = True
            self.get_logger().info("✅ 成功接收到相機內參！")

    def depth_callback(self, msg):
        # 將深度圖轉換為 OpenCV 格式 (16UC1, 單位: 毫米 mm)
        try:
            self.depth_image = self.bridge.imgmsg_to_cv2(msg, "16UC1")
        except Exception as e:
            self.get_logger().error(f"深度圖轉換失敗: {e}")

    def color_callback(self, msg):
        # 必須等深度圖和相機資訊都到位才開始處理
        if self.depth_image is None or not self.camera_info_received:
            self.get_logger().info("⏳ 收到彩色畫面，但還在等待「深度圖」或「相機內參」...", throttle_duration_sec=3.0)
            return
            
        try:
            cv_image = self.bridge.imgmsg_to_cv2(msg, "bgr8")
            results = self.model(cv_image, verbose=False)
            
            boxes = results[0].boxes
            annotated_frame = results[0].plot()
            
            if len(boxes) > 0:
                # 只取第一個 (信心度最高) 的物件
                box = boxes[0]
                class_name = self.model.names[int(box.cls[0])]
                
                # 1. 取得 bounding box 的中心像素座標 (u, v)
                x1, y1, x2, y2 = box.xyxy[0].cpu().numpy()
                u = int((x1 + x2) / 2)
                v = int((y1 + y2) / 2)
                
                # 確保中心點在影像範圍內
                h, w = self.depth_image.shape
                if 0 <= u < w and 0 <= v < h:
                    # 2. 取得該點的深度 (z 軸距離)，並將 mm 轉換為 m
                    depth_mm = self.depth_image[v, u]
                    if depth_mm > 0:
                        depth_m = depth_mm / 1000.0
                        
                        # 3. 相機內參轉換 (Deprojection): 2D -> 3D
                        fx = self.camera_model.fx()
                        fy = self.camera_model.fy()
                        cx = self.camera_model.cx()
                        cy = self.camera_model.cy()
                        
                        x_cam = (u - cx) * depth_m / fx
                        y_cam = (v - cy) * depth_m / fy
                        z_cam = depth_m
                        
                        # 在畫面上畫一個紅色十字準星，標示測距位置
                        cv2.drawMarker(annotated_frame, (u, v), (0, 0, 255), cv2.MARKER_CROSS, 20, 2)
                        self.get_logger().info(f"🎯 鎖定 {class_name}！座標: X:{x_cam:.2f}, Y:{y_cam:.2f}, Z:{z_cam:.2f} m")
                        
                        # 4. 發布 TF 座標
                        self.publish_target_tf(x_cam, y_cam, z_cam, class_name, msg.header.stamp)

            # 發布畫好框與準星的影像
            annotated_msg = self.bridge.cv2_to_imgmsg(annotated_frame, "bgr8")
            annotated_msg.header = msg.header
            self.publisher.publish(annotated_msg)
            
        except Exception as e:
            self.get_logger().error(f"影像處理錯誤: {e}")

    def publish_target_tf(self, x, y, z, name, stamp):
        t = TransformStamped()
        t.header.stamp = stamp
        t.header.frame_id = 'camera_color_optical_frame'
        t.child_frame_id = f'target_{name}'
        
        t.transform.translation.x = float(x)
        t.transform.translation.y = float(y)
        t.transform.translation.z = float(z)
        t.transform.rotation.w = 1.0
        
        self.tf_broadcaster.sendTransform(t)

def main(args=None):
    rclpy.init(args=args)
    node = YoloDetector()
    rclpy.spin(node)
    rclpy.shutdown()

if __name__ == '__main__':
    main()
# ViperX-300S 手臂校正與常見問題排除指南

本文件記錄了自行組裝 ViperX-300S 機械手臂後，如何透過軟體與硬體調整馬達狀態，解決 RViz2 顯示與實體不符的問題。

## 1. 調整手臂原點 (Homing Offset)
由於自行組裝時可能錯位，需透過 Dynamixel Wizard 2.0 設定各軸的原點：
1. 開啟 Dynamixel Wizard，關閉所有馬達的 **Torque**。
2. 將手臂手動擺正為「絕對零度」姿態 (整隻手臂筆直朝上方)。
3. 在各軸馬達的 Address 20 (`Homing Offset`) 寫入補償值，計算方式為：`新 Offset = 舊 Offset + (2048 - 物理擺正時的 Present Position 讀值)`。
4. **注意**：如果補償值超出範圍 (超過 ±1044)，表示當初組裝相差了 180 度，請務必「拆下該關節金屬件，旋轉半圈後重新鎖回」，否則 Homing Offset 將無效。

*註：Homing Offset 寫入馬達 EEPROM 即生效，**不會**被 ROS2 設定檔覆蓋。*

## 2. 馬達作動極限與方向被重置的問題
在執行 `xsarm_control` (ROS 驅動) 時，系統會優先讀取 `ros2_ws/src/interbotix_ros_manipulators/interbotix_ros_xsarms/interbotix_xsarm_control/config/vx300s.yaml` 設定檔。
- **Min/Max Position Limit**：若在 Dynamixel Wizard 調整極限，每次啟動 ROS 都會被上述 `.yaml` 檔覆蓋。因此，若需修改極限，請直接修改 `.yaml`。
- **作動方向反轉 (Drive Mode)**：若發現特定馬達 (如 ID 7, ID 9) 旋轉方向與 RViz 內的方向相反，請前往 `.yaml` 檔尋找對應馬達的 `Drive_Mode` 參數。`0` 表示正向，`1` 表示反轉，根據需求修改即可。

## 3. 修改 YAML 設定後的編譯與啟動步驟
因為修改了 ROS workspace (`ros2_ws`) 的原始碼，必須在 Docker 容器內重新進行建置，新設定才會生效。

**步驟：**
1. 啟動並進入 Docker 容器：
  
   # (主機端) 開放圖形介面權限與 USB 權限
   xhost +local:docker
   sudo chmod 777 /dev/ttyUSB*
   
   # (主機端) 進入 docker 目錄並啟動環境
   cd ~/jerry/viperx300s-VLA/docker
   ./run.sh
   
   # (主機端) 進入容器終端機
   docker exec -it viperx300s_robot bash
   
2. 在 Docker 容器內重新編譯工作區：
   
   cd /workspace/ros2_ws
   colcon build --symlink-install
   source install/setup.bash
   
3. 驗證修改結果：
   
   ros2 launch interbotix_xsarm_control xsarm_control.launch.py robot_model:=vx300s
   

## 4. 控制機器手臂的兩種方式（一樣在docker內）

確認校正完畢且 RViz2 顯示與實體同步後，可透過以下兩種方式操作手臂：

### 方式一：使用 MoveIt2 手動圖形化控制 (基礎測試推薦)
不需撰寫程式，直接透過 RViz2 的圖形介面拖曳手臂，用來確保運動學與避障功能正常。

**啟動指令：**
```bash
ros2 launch interbotix_xsarm_moveit xsarm_moveit.launch.py robot_model:=vx300s hardware_type:=actual
```

**操作方式與注意事項：**
1. 啟動後在 RViz2 畫面中，拖曳末端夾爪出現的互動式箭頭 (Interactive Markers) 移至想去的位置。
2. 點擊左下角 **MotionPlanning** 面板的 **"Plan & Execute"** 執行動作。
3. **回到初始起點：** 在 MotionPlanning 面板內展開 **"Planning Request"**，將 **"Select Goal State"** 選單設定為 `Sleep` (安全收納姿態) 或 `Home` (預設伸直姿勢)，再按 "Plan & Execute" 即可讓機器人自動收回。
4. **切勿點擊 RViz2 左下角的 `Reset`**：這只是畫面引擎重置按鈕，並非實體歸零。誤按會導致 TF 座標暫時丟失而讓畫面出現「身首分離」的錯覺。若不慎按到，只要再隨意拖曳執行一次移動指令更新坐標，或重新開啟程式即可恢復。

### 方式二：啟動完整的 VLA 視覺伺服系統
啟動專案核心功能，讓手臂依據 Intel RealSense 相機擷取之影像進行自動追蹤與控制。

**啟動步驟：**
需要開啟 **4 個獨立的終端機**，分別執行 `docker exec -it viperx300s_robot bash` 進入容器後，依序啟動：

**終端機 1 (視覺模型控制器)：**

ros2 launch vlpoint controller.launch.py

**終端機 2 (視覺處理工作節點)：**

ros2 launch vlpoint worker.launch.py

**終端機 3 (啟動手臂底層與路徑規劃 MoveIt2)：**

ros2 launch interbotix_xsarm_moveit xsarm_moveit.launch.py robot_model:=vx300s hardware_type:=actual

**終端機 4 (視覺伺服追蹤程式)：**

ros2 launch vlservo vlservoing.launch.py


## 5. 連接與啟動 Intel RealSense 相機 (視覺處理前置準備)

因為 Docker 容器需要在啟動時抓取主機的硬體清單，要讓 Docker 順利讀到相機，**請務必在啟動容器前插好 USB**。

**連接步驟：**
1. **硬體連接：** 將 Intel RealSense 相機插入電腦主機的 **USB 3.0 (藍色) 以上的孔位** (USB 2.0 可能會造成頻寬不足無法正常傳輸影像)。
2. **開放存取權限 (在主機端電腦)：**
   開啟主機的終端機，執行以下指令讓所有 USB 與影像設備皆有讀寫權限：
   
   sudo chmod -R 777 /dev/bus/usb/
   sudo chmod 777 /dev/video*
   
3. **啟動 Docker 容器：**
   這時候再回到 `docker/` 資料夾中執行 `./run.sh`。由於你的 `docker-compose.yml` 已經預先寫好了 `/dev/video*` 與 `/dev/bus/usb` 的掛載關聯，此時容器內部就已經持有相機了。
4. **驗證相機是否成功連線：**
   進入 Docker 容器後 (`docker exec -it viperx300s_robot bash`)，輸入以下指令來測試連線：
   
   rs-enumerate-devices
   
   如果有印出相機的名稱 (如 Intel RealSense D435i)、序號與各種支援的解析度清單，就代表相機已經完美連上，可以放心執行上面的「方式二：視覺伺服系統」了！

進到 Docker 容器後，只要打 rs-enumerate-devices 這個官方工具指令，如果畫面噴出一大串相機的序號跟支援的解析度清單，就代表成功讀到，可以接著繼續玩視覺追蹤了！

每次重開機/平常開發的日常使用流程】

先插上手臂 USB 跟相機 USB，執行 sudo chmod 777 /dev/ttyUSB* /dev/video*。
進入 docker 資料夾，執行 ./run.sh。

如果要在這個黑盒子裡開多個終端機跑程式，就在主機端開新的終端機，用 docker exec -it viperx300s_robot bash 鑽進去下指令。
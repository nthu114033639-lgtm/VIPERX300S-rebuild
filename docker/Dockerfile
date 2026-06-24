# Minimal LLM + ROS 2 Humble (GPU-ready) + Interbotix ViperX-300S
FROM nvidia/cuda:12.8.0-runtime-ubuntu22.04

# 設定環境
ENV DEBIAN_FRONTEND=noninteractive \
    TZ=Asia/Taipei \
    LANG=en_US.UTF-8 \
    LC_ALL=en_US.UTF-8 \
    ROS_DISTRO=humble \
    PIP_NO_CACHE_DIR=1 \
    PIP_BREAK_SYSTEM_PACKAGES=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    YOLO_CONFIG_DIR=/workspace/.ultralytics \
    ROS_DOMAIN_ID=15 \
    ROS_LOCALHOST_ONLY=0

# STEP 1: 設定基礎環境與 ROS 2 軟體來源 (Software Sources)
RUN apt-get update && apt-get install -y --no-install-recommends \
    gnupg2 \
    lsb-release \
    curl \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/* # 清理快取

RUN curl -sSL https://raw.githubusercontent.com/ros/rosdistro/master/ros.key -o /usr/share/keyrings/ros-archive-keyring.gpg
RUN echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/ros-archive-keyring.gpg] http://packages.ros.org/ros2/ubuntu $(. /etc/os-release && echo $UBUNTU_CODENAME) main" | tee /etc/apt/sources.list.d/ros2.list > /dev/null

# STEP 2: 安裝所有需要的系統套件 (APT Packages)
# 基本工具與開發套件
RUN apt-get update && apt-get install -y --no-install-recommends \
    git wget curl vim nano \
    locales \
    python3 \
    python3-pip \
    python3-dev \
    python3-zmq \
    python3-opencv \
    build-essential cmake \
    software-properties-common \
    sudo \
    udev \
    usbutils \
    libasound2-dev \
    ffmpeg \
    libsm6 \
    libxext6 \
    libxrender-dev \
    unzip \
    qtbase5-dev \
    qtchooser \
    qt5-qmake \
    qtbase5-dev-tools \
    python3-pyqt5 \
    libxkbcommon-x11-0 \
    libxcb-icccm4 \
    libxcb-image0 \
    libxcb-keysyms1 \
    libxcb-randr0 \
    libxcb-render-util0 \
    libxcb-xinerama0 \
    libxcb-xinput0 \
    libxcb-xfixes0 \
    x11-apps \
    && locale-gen en_US en_US.UTF-8 \
    && update-locale LANG=en_US.UTF-8 LC_ALL=en_US.UTF-8 \
    && rm -rf /var/lib/apt/lists/*

# ROS 2 Humble Desktop Full and ROS tooling
RUN apt-get update && apt-get install -y --no-install-recommends \
    ros-humble-desktop-full \
    ros-humble-realsense2-camera \
    ros-humble-realsense2-camera-msgs \
    ros-humble-realsense2-description \
    python3-colcon-common-extensions \
    python3-rosdep \
    python3-argcomplete \
    whiptail \
    iproute2 \
    python3-colcon-common-extensions \
    python3-rosdep \
    python3-vcstool \
    python3-argcomplete \
    whiptail \
    iproute2 \
    ros-humble-rviz2 \
    ros-humble-rqt \
    ros-humble-rqt-common-plugins \
    ros-humble-tf2-tools \
    ros-humble-tf-transformations \
    ros-humble-joint-state-publisher \
    ros-humble-joint-state-publisher-gui \
    ros-humble-robot-state-publisher \
    ros-humble-xacro \
    && rm -rf /var/lib/apt/lists/*

# MoveIt2
RUN apt-get update && apt-get install -y --no-install-recommends \
    ros-humble-moveit \
    ros-humble-moveit-msgs \
    ros-humble-moveit-servo \
    ros-humble-moveit-ros-perception \
    && rm -rf /var/lib/apt/lists/*


# Dynamixel SDK 和 ros2_control 相關套件 (Interbotix 需要)
RUN apt-get update && apt-get install -y --no-install-recommends \
    ros-humble-dynamixel-sdk \
    ros-humble-controller-manager \
    ros-humble-joint-state-broadcaster \
    ros-humble-joint-trajectory-controller \
    ros-humble-ros2-control \
    ros-humble-ros2-controllers \
    && rm -rf /var/lib/apt/lists/*

# AprilTag 相關套件 (用於視覺定位)
RUN apt-get update && apt-get install -y --no-install-recommends \
    ros-humble-apriltag \
    ros-humble-image-transport \
    ros-humble-cv-bridge \
    ros-humble-image-geometry \
    libopencv-dev \
    libfreeimage-dev \
    && rm -rf /var/lib/apt/lists/* # 在所有 apt-get install 的最後清理一次
# Use bash for subsequent RUN commands so we can 'source'
SHELL ["/bin/bash", "-lc"]

# STEP 3: 初始化 rosdep (ROS Dependency Tool)
RUN rosdep init 2>/dev/null || true && rosdep update


# STEP 4: 安裝所有 Python 套件
# Python dependencies - 使用 constraints 鎖定版本避免衝突
# 1. 先安裝基礎套件
RUN pip3 install 'pip<25' 'setuptools<80,>=68' 'wheel>=0.40' 'packaging>=24.0'

# 2. 建立 constraints 文件，鎖定 numpy 1.x
RUN printf "numpy==1.26.4\nsympy==1.14.0\nmpmath>=1.3.0\n" > /tmp/constraints.txt

# 3. 安裝 numpy 和科學計算套件
RUN pip3 install -c /tmp/constraints.txt numpy==1.26.4 && \
    pip3 install --no-cache-dir 'scipy>=1.11,<1.12'

# 4. 安裝 sympy (避免 distutils 衝突)
RUN pip3 install --ignore-installed -c /tmp/constraints.txt sympy==1.14.0 "mpmath>=1.3.0"

# 5. 安裝 PyTorch (CUDA 12.8 版本)
RUN pip3 install -c /tmp/constraints.txt --index-url https://download.pytorch.org/whl/cu128 \
    torch torchvision torchaudio

# 6. 安裝 AI/ML 相關套件
RUN pip3 install -c /tmp/constraints.txt \
    transformers \
    accelerate \
    bitsandbytes \
    soundfile \
    ultralytics \
    sentencepiece \
    protobuf

# 7. 安裝 Web/UI 套件
RUN pip3 install -c /tmp/constraints.txt \
    fastapi==0.112.4 \
    uvicorn[standard] \
    gradio==4.16.0 \
    PyQt5>=5.15.0

# 8. 安裝機器人相關 Python 套件
RUN pip3 install -c /tmp/constraints.txt \
    modern_robotics \
    pyserial \
    urchin

# 9. 升級 transforms3d 到支援 NumPy 1.26+ 的版本 (修復 np.float 相容性問題)
RUN pip3 install --upgrade transforms3d>=0.4.2

# STEP 5: 設定硬體權限與 Shell 環境
# udev 規則 (為 Dynamixel U2D2 和 RealSense)
RUN echo 'SUBSYSTEM=="usb", ATTRS{idVendor}=="0bda", ATTRS{idProduct}=="0411", MODE="0666"' > /etc/udev/rules.d/99-realsense.rules && \
    echo 'SUBSYSTEM=="usb", ATTRS{idVendor}=="8087", MODE="0666"' >> /etc/udev/rules.d/99-realsense.rules && \
    echo 'SUBSYSTEM=="tty", ATTRS{idVendor}=="0403", MODE="0666"' > /etc/udev/rules.d/99-interbotix.rules && \
    echo 'SUBSYSTEM=="tty", ATTRS{idVendor}=="0403", ATTRS{idProduct}=="6014", MODE="0666", GROUP="dialout"' >> /etc/udev/rules.d/99-interbotix.rules

# 將 root 用戶加入 dialout 組 (允許訪問串口設備)
RUN usermod -aG dialout root


# 安裝穩定版本的 Pillow（與 torch、transformers 相容）
RUN pip3 install pillow==10.2.0

WORKDIR /workspace

# Copy entire project into the image
COPY . /workspace

# Bootstrap a ros2_ws (non-fatal if empty)
RUN mkdir -p /workspace/ros2_ws/src && \
    source /opt/ros/${ROS_DISTRO}/setup.bash && \
    cd /workspace/ros2_ws && colcon build --symlink-install || true

# 預設進入容器後 source ROS2 & workspace
RUN echo "source /opt/ros/humble/setup.bash" >> /root/.bashrc && \
    echo "if [ -f /workspace/ros2_ws/install/setup.bash ]; then source /workspace/ros2_ws/install/setup.bash; fi" >> /root/.bashrc && \
    echo "export PS1='\\u@\\h:\\w# '" >> /root/.bashrc && \
    echo "echo 'ROS2 Humble + GPU + Interbotix ViperX-300S 環境已就緒!'" >> /root/.bashrc

# Ensure login shells also load .bashrc (for docker exec -it bash -l)
RUN printf '%s\n' "if [ -f ~/.bashrc ]; then" \
    ". ~/.bashrc" \
    "fi" > /root/.bash_profile

# Keep container alive for interactive work
CMD ["sleep", "infinity"]

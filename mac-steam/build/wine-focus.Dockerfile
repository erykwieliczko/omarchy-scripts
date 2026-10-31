FROM ubuntu:24.04
RUN apt-get -qq update && DEBIAN_FRONTEND=noninteractive apt-get -qq install -y --no-install-recommends \
    build-essential autoconf bison flex pkg-config python3 perl \
    libx11-dev libxext-dev libxrender-dev libxi-dev libxrandr-dev libxfixes-dev \
    libxcursor-dev libxcomposite-dev libxxf86vm-dev libxinerama-dev libfreetype6-dev \
    libfontconfig1-dev libvulkan-dev libgl-dev libegl-dev libglx-dev \
    libxpresent-dev libxshmfence-dev \
    && rm -rf /var/lib/apt/lists/*

FROM registry.gitlab.com/mlamarre/vulkan
LABEL MAINTAINER mlamarre@vlam3d.com

RUN apt-get update && apt-get install -y --no-install-recommends \
software-properties-common \
build-essential \
ca-certificates \
git \
wget \
unzip \
yasm \
pkg-config \
libcurl4-openssl-dev \
zlib1g-dev \
nano \
python3 \
python3-distutils \
libx11-xcb-dev \
libegl1-mesa-dev

# Install cmake version 3.15
RUN wget https://github.com/Kitware/CMake/releases/download/v3.15.2/cmake-3.15.2-Linux-x86_64.tar.gz && \
    tar -xvf cmake-3.15.2-Linux-x86_64.tar.gz && cp cmake-3.15.2-Linux-x86_64/bin/cmake /usr/local/bin && \
    mkdir -p /usr/local/share/cmake-3.15 && \
    cp -r cmake-3.15.2-Linux-x86_64/share/cmake-3.15/* /usr/local/share/cmake-3.15 && \
    rm -rf cmake-3.15.2-Linux-x86_64*

WORKDIR /tmp
RUN mkdir -p /root/.conda && \
    wget --quiet https://repo.anaconda.com/miniconda/Miniconda3-latest-Linux-x86_64.sh -O ~/miniconda.sh && \
    /bin/bash ~/miniconda.sh -b -p /opt/conda && \
    rm ~/miniconda.sh && \
    /opt/conda/bin/conda clean -tipsy && \
    ln -s /opt/conda/etc/profile.d/conda.sh /etc/profile.d/conda.sh && \
    echo ". /opt/conda/etc/profile.d/conda.sh" >> ~/.bashrc && \
    echo "conda activate base" >> ~/.bashrc && \
    find /opt/conda/ -follow -type f -name '*.a' -delete && \
    find /opt/conda/ -follow -type f -name '*.js.map' -delete

ENV PATH /opt/conda/bin:$PATH
WORKDIR /

ARG PYTHON_VERSION=3.7
RUN conda install -y python=$PYTHON_VERSION
RUN conda update -n base conda
RUN conda install -y numpy pillow pyqt contextlib2 swig
RUN pip install pypicloud[server] twine

# When running with --user 1000, 1001, 1002
RUN groupadd appuser -g 1000 && useradd -r -u 1000 appuser -g appuser
RUN groupadd appuser1 -g 1001 && useradd -r -u 1001 appuser1 -g appuser1
RUN groupadd appuser2 -g 1002 && useradd -r -u 1002 appuser2 -g appuser2

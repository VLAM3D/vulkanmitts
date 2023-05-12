FROM registry.gitlab.com/mlamarre/vulkan/vulkan:1.3.243

ARG DEBIAN_FRONTEND=noninteractive
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

ENV CMAKE_VERSION=3.26
ENV CMAKE_BUILD=3
RUN wget https://github.com/Kitware/CMake/releases/download/v${CMAKE_VERSION}.${CMAKE_BUILD}/cmake-${CMAKE_VERSION}.${CMAKE_BUILD}-Linux-x86_64.sh \
      -q -O /tmp/cmake-install.sh \
      && chmod u+x /tmp/cmake-install.sh \
      && mkdir /usr/bin/cmake \
      && /tmp/cmake-install.sh --skip-license --prefix=/usr/local \
      && rm /tmp/cmake-install.sh

WORKDIR /tmp
ARG MAMBAFORGE_NAME=Mambaforge
ARG MAMBAFORGE_VERSION=23.1.0-1
ENV CONDA_DIR=/opt/conda
ENV LANG=C.UTF-8 LC_ALL=C.UTF-8
ENV PATH=${CONDA_DIR}/bin:${PATH}
RUN mkdir -p /root/.conda && \
    wget --no-hsts --quiet https://github.com/conda-forge/miniforge/releases/download/${MAMBAFORGE_VERSION}/${MAMBAFORGE_NAME}-${MAMBAFORGE_VERSION}-Linux-$(uname -m).sh -O ~/mambaforge.sh && \
    /bin/bash ~/mambaforge.sh -b -p /opt/conda && \
    rm ~/mambaforge.sh && \
    /opt/conda/bin/conda clean --tarballs --index-cache --packages --yes && \
    ln -s /opt/conda/etc/profile.d/conda.sh /etc/profile.d/conda.sh && \
    echo ". /opt/conda/etc/profile.d/conda.sh" >> ~/.bashrc && \
    echo "conda activate base" >> ~/.bashrc && \
    find /opt/conda/ -follow -type f -name '*.a' -delete && \
    find /opt/conda/ -follow -type f -name '*.pyc' -delete && \
    /opt/conda/bin/conda clean --force-pkgs-dirs --all --yes  && \
    echo ". ${CONDA_DIR}/etc/profile.d/conda.sh && conda activate base" >> /etc/skel/.bashrc && \
    echo ". ${CONDA_DIR}/etc/profile.d/conda.sh && conda activate base" >> ~/.bashrc

WORKDIR /

ARG PYTHON_VERSION=3.10
RUN mamba install -y python=$PYTHON_VERSION
RUN mamba config --set channel_priority strict
RUN mamba install -y numpy pillow pyqt contextlib2 swig==4.0.0 -c conda-forge
RUN pip install pypicloud[server] twine

# When running with --user 1000, 1001, 1002
RUN groupadd appuser -g 1000 && useradd -r -u 1000 appuser -g appuser
RUN groupadd appuser1 -g 1001 && useradd -r -u 1001 appuser1 -g appuser1
RUN groupadd appuser2 -g 1002 && useradd -r -u 1002 appuser2 -g appuser2

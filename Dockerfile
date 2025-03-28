FROM python:bookworm
RUN apt-get update

# Install packages for building the binary
RUN apt-get install -y build-essential libncurses-dev zlib1g-dev gawk git \
gettext libssl-dev xsltproc rsync wget unzip python3 python3-setuptools

COPY requirements.txt /tmp/requirements.txt
RUN pip install -r /tmp/requirements.txt

COPY . /app/ptah 
WORKDIR /app/ptah

ARG openwrt_version
ARG ptah_version
ARG ptah_config

# Prepare the image builder
RUN --mount=type=secret,id=credentials python3 /app/ptah/prepare_image_builder.py --config ${ptah_config} \ 
    --ptah-version ${ptah_version} --openwrt-version ${openwrt_version} --output-dir "/build" \
    --secrets-source "file" --secrets-file "/run/secrets/credentials" \
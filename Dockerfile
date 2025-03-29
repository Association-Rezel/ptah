FROM python:bookworm
RUN apt-get update

# Install packages for building the binary
RUN apt-get install -y build-essential libncurses-dev zlib1g-dev gawk git \
gettext libssl-dev xsltproc rsync wget unzip python3 python3-setuptools

COPY requirements.txt /tmp/requirements.txt
RUN pip install -r /tmp/requirements.txt

COPY ./app /app
WORKDIR /app

ARG ptah_config

COPY ./${ptah_config} /opt/ptah_config.yaml

# Prepare the image builder
RUN --mount=type=secret,id=credentials python3 /app/prepare_image_builder.py --config /opt/ptah_config.yaml \ 
    --docker-secrets-mount /run/secrets/credentials
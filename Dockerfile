FROM python:bookworm

# Install packages for building the binary
RUN apt-get update \
    && apt-get install -y build-essential gettext git gawk libncurses-dev \
    libssl-dev python3 python3-setuptools rsync unzip wget xsltproc zlib1g-dev \
    && apt-get clean

COPY requirements.txt /tmp/requirements.txt
RUN pip install -r /tmp/requirements.txt

ARG PTAH_CONFIG_FILE

RUN if [ -z "$PTAH_CONFIG_FILE" ]; then \
    echo "No ptah_config_file provided, crashing the build"; \
    exit 1; \
    fi;

COPY ${PTAH_CONFIG_FILE} /opt/ptah_config.yaml

COPY . /app
WORKDIR /app

COPY ./entrypoint.sh /entrypoint.sh

RUN python3 /app/prepare_docker_environment.py --config /opt/ptah_config.yaml

ENTRYPOINT [ "bash", "/entrypoint.sh" ]
FROM python:bookworm

RUN apt-get update \
    && apt-get install -y build-essential gettext git gawk libncurses-dev \
    libssl-dev python3 python3-setuptools rsync unzip wget xsltproc zlib1g-dev \
    && apt-get clean

COPY requirements.txt /tmp/requirements.txt
RUN pip install -r /tmp/requirements.txt

ARG PTAH_CONFIG_FILE

ARG DEPLOY_ENV=local

ENV DEPLOY_ENV=${DEPLOY_ENV}

RUN if [ -z "$PTAH_CONFIG_FILE" ]; then \
    echo "No ptah_config_file provided, crashing the build"; \
    exit 1; \
    fi;

COPY ${PTAH_CONFIG_FILE} /opt/ptah_config.yaml

COPY . /app
WORKDIR /app

EXPOSE 8000

COPY ./entrypoint.sh /entrypoint.sh

RUN python3 /app/prepare_environment.py --config /opt/ptah_config.yaml

ENTRYPOINT [ "bash", "/entrypoint.sh" ]

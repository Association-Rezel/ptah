FROM python:bookworm
RUN apt-get update

# Install packages for building the binary
RUN apt-get install -y build-essential libncurses-dev zlib1g-dev gawk git \
gettext libssl-dev xsltproc rsync wget unzip python3 python3-setuptools

COPY requirements.txt /tmp/requirements.txt
RUN pip install -r /tmp/requirements.txt

COPY ./ptah /app
WORKDIR /app

COPY ./entrypoint.sh /entrypoint.sh

ENTRYPOINT [ "bash", "/entrypoint.sh" ]
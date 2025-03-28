#!/bin/bash

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[1;34m'
NC='\033[0m'

OPENWRT_RELEASE_URL="https://downloads.openwrt.org/releases/"

# ---------------------------------------------------------------------------- #
#                                   Precheck                                   #
# ---------------------------------------------------------------------------- #

# Check if Docker is installed
if ! command -v docker &> /dev/null; then
    echo -e "${RED}Docker is not installed. Please install Docker first.${NC}"
    exit 1
fi

# ---------------------------------------------------------------------------- #
#                                Setup variables                               #
# ---------------------------------------------------------------------------- #

# Function to display usage/help
usage() {
    echo -e "${RED}Usage: $0 --config <Path to ptah config yaml> \
    [--openwrt-version <OpenWRT Version number to build to>] [--ptah-version <Ptah version] ${NC}"
    exit 1
}

# Check if the user has asked for help
for arg in "$@"; do
    if [[ "$arg" == "--help" || "$arg" == "-h" ]]; then
        usage
        exit 0
    fi
done

# Parse the flags
while [[ "$#" -gt 0 ]]; do
    case $1 in
        --config) CONFIG="$2"; shift ;;
        --openwrt-version) OPENWRT_VERSION="$2"; shift ;;
        --ptah-version) PTAH_VERSION="$2"; shift ;;
        *) echo -e "${RED}Unknown parameter passed: $1${NC}"; usage; exit 1 ;;
    esac
    shift
done

# Check if the required flags are passed
if [[ -z "$CONFIG" ]]; then
    echo -e "${RED}Missing required arguments${NC}"
    usage
    exit 1
fi

# Check if the config file exists
if [[ ! -f "$CONFIG" ]]; then
    echo -e "${RED}Config file not found${NC}"
    exit 1
fi

LATEST_RELEASE=$(curl -s $OPENWRT_RELEASE_URL | grep -oP "([0-9]+\.[0-9]+\.[0-9]+)" |sort -V |tail -n1)
echo -e "${BLUE}Latest OpenWRT release: $LATEST_RELEASE${NC}"

# Check if the openwrt version is passed
if [[ -z "$OPENWRT_VERSION" ]]; then
    echo -e "${YELLOW}OpenWRT version not passed. Defaulting to latest: $LATEST_RELEASE ${NC}"
    OPENWRT_VERSION=$LATEST_RELEASE
fi

# Check if the ptah version is passed
if [[ -z "$PTAH_VERSION" ]]; then
    echo -e "${YELLOW}Ptah version not passed. Defaulting to latest${NC}"
    PTAH_VERSION="ptah:latest"
fi

# Check if the openwrt version is valid
if [[ ! $(curl -s "$OPENWRT_RELEASE_URL" | grep -oP "([0-9]+\.[0-9]+\.[0-9]+)" | grep -w "$OPENWRT_VERSION") ]]; then
    echo -e "${RED}Invalid OpenWRT version${NC}"
    exit 1
fi

# ---------------------------------------------------------------------------- #
#                              Build Docker image                              #
# ---------------------------------------------------------------------------- #

docker build -t $PTAH_VERSION . --secret id=credentials,src=.env \
    --build-arg openwrt_version="$OPENWRT_VERSION" \
    --build-arg ptah_version="$PTAH_VERSION" \
    --build-arg ptah_config="$CONFIG"

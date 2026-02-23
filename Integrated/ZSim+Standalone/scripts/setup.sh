#! /usr/bin/env bash

ORIGINAL_DIR=$(pwd)
HOME_DIR="/mnt/ssd"
ZOO_GITHUB="git@github.com:bakhshalipour/zoo-pre-release.git"


echo "Installing Linux programs..."
# Removed the flag file check since it wasn't defined
sudo apt-get -y update
sudo apt-get -y upgrade

packages=(
    build-essential scons libconfig-dev libconfig++-dev
    libhdf5-dev libelf-dev python3.10-venv
)

sudo apt-get install -y "${packages[@]}"

echo '--------------------------------------------------------------------------------'

echo "Installing Intel Pin..."
if [[ -z "$PINPATH" ]]; then
    pin_url="https://software.intel.com/sites/landingpage/pintool/downloads/pin-2.14-71313-gcc.4.4.7-linux.tar.gz"
    pin_dir="${pin_url##*/}"
    pin_dir="${pin_dir%%.tar.gz}"

    curl -L "$pin_url" -o pin.tar.gz
    tar -xzf pin.tar.gz
    rm pin.tar.gz
    if [[ ! -d "$pin_dir" ]]; then
        echo "$pin_dir is not created!"
        exit 1
    fi

    # Export for current session AND add to .bashrc
    export PINPATH=$(readlink -f $pin_dir)
    echo "export PINPATH=$PINPATH" >> $HOME/.bashrc
    echo "PINPATH set to: $PINPATH"
else
    echo "Pin is already installed. PINPATH=$PINPATH"
fi

echo '--------------------------------------------------------------------------------'

echo "Setting up DRAMSim3 (needed for build)"
if [[ -z "$DRAMSIM3PATH" ]]; then
    dramsim3_dir="$(pwd)/DRAMsim3"

    if [[ ! -d "$dramsim3_dir" ]]; then
        echo "$dramsim3_dir is missing!"
        exit 1
    fi

    # Export for current session AND add to .bashrc
    export DRAMSIM3PATH=$(readlink -f $dramsim3_dir)
    echo "export DRAMSIM3PATH=$DRAMSIM3PATH" >> $HOME/.bashrc
    echo "DRAMSIM3PATH set to: $DRAMSIM3PATH"
else
    echo "DRAMSim3 already installed. DRAMSIM3PATH=$DRAMSIM3PATH"
fi

# Always build DRAMSim3 if path exists
if [[ -d "$DRAMSIM3PATH" ]]; then
    echo "Building DRAMSim3..."
    cd "$DRAMSIM3PATH"
    mkdir -p build
    cd build
    cmake ..
    make -j$(nproc)
fi

echo '--------------------------------------------------------------------------------'

echo "Building ZSim+Standalone Mess"
if [[ ! -z "$DRAMSIM3PATH" && ! -z "$PINPATH" ]]; then
    cd "${ORIGINAL_DIR}"
    echo "Current environment:"
    echo "  DRAMSIM3PATH=$DRAMSIM3PATH"
    echo "  PINPATH=$PINPATH"
    
    scons -c
    scons -j$(nproc) FEATURE_CXL_MEM=1
else
    echo "ERROR: Missing dependencies:"
    echo "  DRAMSIM3PATH=$DRAMSIM3PATH"
    echo "  PINPATH=$PINPATH"
    exit 1
fi

echo '--------------------------------------------------------------------------------'

echo "Cloning Zoo Memory Benchmark - dataset install will take roughly an hour"
zoo_dir="${HOME_DIR}/zoo-pre-release"
if [[ -z "$ZOOPATH" ]]; then
    git clone -b cxl-zsim "$ZOO_GITHUB" "$zoo_dir"

    if [[ ! -d "$zoo_dir" ]]; then
        echo "$zoo_dir is missing! Likely an error while cloning the repo"
        exit 1
    fi

    # Export for current session AND add to .bashrc
    export ZOOPATH=$(readlink -f "$zoo_dir")
    echo "export ZOOPATH=$ZOOPATH" >> "$HOME/.bashrc"
    echo "ZOOPATH set to: $ZOOPATH"
else
    if [[ ! -d "$ZOOPATH" ]]; then
        echo "$zoo_dir is missing! Will retry cloning the repo"
        git clone -b cxl-zsim "$ZOO_GITHUB" "$zoo_dir"
        if [[ ! -d "$zoo_dir" ]]; then
            echo "Failed to clone zoo repository!"
            exit 1
        fi
    fi  
    echo "Zoo Memory Benchmark already installed. ZOOPATH=$ZOOPATH"
fi

# Setup Zoo if the path exists
if [[ -d "$ZOOPATH" ]]; then
    cd "$ZOOPATH" || exit 1
    if [[ -f "$ZOOPATH/scripts/setup.sh" ]]; then
        "$ZOOPATH/scripts/setup.sh"
    fi
fi

echo '--------------------------------------------------------------------------------'
echo "Setup complete!"
echo "Environment variables set:"
echo "  PINPATH=$PINPATH"
echo "  DRAMSIM3PATH=$DRAMSIM3PATH"
echo "  ZOOPATH=$ZOOPATH"
echo ""
echo "To use these in new shell sessions, run: source ~/.bashrc"

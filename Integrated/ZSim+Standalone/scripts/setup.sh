ORIGINAL_DIR=$(pwd)
HOME_DIR="/mnt/ssd/"
ZOO_GITHUB="git@github.com:bakhshalipour/zoo-pre-release.git"


echo "Installing Linux programs..."
if [[ ! -f "$LINUX_PROGRAMS_FLAG_FILE" ]]; then
    sudo apt-get -y update
    sudo apt-get -y upgrade

    packages=(
        build-essential scons libconfig-dev libconfig++-dev
        libhdf5-dev libelf-dev 
    )

    sudo apt-get install -y "${packages[@]}"
else
    echo "Linux programs are already installed"
fi

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

    echo "export PINPATH=$(readlink -f $pin_dir)" >>$HOME/.bashrc
    echo "Run the following command to apply changes across all sessions."
    echo "source ~/.bashrc"
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

    echo "export DRAMSIM3PATH=$(readlink -f $dramsim3_dir)" >>$HOME/.bashrc
    echo "Run the following command to apply changes across all sessions."
    echo "source ~/.bashrc"

else
    echo "DRAMSim3 already installed. DRAMSIM3PATH=$DRAMSIM3PATH"
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
    scons -c
    scons -j$(nproc)
else
    echo "Missing dependencies:"
    echo "  DRAMSIM3PATH=$DRAMSIM3PATH"
    echo "  PINPATH=$PINPATH"
    exit 1
fi

echo '--------------------------------------------------------------------------------'

#TODO: clean up this flow 
echo "Cloning Zoo Memory Benchmark - dataset install will take roughly an hour"
zoo_dir="${HOME_DIR}/zoo-pre-release"
if [[ -z "$ZOOPATH" ]]; then
    git clone -b cxl-zsim "$ZOO_GITHUB" "$zoo_dir"

    if [[ ! -d "$zoo_dir" ]]; then
        echo "$zoo_dir is missing! Likely an error while cloning the repo"
        exit 1
    fi

    echo "export ZOOPATH=$(readlink -f "$zoo_dir")" >> "$HOME/.bashrc"
    echo "Run the following command to apply changes across all sessions."
    echo "source ~/.bashrc"

else
    if [[ ! -d "$ZOOPATH" ]]; then
        echo "$zoo_dir is missing! Will retry cloning the repo"
        git clone -b cxl-zsim "$ZOO_GITHUB" "$zoo_dir"
        exit 1
    fi  
    echo "Zoo Memory Benchmark already installed. ZOOPATH=$ZOOPATH"
    cd "$ZOOPATH" || exit 1
    "$ZOOPATH/scripts/setup.sh"
fi


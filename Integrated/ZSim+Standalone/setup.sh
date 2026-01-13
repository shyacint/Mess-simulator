original_dir=$(pwd)

#todo: add code to setup env variables for dramsim3

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
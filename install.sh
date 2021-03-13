#!/bin/sh

# sudo apt --assume-yes update
# sudo apt --assume-yes upgrade
# sudo apt --assume-yes install git

# cd /opt
# sudo git clone https://github.com/mtovts/visiobas-panel visiobas-controller
# cd /opt/visbas-controller
# sudo sh install.sh

# Set mqtt.yaml and i2c.yaml

sudo apt --assume-yes install i2c-tools
sudo apt --assume-yes install python3-pip
sudo apt --assume-yes install mosquitto mosquitto-clients

# sudo raspi-config  # 3. Interface Options
# enable I2C, then reboot
# ensure i2c available in /dev/

# note available buses (0x20 and 0x25 now)

cd /opt/visbas-controller
cp vb_controller.service /etc/systemd/system/vb_controller.service
systemctl start vb_controller

pip3 install -r requirements.txt

# todo: detect i2c buses
i2cdetect -y 1

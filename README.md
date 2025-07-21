# ecris.csd
Codes for taking on-line ECRIS charge state distributions

# Beamline Computer

The beamline computer runs the python script for taking fast CSDs using a service. Commands for status/start/stop:

```bash
sudo systemctl status fast-csd
sudo systemctl start fast-csd
sudo systemctl stop fast-csd
```
By default the service will start up when the computer is rebooted.

## Networking

The interface in use is `enp46s0` which is now managed by network manager via `nmcli`. To see the status of networks you can use to see the IP address.

```bash
nmcli
# or
ifconfig
```

If there are issues, you can connect to the computer locally via an HDMI monitor and manually cycle the connection using

```bash
sudo ifdown enp46s0
sudo ifup enp46s0
```

A local HDMI connection should work, the default linux kernal boot option. `/etc/default/grub` was modified to add the `video` flag to the default option:

```bash
GRUB_CMDLINE_LINUX_DEFAULT="quiet splash video=HDMI-A:1920x1080-32D"
```

And then `update-grub` was run. This should ensure the HDMI ports remain active even if not present when the system is restarted.
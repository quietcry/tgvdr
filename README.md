[![hacs_badge](https://img.shields.io/badge/HACS-Custom-41BDF5.svg?style=for-the-badge)](https://github.com/hacs/integration)

# VDR integration for Home Assistant as connector for Klaus Schmidingers VDR
works together with [tgepg-card](https://github.com/quietcry/tgepg-card.git) as frontend

this is a fork of [ha_pyvdr_integration](https://github.com/baschno/ha_pyvdr_integration.git) with integrated fork of [pyvdr](https://github.com/baschno/pyvdr.git) from [baschno](https://github.com/baschno)
***


* @published: March 2024
* @author: Thomas Geißenhöner
* @workspace: `conf/custom_components/tgvdr`
* thanks to [baschno](https://github.com/baschno) for inspiration
  
this is a very early version! Please be beware.

## Prerequisites

* a running VDR 

## Basic Configuration (manual)

```yaml
sensor:
    - platform: vdr
      host: <ip>
      port: 6419
      timeout: 2
```
a lot (at the moment) undocumented configurations are available or planned 


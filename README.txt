Ruckusist .Dotfiles

A set of configuration files that make me comfortable in my bash environment.

Installation:
(1) clone this repo to .files
git clone https://github.com/ruckusist/dotfiles ~/.files

(2) launch a python script to do all the heavy lifting.
sudo python3 ~/.files/dotfiles.py

# This will try to install packages from APT, PIP, and CARGO for now.
# In the case of installing Rust for Cargo, and fontconfig for powerline
# and powerline itself, Root Privilages will be necessary.

GOAL:
This dot files file replacer/updater should be used to setup a basic linux system.
it should also be able to backup and replace all of my important system files,
fstab, grub.conf, stuff like that should be put away just like this as well.

CHANGELOG:
11-19-19: exa is setup just the way i like it. powerline  install via APT is better
than install via clone or pip. tmux setup was simple should have done that sooner.
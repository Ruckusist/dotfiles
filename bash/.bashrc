# If not running interactively, don't do anything
case $- in
    *i*) ;;
      *) return;;
esac

# HISTORY FILE MAINTANENCE
HISTCONTROL=ignoreboth  # ignore blanks
HISTSIZE=1000           # ??
HISTFILESIZE=2000       # ??

# SHELL OPTIONS
shopt -s checkwinsize  # Check size on every refresh
shopt -s globstar      # Use ** for 'grab-all'
shopt -s histappend    # append to history file - not overwrite

# THIS SAYS PROGRAMABLE COMPLETION
if ! shopt -oq posix; then
  if [ -f /usr/share/bash-completion/bash_completion ]; then
    . /usr/share/bash-completion/bash_completion
  elif [ -f /etc/bash_completion ]; then
    . /etc/bash_completion
  fi
fi

# USING Aliases
if [ -f ~/.bash_aliases ]; then
    . ~/.bash_aliases
fi

# POWERLINE CONFIG
powerline-daemon -q
POWERLINE_BASH_CONTINUATION=1
POWERLINE_BASH_SELECT=1
source "/home/dad/.local/lib/python3.7/site-packages/powerline/bindings/bash/powerline.sh"
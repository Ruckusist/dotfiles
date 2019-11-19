# UBUNTU SUGGESTED
alias ls='ls --color=auto'
alias grep='grep --color=auto'
alias fgrep='fgrep --color=auto'
alias egrep='egrep --color=auto'

# Folder stuffs -t=mod --time-style=iso --grid --long
alias ..="cd .."
alias l="exa --git --binary --all --sort=ext --extended --grid"
alias lr="exa --git --binary --header --all --sort=ext --extended --recurse --ignore-glob='*git*'"
alias lt="exa --git --binary --header --all --sort=ext --extended --tree --ignore-glob='*git*'"
alias ll="exa --git --binary --header --all --sort=ext --extended --ignore-glob='*git*' --long"
alias lll="df -h  && exa --git --binary --header --all --sort=ext --extended --ignore-glob='*git*'"

# PYTHON RELATED
alias python="python3"
alias pip="pip3"
alias pinstall="sudo -H python3 -m pip install -U"
alias boom="sudo -H python3"

# C++ BUILD TOOLS
export GCC_COLORS='error=01;31:warning=01;35:note=01;36:caret=01;32:locus=01:quote=01'

# PROJECT RELEATED
alias getwd='cp -r /drive/dotfiles ~/.files'
alias killwd='rm -rf ~/.files'
alias wd='cd ~/.files'
alias rekt='python .files/dotfiles.py'

# TIPS AND TRICKS!
alias sl="ls"
alias cp="cp -r"
# BASH USER STARTUP SEQUENCE

# LOAD BASHRC SETTINGS -->
if [ -f ~/.bashrc ]; then
   source ~/.bashrc
fi

# ADD LOCAL BIN TO PATH -->
if [ -d "$HOME/.local/bin" ] ; then
    PATH="$HOME/.local/bin:$PATH"
fi
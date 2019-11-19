# BASH USER STARTUP SEQUENCE

# ADD LOCAL BIN TO PATH -->
# THE Bashrc depends on this.  # THIS IS HAPPENING TWICE...
if [ -d "$HOME/.local/bin" ] ; then
    PATH="$PATH:$HOME/.local/bin"
fi

# ADD [RUST]CARGO BIN TO PATH -->
# THE Bashrc depends on this.
if [ -d "$HOME/.cargo/bin" ] ; then
    PATH="$PATH:$HOME/.cargo/bin"
fi

# LOAD BASHRC SETTINGS -->
if [ -f ~/.bashrc ]; then
   . ~/.bashrc
fi

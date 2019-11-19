import os, shutil, filecmp
from pip._internal import main as pipmain

USERHOME = os.path.expanduser("~")

def setup_bash(verbose=False):
    """am i making this harder than it needs to be...
    id bet I could do a blah blah for file in bashfiles... 
    maybe its fine.
    """
    global USERHOME
    bashfiles = [
        '.bashrc', '.bash_profile', '.bash_aliases', '.bash_logout', '.bash_history'
    ]
    for x in bashfiles:
        OLD_FILE = os.path.join(USERHOME, x)
        BACKUP_FILE = os.path.join(USERHOME,'.files', 'backup', f"{x}.old")
        NEW_FILE = os.path.join(USERHOME, '.files', 'files', x)
        if verbose: print(f"!--> checking on file {OLD_FILE}")
        if os.path.exists(OLD_FILE):
            if not filecmp.cmp(OLD_FILE, NEW_FILE):
                shutil.move(OLD_FILE, BACKUP_FILE)
                if verbose: print(f"[backup] --> {BACKUP_FILE}")
                shutil.move(NEW_FILE, OLD_FILE)
                if verbose: print(f"[update] <-- {NEW_FILE}")
            else:
                if verbose: print(f"[allgood] No Changes to file: {x}")
        else:
            if verbose: print(f"[error] {x} does not exist")
            shutil.move(NEW_FILE, OLD_FILE)
            if verbose: print(f"[update] <-- {NEW_FILE}")

def install_via_cargo(repo): os.system(f'cargo install {repo}')

def install_via_pip(repo): pipmain(['install', '-U', repo])

def install_via_apt(repo): os.system(f"sudo apt install {repo}")

def get_powerline():
    """
    DEPENDENCIES: apt install fontconfig.
    """
    global USERHOME
    print("Installing dependencies")
    install_via_apt('fontconfig')
    print("Getting Powerline-fonts")
    # get symbols font
    if not os.path.exists(
        os.path.join(USERHOME, '.local', 'share', 'fonts', 'PowerlineSymbols.otf')
        ):
        os.system('wget https://github.com/powerline/powerline/raw/develop/font/PowerlineSymbols.otf')
        # Move the font to the right place.
        if not os.path.exists(os.path.join(
            USERHOME, '.local', 'share', 'fonts'
        )):
            os.mkdir(os.path.join(USERHOME, '.local', 'share', 'fonts'))
            os.system('mv PowerlineSymbols.otf ~/.local/share/fonts/')
    # IF everything else is good to this point just try to reinstall the fonts the folder.
    else: print("Already Got Powerline-font Symbols")
    print("Installing Font with fc-cache")
    os.system('fc-cache -vf ~/.local/share/fonts/')
    # get symbols config
    if not os.path.exists(os.path.join(USERHOME, '.local', 'share', 'fonts', 'PowerlineSymbols.otf')):
        os.system('wget https://github.com/powerline/powerline/raw/develop/font/10-powerline-symbols.conf')
        
        # Move the config to the right place.
        if not os.path.exists(os.path.join(USERHOME, '.config')):
            os.mkdir(os.path.join(USERHOME, '.config'))
        if not os.path.exists(os.path.join(USERHOME, '.config', 'fontconfig')):
            os.mkdir(os.path.join(USERHOME, '.config', 'fontconfig'))
        if not os.path.exists(os.path.join(USERHOME, '.config', 'fontconfig', 'conf.d')):
            os.mkdir(os.path.join(USERHOME, '.config', 'fontconfig', 'conf.d'))
        os.system('mv 10-powerline-symbols.conf ~/.config/fontconfig/conf.d/')
    else: print("Already Got Powerline-font Config")
    print("finished getting powerline fonts.")

    ## NEXT THING!
    print("Getting Powerline.")
    install_via_pip('powerline-status')
    print("Make sure to add POWERLINE to the PS1 in your .bashrc")
    return True

def setup_powerline():
    install_via_apt('powerline')  # GEEZ

def setup_exa():
    install_via_apt('cargo')
    install_via_cargo('exa')

def source_profile(): 
    global USERHOME
    os.system(f". {os.path.join(USERHOME,'.bash_profile')}")

def transfer_file(NEW_FILE, BACKUP_FILE, OLD_FILE, verbose=True):
    if os.path.exists(OLD_FILE):
        if not filecmp.cmp(OLD_FILE, NEW_FILE):
            shutil.move(OLD_FILE, BACKUP_FILE)
            if verbose: print(f"[backup] --> {BACKUP_FILE}")
            shutil.move(NEW_FILE, OLD_FILE)
            if verbose: print(f"[update] <-- {NEW_FILE}")
        else:
            if verbose: print(f"[allgood] No Changes to file: {OLD_FILE}")
    else:
        if verbose: print(f"[error] {OLD_FILE} does not exist, not backing up.")
        shutil.move(NEW_FILE, OLD_FILE)
        if verbose: print(f"[new] <-- {NEW_FILE}")
    

def setup_tmux():
    global USERHOME
    print("working on tmux")
    OLD_FILE = os.path.join(USERHOME, '.tmux.conf')
    BACKUP_FILE = os.path.join(USERHOME, '.files', 'backup', '.tmux.conf')
    NEW_FILE = os.path.join(USERHOME, '.files', 'files', '.tmux.conf')
    transfer_file(NEW_FILE, BACKUP_FILE, OLD_FILE)

if __name__ == "__main__":
    print("Starting Dotfile Update")
    try:
        # setup_exa()
        # setup_powerline()
        # setup_bash()
        setup_tmux()
    finally:
        source_profile()
    print("finished update.")
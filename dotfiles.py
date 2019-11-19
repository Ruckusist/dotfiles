import os, shutil, filecmp
from pip._internal import main as pipmain

USERHOME = os.path.expanduser("~")

print("Getting the Dotfiles right.")

def backup_old_file(old_file): return

def copy_file_to(file, dest): return

def clone_repo(repo): return

def setup_bash():
    global USERHOME
    print(f"Setting up bash files in {USERHOME}")
    bashfiles = [
        '.bashrc', '.bash_profile', '.bash_aliases'
    ]
    for x in bashfiles:
        # first take the old files and put them in the backup folder
        # I guess im going to overwrite an older backed up file at this point.
        if os.path.exists(os.path.join(USERHOME, x)):
            if not filecmp(
                os.path.join(USERHOME, x),
                os.path.join(USERHOME, '.files', 'bash', x)
            ):
                shutil.move(os.path.join(USERHOME, x), os.path.join(USERHOME,'.files', 'backup', f"{x}.old"))
                print(f"[backup] --> ~/.files/backup/{x}.old")
                shutil.move(os.path.join(USERHOME, '.files', 'bash', x), os.path.join(USERHOME, x))
                print(f"[update] <-- ~/.files/{x}")
            else:
                print(f"[allgood] No Changes to file: {x}")


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

# get_powerline()
setup_bash()
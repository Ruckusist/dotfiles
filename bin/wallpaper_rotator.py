import random
import pathlib
import os

WALLPAPER_DIR = pathlib.Path.home() / "wall"

def get_random_wallpaper():
    wallpapers = list(WALLPAPER_DIR.glob("*"))
    return random.choice(wallpapers) if wallpapers else None

def set_wallpaper(wallpaper_path):
    if wallpaper_path and os.path.exists(wallpaper_path):
        os.system(f"feh --bg-scale '{wallpaper_path}'")


def main():
    wallpaper = get_random_wallpaper()
    if wallpaper:
        set_wallpaper(wallpaper)
        print(f"Wallpaper set to: {wallpaper}")
    else:
        print("No wallpapers found.")

if __name__ == "__main__":
    main()
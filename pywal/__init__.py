"""
wal - Generate and change colorschemes on the fly.
Created by Dylan Araps.
"""
import argparse
import os
import pathlib
import random
import re
import shutil
import subprocess
import sys

__version__ = "0.1.6"

# Internal variables.
COLOR_COUNT = 16
CACHE_DIR = pathlib.Path.home() / ".cache/wal/"


# pylint: disable=too-few-public-methods
class ColorType(object):
    """Store colors in various formats."""
    plain = []
    xrdb = []
    sequences = []
    shell = []
    scss = []
    css = [":root {"]
    putty = [
        "Windows Registry Editor Version 5.00",
        "[HKEY_CURRENT_USER\\Software\\SimonTatham\\PuTTY\\Sessions\\Wal]",
    ]


# pylint: disable=too-few-public-methods
class Args(object):
    """Store args."""
    notify = True


# ARGS {{{


def get_args():
    """Get the script arguments."""
    description = "wal - Generate colorschemes on the fly"
    arg = argparse.ArgumentParser(description=description)

    # Add the args.
    arg.add_argument("-c", action="store_true",
                     help="Delete all cached colorschemes.")

    arg.add_argument("-i", metavar="\"/path/to/img.jpg\"",
                     help="Which image or directory to use.")

    arg.add_argument("-n", action="store_true",
                     help="Skip setting the wallpaper.")

    arg.add_argument("-o", metavar="\"script_name\"",
                     help="External script to run after \"wal\".")

    arg.add_argument("-q", action="store_true",
                     help="Quiet mode, don\"t print anything and \
                           don't display notifications.")

    arg.add_argument("-r", action="store_true",
                     help="Reload current colorscheme.")

    arg.add_argument("-t", action="store_true",
                     help="Fix artifacts in VTE Terminals. \
                           (Termite, xfce4-terminal)")

    arg.add_argument("-v", action="store_true",
                     help="Print \"wal\" version.")

    return arg.parse_args()


def process_args(args):
    """Process args."""
    # If no args were passed.
    if not len(sys.argv) > 1:
        print("error: wal needs to be given arguments to run.\n"
              "       Refer to \"wal -h\" for more info.")
        exit(1)

    # -q
    if args.q:
        sys.stdout = sys.stderr = open(os.devnull, "w")
        Args.notify = False

    # -c
    if args.c:
        shutil.rmtree(CACHE_DIR / "schemes")
        create_cache_dir()

    # -r
    if args.r:
        reload_colors(args.t)

    # -v
    if args.v:
        print(f"wal {__version__}")
        exit(0)

    # -i
    if args.i:
        image = get_image(args.i)
        ColorType.plain = get_colors(image)

        if not args.n:
            set_wallpaper(image)

        # Set the colors.
        send_sequences(ColorType.plain, args.t)
        export_colors(ColorType.plain)

    # -o
    if args.o:
        disown(args.o)


# }}}


# COLORSCHEME GENERATION {{{


def get_image(img):
    """Validate image input."""
    # Check if the user has Imagemagick installed.
    if not shutil.which("convert"):
        print("error: imagemagick not found, exiting...\n"
              "error: wal requires imagemagick to function.")
        exit(1)

    image = pathlib.Path(img)

    if image.is_file():
        wal_img = image

    # Pick a random image from the directory.
    elif image.is_dir():
        file_types = (".png", ".jpg", ".jpeg", ".jpe", ".gif")

        # Get the filename of the current wallpaper.
        current_img = pathlib.Path(CACHE_DIR / "wal")

        if current_img.is_file():
            current_img = read_file(current_img)
            current_img = os.path.basename(current_img[0])

        # Get a list of images.
        images = [img for img in os.listdir(image)
                  if img.endswith(file_types) and
                  img != current_img]

        wal_img = random.choice(images)
        wal_img = pathlib.Path(image / wal_img)

    else:
        print("error: No valid image file found.")
        exit(1)

    print("image: Using image", wal_img)
    return str(wal_img)


def imagemagick(color_count, img):
    """Call Imagemagick to generate a scheme."""
    colors = subprocess.Popen(["convert", img, "+dither", "-colors",
                               str(color_count), "-unique-colors", "txt:-"],
                              stdout=subprocess.PIPE)

    return colors.stdout.readlines()


def gen_colors(img):
    """Generate a color palette using imagemagick."""
    # Generate initial scheme.
    raw_colors = imagemagick(COLOR_COUNT, img)

    # If imagemagick finds less than 16 colors, use a larger source number
    # of colors.
    index = 0
    while len(raw_colors) - 1 < COLOR_COUNT:
        index += 1
        raw_colors = imagemagick(COLOR_COUNT + index, img)

        print("colors: Imagemagick couldn't generate a", COLOR_COUNT,
              "color palette, trying a larger palette size",
              COLOR_COUNT + index)

    # Remove the first element, which isn't a color.
    del raw_colors[0]

    # Create a list of hex colors.
    return [re.search("#.{6}", str(col)).group(0) for col in raw_colors]


def get_colors(img):
    """Generate a colorscheme using imagemagick."""
    # Cache the wallpaper name.
    save_file(img, CACHE_DIR / "wal")

    # Cache the sequences file.
    cache_file = pathlib.Path(CACHE_DIR / "schemes" / img.replace("/", "_"))

    if cache_file.is_file():
        colors = read_file(cache_file)
        print("colors: Found cached colorscheme.")

    else:
        print("colors: Generating a colorscheme...")
        notify("wal: Generating a colorscheme...")

        # Generate the colors.
        colors = gen_colors(img)
        colors = sort_colors(colors)

        # Cache the colorscheme.
        save_file("\n".join(colors), cache_file)

        print("colors: Generated colorscheme")
        notify("wal: Generation complete.")

    return colors


def sort_colors(colors):
    """Sort the generated colors."""
    sorted_colors = []
    sorted_colors.append(colors[0])
    sorted_colors.append(colors[9])
    sorted_colors.append(colors[10])
    sorted_colors.append(colors[11])
    sorted_colors.append(colors[12])
    sorted_colors.append(colors[13])
    sorted_colors.append(colors[14])
    sorted_colors.append(colors[15])
    sorted_colors.append(set_grey(colors))
    sorted_colors.append(colors[9])
    sorted_colors.append(colors[10])
    sorted_colors.append(colors[11])
    sorted_colors.append(colors[12])
    sorted_colors.append(colors[13])
    sorted_colors.append(colors[14])
    sorted_colors.append(colors[15])
    return sorted_colors


# }}}


# SEND SEQUENCES {{{


def set_special(index, color):
    """Build the escape sequence for special colors."""
    ColorType.sequences.append(f"\\033]{index};{color}\\007")

    if index == 10:
        ColorType.xrdb.append(f"URxvt*foreground: {color}")
        ColorType.xrdb.append(f"XTerm*foreground: {color}")

    elif index == 11:
        ColorType.xrdb.append(f"URxvt*background: {color}")
        ColorType.xrdb.append(f"XTerm*background: {color}")

    elif index == 12:
        ColorType.xrdb.append(f"URxvt*cursorColor: {color}")
        ColorType.xrdb.append(f"XTerm*cursorColor: {color}")

    elif index == 66:
        ColorType.xrdb.append(f"*.color{index}: {color}")
        ColorType.xrdb.append(f"*color{index}: {color}")
        ColorType.sequences.append(f"\\033]4;{index};{color}\\007")


def set_color(index, color):
    """Build the escape sequence we need for each color."""
    ColorType.xrdb.append(f"*.color{index}: {color}")
    ColorType.xrdb.append(f"*color{index}: {color}")
    ColorType.sequences.append(f"\\033]4;{index};{color}\\007")
    ColorType.shell.append(f"color{index}='{color}'")
    ColorType.css.append(f"\t--color{index}: {color};")
    ColorType.scss.append(f"$color{index}: {color};")

    rgb = hex_to_rgb(color)
    ColorType.putty.append(f"\"Colour{index}\"=\"{rgb}\"")


def set_grey(colors):
    """Set a grey color based on brightness of color0."""
    return {
        0: "#666666",
        1: "#666666",
        2: "#757575",
        3: "#999999",
        4: "#999999",
        5: "#8a8a8a",
        6: "#a1a1a1",
        7: "#a1a1a1",
        8: "#a1a1a1",
        9: "#a1a1a1",
    }.get(int(colors[0][1]), colors[7])


def send_sequences(colors, vte):
    """Send colors to all open terminals."""
    set_special(10, colors[15])
    set_special(11, colors[0])
    set_special(12, colors[15])
    set_special(13, colors[15])
    set_special(14, colors[0])

    # This escape sequence doesn"t work in VTE terminals.
    if not vte:
        set_special(708, colors[0])

    # Create the sequences.
    # pylint: disable=W0106
    [set_color(num, color) for num, color in enumerate(colors)]

    # Set a blank color that isn"t affected by bold highlighting.
    set_special(66, colors[0])

    # Make the terminal interpret escape sequences.
    sequences = fix_escape("".join(ColorType.sequences))

    # Get a list of terminals.
    terminals = [f"/dev/pts/{term}" for term in os.listdir("/dev/pts/")
                 if len(term) < 4]
    terminals.append(CACHE_DIR / "sequences")

    # Send the sequences to all open terminals.
    # pylint: disable=W0106
    [save_file(sequences, term) for term in terminals]

    print("colors: Set terminal colors")


# }}}


# WALLPAPER SETTING {{{


def get_desktop_env():
    """Identify the current running desktop environment."""
    desktop = os.getenv("XDG_CURRENT_DESKTOP")
    if desktop:
        return desktop

    desktop = os.getenv("DESKTOP_SESSION")
    if desktop:
        return desktop

    desktop = os.getenv("GNOME_DESKTOP_SESSION_ID")
    if desktop:
        return "GNOME"

    desktop = os.getenv("MATE_DESKTOP_SESSION_ID")
    if desktop:
        return "MATE"


def xfconf(path, img):
    """Call xfconf to set the wallpaper on XFCE."""
    disown("xfconf-query", "--channel", "xfce4-desktop",
           "--property", path, "--set", img)


def set_desktop_wallpaper(desktop, img):
    """Set the wallpaper for the desktop environment."""
    desktop = str(desktop).lower()

    if "xfce" in desktop or "xubuntu" in desktop:
        # XFCE requires two commands since they differ between versions.
        xfconf("/backdrop/screen0/monitor0/image-path", img)
        xfconf("/backdrop/screen0/monitor0/workspace0/last-image", img)

    elif "muffin" in desktop or "cinnamon" in desktop:
        subprocess.Popen(["gsettings", "set",
                          "org.cinnamon.desktop.background",
                          "picture-uri", "file:///" + img])

    elif "gnome" in desktop:
        subprocess.Popen(["gsettings", "set",
                          "org.gnome.desktop.background",
                          "picture-uri", "file:///" + img])

    elif "mate" in desktop:
        subprocess.Popen(["gsettings", "set", "org.mate.background",
                          "picture-filename", img])


def set_wallpaper(img):
    """Set the wallpaper."""
    desktop = get_desktop_env()

    if desktop:
        set_desktop_wallpaper(desktop, img)

    else:
        if shutil.which("feh"):
            subprocess.Popen(["feh", "--bg-fill", img])

        elif shutil.which("nitrogen"):
            subprocess.Popen(["nitrogen", "--set-zoom-fill", img])

        elif shutil.which("bgs"):
            subprocess.Popen(["bgs", img])

        elif shutil.which("hsetroot"):
            subprocess.Popen(["hsetroot", "-fill", img])

        elif shutil.which("habak"):
            subprocess.Popen(["habak", "-mS", img])

        else:
            print("error: No wallpaper setter found.")
            return

    print("wallpaper: Set the new wallpaper")
    return 0


# }}}


# EXPORT COLORS {{{


def save_colors(colors, export_file, message):
    """Export colors to var format."""
    colors = "\n".join(colors)
    save_file(f"{colors}\n", CACHE_DIR / export_file)
    print(f"export: exported {message}.")


def export_rofi(colors):
    """Append rofi colors to the x_colors list."""
    ColorType.xrdb.append(f"rofi.color-window: {colors[0]}, "
                          f"{colors[0]}, {colors[10]}")
    ColorType.xrdb.append(f"rofi.color-normal: {colors[0]}, "
                          f"{colors[15]}, {colors[0]}, "
                          f"{colors[10]}, {colors[0]}")
    ColorType.xrdb.append(f"rofi.color-active: {colors[0]}, "
                          f"{colors[15]}, {colors[0]}, "
                          f"{colors[10]}, {colors[0]}")
    ColorType.xrdb.append(f"rofi.color-urgent: {colors[0]}, "
                          f"{colors[9]}, {colors[0]}, "
                          f"{colors[9]}, {colors[15]}")


def export_emacs(colors):
    """Set emacs colors."""
    ColorType.xrdb.append(f"emacs*background: {colors[0]}")
    ColorType.xrdb.append(f"emacs*foreground: {colors[15]}")


def reload_xrdb(export_file):
    """Merge the colors into the X db so new terminals use them."""
    if shutil.which("xrdb"):
        subprocess.call(["xrdb", "-merge", CACHE_DIR / export_file])


def reload_i3():
    """Reload i3 colors."""
    if shutil.which("i3-msg"):
        disown("i3-msg", "reload")


def export_colors(colors):
    """Export colors in various formats."""
    save_colors(ColorType.plain, "colors", "plain hex colors")
    save_colors(ColorType.shell, "colors.sh", "shell variables")

    # Web based colors.
    ColorType.css.append("}")
    save_colors(ColorType.css, "colors.css", "css variables")
    save_colors(ColorType.scss, "colors.scss", "scss variables")

    # Text editor based colors.
    save_colors(ColorType.putty, "colors-putty.reg", "putty theme")

    # X based colors.
    export_rofi(colors)
    export_emacs(colors)
    save_colors(ColorType.xrdb, "xcolors", "xrdb colors")

    # i3 colors.
    reload_xrdb("xcolors")
    reload_i3()


# }}}


# OTHER FUNCTIONS {{{


def reload_colors(vte):
    """Reload colors."""
    sequence_file = pathlib.Path(CACHE_DIR / "sequences")

    if sequence_file.is_file():
        sequences = "".join(read_file(sequence_file))

        # If vte mode was used, remove the problem sequence.
        if vte:
            sequences = re.sub(r"\]708;\#.{6}", "", sequences)

        # Make the terminal interpret escape sequences.
        print(fix_escape(sequences), end="")

    exit(0)


def read_file(input_file):
    """Read colors from a file."""
    return open(input_file).read().splitlines()


def save_file(colors, export_file):
    """Write the colors to the file."""
    with open(export_file, "w") as file:
        file.write(colors)


def create_cache_dir():
    """Alias to create the cache dir."""
    pathlib.Path(CACHE_DIR / "schemes").mkdir(parents=True, exist_ok=True)


def hex_to_rgb(color):
    """Convert a hex color to rgb."""
    red, green, blue = list(bytes.fromhex(color.strip("#")))
    return f"{red},{green},{blue}"


def fix_escape(string):
    """Decode a string."""
    return bytes(string, "utf-8").decode("unicode_escape")


def notify(msg):
    """Send arguements to notify-send."""
    if shutil.which("notify-send") and Args.notify:
        subprocess.Popen(["notify-send", msg],
                         stdout=subprocess.DEVNULL,
                         stderr=subprocess.DEVNULL,
                         preexec_fn=os.setpgrp)


def disown(*cmd):
    """Call a system command in the background,
       disown it and hide it's output."""
    subprocess.Popen(["nohup"] + list(cmd),
                     stdout=subprocess.DEVNULL,
                     stderr=subprocess.DEVNULL,
                     preexec_fn=os.setpgrp)


# }}}


def main():
    """Main script function."""
    create_cache_dir()
    args = get_args()
    process_args(args)

    # This saves 10ms.
    # pylint: disable=W0212
    # os._exit(0)


if __name__ == "__main__":
    main()
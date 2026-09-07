#!/usr/bin/env bash
#
# install.sh - Manage symlinks and installation for the i3wm Desktop Environment
#
# Idempotent script to consolidate, back up, and softlink configuration files
# from this repository to their expected locations in $HOME.
#

set -eo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKUP_BASE="${HOME}/.dotfiles_backup"
TIMESTAMP="$(date +%Y%m%d_%H%M%S)"
BACKUP_DIR="${BACKUP_BASE}/${TIMESTAMP}"

DRY_RUN=false
UNLINK_MODE=false
STATUS_MODE=false
RELOAD_MODE=false
CHECK_DEPS=false

# Colors (if terminal supports it)
if [ -t 1 ]; then
    C_RESET="\033[0m"
    C_GREEN="\033[1;32m"
    C_BLUE="\033[1;34m"
    C_YELLOW="\033[1;33m"
    C_RED="\033[1;31m"
    C_CYAN="\033[1;36m"
    C_GRAY="\033[0;90m"
else
    C_RESET=""
    C_GREEN=""
    C_BLUE=""
    C_YELLOW=""
    C_RED=""
    C_CYAN=""
    C_GRAY=""
fi

log_info()    { echo -e "${C_BLUE}ℹ  $*${C_RESET}"; }
log_success() { echo -e "${C_GREEN}✓  $*${C_RESET}"; }
log_warn()    { echo -e "${C_YELLOW}⚠  $*${C_RESET}"; }
log_error()   { echo -e "${C_RED}✖  $*${C_RESET}"; }
log_dim()     { echo -e "${C_GRAY}   $*${C_RESET}"; }

usage() {
    cat << USAGE
i3wm Desktop Environment Dotfiles Installer

Usage:
  ./install.sh [OPTIONS]

Options:
  --status         Show current symlink status for all managed configs
  --dry-run        Simulate operations without touching the filesystem
  --unlink         Remove managed symlinks
  --reload         Reload i3, Polybar, and Picom in-place
  --check-deps     Verify installed system packages and dependencies
  --backup-dir <D> Specify a custom backup directory
  --help, -h       Display this help message

Managed components:
  config/i3        -> ~/.config/i3
  config/polybar   -> ~/.config/polybar
  config/picom     -> ~/.config/picom
  config/dunst     -> ~/.config/dunst
  bin/*            -> ~/.local/bin/*
  home/* (dotfiles)-> ~/*

USAGE
    exit 0
}

# Parse command line flags
while [[ $# -gt 0 ]]; do
    case "$1" in
        --dry-run)
            DRY_RUN=true
            shift
            ;;
        --unlink)
            UNLINK_MODE=true
            shift
            ;;
        --status)
            STATUS_MODE=true
            shift
            ;;
        --reload)
            RELOAD_MODE=true
            shift
            ;;
        --check-deps)
            CHECK_DEPS=true
            shift
            ;;
        --backup-dir)
            BACKUP_DIR="$2"
            shift 2
            ;;
        -h|--help)
            usage
            ;;
        *)
            log_error "Unknown argument: $1"
            echo "Run ./install.sh --help for usage information."
            exit 1
            ;;
    esac
done

ensure_executable_permissions() {
    # Ensure scripts have +x set
    find "${REPO_DIR}/bin" -type f -exec chmod +x {} + 2>/dev/null || true
    find "${REPO_DIR}/config/polybar" -type f \( -name "*.sh" -o -name "*.py" \) -exec chmod +x {} + 2>/dev/null || true
    if [ -f "${REPO_DIR}/home/.fehbg" ]; then
        chmod +x "${REPO_DIR}/home/.fehbg" 2>/dev/null || true
    fi
}

check_dependencies() {
    echo -e "${C_CYAN}=== Checking Desktop Environment Dependencies ===${C_RESET}"
    local core_deps=("i3" "polybar" "picom" "dunst" "feh" "python3")
    local extra_deps=("rofi" "playerctl" "tmux" "maim" "nm-applet" "xss-lock" "i3lock" "wpctl")

    echo -e "\n${C_BLUE}Core Components:${C_RESET}"
    for cmd in "${core_deps[@]}"; do
        if command -v "$cmd" >/dev/null 2>&1; then
            echo -e "  [${C_GREEN}INSTALLED${C_RESET}] $cmd -> $(command -v "$cmd")"
        else
            echo -e "  [${C_RED}MISSING  ${C_RESET}] $cmd"
        fi
    done

    echo -e "\n${C_BLUE}Desktop Utilities:${C_RESET}"
    for cmd in "${extra_deps[@]}"; do
        if command -v "$cmd" >/dev/null 2>&1; then
            echo -e "  [${C_GREEN}INSTALLED${C_RESET}] $cmd -> $(command -v "$cmd")"
        else
            echo -e "  [${C_YELLOW}OPTIONAL ${C_RESET}] $cmd (run: sudo apt install $cmd)"
        fi
    done
    echo ""
}

# List all mappings as: "SRC_REL" "DEST_REL_TO_HOME" "TYPE(dir|file)"
get_mappings() {
    # 1. Config directories
    for dir in "${REPO_DIR}/config"/*; do
        if [ -d "$dir" ]; then
            local base
            base="$(basename "$dir")"
            echo "config/${base}|.config/${base}|dir"
        fi
    done

    # 2. Executables in bin/
    if [ -d "${REPO_DIR}/bin" ]; then
        for file in "${REPO_DIR}/bin"/*; do
            if [ -f "$file" ]; then
                local base
                base="$(basename "$file")"
                echo "bin/${base}|.local/bin/${base}|file"
            fi
        done
    fi

    # 3. Root dotfiles in home/
    if [ -d "${REPO_DIR}/home" ]; then
        shopt -s nullglob dotglob
        for file in "${REPO_DIR}/home"/*; do
            if [ -f "$file" ]; then
                local base
                base="$(basename "$file")"
                echo "home/${base}|${base}|file"
            fi
        done
        shopt -u nullglob dotglob
    fi
}

check_status() {
    echo -e "${C_CYAN}=== Managed Configuration Symlink Status ===${C_RESET}\n"
    printf "%-32s -> %-36s [%s]\n" "Source in Repo" "Destination in \$HOME" "Status"
    echo "--------------------------------------------------------------------------------"

    get_mappings | while IFS='|' read -r src_rel dest_rel type; do
        local src="${REPO_DIR}/${src_rel}"
        local dest="${HOME}/${dest_rel}"
        local status_label

        if [ -L "$dest" ]; then
            local target
            target="$(readlink "$dest" || true)"
            local target_abs
            target_abs="$(readlink -f "$dest" || true)"
            local src_abs
            src_abs="$(readlink -f "$src" || true)"

            if [ "$target_abs" == "$src_abs" ]; then
                status_label="${C_GREEN}LINKED (OK)${C_RESET}"
            else
                status_label="${C_RED}WRONG LINK -> ${target}${C_RESET}"
            fi
        elif [ -e "$dest" ]; then
            status_label="${C_YELLOW}LOCAL (Unlinked file/dir)${C_RESET}"
        else
            status_label="${C_GRAY}NOT INSTALLED${C_RESET}"
        fi

        printf "%-32s -> %-36s [%b]\n" "$src_rel" "~/$dest_rel" "$status_label"
    done
    echo ""
}

unlink_all() {
    echo -e "${C_CYAN}=== Unlinking Managed Dotfiles ===${C_RESET}\n"

    get_mappings | while IFS='|' read -r src_rel dest_rel type; do
        local src="${REPO_DIR}/${src_rel}"
        local dest="${HOME}/${dest_rel}"

        if [ -L "$dest" ]; then
            local target_abs
            target_abs="$(readlink -f "$dest" || true)"
            local src_abs
            src_abs="$(readlink -f "$src" || true)"

            if [ "$target_abs" == "$src_abs" ]; then
                if [ "$DRY_RUN" = true ]; then
                    log_dim "[DRY-RUN] Would remove symlink: $dest"
                else
                    rm "$dest"
                    log_warn "Removed symlink: ~/$dest_rel"
                fi
            else
                log_dim "Skipping ~/$dest_rel (points elsewhere: $(readlink "$dest"))"
            fi
        else
            log_dim "Skipping ~/$dest_rel (not a symlink)"
        fi
    done
    log_success "Unlink operations completed."
}

link_all() {
    echo -e "${C_CYAN}=== Installing & Softlinking Configurations ===${C_RESET}\n"

    local backup_performed=false

    # Ensure parent destinations exist
    if [ "$DRY_RUN" = false ]; then
        mkdir -p "${HOME}/.config" "${HOME}/.local/bin"
        ensure_executable_permissions
    fi

    get_mappings | while IFS='|' read -r src_rel dest_rel type; do
        local src="${REPO_DIR}/${src_rel}"
        local dest="${HOME}/${dest_rel}"
        local dest_parent
        dest_parent="$(dirname "$dest")"

        # Check if already correctly linked
        if [ -L "$dest" ]; then
            local target_abs
            target_abs="$(readlink -f "$dest" || true)"
            local src_abs
            src_abs="$(readlink -f "$src" || true)"

            if [ "$target_abs" == "$src_abs" ]; then
                log_dim "Already linked: ~/$dest_rel -> $src_rel"
                continue
            fi
        fi

        # If dest exists (file, directory, or broken symlink), back it up
        if [ -e "$dest" ] || [ -L "$dest" ]; then
            if [ "$DRY_RUN" = true ]; then
                log_dim "[DRY-RUN] Would backup existing ~/$dest_rel to ${BACKUP_DIR}/$dest_rel"
                log_dim "[DRY-RUN] Would symlink ~/$dest_rel -> $src"
                continue
            else
                mkdir -p "${BACKUP_DIR}/$(dirname "$dest_rel")"
                # Move to backup
                mv "$dest" "${BACKUP_DIR}/${dest_rel}"
                log_warn "Backed up existing ~/$dest_rel -> ${BACKUP_DIR}/$dest_rel"
                backup_performed=true
            fi
        else
            if [ "$DRY_RUN" = true ]; then
                log_dim "[DRY-RUN] Would create directory $(dirname "$dest") and symlink ~/$dest_rel -> $src"
                continue
            fi
        fi

        # Create parent directory if needed
        mkdir -p "$dest_parent"

        # Create symlink
        ln -sn "$src" "$dest"
        log_success "Linked: ~/$dest_rel -> $src"
    done

    if [ "$backup_performed" = true ]; then
        echo ""
        log_info "Original non-symlink files backed up to: ${BACKUP_DIR}"
    fi

    echo ""
    log_success "All configurations softlinked successfully!"
}

reload_environment() {
    echo -e "\n${C_CYAN}=== Reloading Desktop Environment Components ===${C_RESET}"

    # 1. Reload i3wm
    if pgrep -x i3 >/dev/null 2>&1; then
        if command -v i3-msg >/dev/null 2>&1; then
            i3-msg -q reload && log_success "i3 configuration reloaded" || log_warn "Failed to reload i3"
        fi
    else
        log_dim "i3 is not currently running"
    fi

    # 2. Restart Polybar
    if [ -x "${REPO_DIR}/config/polybar/launch.sh" ]; then
        if pgrep -x polybar >/dev/null 2>&1; then
            "${REPO_DIR}/config/polybar/launch.sh" >/dev/null 2>&1 &
            log_success "Polybar restarted"
        else
            log_dim "Polybar is not currently running"
        fi
    fi

    # 3. Dunst reload
    if pgrep -x dunst >/dev/null 2>&1; then
        killall -q dunst || true
        dunst >/dev/null 2>&1 &
        log_success "Dunst restarted"
    fi

    # 4. Picom reload
    if pgrep -x picom >/dev/null 2>&1; then
        killall -q picom || true
        picom --config "${HOME}/.config/picom/picom.conf" -b >/dev/null 2>&1 &
        log_success "Picom restarted"
    fi

    # 5. Ultrawide layout daemon
    if pgrep -f "i3-single-center.py" >/dev/null 2>&1; then
        pkill -f "i3-single-center.py" || true
        sleep 0.2
    fi
    nohup "${HOME}/.local/bin/i3-single-center.py" >/dev/null 2>&1 &
    log_success "Centered Master layout daemon restarted"
}

# Main execution flow
if [ "$CHECK_DEPS" = true ]; then
    check_dependencies
    exit 0
fi

if [ "$STATUS_MODE" = true ]; then
    check_status
    exit 0
fi

if [ "$UNLINK_MODE" = true ]; then
    unlink_all
    exit 0
fi

link_all

if [ "$RELOAD_MODE" = true ]; then
    reload_environment
fi

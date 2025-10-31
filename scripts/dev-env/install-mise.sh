#!/usr/bin/env bash

# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0

set -eu

__mise_bootstrap() {
    local script_dir=$( cd -- "$( dirname -- "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )
    local project_dir=$( cd -- "$( dirname -- "$script_dir" )" &> /dev/null && pwd )
    export MISE_BOOTSTRAP_PROJECT_DIR="$project_dir"
    local cache_home="${XDG_CACHE_HOME:-$HOME/.cache}/mise"
    export MISE_INSTALL_PATH="$cache_home/mise-2025.10.20"
    install() {
        #!/bin/sh
        set -eu

        #region logging setup
        if [ "${MISE_DEBUG-}" = "true" ] || [ "${MISE_DEBUG-}" = "1" ]; then
          debug() {
            echo "$@" >&2
          }
        else
          debug() {
            :
          }
        fi

        if [ "${MISE_QUIET-}" = "1" ] || [ "${MISE_QUIET-}" = "true" ]; then
          info() {
            :
          }
        else
          info() {
            echo "$@" >&2
          }
        fi

        error() {
          echo "$@" >&2
          exit 1
        }
        #endregion

        #region environment setup
        get_os() {
          os="$(uname -s)"
          if [ "$os" = Darwin ]; then
            echo "macos"
          elif [ "$os" = Linux ]; then
            echo "linux"
          else
            error "unsupported OS: $os"
          fi
        }

        get_arch() {
          musl=""
          if type ldd >/dev/null 2>/dev/null; then
            if [ "${MISE_INSTALL_MUSL-}" = "1" ] || [ "${MISE_INSTALL_MUSL-}" = "true" ]; then
              musl="-musl"
            else
              libc=$(ldd /bin/ls | grep 'musl' | head -1 | cut -d ' ' -f1)
              if [ -n "$libc" ]; then
                musl="-musl"
              fi
            fi
          fi
          arch="$(uname -m)"
          if [ "$arch" = x86_64 ]; then
            echo "x64$musl"
          elif [ "$arch" = aarch64 ] || [ "$arch" = arm64 ]; then
            echo "arm64$musl"
          elif [ "$arch" = armv7l ]; then
            echo "armv7$musl"
          else
            error "unsupported architecture: $arch"
          fi
        }

        get_ext() {
          if [ -n "${MISE_INSTALL_EXT:-}" ]; then
            echo "$MISE_INSTALL_EXT"
          elif [ -n "${MISE_VERSION:-}" ] && echo "$MISE_VERSION" | grep -q '^v2024'; then
            # 2024 versions don't have zstd tarballs
            echo "tar.gz"
          elif tar_supports_zstd; then
            echo "tar.zst"
          elif command -v zstd >/dev/null 2>&1; then
            echo "tar.zst"
          else
            echo "tar.gz"
          fi
        }

        tar_supports_zstd() {
          # tar is bsdtar or version is >= 1.31
          if tar --version | grep -q 'bsdtar' && command -v zstd >/dev/null 2>&1; then
            true
          elif tar --version | grep -q '1\.(3[1-9]|[4-9][0-9]'; then
            true
          else
            false
          fi
        }

        shasum_bin() {
          if command -v shasum >/dev/null 2>&1; then
            echo "shasum"
          elif command -v sha256sum >/dev/null 2>&1; then
            echo "sha256sum"
          else
            error "mise install requires shasum or sha256sum but neither is installed. Aborting."
          fi
        }

        get_checksum() {
          version=$1
          os=$2
          arch=$3
          ext=$4
          url="https://github.com/jdx/mise/releases/download/v${version}/SHASUMS256.txt"

          # For current version use static checksum otherwise
          # use checksum from releases
          if [ "$version" = "v2025.10.20" ]; then
            checksum_linux_x86_64="87ada958f279bb6b92f7d6452829e12a62edd5ab4c4b7ac09a126fb2816949ff  ./mise-v2025.10.20-linux-x64.tar.gz"
            checksum_linux_x86_64_musl="1ecbe5dfb63283a15b6c844cac015301f0dab7a279d28b4642087e6ca0657328  ./mise-v2025.10.20-linux-x64-musl.tar.gz"
            checksum_linux_arm64="cc5e449045b85562a2251af9a64f98e54e6812f05710e1580991cbf43a6a2378  ./mise-v2025.10.20-linux-arm64.tar.gz"
            checksum_linux_arm64_musl="9af62c4c55360559be781b4a377a07b3a25bfc0d928fb4ba450e492fddc5264e  ./mise-v2025.10.20-linux-arm64-musl.tar.gz"
            checksum_linux_armv7="d3ae3133f88cd32d9be9b6fbd46aa5f06d39e1e3f9eae4c2efc21fe7b8ca9f53  ./mise-v2025.10.20-linux-armv7.tar.gz"
            checksum_linux_armv7_musl="61717231a8e3a46db7961523e434c9b5e0ba01161dc8b6999ebf8f05340de8e0  ./mise-v2025.10.20-linux-armv7-musl.tar.gz"
            checksum_macos_x86_64="5f3ff9f26f2ba8129544f42dbced868acdf9dc135fbca20e074d5a37ab47e620  ./mise-v2025.10.20-macos-x64.tar.gz"
            checksum_macos_arm64="e0500b06be66f7f18a3d746085894a130a21e428d76987577ae142667a84edd0  ./mise-v2025.10.20-macos-arm64.tar.gz"
            checksum_linux_x86_64_zstd="0b001d6159606860d3d5cd9cbef85ac131d9bd4f343f743148ff0874a378bda2  ./mise-v2025.10.20-linux-x64.tar.zst"
            checksum_linux_x86_64_musl_zstd="60995c808f6f19629b9a0f79af6407ae84a4e9a4fa1283754e8752441c73c7d9  ./mise-v2025.10.20-linux-x64-musl.tar.zst"
            checksum_linux_arm64_zstd="d5f74292ed482129e2728833f72eeeb129a0600ca1a4ca408c3c1b0a61203ecc  ./mise-v2025.10.20-linux-arm64.tar.zst"
            checksum_linux_arm64_musl_zstd="d64f172de73b0a2879da4634ce8b4be0627164c9538ab880eb5edf2e1c35bc66  ./mise-v2025.10.20-linux-arm64-musl.tar.zst"
            checksum_linux_armv7_zstd="9c9791ad382fbbe654c251a47655783faf48d9d265966f769420deb4f7c4aa43  ./mise-v2025.10.20-linux-armv7.tar.zst"
            checksum_linux_armv7_musl_zstd="3bf242ccdc99cb220fe956278af72eba1c2d3880e564a9b8d6fff9606cce2676  ./mise-v2025.10.20-linux-armv7-musl.tar.zst"
            checksum_macos_x86_64_zstd="b4d5cac0e7d075cb5a3e9a1f2d7a3895c7dba630a5f68a789464c6799d58c0a4  ./mise-v2025.10.20-macos-x64.tar.zst"
            checksum_macos_arm64_zstd="e53be73302ee61f44e5989fc85ab38b0ab0ac7debbc733554745b77d7616e23e  ./mise-v2025.10.20-macos-arm64.tar.zst"

            # TODO: refactor this, it's a bit messy
            if [ "$ext" = "tar.zst" ]; then
              if [ "$os" = "linux" ]; then
                if [ "$arch" = "x64" ]; then
                  echo "$checksum_linux_x86_64_zstd"
                elif [ "$arch" = "x64-musl" ]; then
                  echo "$checksum_linux_x86_64_musl_zstd"
                elif [ "$arch" = "arm64" ]; then
                  echo "$checksum_linux_arm64_zstd"
                elif [ "$arch" = "arm64-musl" ]; then
                  echo "$checksum_linux_arm64_musl_zstd"
                elif [ "$arch" = "armv7" ]; then
                  echo "$checksum_linux_armv7_zstd"
                elif [ "$arch" = "armv7-musl" ]; then
                  echo "$checksum_linux_armv7_musl_zstd"
                else
                  warn "no checksum for $os-$arch"
                fi
              elif [ "$os" = "macos" ]; then
                if [ "$arch" = "x64" ]; then
                  echo "$checksum_macos_x86_64_zstd"
                elif [ "$arch" = "arm64" ]; then
                  echo "$checksum_macos_arm64_zstd"
                else
                  warn "no checksum for $os-$arch"
                fi
              else
                warn "no checksum for $os-$arch"
              fi
            else
              if [ "$os" = "linux" ]; then
                if [ "$arch" = "x64" ]; then
                  echo "$checksum_linux_x86_64"
                elif [ "$arch" = "x64-musl" ]; then
                  echo "$checksum_linux_x86_64_musl"
                elif [ "$arch" = "arm64" ]; then
                  echo "$checksum_linux_arm64"
                elif [ "$arch" = "arm64-musl" ]; then
                  echo "$checksum_linux_arm64_musl"
                elif [ "$arch" = "armv7" ]; then
                  echo "$checksum_linux_armv7"
                elif [ "$arch" = "armv7-musl" ]; then
                  echo "$checksum_linux_armv7_musl"
                else
                  warn "no checksum for $os-$arch"
                fi
              elif [ "$os" = "macos" ]; then
                if [ "$arch" = "x64" ]; then
                  echo "$checksum_macos_x86_64"
                elif [ "$arch" = "arm64" ]; then
                  echo "$checksum_macos_arm64"
                else
                  warn "no checksum for $os-$arch"
                fi
              else
                warn "no checksum for $os-$arch"
              fi
            fi
          else
            if command -v curl >/dev/null 2>&1; then
              debug ">" curl -fsSL "$url"
              checksums="$(curl --compressed -fsSL "$url")"
            else
              if command -v wget >/dev/null 2>&1; then
                debug ">" wget -qO - "$url"
                stderr=$(mktemp)
                checksums="$(wget -qO - "$url")"
              else
                error "mise standalone install specific version requires curl or wget but neither is installed. Aborting."
              fi
            fi
            # TODO: verify with minisign or gpg if available

            checksum="$(echo "$checksums" | grep "$os-$arch.$ext")"
            if ! echo "$checksum" | grep -Eq "^([0-9a-f]{32}|[0-9a-f]{64})"; then
              warn "no checksum for mise $version and $os-$arch"
            else
              echo "$checksum"
            fi
          fi
        }

        #endregion

        download_file() {
          url="$1"
          filename="$(basename "$url")"
          cache_dir="$(mktemp -d)"
          file="$cache_dir/$filename"

          info "mise: installing mise..."

          if command -v curl >/dev/null 2>&1; then
            debug ">" curl -#fLo "$file" "$url"
            curl -#fLo "$file" "$url"
          else
            if command -v wget >/dev/null 2>&1; then
              debug ">" wget -qO "$file" "$url"
              stderr=$(mktemp)
              wget -O "$file" "$url" >"$stderr" 2>&1 || error "wget failed: $(cat "$stderr")"
            else
              error "mise standalone install requires curl or wget but neither is installed. Aborting."
            fi
          fi

          echo "$file"
        }

        install_mise() {
          version="${MISE_VERSION:-v2025.10.20}"
          version="${version#v}"
          os="${MISE_INSTALL_OS:-$(get_os)}"
          arch="${MISE_INSTALL_ARCH:-$(get_arch)}"
          ext="${MISE_INSTALL_EXT:-$(get_ext)}"
          install_path="${MISE_INSTALL_PATH:-$HOME/.local/bin/mise}"
          install_dir="$(dirname "$install_path")"
          install_from_github="${MISE_INSTALL_FROM_GITHUB:-}"
          if [ "$version" != "v2025.10.20" ] || [ "$install_from_github" = "1" ] || [ "$install_from_github" = "true" ]; then
            tarball_url="https://github.com/jdx/mise/releases/download/v${version}/mise-v${version}-${os}-${arch}.${ext}"
          elif [ -n "${MISE_TARBALL_URL-}" ]; then
            tarball_url="$MISE_TARBALL_URL"
          else
            tarball_url="https://mise.jdx.dev/v${version}/mise-v${version}-${os}-${arch}.${ext}"
          fi

          cache_file=$(download_file "$tarball_url")
          debug "mise-setup: tarball=$cache_file"

          debug "validating checksum"
          cd "$(dirname "$cache_file")" && get_checksum "$version" "$os" "$arch" "$ext" | "$(shasum_bin)" -c >/dev/null

          # extract tarball
          mkdir -p "$install_dir"
          rm -rf "$install_path"
          cd "$(mktemp -d)"
          if [ "$ext" = "tar.zst" ] && ! tar_supports_zstd; then
            zstd -d -c "$cache_file" | tar -xf -
          else
            tar -xf "$cache_file"
          fi
          mv mise/bin/mise "$install_path"
          info "mise: installed successfully to $install_path"
        }

        after_finish_help() {
          case "${SHELL:-}" in
          */zsh)
            info "mise: run the following to activate mise in your shell:"
            info "echo \"eval \\\"\\\$($install_path activate zsh)\\\"\" >> \"${ZDOTDIR-$HOME}/.zshrc\""
            info ""
            info "mise: run \`mise doctor\` to verify this is setup correctly"
            ;;
          */bash)
            info "mise: run the following to activate mise in your shell:"
            info "echo \"eval \\\"\\\$($install_path activate bash)\\\"\" >> ~/.bashrc"
            info ""
            info "mise: run \`mise doctor\` to verify this is setup correctly"
            ;;
          */fish)
            info "mise: run the following to activate mise in your shell:"
            info "echo \"$install_path activate fish | source\" >> ~/.config/fish/config.fish"
            info ""
            info "mise: run \`mise doctor\` to verify this is setup correctly"
            ;;
          *)
            info "mise: run \`$install_path --help\` to get started"
            ;;
          esac
        }

        install_mise
        if [ "${MISE_INSTALL_HELP-}" != 0 ]; then
          after_finish_help
        fi

        cd "$MISE_BOOTSTRAP_PROJECT_DIR"
    }
    local MISE_INSTALL_HELP=0
    test -f "$MISE_INSTALL_PATH" || install
}
__mise_bootstrap
exec "$MISE_INSTALL_PATH" "$@"

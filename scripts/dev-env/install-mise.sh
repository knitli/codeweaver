#!/usr/bin/env bash

# SPDX-FileCopyrightText: 2025 Knitli Inc. <knitli@knit.li>
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0

set -eu

__mise_bootstrap()
                   {
    local script_dir
    script_dir=$( cd -- "$( dirname -- "${BASH_SOURCE[0]}")"  &> /dev/null && pwd)
    local project_dir
    project_dir=$( cd -- "$( dirname -- "$script_dir")"  &> /dev/null && pwd)
    export MISE_BOOTSTRAP_PROJECT_DIR="$project_dir"
    local cache_home="${XDG_CACHE_HOME:-$HOME/.cache}/mise"
    export MISE_INSTALL_PATH="$cache_home/mise-2025.7.0"
    install()
              {
        #!/bin/sh
        set -eu

        #region logging setup
        if [ "${MISE_DEBUG-}" = "true" ] || [ "${MISE_DEBUG-}" = "1" ]; then
            debug()
                  {
                echo "$@" >&2
            }
        else
            debug()
                  {
                :
            }
        fi

        if [ "${MISE_QUIET-}" = "1" ] || [ "${MISE_QUIET-}" = "true" ]; then
            info()
                 {
                :
            }
        else
            info()
                 {
                echo "$@" >&2
            }
        fi

        error()
                {
            echo "$@" >&2
            exit 1
        }
        #endregion

        #region environment setup
        get_os()
                 {
            os="$(uname -s)"
            if [ "$os" = Darwin ]; then
                echo "macos"
            elif [ "$os" = Linux ]; then
                echo "linux"
            else
                error "unsupported OS: $os"
            fi
        }

        get_arch()
                   {
            musl=""
            if type ldd > /dev/null 2> /dev/null; then
                libc=$(ldd /bin/ls | grep 'musl' | head -1 | cut -d ' ' -f1)
                if [ -n "$libc" ]; then
                    musl="-musl"
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

        get_ext()
                  {
            if [ -n "${MISE_INSTALL_EXT:-}" ]; then
                echo "$MISE_INSTALL_EXT"
            elif [ -n "${MISE_VERSION:-}" ] && echo "$MISE_VERSION" | grep -q '^v2024'; then
                # 2024 versions don't have zstd tarballs
                echo "tar.gz"
            elif tar_supports_zstd; then
                echo "tar.zst"
            elif command -v zstd > /dev/null 2>&1; then
                echo "tar.zst"
            else
                echo "tar.gz"
            fi
        }

        tar_supports_zstd()
                            {
            # tar is bsdtar or version is >= 1.31
            if tar --version | grep -q 'bsdtar' && command -v zstd > /dev/null 2>&1; then
                true
            elif tar --version | grep -q '1\.(3[1-9]|[4-9][0-9]'; then
                true
            else
                false
            fi
        }

        shasum_bin()
                     {
            if command -v shasum > /dev/null 2>&1; then
                echo "shasum"
            elif command -v sha256sum > /dev/null 2>&1; then
                echo "sha256sum"
            else
                error "mise install requires shasum or sha256sum but neither is installed. Aborting."
            fi
        }

        get_checksum()
                       {
            version=$1
            os="$(get_os)"
            arch="$(get_arch)"
            ext="$(get_ext)"
            url="https://github.com/jdx/mise/releases/download/v${version}/SHASUMS256.txt"

            # For current version use static checksum otherwise
            # use checksum from releases
            if [ "$version" = "v2025.7.0" ]; then
                checksum_linux_x86_64="6acf15c581d25897b9296d158b2107eb4ef80032944685ac4a4884ec214abcac  ./mise-v2025.7.0-linux-x64.tar.gz"
                checksum_linux_x86_64_musl="d0707ea8f10977681bdc4c666626b6be69f644e0cf686b200db0165d5e7a648d  ./mise-v2025.7.0-linux-x64-musl.tar.gz"
                checksum_linux_arm64="51c5a1edbdb5fb6a0db048edae30bce53cff35965b06f2ee8f515fd06fd6875e  ./mise-v2025.7.0-linux-arm64.tar.gz"
                checksum_linux_arm64_musl="fe6f891a3f8b1a5618da7af198e3f9077d48b593714f8fd982af19c0bd558236  ./mise-v2025.7.0-linux-arm64-musl.tar.gz"
                checksum_linux_armv7="d1d88b9cd5e7f3418bdbb9c906fa2099d73f9bb8cdcc6fccb4f4f7cde98a88d9  ./mise-v2025.7.0-linux-armv7.tar.gz"
                checksum_linux_armv7_musl="b78a914d81951a366d56b3328dcb0589ac227564350a1cd51dd104d0b47fb00b  ./mise-v2025.7.0-linux-armv7-musl.tar.gz"
                checksum_macos_x86_64="e00f1dcecb36d507afa59577e3cef128cfcfe42f76fe1fb1a57be7e012c7cfd6  ./mise-v2025.7.0-macos-x64.tar.gz"
                checksum_macos_arm64="23f16ff52dc867e6805a50dfb7d43991fdc19832c9b21c8182e4bd389c1d2748  ./mise-v2025.7.0-macos-arm64.tar.gz"
                checksum_linux_x86_64_zstd="7e72bcd361321d0c374b1c17a182cb4ef23211a6d9a5da59ca97031ccf10aa4f  ./mise-v2025.7.0-linux-x64.tar.zst"
                checksum_linux_x86_64_musl_zstd="5dce4d79ea784539335b77b0b0ef98c2e9cd7aa81fc6d8982001eff9cbaa4d32  ./mise-v2025.7.0-linux-x64-musl.tar.zst"
                checksum_linux_arm64_zstd="edceac8b78350480ccecffb22471e0f9251867f15942c65363e766f8c27dfb26  ./mise-v2025.7.0-linux-arm64.tar.zst"
                checksum_linux_arm64_musl_zstd="382567f67e4db1db4281338a5b7d28b850fd24e95ee9ea5e38737e83824a7ea9  ./mise-v2025.7.0-linux-arm64-musl.tar.zst"
                checksum_linux_armv7_zstd="f161c71753e99c11280e20e607360084bbd296a41b4f55970237b880db0008b3  ./mise-v2025.7.0-linux-armv7.tar.zst"
                checksum_linux_armv7_musl_zstd="11529e746ab4ccef42936031e66b510f2807d6697f8d381dbc2f7b8e4410e804  ./mise-v2025.7.0-linux-armv7-musl.tar.zst"
                checksum_macos_x86_64_zstd="86272dc669887d27f1f2d29456db2bd8ed6b514ff4ec183545d675a864856b81  ./mise-v2025.7.0-macos-x64.tar.zst"
                checksum_macos_arm64_zstd="b8426a5530ab1da9ef8ada9d2f3c3869ea1abd552480e9a86f461d6fe000a909  ./mise-v2025.7.0-macos-arm64.tar.zst"

                # TODO: refactor this, it's a bit messy
                if [ "$(get_ext)" = "tar.zst" ]; then
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
                if command -v curl > /dev/null 2>&1; then
                    debug ">" curl -fsSL "$url"
                    checksums="$(curl --compressed -fsSL "$url")"
                else
                    if command -v wget > /dev/null 2>&1; then
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

        download_file()
                        {
            url="$1"
            filename="$(basename "$url")"
            cache_dir="$(mktemp -d)"
            file="$cache_dir/$filename"

            info "mise: installing mise..."

            if command -v curl > /dev/null 2>&1; then
                debug ">" curl -#fLo "$file" "$url"
                curl -#fLo "$file" "$url"
            else
                if command -v wget > /dev/null 2>&1; then
                    debug ">" wget -qO "$file" "$url"
                    stderr=$(mktemp)
                    wget -O "$file" "$url" > "$stderr" 2>&1 || error "wget failed: $(cat "$stderr")"
                else
                    error "mise standalone install requires curl or wget but neither is installed. Aborting."
                fi
            fi

            echo "$file"
        }

        install_mise()
                       {
            version="${MISE_VERSION:-v2025.7.0}"
            version="${version#v}"
            os="$(get_os)"
            arch="$(get_arch)"
            ext="$(get_ext)"
            install_path="${MISE_INSTALL_PATH:-$HOME/.local/bin/mise}"
            install_dir="$(dirname "$install_path")"
            tarball_url="https://github.com/jdx/mise/releases/download/v${version}/mise-v${version}-${os}-${arch}.${ext}"

            cache_file=$(download_file "$tarball_url")
            debug "mise-setup: tarball=$cache_file"

            debug "validating checksum"
            cd "$(dirname "$cache_file")" && get_checksum "$version" | "$(shasum_bin)" -c > /dev/null

            # extract tarball
            mkdir -p "$install_dir"
            rm -rf "$install_path"
            cd "$(mktemp -d)"
            if [ "$(get_ext)" = "tar.zst" ] && ! tar_supports_zstd; then
                zstd -d -c "$cache_file" | tar -xf -
            else
                tar -xf "$cache_file"
            fi
            mv mise/bin/mise "$install_path"
            info "mise: installed successfully to $install_path"
        }

        after_finish_help()
                            {
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

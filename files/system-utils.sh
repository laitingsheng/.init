function _dircolors() {
    [ -r ~/.dircolors ] && eval "$($1 -b ~/.dircolors)" || eval "$($1 -b)"
}

function _wrap_colour() {
    prefix=$1
    shift 1

    for command in $*
    do
        name="${prefix}${command}"
        alias ${name}="${name} --color=auto"
    done
}

function _augment_gnu_ls() {
    ls="${1:-}ls"
    alias ${ls}="${ls} --color=auto --group-directories-first"
}

function _ls_aliases() {
    prefix=${1:-}
    ls="${prefix}ls"
    alias "${prefix}l"="${ls} -CF"
    alias "${prefix}la"="${ls} -AF"
    alias "${prefix}ll"="${ls} -alhF"
}

case $OSTYPE in
    darwin*)
        export CLICOLOR=1

        alias ls='ls -G'
        _wrap_colour '' grep egrep fgrep
        _ls_aliases

        _dircolors "$(brew --prefix)/bin/gdircolors"
        _wrap_colour g dir vdir grep egrep fgrep
        _augment_gnu_ls g
        _ls_aliases g
        ;;
    linux*)
        _dircolors '/usr/bin/dircolors'
        _wrap_colour '' dir vdir grep egrep fgrep
        _augment_gnu_ls
        _ls_aliases

        case $(uname -r) in
            *-microsoft-standard-WSL2)
                PATH="$PATH:/mnt/c/Windows/System32:/mnt/c/Windows"
                ;;
        esac
        ;;
    *)
        echo "system-utils: cannot recognise the OS type (${OSTYPE:-unknown})" >&2
        echo 'system-utils: nothing has been modified' >&2
        ;;
esac

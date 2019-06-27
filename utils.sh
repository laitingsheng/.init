# colours
NC='\033[0m'
RED='\033[0;31m'
YELLOW='\033[1;33m'

# logging levels
INFO="${YELLOW}INFO${NC}"
WARNING="${RED}WARNING${NC}"

info_echo() {
	printf "$INFO: $*\n"
}

info_printf() {
	printf "$INFO: $*"
}

warning_echo() {
	printf "$WARNING: $*\n" >&2
}

warning_printf() {
	printf "$WARNING: $*" >&2
}

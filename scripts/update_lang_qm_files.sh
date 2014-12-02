PWD="$(pwd -P)"

MAIN_DIR="$(cd "$(dirname "$0")/../lxnstack" && pwd -P)"
LANG_DIR="${MAIN_DIR}/data/lang"

cd "${LANG_DIR}"

for langfile in $(find ${LANG_DIR} -name "*.ts")
{
    lrelease ${langfile}
}

cd "${PWD}"

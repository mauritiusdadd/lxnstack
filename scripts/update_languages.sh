PWD="$(pwd -P)"

MAIN_DIR="$(cd "$(dirname "$0")/../lxnstack" && pwd -P)"

source_files=$(find ${MAIN_DIR} -name "*.py" -or -name "*.ui")

cd "${MAIN_DIR}/data/lang"

pylupdate4 -noobsolete ${source_files} -ts ./lang_it_IT.ts
pylupdate4 -noobsolete ${source_files} -ts ./lang_en_US.ts

cd "${PWD}"
export TS_FILES=$(ls ./lang | grep .ts)

for x in $TS_FILES
{
    lrelease ./lang/$x
}
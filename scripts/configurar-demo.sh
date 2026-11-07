#!/bin/sh
set -eu

cd "$(dirname "$0")/../Alimenta/marachef_mvp_funcional/marachef_mvp"
if [ -e .env ]; then
    printf '%s\n' 'O .env existente foi preservado.'
    exit 0
fi

secret() {
    od -An -N32 -tx1 /dev/urandom | tr -d ' \n'
}

db_password=$(secret)
session_secret=$(secret)
if [ "${#db_password}" -ne 64 ] || [ "${#session_secret}" -ne 64 ]; then
    printf '%s\n' 'Não foi possível gerar os segredos locais.' >&2
    exit 1
fi

(
    umask 077
    set -C
    cr=$(printf '\r')
    sed -e "s/${cr}\$//" \
        -e "s/^POSTGRES_PASSWORD=$/POSTGRES_PASSWORD=$db_password/" \
        -e "s|^DATABASE_URL=$|DATABASE_URL=postgresql://marachef:${db_password}@127.0.0.1:5433/marachef|" \
        -e "s/^MARACHEF_SESSION_SECRET=$/MARACHEF_SESSION_SECRET=$session_secret/" \
        .env.example > .env
)
printf '%s\n' '.env local criado. Configure GEMINI_API_KEY nesse arquivo se for usar o chat ou analisar novos vídeos.'

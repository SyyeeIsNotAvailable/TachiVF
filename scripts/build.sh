#!/bin/sh
set -eu
cd "$(dirname "$0")/.."
sh ./gradlew --no-daemon \
    :lib-multisrc:madara:lintRelease \
    :src:fr:mangascantrad:lintRelease \
    :src:fr:mangakawaii:lintRelease \
    :src:fr:animesama:lintRelease \
    :src:fr:aniverse:lintRelease
sh ./gradlew --no-daemon \
    :src:fr:mangascantrad:assembleRelease \
    :src:fr:mangakawaii:assembleRelease \
    :src:fr:animesama:assembleRelease \
    :src:fr:aniverse:assembleRelease

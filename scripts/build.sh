#!/bin/sh
set -eu
cd "$(dirname "$0")/.."
python scripts/apply_patches.py
sh ./gradlew --no-daemon \
    :core:lintRelease \
    :lib-multisrc:madara:lintRelease \
    :src:fr:mangascantrad:lintRelease \
    :src:fr:mangakawaii:lintRelease \
    :src:fr:animesama:lintRelease \
    :src:fr:aniverse:lintRelease \
    :src:fr:japscan:lintRelease \
    :src:fr:japscan:testReleaseUnitTest
sh ./gradlew --no-daemon \
    :src:fr:mangascantrad:assembleRelease \
    :src:fr:mangakawaii:assembleRelease \
    :src:fr:animesama:assembleRelease \
    :src:fr:aniverse:assembleRelease \
    :src:fr:japscan:assembleRelease

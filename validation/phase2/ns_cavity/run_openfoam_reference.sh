#!/usr/bin/env bash
set -euo pipefail

if [[ $# -ne 1 ]]; then
    echo "usage: run_openfoam_reference.sh <absolute-reference-root>" >&2
    exit 2
fi

reference_root="$1"
if [[ ! -d "$reference_root" ]]; then
    echo "reference root does not exist: $reference_root" >&2
    exit 3
fi

for grid in 32 64 128; do
    case_root="$reference_root/grid-$grid"
    if [[ ! -d "$case_root" ]]; then
        echo "case root does not exist: $case_root" >&2
        exit 4
    fi
    (
        cd "$case_root"
        blockMesh > blockMesh.log 2>&1
        checkMesh > checkMesh.log 2>&1
        icoFoam > icoFoam.log 2>&1
    )
done

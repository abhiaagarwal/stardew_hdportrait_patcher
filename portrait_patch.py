"""
Stardew Valley HD Portrait Patcher by purplexpresso
    Last Modified 8/31/22
    Converts PyTK based HD Portrait mods for Stardew Valley into HD Portraits by swyrl compatible mod
    See usage with portrait_patch.py --help
    Licensed under GPL 3.0
"""
import argparse
from ast import parse
from enum import Enum, auto
import logging
from collections import defaultdict
import pathlib
import re as regex
from copy import deepcopy
from typing import Any, Dict, Final, List, DefaultDict

import json5


class FileParsed(Enum):
    INDIVIDUAL = auto()
    GLOBBED = auto()


def _clone_dir_tree(source: pathlib.Path, destination: pathlib.Path) -> None:
    import shutil

    shutil.copytree(
        source.resolve(),
        destination.resolve(),
        ignore=lambda directory, files: [
            file for file in files if (pathlib.Path(directory) / file).is_file()
        ],
    )


def _valid_dir(path: str, check_content=False) -> pathlib.Path:
    directory = pathlib.Path(path)
    if directory.is_dir():
        if check_content and not (directory / "content.json").is_file():
            raise argparse.ArgumentTypeError(
                f"{directory.resolve()} does not have content.json inside"
            )
        return directory
    else:
        raise argparse.ArgumentTypeError(f"{directory.resolve()} is not a valid path")


def _get_file_or_backup(file: pathlib.Path) -> pathlib.Path:
    backup_file = file.with_suffix(".bak")
    return backup_file if backup_file.is_file() else file


def _rewrite(
    file: pathlib.Path,
    json_data: Dict[str, Any],
    main_dir: pathlib.Path,
    copy_dir: pathlib.Path | None,
    force_rewrite=False,
) -> None:
    backup_file = file.with_suffix(".bak")
    if not (force_rewrite or copy_dir or backup_file.is_file()):
        file.rename(backup_file)
    with (file if copy_dir is None else copy_dir / file.relative_to(main_dir)).open(
        "w+"
    ) as new_file:
        json5.dump(json_data, new_file, quote_keys=True, indent=4)


def remove_pytk_dependency(manifest_file: pathlib.Path) -> Dict[str, Any]:
    with manifest_file.open("r") as manifest:
        manifest_dict: DefaultDict[str, Any] = defaultdict(list, json5.load(manifest))
    
    PYTK_DEPENDENCY: Final = {"UniqueID": "Platonymous.Toolkit"}
    HD_PORTRAITS_DEPENDENCY: Final = {"UniqueID": "tlitookilakin.HDPortraits"}

    dependencies: List[Dict[str, str]] = manifest_dict["Dependencies"]
    dependencies.append(HD_PORTRAITS_DEPENDENCY)
    try:
        dependencies.remove(PYTK_DEPENDENCY)
    except ValueError:
        pass
    return manifest_dict


def create_metadata_json(
    metadata_file: pathlib.Path, target_name: str
) -> Dict[str, Any] | None:
    try:
        with metadata_file.with_suffix(".pytk.json").open("r") as pytk_file:
            pytk_dict: Dict[str, Any] = json5.load(pytk_file)
    except FileNotFoundError:
        return None

    STARDEW_PORTRAIT_SIZE: Final[int] = 64

    sprite_size = int(pytk_dict["Scale"]) * STARDEW_PORTRAIT_SIZE
    asset_dict = {
        "Size": sprite_size,
        "Portrait": target_name,
    }
    # if "Animation" in pytk_dict:
    #     pytk_animation: Dict[str, int] = pytk_dict["Animation"]
    #     asset_dict["Animation"] = {
    #         "HFrames": int(
    #             pytk_animation.get("FrameWidth", sprite_size) / sprite_size
    #         ),
    #         "VFrames": int(
    #             pytk_animation.get("FrameHeight", sprite_size) / sprite_size
    #         ),
    #         "Speed": int(1000 / pytk_animation.get("FPS", 30)),
    #     }
    return asset_dict


def convert_portraits() -> None:
    parser = argparse.ArgumentParser(
        description="Converts PyTK based HD Portrait mods for Stardew Valley into HD Portraits by swyrl compatible mod",
    )
    parser.add_argument(
        "--path",
        "-p",
        required=True,
        type=lambda str: _valid_dir(str, check_content=True),
        help="Path to Content Patcher directory",
    )
    parser.add_argument(
        "--mode",
        "-m",
        default="internal",
        type=str,
        choices=["internal", "copy"],
        help="Mode of operation. [internal] changes the files inside the folder, while [copy] creates a new folder structure entirely, most useful with a VFS",
    )
    parser.add_argument(
        "--copy_dir",
        nargs="?",
        type=_valid_dir,
        help="Sets directory where copied files are outputed. Only valid if --mode copy is specified",
    )
    parser.add_argument(
        "--prefix",
        default="HDPortraitsPatch",
        type=str,
        help="Prefix on generated Targets. Do not touch unless you know what you're doing.",
    )
    args = parser.parse_args()

    content_patch_dir: Final[pathlib.Path] = args.path
    copy_dir: Final[pathlib.Path] | None = (
        (args.copy_dir if args.copy_dir is not None else content_patch_dir)
        / content_patch_dir.name
        if args.mode == "copy"
        else None
    )
    if copy_dir:
        _clone_dir_tree(content_patch_dir, copy_dir)

    hd_portraits: Final = pathlib.PurePath("Mods/HDPortraits")
    hd_portraits_patch: Final = pathlib.PurePath(f"Mods/{args.prefix}")

    content_file: Final = _get_file_or_backup(content_patch_dir / "content.json")

    content_patcher_token: Final = regex.compile(r"\{\{(.*)\}\}")
    with content_file.open("r") as content:
        content_dict: Dict[str, Any] = json5.load(content)

    metadata_item: Dict[str, Any]
    for index, metadata_item in enumerate(content_dict["Changes"].copy()):
        metadata_item["Action"] = "Load"
        portrait_item = deepcopy(metadata_item)

        portrait_name: Final = pathlib.PurePath(metadata_item["Target"]).name
        portrait_file: Final = content_patch_dir / pathlib.PurePath(
            metadata_item["FromFile"]
        )
        metadata_file: Final = portrait_file.with_suffix(".json")

        hd_portraits_target_path: Final = hd_portraits / portrait_name
        metadata_item["Target"] = hd_portraits_target_path.as_posix()
        metadata_item["FromFile"] = metadata_file.relative_to(
            content_patch_dir
        ).as_posix()

        hd_portraits_patch_target_path: Final = hd_portraits_patch / portrait_name
        portrait_item["Target"] = hd_portraits_patch_target_path.as_posix()
        portrait_item["FromFile"] = portrait_file.relative_to(
            content_patch_dir
        ).as_posix()

        content_dict["Changes"].insert(2 * index, portrait_item)

        parsed_files: Dict[str, FileParsed] = {}
        if content_patcher_token.search(portrait_file.name):
            for globbed_portrait_file in portrait_file.parent.glob("*.png"):
                if globbed_portrait_file.name in parsed_files:
                    continue

                parsed_files[globbed_portrait_file.name] = FileParsed.GLOBBED
                globbed_metadata_file = globbed_portrait_file.with_suffix(".json")

                globbed_metadata_json = create_metadata_json(
                    globbed_metadata_file, hd_portraits_patch_target_path.as_posix()
                )
                if globbed_metadata_json is None:
                    continue

                _rewrite(
                    globbed_metadata_file,
                    globbed_metadata_json,
                    content_patch_dir,
                    copy_dir,
                    force_rewrite=True,
                )
        elif portrait_file.is_file():
            if parsed_files.get(portrait_file.name) is FileParsed.INDIVIDUAL:
                continue

            parsed_files[portrait_file.name] = FileParsed.INDIVIDUAL
            metadata_json = create_metadata_json(
                metadata_file, hd_portraits_patch_target_path.as_posix()
            )
            if metadata_json is None:
                continue

            _rewrite(
                metadata_file,
                metadata_json,
                content_patch_dir,
                copy_dir,
                force_rewrite=True,
            )

    _rewrite(
        content_file,
        content_dict,
        content_patch_dir,
        copy_dir,
    )

    manifest_file: Final = _get_file_or_backup(content_patch_dir / "manifest.json")
    manifest_dict: Final = remove_pytk_dependency(manifest_file)

    _rewrite(
        manifest_file,
        manifest_dict,
        content_patch_dir,
        copy_dir,
    )

    return


if __name__ == "__main__":
    convert_portraits()

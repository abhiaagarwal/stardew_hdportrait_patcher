"""
Stardew Valley HD Portrait Patcher by purplexpresso
    Last Modified 8/31/22
    Converts PyTK based HD Portrait mods for Stardew Valley into HD Portraits by swyrl compatible mod
    See usage with portrait_patch.py --help
    Licensed under GPL 3.0
"""
import argparse
import logging
from copy import deepcopy
import pathlib
from typing import Any, Dict, List

import json5


def _add_copy_directory(
    path: pathlib.Path, main_dir: pathlib.Path, copy_dir: pathlib.Path
) -> pathlib.Path:
    return copy_dir / path.relative_to(main_dir)


def _clone_dir_tree(source: pathlib.Path, destination: pathlib.Path) -> None:
    import shutil

    shutil.copytree(
        source.resolve(),
        destination.resolve(),
        ignore=lambda directory, files: [
            file for file in files if (pathlib.Path(directory) / file).is_file()
        ],
    )


def _rewrite(file: pathlib.Path, json_data: Dict[str, Any], backup=True) -> None:
    if backup:
        file.rename(file.with_suffix(".bak"))
    with file.open("w+") as new_file:
        json5.dump(json_data, new_file, quote_keys=True, indent=4)


def remove_pytk_dependency(manifest_file: pathlib.Path) -> Dict[str, Any]:
    pytk_dependency = {"UniqueID": "Platonymous.Toolkit"}
    hd_portraits_dependency = {"UniqueID": "tlitookilakin.HDPortraits"}
    with manifest_file.open("r") as manifest:
        manifest_dict: Dict[str, Any] = json5.load(manifest)
        dependencies: List[Dict[str, str]] = manifest_dict["Dependencies"]
        dependencies.append(hd_portraits_dependency)
        try:
            dependencies.remove(pytk_dependency)
        except ValueError:
            pass
        return manifest_dict


def create_asset_json(portrait_file: pathlib.Path) -> Dict[str, Any]:
    with portrait_file.with_suffix(".pytk.json").open("r") as pytk:
        pytk_dict: Dict[str, Any] = json5.load(pytk)
        sprite_size = int(pytk_dict["Scale"]) * 64
        asset_dict = {
            "Size": sprite_size,
            "Portrait": f"Mods/HDPortraitsPatch/{portrait_file.stem}",
        }
        if "Animation" in pytk_dict:
            pytk_animation: Dict[str, int] = pytk_dict["Animation"]
            asset_dict["Animation"] = {
                "HFrames": int(
                    pytk_animation.get("FrameWidth", sprite_size) / sprite_size
                ),
                "VFrames": int(
                    pytk_animation.get("FrameHeight", sprite_size) / sprite_size
                ),
                "Speed": int(1000 / pytk_animation.get("FPS", 30)),
            }

        return asset_dict


def replace_content(content_file: pathlib.Path) -> Dict[str, Any]:
    with content_file.open("r") as content:
        content_dict: Dict[str, Any] = json5.load(content)
        item: Dict[str, Any]

        for index, metadata_item in enumerate(content_dict["Changes"].copy()):
            metadata_item["Action"] = "Load"
            portrait_item = deepcopy(metadata_item)
            portrait_name = pathlib.PurePath(metadata_item["Target"]).name
            portrait_file = pathlib.PurePath(metadata_item["FromFile"])

            metadata_item["Target"] = f"Mods/HDPortraits/{portrait_name}"
            metadata_item["FromFile"] = portrait_file.with_suffix(".json").as_posix()

            portrait_item["Target"] = f"Mods/HDPortraitsPatch/{portrait_name}"
            portrait_item["FromFile"] = portrait_file.as_posix()

            content_dict["Changes"].insert(2 * index, portrait_item)

        return content_dict


def _is_valid_dir(path: str) -> str:
    directory = pathlib.Path(path)
    if directory.is_dir():
        if (directory / "content.json").is_file():
            return path
        else:
            raise argparse.ArgumentTypeError(
                f"path: {directory.resolve()} does not have content.json inside"
            )
    else:
        raise argparse.ArgumentTypeError(
            f"path: {directory.resolve()} is not a valid path"
        )


def convert_portraits() -> None:
    parser = argparse.ArgumentParser(
        description="Converts PyTK based HD Portrait mods for Stardew Valley into HD Portraits by swyrl compatible mod",
    )
    parser.add_argument(
        "--path",
        "-p",
        default=".",
        type=_is_valid_dir,
        help="path to Content Patcher directory",
    )
    parser.add_argument(
        "--mode",
        "-m",
        default="internal",
        choices=["internal", "copy"],
        help="mode of operation. [internal] changes the files inside the folder, while [copy] creates a new folder structure entirely, most useful with a VFS",
    )
    args = parser.parse_args()

    copy: bool = args.mode == "copy"
    content_patch_dir = pathlib.Path(args.path).resolve()
    copy_dir = content_patch_dir / content_patch_dir.name

    content_file = content_patch_dir / "content.json"

    if copy:
        _clone_dir_tree(content_patch_dir, copy_dir)

    new_content = replace_content(content_file)

    if copy:
        content_file = _add_copy_directory(content_file, content_patch_dir, copy_dir)

    _rewrite(content_file, new_content, backup=not copy)

    for portrait_file in content_patch_dir.rglob("*.png"):
        portrait_pytk_file = portrait_file.with_suffix(".pytk.json")
        if not portrait_pytk_file.is_file():
            break
        portrait_data: Dict[str, Any] = create_asset_json(portrait_file)

        new_portrait_file = (
            portrait_file
            if not copy
            else _add_copy_directory(portrait_file, content_patch_dir, copy_dir)
        )

        with new_portrait_file.with_suffix(".json").open("w+") as portrait_json:
            json5.dump(portrait_data, portrait_json, quote_keys=True, indent=4)

    manifest_file = content_patch_dir / "manifest.json"

    new_manifest = remove_pytk_dependency(manifest_file)
    if copy:
        manifest_file = _add_copy_directory(manifest_file, content_patch_dir, copy_dir)
    _rewrite(manifest_file, new_manifest, backup=not copy)

    return


if __name__ == "__main__":
    convert_portraits()

"""
Stardew Valley HD Portrait Patcher by purplecoffee
    Last Modified 8/30/22
    Converts PyTK based HD Portraits into HD Portrait Mod by swyrl
    See usage with portrait_patch --help
    Licensed under GPL 3.0
"""
import argparse
import pathlib
import json5
from typing import Dict, List, Any

from pprint import pprint


def remove_pytk_dependency(manifest_file: pathlib.Path) -> Dict[str, Any]:
    pytk_dependency = {"UniqueID": "Platonymous.Toolkit"}
    hd_portraits_dependency = {"UniqueID": "tlitookilakin.HDPortraits"}
    with manifest_file.open("r") as manifest:
        manifest_dict: Dict[str, Any] = json5.load(manifest)
        dependencies: List[Dict[str, str]] = manifest_dict["Dependencies"]
        dependencies.append(hd_portraits_dependency)
        dependencies.remove(pytk_dependency)
        return manifest_dict


def create_asset_json(
    portrait_file: pathlib.Path, working_directory: pathlib.Path
) -> Dict[str, Any]:
    with portrait_file.with_suffix(".pytk.json").open("r") as pytk:
        pytk_dict: Dict[str, Any] = json5.load(pytk)
        sprite_size = int(pytk_dict["Scale"]) * 64
        asset_dict = {
            "Size": sprite_size,
            "Portrait": portrait_file.relative_to(working_directory).as_posix(),
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
                "Speed": int(1000 / pytk_animation.get("FPS", 20)),
            }

        return asset_dict


def replace_content(content_file: pathlib.Path) -> Dict[str, Any]:
    with content_file.open("r") as content:
        content_dict: Dict[str, Any] = json5.load(content)
        for item in content_dict["Changes"]:
            item["Action"] = "Load"
            item["Target"] = f"Mods/HDPortraitsPatch/{item['Target']}"
            item["FromFile"] = (
                pathlib.PurePath(item["FromFile"]).with_suffix(".json").as_posix()
            )

        return content_dict


def main() -> None:
    # working_directory = pathlib.Path(__file__).parent.absolute()
    working_directory = pathlib.Path(
        "/Users/abhiagarwal/Code/stardew_hdtexture_patcher/Test/[CP] DCBurger's High Res Portraits"
    )

    content_file = working_directory / "content.json"

    if not content_file.is_file():
        print("File needs to be located in same directory as content.json")
        return

    new_content = replace_content(content_file)
    content_file.rename(content_file.with_suffix(".bak"))
    with content_file.open("w+") as content:
        json5.dump(new_content, content, quote_keys=True, indent=4)

    for portrait_file in working_directory.rglob("*.png"):
        portrait_pytk_file = portrait_file.with_suffix(".pytk.json")
        if not portrait_pytk_file.is_file():
            break
        portrait_data: Dict[str, Any] = create_asset_json(
            portrait_file, working_directory
        )
        with portrait_file.with_suffix(".json").open("w+") as portrait_json:
            json5.dump(portrait_data, portrait_json, quote_keys=True, indent=4)

    manifest_file = working_directory / "manifest.json"

    new_manifest = remove_pytk_dependency(manifest_file)
    pprint(new_manifest)

    return


if __name__ == "__main__":
    main()

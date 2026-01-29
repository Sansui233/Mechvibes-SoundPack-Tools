from __future__ import annotations

import argparse
from pathlib import Path

from pydantic import ValidationError

from mspt.audio import generate_sourcemap
from mspt.config import generate_config
from mspt.pack import pack_target
from mspt.paths import resolve_pack_dir, resolve_sourcemap_path, resolve_target_dir


def run_prepare(input_dir: Path) -> Path:
    target_dir = resolve_target_dir(input_dir)
    return generate_sourcemap(input_dir, target_dir)


def run_build(
    input_path: Path, split: bool, rule_path: Path | None
) -> tuple[Path, Path]:
    sourcemap_path = resolve_sourcemap_path(input_path)
    target_dir = sourcemap_path.parent
    if not sourcemap_path.exists():
        raise FileNotFoundError(f"sourcemap.json not found at {sourcemap_path}")
    config_path = generate_config(
        sourcemap_path, target_dir, split=split, rule_path=rule_path
    )
    return target_dir, config_path


def build_parser() -> argparse.ArgumentParser:
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument(
        "--split",
        action="store_true",
        help="Split timing into keydown/keyup halves",
    )
    common.add_argument("--rule", help="Rule file path", default=None)
    common.add_argument(
        "--release",
        action="store_true",
        help="Auto pack to zip after build",
    )

    parser = argparse.ArgumentParser(
        description=(
            "MechvibesDX SoundPack Generator\n"
            "\n"
            "One-shot:\n"
            "  mspt -i <INPUT_DIR> --release\n"
        ),
        parents=[common],
        formatter_class=argparse.RawTextHelpFormatter,
    )
    parser.add_argument(
        "-i",
        "--input",
        required=False,
        help="Input folder or sourcemap.json (required without subcommand)",
    )

    subparsers = parser.add_subparsers(dest="command")
    prepare_parser = subparsers.add_parser(
        "prepare", help="Generate sound.ogg and sourcemap.json", parents=[common]
    )
    prepare_parser.add_argument("-i", "--input", required=True, help="Input folder")

    build_parser = subparsers.add_parser(
        "build", help="Generate config.json from sourcemap.json", parents=[common]
    )
    build_parser.add_argument(
        "-i", "--input", required=True, help="Input folder or sourcemap.json"
    )

    pack_parser = subparsers.add_parser(
        "pack", help="Zip target folder (exclude sourcemap.json)", parents=[common]
    )
    pack_parser.add_argument(
        "-i", "--input", required=True, help="Input folder or sourcemap.json"
    )

    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    if not args.command and not args.input:
        parser.error("the following arguments are required: -i/--input")
    input_path = Path(args.input)
    rule_path = Path(args.rule) if args.rule else None

    try:
        if args.command == "prepare":
            sourcemap_path = run_prepare(input_path)
            print(f"Prepare complete: {sourcemap_path}")
        elif args.command == "build":
            target_dir, config_path = run_build(
                input_path, split=args.split, rule_path=rule_path
            )
            print(f"Build complete: {config_path}")
            if args.release:
                zip_path = pack_target(target_dir)
                print(f"Pack complete: {zip_path}")
        elif args.command == "pack":
            target_dir = resolve_pack_dir(input_path)
            zip_path = pack_target(target_dir)
            print(f"Pack complete: {zip_path}")
        else:
            sourcemap_path = run_prepare(input_path)
            print(f"Prepare complete: {sourcemap_path}")
            target_dir, config_path = run_build(
                sourcemap_path, split=args.split, rule_path=rule_path
            )
            print(f"Build complete: {config_path}")
            if args.release:
                zip_path = pack_target(target_dir)
                print(f"Pack complete: {zip_path}")
    except (ValidationError, ValueError, FileNotFoundError) as exc:
        parser.error(str(exc))
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

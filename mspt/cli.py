from __future__ import annotations

import argparse
from pathlib import Path

from pydantic import ValidationError

from mspt.audio import generate_sourcemap
from mspt.config import generate_config, parse_schema_selector
from mspt.pack import pack_target
from mspt.paths import resolve_pack_dir, resolve_sourcemap_path, resolve_target_dir


def run_prepare(input_dir: Path) -> Path:
    target_dir = resolve_target_dir(input_dir)
    return generate_sourcemap(input_dir, target_dir)


def run_build(
    input_path: Path,
    split: bool,
    rule_path: Path | None,
    schema: str,
    dx_compatible: bool,
) -> tuple[Path, dict[str, Path]]:
    sourcemap_path = resolve_sourcemap_path(input_path)
    target_dir = sourcemap_path.parent
    if not sourcemap_path.exists():
        raise FileNotFoundError(f"sourcemap.json not found at {sourcemap_path}")
    config_paths = generate_config(
        sourcemap_path,
        target_dir,
        split=split,
        rule_path=rule_path,
        schema=schema,
        dx_compatible=dx_compatible,
    )
    return target_dir, config_paths


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
    common.add_argument(
        "--schema",
        default="v1|v2",
        help=(
            "Schema selector. Use `v1|v2|mvdx` combined with `|` (OR). "
            "Special value: `all` = v1|v2|mvdx. Default: v1|v2."
        ),
    )
    common.add_argument(
        "--dx-compatible",
        action="store_true",
        help=(
            'Mechvibes-dx compatibility: emit Mechvibes v1/v2 `version` as a string ("1"/"2"). '
        ),
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
    # Validate schema selector early (so argparse shows a clean error)
    parse_schema_selector(args.schema)

    try:
        if args.command == "prepare":
            sourcemap_path = run_prepare(input_path)
            print(f"Prepare complete: {sourcemap_path}")
        elif args.command == "build":
            target_dir, config_paths = run_build(
                input_path,
                split=args.split,
                rule_path=rule_path,
                schema=args.schema,
                dx_compatible=args.dx_compatible,
            )
            print(
                "Build complete: "
                + ", ".join(f"{k}={v}" for k, v in sorted(config_paths.items()))
            )
            if args.release:
                schemas = sorted(parse_schema_selector(args.schema))
                for s in schemas:
                    zip_path = pack_target(target_dir, config_variant=s)
                    print(f"Pack complete: {zip_path}")
        elif args.command == "pack":
            target_dir = resolve_pack_dir(input_path)
            schemas = sorted(parse_schema_selector(args.schema))
            for s in schemas:
                zip_path = pack_target(target_dir, config_variant=s)
                print(f"Pack complete: {zip_path}")
        else:
            sourcemap_path = run_prepare(input_path)
            print(f"Prepare complete: {sourcemap_path}")
            target_dir, config_paths = run_build(
                sourcemap_path,
                split=args.split,
                rule_path=rule_path,
                schema=args.schema,
                dx_compatible=args.dx_compatible,
            )
            print(
                "Build complete: "
                + ", ".join(f"{k}={v}" for k, v in sorted(config_paths.items()))
            )
            if args.release:
                schemas = sorted(parse_schema_selector(args.schema))
                for s in schemas:
                    zip_path = pack_target(target_dir, config_variant=s)
                    print(f"Pack complete: {zip_path}")
    except (ValidationError, ValueError, FileNotFoundError) as exc:
        parser.error(str(exc))
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
